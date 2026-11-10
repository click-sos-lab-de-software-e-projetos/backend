import time
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.deps import obter_segredo_jwt, obter_validade_jwt_min
from app.constants import EXPIRACAO_JWT_PADRAO_MIN, NOME_VARIAVEL_EXPIRACAO_JWT
from app.db.sessao import obter_sessao
from app.main import app
from app.services import auth as servico

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"


class _SessaoProibida:
    def __getattr__(self, nome):
        raise AssertionError("A rota usou o banco com um corpo inválido.")


@pytest.fixture
def client():
    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
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


ME = "/api/v1/auth/me"
SENHA_ME = "/api/v1/auth/me/senha"


def _token() -> dict[str, str]:
    payload = {"sub": str(uuid4()), "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(payload, SEGREDO_TESTE, algorithm='HS256')}"}


def _servico_proibido(*_):
    raise AssertionError("A rota chamou o serviço com corpo inválido.")


@pytest.mark.parametrize(
    ("metodo", "caminho", "corpo"),
    [
        ("patch", ME, {"nome_completo": "Outro Nome"}),
        ("post", SENHA_ME, {"senha_atual": "atual", "senha_nova": "senha-nova-123"}),
    ],
)
def alterar_perfil_ou_senha_sem_token_deve_responder_401_sem_usar_o_banco(client, metodo, caminho, corpo):
    resposta = client.request(metodo, caminho, json=corpo)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("metodo", "caminho", "corpo"),
    [
        ("patch", ME, {}),
        ("patch", ME, {"email": "outra@example.com"}),
        ("patch", ME, {"telefone_pessoal": None}),
        ("post", SENHA_ME, {"senha_atual": "atual", "senha_nova": "curta"}),
    ],
)
def alterar_perfil_ou_senha_com_corpo_invalido_deve_responder_422_sem_chamar_o_servico(
    client, metodo, caminho, corpo, monkeypatch
):
    app.dependency_overrides[obter_sessao] = lambda: None
    monkeypatch.setattr(servico, "atualizar_perfil", _servico_proibido, raising=False)
    monkeypatch.setattr(servico, "trocar_senha", _servico_proibido, raising=False)

    assert client.request(metodo, caminho, json=corpo, headers=_token()).status_code == 422


def openapi_deve_documentar_edicao_do_perfil_e_troca_de_senha_como_rotas_privadas():
    caminhos = app.openapi()["paths"]
    patch = caminhos[ME]["patch"]
    senha = caminhos[SENHA_ME]["post"]
    assert {"200", "401", "422"} <= set(patch["responses"])
    assert {"204", "400", "401", "422"} <= set(senha["responses"])
    assert {"HTTPBearer": []} in patch["security"]
    assert {"HTTPBearer": []} in senha["security"]
