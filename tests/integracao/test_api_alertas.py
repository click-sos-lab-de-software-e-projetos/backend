import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt
from app.constants import LIMITE_MENSAGEM_SOS
from app.db.sessao import criar_engine, obter_sessao
from app.main import app
from integracao.fabricas import inserir_contato, inserir_usuario

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
ROTA = "/api/v1/sos/alertas"
# Coordenadas sem significado geográfico, como pede o README.
LATITUDE, LONGITUDE = 12.345678, 65.432198
CORPO = {"latitude": LATITUDE, "longitude": LONGITUDE}


def _token(usuario_id) -> dict[str, str]:
    payload = {"sub": str(usuario_id), "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(payload, SEGREDO_TESTE, algorithm='HS256')}"}


@pytest.fixture
def engine_app(banco_migrado, url_teste):
    engine = criar_engine(url_teste)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine_app):
    def _sessao_de_teste():
        with Session(engine_app, expire_on_commit=False) as sessao:
            yield sessao

    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_sessao] = _sessao_de_teste
    yield TestClient(app)
    app.dependency_overrides.clear()


def _usuario(banco_migrado, *contatos: dict):
    """Cria uma pessoa e os contatos descritos (padrão: ativo e sem consentimento)."""
    with banco_migrado.begin() as conexao:
        usuario_id = inserir_usuario(conexao).id
        for contato in contatos:
            inserir_contato(conexao, usuario_id, **contato)
    return usuario_id


APTO = {"consentido_em": datetime(2026, 1, 1, tzinfo=UTC)}


@pytest.fixture
def ana(banco_migrado):
    return _usuario(banco_migrado, APTO)


def _alertas(banco_migrado) -> list:
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text(
                "SELECT id, usuario_id, mensagem, status_envio, tentativas, "
                "ST_X(localizacao) AS lng, ST_Y(localizacao) AS lat, "
                "ST_SRID(localizacao) AS srid FROM alertas_sos"
            )
        ).all()


def _contar(banco_migrado, tabela: str) -> int:
    with banco_migrado.connect() as conexao:
        return conexao.execute(text(f"SELECT count(*) FROM {tabela}")).scalar_one()


# --- criação bem-sucedida --------------------------------------------------


def criar_alerta_deve_responder_201_com_id_status_e_data(client, ana):
    resposta = client.post(ROTA, json={**CORPO, "mensagem": "Preciso de ajuda"}, headers=_token(ana))

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert set(corpo) == {"id", "status_envio", "criado_em"}
    assert corpo["status_envio"] == "PENDENTE"


def criar_alerta_deve_gravar_ponto_mensagem_e_dono_do_token(client, banco_migrado, ana):
    resposta = client.post(ROTA, json={**CORPO, "mensagem": "Preciso de ajuda"}, headers=_token(ana))

    (alerta,) = _alertas(banco_migrado)
    assert str(alerta.id) == resposta.json()["id"]
    assert alerta.usuario_id == ana
    assert alerta.mensagem == "Preciso de ajuda"
    assert (alerta.lat, alerta.lng, alerta.srid) == (LATITUDE, LONGITUDE, 4326)


def criar_alerta_nao_deve_disparar_envio(client, banco_migrado, ana):
    client.post(ROTA, json=CORPO, headers=_token(ana))

    (alerta,) = _alertas(banco_migrado)
    assert (alerta.status_envio, alerta.tentativas) == ("PENDENTE", 0)
    assert _contar(banco_migrado, "tentativas_envio_sos") == 0


@pytest.mark.parametrize("corpo", [CORPO, {**CORPO, "mensagem": ""}, {**CORPO, "mensagem": "   "}])
def criar_alerta_sem_mensagem_deve_gravar_null_para_o_sos_04_usar_a_padrao(
    client, banco_migrado, ana, corpo
):
    assert client.post(ROTA, json=corpo, headers=_token(ana)).status_code == 201
    assert _alertas(banco_migrado)[0].mensagem is None


def criar_alerta_com_mensagem_no_limite_deve_gravar_inteira(client, banco_migrado, ana):
    corpo = {**CORPO, "mensagem": "a" * LIMITE_MENSAGEM_SOS}
    assert client.post(ROTA, json=corpo, headers=_token(ana)).status_code == 201
    assert len(_alertas(banco_migrado)[0].mensagem) == LIMITE_MENSAGEM_SOS


def criar_alerta_com_um_contato_apto_entre_inaptos_deve_ser_aceito(client, banco_migrado):
    usuario = _usuario(banco_migrado, {}, {**APTO, "ativo": False}, APTO)
    assert client.post(ROTA, json=CORPO, headers=_token(usuario)).status_code == 201


# --- usuário sem contatos aptos --------------------------------------------


@pytest.mark.parametrize(
    "contatos",
    [
        pytest.param((), id="sem-contatos"),
        pytest.param(({**APTO, "ativo": False},), id="so-inativo-consentido"),
        pytest.param(({},), id="so-ativo-sem-consentimento"),
    ],
)
def criar_alerta_sem_contato_ativo_e_consentido_deve_responder_422_sem_gravar(
    client, banco_migrado, contatos
):
    usuario = _usuario(banco_migrado, *contatos)

    resposta = client.post(ROTA, json=CORPO, headers=_token(usuario))

    assert resposta.status_code == 422
    assert "contato" in resposta.json()["detail"].lower()
    assert _contar(banco_migrado, "alertas_sos") == 0


def contato_apto_de_outra_pessoa_nao_deve_habilitar_o_alerta(client, banco_migrado, ana):
    sem_contatos = _usuario(banco_migrado)
    assert client.post(ROTA, json=CORPO, headers=_token(sem_contatos)).status_code == 422


# --- validação e autenticação ----------------------------------------------


@pytest.mark.parametrize(
    "corpo",
    [
        {**CORPO, "latitude": 90.1},
        {**CORPO, "longitude": -180.1},
        {"latitude": LATITUDE},
        {**CORPO, "mensagem": "a" * (LIMITE_MENSAGEM_SOS + 1)},
        {**CORPO, "usuario_id": str(uuid4())},
    ],
    ids=["latitude", "longitude", "sem-longitude", "mensagem-longa", "usuario-id"],
)
def criar_alerta_com_corpo_invalido_deve_responder_422_sem_gravar(
    client, banco_migrado, ana, corpo
):
    assert client.post(ROTA, json=corpo, headers=_token(ana)).status_code == 422
    assert _contar(banco_migrado, "alertas_sos") == 0


def criar_alerta_com_token_de_usuario_inexistente_deve_responder_401(client, banco_migrado):
    resposta = client.post(ROTA, json=CORPO, headers=_token(uuid4()))
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"
    assert _contar(banco_migrado, "alertas_sos") == 0


# --- privacidade -----------------------------------------------------------


def criar_alerta_nao_deve_registrar_coordenadas_nem_mensagem_em_logs(client, ana, caplog):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")

    client.post(ROTA, json={**CORPO, "mensagem": "Texto Sigiloso"}, headers=_token(ana))

    assert "INSERT INTO alertas_sos" in caplog.text, "o SQL precisa ser capturado"
    for dado in ("12.345678", "65.432198", "Texto Sigiloso"):
        assert dado not in caplog.text
