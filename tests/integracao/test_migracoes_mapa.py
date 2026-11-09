"""As migrações 0006 e 0007 reproduzem o schema que já existe no Neon.

O Neon foi migrado antes de essas revisões estarem no Git. As definições
abaixo foram copiadas do banco real; se divergirem, `alembic stamp 0007` no
Neon deixaria o histórico mentindo sobre o schema.
"""

import pytest
from alembic import command
from sqlalchemy import text

from integracao.inspecao import definicoes_de_indices, restricoes

RESTRICOES_ESPERADAS = {
    "interno.fontes_geograficas": {
        ("fontes_geograficas_pkey", "PRIMARY KEY (id)"),
        ("fontes_geograficas_arquivo_sha256_key", "UNIQUE (arquivo_sha256)"),
    },
    "interno.cargas_ssp": {
        ("cargas_ssp_pkey", "PRIMARY KEY (id)"),
        ("cargas_ssp_arquivo_sha256_key", "UNIQUE (arquivo_sha256)"),
        (
            "ck_cargas_ssp_status",
            "CHECK (((status)::text = ANY ((ARRAY['PROCESSANDO'::character varying, "
            "'CONCLUIDA'::character varying, 'FALHOU'::character varying])::text[])))",
        ),
    },
    "interno.ocorrencias_ssp": {
        ("ocorrencias_ssp_pkey", "PRIMARY KEY (id)"),
        ("ocorrencias_ssp_chave_fonte_key", "UNIQUE (chave_fonte)"),
        ("ck_ocorrencias_ssp_peso", "CHECK (((peso >= 1) AND (peso <= 3)))"),
        (
            "ocorrencias_ssp_carga_id_fkey",
            "FOREIGN KEY (carga_id) REFERENCES interno.cargas_ssp(id) ON DELETE RESTRICT",
        ),
    },
    "regioes_seguranca": {
        ("regioes_seguranca_pkey", "PRIMARY KEY (id)"),
        ("regioes_seguranca_id_publico_key", "UNIQUE (id_publico)"),
        ("ck_regioes_cor_hex", "CHECK (((cor_hex)::text ~ '^#[0-9A-F]{6}$'::text))"),
        ("ck_regioes_raio_positivo", "CHECK ((raio_metros > 0))"),
        (
            "regioes_seguranca_fonte_geografica_id_fkey",
            "FOREIGN KEY (fonte_geografica_id) REFERENCES interno.fontes_geograficas(id) "
            "ON DELETE RESTRICT",
        ),
    },
}

INDICES_ESPERADOS = {
    "ocorrencias_ssp": {
        "CREATE INDEX ix_ocorrencias_ssp_carga_id ON interno.ocorrencias_ssp "
        "USING btree (carga_id)",
        "CREATE INDEX ix_ocorrencias_ssp_localizacao ON interno.ocorrencias_ssp "
        "USING gist (localizacao)",
        "CREATE INDEX ix_ocorrencias_ssp_municipio_data ON interno.ocorrencias_ssp "
        "USING btree (municipio_ibge, data_ocorrencia)",
        "CREATE INDEX ix_ocorrencias_ssp_natureza ON interno.ocorrencias_ssp "
        "USING btree (natureza_apurada)",
    },
    "regioes_seguranca": {
        "CREATE INDEX ix_regioes_seguranca_fonte_geografica_id ON public.regioes_seguranca "
        "USING btree (fonte_geografica_id)",
        "CREATE INDEX ix_regioes_seguranca_limites ON public.regioes_seguranca "
        "USING gist (limites)",
    },
}


def _sem_not_null(conjunto: set[tuple[str, str]]) -> set[tuple[str, str]]:
    # O PostgreSQL 18 (Neon) lista NOT NULL como restrição; o 16 dos testes, não.
    return {(nome, definicao) for nome, definicao in conjunto if not definicao.startswith("NOT NULL")}


@pytest.mark.parametrize("tabela", sorted(RESTRICOES_ESPERADAS))
def restricoes_devem_ser_identicas_as_do_neon(banco_migrado, tabela):
    assert _sem_not_null(restricoes(banco_migrado, tabela)) == RESTRICOES_ESPERADAS[tabela]


@pytest.mark.parametrize("tabela", sorted(INDICES_ESPERADOS))
def indices_secundarios_devem_ser_identicos_aos_do_neon(banco_migrado, tabela):
    secundarios = {
        definicao
        for definicao in definicoes_de_indices(banco_migrado, tabela)
        if not definicao.startswith("CREATE UNIQUE")
    }
    assert secundarios == INDICES_ESPERADOS[tabela]


def colunas_geometricas_devem_usar_srid_4326(banco_migrado):
    with banco_migrado.connect() as conexao:
        linhas = conexao.execute(
            text(
                "SELECT f_table_schema, f_table_name, f_geometry_column, type, srid "
                "FROM geometry_columns WHERE f_table_name IN ('ocorrencias_ssp', 'regioes_seguranca')"
            )
        ).all()
    assert set(linhas) == {
        ("interno", "ocorrencias_ssp", "localizacao", "POINT", 4326),
        ("public", "regioes_seguranca", "limites", "MULTIPOLYGON", 4326),
        ("public", "regioes_seguranca", "centroide", "POINT", 4326),
    }


def regiao_nova_deve_usar_defaults_do_neon(banco_migrado):
    with banco_migrado.begin() as conexao:
        fonte_id = conexao.execute(
            text(
                "INSERT INTO interno.fontes_geograficas "
                "(arquivo_sha256, nome_arquivo, fonte_url, licenca) "
                "VALUES (repeat('a', 64), 'distritos.geojson', 'https://example.com', 'aberta') "
                "RETURNING id"
            )
        ).scalar_one()
        regiao = conexao.execute(
            text(
                "INSERT INTO regioes_seguranca "
                "(id_publico, fonte_geografica_id, nome, limites, centroide, raio_metros) "
                "VALUES ('distrito-teste', :fonte, 'Teste', "
                "ST_Multi(ST_MakeEnvelope(0, 0, 1, 1, 4326)), ST_SetSRID(ST_MakePoint(0.5, 0.5), 4326), 100) "
                "RETURNING score_oficial, score_final, cor_hex"
            ),
            {"fonte": fonte_id},
        ).one()
    assert (regiao.score_oficial, regiao.score_final, regiao.cor_hex) == (0, 0, "#22C55E")


def downgrade_ate_0005_deve_remover_schema_interno(config_alembic, engine):
    command.downgrade(config_alembic, "base")
    command.upgrade(config_alembic, "head")
    command.downgrade(config_alembic, "0005")
    try:
        with engine.connect() as conexao:
            existe = conexao.execute(
                text("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'interno'")
            ).scalar_one()
        assert existe == 0
    finally:
        command.downgrade(config_alembic, "base")
