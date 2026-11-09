"""Consentimento do contato por link de uso único (Tarefa 1, Regra 03)."""

import hashlib
import logging
import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt, obter_url_consentimento
from app.constants import VALIDADE_LINK_CONSENTIMENTO_DIAS
from app.db.sessao import criar_engine, obter_sessao
from app.main import app
from integracao.fabricas import inserir_contato, inserir_usuario

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
URL_PAGINA = "https://consentimento.example.com/"
PEDIDO = "/api/v1/consentimento/pedido"
RESPOSTA = "/api/v1/consentimento/resposta"
MSG_LINK_INVALIDO = "Link inválido ou expirado."


def _auth(usuario_id) -> dict[str, str]:
    payload = {"sub": str(usuario_id), "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(payload, SEGREDO_TESTE, algorithm='HS256')}"}


def _link(contato_id) -> str:
    return f"/api/v1/contatos/{contato_id}/consentimento"


@pytest.fixture
def engine_app(banco_migrado, url_teste):
    engine = criar_engine(url_teste)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine_app):
    def _sessao_de_teste():
        with Session(engine_app, expire_on_commit=False) as sessao:
            yield sessao

    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_url_consentimento] = lambda: URL_PAGINA
    app.dependency_overrides[obter_sessao] = _sessao_de_teste
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def ana(banco_migrado):
    with banco_migrado.begin() as conexao:
        return inserir_usuario(conexao, nome_completo="Ana Ficticia").id


@pytest.fixture
def contato(banco_migrado, ana):
    with banco_migrado.begin() as conexao:
        return inserir_contato(conexao, ana, nome="Bruno Ficticio").id


def _gerar_token(client, ana, contato) -> str:
    resposta = client.post(_link(contato), headers=_auth(ana))
    assert resposta.status_code == 201
    return resposta.json()["url"].split("#token=", 1)[1]


def _linha(banco_migrado, contato_id):
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text(
                "SELECT consentido_em, recusado_em, token_consentimento_hash, "
                "token_consentimento_expira_em FROM contatos_emergencia WHERE id = :id"
            ),
            {"id": contato_id},
        ).one()


# --- gerar o link ------------------------------------------------------------


def gerar_link_deve_devolver_url_da_pagina_com_token_no_fragmento(client, ana, contato):
    resposta = client.post(_link(contato), headers=_auth(ana))

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["url"].startswith(f"{URL_PAGINA}#token=")
    expira = datetime.fromisoformat(corpo["expira_em"])
    esperado = datetime.now(UTC) + timedelta(days=VALIDADE_LINK_CONSENTIMENTO_DIAS)
    assert abs(expira - esperado) < timedelta(minutes=1)


def gerar_link_deve_guardar_so_o_hash_do_token(client, banco_migrado, ana, contato):
    token = _gerar_token(client, ana, contato)

    linha = _linha(banco_migrado, contato)
    assert linha.token_consentimento_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in linha.token_consentimento_hash


def gerar_link_de_novo_deve_invalidar_o_anterior(client, ana, contato):
    antigo = _gerar_token(client, ana, contato)
    novo = _gerar_token(client, ana, contato)

    assert client.post(PEDIDO, json={"token": antigo}).status_code == 404
    assert client.post(PEDIDO, json={"token": novo}).status_code == 200


def gerar_link_de_contato_de_outra_pessoa_deve_responder_404(client, banco_migrado, contato):
    with banco_migrado.begin() as conexao:
        bruno = inserir_usuario(conexao).id

    resposta = client.post(_link(contato), headers=_auth(bruno))

    assert resposta.status_code == 404
    assert _linha(banco_migrado, contato).token_consentimento_hash is None


def gerar_link_para_contato_que_ja_consentiu_deve_responder_409(client, ana, contato):
    token = _gerar_token(client, ana, contato)
    client.post(RESPOSTA, json={"token": token, "aceito": True})

    assert client.post(_link(contato), headers=_auth(ana)).status_code == 409


def gerar_link_sem_token_jwt_deve_responder_401(client, contato):
    assert client.post(_link(contato)).status_code == 401


# --- página pública: ver o pedido ----------------------------------------------


def pedido_deve_mostrar_quem_pediu_sem_telefones(client, ana, contato):
    token = _gerar_token(client, ana, contato)

    resposta = client.post(PEDIDO, json={"token": token})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nome_contato"] == "Bruno Ficticio"
    assert corpo["nome_solicitante"] == "Ana Ficticia"
    assert set(corpo) == {"nome_contato", "nome_solicitante", "expira_em"}


def pedido_com_token_desconhecido_deve_responder_404(client):
    resposta = client.post(PEDIDO, json={"token": "x" * 43})

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == MSG_LINK_INVALIDO


def pedido_com_token_expirado_deve_responder_404(client, banco_migrado, ana, contato):
    token = _gerar_token(client, ana, contato)
    with banco_migrado.begin() as conexao:
        conexao.execute(
            text(
                "UPDATE contatos_emergencia "
                "SET token_consentimento_expira_em = now() - interval '1 second' WHERE id = :id"
            ),
            {"id": contato},
        )

    resposta = client.post(PEDIDO, json={"token": token})

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == MSG_LINK_INVALIDO


