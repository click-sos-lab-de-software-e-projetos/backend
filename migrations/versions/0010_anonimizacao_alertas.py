"""permite alerta anonimizado (Tarefa 10, Regra 08)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "alertas_sos"
FK_USUARIO = "alertas_sos_usuario_id_fkey"
CHECK_ANONIMIZADO = "ck_alertas_localizacao_ou_anonimizado"


def upgrade() -> None:
    op.add_column(TABELA, sa.Column("anonimizado_em", sa.DateTime(timezone=True), nullable=True))
    op.alter_column(TABELA, "localizacao", nullable=True)
    op.create_check_constraint(CHECK_ANONIMIZADO, TABELA, "localizacao IS NOT NULL OR anonimizado_em IS NOT NULL")
    # Excluir a conta mantém o alerta, sem dono, para estatística.
    op.alter_column(TABELA, "usuario_id", nullable=True)
    op.drop_constraint(FK_USUARIO, TABELA, type_="foreignkey")
    op.create_foreign_key(FK_USUARIO, TABELA, "usuarios", ["usuario_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    # As coordenadas e o dono não voltam: os alertas anonimizados ou sem dono são apagados.
    op.execute("DELETE FROM alertas_sos WHERE localizacao IS NULL OR usuario_id IS NULL")
    op.drop_constraint(FK_USUARIO, TABELA, type_="foreignkey")
    op.create_foreign_key(FK_USUARIO, TABELA, "usuarios", ["usuario_id"], ["id"], ondelete="CASCADE")
    op.alter_column(TABELA, "usuario_id", nullable=False)
    op.drop_constraint(CHECK_ANONIMIZADO, TABELA, type_="check")
    op.alter_column(TABELA, "localizacao", nullable=False)
    op.drop_column(TABELA, "anonimizado_em")
