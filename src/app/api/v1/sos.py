from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import obter_usuario_id
from app.db.sessao import obter_sessao
from app.schemas.sos import AlertaCriadoResposta, CriarAlertaRequisicao
from app.services import alertas as servico

# A pessoa usuária vem antes da sessão: sem token válido, o banco nem é aberto.
UsuarioId = Annotated[UUID, Depends(obter_usuario_id)]
Sessao = Annotated[Session, Depends(obter_sessao)]

MSG_SEM_CONTATOS = (
    "Nenhum contato ativo com consentimento registrado. "
    "Cadastre um contato e confirme o consentimento antes de acionar o S.O.S."
)

router = APIRouter(prefix="/api/v1/sos", tags=["sos"])


@router.post(
    "/alertas",
    response_model=AlertaCriadoResposta,
    status_code=status.HTTP_201_CREATED,
    summary="Acionar o S.O.S",
    description=(
        "Grava o alerta como `PENDENTE` e responde na hora; o envio aos contatos "
        "acontece em segundo plano. A pessoa usuária vem do token, nunca do corpo."
    ),
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        422: {
            "description": (
                "Corpo inválido (coordenada fora do intervalo, mensagem acima de 255 "
                "caracteres, campo extra) ou nenhum contato ativo com consentimento."
            )
        },
    },
)
def criar_alerta(dados: CriarAlertaRequisicao, usuario_id: UsuarioId, sessao: Sessao):
    try:
        return servico.criar_alerta(sessao, usuario_id, dados)
    except servico.UsuarioNaoEncontrado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except servico.SemContatosAptos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=MSG_SEM_CONTATOS
        ) from None
