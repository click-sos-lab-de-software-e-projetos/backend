import os

from app.constants import NOME_VARIAVEL_URL_BANCO

PREFIXOS_SEM_DRIVER = ("postgresql://", "postgres://")
PREFIXO_PSYCOPG = "postgresql+psycopg://"


def obter_url_banco() -> str:
    url = os.environ.get(NOME_VARIAVEL_URL_BANCO)
    if not url:
        raise RuntimeError(f"{NOME_VARIAVEL_URL_BANCO} não configurada.")
    for prefixo in PREFIXOS_SEM_DRIVER:
        if url.startswith(prefixo):
            return PREFIXO_PSYCOPG + url.removeprefix(prefixo)
    return url
