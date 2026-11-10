"""Ponto de entrada da API FastAPI."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, consentimento, contatos, mapa, sos
from app.constants import NOME_VARIAVEL_CORS


def configurar_cors(app: FastAPI, origens_regex: str | None) -> None:
    """Libera o navegador (ex.: `flutter run -d chrome`) só para as origens do regex."""
    if not origens_regex:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=origens_regex,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


app = FastAPI(
    title="Click S.O.S API",
    version="0.1.0",
    description=(
        "API do Click S.O.S. Rotas privadas exigem `Authorization: Bearer <JWT>`, "
        "obtido em `POST /api/v1/auth/login`."
    ),
)

app.include_router(auth.router)
app.include_router(contatos.router)
app.include_router(consentimento.router)
app.include_router(sos.router)
app.include_router(mapa.router)
configurar_cors(app, os.environ.get(NOME_VARIAVEL_CORS))


@app.get("/health", tags=["operacional"])
def health_check() -> dict[str, str]:
    """Confirma que a aplicação iniciou."""
    return {"status": "ok"}
