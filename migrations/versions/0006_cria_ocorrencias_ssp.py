"""cria schema interno com as cargas e ocorrências da SSP

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27

Reescrita em 09/11/2026 a partir do schema do Neon, que já estava nesta
revisão sem o arquivo estar no Git. No Neon, não rode de novo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_GERADO = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.execute("CREATE SCHEMA interno")
    op.create_table(
        "cargas_ssp",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=UUID_GERADO),
        sa.Column("arquivo_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("nome_arquivo", sa.String(255), nullable=False),
        sa.Column("fonte_url", sa.String(2048), nullable=True),
        sa.Column("licenca", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PROCESSANDO"),
        sa.Column(
            "iniciado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finalizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("linhas_lidas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("inseridas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("atualizadas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rejeitadas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("erros_amostra", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.CheckConstraint(
            "status IN ('PROCESSANDO', 'CONCLUIDA', 'FALHOU')", name="ck_cargas_ssp_status"
        ),
        schema="interno",
    )
    op.create_table(
        "ocorrencias_ssp",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=UUID_GERADO),
        sa.Column(
            "carga_id",
            UUID(as_uuid=True),
            sa.ForeignKey("interno.cargas_ssp.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("chave_fonte", sa.String(64), nullable=False, unique=True),
        sa.Column("municipio_ibge", sa.String(7), nullable=False),
        sa.Column("municipio_nome", sa.String(120), nullable=False),
        sa.Column("departamento", sa.String(160), nullable=True),
        sa.Column("seccional", sa.String(160), nullable=True),
        sa.Column("delegacia", sa.String(160), nullable=True),
        sa.Column("data_ocorrencia", sa.Date, nullable=True),
        sa.Column("hora_ocorrencia", sa.Time, nullable=True),
        sa.Column("periodo", sa.String(80), nullable=True),
        sa.Column("bairro", sa.String(120), nullable=True),
        sa.Column("rubrica", sa.String(255), nullable=True),
        sa.Column("conduta", sa.String(255), nullable=True),
        sa.Column("natureza_apurada", sa.String(255), nullable=True),
        sa.Column("peso", sa.Integer, nullable=False),
        sa.Column(
            "localizacao", Geometry("POINT", srid=4326, spatial_index=False), nullable=False
        ),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("peso BETWEEN 1 AND 3", name="ck_ocorrencias_ssp_peso"),
        schema="interno",
    )
    op.create_index(
        "ix_ocorrencias_ssp_carga_id", "ocorrencias_ssp", ["carga_id"], schema="interno"
    )
    op.create_index(
        "ix_ocorrencias_ssp_localizacao",
        "ocorrencias_ssp",
        ["localizacao"],
        schema="interno",
        postgresql_using="gist",
    )
    op.create_index(
        "ix_ocorrencias_ssp_municipio_data",
        "ocorrencias_ssp",
        ["municipio_ibge", "data_ocorrencia"],
        schema="interno",
    )
    op.create_index(
        "ix_ocorrencias_ssp_natureza", "ocorrencias_ssp", ["natureza_apurada"], schema="interno"
    )


def downgrade() -> None:
    op.drop_table("ocorrencias_ssp", schema="interno")
    op.drop_table("cargas_ssp", schema="interno")
    op.execute("DROP SCHEMA interno")
