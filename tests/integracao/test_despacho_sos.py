from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from whatsapp_falso import EnviadorWhatsAppFalso

from app.services.mensagem_sos import montar_mensagem_emergencia
from app.workers.despacho_sos import despachar_alerta, obter_despacho, obter_enviador_whatsapp
from integracao.fabricas import inserir_alerta, inserir_contato, inserir_usuario

APTO = {"consentido_em": datetime(2026, 1, 1, tzinfo=UTC)}
LATITUDE, LONGITUDE = 0.25, 0.75


@pytest.fixture
def fabrica(banco_migrado):
    return sessionmaker(banco_migrado, expire_on_commit=False)


def _preparar(banco_migrado, *contatos: dict, mensagem=None):
    """Cria uma pessoa, os contatos descritos e um alerta PENDENTE dela."""
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao, nome_completo="Ana Ficticia")
        contatos_ids = [
            inserir_contato(conexao, usuario.id, **contato).id for contato in contatos
        ]
        alerta = inserir_alerta(
            conexao, usuario.id, latitude=LATITUDE, longitude=LONGITUDE, mensagem=mensagem
        )
    return usuario.id, alerta.id, contatos_ids


def _telefone(banco_migrado, contato_id) -> str:
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text("SELECT telefone_whatsapp FROM contatos_emergencia WHERE id = :id"),
            {"id": contato_id},
        ).scalar_one()


def _alerta(banco_migrado, alerta_id):
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text("SELECT status_envio, tentativas FROM alertas_sos WHERE id = :id"),
            {"id": alerta_id},
        ).one()


def _tentativas(banco_migrado, alerta_id) -> list:
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text(
                "SELECT contato_id, numero_tentativa, status, erro_codigo "
                "FROM tentativas_envio_sos WHERE alerta_id = :id "
                "ORDER BY numero_tentativa, contato_id"
            ),
            {"id": alerta_id},
        ).all()


def despachar_alerta_deve_enviar_o_texto_da_mensagem_a_cada_contato_apto(banco_migrado, fabrica):
    _, alerta_id, (apto_1, _inativo, _sem_consentimento, apto_2) = _preparar(
        banco_migrado, APTO, {**APTO, "ativo": False}, {}, APTO
    )
    with banco_migrado.begin() as conexao:
        outra = inserir_usuario(conexao).id
        inserir_contato(conexao, outra, **APTO)
    falso = EnviadorWhatsAppFalso()

    despachar_alerta(alerta_id, fabrica_sessao=fabrica, enviador=falso)

    texto = montar_mensagem_emergencia("Ana Ficticia", LATITUDE, LONGITUDE, None).texto
    esperados = {(_telefone(banco_migrado, c), texto) for c in (apto_1, apto_2)}
    assert len(falso.envios) == 2
    assert set(falso.envios) == esperados


def despachar_alerta_com_sucesso_deve_gravar_tentativa_e_marcar_enviado(banco_migrado, fabrica):
    _, alerta_id, contatos = _preparar(banco_migrado, APTO, APTO)

    despachar_alerta(alerta_id, fabrica_sessao=fabrica, enviador=EnviadorWhatsAppFalso())

    assert tuple(_alerta(banco_migrado, alerta_id)) == ("ENVIADO", 1)
    tentativas = _tentativas(banco_migrado, alerta_id)
    assert {t.contato_id for t in tentativas} == set(contatos)
    assert {(t.numero_tentativa, t.status, t.erro_codigo) for t in tentativas} == {(1, "SUCESSO", None)}


def despachar_alerta_sem_contato_apto_deve_marcar_erro_sem_enviar(banco_migrado, fabrica):
    _, alerta_id, _ = _preparar(banco_migrado, {**APTO, "ativo": False})
    falso = EnviadorWhatsAppFalso()

    despachar_alerta(alerta_id, fabrica_sessao=fabrica, enviador=falso)

    assert falso.envios == []
    assert tuple(_alerta(banco_migrado, alerta_id)) == ("ERRO", 0)
    assert _tentativas(banco_migrado, alerta_id) == []


def despacho_sem_variaveis_da_evolution_deve_marcar_o_alerta_como_erro(
    banco_migrado, fabrica, monkeypatch
):
    for nome in ("EVOLUTION_API_URL", "EVOLUTION_API_KEY", "EVOLUTION_INSTANCE"):
        monkeypatch.delenv(nome, raising=False)
    obter_enviador_whatsapp.cache_clear()
    _, alerta_id, _ = _preparar(banco_migrado, APTO)

    obter_despacho(fabrica)(alerta_id)

    assert tuple(_alerta(banco_migrado, alerta_id)) == ("ERRO", 0)
