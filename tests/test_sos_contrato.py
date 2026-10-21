import time
from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.deps import obter_segredo_jwt
from app.api.v1.sos import obter_servico_alertas
from app.main import app
from app.schemas.sos import AlertaCriadoResposta

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
URL = "/api/v1/sos/alertas"
USUARIO_ID = uuid4()
CORPO_VALIDO = {"latitude": -23.55, "longitude": -46.63}  # exemplo genérico da documentação


class ServicoFake:
    """Substitui o serviço real (SOS-03) e registra as chamadas."""

    def __init__(self) -> None:
        self.chamadas = []

    def criar_alerta(self, usuario_id, dados):
        self.chamadas.append((usuario_id, dados))
        return AlertaCriadoResposta(
            id=uuid4(), status_envio="PENDENTE", criado_em=datetime.now(timezone.utc)
        )


@pytest.fixture
def servico():
    fake = ServicoFake()
    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_servico_alertas] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client(servico):
    return TestClient(app)


def gerar_token(usuario_id=USUARIO_ID, segredo=SEGREDO_TESTE, expira_em=300) -> str:
    payload = {"sub": str(usuario_id), "exp": int(time.time()) + expira_em}
    return jwt.encode(payload, segredo, algorithm="HS256")


def cabecalho(token: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or gerar_token()}"}


# --- Caminho feliz ---------------------------------------------------------

def test_cria_alerta_retorna_201_e_usa_usuario_do_token(client, servico):
    resposta = client.post(URL, json=CORPO_VALIDO, headers=cabecalho())

    assert resposta.status_code == 201
    assert resposta.json()["status_envio"] == "PENDENTE"
    usuario_id, _ = servico.chamadas[0]
    assert usuario_id == USUARIO_ID


def test_resposta_nao_devolve_coordenadas(client):
    resposta = client.post(URL, json=CORPO_VALIDO, headers=cabecalho())
    assert resposta.status_code == 201
    assert "latitude" not in resposta.json() and "longitude" not in resposta.json()

# --- Mensagem --------------------------------------------------------------

def test_aceita_mensagem_com_255_caracteres(client):
    corpo = {**CORPO_VALIDO, "mensagem": "a" * 255}
    assert client.post(URL, json=corpo, headers=cabecalho()).status_code == 201


def test_rejeita_mensagem_com_256_caracteres(client, servico):
    corpo = {**CORPO_VALIDO, "mensagem": "a" * 256}
    assert client.post(URL, json=corpo, headers=cabecalho()).status_code == 422
    assert servico.chamadas == []


def test_mensagem_e_opcional(client):
    assert client.post(URL, json=CORPO_VALIDO, headers=cabecalho()).status_code == 201


# --- Coordenadas -----------------------------------------------------------

@pytest.mark.parametrize(
    ("campo", "valor"),
    [("latitude", 90.1), ("latitude", -90.1), ("longitude", 180.1), ("longitude", -180.1)],
)
def test_rejeita_coordenada_fora_do_intervalo(client, campo, valor):
    corpo = {**CORPO_VALIDO, campo: valor}
    assert client.post(URL, json=corpo, headers=cabecalho()).status_code == 422


@pytest.mark.parametrize("campo", ["latitude", "longitude"])
def test_exige_coordenadas(client, campo):
    corpo = {k: v for k, v in CORPO_VALIDO.items() if k != campo}
    assert client.post(URL, json=corpo, headers=cabecalho()).status_code == 422


def test_rejeita_usuario_id_enviado_no_corpo(client):
    """Regra 01: o usuário vem SOMENTE do token."""
    corpo = {**CORPO_VALIDO, "usuario_id": str(uuid4())}
    assert client.post(URL, json=corpo, headers=cabecalho()).status_code == 422


# --- Autenticação ----------------------------------------------------------

def test_sem_token_retorna_401(client):
    resposta = client.post(URL, json=CORPO_VALIDO)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def test_token_de_outro_segredo_retorna_401(client):
    token = gerar_token(segredo="outro-segredo-qualquer-com-32-bytes!")
    assert client.post(URL, json=CORPO_VALIDO, headers=cabecalho(token)).status_code == 401


def test_token_expirado_retorna_401(client):
    token = gerar_token(expira_em=-10)
    assert client.post(URL, json=CORPO_VALIDO, headers=cabecalho(token)).status_code == 401


def test_token_sem_sub_retorna_401(client):
    """Regra 09: token sem identidade da pessoa usuária é inválido."""
    token = jwt.encode({"exp": int(time.time()) + 300}, SEGREDO_TESTE, algorithm="HS256")
    assert client.post(URL, json=CORPO_VALIDO, headers=cabecalho(token)).status_code == 401


# --- OpenAPI ---------------------------------------------------------------

def test_openapi_documenta_respostas_e_limite(client):
    esquema = client.get("/openapi.json").json()
    respostas = esquema["paths"][URL]["post"]["responses"]
    assert {"201", "401", "422"} <= set(respostas)

    mensagem = esquema["components"]["schemas"]["CriarAlertaRequisicao"]["properties"]["mensagem"]
    assert any(opcao.get("maxLength") == 255 for opcao in mensagem["anyOf"])