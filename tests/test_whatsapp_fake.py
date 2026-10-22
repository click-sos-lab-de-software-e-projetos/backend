"""SOS-05: contrato do envio por WhatsApp e o fake usado pelos testes do worker."""

import asyncio

from app.services import whatsapp
from app.services.whatsapp import ClienteWhatsAppFake, ResultadoEnvio

TELEFONE = "+5511900000000"  # fictício


def resultado_sucesso_nao_deve_ter_codigo_de_erro():
    assert ResultadoEnvio.ok() == ResultadoEnvio(sucesso=True, erro_codigo=None)


def resultado_falha_deve_guardar_o_codigo_de_erro():
    assert ResultadoEnvio.falha("TIMEOUT") == ResultadoEnvio(sucesso=False, erro_codigo="TIMEOUT")


def fake_sem_roteiro_deve_responder_sucesso_e_registrar_o_envio():
    fake = ClienteWhatsAppFake()

    resultado = asyncio.run(fake.enviar_texto(TELEFONE, "texto"))

    assert resultado == ResultadoEnvio.ok()
    assert fake.enviados == [(TELEFONE, "texto")]


def fake_com_roteiro_deve_devolver_as_respostas_na_ordem():
    fake = ClienteWhatsAppFake([ResultadoEnvio.falha("TIMEOUT"), ResultadoEnvio.ok()])

    async def enviar_duas_vezes():
        return [await fake.enviar_texto(TELEFONE, "texto") for _ in range(2)]

    assert asyncio.run(enviar_duas_vezes()) == [ResultadoEnvio.falha("TIMEOUT"), ResultadoEnvio.ok()]


def fake_lento_deve_esperar_o_atraso_configurado_antes_de_responder(monkeypatch):
    # Confere o pedido de espera em vez de cronometrar: no Windows o relógio do
    # asyncio anda em saltos de ~15 ms e uma espera de 50 ms chega a medir 47 ms.
    esperas = []

    async def dormir(segundos):
        esperas.append(segundos)

    monkeypatch.setattr(whatsapp.asyncio, "sleep", dormir)
    fake = ClienteWhatsAppFake(atraso_segundos=0.05)

    assert asyncio.run(fake.enviar_texto(TELEFONE, "texto")) == ResultadoEnvio.ok()
    assert esperas == [0.05]


def fake_sem_atraso_nao_deve_esperar(monkeypatch):
    esperas = []

    async def dormir(segundos):
        esperas.append(segundos)

    monkeypatch.setattr(whatsapp.asyncio, "sleep", dormir)

    asyncio.run(ClienteWhatsAppFake().enviar_texto(TELEFONE, "texto"))

    assert esperas == []
