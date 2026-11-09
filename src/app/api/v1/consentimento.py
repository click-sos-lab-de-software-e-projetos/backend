"""Rotas públicas da página de consentimento.

O token vai no corpo, não no caminho, para não aparecer em logs de acesso.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.sessao import obter_sessao
from app.schemas.consentimento import (
    PedidoConsentimentoRequisicao,
    PedidoConsentimentoResposta,
    RespostaConsentimentoRequisicao,
    RespostaConsentimentoResultado,
)
from app.services import consentimento as servico

Sessao = Annotated[Session, Depends(obter_sessao)]

MSG_LINK_INVALIDO = "Link inválido ou expirado."
R_404 = {404: {"description": MSG_LINK_INVALIDO}}

router = APIRouter(prefix="/api/v1/consentimento", tags=["consentimento"])


def _link_invalido() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_LINK_INVALIDO)


@router.post(
    "/pedido",
    response_model=PedidoConsentimentoResposta,
    responses=R_404,
    summary="Ver pedido de consentimento",
    description="Mostra quem pediu o consentimento. Não devolve telefones.",
)
def ver_pedido(dados: PedidoConsentimentoRequisicao, sessao: Sessao):
    try:
        pedido = servico.obter_pedido(sessao, dados.token)
    except servico.LinkInvalido:
        raise _link_invalido() from None
    return PedidoConsentimentoResposta(
        nome_contato=pedido.nome_contato,
        nome_solicitante=pedido.nome_solicitante,
        expira_em=pedido.expira_em,
    )


@router.post(
    "/resposta",
    response_model=RespostaConsentimentoResultado,
    responses=R_404,
    summary="Aceitar ou recusar",
    description="Grava a resposta do contato. O link deixa de valer depois disso.",
)
def responder(dados: RespostaConsentimentoRequisicao, sessao: Sessao):
    try:
        servico.responder(sessao, dados.token, dados.aceito)
    except servico.LinkInvalido:
        raise _link_invalido() from None
    return RespostaConsentimentoResultado(status="ACEITO" if dados.aceito else "RECUSADO")
