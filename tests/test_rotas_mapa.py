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
def consultar_regioes_com_parametro_invalido_deve_responder_422_sem_consultar_regioes(
    client, parametros, monkeypatch
):
    # O FastAPI cria a sessão mesmo com parâmetro inválido, mas ela só conecta no 1º uso.
    app.dependency_overrides[obter_sessao] = lambda: None
    monkeypatch.setattr(servico, "listar_regioes_proximas", _consulta_proibida)

    assert client.get(ROTA, params=parametros).status_code == 422


def openapi_deve_documentar_regioes_como_rota_publica_com_respostas_200_e_422():
    operacao = app.openapi()["paths"][ROTA]["get"]
    respostas = operacao["responses"]
    assert {"200", "422"} <= set(respostas)
    assert "401" not in respostas
    assert respostas["200"]["content"]["application/json"]["schema"]["items"]["$ref"].endswith(
        "/RegiaoResposta"
    )
    assert "security" not in operacao
    raio = next(p for p in operacao["parameters"] if p["name"] == "raio")
    assert (raio["schema"]["default"], raio["schema"]["maximum"]) == (3000, 10000)


ROTA_FEEDBACK = "/api/v1/mapa/regioes/distrito-sp-1/feedbacks"
FEEDBACK_VALIDO = {"categoria": "ILUMINACAO", "texto": "Rua escura"}


def _feedback_proibido(*_):
    raise AssertionError("A rota gravou um feedback com corpo inválido.")


@pytest.mark.parametrize("cabecalhos", [{}, {"Authorization": "Bearer nao-e-jwt"}])
def enviar_feedback_sem_token_valido_deve_responder_401_sem_tocar_no_banco(client, cabecalhos):
    resposta = client.post(ROTA_FEEDBACK, json=FEEDBACK_VALIDO, headers=cabecalhos)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "corpo",
    [{}, {"categoria": "BARULHO"}, {"categoria": "OUTRO"}, {"categoria": "ASSALTO", "texto": "a" * 501}],
)
def enviar_feedback_com_corpo_invalido_deve_responder_422_sem_gravar(client, corpo, monkeypatch):
    app.dependency_overrides[obter_sessao] = lambda: None
    monkeypatch.setattr(servico, "criar_feedback", _feedback_proibido, raising=False)

    assert client.post(ROTA_FEEDBACK, json=corpo, headers=_token()).status_code == 422


def openapi_deve_documentar_respostas_201_401_404_e_422_do_feedback():
    operacao = app.openapi()["paths"]["/api/v1/mapa/regioes/{regiao_id}/feedbacks"]["post"]
    assert {"201", "401", "404", "422"} <= set(operacao["responses"])
    assert operacao["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/FeedbackCriadoResposta"
    )
    assert {"HTTPBearer": []} in operacao["security"]
