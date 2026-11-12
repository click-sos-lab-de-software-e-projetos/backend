from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt, obter_usuario_id, obter_validade_jwt_min
from app.constants import TAMANHO_MINIMO_SENHA
from app.core.security import emitir_token
from app.db.sessao import obter_sessao
from app.schemas.auth import (
    AtualizarPerfilRequisicao,
    CadastroRequisicao,
    ExcluirContaRequisicao,
    LoginRequisicao,
    TokenResposta,
    TrocarSenhaRequisicao,
    UsuarioResposta,
)
from app.services import auth as servico

# A pessoa usuária vem antes da sessão: sem token válido, o banco nem é aberto.
UsuarioId = Annotated[UUID, Depends(obter_usuario_id)]
Sessao = Annotated[Session, Depends(obter_sessao)]
Segredo = Annotated[str, Depends(obter_segredo_jwt)]
ValidadeMin = Annotated[int, Depends(obter_validade_jwt_min)]

MSG_EMAIL_EM_USO = "E-mail já cadastrado."
MSG_CREDENCIAIS = "E-mail ou senha inválidos."
MSG_SENHA_ATUAL = "Senha atual incorreta."
MSG_SENHA_INCORRETA = "Senha incorreta."
MSG_ALERTA_EM_ENVIO = "Há um alerta S.O.S em envio. Tente de novo quando o envio terminar."
RESPOSTA_401 = {401: {"description": "Token ausente, inválido ou expirado."}}

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


@router.get(
    "/me",
    response_model=UsuarioResposta,
    summary="Ver meu perfil",
    description="Devolve a pessoa usuária do token, sem senha nem hash.",
    responses=RESPOSTA_401,
)
def obter_perfil(usuario_id: UsuarioId, sessao: Sessao):
    try:
        return servico.obter(sessao, usuario_id)
    except servico.UsuarioNaoEncontrado:
        raise _nao_autenticado() from None


@router.patch(
    "/me",
    response_model=UsuarioResposta,
    summary="Editar meu perfil",
    description=(
        "Altera `nome_completo` e/ou `telefone_pessoal`; só os campos enviados mudam. "
        "O e-mail não é editável."
    ),
    responses={
        **RESPOSTA_401,
        422: {"description": "Corpo vazio, campo nulo, valor inválido ou campo não editável (como `email`)."},
    },
)
def editar_perfil(dados: AtualizarPerfilRequisicao, usuario_id: UsuarioId, sessao: Sessao):
    try:
        return servico.atualizar_perfil(sessao, usuario_id, dados)
    except servico.UsuarioNaoEncontrado:
        raise _nao_autenticado() from None


@router.post(
    "/me/senha",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Trocar minha senha",
    description=(
        f"Exige a senha atual. A nova precisa de ao menos {TAMANHO_MINIMO_SENHA} caracteres. "
        "Tokens já emitidos continuam válidos até expirar."
    ),
    responses={
        400: {"description": MSG_SENHA_ATUAL},
        **RESPOSTA_401,
        422: {"description": "Corpo inválido (senha nova fora da política ou campo extra)."},
    },
)
def trocar_senha(dados: TrocarSenhaRequisicao, usuario_id: UsuarioId, sessao: Sessao):
    try:
        servico.trocar_senha(sessao, usuario_id, dados.senha_atual, dados.senha_nova)
    except servico.UsuarioNaoEncontrado:
        raise _nao_autenticado() from None
    except servico.SenhaAtualIncorreta:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MSG_SENHA_ATUAL) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Excluir minha conta",
    description=(
        "Exige a senha. Apaga a pessoa, os contatos e os alertas que ela marcou no mapa. Os alertas de S.O.S ficam "
        "anonimizados, sem dono, coordenadas nem mensagem, só para estatística. "
        "Não dá para desfazer."
    ),
    responses={
        400: {"description": MSG_SENHA_INCORRETA},
        **RESPOSTA_401,
        409: {"description": MSG_ALERTA_EM_ENVIO},
        422: {"description": "Corpo inválido (sem senha ou com campo extra)."},
    },
)
def excluir_conta(dados: ExcluirContaRequisicao, usuario_id: UsuarioId, sessao: Sessao):
    try:
        servico.excluir_conta(sessao, usuario_id, dados.senha)
    except servico.UsuarioNaoEncontrado:
        raise _nao_autenticado() from None
    except servico.SenhaAtualIncorreta:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=MSG_SENHA_INCORRETA) from None
    except servico.AlertaEmEnvio:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MSG_ALERTA_EM_ENVIO) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _nao_autenticado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
