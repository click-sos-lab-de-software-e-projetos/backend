import time
from datetime import date
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt
from app.constants import CATEGORIAS_FEEDBACK
from app.db.sessao import criar_engine, obter_sessao
from app.main import app
from app.services.mapa import recalcular_regioes
from integracao.fabricas import inserir_carga_ssp, inserir_ocorrencia, inserir_regiao, inserir_usuario

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
PONTO = {"latitude": 0.005, "longitude": 0.005}


def _token(usuario_id) -> dict[str, str]:
    payload = {"sub": str(usuario_id), "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(payload, SEGREDO_TESTE, algorithm='HS256')}"}


def _rota(id_publico: str) -> str:
    return f"/api/v1/mapa/regioes/{id_publico}/feedbacks"


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
def pessoa_e_distrito(banco_migrado):
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao).id
        regiao = inserir_regiao(conexao, 0.0, 0.0, 0.01, 0.01)
    return usuario, regiao


def _feedbacks(banco_migrado) -> list:
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text("SELECT id, usuario_id, regiao_id, categoria, texto, status FROM feedbacks_comunidade")
        ).all()


def feedback_valido_deve_ser_gravado_como_pendente(client, banco_migrado, pessoa_e_distrito):
    usuario, regiao = pessoa_e_distrito

    resposta = client.post(
        _rota(regiao.id_publico), json={"categoria": "ILUMINACAO", "texto": " Rua escura "}, headers=_token(usuario)
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert set(corpo) == {"id", "regiao_id", "categoria", "status", "criado_em"}
    assert (corpo["regiao_id"], corpo["categoria"], corpo["status"]) == (regiao.id_publico, "ILUMINACAO", "PENDENTE")
    [linha] = _feedbacks(banco_migrado)
    assert (str(linha.id), linha.usuario_id, linha.regiao_id) == (corpo["id"], usuario, regiao.id)
    assert (linha.categoria, linha.texto, linha.status) == ("ILUMINACAO", "Rua escura", "PENDENTE")


def feedback_para_distrito_desconhecido_deve_responder_404_sem_gravar(client, banco_migrado, pessoa_e_distrito):
    usuario, _ = pessoa_e_distrito

    resposta = client.post(_rota("distrito-inexistente"), json={"categoria": "ASSALTO"}, headers=_token(usuario))

    assert resposta.status_code == 404
    assert _feedbacks(banco_migrado) == []


def feedback_de_pessoa_inexistente_deve_responder_401_sem_gravar(client, banco_migrado, pessoa_e_distrito):
    _, regiao = pessoa_e_distrito

    resposta = client.post(_rota(regiao.id_publico), json={"categoria": "ASSALTO"}, headers=_token(uuid4()))

    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"
    assert _feedbacks(banco_migrado) == []


def _estado_do_mapa(client, banco_migrado, engine, usuario):
    with Session(engine) as sessao:
        recalcular_regioes(sessao)
        sessao.commit()
    with banco_migrado.connect() as conexao:
        scores = conexao.execute(
            text("SELECT id_publico, score_oficial, score_final, cor_hex FROM regioes_seguranca ORDER BY id_publico")
        ).all()
    resposta = client.get("/api/v1/mapa/regioes", params=PONTO, headers=_token(usuario))
    assert resposta.status_code == 200
    return scores, resposta.json()


def feedback_nao_deve_alterar_score_nem_a_consulta_do_mapa(client, banco_migrado, engine, pessoa_e_distrito):
    usuario, regiao = pessoa_e_distrito
    with banco_migrado.begin() as conexao:
        vizinho = inserir_regiao(conexao, 0.01, 0.0, 0.02, 0.01)
        carga = inserir_carga_ssp(conexao).id
        inserir_ocorrencia(conexao, carga, 0.005, 0.005, peso=3, data_ocorrencia=date(2026, 3, 1))
        inserir_ocorrencia(conexao, carga, 0.005, 0.015, peso=1, data_ocorrencia=date(2026, 3, 1))
    antes = _estado_do_mapa(client, banco_migrado, engine, usuario)

    for id_publico in (regiao.id_publico, vizinho.id_publico):
        for categoria in CATEGORIAS_FEEDBACK:
            corpo = {"categoria": categoria, "texto": "relato"}
            assert client.post(_rota(id_publico), json=corpo, headers=_token(usuario)).status_code == 201

    assert _estado_do_mapa(client, banco_migrado, engine, usuario) == antes
