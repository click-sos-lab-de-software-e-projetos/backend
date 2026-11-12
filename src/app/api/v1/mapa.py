from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import obter_usuario_id
from app.constants import (
    LIMITE_ALERTAS_COMUNIDADE_MAPA,
    LIMITE_REGIOES_MAPA,
    LIMITE_TEXTO_ALERTA_COMUNIDADE,
    RAIO_MAXIMO_MAPA_M,
    RAIO_PADRAO_MAPA_M,
    VALIDADE_ALERTA_COMUNIDADE_HORAS,
)
from app.db.sessao import obter_sessao
from app.schemas.mapa import AlertaComunidadeResposta, CriarAlertaComunidadeRequisicao, RegiaoResposta
from app.services import mapa as servico

# Ao criar alerta, a pessoa usuária vem antes da sessão: sem token válido, o banco nem é aberto.
UsuarioId = Annotated[UUID, Depends(obter_usuario_id)]
Sessao = Annotated[Session, Depends(obter_sessao)]

Latitude = Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)]
Raio = Annotated[int, Query(ge=1, le=RAIO_MAXIMO_MAPA_M, description="Em metros.")]

router = APIRouter(prefix="/api/v1/mapa", tags=["mapa"])


@router.get(
    "/regioes",
    response_model=list[RegiaoResposta],
    summary="Regiões de risco próximas",
    description=(
        "Distritos com a borda a até `raio` metros do ponto, do mais próximo ao mais "
        f"distante (o distrito onde o ponto está vem primeiro), no máximo {LIMITE_REGIOES_MAPA}. "
        "O score vai de 0 a 100 e a cor segue as faixas verde, amarela e vermelha. "
        "Rota pública: não exige token."
    ),
)
def listar_regioes(
    latitude: Latitude,
    longitude: Longitude,
    sessao: Sessao,
    raio: Raio = RAIO_PADRAO_MAPA_M,
):
    return servico.listar_regioes_proximas(sessao, latitude, longitude, raio)


@router.get(
    "/alertas",
    response_model=list[AlertaComunidadeResposta],
    summary="Alertas da comunidade próximos",
    description=(
        f"Alertas criados nas últimas {VALIDADE_ALERTA_COMUNIDADE_HORAS} horas a até `raio` metros do ponto, "
        f"do mais novo ao mais antigo, no máximo {LIMITE_ALERTAS_COMUNIDADE_MAPA}. Não diz quem criou. "
        "Rota pública: não exige token."
    ),
)
def listar_alertas(latitude: Latitude, longitude: Longitude, sessao: Sessao, raio: Raio = RAIO_PADRAO_MAPA_M):
    return servico.listar_alertas_proximos(sessao, latitude, longitude, raio)


@router.post(
    "/alertas",
    response_model=AlertaComunidadeResposta,
    status_code=status.HTTP_201_CREATED,
    summary="Criar alerta no mapa",
    description=(
        "Marca um alerta da comunidade no ponto informado (o app manda a posição do GPS), como no Waze. "
        f"Ele aparece em `GET /mapa/alertas` por {VALIDADE_ALERTA_COMUNIDADE_HORAS} horas e não altera o score "
        "nem a cor do mapa. A pessoa usuária vem do token, nunca do corpo."
    ),
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        422: {
            "description": (
                f"Corpo inválido (categoria desconhecida, texto acima de {LIMITE_TEXTO_ALERTA_COMUNIDADE} "
                "caracteres, categoria OUTRO sem texto, coordenada fora do intervalo, campo extra)."
            )
        },
    },
)
def criar_alerta(dados: CriarAlertaComunidadeRequisicao, usuario_id: UsuarioId, sessao: Sessao):
    try:
        return servico.criar_alerta(sessao, usuario_id, dados)
    except servico.UsuarioNaoEncontrado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
