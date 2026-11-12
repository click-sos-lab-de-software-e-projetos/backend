from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.constants import LIMITE_TEXTO_ALERTA_COMUNIDADE


class Centroide(BaseModel):
    latitude: float
    longitude: float


class RegiaoResposta(BaseModel):
    """Só o que o app desenha. Nunca o UUID interno, os limites nem as ocorrências."""

    id: str
    nome: str
    centroide: Centroide
    score: int
    cor_hex: str
    raio_metros: int


CategoriaAlerta = Literal["ILUMINACAO", "ASSALTO", "ASSEDIO", "MOVIMENTO", "POLICIAMENTO", "OUTRO"]
TextoAlerta = Annotated[str, StringConstraints(strip_whitespace=True, max_length=LIMITE_TEXTO_ALERTA_COMUNIDADE)]


class CriarAlertaComunidadeRequisicao(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"categoria": "ILUMINACAO", "texto": "Rua sem iluminação", "latitude": -23.55, "longitude": -46.63}
            ]
        },
    )

    categoria: CategoriaAlerta
    texto: TextoAlerta | None = Field(default=None, description="Opcional, exceto na categoria OUTRO.")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)

    @field_validator("texto")
    @classmethod
    def _vazio_vira_nulo(cls, texto: str | None) -> str | None:
        return texto or None

    @model_validator(mode="after")
    def _outro_exige_texto(self) -> Self:
        if self.categoria == "OUTRO" and self.texto is None:
            raise ValueError("A categoria OUTRO exige texto.")
        return self


class AlertaComunidadeResposta(BaseModel):
    """O que o mapa mostra. Nunca quem criou o alerta."""

    id: UUID
    categoria: CategoriaAlerta
    texto: str | None
    latitude: float
    longitude: float
    criado_em: datetime
