import time
from uuid import UUID

import bcrypt
import jwt

ALGORITMO_JWT = "HS256"


class TokenInvalido(Exception):
    pass


def extrair_usuario_id(token: str, segredo: str) -> UUID:
    try:
        payload = jwt.decode(
            token, segredo, algorithms=[ALGORITMO_JWT], options={"require": ["sub", "exp"]}
        )
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as erro:
        raise TokenInvalido from erro


def emitir_token(
    usuario_id: UUID, segredo: str, validade_min: int, agora: int | None = None
) -> str:
    emitido_em = int(time.time()) if agora is None else agora
    payload = {"sub": str(usuario_id), "iat": emitido_em, "exp": emitido_em + validade_min * 60}
    return jwt.encode(payload, segredo, algorithm=ALGORITMO_JWT)


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), senha_hash.encode())
    except ValueError:
        # Hash que não é bcrypt (ex.: pessoas criadas pelo scripts/token_dev.py).
        return False
