"""Contratos HTTP do alerta S.O.S."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

LIMITE_MENSAGEM = 255

MensagemLivre = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=LIMITE_MENSAGEM)
]


class CriarAlertaRequisicao(BaseModel):
    """Corpo enviado pelo app. Não aceita identificador de usuário (Regra 01)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"latitude": -23.55, "longitude": -46.63, "mensagem": "Preciso de ajuda"}]
        },
    )

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    mensagem: MensagemLivre | None = Field(
        default=None,
        description="Texto livre opcional. Vazio usa a mensagem padrão (SOS-04).",
    )


class AlertaCriadoResposta(BaseModel):
    """Confirma a criação. Não ecoa coordenadas, por privacidade."""

    id: UUID
    status_envio: Literal["PENDENTE"]
    criado_em: datetime