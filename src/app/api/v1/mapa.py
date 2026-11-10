from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import obter_usuario_id
from app.constants import LIMITE_REGIOES_MAPA, RAIO_MAXIMO_MAPA_M, RAIO_PADRAO_MAPA_M
from app.db.sessao import obter_sessao
from app.schemas.mapa import RegiaoResposta
from app.services import mapa as servico

# A pessoa usuária vem antes da sessão: sem token válido, o banco nem é aberto.
UsuarioId = Annotated[UUID, Depends(obter_usuario_id)]
Sessao = Annotated[Session, Depends(obter_sessao)]

router = APIRouter(prefix="/api/v1/mapa", tags=["mapa"])


@router.get(
    "/regioes",
    response_model=list[RegiaoResposta],
    summary="Regiões de risco próximas",
    description=(
        "Distritos com a borda a até `raio` metros do ponto, do mais próximo ao mais "
        f"distante (o distrito onde o ponto está vem primeiro), no máximo {LIMITE_REGIOES_MAPA}. "
        "O score vai de 0 a 100 e a cor segue as faixas verde, amarela e vermelha."
    ),
    responses={401: {"description": "Token ausente, inválido ou expirado."}},
)
def listar_regioes(
    usuario_id: UsuarioId,
    latitude: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    longitude: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
    sessao: Sessao,
    raio: Annotated[int, Query(ge=1, le=RAIO_MAXIMO_MAPA_M, description="Em metros.")] = RAIO_PADRAO_MAPA_M,
):
    return servico.listar_regioes_proximas(sessao, latitude, longitude, raio)
