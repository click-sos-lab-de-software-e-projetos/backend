"""cria contatos_emergencia

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contatos_emergencia",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("telefone_whatsapp", sa.String(20), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("consentido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            r"telefone_whatsapp ~ '^\+[1-9][0-9]{7,14}$'", name="ck_contatos_telefone_e164"
        ),
    )
    op.create_index("ix_contatos_emergencia_usuario_id", "contatos_emergencia", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_contatos_emergencia_usuario_id", table_name="contatos_emergencia")
    op.drop_table("contatos_emergencia")
