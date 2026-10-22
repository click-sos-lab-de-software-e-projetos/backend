import os
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.constants import NOME_VARIAVEL_SEGREDO_JWT
from app.core.security import TokenInvalido, extrair_usuario_id

esquema_bearer = HTTPBearer(auto_error=False)


def obter_segredo_jwt() -> str:
    segredo = os.environ.get(NOME_VARIAVEL_SEGREDO_JWT)
    if not segredo:
        raise RuntimeError(f"{NOME_VARIAVEL_SEGREDO_JWT} não configurada.")
    return segredo


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
