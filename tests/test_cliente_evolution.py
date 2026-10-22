"""SOS-05: cliente da Evolution API, testado sem rede com httpx.MockTransport.

URL, chave, instância e telefone são fictícios.
"""

import asyncio
import json

import httpx
import pytest

from app.services.evolution import ClienteEvolution
from app.services.whatsapp import ResultadoEnvio

URL_BASE = "http://evolution.teste:8080"
CHAVE = "chave-ficticia-123"
INSTANCIA = "click-sos-teste"
TELEFONE = "+5511900000000"
TEXTO = "Pessoa Exemplo acionou o botão do Click S.O.S."


def _cliente(responder):
    return ClienteEvolution(
        url_base=URL_BASE, chave=CHAVE, instancia=INSTANCIA, transporte=httpx.MockTransport(responder)
    )


def _enviar(responder) -> ResultadoEnvio:
    return asyncio.run(_cliente(responder).enviar_texto(TELEFONE, TEXTO))


def envio_deve_fazer_post_no_send_text_da_instancia_com_a_chave_no_cabecalho():
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(201, json={"key": {"id": "abc"}})

    assert _enviar(responder) == ResultadoEnvio.ok()

    (requisicao,) = requisicoes
    assert requisicao.method == "POST"
    assert str(requisicao.url) == f"{URL_BASE}/message/sendText/{INSTANCIA}"
    assert requisicao.headers["apikey"] == CHAVE


def envio_deve_mandar_numero_sem_o_mais_e_o_texto_no_corpo():
    corpos = []

    def responder(requisicao):
        corpos.append(json.loads(requisicao.content))
        return httpx.Response(200)

    _enviar(responder)

    assert corpos == [{"number": "5511900000000", "text": TEXTO}]


def url_base_com_barra_no_fim_nao_deve_duplicar_a_barra():
    urls = []

    def responder(requisicao):
        urls.append(str(requisicao.url))
        return httpx.Response(200)

    cliente = ClienteEvolution(
        url_base=URL_BASE + "/", chave=CHAVE, instancia=INSTANCIA,
        transporte=httpx.MockTransport(responder),
    )
    asyncio.run(cliente.enviar_texto(TELEFONE, TEXTO))

    assert urls == [f"{URL_BASE}/message/sendText/{INSTANCIA}"]


@pytest.mark.parametrize("telefone", ["5511900000000", "+55 11 90000-0000", "", "+0119"])
def telefone_fora_do_e164_deve_ser_rejeitado_antes_de_chamar_a_api(telefone):
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao)
        return httpx.Response(200)

    with pytest.raises(ValueError, match="E.164"):
        asyncio.run(_cliente(responder).enviar_texto(telefone, TEXTO))
    assert chamadas == []
