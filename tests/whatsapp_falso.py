"""Enviador de WhatsApp falso para os testes; nunca usa rede."""

from collections.abc import Iterable, Mapping

from app.services.whatsapp import Desfecho, ResultadoEnvio


class EnviadorWhatsAppFalso:
    """Registra os envios e devolve os resultados do roteiro, em ordem.

    `por_telefone` dá um roteiro próprio a cada número; os demais usam
    `roteiro`. Sem roteiro, ou depois que ele acaba, o envio é bem-sucedido.
    """

    def __init__(
        self,
        roteiro: Iterable[ResultadoEnvio] = (),
        por_telefone: Mapping[str, Iterable[ResultadoEnvio]] | None = None,
    ):
        self._roteiro = list(roteiro)
        self._por_telefone = {tel: list(r) for tel, r in (por_telefone or {}).items()}
        self.envios: list[tuple[str, str]] = []

    def enviar(self, telefone_e164: str, texto: str) -> ResultadoEnvio:
        self.envios.append((telefone_e164, texto))
        roteiro = self._por_telefone.get(telefone_e164, self._roteiro)
        if roteiro:
            return roteiro.pop(0)
        return ResultadoEnvio(Desfecho.ENVIADO)
