from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import obter_usuario_id
from app.db.sessao import obter_sessao
from app.schemas.sos import (
    AlertaCriadoResposta,
    AlertaStatusResposta,
    CriarAlertaRequisicao,
)
from app.services import alertas as servico
from app.workers.despacho_sos import Despacho, obter_despacho

# A pessoa usuária vem antes da sessão: sem token válido, o banco nem é aberto.
UsuarioId = Annotated[UUID, Depends(obter_usuario_id)]
Sessao = Annotated[Session, Depends(obter_sessao)]
DespachoAlerta = Annotated[Despacho, Depends(obter_despacho)]

MSG_SEM_CONTATOS = (
    "Nenhum contato ativo com consentimento registrado. "
    "Cadastre um contato e confirme o consentimento antes de acionar o S.O.S."
)
MSG_ALERTA_NAO_ENCONTRADO = "Alerta não encontrado."
LIMITE_PADRAO_LISTA = 20
LIMITE_MAXIMO_LISTA = 50

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
def criar_alerta(
    dados: CriarAlertaRequisicao,
    usuario_id: UsuarioId,
    sessao: Sessao,
    despacho: DespachoAlerta,
    tarefas: BackgroundTasks,
):
    try:
        alerta = servico.criar_alerta(sessao, usuario_id, dados)
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
    # Roda depois que a resposta sai: um WhatsApp lento não atrasa o app (SOS-06).
    tarefas.add_task(despacho, alerta.id)
    return alerta


@router.get(
    "/alertas",
    response_model=list[AlertaStatusResposta],
    summary="Listar os últimos alertas",
    description=(
        "Últimos alertas da pessoa dona do token, do mais recente ao mais antigo, "
        f"no máximo `limite` (padrão {LIMITE_PADRAO_LISTA}, até {LIMITE_MAXIMO_LISTA}). "
        "Não devolve coordenadas, mensagem nem telefones."
    ),
    responses={401: {"description": "Token ausente, inválido ou expirado."}},
)
def listar_alertas(
    usuario_id: UsuarioId,
    sessao: Sessao,
    limite: Annotated[int, Query(ge=1, le=LIMITE_MAXIMO_LISTA)] = LIMITE_PADRAO_LISTA,
):
    return servico.listar_alertas(sessao, usuario_id, limite)


@router.get(
    "/alertas/{alerta_id}",
    response_model=AlertaStatusResposta,
    summary="Consultar o status do alerta",
    description=(
        "Mostra se o alerta já foi enviado aos contatos (`PENDENTE`, `ENVIADO` ou `ERRO`) "
        "e quantas rodadas de envio houve. O app consulta a cada poucos segundos até "
        "`ENVIADO` ou `ERRO`. Não devolve coordenadas, mensagem nem telefones."
    ),
    responses={
        401: {"description": "Token ausente, inválido ou expirado."},
        404: {"description": "Alerta inexistente ou de outra pessoa."},
    },
)
def consultar_alerta(alerta_id: UUID, usuario_id: UsuarioId, sessao: Sessao):
    try:
        return servico.obter_alerta(sessao, usuario_id, alerta_id)
    except servico.AlertaNaoEncontrado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=MSG_ALERTA_NAO_ENCONTRADO
        ) from None
