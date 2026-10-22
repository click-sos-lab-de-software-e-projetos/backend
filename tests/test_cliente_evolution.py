"""SOS-05: cliente da Evolution API, testado sem rede com httpx.MockTransport.

URL, chave, instância e telefone são fictícios.
"""

import asyncio
import logging
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


@pytest.mark.parametrize("excecao", [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout])
def tempo_esgotado_deve_virar_falha_timeout(excecao):
    def responder(requisicao):
        raise excecao("tempo esgotado", request=requisicao)

    assert _enviar(responder) == ResultadoEnvio.falha("TIMEOUT")


def falha_de_conexao_deve_virar_falha_conexao():
    def responder(requisicao):
        raise httpx.ConnectError("recusada", request=requisicao)

    assert _enviar(responder) == ResultadoEnvio.falha("CONEXAO")


@pytest.mark.parametrize("status", [400, 401, 404, 500, 503])
def resposta_de_erro_http_deve_virar_falha_com_o_status(status):
    assert _enviar(lambda requisicao: httpx.Response(status)) == ResultadoEnvio.falha(f"HTTP_{status}")


def cliente_deve_aplicar_o_timeout_padrao_de_3_segundos():
    timeouts = []

    def responder(requisicao):
        timeouts.append(requisicao.extensions["timeout"])
        return httpx.Response(200)

    _enviar(responder)

    assert timeouts == [{"connect": 3.0, "read": 3.0, "write": 3.0, "pool": 3.0}]


AMBIENTE_COMPLETO = {
    "EVOLUTION_API_URL": URL_BASE,
    "EVOLUTION_API_KEY": CHAVE,
    "EVOLUTION_INSTANCE": INSTANCIA,
}


def cliente_do_ambiente_deve_usar_url_chave_e_instancia_das_variaveis():
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(200)

    cliente = ClienteEvolution.do_ambiente(AMBIENTE_COMPLETO, transporte=httpx.MockTransport(responder))
    asyncio.run(cliente.enviar_texto(TELEFONE, TEXTO))

    assert str(requisicoes[0].url) == f"{URL_BASE}/message/sendText/{INSTANCIA}"
    assert requisicoes[0].headers["apikey"] == CHAVE


@pytest.mark.parametrize("variavel", sorted(AMBIENTE_COMPLETO))
@pytest.mark.parametrize("valor", [None, "", "   "])
def cliente_do_ambiente_sem_variavel_deve_falhar_citando_so_o_nome(variavel, valor):
    ambiente = {k: v for k, v in AMBIENTE_COMPLETO.items() if k != variavel}
    if valor is not None:
        ambiente[variavel] = valor

    with pytest.raises(RuntimeError, match=variavel) as erro:
        ClienteEvolution.do_ambiente(ambiente)

    for segredo in (CHAVE, URL_BASE):
        assert segredo not in str(erro.value)


def repr_do_cliente_nao_deve_expor_a_chave():
    assert CHAVE not in repr(_cliente(lambda requisicao: httpx.Response(200)))


@pytest.mark.parametrize("status", [201, 500])
def envio_nao_deve_levar_chave_telefone_nem_texto_para_o_log(caplog, status):
    caplog.set_level(logging.DEBUG)

    _enviar(lambda requisicao: httpx.Response(status, text=f"eco {TELEFONE} {TEXTO}"))

    registros = caplog.text
    assert "HTTP Request" in registros  # o httpx registra a chamada; o teste não passa no vazio
    for dado in (CHAVE, TELEFONE.removeprefix("+"), TEXTO):
        assert dado not in registros
