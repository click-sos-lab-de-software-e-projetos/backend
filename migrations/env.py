from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.db import models  # noqa: F401  (registra as tabelas em Base.metadata)
from app.db.base import Base, somente_tabelas_mapeadas
from app.db.config import obter_url_banco

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or obter_url_banco()


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        include_object=somente_tabelas_mapeadas,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=somente_tabelas_mapeadas,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
