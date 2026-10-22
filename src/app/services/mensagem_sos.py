"""Texto do alerta S.O.S enviado aos contatos (SOS-04, Regra 02).

Função pura: não lê banco, não chama a Evolution API e não escreve em log.
Quem chama (o worker do SOS-06) entrega os dados já carregados.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

from app.constants import MENSAGEM_PADRAO_SOS

URL_BUSCA_GOOGLE_MAPS = "https://www.google.com/maps/search/"
CASAS_DECIMAIS = 6  # cerca de 11 cm no equador; mais que isso é ruído de GPS


@dataclass(frozen=True)
class MensagemEmergencia:
    titulo: str
    link_google_maps: str
    coordenadas: str
    mensagem: str

    @property
    def texto(self) -> str:
        """Corpo único enviado pelo WhatsApp; a mensagem padrão cita a localização "acima"."""
        return f"{self.titulo}\n\nCoordenadas: {self.coordenadas}\n\n{self.mensagem}"


def montar_mensagem_emergencia(
    nome_usuario: str, latitude: float, longitude: float, mensagem: str | None
) -> MensagemEmergencia:
    lat, lng = _formatar(latitude), _formatar(longitude)
    link = f"{URL_BUSCA_GOOGLE_MAPS}?{urlencode({'api': 1, 'query': f'{lat},{lng}'}, safe=',')}"
    return MensagemEmergencia(
        titulo=f"{nome_usuario} acionou o botão do Click S.O.S. nas coordenadas: {link}",
        link_google_maps=link,
        coordenadas=f"{lat}, {lng}",
        mensagem=(mensagem or "").strip() or MENSAGEM_PADRAO_SOS,
    )


def _formatar(grau: float) -> str:
    return f"{grau:.{CASAS_DECIMAIS}f}"
