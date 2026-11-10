"""Envio do alerta S.O.S aos contatos, depois da resposta HTTP (SOS-06).

Roda como BackgroundTask: a rota responde com o alerta PENDENTE e só então
este módulo envia, com sessão própria, e grava cada tentativa.
"""

import logging
from collections.abc import Callable
from functools import lru_cache, partial
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

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
    alerta_id: UUID, fabrica_sessao: FabricaSessao, enviador: EnviadorWhatsApp
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
        enviados = 0
        for contato in contatos:
            resultado = enviador.enviar(contato.telefone_whatsapp, texto)
            sucesso = resultado.desfecho == Desfecho.ENVIADO
            enviados += sucesso
            sessao.add(
                TentativaEnvioSos(
                    alerta_id=alerta.id,
                    contato_id=contato.id,
                    numero_tentativa=1,
                    status="SUCESSO" if sucesso else "FALHOU",
                    erro_codigo=resultado.erro_codigo,
                )
            )
        alerta.tentativas = 1
        alerta.status_envio = "ENVIADO" if enviados else "ERRO"
        sessao.commit()


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
