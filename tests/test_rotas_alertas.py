from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import obter_segredo_jwt
from app.db.sessao import obter_sessao
from app.main import app

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
ROTA = "/api/v1/sos/alertas"
CORPO = {"latitude": 0.25, "longitude": 0.75}


def _sessao_proibida():
    raise AssertionError("A rota tocou no banco antes de autenticar.")


@pytest.fixture
def client():
    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_sessao] = _sessao_proibida
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("cabecalhos", [{}, {"Authorization": "Bearer nao-e-jwt"}])
def criar_alerta_sem_token_valido_deve_responder_401_sem_tocar_no_banco(client, cabecalhos):
    resposta = client.post(ROTA, json=CORPO, headers=cabecalhos)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def _operacao():
    return app.openapi()["paths"][ROTA]["post"]


def openapi_deve_documentar_respostas_201_401_e_422_do_alerta():
    respostas = _operacao()["responses"]
    assert {"201", "401", "422"} <= set(respostas)
    assert respostas["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/AlertaCriadoResposta"
    )
    assert "contato" in respostas["422"]["description"].lower()


def openapi_deve_documentar_corpo_e_bearer_do_alerta():
    operacao = _operacao()
    corpo = operacao["requestBody"]["content"]["application/json"]["schema"]
    assert corpo["$ref"].endswith("/CriarAlertaRequisicao")
    assert {"HTTPBearer": []} in operacao["security"]


@pytest.mark.parametrize("cabecalhos", [{}, {"Authorization": "Bearer nao-e-jwt"}])
def consultar_alerta_sem_token_valido_deve_responder_401_sem_tocar_no_banco(client, cabecalhos):
    resposta = client.get(f"{ROTA}/{uuid4()}", headers=cabecalhos)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def openapi_deve_documentar_respostas_200_401_404_e_422_da_consulta():
    operacao = app.openapi()["paths"][f"{ROTA}/{{alerta_id}}"]["get"]
    respostas = operacao["responses"]
    assert {"200", "401", "404", "422"} <= set(respostas)
    assert respostas["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/AlertaStatusResposta"
    )
    assert {"HTTPBearer": []} in operacao["security"]


@pytest.mark.parametrize("cabecalhos", [{}, {"Authorization": "Bearer nao-e-jwt"}])
def listar_alertas_sem_token_valido_deve_responder_401_sem_tocar_no_banco(client, cabecalhos):
    resposta = client.get(ROTA, headers=cabecalhos)
    assert resposta.status_code == 401


def openapi_deve_documentar_a_lista_de_alertas():
    operacao = app.openapi()["paths"][ROTA]["get"]
    assert {"200", "401", "422"} <= set(operacao["responses"])
    esquema = operacao["responses"]["200"]["content"]["application/json"]["schema"]
    assert esquema["items"]["$ref"].endswith("/AlertaStatusResposta")
    assert {"HTTPBearer": []} in operacao["security"]
