from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt, obter_validade_jwt_min
from app.constants import TAMANHO_MINIMO_SENHA
from app.core.security import emitir_token
from app.db.sessao import obter_sessao
from app.schemas.auth import (
    CadastroRequisicao,
    LoginRequisicao,
    TokenResposta,
    UsuarioResposta,
)
from app.services import auth as servico

Sessao = Annotated[Session, Depends(obter_sessao)]
Segredo = Annotated[str, Depends(obter_segredo_jwt)]
ValidadeMin = Annotated[int, Depends(obter_validade_jwt_min)]

MSG_EMAIL_EM_USO = "E-mail já cadastrado."
MSG_CREDENCIAIS = "E-mail ou senha inválidos."

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/cadastro",
    response_model=UsuarioResposta,
    status_code=status.HTTP_201_CREATED,
    summary="Criar conta",
    description=(
        f"Cria a pessoa usuária. A senha precisa de ao menos {TAMANHO_MINIMO_SENHA} "
        "caracteres e é guardada só como hash bcrypt. Não devolve token: em seguida, "
        "use o login."
    ),
    responses={
        409: {"description": MSG_EMAIL_EM_USO},
        422: {"description": "Corpo inválido (e-mail, senha, telefone E.164 ou campo extra)."},
    },
)
def cadastrar(dados: CadastroRequisicao, sessao: Sessao):
    try:
        return servico.cadastrar(sessao, dados)
    except servico.EmailJaCadastrado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=MSG_EMAIL_EM_USO
        ) from None


@router.post(
    "/login",
    response_model=TokenResposta,
    summary="Entrar",
    description=(
        "Troca e-mail e senha por um JWT Bearer. Não há renovação: quando o token "
        "expirar (`expires_in`, em segundos), as rotas privadas respondem 401 e é "
        "preciso entrar de novo."
    ),
    responses={
        401: {"description": MSG_CREDENCIAIS},
        422: {"description": "Corpo inválido."},
    },
)
def login(dados: LoginRequisicao, sessao: Sessao, segredo: Segredo, validade_min: ValidadeMin):
    try:
        usuario = servico.autenticar(sessao, dados.email, dados.senha)
    except servico.CredenciaisInvalidas:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MSG_CREDENCIAIS,
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return TokenResposta(
        access_token=emitir_token(usuario.id, segredo, validade_min),
        expires_in=validade_min * 60,
    )
