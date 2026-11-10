"""Envio do alerta S.O.S aos contatos, depois da resposta HTTP (SOS-06).

Roda como BackgroundTask: a rota responde com o alerta PENDENTE e só então
este módulo envia, com sessão própria, e grava cada tentativa.

Retentativas (SOS-07, Regra 04): até 5 rodadas sobre os contatos com falha
temporária, com esperas de 5, 10, 15 e 20 s. O alerta vira ENVIADO no primeiro
contato atendido e ERRO só se ninguém receber.
"""

import logging
import time
from collections.abc import Callable
from functools import lru_cache, partial
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.constants import ESPERAS_RETENTATIVA_S, MAXIMO_TENTATIVAS_ENVIO
from app.db.models import AlertaSos, ContatoEmergencia, TentativaEnvioSos, Usuario
from app.db.sessao import obter_fabrica_sessao
from app.services.alertas import condicoes_contato_apto
from app.services.mensagem_sos import montar_mensagem_emergencia
from app.services.whatsapp import (
    Desfecho,
    EnviadorEvolution,
    EnviadorWhatsApp,
    criar_enviador_evolution,
)

logger = logging.getLogger(__name__)

Despacho = Callable[[UUID], None]
FabricaSessao = sessionmaker[Session]


def despachar_alerta(
    alerta_id: UUID,
    fabrica_sessao: FabricaSessao,
    enviador: EnviadorWhatsApp,
    esperar: Callable[[float], None] = time.sleep,
) -> None:
    with fabrica_sessao() as sessao:
        alerta = sessao.get_one(AlertaSos, alerta_id)
        contatos = sessao.scalars(
            select(ContatoEmergencia).where(*condicoes_contato_apto(alerta.usuario_id))
        ).all()
        if not contatos:
            alerta.status_envio = "ERRO"
            sessao.commit()
            return

        texto = _montar_texto(sessao, alerta)
        pendentes = list(contatos)
        for rodada in range(1, MAXIMO_TENTATIVAS_ENVIO + 1):
            if rodada > 1:
                esperar(ESPERAS_RETENTATIVA_S[rodada - 2])
            pendentes, enviados = _enviar_rodada(sessao, alerta, pendentes, texto, enviador, rodada)
            alerta.tentativas = rodada
            # ENVIADO no primeiro sucesso e não muda mais; quem falhou segue sendo tentado.
            if enviados:
                alerta.status_envio = "ENVIADO"
            # Commit por rodada: o status fica visível para o app durante as esperas.
            sessao.commit()
            if not pendentes:
                break
        if alerta.status_envio == "PENDENTE":
            alerta.status_envio = "ERRO"
            sessao.commit()


def _enviar_rodada(
    sessao: Session,
    alerta: AlertaSos,
    contatos: list[ContatoEmergencia],
    texto: str,
    enviador: EnviadorWhatsApp,
    rodada: int,
) -> tuple[list[ContatoEmergencia], int]:
    """Envia a cada contato; devolve quem tentar de novo (falha temporária) e quantos receberam."""
    repetir, enviados = [], 0
    for contato in contatos:
        resultado = enviador.enviar(contato.telefone_whatsapp, texto)
        sucesso = resultado.desfecho == Desfecho.ENVIADO
        sessao.add(
            TentativaEnvioSos(
                alerta_id=alerta.id,
                contato_id=contato.id,
                numero_tentativa=rodada,
                status="SUCESSO" if sucesso else "FALHOU",
                erro_codigo=resultado.erro_codigo,
            )
        )
        enviados += sucesso
        if resultado.desfecho == Desfecho.FALHA_TEMPORARIA:
            repetir.append(contato)
    return repetir, enviados


def _montar_texto(sessao: Session, alerta: AlertaSos) -> str:
    nome, latitude, longitude = sessao.execute(
        select(
            Usuario.nome_completo,
            func.ST_Y(AlertaSos.localizacao),
            func.ST_X(AlertaSos.localizacao),
        )
        .join(Usuario, Usuario.id == AlertaSos.usuario_id)
        .where(AlertaSos.id == alerta.id)
    ).one()
    return montar_mensagem_emergencia(nome, latitude, longitude, alerta.mensagem).texto


def _marcar_erro(alerta_id: UUID, fabrica_sessao: FabricaSessao, motivo: str) -> None:
    logger.warning("despacho_sos alerta_id=%s sem_envio motivo=%s", alerta_id, motivo)
    with fabrica_sessao() as sessao:
        sessao.get_one(AlertaSos, alerta_id).status_envio = "ERRO"
        sessao.commit()


@lru_cache(maxsize=1)
def obter_enviador_whatsapp() -> EnviadorEvolution:
    # Um httpx.Client para a aplicação inteira; ele é seguro entre threads.
    return criar_enviador_evolution()


def obter_despacho(
    fabrica_sessao: Annotated[FabricaSessao, Depends(obter_fabrica_sessao)],
) -> Despacho:
    """Dependência FastAPI: devolve a função que a rota agenda com o ID do alerta."""
    try:
        enviador = obter_enviador_whatsapp()
    except RuntimeError as erro:
        # A mensagem traz só o nome da variável ausente, nunca valores.
        return partial(_marcar_erro, fabrica_sessao=fabrica_sessao, motivo=str(erro))
    return partial(despachar_alerta, fabrica_sessao=fabrica_sessao, enviador=enviador)
