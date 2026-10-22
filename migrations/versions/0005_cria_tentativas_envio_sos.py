"""cria tentativas_envio_sos

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tentativas_envio_sos",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "alerta_id",
            UUID(as_uuid=True),
            sa.ForeignKey("alertas_sos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contato_id",
            UUID(as_uuid=True),
            sa.ForeignKey("contatos_emergencia.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("numero_tentativa", sa.Integer, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("erro_codigo", sa.String(50), nullable=True),
        sa.Column(
            "executado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "numero_tentativa BETWEEN 1 AND 5", name="ck_tentativas_numero_de_1_a_5"
        ),
        sa.CheckConstraint("status IN ('SUCESSO', 'FALHOU')", name="ck_tentativas_status"),
        sa.UniqueConstraint(
            "alerta_id", "contato_id", "numero_tentativa", name="uq_tentativas_alerta_contato_numero"
        ),
    )
    op.create_index("ix_tentativas_envio_sos_alerta_id", "tentativas_envio_sos", ["alerta_id"])


def downgrade() -> None:
    op.drop_index("ix_tentativas_envio_sos_alerta_id", table_name="tentativas_envio_sos")
    op.drop_table("tentativas_envio_sos")
