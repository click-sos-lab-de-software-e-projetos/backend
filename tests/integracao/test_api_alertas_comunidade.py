import time
from datetime import date
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt
from app.constants import CATEGORIAS_ALERTA_COMUNIDADE
from app.db.sessao import criar_engine, obter_sessao
from app.main import app
from app.services.mapa import recalcular_regioes
from integracao.fabricas import inserir_carga_ssp, inserir_ocorrencia, inserir_regiao, inserir_usuario

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
ROTA = "/api/v1/mapa/alertas"
PONTO = {"latitude": 0.005, "longitude": 0.005}


def _token(usuario_id) -> dict[str, str]:
    payload = {"sub": str(usuario_id), "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(payload, SEGREDO_TESTE, algorithm='HS256')}"}


@pytest.fixture
def engine(url_teste):
    engine = criar_engine(url_teste)
    yield engine
    engine.dispose()


@pytest.fixture
def client(banco_migrado, engine):
    def _sessao_de_teste():
        with Session(engine) as sessao:
            yield sessao

    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_sessao] = _sessao_de_teste
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def pessoa(banco_migrado):
    with banco_migrado.begin() as conexao:
        return inserir_usuario(conexao).id


def _alertas(banco_migrado) -> list:
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text(
                "SELECT id, usuario_id, categoria, texto, ST_Y(localizacao) AS latitude, "
                "ST_X(localizacao) AS longitude FROM alertas_comunidade"
            )
        ).all()


def alerta_valido_deve_ser_gravado_no_ponto_e_aparecer_sem_token(client, banco_migrado, pessoa):
    corpo = {"categoria": "ILUMINACAO", "texto": " Rua escura ", **PONTO}

    resposta = client.post(ROTA, json=corpo, headers=_token(pessoa))

    assert resposta.status_code == 201
    criado = resposta.json()
    assert set(criado) == {"id", "categoria", "texto", "latitude", "longitude", "criado_em"}
    [linha] = _alertas(banco_migrado)
    assert (str(linha.id), linha.usuario_id, linha.categoria, linha.texto) == (
        criado["id"],
        pessoa,
        "ILUMINACAO",
        "Rua escura",
    )
    assert (linha.latitude, linha.longitude) == pytest.approx((0.005, 0.005))
    assert client.get(ROTA, params=PONTO).json() == [criado]


def alerta_de_pessoa_inexistente_deve_responder_401_sem_gravar(client, banco_migrado):
    resposta = client.post(ROTA, json={"categoria": "ASSALTO", **PONTO}, headers=_token(uuid4()))

    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"
    assert _alertas(banco_migrado) == []


def listagem_deve_trazer_so_alertas_validos_dentro_do_raio_do_mais_novo_ao_mais_antigo(client, banco_migrado, pessoa):
    with banco_migrado.begin() as conexao:
        for categoria, latitude, idade in [
            ("ASSALTO", 0.005, "1 hour"),
            ("ASSEDIO", 0.006, "5 minutes"),
            ("ILUMINACAO", 0.005, "25 hours"),
            ("MOVIMENTO", 0.2, "5 minutes"),
        ]:
            conexao.execute(
                text(
                    "INSERT INTO alertas_comunidade (usuario_id, categoria, localizacao, criado_em) "
                    "VALUES (:u, :c, ST_SetSRID(ST_MakePoint(0.005, :lat), 4326), now() - CAST(:idade AS interval))"
                ),
                {"u": pessoa, "c": categoria, "lat": latitude, "idade": idade},
            )

    resposta = client.get(ROTA, params=PONTO | {"raio": 5000})

    assert resposta.status_code == 200
    assert [alerta["categoria"] for alerta in resposta.json()] == ["ASSEDIO", "ASSALTO"]


def _estado_do_mapa(client, banco_migrado, engine):
    with Session(engine) as sessao:
        recalcular_regioes(sessao)
        sessao.commit()
    with banco_migrado.connect() as conexao:
        scores = conexao.execute(
            text("SELECT id_publico, score_oficial, score_final, cor_hex FROM regioes_seguranca ORDER BY id_publico")
        ).all()
    resposta = client.get("/api/v1/mapa/regioes", params=PONTO)
    assert resposta.status_code == 200
    return scores, resposta.json()


def alertas_nao_devem_alterar_score_nem_a_consulta_das_regioes(client, banco_migrado, engine, pessoa):
    with banco_migrado.begin() as conexao:
        inserir_regiao(conexao, 0.0, 0.0, 0.01, 0.01)
        inserir_regiao(conexao, 0.01, 0.0, 0.02, 0.01)
        carga = inserir_carga_ssp(conexao).id
        inserir_ocorrencia(conexao, carga, 0.005, 0.005, peso=3, data_ocorrencia=date(2026, 3, 1))
        inserir_ocorrencia(conexao, carga, 0.005, 0.015, peso=1, data_ocorrencia=date(2026, 3, 1))
    antes = _estado_do_mapa(client, banco_migrado, engine)

    for longitude in (0.005, 0.015):
        for categoria in CATEGORIAS_ALERTA_COMUNIDADE:
            corpo = {"categoria": categoria, "texto": "relato", "latitude": 0.005, "longitude": longitude}
            assert client.post(ROTA, json=corpo, headers=_token(pessoa)).status_code == 201

    assert _estado_do_mapa(client, banco_migrado, engine) == antes
