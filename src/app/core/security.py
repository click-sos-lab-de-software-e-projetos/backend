"""Validação de tokens JWT (Regra 09)."""

from uuid import UUID

import jwt

ALGORITMO = "HS256"


class TokenInvalido(Exception):
    """Token expirado, mal assinado ou sem 'sub' válido."""


def extrair_usuario_id(token: str, segredo: str) -> UUID:
    try:
        payload = jwt.decode(
            token, segredo, algorithms=[ALGORITMO], options={"require": ["sub", "exp"]}
        )
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as erro:
        raise TokenInvalido from erro