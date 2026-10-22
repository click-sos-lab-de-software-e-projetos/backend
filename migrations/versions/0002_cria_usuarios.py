"""cria usuarios

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("nome_completo", sa.String(120), nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("telefone_pessoal", sa.String(20), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_usuarios_email_minusculo", "usuarios", [sa.text("lower(email)")], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_usuarios_email_minusculo", table_name="usuarios")
    op.drop_table("usuarios")
