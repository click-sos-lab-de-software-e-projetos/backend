import logging

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt, obter_validade_jwt_min
from app.db.sessao import criar_engine, obter_sessao
from app.main import app
from integracao.fabricas import (
    inserir_alerta,
    inserir_contato,
    inserir_regiao,
    inserir_tentativa,
    inserir_usuario,
)

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


# --- me ------------------------------------------------------------------------


def me_com_token_do_login_deve_devolver_o_perfil_sem_senha(client):
    usuario_id = client.post(CADASTRO, json=CORPO).json()["id"]
    token = _login(client).json()["access_token"]

    resposta = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200
    assert resposta.json()["id"] == usuario_id
    assert set(resposta.json()) == {"id", "nome_completo", "email", "telefone_pessoal", "criado_em"}


def me_de_usuario_removido_deve_responder_401(client, banco_migrado):
    usuario_id = client.post(CADASTRO, json=CORPO).json()["id"]
    token = _login(client).json()["access_token"]
    with banco_migrado.begin() as conexao:
        conexao.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario_id})

    resposta = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 401


# --- edição do perfil e troca de senha -------------------------------------------


def _cadastrar_e_entrar(client) -> dict[str, str]:
    client.post(CADASTRO, json=CORPO)
    return {"Authorization": f"Bearer {_login(client).json()['access_token']}"}


def editar_perfil_deve_mudar_so_os_campos_enviados(client):
    cabecalhos = _cadastrar_e_entrar(client)

    resposta = client.patch("/api/v1/auth/me", json={"telefone_pessoal": "+5500911111111"}, headers=cabecalhos)

    assert resposta.status_code == 200
    assert resposta.json()["telefone_pessoal"] == "+5500911111111"
    perfil = client.get("/api/v1/auth/me", headers=cabecalhos).json()
    assert (perfil["nome_completo"], perfil["email"], perfil["telefone_pessoal"]) == (
        CORPO["nome_completo"],
        CORPO["email"],
        "+5500911111111",
    )

    client.patch("/api/v1/auth/me", json={"nome_completo": " Nome Novo "}, headers=cabecalhos)
    perfil = client.get("/api/v1/auth/me", headers=cabecalhos).json()
    assert (perfil["nome_completo"], perfil["telefone_pessoal"]) == ("Nome Novo", "+5500911111111")


def trocar_senha_com_a_senha_atual_deve_valer_no_proximo_login(client):
    cabecalhos = _cadastrar_e_entrar(client)

    resposta = client.post(
        "/api/v1/auth/me/senha", json={"senha_atual": SENHA, "senha_nova": "senha-nova-456"}, headers=cabecalhos
    )

    assert resposta.status_code == 204
    assert resposta.content == b""
    assert _login(client, senha="senha-nova-456").status_code == 200
    assert _login(client).status_code == 401


def trocar_senha_com_a_senha_atual_errada_deve_responder_400_sem_mudar(client):
    cabecalhos = _cadastrar_e_entrar(client)

    resposta = client.post(
        "/api/v1/auth/me/senha", json={"senha_atual": "errada", "senha_nova": "senha-nova-456"}, headers=cabecalhos
    )

    assert resposta.status_code == 400
    assert _login(client).status_code == 200
    assert _login(client, senha="senha-nova-456").status_code == 401


@pytest.mark.parametrize(
    ("metodo", "caminho", "corpo"),
    [
        ("patch", "/api/v1/auth/me", {"nome_completo": "Nome Novo"}),
        ("post", "/api/v1/auth/me/senha", {"senha_atual": SENHA, "senha_nova": "senha-nova-456"}),
        ("delete", "/api/v1/auth/me", {"senha": SENHA}),
    ],
)
def alterar_perfil_ou_senha_de_usuario_removido_deve_responder_401(client, banco_migrado, metodo, caminho, corpo):
    usuario_id = client.post(CADASTRO, json=CORPO).json()["id"]
    cabecalhos = {"Authorization": f"Bearer {_login(client).json()['access_token']}"}
    with banco_migrado.begin() as conexao:
        conexao.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario_id})

    resposta = client.request(metodo, caminho, json=corpo, headers=cabecalhos)

    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


# --- exclusão de conta ---------------------------------------------------------


