"""Criação do alerta S.O.S (SOS-03, Regras 01, 02 e 03).

Grava o alerta como PENDENTE e devolve; o despacho por WhatsApp é do worker
(SOS-06), então nada aqui chama serviço externo.
"""

from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models import AlertaSos, ContatoEmergencia, Usuario
from app.schemas.sos import CriarAlertaRequisicao

SRID_WGS84 = 4326


class UsuarioNaoEncontrado(Exception):
    pass


class SemContatosAptos(Exception):
    """Nenhum contato ativo e com consentimento registrado."""


class AlertaNaoEncontrado(Exception):
    """Alerta inexistente ou de outra pessoa: os dois casos são indistinguíveis."""


def obter_alerta(sessao: Session, usuario_id: UUID, alerta_id: UUID) -> AlertaSos:
    alerta = sessao.scalar(
        select(AlertaSos).where(AlertaSos.id == alerta_id, AlertaSos.usuario_id == usuario_id)
    )
    if alerta is None:
        raise AlertaNaoEncontrado
    return alerta


def listar_alertas(sessao: Session, usuario_id: UUID, limite: int) -> list[AlertaSos]:
    return list(
        sessao.scalars(
            select(AlertaSos)
            .where(AlertaSos.usuario_id == usuario_id)
            .order_by(AlertaSos.criado_em.desc(), AlertaSos.id)
            .limit(limite)
        )
    )


def criar_alerta(sessao: Session, usuario_id: UUID, dados: CriarAlertaRequisicao) -> AlertaSos:
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNaoEncontrado
    if _contar_contatos_aptos(sessao, usuario_id) == 0:
        raise SemContatosAptos

    alerta = AlertaSos(
        usuario_id=usuario_id,
        # ST_MakePoint recebe longitude primeiro (x, y).
        localizacao=func.ST_SetSRID(func.ST_MakePoint(dados.longitude, dados.latitude), SRID_WGS84),
        # Sem mensagem no corpo, vale a salva em Ajustes; sem as duas, NULL e o SOS-04 usa a padrão
        # da Regra 02. O alerta guarda a cópia: mudar Ajustes depois não altera alertas antigos.
        mensagem=dados.mensagem or usuario.mensagem_sos or None,
    )
    sessao.add(alerta)
    sessao.flush()
    sessao.refresh(alerta)  # carrega status_envio e criado_em gerados pelo banco
    sessao.commit()
    return alerta


def condicoes_contato_apto(usuario_id: UUID) -> tuple[ColumnElement[bool], ...]:
    """Contato que pode receber o alerta: da pessoa, ativo e com consentimento (Regra 03)."""
    return (
        ContatoEmergencia.usuario_id == usuario_id,
        ContatoEmergencia.ativo.is_(True),
        ContatoEmergencia.consentido_em.is_not(None),
    )


def _contar_contatos_aptos(sessao: Session, usuario_id: UUID) -> int:
    return sessao.scalar(
        select(func.count())
        .select_from(ContatoEmergencia)
        .where(*condicoes_contato_apto(usuario_id))
    )