@pytest.mark.parametrize("token", ["", "curto", "a" * 200, "com espaço" * 5])
def pedido_com_token_mal_formado_deve_responder_422(client, token):
    assert client.post(PEDIDO, json={"token": token}).status_code == 422


# --- página pública: responder -------------------------------------------------


def aceitar_deve_gravar_consentimento_e_queimar_o_token(client, banco_migrado, ana, contato):
    token = _gerar_token(client, ana, contato)

    resposta = client.post(RESPOSTA, json={"token": token, "aceito": True})

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ACEITO"}
    linha = _linha(banco_migrado, contato)
    assert linha.consentido_em is not None
    assert linha.recusado_em is None
    assert linha.token_consentimento_hash is None
    assert linha.token_consentimento_expira_em is None


def recusar_deve_gravar_recusa_sem_consentimento(client, banco_migrado, ana, contato):
    token = _gerar_token(client, ana, contato)

    resposta = client.post(RESPOSTA, json={"token": token, "aceito": False})

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "RECUSADO"}
    linha = _linha(banco_migrado, contato)
    assert linha.consentido_em is None
    assert linha.recusado_em is not None
    assert linha.token_consentimento_hash is None


def aceitar_depois_de_ter_recusado_deve_limpar_a_recusa(client, banco_migrado, ana, contato):
    client.post(RESPOSTA, json={"token": _gerar_token(client, ana, contato), "aceito": False})

    client.post(RESPOSTA, json={"token": _gerar_token(client, ana, contato), "aceito": True})

    linha = _linha(banco_migrado, contato)
    assert linha.consentido_em is not None
    assert linha.recusado_em is None


def responder_duas_vezes_com_o_mesmo_token_deve_responder_404(client, ana, contato):
    token = _gerar_token(client, ana, contato)
    client.post(RESPOSTA, json={"token": token, "aceito": True})

    resposta = client.post(RESPOSTA, json={"token": token, "aceito": False})

    assert resposta.status_code == 404


def responder_sem_o_campo_aceito_deve_responder_422(client, ana, contato):
    token = _gerar_token(client, ana, contato)
    assert client.post(RESPOSTA, json={"token": token}).status_code == 422


def contato_que_aceitou_deve_aparecer_consentido_na_lista(client, ana, contato):
    client.post(RESPOSTA, json={"token": _gerar_token(client, ana, contato), "aceito": True})

    [item] = client.get("/api/v1/contatos", headers=_auth(ana)).json()

    assert item["consentido_em"] is not None
    assert item["recusado_em"] is None
    assert "token_consentimento_hash" not in item


def token_nao_deve_aparecer_nos_logs(client, caplog, ana, contato):
    with caplog.at_level(logging.DEBUG):
        token = _gerar_token(client, ana, contato)
        client.post(PEDIDO, json={"token": token})
        client.post(RESPOSTA, json={"token": token, "aceito": True})

    assert token not in caplog.text


# --- trocar o telefone ---------------------------------------------------------


def trocar_telefone_deve_apagar_consentimento_recusa_e_link(client, banco_migrado, ana, contato):
    client.post(RESPOSTA, json={"token": _gerar_token(client, ana, contato), "aceito": True})

    resposta = client.patch(
        f"/api/v1/contatos/{contato}",
        json={"telefone_whatsapp": "+5500911112222"},
        headers=_auth(ana),
    )

    assert resposta.status_code == 200
    assert resposta.json()["consentido_em"] is None
    linha = _linha(banco_migrado, contato)
    assert (linha.consentido_em, linha.recusado_em, linha.token_consentimento_hash) == (
        None,
        None,
        None,
    )


def trocar_telefone_deve_invalidar_link_pendente(client, ana, contato):
    token = _gerar_token(client, ana, contato)

    client.patch(
        f"/api/v1/contatos/{contato}",
        json={"telefone_whatsapp": "+5500911112222"},
        headers=_auth(ana),
    )

    assert client.post(PEDIDO, json={"token": token}).status_code == 404


def editar_so_o_nome_deve_manter_o_consentimento(client, ana, contato):
    client.post(RESPOSTA, json={"token": _gerar_token(client, ana, contato), "aceito": True})

    resposta = client.patch(
        f"/api/v1/contatos/{contato}", json={"nome": "Bruno"}, headers=_auth(ana)
    )

    assert resposta.json()["consentido_em"] is not None


def repetir_o_mesmo_telefone_deve_manter_o_consentimento(client, banco_migrado, ana, contato):
    client.post(RESPOSTA, json={"token": _gerar_token(client, ana, contato), "aceito": True})
    with banco_migrado.connect() as conexao:
        telefone = conexao.execute(
            text("SELECT telefone_whatsapp FROM contatos_emergencia WHERE id = :id"),
            {"id": contato},
        ).scalar_one()

    resposta = client.patch(
        f"/api/v1/contatos/{contato}", json={"telefone_whatsapp": telefone}, headers=_auth(ana)
    )

    assert resposta.json()["consentido_em"] is not None
