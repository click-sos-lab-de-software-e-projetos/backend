from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import obter_segredo_jwt
from app.db.sessao import obter_sessao
from app.main import app

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
ID = uuid4()
ROTAS = [
    ("GET", "/api/v1/contatos", None),
    ("POST", "/api/v1/contatos", {"nome": "Ana", "telefone_whatsapp": "+5500900000000"}),
    ("GET", f"/api/v1/contatos/{ID}", None),
    ("PATCH", f"/api/v1/contatos/{ID}", {"ativo": False}),
    ("DELETE", f"/api/v1/contatos/{ID}", None),
]


def _sessao_proibida():
    raise AssertionError("A rota tocou no banco antes de autenticar.")


@pytest.fixture
def client():
    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_sessao] = _sessao_proibida
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(("metodo", "caminho", "corpo"), ROTAS)
def rotas_contatos_sem_token_deve_responder_401_sem_tocar_no_banco(
    client, metodo, caminho, corpo
):
    resposta = client.request(metodo, caminho, json=corpo)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(("metodo", "caminho", "corpo"), ROTAS)
def rotas_contatos_com_token_invalido_deve_responder_401(client, metodo, caminho, corpo):
    cabecalhos = {"Authorization": "Bearer token-que-nao-e-jwt"}
    resposta = client.request(metodo, caminho, json=corpo, headers=cabecalhos)
    assert resposta.status_code == 401


def openapi_deve_documentar_as_rotas_de_contatos_com_bearer():
    caminhos = app.openapi()["paths"]
    colecao, item = caminhos["/api/v1/contatos"], caminhos["/api/v1/contatos/{contato_id}"]
    assert set(colecao) == {"get", "post"}
    assert set(item) == {"get", "patch", "delete"}
    for operacao in [*colecao.values(), *item.values()]:
        assert {"HTTPBearer": []} in operacao["security"]
        assert "401" in operacao["responses"]


def openapi_deve_documentar_o_conflito_do_quarto_contato_ativo():
    caminhos = app.openapi()["paths"]
    assert "409" in caminhos["/api/v1/contatos"]["post"]["responses"]
    assert "409" in caminhos["/api/v1/contatos/{contato_id}"]["patch"]["responses"]
