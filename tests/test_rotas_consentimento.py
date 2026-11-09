from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import obter_segredo_jwt, obter_url_consentimento
from app.constants import NOME_VARIAVEL_URL_CONSENTIMENTO
from app.db.sessao import obter_sessao
from app.main import app

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"


class _SessaoProibida:
    def __getattr__(self, nome):
        raise AssertionError("A rota consultou o banco antes de validar a entrada.")


@pytest.fixture
def client():
    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_sessao] = _SessaoProibida
    yield TestClient(app)
    app.dependency_overrides.clear()


def gerar_link_sem_token_deve_responder_401_sem_tocar_no_banco(client):
    resposta = client.post(f"/api/v1/contatos/{uuid4()}/consentimento")
    assert resposta.status_code == 401


@pytest.mark.parametrize("caminho", ["/api/v1/consentimento/pedido", "/api/v1/consentimento/resposta"])
def rotas_publicas_com_token_mal_formado_deve_responder_422_sem_consultar_o_banco(client, caminho):
    resposta = client.post(caminho, json={"token": "curto", "aceito": True})
    assert resposta.status_code == 422


def openapi_deve_documentar_rotas_publicas_sem_bearer_e_link_com_bearer():
    caminhos = app.openapi()["paths"]
    for caminho in ("/api/v1/consentimento/pedido", "/api/v1/consentimento/resposta"):
        operacao = caminhos[caminho]["post"]
        assert "security" not in operacao
        assert "404" in operacao["responses"]
    link = caminhos["/api/v1/contatos/{contato_id}/consentimento"]["post"]
    assert {"HTTPBearer": []} in link["security"]
    assert {"401", "404", "409"} <= set(link["responses"])


def url_consentimento_deve_vir_da_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv(NOME_VARIAVEL_URL_CONSENTIMENTO, "https://pagina.example.com/")
    assert obter_url_consentimento() == "https://pagina.example.com/"


def url_consentimento_ausente_deve_falhar_com_mensagem_clara(monkeypatch):
    monkeypatch.delenv(NOME_VARIAVEL_URL_CONSENTIMENTO, raising=False)
    with pytest.raises(RuntimeError, match=NOME_VARIAVEL_URL_CONSENTIMENTO):
        obter_url_consentimento()
