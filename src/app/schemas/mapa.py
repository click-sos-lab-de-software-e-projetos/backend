from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.constants import LIMITE_TEXTO_FEEDBACK


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


CategoriaFeedback = Literal["ILUMINACAO", "ASSALTO", "ASSEDIO", "MOVIMENTO", "POLICIAMENTO", "OUTRO"]
TextoFeedback = Annotated[str, StringConstraints(strip_whitespace=True, max_length=LIMITE_TEXTO_FEEDBACK)]


class CriarFeedbackRequisicao(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"categoria": "ILUMINACAO", "texto": "Rua sem iluminação à noite"}]},
    )

    categoria: CategoriaFeedback
    texto: TextoFeedback | None = Field(default=None, description="Opcional, exceto na categoria OUTRO.")

    @field_validator("texto")
    @classmethod
    def _vazio_vira_nulo(cls, texto: str | None) -> str | None:
        return texto or None

    @model_validator(mode="after")
    def _outro_exige_texto(self) -> Self:
        if self.categoria == "OUTRO" and self.texto is None:
            raise ValueError("A categoria OUTRO exige texto.")
        return self


class FeedbackCriadoResposta(BaseModel):
    """Confirma o envio. Não devolve o texto nem quem enviou."""

    id: UUID
    regiao_id: str
    categoria: CategoriaFeedback
    status: Literal["PENDENTE"]
    criado_em: datetime
