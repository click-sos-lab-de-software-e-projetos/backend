import pytest
from fastapi.testclient import TestClient

from app.api.deps import obter_segredo_jwt, obter_validade_jwt_min
from app.constants import EXPIRACAO_JWT_PADRAO_MIN, NOME_VARIAVEL_EXPIRACAO_JWT
from app.db.sessao import obter_sessao
from app.main import app


class _SessaoProibida:
    def __getattr__(self, nome):
        raise AssertionError("A rota usou o banco com um corpo inválido.")


@pytest.fixture
def client():
    app.dependency_overrides[obter_segredo_jwt] = lambda: "segredo-apenas-para-testes-com-32-bytes"
    app.dependency_overrides[obter_sessao] = _SessaoProibida
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("caminho", "corpo"),
    [
        ("/api/v1/auth/cadastro", {"email": "pessoa@example.com", "senha": "curta"}),
        ("/api/v1/auth/login", {"email": "nao-e-email", "senha": "senha-ficticia"}),
    ],
)
def rotas_auth_com_corpo_invalido_deve_responder_422_sem_usar_o_banco(
    client, caminho, corpo
):
    assert client.post(caminho, json=corpo).status_code == 422


def openapi_deve_documentar_cadastro_e_login_como_rotas_publicas():
    caminhos = app.openapi()["paths"]
    cadastro = caminhos["/api/v1/auth/cadastro"]["post"]
    login = caminhos["/api/v1/auth/login"]["post"]
    assert {"201", "409", "422"} <= set(cadastro["responses"])
    assert {"200", "401", "422"} <= set(login["responses"])
    assert "security" not in cadastro
    assert "security" not in login


def obter_validade_jwt_min_sem_variavel_deve_usar_24_horas(monkeypatch):
    monkeypatch.delenv(NOME_VARIAVEL_EXPIRACAO_JWT, raising=False)
    assert obter_validade_jwt_min() == EXPIRACAO_JWT_PADRAO_MIN == 24 * 60


def obter_validade_jwt_min_com_variavel_deve_usar_o_valor(monkeypatch):
    monkeypatch.setenv(NOME_VARIAVEL_EXPIRACAO_JWT, "15")
    assert obter_validade_jwt_min() == 15


@pytest.mark.parametrize("valor", ["0", "-5", "abc"])
def obter_validade_jwt_min_com_valor_invalido_deve_lancar_erro(monkeypatch, valor):
    monkeypatch.setenv(NOME_VARIAVEL_EXPIRACAO_JWT, valor)
    with pytest.raises(RuntimeError):
        obter_validade_jwt_min()


def me_sem_token_deve_responder_401_sem_usar_o_banco(client):
    resposta = client.get("/api/v1/auth/me")
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def openapi_deve_documentar_me_como_rota_privada():
    me = app.openapi()["paths"]["/api/v1/auth/me"]["get"]
    assert {"HTTPBearer": []} in me["security"]
    assert "401" in me["responses"]
