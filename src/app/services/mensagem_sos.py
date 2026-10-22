"""Texto do alerta S.O.S enviado aos contatos (SOS-04, Regra 02).

Função pura: não lê banco, não chama a Evolution API e não escreve em log.
Quem chama (o worker do SOS-06) entrega os dados já carregados.
"""

import math
from dataclasses import dataclass, field
from urllib.parse import urlencode

from app.constants import MENSAGEM_PADRAO_SOS

URL_BUSCA_GOOGLE_MAPS = "https://www.google.com/maps/search/"
CASAS_DECIMAIS = 6  # cerca de 11 cm no equador; mais que isso é ruído de GPS
LIMITES = {"latitude": 90, "longitude": 180}


@dataclass(frozen=True)
class MensagemEmergencia:
    # repr=False: um log descuidado do objeto não pode vazar nome nem localização.
    titulo: str = field(repr=False)
    link_google_maps: str = field(repr=False)
    coordenadas: str = field(repr=False)
    mensagem: str = field(repr=False)

    @property
    def texto(self) -> str:
        """Corpo único enviado pelo WhatsApp; a mensagem padrão cita a localização "acima"."""
        return f"{self.titulo}\n\nCoordenadas: {self.coordenadas}\n\n{self.mensagem}"


def montar_mensagem_emergencia(
    nome_usuario: str, latitude: float, longitude: float, mensagem: str | None
) -> MensagemEmergencia:
    nome = nome_usuario.strip()
    if not nome:
        raise ValueError("nome_usuario não pode ser vazio")
    lat = _formatar("latitude", latitude)
    lng = _formatar("longitude", longitude)
    link = f"{URL_BUSCA_GOOGLE_MAPS}?{urlencode({'api': 1, 'query': f'{lat},{lng}'}, safe=',')}"
    return MensagemEmergencia(
        titulo=f"{nome} acionou o botão do Click S.O.S. nas coordenadas: {link}",
        link_google_maps=link,
        coordenadas=f"{lat}, {lng}",
        mensagem=(mensagem or "").strip() or MENSAGEM_PADRAO_SOS,
    )


def _formatar(campo: str, grau: float) -> str:
    # A mensagem de erro cita só o campo, nunca o valor recebido.
    if not math.isfinite(grau) or abs(grau) > LIMITES[campo]:
        raise ValueError(f"{campo} fora do intervalo válido")
    # Somar 0.0 depois de arredondar troca -0.0 por 0.0 ("-0.000000" confundiria quem lê).
    return f"{round(grau, CASAS_DECIMAIS) + 0.0:.{CASAS_DECIMAIS}f}"
