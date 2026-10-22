"""Cliente da Evolution API para o envio do alerta por WhatsApp (SOS-05).

Faz uma única tentativa por chamada; retentativas são do SOS-07. Não escreve
em log: chave, telefone e texto nunca saem daqui.
"""

import os
import re
from collections.abc import Mapping

import httpx

from app.constants import NOMES_VARIAVEIS_EVOLUTION
from app.services.whatsapp import ResultadoEnvio

# Mesmo padrão do CHECK ck_contatos_telefone_e164 (migração 0003). Quando o
# CONT-01 entrar na main, trocar por app.constants.PADRAO_TELEFONE_E164.
_PADRAO_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")
TIMEOUT_PADRAO_SEGUNDOS = 3.0  # Especificação de Arquitetura, seção 06


class ClienteEvolution:
    def __init__(
        self,
        url_base: str,
        chave: str,
        instancia: str,
        timeout_segundos: float = TIMEOUT_PADRAO_SEGUNDOS,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url_envio = f"{url_base.rstrip('/')}/message/sendText/{instancia}"
        self._chave = chave
        self._timeout = timeout_segundos
        self._transporte = transporte

    @classmethod
    def do_ambiente(
        cls,
        ambiente: Mapping[str, str] = os.environ,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> "ClienteEvolution":
        valores = {nome: (ambiente.get(nome) or "").strip() for nome in NOMES_VARIAVEIS_EVOLUTION}
        ausentes = [nome for nome, valor in valores.items() if not valor]
        if ausentes:
            # Cita só os nomes; valores (URL, chave) nunca entram na mensagem.
            raise RuntimeError(f"variáveis de ambiente ausentes: {', '.join(ausentes)}")
        url, chave, instancia = valores.values()
        return cls(url_base=url, chave=chave, instancia=instancia, transporte=transporte)

    async def enviar_texto(self, telefone_e164: str, texto: str) -> ResultadoEnvio:
        if not _PADRAO_E164.fullmatch(telefone_e164):
            raise ValueError("telefone precisa estar no formato E.164")
        # A Evolution API espera o número sem o "+".
        corpo = {"number": telefone_e164.removeprefix("+"), "text": texto}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transporte) as http:
                resposta = await http.post(
                    self._url_envio, json=corpo, headers={"apikey": self._chave}
                )
        except httpx.TimeoutException:
            return ResultadoEnvio.falha("TIMEOUT")
        except httpx.TransportError:
            return ResultadoEnvio.falha("CONEXAO")
        # Só o status: o corpo da resposta pode ecoar número e texto.
        if resposta.is_success:
            return ResultadoEnvio.ok()
        return ResultadoEnvio.falha(f"HTTP_{resposta.status_code}")
