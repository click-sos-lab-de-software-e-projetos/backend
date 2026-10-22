"""cria alertas_sos

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID

from app.constants import LIMITE_MENSAGEM_SOS

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alertas_sos",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "usuario_id",
            UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "localizacao",
            Geometry("POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("mensagem", sa.String(LIMITE_MENSAGEM_SOS), nullable=True),
        sa.Column("status_envio", sa.String(20), nullable=False, server_default="PENDENTE"),
        sa.Column("tentativas", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status_envio IN ('PENDENTE', 'ENVIADO', 'ERRO')", name="ck_alertas_status_envio"
        ),
        sa.CheckConstraint("tentativas >= 0", name="ck_alertas_tentativas_nao_negativas"),
    )
    op.create_index(
        "ix_alertas_sos_localizacao", "alertas_sos", ["localizacao"], postgresql_using="gist"
    )
    op.create_index("ix_alertas_sos_usuario_id", "alertas_sos", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_alertas_sos_usuario_id", table_name="alertas_sos")
    op.drop_index("ix_alertas_sos_localizacao", table_name="alertas_sos")
    op.drop_table("alertas_sos")
