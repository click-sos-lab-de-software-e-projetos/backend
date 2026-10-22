"""Ponto de entrada da API FastAPI."""

from fastapi import FastAPI

from app.api.v1 import contatos

app = FastAPI(
    title="Click S.O.S API",
    version="0.1.0",
    description="API do Click S.O.S. Rotas privadas exigem `Authorization: Bearer <JWT>`.",
)

app.include_router(contatos.router)


@app.get("/health", tags=["operacional"])
def health_check() -> dict[str, str]:
    """Confirma que a aplicação iniciou."""
    return {"status": "ok"}
