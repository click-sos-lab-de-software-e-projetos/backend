"""Consentimento do contato por link de uso único (Regra 03).

O link leva um token aleatório; o banco guarda só o SHA-256 dele. Token
desconhecido, expirado ou já usado são indistinguíveis para quem chama.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import VALIDADE_LINK_CONSENTIMENTO_DIAS
from app.db.models import ContatoEmergencia, Usuario
from app.services import contatos


class LinkInvalido(Exception):
    pass


class ContatoJaConsentiu(Exception):
    pass


@dataclass(frozen=True)
class LinkGerado:
    token: str
    expira_em: datetime


@dataclass(frozen=True)
class Pedido:
    nome_contato: str
    nome_solicitante: str
    expira_em: datetime


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def gerar_link(sessao: Session, usuario_id: UUID, contato_id: UUID) -> LinkGerado:
    contato = contatos.obter(sessao, usuario_id, contato_id)
    if contato.consentido_em is not None:
        raise ContatoJaConsentiu

    token = secrets.token_urlsafe(32)
    expira_em = datetime.now(UTC) + timedelta(days=VALIDADE_LINK_CONSENTIMENTO_DIAS)
    contato.token_consentimento_hash = _hash(token)
    contato.token_consentimento_expira_em = expira_em
    sessao.commit()
    return LinkGerado(token=token, expira_em=expira_em)


def obter_pedido(sessao: Session, token: str) -> Pedido:
    linha = sessao.execute(
        select(ContatoEmergencia, Usuario.nome_completo)
        .join(Usuario, Usuario.id == ContatoEmergencia.usuario_id)
        .where(*_token_valido(token))
    ).one_or_none()
    if linha is None:
        raise LinkInvalido
    contato, nome_solicitante = linha
    return Pedido(
        nome_contato=contato.nome,
        nome_solicitante=nome_solicitante,
        expira_em=contato.token_consentimento_expira_em,
    )


def responder(sessao: Session, token: str, aceito: bool) -> None:
    contato = sessao.scalar(
        select(ContatoEmergencia).where(*_token_valido(token)).with_for_update()
    )
    if contato is None:
        raise LinkInvalido

    agora = datetime.now(UTC)
    contato.consentido_em = agora if aceito else None
    contato.recusado_em = None if aceito else agora
    contato.token_consentimento_hash = None
    contato.token_consentimento_expira_em = None
    sessao.commit()


def _token_valido(token: str):
    return (
        ContatoEmergencia.token_consentimento_hash == _hash(token),
        ContatoEmergencia.token_consentimento_expira_em > datetime.now(UTC),
    )
