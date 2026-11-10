from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    StringConstraints,
    model_validator,
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


class AtualizarPerfilRequisicao(BaseModel):
    """PATCH parcial: só os campos enviados mudam. O e-mail não é editável."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"telefone_pessoal": "+5500911111111"}]},
    )

    # Sem `| None`: o padrão nunca é validado, e `null` enviado explicitamente vira 422.
    nome_completo: NomeCompleto = None
    telefone_pessoal: TelefoneE164 = None

    @model_validator(mode="after")
    def _ao_menos_um_campo(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Envie ao menos um campo para alterar.")
        return self


class TrocarSenhaRequisicao(BaseModel):
    """A senha nova segue a política do cadastro; a atual, só não pode ser vazia."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"senha_atual": "senha-ficticia", "senha_nova": "senha-ficticia-nova"}]
        },
    )

    senha_atual: Annotated[str, StringConstraints(min_length=1)]
    senha_nova: SenhaNova


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
