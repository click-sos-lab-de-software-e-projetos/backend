from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import obter_url_consentimento, obter_usuario_id
from app.constants import LIMITE_CONTATOS_ATIVOS
from app.db.sessao import obter_sessao
from app.schemas.consentimento import LinkConsentimentoResposta
from app.schemas.contatos import (
    AtualizarContatoRequisicao,
    ContatoResposta,
    CriarContatoRequisicao,
)
from app.services import consentimento as servico_consentimento
from app.services import contatos as servico

# A pessoa usuária vem antes da sessão: sem token válido, o banco nem é aberto.
UsuarioId = Annotated[UUID, Depends(obter_usuario_id)]
Sessao = Annotated[Session, Depends(obter_sessao)]

MSG_NAO_ENCONTRADO = "Contato não encontrado."
MSG_JA_CONSENTIU = "Este contato já deu consentimento."
MSG_LIMITE = f"Limite de {LIMITE_CONTATOS_ATIVOS} contatos ativos atingido."

R_401 = {401: {"description": "Token ausente, inválido ou expirado."}}
R_404 = {404: {"description": MSG_NAO_ENCONTRADO}}
R_409 = {409: {"description": MSG_LIMITE}}

router = APIRouter(prefix="/api/v1/contatos", tags=["contatos"], responses=R_401)


def _nao_autenticado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _nao_encontrado() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_NAO_ENCONTRADO)


def _limite() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MSG_LIMITE)


@router.get("", response_model=list[ContatoResposta], summary="Listar meus contatos")
def listar_contatos(usuario_id: UsuarioId, sessao: Sessao):
    return servico.listar(sessao, usuario_id)


@router.post(
    "",
    response_model=ContatoResposta,
    status_code=status.HTTP_201_CREATED,
    responses=R_409,
    summary="Cadastrar contato",
    description=(
        f"Cria um contato ativo. Cada pessoa tem no máximo {LIMITE_CONTATOS_ATIVOS} "
        "contatos ativos. O consentimento (`consentido_em`) começa vazio."
    ),
)
def criar_contato(dados: CriarContatoRequisicao, usuario_id: UsuarioId, sessao: Sessao):
    try:
        return servico.criar(sessao, usuario_id, dados)
    except servico.UsuarioNaoEncontrado:
        raise _nao_autenticado() from None
    except servico.LimiteDeContatosAtivos:
        raise _limite() from None


@router.get(
    "/{contato_id}", response_model=ContatoResposta, responses=R_404, summary="Ver contato"
)
def obter_contato(contato_id: UUID, usuario_id: UsuarioId, sessao: Sessao):
    try:
        return servico.obter(sessao, usuario_id, contato_id)
    except servico.ContatoNaoEncontrado:
        raise _nao_encontrado() from None


@router.patch(
    "/{contato_id}",
    response_model=ContatoResposta,
    responses={**R_404, **R_409},
    summary="Editar contato",
    description=(
        "Atualização parcial. Reativar um contato respeita o limite de ativos. "
        "Trocar o telefone apaga o consentimento, a recusa e o link pendente."
    ),
)
def atualizar_contato(
    contato_id: UUID, dados: AtualizarContatoRequisicao, usuario_id: UsuarioId, sessao: Sessao
):
    try:
        return servico.atualizar(sessao, usuario_id, contato_id, dados)
    except servico.UsuarioNaoEncontrado:
        raise _nao_autenticado() from None
    except servico.ContatoNaoEncontrado:
        raise _nao_encontrado() from None
    except servico.LimiteDeContatosAtivos:
        raise _limite() from None


@router.delete(
    "/{contato_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=R_404,
    summary="Remover contato",
)
def remover_contato(contato_id: UUID, usuario_id: UsuarioId, sessao: Sessao) -> Response:
    try:
        servico.remover(sessao, usuario_id, contato_id)
    except servico.ContatoNaoEncontrado:
        raise _nao_encontrado() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{contato_id}/consentimento",
    response_model=LinkConsentimentoResposta,
    status_code=status.HTTP_201_CREATED,
    responses={**R_404, 409: {"description": MSG_JA_CONSENTIU}},
    summary="Gerar link de consentimento",
    description=(
        "Gera o link de uso único que a pessoa envia ao contato. Gerar de novo "
        "invalida o link anterior. O token vai no fragmento (`#token=`), que o "
        "navegador não envia ao servidor da página."
    ),
)
def gerar_link_consentimento(
    contato_id: UUID,
    usuario_id: UsuarioId,
    sessao: Sessao,
    url_pagina: Annotated[str, Depends(obter_url_consentimento)],
):
    try:
        link = servico_consentimento.gerar_link(sessao, usuario_id, contato_id)
    except servico.ContatoNaoEncontrado:
        raise _nao_encontrado() from None
    except servico_consentimento.ContatoJaConsentiu:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MSG_JA_CONSENTIU) from None
    return LinkConsentimentoResposta(url=f"{url_pagina}#token={link.token}", expira_em=link.expira_em)
