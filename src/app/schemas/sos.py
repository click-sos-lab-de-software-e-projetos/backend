from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.constants import LIMITE_MENSAGEM_SOS

MensagemLivre = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=LIMITE_MENSAGEM_SOS)
]


class CriarAlertaRequisicao(BaseModel):
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
    id: UUID
    status_envio: Literal["PENDENTE"]
    criado_em: datetime
