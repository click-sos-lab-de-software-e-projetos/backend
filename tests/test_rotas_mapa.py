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
def consultar_regioes_sem_token_valido_deve_responder_200(client, cabecalhos, monkeypatch):
    app.dependency_overrides[obter_sessao] = lambda: None
    monkeypatch.setattr(servico, "listar_regioes_proximas", lambda *_: [])

    resposta = client.get(ROTA, params=PONTO, headers=cabecalhos)

    assert resposta.status_code == 200
    assert resposta.json() == []


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
def consultar_regioes_com_parametro_invalido_deve_responder_422_sem_consultar_regioes(client, parametros, monkeypatch):
    # O FastAPI cria a sessão mesmo com parâmetro inválido, mas ela só conecta no 1º uso.
    app.dependency_overrides[obter_sessao] = lambda: None
    monkeypatch.setattr(servico, "listar_regioes_proximas", _consulta_proibida)

    assert client.get(ROTA, params=parametros).status_code == 422


def openapi_deve_documentar_regioes_como_rota_publica_com_respostas_200_e_422():
    operacao = app.openapi()["paths"][ROTA]["get"]
    respostas = operacao["responses"]
    assert {"200", "422"} <= set(respostas)
    assert "401" not in respostas
    assert respostas["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith("/RegiaoResposta")
    assert "security" not in operacao
    raio = next(p for p in operacao["parameters"] if p["name"] == "raio")
    assert (raio["schema"]["default"], raio["schema"]["maximum"]) == (3000, 10000)


ROTA_ALERTAS = "/api/v1/mapa/alertas"
ALERTA_VALIDO = {"categoria": "ILUMINACAO", "texto": "Rua escura", **PONTO}


def _alerta_proibido(*_):
    raise AssertionError("A rota gravou um alerta com corpo inválido.")


@pytest.mark.parametrize("cabecalhos", [{}, {"Authorization": "Bearer nao-e-jwt"}])
def criar_alerta_sem_token_valido_deve_responder_401_sem_tocar_no_banco(client, cabecalhos):
    resposta = client.post(ROTA_ALERTAS, json=ALERTA_VALIDO, headers=cabecalhos)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "corpo",
    [{}, PONTO | {"categoria": "BARULHO"}, PONTO | {"categoria": "OUTRO"}, {"categoria": "ASSALTO"}],
)
def criar_alerta_com_corpo_invalido_deve_responder_422_sem_gravar(client, corpo, monkeypatch):
    app.dependency_overrides[obter_sessao] = lambda: None
    monkeypatch.setattr(servico, "criar_alerta", _alerta_proibido)

    assert client.post(ROTA_ALERTAS, json=corpo, headers=_token()).status_code == 422


def listar_alertas_sem_token_deve_consultar_com_o_raio_padrao(client, monkeypatch):
    app.dependency_overrides[obter_sessao] = lambda: None
    chamadas = []
    monkeypatch.setattr(servico, "listar_alertas_proximos", lambda *args: chamadas.append(args[1:]) or [])

    resposta = client.get(ROTA_ALERTAS, params=PONTO)

    assert resposta.status_code == 200
    assert resposta.json() == []
    assert chamadas == [(PONTO["latitude"], PONTO["longitude"], 3000)]


def openapi_deve_documentar_criacao_autenticada_e_listagem_publica_dos_alertas():
    caminho = app.openapi()["paths"]["/api/v1/mapa/alertas"]
    assert {"201", "401", "422"} <= set(caminho["post"]["responses"])
    assert caminho["post"]["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/AlertaComunidadeResposta"
    )
    assert {"HTTPBearer": []} in caminho["post"]["security"]
    assert "security" not in caminho["get"]
    assert "/api/v1/mapa/regioes/{regiao_id}/feedbacks" not in app.openapi()["paths"]
