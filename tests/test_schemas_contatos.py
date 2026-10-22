from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.contatos import (
    AtualizarContatoRequisicao,
    ContatoResposta,
    CriarContatoRequisicao,
)

CORPO_VALIDO = {"nome": "Contato Ficticio", "telefone_whatsapp": "+5500900000000"}


def requisicao_contato_valida_deve_ser_aceita():
    contato = CriarContatoRequisicao.model_validate(CORPO_VALIDO)
    assert contato.nome == "Contato Ficticio"
    assert contato.telefone_whatsapp == "+5500900000000"


def requisicao_contato_deve_remover_espacos_das_pontas_do_nome():
    contato = CriarContatoRequisicao.model_validate({**CORPO_VALIDO, "nome": "  Ana  "})
    assert contato.nome == "Ana"


@pytest.mark.parametrize(
    "telefone",
    [
        "5500900000000",  # sem o +
        "+0500900000000",  # código de país começando em 0
        "+5500 90000000",  # espaço no meio
        "+55(00)900000000",  # pontuação
        "+1234567",  # curto demais: 7 dígitos
        "+1234567890123456",  # longo demais: 16 dígitos
        "",
    ],
)
def requisicao_contato_com_telefone_fora_do_e164_deve_ser_rejeitada(telefone):
    with pytest.raises(ValidationError):
        CriarContatoRequisicao.model_validate({**CORPO_VALIDO, "telefone_whatsapp": telefone})


@pytest.mark.parametrize("telefone", ["+12345678", "+123456789012345"])
def requisicao_contato_com_telefone_nos_limites_do_e164_deve_ser_aceita(telefone):
    contato = CriarContatoRequisicao.model_validate({**CORPO_VALIDO, "telefone_whatsapp": telefone})
    assert contato.telefone_whatsapp == telefone


@pytest.mark.parametrize("nome", ["", "   ", "a" * 101])
def requisicao_contato_com_nome_vazio_ou_longo_deve_ser_rejeitada(nome):
    with pytest.raises(ValidationError):
        CriarContatoRequisicao.model_validate({**CORPO_VALIDO, "nome": nome})


@pytest.mark.parametrize("campo", ["usuario_id", "id", "consentido_em"])
def requisicao_contato_com_campo_controlado_pelo_servidor_deve_ser_rejeitada(campo):
    with pytest.raises(ValidationError):
        CriarContatoRequisicao.model_validate({**CORPO_VALIDO, campo: str(uuid4())})


def atualizacao_contato_parcial_deve_aceitar_um_campo_so():
    atualizacao = AtualizarContatoRequisicao.model_validate({"ativo": False})
    assert atualizacao.model_dump(exclude_unset=True) == {"ativo": False}


def atualizacao_contato_vazia_deve_ser_rejeitada():
    with pytest.raises(ValidationError):
        AtualizarContatoRequisicao.model_validate({})


@pytest.mark.parametrize("campo", ["nome", "telefone_whatsapp", "ativo"])
def atualizacao_contato_com_null_explicito_deve_ser_rejeitada(campo):
    with pytest.raises(ValidationError):
        AtualizarContatoRequisicao.model_validate({campo: None})


def atualizacao_contato_com_telefone_invalido_deve_ser_rejeitada():
    with pytest.raises(ValidationError):
        AtualizarContatoRequisicao.model_validate({"telefone_whatsapp": "11999999999"})


def atualizacao_contato_com_usuario_id_deve_ser_rejeitada():
    with pytest.raises(ValidationError):
        AtualizarContatoRequisicao.model_validate({"usuario_id": str(uuid4())})


def resposta_contato_nao_deve_expor_usuario_id():
    assert set(ContatoResposta.model_fields) == {
        "id",
        "nome",
        "telefone_whatsapp",
        "ativo",
        "consentido_em",
        "criado_em",
    }
