"""Cadastro e login (AUTH-01, Regra 09).

O login não revela se o e-mail existe: e-mail desconhecido e senha errada
lançam a mesma exceção e gastam o mesmo tempo de bcrypt.
"""

from functools import lru_cache

from psycopg.errors import UniqueViolation
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import gerar_hash_senha, verificar_senha
from app.db.models import Usuario
from app.schemas.auth import CadastroRequisicao

INDICE_EMAIL_UNICO = "uq_usuarios_email_minusculo"


class EmailJaCadastrado(Exception):
    pass


class CredenciaisInvalidas(Exception):
    pass


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


def _violou_email_unico(erro: IntegrityError) -> bool:
    return (
        isinstance(erro.orig, UniqueViolation)
        and erro.orig.diag.constraint_name == INDICE_EMAIL_UNICO
    )


@lru_cache(maxsize=1)
def _hash_de_referencia() -> str:
    return gerar_hash_senha("senha-que-ninguem-usa")
