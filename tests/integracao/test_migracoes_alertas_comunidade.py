import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from integracao.fabricas import inserir_usuario
from integracao.inspecao import definicoes_de_indices, restricoes, tabelas

TABELA = "alertas_comunidade"

RESTRICOES_ESPERADAS = {
    ("alertas_comunidade_pkey", "PRIMARY KEY (id)"),
    (
        "alertas_comunidade_usuario_id_fkey",
        "FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE",
    ),
    (
        "ck_alertas_comunidade_categoria",
        "CHECK (((categoria)::text = ANY ((ARRAY['ILUMINACAO'::character varying, "
        "'ASSALTO'::character varying, 'ASSEDIO'::character varying, 'MOVIMENTO'::character varying, "
        "'POLICIAMENTO'::character varying, 'OUTRO'::character varying])::text[])))",
    ),
    (
        "ck_alertas_comunidade_outro_com_texto",
        "CHECK ((((categoria)::text <> 'OUTRO'::text) OR (texto IS NOT NULL)))",
    ),
}

INDICES_ESPERADOS = {
    "CREATE INDEX ix_alertas_comunidade_localizacao ON public.alertas_comunidade USING gist (localizacao)",
    "CREATE INDEX ix_alertas_comunidade_criado_em ON public.alertas_comunidade USING btree (criado_em)",
    "CREATE INDEX ix_alertas_comunidade_usuario_id ON public.alertas_comunidade USING btree (usuario_id)",
}


def _sem_not_null(conjunto: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return {(nome, definicao) for nome, definicao in conjunto if not definicao.startswith("NOT NULL")}


def alertas_comunidade_deve_ter_fk_checks_e_indices_e_substituir_os_feedbacks(banco_migrado):
    assert _sem_not_null(restricoes(banco_migrado, TABELA)) == RESTRICOES_ESPERADAS
    secundarios = {d for d in definicoes_de_indices(banco_migrado, TABELA) if not d.startswith("CREATE UNIQUE")}
    assert secundarios == INDICES_ESPERADOS
    assert "feedbacks_comunidade" not in tabelas(banco_migrado)


def _inserir_alerta(conexao, usuario_id, categoria="ASSALTO", texto=None):
    return conexao.execute(
        text(
            "INSERT INTO alertas_comunidade (usuario_id, categoria, texto, localizacao) "
            "VALUES (:usuario_id, :categoria, :texto, ST_SetSRID(ST_MakePoint(0, 0), 4326)) RETURNING criado_em"
        ),
        {"usuario_id": usuario_id, "categoria": categoria, "texto": texto},
    ).one()


def alerta_deve_ganhar_data_e_sumir_com_a_pessoa(banco_migrado):
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao).id
        assert _inserir_alerta(conexao, usuario).criado_em is not None

    with banco_migrado.begin() as conexao:
        conexao.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario})
        assert conexao.execute(text("SELECT count(*) FROM alertas_comunidade")).scalar_one() == 0


@pytest.mark.parametrize(("categoria", "texto"), [("BARULHO", "x"), ("OUTRO", None)])
def banco_deve_recusar_categoria_invalida_e_outro_sem_texto(banco_migrado, categoria, texto):
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao).id

    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        _inserir_alerta(conexao, usuario, categoria, texto)
