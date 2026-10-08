"""Ponto de entrada provisório da API FastAPI."""

from fastapi import FastAPI

app = FastAPI(
    title="Click S.O.S API",
    version="0.1.0",
    description="Estrutura inicial; recursos de negócio ainda não foram implementados.",
)


@app.get("/health", tags=["operacional"])
def health_check() -> dict[str, str]:
    """Confirma que a aplicação iniciou."""
    return {"status": "ok"}
