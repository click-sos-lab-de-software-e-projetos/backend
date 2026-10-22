from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.db.config import normalizar_url, obter_url_banco


def criar_engine(url: str) -> Engine:
    # hide_parameters: telefones e coordenadas não aparecem em logs do SQLAlchemy
    # nem nas mensagens de erro de banco (ex.: IntegrityError em um traceback).
    return create_engine(normalizar_url(url), pool_pre_ping=True, hide_parameters=True)


@lru_cache(maxsize=1)
def obter_engine() -> Engine:
    return criar_engine(obter_url_banco())


def obter_sessao() -> Iterator[Session]:
    """Dependência FastAPI: uma sessão por requisição. Quem grava faz o commit."""
    with Session(obter_engine(), expire_on_commit=False) as sessao:
        yield sessao
