import time
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.deps import obter_segredo_jwt
from app.db.sessao import obter_sessao
from app.main import app
from app.services import mapa as servico

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
ROTA = "/api/v1/mapa/regioes"
PONTO = {"latitude": 0.005, "longitude": 0.005}


def _sessao_proibida():
    raise AssertionError("A rota tocou no banco antes de validar o token.")


def _consulta_proibida(*_):
    raise AssertionError("A rota consultou as regiões com parâmetro inválido.")


def _token() -> dict[str, str]:
    payload = {"sub": str(uuid4()), "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(payload, SEGREDO_TESTE, algorithm='HS256')}"}


@pytest.fixture
def client():
    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_sessao] = _sessao_proibida
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("cabecalhos", [{}, {"Authorization": "Bearer nao-e-jwt"}])
def consultar_regioes_sem_token_valido_deve_responder_401_sem_tocar_no_banco(client, cabecalhos):
    resposta = client.get(ROTA, params=PONTO, headers=cabecalhos)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "parametros",
    [
        {"longitude": 0.005},
        {"latitude": 0.005},
        {**PONTO, "latitude": 90.1},
        {**PONTO, "longitude": -180.1},
        {**PONTO, "raio": 0},
        {**PONTO, "raio": 10001},
        {**PONTO, "raio": "longe"},
        {**PONTO, "latitude": "nan"},
    ],
)
def consultar_regioes_com_parametro_invalido_deve_responder_422_sem_consultar_regioes(
    client, parametros, monkeypatch
):
    # O FastAPI cria a sessão mesmo com parâmetro inválido, mas ela só conecta no 1º uso.
    app.dependency_overrides[obter_sessao] = lambda: None
    monkeypatch.setattr(servico, "listar_regioes_proximas", _consulta_proibida)

    assert client.get(ROTA, params=parametros, headers=_token()).status_code == 422


def openapi_deve_documentar_respostas_200_401_e_422_das_regioes():
    operacao = app.openapi()["paths"][ROTA]["get"]
    respostas = operacao["responses"]
    assert {"200", "401", "422"} <= set(respostas)
    assert respostas["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
        "/RegiaoResposta"
    )
    assert {"HTTPBearer": []} in operacao["security"]
    raio = next(p for p in operacao["parameters"] if p["name"] == "raio")
    assert (raio["schema"]["default"], raio["schema"]["maximum"]) == (3000, 10000)
