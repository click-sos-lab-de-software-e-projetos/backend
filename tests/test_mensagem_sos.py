"""SOS-04: monta o título, o link e o texto do alerta (Regra 02).

Dados fictícios: nenhuma pessoa, telefone ou coordenada real.
"""

from urllib.parse import parse_qs, urlparse

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
