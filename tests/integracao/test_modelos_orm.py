from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

from app.db.base import Base, somente_tabelas_mapeadas
from app.db.models import AlertaSos, ContatoEmergencia, TentativaEnvioSos, Usuario


def metadados_orm_deve_coincidir_com_banco_migrado(banco_migrado):
    with banco_migrado.connect() as conexao:
        contexto = MigrationContext.configure(
            conexao,
            opts={"include_object": somente_tabelas_mapeadas, "compare_type": True},
        )
        diferencas = compare_metadata(contexto, Base.metadata)
    assert diferencas == []


def modelos_deve_cobrir_as_quatro_tabelas_do_epico():
    tabelas = {
        modelo.__tablename__
        for modelo in (Usuario, ContatoEmergencia, AlertaSos, TentativaEnvioSos)
    }
    assert tabelas == set(Base.metadata.tables)
