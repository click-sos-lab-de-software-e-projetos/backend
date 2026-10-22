from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.constants import LIMITE_NOME_CONTATO, PADRAO_TELEFONE_E164

NomeContato = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=LIMITE_NOME_CONTATO)
]
TelefoneE164 = Annotated[str, StringConstraints(pattern=PADRAO_TELEFONE_E164)]

EXEMPLO = {"nome": "Contato Ficticio", "telefone_whatsapp": "+5500900000000"}


class CriarContatoRequisicao(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EXEMPLO]})

    nome: NomeContato
    telefone_whatsapp: TelefoneE164


class AtualizarContatoRequisicao(BaseModel):
    """Atualização parcial: só os campos enviados mudam."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"ativo": False}]}
    )

    nome: NomeContato | None = None
    telefone_whatsapp: TelefoneE164 | None = None
    ativo: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _exigir_algum_campo_sem_null(cls, dados: Any) -> Any:
        if isinstance(dados, dict):
            if not dados:
                raise ValueError("Envie ao menos um campo para atualizar.")
            nulos = sorted(campo for campo, valor in dados.items() if valor is None)
            if nulos:
                raise ValueError(f"Campos não aceitam null: {', '.join(nulos)}.")
        return dados


class ContatoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    telefone_whatsapp: str
    ativo: bool
    consentido_em: datetime | None
    criado_em: datetime
