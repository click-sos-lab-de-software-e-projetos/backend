"""Ponto de entrada da API FastAPI."""

from fastapi import FastAPI

from app.api.v1 import auth, contatos, sos

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
app.include_router(sos.router)


@app.get("/health", tags=["operacional"])
def health_check() -> dict[str, str]:
    """Confirma que a aplicação iniciou."""
    return {"status": "ok"}
