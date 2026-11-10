from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from whatsapp_falso import EnviadorWhatsAppFalso

from app.services.mensagem_sos import montar_mensagem_emergencia
from app.services.whatsapp import Desfecho, ResultadoEnvio
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


# --- SOS-07: retentativas (Regra 04) ----------------------------------------

TEMPORARIA = ResultadoEnvio(Desfecho.FALHA_TEMPORARIA, "HTTP_503")
DEFINITIVA = ResultadoEnvio(Desfecho.FALHA_DEFINITIVA, "HTTP_400")


class RelogioFalso:
    """Registra as esperas pedidas e o status do alerta no momento de cada uma."""

    def __init__(self, banco_migrado, alerta_id):
        self._banco, self._alerta_id = banco_migrado, alerta_id
        self.esperas: list[float] = []
        self.status_durante: list[str] = []

    def __call__(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.status_durante.append(_alerta(self._banco, self._alerta_id).status_envio)


def _despachar(banco_migrado, fabrica, alerta_id, falso) -> RelogioFalso:
    relogio = RelogioFalso(banco_migrado, alerta_id)
    despachar_alerta(alerta_id, fabrica_sessao=fabrica, enviador=falso, esperar=relogio)
    return relogio


def falha_temporaria_deve_ser_tentada_de_novo_apos_5_segundos(banco_migrado, fabrica):
    _, alerta_id, _ = _preparar(banco_migrado, APTO)

    relogio = _despachar(banco_migrado, fabrica, alerta_id, EnviadorWhatsAppFalso([TEMPORARIA]))

    assert relogio.esperas == [5]
    assert tuple(_alerta(banco_migrado, alerta_id)) == ("ENVIADO", 2)
    linhas = [(t.numero_tentativa, t.status, t.erro_codigo) for t in _tentativas(banco_migrado, alerta_id)]
    assert linhas == [(1, "FALHOU", "HTTP_503"), (2, "SUCESSO", None)]


def alerta_deve_continuar_pendente_entre_rodadas(banco_migrado, fabrica):
    _, alerta_id, _ = _preparar(banco_migrado, APTO)

    relogio = _despachar(
        banco_migrado, fabrica, alerta_id, EnviadorWhatsAppFalso([TEMPORARIA, TEMPORARIA])
    )

    assert relogio.status_durante == ["PENDENTE", "PENDENTE"]


def alerta_com_cinco_falhas_temporarias_deve_virar_erro_apos_esperas_5_10_15_20(banco_migrado, fabrica):
    _, alerta_id, _ = _preparar(banco_migrado, APTO)

    relogio = _despachar(banco_migrado, fabrica, alerta_id, EnviadorWhatsAppFalso([TEMPORARIA] * 6))

    assert relogio.esperas == [5, 10, 15, 20]
    assert tuple(_alerta(banco_migrado, alerta_id)) == ("ERRO", 5)
    tentativas = _tentativas(banco_migrado, alerta_id)
    assert [(t.numero_tentativa, t.status) for t in tentativas] == [(n, "FALHOU") for n in range(1, 6)]


def falha_definitiva_nao_deve_ser_tentada_de_novo(banco_migrado, fabrica):
    _, alerta_id, _ = _preparar(banco_migrado, APTO)
    falso = EnviadorWhatsAppFalso([DEFINITIVA])

    relogio = _despachar(banco_migrado, fabrica, alerta_id, falso)

    assert len(falso.envios) == 1
    assert relogio.esperas == []
    assert tuple(_alerta(banco_migrado, alerta_id)) == ("ERRO", 1)


def alerta_deve_virar_enviado_na_primeira_rodada_com_sucesso_e_seguir_tentando_os_demais(
    banco_migrado, fabrica
):
    _, alerta_id, (contato_a, contato_b) = _preparar(banco_migrado, APTO, APTO)
    falso = EnviadorWhatsAppFalso(
        por_telefone={_telefone(banco_migrado, contato_b): [TEMPORARIA, TEMPORARIA]}
    )

    relogio = _despachar(banco_migrado, fabrica, alerta_id, falso)

    assert relogio.status_durante == ["ENVIADO", "ENVIADO"]
    assert tuple(_alerta(banco_migrado, alerta_id)) == ("ENVIADO", 3)
    por_contato = {}
    for t in _tentativas(banco_migrado, alerta_id):
        por_contato.setdefault(t.contato_id, []).append(t.status)
    assert por_contato == {contato_a: ["SUCESSO"], contato_b: ["FALHOU", "FALHOU", "SUCESSO"]}


def alerta_enviado_nao_deve_voltar_para_erro_se_os_demais_esgotarem(banco_migrado, fabrica):
    _, alerta_id, (_, contato_b) = _preparar(banco_migrado, APTO, APTO)
    falso = EnviadorWhatsAppFalso(
        por_telefone={_telefone(banco_migrado, contato_b): [TEMPORARIA] * 5}
    )

    _despachar(banco_migrado, fabrica, alerta_id, falso)

    assert tuple(_alerta(banco_migrado, alerta_id)) == ("ENVIADO", 5)
