from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from integracao.fabricas import inserir_contato, inserir_usuario
from integracao.inspecao import colunas, definicoes_de_indices


def tabela_contatos_deve_ter_colunas_esperadas(banco_migrado):
    assert colunas(banco_migrado, "contatos_emergencia") == {
        "id": ("uuid", None, False),
        "usuario_id": ("uuid", None, False),
        "nome": ("character varying", 100, False),
        "telefone_whatsapp": ("character varying", 20, False),
        "ativo": ("boolean", None, False),
        "consentido_em": ("timestamp with time zone", None, True),
        "criado_em": ("timestamp with time zone", None, False),
    }


def contato_com_usuario_inexistente_deve_violar_fk(banco_migrado):
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_contato(conexao, uuid4())


def remover_usuario_deve_remover_seus_contatos(banco_migrado):
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao)
        inserir_contato(conexao, usuario.id)
        conexao.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario.id})
        restantes = conexao.execute(text("SELECT count(*) FROM contatos_emergencia")).scalar()
    assert restantes == 0


def contato_novo_deve_nascer_ativo_e_sem_consentimento(banco_migrado):
    with banco_migrado.begin() as conexao:
        contato = inserir_contato(conexao, inserir_usuario(conexao).id)
    assert contato.ativo is True
    assert contato.consentido_em is None


@pytest.mark.parametrize(
    "telefone", ["5500800000001", "+0500800000001", "+55 008 0000 0001", "+1234567", ""]
)
def telefone_fora_do_formato_e164_deve_violar_check(banco_migrado, telefone):
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_contato(conexao, inserir_usuario(conexao).id, telefone_whatsapp=telefone)


def contatos_deve_ter_indice_por_usuario_id(banco_migrado):
    indices = definicoes_de_indices(banco_migrado, "contatos_emergencia")
    assert any(definicao.endswith("(usuario_id)") for definicao in indices)