def _dados_da_pessoa(conexao, usuario_id, status_envio="ENVIADO") -> dict:
    contato = inserir_contato(conexao, usuario_id).id
    alerta = inserir_alerta(conexao, usuario_id, mensagem="socorro", status_envio=status_envio).id
    inserir_tentativa(conexao, alerta, contato, status="SUCESSO")
    regiao = inserir_regiao(conexao, 0.0, 0.0, 0.01, 0.01).id
    conexao.execute(
        text("INSERT INTO feedbacks_comunidade (usuario_id, regiao_id, categoria) VALUES (:u, :r, 'ASSALTO')"),
        {"u": usuario_id, "r": regiao},
    )
    return {"contato": contato, "alerta": alerta}


def _retrato(banco_migrado) -> dict:
    with banco_migrado.connect() as conexao:
        return {
            "usuarios": conexao.execute(text("SELECT id FROM usuarios ORDER BY id")).all(),
            "contatos": conexao.execute(text("SELECT id FROM contatos_emergencia ORDER BY id")).all(),
            "feedbacks": conexao.execute(text("SELECT usuario_id FROM feedbacks_comunidade ORDER BY id")).all(),
            "alertas": conexao.execute(
                text(
                    "SELECT id, usuario_id, localizacao IS NULL AS sem_local, mensagem, "
                    "anonimizado_em IS NOT NULL AS anonimizado, status_envio FROM alertas_sos ORDER BY id"
                )
            ).all(),
            "tentativas": conexao.execute(
                text("SELECT alerta_id, contato_id FROM tentativas_envio_sos ORDER BY id")
            ).all(),
        }


@pytest.fixture
def pessoa_com_dados(client, banco_migrado):
    """A pessoa do cadastro com contato, alerta, tentativa e feedback, e outra pessoa com o mesmo."""
    usuario_id = client.post(CADASTRO, json=CORPO).json()["id"]
    cabecalhos = {"Authorization": f"Bearer {_login(client).json()['access_token']}"}
    with banco_migrado.begin() as conexao:
        dados = _dados_da_pessoa(conexao, usuario_id)
        outra = inserir_usuario(conexao).id
        _dados_da_pessoa(conexao, outra)
    return usuario_id, cabecalhos, dados, outra


def excluir_conta_deve_apagar_a_pessoa_e_anonimizar_os_alertas(client, banco_migrado, pessoa_com_dados):
    usuario_id, cabecalhos, dados, outra = pessoa_com_dados

    resposta = client.request("DELETE", "/api/v1/auth/me", json={"senha": SENHA}, headers=cabecalhos)

    assert resposta.status_code == 204
    assert resposta.content == b""
    retrato = _retrato(banco_migrado)
    assert [linha.id for linha in retrato["usuarios"]] == [outra]
    assert len(retrato["contatos"]) == 1
    assert [linha.usuario_id for linha in retrato["feedbacks"]] == [outra]
    alerta = next(linha for linha in retrato["alertas"] if linha.id == dados["alerta"])
    assert (alerta.usuario_id, alerta.sem_local, alerta.mensagem, alerta.anonimizado, alerta.status_envio) == (
        None,
        True,
        None,
        True,
        "ENVIADO",
    )
    tentativa = next(linha for linha in retrato["tentativas"] if linha.alerta_id == dados["alerta"])
    assert tentativa.contato_id is None
    alerta_da_outra = next(linha for linha in retrato["alertas"] if linha.id != dados["alerta"])
    assert (alerta_da_outra.usuario_id, alerta_da_outra.sem_local, alerta_da_outra.anonimizado) == (outra, False, False)
    assert client.get("/api/v1/auth/me", headers=cabecalhos).status_code == 401
    assert _login(client).status_code == 401


def excluir_conta_com_senha_errada_deve_responder_400_sem_apagar(client, banco_migrado, pessoa_com_dados):
    _, cabecalhos, _, _ = pessoa_com_dados
    antes = _retrato(banco_migrado)

    resposta = client.request("DELETE", "/api/v1/auth/me", json={"senha": "errada"}, headers=cabecalhos)

    assert resposta.status_code == 400
    assert _retrato(banco_migrado) == antes


def excluir_conta_com_alerta_pendente_deve_responder_409_sem_apagar(client, banco_migrado, pessoa_com_dados):
    usuario_id, cabecalhos, _, _ = pessoa_com_dados
    with banco_migrado.begin() as conexao:
        inserir_alerta(conexao, usuario_id, status_envio="PENDENTE")
    antes = _retrato(banco_migrado)

    resposta = client.request("DELETE", "/api/v1/auth/me", json={"senha": SENHA}, headers=cabecalhos)

    assert resposta.status_code == 409
    assert _retrato(banco_migrado) == antes
