"""adiciona consentimento por link aos contatos

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "contatos_emergencia"


def upgrade() -> None:
    op.add_column(TABELA, sa.Column("recusado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABELA, sa.Column("token_consentimento_hash", sa.String(64), nullable=True))
    op.add_column(
        TABELA,
        sa.Column("token_consentimento_expira_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_contatos_token_consentimento_hash", TABELA, ["token_consentimento_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_contatos_token_consentimento_hash", TABELA, type_="unique")
    op.drop_column(TABELA, "token_consentimento_expira_em")
    op.drop_column(TABELA, "token_consentimento_hash")
    op.drop_column(TABELA, "recusado_em")
