"""Regras de negócio dos contatos de emergência (CONT-01, Regra 03).

Toda consulta filtra pelo usuario_id vindo do token: o contato de outra
pessoa é indistinguível de um contato inexistente.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import LIMITE_CONTATOS_ATIVOS
from app.db.models import ContatoEmergencia, Usuario
from app.schemas.contatos import AtualizarContatoRequisicao, CriarContatoRequisicao


class ContatoNaoEncontrado(Exception):
    pass


class LimiteDeContatosAtivos(Exception):
    pass


class UsuarioNaoEncontrado(Exception):
    pass


def listar(sessao: Session, usuario_id: UUID) -> list[ContatoEmergencia]:
    consulta = (
        select(ContatoEmergencia)
        .where(ContatoEmergencia.usuario_id == usuario_id)
        .order_by(ContatoEmergencia.criado_em, ContatoEmergencia.id)
    )
    return list(sessao.scalars(consulta))


def obter(sessao: Session, usuario_id: UUID, contato_id: UUID) -> ContatoEmergencia:
    contato = sessao.scalar(
        select(ContatoEmergencia).where(
            ContatoEmergencia.id == contato_id, ContatoEmergencia.usuario_id == usuario_id
        )
    )
    if contato is None:
        raise ContatoNaoEncontrado
    return contato


def criar(
    sessao: Session, usuario_id: UUID, dados: CriarContatoRequisicao
) -> ContatoEmergencia:
    _travar_usuario(sessao, usuario_id)
    _garantir_vaga_para_ativo(sessao, usuario_id)

    contato = ContatoEmergencia(usuario_id=usuario_id, **dados.model_dump())
    sessao.add(contato)
    sessao.flush()
    sessao.refresh(contato)  # carrega ativo e criado_em gerados pelo banco
    sessao.commit()
    return contato


def atualizar(
    sessao: Session, usuario_id: UUID, contato_id: UUID, dados: AtualizarContatoRequisicao
) -> ContatoEmergencia:
    mudancas = dados.model_dump(exclude_unset=True)
    if mudancas.get("ativo"):
        _travar_usuario(sessao, usuario_id)
    contato = obter(sessao, usuario_id, contato_id)

    if mudancas.get("ativo") and not contato.ativo:
        _garantir_vaga_para_ativo(sessao, usuario_id)

    for campo, valor in mudancas.items():
        setattr(contato, campo, valor)
    sessao.commit()
    return contato


def remover(sessao: Session, usuario_id: UUID, contato_id: UUID) -> None:
    sessao.delete(obter(sessao, usuario_id, contato_id))
    sessao.commit()


def _travar_usuario(sessao: Session, usuario_id: UUID) -> None:
    """Serializa as gravações da mesma pessoa.

    Sem o FOR UPDATE, duas requisições simultâneas contariam 2 ativos ao mesmo
    tempo e ambas gravariam, deixando a pessoa com 4.
    """
    encontrado = sessao.scalar(
        select(Usuario.id).where(Usuario.id == usuario_id).with_for_update()
    )
    if encontrado is None:
        raise UsuarioNaoEncontrado


def _garantir_vaga_para_ativo(sessao: Session, usuario_id: UUID) -> None:
    ativos = sessao.scalar(
        select(func.count())
        .select_from(ContatoEmergencia)
        .where(ContatoEmergencia.usuario_id == usuario_id, ContatoEmergencia.ativo.is_(True))
    )
    if ativos >= LIMITE_CONTATOS_ATIVOS:
        raise LimiteDeContatosAtivos
