from pydantic import BaseModel


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
