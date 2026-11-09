from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.auth import CadastroRequisicao, LoginRequisicao, UsuarioResposta

CADASTRO = {
    "nome_completo": "Pessoa Ficticia",
    "email": "pessoa@example.com",
    "senha": "senha-ficticia",
    "telefone_pessoal": "+5500900000000",
}


def cadastro_valido_deve_ser_aceito():
    cadastro = CadastroRequisicao.model_validate(CADASTRO)
    assert cadastro.email == "pessoa@example.com"


def cadastro_deve_normalizar_email_para_minusculas_e_tirar_espacos_do_nome():
    cadastro = CadastroRequisicao.model_validate(
        {**CADASTRO, "email": "Pessoa@Example.COM", "nome_completo": "  Pessoa  "}
    )
    assert cadastro.email == "pessoa@example.com"
    assert cadastro.nome_completo == "Pessoa"


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("email", "nao-e-email"),
        ("email", ""),
        ("nome_completo", "   "),
        ("nome_completo", "a" * 121),
        ("telefone_pessoal", "11999999999"),
        ("senha", "1234567"),  # abaixo do mínimo de 8
        ("senha", "a" * 73),  # acima do limite de 72 bytes do bcrypt
        ("senha", "ç" * 37),  # 37 caracteres, mas 74 bytes em UTF-8
    ],
)
def cadastro_com_campo_invalido_deve_ser_rejeitado(campo, valor):
    with pytest.raises(ValidationError):
        CadastroRequisicao.model_validate({**CADASTRO, campo: valor})


@pytest.mark.parametrize("senha", ["12345678", "a" * 72])
def cadastro_com_senha_nos_limites_deve_ser_aceito(senha):
    assert CadastroRequisicao.model_validate({**CADASTRO, "senha": senha}).senha == senha


@pytest.mark.parametrize("campo", ["id", "senha_hash", "criado_em"])
def cadastro_com_campo_controlado_pelo_servidor_deve_ser_rejeitado(campo):
    with pytest.raises(ValidationError):
        CadastroRequisicao.model_validate({**CADASTRO, campo: str(uuid4())})


def login_deve_normalizar_email_para_minusculas():
    login = LoginRequisicao.model_validate({"email": "Pessoa@Example.com", "senha": "x"})
    assert login.email == "pessoa@example.com"


@pytest.mark.parametrize("corpo", [{"email": "pessoa@example.com"}, {"senha": "x"}])
def login_sem_email_ou_senha_deve_ser_rejeitado(corpo):
    with pytest.raises(ValidationError):
        LoginRequisicao.model_validate(corpo)


def resposta_usuario_nao_deve_expor_senha_nem_hash():
    assert set(UsuarioResposta.model_fields) == {
        "id",
        "nome_completo",
        "email",
        "telefone_pessoal",
        "criado_em",
    }
