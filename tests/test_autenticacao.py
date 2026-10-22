import time
from typing import Annotated
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import obter_segredo_jwt, obter_usuario_id
from app.constants import NOME_VARIAVEL_SEGREDO_JWT

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
USUARIO_ID = uuid4()

app_teste = FastAPI()


@app_teste.get("/protegida")
def rota_protegida(usuario_id: Annotated[UUID, Depends(obter_usuario_id)]) -> dict[str, str]:
    return {"usuario_id": str(usuario_id)}


@pytest.fixture
def client():
    app_teste.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    yield TestClient(app_teste)
    app_teste.dependency_overrides.clear()


def gerar_token(payload: dict, segredo: str = SEGREDO_TESTE) -> str:
    return jwt.encode(payload, segredo, algorithm="HS256")


def payload_valido(expira_em: int = 300) -> dict:
    return {"sub": str(USUARIO_ID), "exp": int(time.time()) + expira_em}


def requisitar(client, token: str | None = None):
    cabecalhos = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/protegida", headers=cabecalhos)


def obter_usuario_id_com_token_valido_deve_retornar_o_uuid_do_sub(client):
    resposta = requisitar(client, gerar_token(payload_valido()))
    assert resposta.status_code == 200
    assert resposta.json() == {"usuario_id": str(USUARIO_ID)}


def obter_usuario_id_sem_token_deve_responder_401_com_cabecalho_bearer(client):
    resposta = requisitar(client)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def obter_usuario_id_com_token_de_outro_segredo_deve_responder_401(client):
    token = gerar_token(payload_valido(), segredo="outro-segredo-qualquer-com-32-bytes!")
    assert requisitar(client, token).status_code == 401


def obter_usuario_id_com_token_expirado_deve_responder_401(client):
    assert requisitar(client, gerar_token(payload_valido(expira_em=-10))).status_code == 401


def obter_usuario_id_com_token_sem_sub_deve_responder_401(client):
    token = gerar_token({"exp": int(time.time()) + 300})
    assert requisitar(client, token).status_code == 401


def obter_usuario_id_com_sub_que_nao_e_uuid_deve_responder_401(client):
    token = gerar_token({"sub": "nao-e-uuid", "exp": int(time.time()) + 300})
    assert requisitar(client, token).status_code == 401


def obter_segredo_jwt_com_variavel_definida_deve_retornar_o_valor(monkeypatch):
    monkeypatch.setenv(NOME_VARIAVEL_SEGREDO_JWT, SEGREDO_TESTE)
    assert obter_segredo_jwt() == SEGREDO_TESTE


def obter_segredo_jwt_sem_variavel_deve_lancar_erro(monkeypatch):
    monkeypatch.delenv(NOME_VARIAVEL_SEGREDO_JWT, raising=False)
    with pytest.raises(RuntimeError):
        obter_segredo_jwt()


def obter_usuario_id_com_segredo_do_ambiente_deve_aceitar_token_assinado_com_ele(
    monkeypatch,
):
    monkeypatch.setenv(NOME_VARIAVEL_SEGREDO_JWT, SEGREDO_TESTE)
    resposta = requisitar(TestClient(app_teste), gerar_token(payload_valido()))
    assert resposta.status_code == 200
    assert resposta.json() == {"usuario_id": str(USUARIO_ID)}
