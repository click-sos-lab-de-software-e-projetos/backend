"""troca feedbacks_comunidade por alertas_comunidade (alertas no mapa, estilo Waze)

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELA = "alertas_comunidade"
UUID_GERADO = sa.text("gen_random_uuid()")
# Fixas para a migração não mudar com as constantes.
CHECK_CATEGORIA = "categoria IN ('ILUMINACAO', 'ASSALTO', 'ASSEDIO', 'MOVIMENTO', 'POLICIAMENTO', 'OUTRO')"
CHECK_OUTRO = "categoria <> 'OUTRO' OR texto IS NOT NULL"


def upgrade() -> None:
    op.drop_table("feedbacks_comunidade")
    op.create_table(
        TABELA,
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=UUID_GERADO),
        # CASCADE: a exclusão de conta leva junto os alertas da pessoa.
        sa.Column(
            "usuario_id",
            UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("texto", sa.String(500), nullable=True),
        sa.Column("localizacao", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(CHECK_CATEGORIA, name="ck_alertas_comunidade_categoria"),
        sa.CheckConstraint(CHECK_OUTRO, name="ck_alertas_comunidade_outro_com_texto"),
    )
    op.create_index("ix_alertas_comunidade_localizacao", TABELA, ["localizacao"], postgresql_using="gist")
    op.create_index("ix_alertas_comunidade_criado_em", TABELA, ["criado_em"])
    op.create_index("ix_alertas_comunidade_usuario_id", TABELA, ["usuario_id"])


def downgrade() -> None:
    op.drop_table(TABELA)
    # Volta a 0009; os feedbacks antigos não voltam.
    op.create_table(
        "feedbacks_comunidade",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=UUID_GERADO),
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
        sa.CheckConstraint(CHECK_CATEGORIA, name="ck_feedbacks_categoria"),
        sa.CheckConstraint("status IN ('PENDENTE', 'APROVADO', 'REJEITADO')", name="ck_feedbacks_status"),
        sa.CheckConstraint(CHECK_OUTRO, name="ck_feedbacks_outro_com_texto"),
    )
    op.create_index("ix_feedbacks_comunidade_regiao_id", "feedbacks_comunidade", ["regiao_id"])
    op.create_index("ix_feedbacks_comunidade_usuario_id", "feedbacks_comunidade", ["usuario_id"])
