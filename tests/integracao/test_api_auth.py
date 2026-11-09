import logging

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt, obter_validade_jwt_min
from app.db.sessao import criar_engine, obter_sessao
from app.main import app
from integracao.fabricas import inserir_usuario

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
CADASTRO = "/api/v1/auth/cadastro"
LOGIN = "/api/v1/auth/login"
SENHA = "senha-ficticia-123"
CORPO = {
    "nome_completo": "Pessoa Ficticia",
    "email": "pessoa.auth@example.com",
    "senha": SENHA,
    "telefone_pessoal": "+5500900000000",
}


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
    app.dependency_overrides[obter_validade_jwt_min] = lambda: 30
    app.dependency_overrides[obter_sessao] = _sessao_de_teste
    yield TestClient(app)
    app.dependency_overrides.clear()


def _login(client, email=CORPO["email"], senha=SENHA):
    return client.post(LOGIN, json={"email": email, "senha": senha})


# --- cadastro ----------------------------------------------------------------


def cadastro_valido_deve_responder_201_sem_senha_nem_hash(client):
    resposta = client.post(CADASTRO, json=CORPO)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert set(corpo) == {"id", "nome_completo", "email", "telefone_pessoal", "criado_em"}
    assert corpo["email"] == CORPO["email"]


def cadastro_deve_guardar_a_senha_como_hash_bcrypt(client, banco_migrado):
    usuario_id = client.post(CADASTRO, json=CORPO).json()["id"]

    with banco_migrado.connect() as conexao:
        senha_hash = conexao.execute(
            text("SELECT senha_hash FROM usuarios WHERE id = :id"), {"id": usuario_id}
        ).scalar_one()
    assert senha_hash.startswith("$2b$")
    assert SENHA not in senha_hash


def cadastro_com_email_ja_usado_deve_responder_409_mesmo_com_outra_caixa(client):
    assert client.post(CADASTRO, json=CORPO).status_code == 201

    repetido = {**CORPO, "email": CORPO["email"].upper()}
    resposta = client.post(CADASTRO, json=repetido)

    assert resposta.status_code == 409


def cadastro_com_dados_invalidos_deve_responder_422_sem_gravar(client, banco_migrado):
    resposta = client.post(CADASTRO, json={**CORPO, "senha": "curta"})

    assert resposta.status_code == 422
    with banco_migrado.connect() as conexao:
        assert conexao.execute(text("SELECT count(*) FROM usuarios")).scalar_one() == 0


# --- login -------------------------------------------------------------------


def login_com_credenciais_certas_deve_emitir_jwt_aceito_nas_rotas_privadas(client):
    usuario_id = client.post(CADASTRO, json=CORPO).json()["id"]

    resposta = _login(client, email=CORPO["email"].upper())

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["expires_in"] == 30 * 60
    payload = jwt.decode(corpo["access_token"], SEGREDO_TESTE, algorithms=["HS256"])
    assert payload["sub"] == usuario_id
    privada = client.get(
        "/api/v1/contatos", headers={"Authorization": f"Bearer {corpo['access_token']}"}
    )
    assert privada.status_code == 200


def login_com_senha_errada_ou_email_inexistente_deve_responder_401_identico(client):
    client.post(CADASTRO, json=CORPO)

    senha_errada = _login(client, senha="outra-senha-123")
    email_inexistente = _login(client, email="ninguem@example.com")

    assert senha_errada.status_code == email_inexistente.status_code == 401
    assert senha_errada.json() == email_inexistente.json()
    assert senha_errada.headers["www-authenticate"] == "Bearer"


def login_de_usuario_sem_hash_bcrypt_deve_responder_401(client, banco_migrado):
    with banco_migrado.begin() as conexao:
        inserir_usuario(conexao, email="legado@example.com", senha_hash="hash-ficticio")

    assert _login(client, email="legado@example.com", senha="hash-ficticio").status_code == 401


def fluxo_de_auth_nao_deve_registrar_senha_hash_nem_token_em_logs(
    client, banco_migrado, caplog
):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")

    client.post(CADASTRO, json=CORPO)
    token = _login(client).json()["access_token"]
    _login(client, senha="outra-senha-123")

    with banco_migrado.connect() as conexao:
        senha_hash = conexao.execute(text("SELECT senha_hash FROM usuarios")).scalar_one()
    assert "INSERT INTO usuarios" in caplog.text, "o SQL precisa ser capturado"
    for segredo in (SENHA, "outra-senha-123", senha_hash, token):
        assert segredo not in caplog.text
