"""Contrato do envio de WhatsApp (SOS-05) e um fake para testes.

O worker (SOS-06) depende só de `ClienteWhatsApp`; em produção recebe o
cliente da Evolution API, nos testes recebe `ClienteWhatsAppFake`.
"""

import asyncio
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ResultadoEnvio:
    """Resultado de uma tentativa. `erro_codigo` vai para `tentativas_envio_sos.erro_codigo`."""

    sucesso: bool
    erro_codigo: str | None = None

    @classmethod
    def ok(cls) -> "ResultadoEnvio":
        return cls(sucesso=True)

    @classmethod
    def falha(cls, erro_codigo: str) -> "ResultadoEnvio":
        return cls(sucesso=False, erro_codigo=erro_codigo)


class ClienteWhatsApp(Protocol):
    async def enviar_texto(self, telefone_e164: str, texto: str) -> ResultadoEnvio: ...


class ClienteWhatsAppFake:
    """Registra os envios e devolve um roteiro de respostas; sem roteiro, sempre sucesso."""

    def __init__(
        self, respostas: Iterable[ResultadoEnvio] = (), atraso_segundos: float = 0.0
    ) -> None:
        self._respostas = deque(respostas)
        self._atraso = atraso_segundos
        self.enviados: list[tuple[str, str]] = []

    async def enviar_texto(self, telefone_e164: str, texto: str) -> ResultadoEnvio:
        if self._atraso:
            await asyncio.sleep(self._atraso)
        self.enviados.append((telefone_e164, texto))
        return self._respostas.popleft() if self._respostas else ResultadoEnvio.ok()
