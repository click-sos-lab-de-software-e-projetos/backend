"""cria fontes_geograficas e regioes_seguranca

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-27

Reescrita em 09/11/2026 a partir do schema do Neon, que já estava nesta
revisão sem o arquivo estar no Git. No Neon, não rode de novo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_GERADO = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        "fontes_geograficas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=UUID_GERADO),
        sa.Column("arquivo_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("nome_arquivo", sa.String(255), nullable=False),
        sa.Column("fonte_url", sa.String(2048), nullable=False),
        sa.Column("licenca", sa.String(500), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema="interno",
    )
    op.create_table(
        "regioes_seguranca",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=UUID_GERADO),
        sa.Column("id_publico", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "fonte_geografica_id",
            UUID(as_uuid=True),
            sa.ForeignKey("interno.fontes_geograficas.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(160), nullable=False),
        sa.Column(
            "limites", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False
        ),
        sa.Column("centroide", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("score_oficial", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("score_final", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cor_hex", sa.String(7), nullable=False, server_default="#22C55E"),
        sa.Column("raio_metros", sa.Integer, nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("cor_hex ~ '^#[0-9A-F]{6}$'", name="ck_regioes_cor_hex"),
        sa.CheckConstraint("raio_metros > 0", name="ck_regioes_raio_positivo"),
    )
    op.create_index(
        "ix_regioes_seguranca_fonte_geografica_id", "regioes_seguranca", ["fonte_geografica_id"]
    )
    op.create_index(
        "ix_regioes_seguranca_limites", "regioes_seguranca", ["limites"], postgresql_using="gist"
    )


def downgrade() -> None:
    op.drop_table("regioes_seguranca")
    op.drop_table("fontes_geograficas", schema="interno")
