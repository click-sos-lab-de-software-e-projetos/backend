"""SOS-04: monta o título, o link e o texto do alerta (Regra 02).

Dados fictícios: nenhuma pessoa, telefone ou coordenada real.
"""

from urllib.parse import parse_qs, urlparse

import pytest

from app.constants import MENSAGEM_PADRAO_SOS
from app.services.mensagem_sos import montar_mensagem_emergencia

NOME = "Pessoa Exemplo"
LATITUDE = -23.55
LONGITUDE = -46.633


def _montar(**alteracoes):
    dados = {"nome_usuario": NOME, "latitude": LATITUDE, "longitude": LONGITUDE, "mensagem": None}
    return montar_mensagem_emergencia(**(dados | alteracoes))


def link_google_maps_deve_apontar_para_as_coordenadas_do_alerta():
    link = urlparse(_montar().link_google_maps)

    assert (link.scheme, link.netloc, link.path) == ("https", "www.google.com", "/maps/search/")
    assert parse_qs(link.query) == {"api": ["1"], "query": ["-23.550000,-46.633000"]}


def link_google_maps_deve_manter_a_virgula_legivel_para_quem_recebe():
    assert _montar().link_google_maps.endswith("query=-23.550000,-46.633000")


def titulo_deve_seguir_o_modelo_da_regra_02():
    mensagem = _montar()

    assert mensagem.titulo == (
        f"{NOME} acionou o botão do Click S.O.S. nas coordenadas: {mensagem.link_google_maps}"
    )


def mensagem_padrao_deve_ser_o_texto_da_regra_02():
    assert MENSAGEM_PADRAO_SOS == (
        "Olá, por favor, com urgência, verifique se está tudo bem comigo. "
        "Minha localização é a informada acima."
    )


@pytest.mark.parametrize("vazia", [None, "", "   ", "\n\t"])
def mensagem_livre_vazia_deve_usar_a_mensagem_padrao(vazia):
    assert _montar(mensagem=vazia).mensagem == MENSAGEM_PADRAO_SOS


def mensagem_livre_preenchida_deve_ser_usada_sem_espacos_nas_pontas():
    assert _montar(mensagem="  Estou na saída do metrô.  ").mensagem == "Estou na saída do metrô."


def coordenadas_devem_vir_legiveis_na_mensagem():
    assert _montar().coordenadas == "-23.550000, -46.633000"


def texto_deve_trazer_titulo_coordenadas_e_mensagem_nessa_ordem():
    mensagem = _montar(mensagem="Estou na saída do metrô.")

    assert mensagem.texto == (
        f"{mensagem.titulo}\n\n"
        "Coordenadas: -23.550000, -46.633000\n\n"
        "Estou na saída do metrô."
    )
