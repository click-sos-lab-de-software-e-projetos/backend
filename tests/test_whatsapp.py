import json
import logging

import httpx
import pytest

from app.constants import (
    NOME_VARIAVEL_EVOLUTION_CHAVE,
    NOME_VARIAVEL_EVOLUTION_INSTANCIA,
    NOME_VARIAVEL_EVOLUTION_URL,
)
from app.services.whatsapp import Desfecho, EnviadorEvolution, criar_enviador_evolution

URL = "http://evolution.test"
CHAVE = "chave-ficticia-123"
INSTANCIA = "click-sos-teste"
TELEFONE = "+5500900000001"
TEXTO = "Mensagem de teste fictícia"


def _enviador(handler, url_base=URL) -> EnviadorEvolution:
    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    return EnviadorEvolution(url_base=url_base, chave=CHAVE, instancia=INSTANCIA, cliente_http=cliente)


def _responder(status):
    return lambda requisicao: httpx.Response(status)


def _levantar(erro):
    def handler(requisicao):
        raise erro("falha simulada", request=requisicao)

    return handler


def enviar_deve_chamar_send_text_da_instancia_com_apikey_e_numero_sem_mais():
    recebidas = []

    def handler(requisicao):
        recebidas.append(requisicao)
        return httpx.Response(201, json={"key": {"id": "abc"}})

    resultado = _enviador(handler).enviar(TELEFONE, TEXTO)

    assert resultado.desfecho == Desfecho.ENVIADO
    assert resultado.erro_codigo is None
    [requisicao] = recebidas
    assert requisicao.method == "POST"
    assert str(requisicao.url) == f"{URL}/message/sendText/{INSTANCIA}"
    assert requisicao.headers["apikey"] == CHAVE
    assert json.loads(requisicao.content) == {"number": "5500900000001", "text": TEXTO}


def enviar_deve_aceitar_url_base_com_barra_no_final():
    urls = []

    def handler(requisicao):
        urls.append(str(requisicao.url))
        return httpx.Response(201)

    _enviador(handler, url_base=URL + "/").enviar(TELEFONE, TEXTO)

    assert urls == [f"{URL}/message/sendText/{INSTANCIA}"]


@pytest.mark.parametrize("status", [429, 500, 503])
def resposta_429_ou_5xx_deve_ser_falha_temporaria_com_codigo_http(status):
    resultado = _enviador(_responder(status)).enviar(TELEFONE, TEXTO)
    assert resultado.desfecho == Desfecho.FALHA_TEMPORARIA
    assert resultado.erro_codigo == f"HTTP_{status}"


@pytest.mark.parametrize("status", [400, 401, 404])
def resposta_4xx_deve_ser_falha_definitiva_com_codigo_http(status):
    resultado = _enviador(_responder(status)).enviar(TELEFONE, TEXTO)
    assert resultado.desfecho == Desfecho.FALHA_DEFINITIVA
    assert resultado.erro_codigo == f"HTTP_{status}"


def timeout_deve_ser_falha_temporaria():
    resultado = _enviador(_levantar(httpx.ReadTimeout)).enviar(TELEFONE, TEXTO)
    assert resultado.desfecho == Desfecho.FALHA_TEMPORARIA
    assert resultado.erro_codigo == "TIMEOUT"


def falha_de_conexao_deve_ser_falha_temporaria():
    resultado = _enviador(_levantar(httpx.ConnectError)).enviar(TELEFONE, TEXTO)
    assert resultado.desfecho == Desfecho.FALHA_TEMPORARIA
    assert resultado.erro_codigo == "CONEXAO"


def enviar_nao_deve_registrar_telefone_texto_nem_chave_em_log(caplog):
    caplog.set_level(logging.DEBUG)

    _enviador(_responder(201)).enviar(TELEFONE, TEXTO)
    _enviador(_responder(500)).enviar(TELEFONE, TEXTO)

    mensagens = [registro.getMessage() for registro in caplog.records]
    assert any("HTTP Request: POST" in mensagem for mensagem in mensagens)
    for proibido in (TELEFONE, TELEFONE.removeprefix("+"), TEXTO, CHAVE):
        assert not any(proibido in mensagem for mensagem in mensagens), proibido


def repr_do_enviador_nao_deve_mostrar_a_chave():
    assert CHAVE not in repr(_enviador(_responder(201)))


def criar_enviador_evolution_deve_ler_as_tres_variaveis(monkeypatch):
    monkeypatch.setenv(NOME_VARIAVEL_EVOLUTION_URL, URL)
    monkeypatch.setenv(NOME_VARIAVEL_EVOLUTION_CHAVE, CHAVE)
    monkeypatch.setenv(NOME_VARIAVEL_EVOLUTION_INSTANCIA, INSTANCIA)

    enviador = criar_enviador_evolution()

    assert (enviador.url_base, enviador.chave, enviador.instancia) == (URL, CHAVE, INSTANCIA)


@pytest.mark.parametrize(
    "ausente",
    [NOME_VARIAVEL_EVOLUTION_URL, NOME_VARIAVEL_EVOLUTION_CHAVE, NOME_VARIAVEL_EVOLUTION_INSTANCIA],
)
def criar_enviador_evolution_sem_variavel_deve_lancar_erro_com_o_nome_dela(monkeypatch, ausente):
    valores = {
        NOME_VARIAVEL_EVOLUTION_URL: URL,
        NOME_VARIAVEL_EVOLUTION_CHAVE: CHAVE,
        NOME_VARIAVEL_EVOLUTION_INSTANCIA: INSTANCIA,
    }
    for nome, valor in valores.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv(ausente, " ")

    with pytest.raises(RuntimeError) as erro:
        criar_enviador_evolution()

    assert ausente in str(erro.value)
    for nome, valor in valores.items():
        if nome != ausente:
            assert valor not in str(erro.value)
