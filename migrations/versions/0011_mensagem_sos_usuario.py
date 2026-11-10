"""mensagem de S.O.S. salva por pessoa (Ajustes do app)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mesmo limite de alertas_sos.mensagem (LIMITE_MENSAGEM_SOS); fixo para a migração não mudar com a constante.
LIMITE = 255


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("mensagem_sos", sa.String(LIMITE), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "mensagem_sos")
