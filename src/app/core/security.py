from uuid import UUID

import jwt


class TokenInvalido(Exception):
    pass


def extrair_usuario_id(token: str, segredo: str) -> UUID:
    try:
        payload = jwt.decode(
            token, segredo, algorithms=["HS256"], options={"require": ["sub", "exp"]}
        )
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as erro:
        raise TokenInvalido from erro
