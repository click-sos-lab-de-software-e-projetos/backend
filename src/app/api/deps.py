import os
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.constants import (
    EXPIRACAO_JWT_PADRAO_MIN,
    NOME_VARIAVEL_EXPIRACAO_JWT,
    NOME_VARIAVEL_SEGREDO_JWT,
    NOME_VARIAVEL_URL_CONSENTIMENTO,
)
from app.core.security import TokenInvalido, extrair_usuario_id

esquema_bearer = HTTPBearer(auto_error=False)


def obter_segredo_jwt() -> str:
    segredo = os.environ.get(NOME_VARIAVEL_SEGREDO_JWT)
    if not segredo:
        raise RuntimeError(f"{NOME_VARIAVEL_SEGREDO_JWT} não configurada.")
    return segredo


def obter_url_consentimento() -> str:
    url = os.environ.get(NOME_VARIAVEL_URL_CONSENTIMENTO)
    if not url:
        raise RuntimeError(f"{NOME_VARIAVEL_URL_CONSENTIMENTO} não configurada.")
    return url


def obter_validade_jwt_min() -> int:
    valor = os.environ.get(NOME_VARIAVEL_EXPIRACAO_JWT)
    if not valor:
        return EXPIRACAO_JWT_PADRAO_MIN
    try:
        minutos = int(valor)
    except ValueError:
        minutos = 0
    if minutos <= 0:
        raise RuntimeError(f"{NOME_VARIAVEL_EXPIRACAO_JWT} deve ser um inteiro positivo.")
    return minutos


def _nao_autenticado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def obter_usuario_id(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    segredo: Annotated[str, Depends(obter_segredo_jwt)],
) -> UUID:
    if credenciais is None:
        raise _nao_autenticado()
    try:
        return extrair_usuario_id(credenciais.credentials, segredo)
    except TokenInvalido:
        raise _nao_autenticado() from None
