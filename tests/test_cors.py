from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import configurar_cors

PREFLIGHT = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "authorization,content-type",
}


def _client(regex: str | None) -> TestClient:
    app = FastAPI()

    @app.post("/rota")
    def rota() -> dict[str, str]:
        return {}

    configurar_cors(app, regex)
    return TestClient(app)


def configurar_cors_com_regex_deve_liberar_a_origem_que_casa():
    resposta = _client(r"http://localhost:\d+").options(
        "/rota", headers={"Origin": "http://localhost:5173", **PREFLIGHT}
    )
    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == "http://localhost:5173"


def configurar_cors_com_regex_deve_recusar_origem_que_nao_casa():
    resposta = _client(r"http://localhost:\d+").options(
        "/rota", headers={"Origin": "https://exemplo.invalid", **PREFLIGHT}
    )
    assert "access-control-allow-origin" not in resposta.headers


def configurar_cors_sem_regex_nao_deve_liberar_nenhuma_origem():
    resposta = _client(None).post("/rota", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in resposta.headers
