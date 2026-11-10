"""Enviador de WhatsApp falso para os testes; nunca usa rede."""

from collections.abc import Iterable

from app.services.whatsapp import Desfecho, ResultadoEnvio


class EnviadorWhatsAppFalso:
    """Registra os envios e devolve os resultados do roteiro, em ordem.

    Sem roteiro, ou depois que ele acaba, todo envio é bem-sucedido.
    """

    def __init__(self, roteiro: Iterable[ResultadoEnvio] = ()):
        self._roteiro = list(roteiro)
        self.envios: list[tuple[str, str]] = []

    def enviar(self, telefone_e164: str, texto: str) -> ResultadoEnvio:
        self.envios.append((telefone_e164, texto))
        if self._roteiro:
            return self._roteiro.pop(0)
        return ResultadoEnvio(Desfecho.ENVIADO)
