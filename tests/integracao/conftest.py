import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, pool

from app.constants import NOME_VARIAVEL_URL_BANCO
from integracao.banco import NOME_VARIAVEL_URL_BANCO_TESTE, validar_url_de_teste

PASTA = Path(__file__).parent
ALEMBIC_INI = PASTA.parents[1] / "alembic.ini"


def pytest_collection_modifyitems(config, items):
    sem_banco = not os.environ.get(NOME_VARIAVEL_URL_BANCO_TESTE)
    for item in items:
        if PASTA in Path(item.path).parents:
            item.add_marker(pytest.mark.integracao)
            if sem_banco:
                item.add_marker(
                    pytest.mark.skip(reason=f"{NOME_VARIAVEL_URL_BANCO_TESTE} não definida")
                )


@pytest.fixture(scope="session")
def url_teste() -> str:
    return validar_url_de_teste(
        os.environ[NOME_VARIAVEL_URL_BANCO_TESTE], os.environ.get(NOME_VARIAVEL_URL_BANCO)
    )


@pytest.fixture(scope="session")
def engine(url_teste):
    engine = create_engine(url_teste, poolclass=pool.NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def config_alembic(url_teste) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url_teste.replace("%", "%%"))
    return config


@pytest.fixture
def banco_migrado(config_alembic, engine):
    command.downgrade(config_alembic, "base")
    command.upgrade(config_alembic, "head")
    yield engine
    command.downgrade(config_alembic, "base")
