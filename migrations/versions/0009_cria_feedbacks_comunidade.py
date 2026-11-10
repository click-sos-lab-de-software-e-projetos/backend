"""cria feedbacks_comunidade (MAP-04)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "feedbacks_comunidade"
UUID_GERADO = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        TABELA,
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=UUID_GERADO),
        # CASCADE: a exclusão de conta (Tarefa 10) leva junto os feedbacks da pessoa.
        sa.Column(
            "usuario_id",
            UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "regiao_id",
            UUID(as_uuid=True),
            sa.ForeignKey("regioes_seguranca.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("texto", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDENTE"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "categoria IN ('ILUMINACAO', 'ASSALTO', 'ASSEDIO', 'MOVIMENTO', 'POLICIAMENTO', 'OUTRO')",
            name="ck_feedbacks_categoria",
        ),
        sa.CheckConstraint("status IN ('PENDENTE', 'APROVADO', 'REJEITADO')", name="ck_feedbacks_status"),
        sa.CheckConstraint("categoria <> 'OUTRO' OR texto IS NOT NULL", name="ck_feedbacks_outro_com_texto"),
    )
    op.create_index("ix_feedbacks_comunidade_regiao_id", TABELA, ["regiao_id"])
    op.create_index("ix_feedbacks_comunidade_usuario_id", TABELA, ["usuario_id"])


def downgrade() -> None:
    op.drop_table(TABELA)
