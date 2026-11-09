from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    StringConstraints,
)

from app.constants import (
    LIMITE_BYTES_SENHA,
    LIMITE_EMAIL,
    LIMITE_NOME_COMPLETO,
    PADRAO_TELEFONE_E164,
    TAMANHO_MINIMO_SENHA,
)


def _caber_no_bcrypt(senha: str) -> str:
    if len(senha.encode()) > LIMITE_BYTES_SENHA:
        raise ValueError(f"A senha aceita no máximo {LIMITE_BYTES_SENHA} bytes.")
    return senha


# O e-mail é único sem diferenciar maiúsculas (índice lower(email) da migração 0002).
Email = Annotated[EmailStr, StringConstraints(max_length=LIMITE_EMAIL), AfterValidator(str.lower)]
NomeCompleto = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=LIMITE_NOME_COMPLETO)
]
SenhaNova = Annotated[
    str, StringConstraints(min_length=TAMANHO_MINIMO_SENHA), AfterValidator(_caber_no_bcrypt)
]
TelefoneE164 = Annotated[str, StringConstraints(pattern=PADRAO_TELEFONE_E164)]

EXEMPLO_CADASTRO = {
    "nome_completo": "Pessoa Ficticia",
    "email": "pessoa@example.com",
    "senha": "senha-ficticia",
    "telefone_pessoal": "+5500900000000",
}


class CadastroRequisicao(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EXEMPLO_CADASTRO]})

    nome_completo: NomeCompleto
    email: Email
    senha: SenhaNova
    telefone_pessoal: TelefoneE164


class LoginRequisicao(BaseModel):
    """Sem a política de senha: ela vale só no cadastro, e o login responde 401 genérico."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"email": "pessoa@example.com", "senha": "senha-ficticia"}]
        },
    )

    email: Email
    senha: Annotated[str, StringConstraints(min_length=1)]


class UsuarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome_completo: str
    email: str
    telefone_pessoal: str
    criado_em: datetime


class TokenResposta(BaseModel):
    """Formato do OAuth2: o app envia `access_token` em `Authorization: Bearer`."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
