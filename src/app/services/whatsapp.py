"""Envio de mensagens de WhatsApp pela Evolution API v2 (SOS-05).

O envio devolve um resultado em vez de levantar exceção: falhar faz parte do
fluxo normal (Regra 04), e o worker decide pelo desfecho se tenta de novo.
Nada aqui escreve em log; o corpo das respostas de erro é descartado, pois
pode ecoar o número e o texto.
"""

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

import httpx

from app.constants import (
    NOME_VARIAVEL_EVOLUTION_CHAVE,
    NOME_VARIAVEL_EVOLUTION_INSTANCIA,
    NOME_VARIAVEL_EVOLUTION_URL,
    TIMEOUT_ENVIO_WHATSAPP_S,
)


class Desfecho(StrEnum):
    ENVIADO = "ENVIADO"
    FALHA_TEMPORARIA = "FALHA_TEMPORARIA"
    FALHA_DEFINITIVA = "FALHA_DEFINITIVA"


@dataclass(frozen=True)
class ResultadoEnvio:
    desfecho: Desfecho
    # Cabe em tentativas_envio_sos.erro_codigo: TIMEOUT, CONEXAO ou HTTP_<status>.
    erro_codigo: str | None = None


class EnviadorWhatsApp(Protocol):
    def enviar(self, telefone_e164: str, texto: str) -> ResultadoEnvio: ...


def _classificar_status(status: int) -> ResultadoEnvio:
    if 200 <= status < 300:
        return ResultadoEnvio(Desfecho.ENVIADO)
    temporaria = status == 429 or status >= 500
    desfecho = Desfecho.FALHA_TEMPORARIA if temporaria else Desfecho.FALHA_DEFINITIVA
    return ResultadoEnvio(desfecho, f"HTTP_{status}")


@dataclass(frozen=True)
class EnviadorEvolution:
    url_base: str
    chave: str = field(repr=False)
    instancia: str
    cliente_http: httpx.Client = field(repr=False)

    def enviar(self, telefone_e164: str, texto: str) -> ResultadoEnvio:
        url = f"{self.url_base.rstrip('/')}/message/sendText/{self.instancia}"
        try:
            resposta = self.cliente_http.post(
                url,
                headers={"apikey": self.chave},
                json={"number": telefone_e164.removeprefix("+"), "text": texto},
            )
        except httpx.TimeoutException:
            return ResultadoEnvio(Desfecho.FALHA_TEMPORARIA, "TIMEOUT")
        except httpx.TransportError:
            return ResultadoEnvio(Desfecho.FALHA_TEMPORARIA, "CONEXAO")
        return _classificar_status(resposta.status_code)


def _ler_variavel(nome: str) -> str:
    valor = (os.environ.get(nome) or "").strip()
    if not valor:
        raise RuntimeError(f"{nome} não configurada.")
    return valor


def criar_enviador_evolution() -> EnviadorEvolution:
    return EnviadorEvolution(
        url_base=_ler_variavel(NOME_VARIAVEL_EVOLUTION_URL),
        chave=_ler_variavel(NOME_VARIAVEL_EVOLUTION_CHAVE),
        instancia=_ler_variavel(NOME_VARIAVEL_EVOLUTION_INSTANCIA),
        cliente_http=httpx.Client(timeout=TIMEOUT_ENVIO_WHATSAPP_S),
    )
