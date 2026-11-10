import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import RETENCAO_ALERTAS_DIAS
from app.services.retencao import ResumoAnonimizacao, anonimizar_alertas_vencidos
from integracao.fabricas import inserir_alerta, inserir_contato, inserir_tentativa, inserir_usuario

# Relativo ao relógio real: o script usa a hora atual.
AGORA = datetime.now(UTC)

CAMINHO = Path(__file__).parents[2] / "scripts" / "anonimizar_alertas.py"
_spec = importlib.util.spec_from_file_location("anonimizar_alertas", CAMINHO)
anonimizar_alertas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anonimizar_alertas)


@pytest.fixture
def alertas(banco_migrado):
    """Um alerta vencido (181 dias) e um dentro do prazo (179 dias), cada um com uma tentativa."""
    with banco_migrado.begin() as conexao:
        usuario = inserir_usuario(conexao).id
        contato = inserir_contato(conexao, usuario).id
        ids = {}
        for nome, dias in (("vencido", RETENCAO_ALERTAS_DIAS + 1), ("recente", RETENCAO_ALERTAS_DIAS - 1)):
            alerta = inserir_alerta(
                conexao,
                usuario,
                mensagem="socorro",
                status_envio="ENVIADO",
                tentativas=1,
                criado_em=AGORA - timedelta(days=dias),
            ).id
            inserir_tentativa(conexao, alerta, contato, status="SUCESSO")
            ids[nome] = alerta
    return ids


def _estado(banco_migrado, alerta_id):
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text(
                "SELECT a.localizacao IS NULL AS sem_local, a.mensagem, a.anonimizado_em, a.status_envio, "
                "a.tentativas, a.criado_em, a.usuario_id, "
                "(SELECT count(contato_id) FROM tentativas_envio_sos t WHERE t.alerta_id = a.id) AS contatos "
                "FROM alertas_sos a WHERE a.id = :id"
            ),
            {"id": alerta_id},
        ).one()


def _anonimizar(engine, agora=AGORA) -> ResumoAnonimizacao:
    with Session(engine) as sessao:
        resumo = anonimizar_alertas_vencidos(sessao, agora)
        sessao.commit()
    return resumo


def alerta_vencido_deve_perder_local_mensagem_e_contatos_e_manter_estatistica(banco_migrado, alertas):
    antes = _estado(banco_migrado, alertas["vencido"])

    assert _anonimizar(banco_migrado) == ResumoAnonimizacao(alertas=1, tentativas=1)

    depois = _estado(banco_migrado, alertas["vencido"])
    assert (depois.sem_local, depois.mensagem, depois.contatos) == (True, None, 0)
    assert depois.anonimizado_em is not None
    assert (depois.status_envio, depois.tentativas, depois.criado_em, depois.usuario_id) == (
        antes.status_envio,
        antes.tentativas,
        antes.criado_em,
        antes.usuario_id,
    )


def alerta_dentro_do_prazo_nao_deve_ser_tocado(banco_migrado, alertas):
    antes = _estado(banco_migrado, alertas["recente"])

    _anonimizar(banco_migrado)

    assert _estado(banco_migrado, alertas["recente"]) == antes


def anonimizar_de_novo_nao_deve_mudar_nada(banco_migrado, alertas):
    _anonimizar(banco_migrado)
    primeira = _estado(banco_migrado, alertas["vencido"])

    assert _anonimizar(banco_migrado, AGORA + timedelta(days=1)) == ResumoAnonimizacao(alertas=0, tentativas=0)
    assert _estado(banco_migrado, alertas["vencido"]) == primeira


def comando_sem_gravar_deve_mostrar_a_contagem_sem_alterar_o_banco(
    banco_migrado, alertas, url_teste, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", url_teste)
    antes = _estado(banco_migrado, alertas["vencido"])

    assert anonimizar_alertas.main([]) == 0

    assert _estado(banco_migrado, alertas["vencido"]) == antes
    saida = capsys.readouterr().out
    assert "Alertas: 1" in saida and "--gravar" in saida
    assert "teste:teste" not in saida


def comando_com_gravar_deve_anonimizar(banco_migrado, alertas, url_teste, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", url_teste)

    assert anonimizar_alertas.main(["--gravar"]) == 0

    assert _estado(banco_migrado, alertas["vencido"]).sem_local is True
    assert _estado(banco_migrado, alertas["recente"]).sem_local is False
