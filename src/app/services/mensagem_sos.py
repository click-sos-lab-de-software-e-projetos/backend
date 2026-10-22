"""Texto do alerta S.O.S enviado aos contatos (SOS-04, Regra 02).

Função pura: não lê banco, não chama a Evolution API e não escreve em log.
Quem chama (o worker do SOS-06) entrega os dados já carregados.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

URL_BUSCA_GOOGLE_MAPS = "https://www.google.com/maps/search/"
CASAS_DECIMAIS = 6  # cerca de 11 cm no equador; mais que isso é ruído de GPS


@dataclass(frozen=True)
class MensagemEmergencia:
    titulo: str
    link_google_maps: str


def montar_mensagem_emergencia(
    nome_usuario: str, latitude: float, longitude: float, mensagem: str | None
) -> MensagemEmergencia:
    coordenadas = f"{latitude:.{CASAS_DECIMAIS}f},{longitude:.{CASAS_DECIMAIS}f}"
    link = f"{URL_BUSCA_GOOGLE_MAPS}?{urlencode({'api': 1, 'query': coordenadas}, safe=',')}"
    titulo = f"{nome_usuario} acionou o botão do Click S.O.S. nas coordenadas: {link}"
    return MensagemEmergencia(titulo=titulo, link_google_maps=link)
