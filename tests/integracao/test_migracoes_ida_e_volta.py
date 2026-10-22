from alembic import command
from alembic.script import ScriptDirectory

from integracao.inspecao import retrato_do_schema, tabelas

TABELAS_DO_EPICO = ["usuarios", "contatos_emergencia", "alertas_sos", "tentativas_envio_sos"]


def downgrade_base_deve_remover_todas_as_tabelas_do_epico(config_alembic, engine):
    command.upgrade(config_alembic, "head")
    command.downgrade(config_alembic, "base")
    assert tabelas(engine).isdisjoint(TABELAS_DO_EPICO)


def cada_revisao_deve_subir_descer_e_subir_novamente(config_alembic, engine):
    command.downgrade(config_alembic, "base")
    revisoes = reversed(list(ScriptDirectory.from_config(config_alembic).walk_revisions()))
    try:
        for revisao in revisoes:
            command.upgrade(config_alembic, revisao.revision)
            command.downgrade(config_alembic, "-1")
            command.upgrade(config_alembic, revisao.revision)
    finally:
        command.downgrade(config_alembic, "base")


def schema_recriado_apos_downgrade_deve_ser_identico_ao_original(config_alembic, engine):
    command.upgrade(config_alembic, "head")
    original = retrato_do_schema(engine, TABELAS_DO_EPICO)
    command.downgrade(config_alembic, "base")
    command.upgrade(config_alembic, "head")
    try:
        assert retrato_do_schema(engine, TABELAS_DO_EPICO) == original
        assert all(original[tabela]["colunas"] for tabela in TABELAS_DO_EPICO)
    finally:
        command.downgrade(config_alembic, "base")
