from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from integracao.fabricas import inserir_alerta, inserir_contato, inserir_tentativa, inserir_usuario
from integracao.inspecao import colunas, definicoes_de_indices


@pytest.fixture
def cenario(banco_migrado):
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao)
        return SimpleNamespace(
            alerta_id=inserir_alerta(conexao, usuario.id).id,
            contato_id=inserir_contato(conexao, usuario.id).id,
        )


def contar_tentativas(conexao) -> int:
    return conexao.execute(text("SELECT count(*) FROM tentativas_envio_sos")).scalar()


def tabela_tentativas_deve_ter_colunas_esperadas(banco_migrado):
    assert colunas(banco_migrado, "tentativas_envio_sos") == {
        "id": ("uuid", None, False),
        "alerta_id": ("uuid", None, False),
        "contato_id": ("uuid", None, True),
        "numero_tentativa": ("integer", None, False),
        "status": ("character varying", 10, False),
        "erro_codigo": ("character varying", 50, True),
        "executado_em": ("timestamp with time zone", None, False),
    }


def tentativas_deve_ter_indice_por_alerta_id(banco_migrado):
    indices = definicoes_de_indices(banco_migrado, "tentativas_envio_sos")
    assert any(definicao.endswith("(alerta_id)") for definicao in indices)


def tentativa_nova_deve_registrar_executado_em_com_fuso(banco_migrado, cenario):
    with banco_migrado.begin() as conexao:
        tentativa = inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id)
    assert tentativa.executado_em.tzinfo is not None


@pytest.mark.parametrize("numero", [1, 5])
def numero_tentativa_dentro_de_1_a_5_deve_ser_aceito(banco_migrado, cenario, numero):
    with banco_migrado.begin() as conexao:
        inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id, numero_tentativa=numero)


@pytest.mark.parametrize("numero", [0, 6])
def numero_tentativa_fora_de_1_a_5_deve_violar_check(banco_migrado, cenario, numero):
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id, numero_tentativa=numero)


@pytest.mark.parametrize("status", ["SUCESSO", "FALHOU"])
def status_de_tentativa_do_dominio_deve_ser_aceito(banco_migrado, cenario, status):
    with banco_migrado.begin() as conexao:
        inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id, status=status)


@pytest.mark.parametrize("status", ["ENVIADO", "falhou", ""])
def status_de_tentativa_fora_do_dominio_deve_violar_check(banco_migrado, cenario, status):
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id, status=status)


def tentativa_repetida_para_mesmo_alerta_contato_e_numero_deve_violar_unicidade(
    banco_migrado, cenario
):
    with banco_migrado.begin() as conexao:
        inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id)
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id)


def remover_alerta_deve_remover_suas_tentativas(banco_migrado, cenario):
    with banco_migrado.begin() as conexao:
        inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id)
        conexao.execute(text("DELETE FROM alertas_sos WHERE id = :id"), {"id": cenario.alerta_id})
        assert contar_tentativas(conexao) == 0


def remover_contato_deve_anular_contato_id_nas_tentativas(banco_migrado, cenario):
    with banco_migrado.begin() as conexao:
        tentativa = inserir_tentativa(conexao, cenario.alerta_id, cenario.contato_id)
        conexao.execute(
            text("DELETE FROM contatos_emergencia WHERE id = :id"), {"id": cenario.contato_id}
        )
        contato_id = conexao.execute(
            text("SELECT contato_id FROM tentativas_envio_sos WHERE id = :id"),
            {"id": tentativa.id},
        ).scalar_one()
    assert contato_id is None
