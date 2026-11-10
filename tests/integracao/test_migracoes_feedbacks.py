import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from integracao.fabricas import inserir_regiao, inserir_usuario
from integracao.inspecao import definicoes_de_indices, restricoes

TABELA = "feedbacks_comunidade"

RESTRICOES_ESPERADAS = {
    ("feedbacks_comunidade_pkey", "PRIMARY KEY (id)"),
    (
        "feedbacks_comunidade_usuario_id_fkey",
        "FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE",
    ),
    (
        "feedbacks_comunidade_regiao_id_fkey",
        "FOREIGN KEY (regiao_id) REFERENCES regioes_seguranca(id) ON DELETE RESTRICT",
    ),
    (
        "ck_feedbacks_categoria",
        "CHECK (((categoria)::text = ANY ((ARRAY['ILUMINACAO'::character varying, "
        "'ASSALTO'::character varying, 'ASSEDIO'::character varying, 'MOVIMENTO'::character varying, "
        "'POLICIAMENTO'::character varying, 'OUTRO'::character varying])::text[])))",
    ),
    (
        "ck_feedbacks_status",
        "CHECK (((status)::text = ANY ((ARRAY['PENDENTE'::character varying, "
        "'APROVADO'::character varying, 'REJEITADO'::character varying])::text[])))",
    ),
    ("ck_feedbacks_outro_com_texto", "CHECK ((((categoria)::text <> 'OUTRO'::text) OR (texto IS NOT NULL)))"),
}

INDICES_ESPERADOS = {
    "CREATE INDEX ix_feedbacks_comunidade_regiao_id ON public.feedbacks_comunidade USING btree (regiao_id)",
    "CREATE INDEX ix_feedbacks_comunidade_usuario_id ON public.feedbacks_comunidade USING btree (usuario_id)",
}


def _sem_not_null(conjunto: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return {(nome, definicao) for nome, definicao in conjunto if not definicao.startswith("NOT NULL")}


def feedbacks_deve_ter_fks_checks_e_indices(banco_migrado):
    assert _sem_not_null(restricoes(banco_migrado, TABELA)) == RESTRICOES_ESPERADAS
    secundarios = {d for d in definicoes_de_indices(banco_migrado, TABELA) if not d.startswith("CREATE UNIQUE")}
    assert secundarios == INDICES_ESPERADOS


def _inserir_feedback(conexao, usuario_id, regiao_id, categoria="ASSALTO", texto=None):
    return conexao.execute(
        text(
            "INSERT INTO feedbacks_comunidade (usuario_id, regiao_id, categoria, texto) "
            "VALUES (:usuario_id, :regiao_id, :categoria, :texto) RETURNING id, status, criado_em"
        ),
        {"usuario_id": usuario_id, "regiao_id": regiao_id, "categoria": categoria, "texto": texto},
    ).one()


def feedback_novo_deve_nascer_pendente_e_sumir_com_a_pessoa(banco_migrado):
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao).id
        regiao = inserir_regiao(conexao, 0, 0, 0.01, 0.01).id
        feedback = _inserir_feedback(conexao, usuario, regiao)
    assert feedback.status == "PENDENTE" and feedback.criado_em is not None

    with banco_migrado.begin() as conexao:
        conexao.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario})
        assert conexao.execute(text("SELECT count(*) FROM feedbacks_comunidade")).scalar_one() == 0


@pytest.mark.parametrize(("categoria", "texto"), [("BARULHO", "x"), ("OUTRO", None)])
def banco_deve_recusar_categoria_invalida_e_outro_sem_texto(banco_migrado, categoria, texto):
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao).id
        regiao = inserir_regiao(conexao, 0, 0, 0.01, 0.01).id

    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        _inserir_feedback(conexao, usuario, regiao, categoria, texto)
