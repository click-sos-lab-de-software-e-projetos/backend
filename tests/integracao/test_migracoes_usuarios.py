import pytest
from sqlalchemy.exc import IntegrityError

from integracao.fabricas import inserir_usuario
from integracao.inspecao import colunas


def tabela_usuarios_deve_ter_colunas_tipos_e_nulidade_esperados(banco_migrado):
    assert colunas(banco_migrado, "usuarios") == {
        "id": ("uuid", None, False),
        "nome_completo": ("character varying", 120, False),
        "email": ("character varying", 150, False),
        "senha_hash": ("character varying", 255, False),
        "telefone_pessoal": ("character varying", 20, False),
        "criado_em": ("timestamp with time zone", None, False),
    }


def usuario_inserido_sem_id_deve_receber_uuid_e_criado_em_automaticos(banco_migrado):
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao)
    assert usuario.id is not None
    assert usuario.criado_em.tzinfo is not None


def email_duplicado_deve_violar_unicidade(banco_migrado):
    with banco_migrado.begin() as conexao:
        inserir_usuario(conexao, email="repetido@example.com")
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_usuario(conexao, email="repetido@example.com")


def email_igual_com_caixa_diferente_deve_violar_unicidade(banco_migrado):
    with banco_migrado.begin() as conexao:
        inserir_usuario(conexao, email="repetido@example.com")
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_usuario(conexao, email="Repetido@Example.COM")
