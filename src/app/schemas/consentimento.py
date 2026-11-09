from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

# secrets.token_urlsafe(32) gera 43 caracteres do alfabeto base64url.
TokenConsentimento = Annotated[
    str, StringConstraints(min_length=32, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]


class LinkConsentimentoResposta(BaseModel):
    url: str
    expira_em: datetime


class PedidoConsentimentoRequisicao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: TokenConsentimento


class PedidoConsentimentoResposta(BaseModel):
    nome_contato: str
    nome_solicitante: str
    expira_em: datetime


class RespostaConsentimentoRequisicao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: TokenConsentimento
    aceito: bool


class RespostaConsentimentoResultado(BaseModel):
    status: Literal["ACEITO", "RECUSADO"]
