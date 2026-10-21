"""Rotas do alerta S.O.S."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import obter_usuario_id
from app.schemas.sos import AlertaCriadoResposta, CriarAlertaRequisicao
from app.services.alertas import ServicoAlertas

router = APIRouter(prefix="/sos", tags=["sos"])


class _ServicoAindaNaoImplementado:
    def criar_alerta(self, usuario_id, dados):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Persistência de alertas pendente (SOS-03).",
        )


def obter_servico_alertas() -> ServicoAlertas:
    return _ServicoAindaNaoImplementado()


@router.post(
    "/alertas",
    status_code=status.HTTP_201_CREATED,
    response_model=AlertaCriadoResposta,
    summary="Cria um alerta S.O.S",
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        422: {"description": "Coordenadas ou mensagem inválidas."},
    },
)
def criar_alerta(
    dados: CriarAlertaRequisicao,
    usuario_id: Annotated[UUID, Depends(obter_usuario_id)],
    servico: Annotated[ServicoAlertas, Depends(obter_servico_alertas)],
) -> AlertaCriadoResposta:
    return servico.criar_alerta(usuario_id, dados)