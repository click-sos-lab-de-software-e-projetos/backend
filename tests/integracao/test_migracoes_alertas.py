import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.constants import LIMITE_MENSAGEM_SOS
from integracao.fabricas import inserir_alerta, inserir_usuario
from integracao.inspecao import colunas, definicoes_de_indices


@pytest.fixture
def usuario_id(banco_migrado):
    with banco_migrado.begin() as conexao:
        return inserir_usuario(conexao).id


def tabela_alertas_deve_ter_colunas_esperadas(banco_migrado):
    assert colunas(banco_migrado, "alertas_sos") == {
        "id": ("uuid", None, False),
        "usuario_id": ("uuid", None, False),
        "localizacao": ("USER-DEFINED", None, False),
        "mensagem": ("character varying", LIMITE_MENSAGEM_SOS, True),
        "status_envio": ("character varying", 20, False),
        "tentativas": ("integer", None, False),
        "criado_em": ("timestamp with time zone", None, False),
    }


def localizacao_deve_ser_point_com_srid_4326(banco_migrado):
    with banco_migrado.connect() as conexao:
        tipo, srid = conexao.execute(
            text(
                "SELECT type, srid FROM geometry_columns "
                "WHERE f_table_name = 'alertas_sos' AND f_geometry_column = 'localizacao'"
            )
        ).one()
    assert (tipo, srid) == ("POINT", 4326)


def ponto_gravado_deve_preservar_longitude_e_latitude(banco_migrado, usuario_id):
    with banco_migrado.begin() as conexao:
        alerta = inserir_alerta(conexao, usuario_id, latitude=0.25, longitude=0.75)
        x, y = conexao.execute(
            text("SELECT ST_X(localizacao), ST_Y(localizacao) FROM alertas_sos WHERE id = :id"),
            {"id": alerta.id},
        ).one()
    assert (x, y) == (0.75, 0.25)


def ponto_com_outro_srid_deve_ser_rejeitado(banco_migrado, usuario_id):
    with pytest.raises(DBAPIError), banco_migrado.begin() as conexao:
        inserir_alerta(conexao, usuario_id, srid=3857)


def alertas_deve_ter_um_unico_indice_gist_em_localizacao(banco_migrado):
    indices = definicoes_de_indices(banco_migrado, "alertas_sos")
    gist = [definicao for definicao in indices if "USING gist (localizacao)" in definicao]
    assert len(gist) == 1, gist


def alertas_deve_ter_indice_por_usuario_id(banco_migrado):
    indices = definicoes_de_indices(banco_migrado, "alertas_sos")
    assert any(definicao.endswith("(usuario_id)") for definicao in indices)


def alerta_novo_deve_nascer_pendente_com_zero_tentativas(banco_migrado, usuario_id):
    with banco_migrado.begin() as conexao:
        alerta = inserir_alerta(conexao, usuario_id)
    assert (alerta.status_envio, alerta.tentativas) == ("PENDENTE", 0)
    assert alerta.criado_em.tzinfo is not None


@pytest.mark.parametrize("status", ["PENDENTE", "ENVIADO", "ERRO"])
def status_envio_do_dominio_deve_ser_aceito(banco_migrado, usuario_id, status):
    with banco_migrado.begin() as conexao:
        assert inserir_alerta(conexao, usuario_id, status_envio=status).status_envio == status


@pytest.mark.parametrize("status", ["ENTREGUE", "pendente", ""])
def status_envio_fora_do_dominio_deve_violar_check(banco_migrado, usuario_id, status):
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_alerta(conexao, usuario_id, status_envio=status)


def tentativas_negativas_deve_violar_check(banco_migrado, usuario_id):
    with pytest.raises(IntegrityError), banco_migrado.begin() as conexao:
        inserir_alerta(conexao, usuario_id, tentativas=-1)


def mensagem_nula_deve_ser_aceita(banco_migrado, usuario_id):
    with banco_migrado.begin() as conexao:
        assert inserir_alerta(conexao, usuario_id).mensagem is None


def mensagem_no_limite_deve_ser_aceita(banco_migrado, usuario_id):
    with banco_migrado.begin() as conexao:
        alerta = inserir_alerta(conexao, usuario_id, mensagem="a" * LIMITE_MENSAGEM_SOS)
    assert len(alerta.mensagem) == LIMITE_MENSAGEM_SOS


def mensagem_acima_do_limite_deve_ser_rejeitada(banco_migrado, usuario_id):
    with pytest.raises(DBAPIError), banco_migrado.begin() as conexao:
        inserir_alerta(conexao, usuario_id, mensagem="a" * (LIMITE_MENSAGEM_SOS + 1))


def remover_usuario_deve_remover_seus_alertas(banco_migrado, usuario_id):
    with banco_migrado.begin() as conexao:
        inserir_alerta(conexao, usuario_id)
        conexao.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario_id})
        assert conexao.execute(text("SELECT count(*) FROM alertas_sos")).scalar() == 0
