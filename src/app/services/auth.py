"""Cadastro, login, perfil e exclusão de conta (AUTH-01, Tarefas 7 e 10, Regras 08 e 09).

O login não revela se o e-mail existe: e-mail desconhecido e senha errada
lançam a mesma exceção e gastam o mesmo tempo de bcrypt.
"""

from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import gerar_hash_senha, verificar_senha
from app.db.models import AlertaSos, Usuario
from app.schemas.auth import AtualizarPerfilRequisicao, CadastroRequisicao
from app.services.retencao import anonimizar_alertas_da_pessoa

INDICE_EMAIL_UNICO = "uq_usuarios_email_minusculo"


class EmailJaCadastrado(Exception):
    pass


class CredenciaisInvalidas(Exception):
    pass


class UsuarioNaoEncontrado(Exception):
    pass


class SenhaAtualIncorreta(Exception):
    pass


class AlertaEmEnvio(Exception):
    """A pessoa tem um alerta PENDENTE; a conta só pode ser excluída depois do envio."""


def cadastrar(sessao: Session, dados: CadastroRequisicao) -> Usuario:
    campos = dados.model_dump(exclude={"senha"})
    usuario = Usuario(**campos, senha_hash=gerar_hash_senha(dados.senha))
    sessao.add(usuario)
    try:
        sessao.flush()
    except IntegrityError as erro:
        sessao.rollback()
        if _violou_email_unico(erro):
            raise EmailJaCadastrado from None
        raise
    sessao.refresh(usuario)  # carrega id e criado_em gerados pelo banco
    sessao.commit()
    return usuario


def autenticar(sessao: Session, email: str, senha: str) -> Usuario:
    usuario = sessao.scalar(select(Usuario).where(func.lower(Usuario.email) == email.lower()))
    if usuario is None:
        verificar_senha(senha, _hash_de_referencia())
        raise CredenciaisInvalidas
    if not verificar_senha(senha, usuario.senha_hash):
        raise CredenciaisInvalidas
    return usuario


def obter(sessao: Session, usuario_id: UUID) -> Usuario:
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNaoEncontrado
    return usuario


def atualizar_perfil(sessao: Session, usuario_id: UUID, dados: AtualizarPerfilRequisicao) -> Usuario:
    usuario = obter(sessao, usuario_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)
    sessao.commit()
    return usuario


def trocar_senha(sessao: Session, usuario_id: UUID, senha_atual: str, senha_nova: str) -> None:
    """Tokens emitidos antes continuam válidos até expirar: não há lista de revogação."""
    usuario = obter(sessao, usuario_id)
    if not verificar_senha(senha_atual, usuario.senha_hash):
        raise SenhaAtualIncorreta
    usuario.senha_hash = gerar_hash_senha(senha_nova)
    sessao.commit()


def excluir_conta(sessao: Session, usuario_id: UUID, senha: str) -> None:
    """Apaga a pessoa; contatos e alertas do mapa caem por CASCADE; os de S.O.S ficam anonimizados, sem dono."""
    # FOR UPDATE: um alerta criado durante a exclusão espera, e depois falha pela FK.
    usuario = sessao.scalar(select(Usuario).where(Usuario.id == usuario_id).with_for_update())
    if usuario is None:
        raise UsuarioNaoEncontrado
    if not verificar_senha(senha, usuario.senha_hash):
        raise SenhaAtualIncorreta
    pendente = exists().where(AlertaSos.usuario_id == usuario_id, AlertaSos.status_envio == "PENDENTE")
    if sessao.scalar(select(pendente)):
        raise AlertaEmEnvio
    anonimizar_alertas_da_pessoa(sessao, usuario_id, datetime.now(UTC))
    sessao.execute(delete(Usuario).where(Usuario.id == usuario_id))
    sessao.commit()


def _violou_email_unico(erro: IntegrityError) -> bool:
    return (
        isinstance(erro.orig, UniqueViolation)
        and erro.orig.diag.constraint_name == INDICE_EMAIL_UNICO
    )


@lru_cache(maxsize=1)
def _hash_de_referencia() -> str:
    return gerar_hash_senha("senha-que-ninguem-usa")
