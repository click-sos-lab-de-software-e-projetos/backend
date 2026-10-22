"""Criação do alerta S.O.S (SOS-03, Regras 01, 02 e 03).

Grava o alerta como PENDENTE e devolve; o despacho por WhatsApp é do worker
(SOS-06), então nada aqui chama serviço externo.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AlertaSos, ContatoEmergencia, Usuario
from app.schemas.sos import CriarAlertaRequisicao

SRID_WGS84 = 4326


class UsuarioNaoEncontrado(Exception):
    pass


class SemContatosAptos(Exception):
    """Nenhum contato ativo e com consentimento registrado."""


def criar_alerta(sessao: Session, usuario_id: UUID, dados: CriarAlertaRequisicao) -> AlertaSos:
    if sessao.get(Usuario, usuario_id) is None:
        raise UsuarioNaoEncontrado
    if _contar_contatos_aptos(sessao, usuario_id) == 0:
        raise SemContatosAptos

    alerta = AlertaSos(
        usuario_id=usuario_id,
        # ST_MakePoint recebe longitude primeiro (x, y).
        localizacao=func.ST_SetSRID(func.ST_MakePoint(dados.longitude, dados.latitude), SRID_WGS84),
        # Vazio vira NULL; o SOS-04 aplica a mensagem padrão da Regra 02.
        mensagem=dados.mensagem or None,
    )
    sessao.add(alerta)
    sessao.flush()
    sessao.refresh(alerta)  # carrega status_envio e criado_em gerados pelo banco
    sessao.commit()
    return alerta


def _contar_contatos_aptos(sessao: Session, usuario_id: UUID) -> int:
    return sessao.scalar(
        select(func.count())
        .select_from(ContatoEmergencia)
        .where(
            ContatoEmergencia.usuario_id == usuario_id,
            ContatoEmergencia.ativo.is_(True),
            ContatoEmergencia.consentido_em.is_not(None),
        )
    )
