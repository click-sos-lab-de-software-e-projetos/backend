import logging
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt
from app.constants import LIMITE_CONTATOS_ATIVOS
from app.db.sessao import criar_engine, obter_sessao
from app.main import app
from integracao.fabricas import (
    inserir_alerta,
    inserir_contato,
    inserir_tentativa,
    inserir_usuario,
)

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
COLECAO = "/api/v1/contatos"


def _token(usuario_id) -> dict[str, str]:
    payload = {"sub": str(usuario_id), "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(payload, SEGREDO_TESTE, algorithm='HS256')}"}


def _corpo(n: int) -> dict[str, str]:
    return {"nome": f"Contato Ficticio {n}", "telefone_whatsapp": f"+55007{n:08d}"}


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
    app.dependency_overrides[obter_sessao] = _sessao_de_teste
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def ana(banco_migrado):
    with banco_migrado.begin() as conexao:
        return inserir_usuario(conexao).id


@pytest.fixture
def bruno(banco_migrado):
    with banco_migrado.begin() as conexao:
        return inserir_usuario(conexao).id


def _criar(client, usuario_id, n: int):
    return client.post(COLECAO, json=_corpo(n), headers=_token(usuario_id))


def _contar_contatos(banco_migrado, usuario_id) -> int:
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text("SELECT count(*) FROM contatos_emergencia WHERE usuario_id = :id"),
            {"id": usuario_id},
        ).scalar_one()


# --- criar e ler -----------------------------------------------------------


def criar_contato_deve_responder_201_com_o_contato_ativo_e_sem_consentimento(client, ana):
    resposta = _criar(client, ana, 1)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome"] == "Contato Ficticio 1"
    assert corpo["telefone_whatsapp"] == "+5500700000001"
    assert corpo["ativo"] is True
    assert corpo["consentido_em"] is None
    assert {"id", "criado_em"} <= set(corpo)
    assert "usuario_id" not in corpo


def criar_contato_deve_gravar_para_o_usuario_do_token(client, banco_migrado, ana):
    contato_id = _criar(client, ana, 1).json()["id"]
    with banco_migrado.connect() as conexao:
        dono = conexao.execute(
            text("SELECT usuario_id FROM contatos_emergencia WHERE id = :id"),
            {"id": contato_id},
        ).scalar_one()
    assert dono == ana


def criar_contato_com_telefone_invalido_deve_responder_422(client, ana):
    corpo = {"nome": "Ana", "telefone_whatsapp": "11999999999"}
    assert client.post(COLECAO, json=corpo, headers=_token(ana)).status_code == 422


def criar_contato_com_usuario_id_no_corpo_deve_responder_422_sem_gravar(
    client, banco_migrado, ana, bruno
):
    corpo = {**_corpo(1), "usuario_id": str(bruno)}
    assert client.post(COLECAO, json=corpo, headers=_token(ana)).status_code == 422
    assert _contar_contatos(banco_migrado, ana) == 0
    assert _contar_contatos(banco_migrado, bruno) == 0


def listar_contatos_deve_trazer_os_do_usuario_em_ordem_de_criacao(client, ana):
    ids = [_criar(client, ana, n).json()["id"] for n in (1, 2)]
    resposta = client.get(COLECAO, headers=_token(ana))
    assert resposta.status_code == 200
    assert [c["id"] for c in resposta.json()] == ids


def listar_contatos_sem_nenhum_deve_responder_lista_vazia(client, ana):
    assert client.get(COLECAO, headers=_token(ana)).json() == []


def obter_contato_proprio_deve_responder_200(client, ana):
    contato = _criar(client, ana, 1).json()
    resposta = client.get(f"{COLECAO}/{contato['id']}", headers=_token(ana))
    assert resposta.status_code == 200
    assert resposta.json() == contato


def obter_contato_inexistente_deve_responder_404(client, ana):
    assert client.get(f"{COLECAO}/{uuid4()}", headers=_token(ana)).status_code == 404


def obter_contato_com_id_que_nao_e_uuid_deve_responder_422(client, ana):
    assert client.get(f"{COLECAO}/nao-e-uuid", headers=_token(ana)).status_code == 422


# --- isolamento entre pessoas usuárias -------------------------------------


def listar_contatos_nao_deve_trazer_contatos_de_outra_pessoa(client, ana, bruno):
    _criar(client, bruno, 1)
    assert client.get(COLECAO, headers=_token(ana)).json() == []


@pytest.mark.parametrize(
    ("metodo", "corpo"), [("GET", None), ("PATCH", {"nome": "Invasao"}), ("DELETE", None)]
)
def contato_de_outra_pessoa_deve_responder_404_e_continuar_intacto(
    client, banco_migrado, ana, bruno, metodo, corpo
):
    contato = _criar(client, bruno, 1).json()

    resposta = client.request(metodo, f"{COLECAO}/{contato['id']}", json=corpo, headers=_token(ana))

    assert resposta.status_code == 404
    assert client.get(f"{COLECAO}/{contato['id']}", headers=_token(bruno)).json() == contato


# --- limite de contatos ativos ---------------------------------------------


def _criar_no_limite(client, usuario_id) -> list[dict]:
    return [_criar(client, usuario_id, n).json() for n in range(1, LIMITE_CONTATOS_ATIVOS + 1)]


def criar_quarto_contato_ativo_deve_responder_409_sem_gravar(client, banco_migrado, ana):
    _criar_no_limite(client, ana)

    resposta = _criar(client, ana, 4)

    assert resposta.status_code == 409
    assert _contar_contatos(banco_migrado, ana) == LIMITE_CONTATOS_ATIVOS


def cadastros_simultaneos_nao_deve_ultrapassar_o_limite_de_ativos(client, banco_migrado, ana):
    # Sem o FOR UPDATE em usuarios, esta corrida gravava de 6 a 9 contatos.
    with ThreadPoolExecutor(max_workers=20) as executor:
        codigos = list(executor.map(lambda n: _criar(client, ana, n).status_code, range(20)))

    assert codigos.count(201) == LIMITE_CONTATOS_ATIVOS
    assert codigos.count(409) == 20 - LIMITE_CONTATOS_ATIVOS
    assert _contar_contatos(banco_migrado, ana) == LIMITE_CONTATOS_ATIVOS


def limite_de_contatos_deve_ser_contado_por_pessoa(client, ana, bruno):
    _criar_no_limite(client, bruno)
    assert _criar(client, ana, 1).status_code == 201


def contato_desativado_nao_deve_contar_no_limite(client, ana):
    primeiro, *_ = _criar_no_limite(client, ana)
    desativar = client.patch(
        f"{COLECAO}/{primeiro['id']}", json={"ativo": False}, headers=_token(ana)
    )
    assert desativar.status_code == 200
    assert desativar.json()["ativo"] is False

    assert _criar(client, ana, 4).status_code == 201


def reativar_contato_com_tres_ativos_deve_responder_409(client, banco_migrado, ana):
    with banco_migrado.begin() as conexao:
        inativo = inserir_contato(conexao, ana, ativo=False).id
    _criar_no_limite(client, ana)

    resposta = client.patch(f"{COLECAO}/{inativo}", json={"ativo": True}, headers=_token(ana))

    assert resposta.status_code == 409
    assert client.get(f"{COLECAO}/{inativo}", headers=_token(ana)).json()["ativo"] is False


def editar_contato_ja_ativo_no_limite_deve_ser_permitido(client, ana):
    primeiro, *_ = _criar_no_limite(client, ana)
    resposta = client.patch(
        f"{COLECAO}/{primeiro['id']}", json={"ativo": True, "nome": "Novo"}, headers=_token(ana)
    )
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Novo"


# --- editar e remover ------------------------------------------------------


def editar_contato_deve_mudar_so_os_campos_enviados(client, ana):
    contato = _criar(client, ana, 1).json()

    resposta = client.patch(
        f"{COLECAO}/{contato['id']}",
        json={"telefone_whatsapp": "+5500799999999"},
        headers=_token(ana),
    )

    assert resposta.status_code == 200
    assert resposta.json() == {**contato, "telefone_whatsapp": "+5500799999999"}
    assert client.get(f"{COLECAO}/{contato['id']}", headers=_token(ana)).json() == resposta.json()


def editar_contato_com_corpo_vazio_deve_responder_422(client, ana):
    contato = _criar(client, ana, 1).json()
    resposta = client.patch(f"{COLECAO}/{contato['id']}", json={}, headers=_token(ana))
    assert resposta.status_code == 422


def remover_contato_deve_responder_204_e_sumir_da_lista(client, ana):
    contato = _criar(client, ana, 1).json()

    resposta = client.delete(f"{COLECAO}/{contato['id']}", headers=_token(ana))

    assert resposta.status_code == 204
    assert resposta.content == b""
    assert client.get(f"{COLECAO}/{contato['id']}", headers=_token(ana)).status_code == 404
    assert client.get(COLECAO, headers=_token(ana)).json() == []


def remover_contato_que_ja_recebeu_alerta_deve_preservar_a_tentativa(
    client, banco_migrado, ana
):
    contato_id = _criar(client, ana, 1).json()["id"]
    with banco_migrado.begin() as conexao:
        alerta = inserir_alerta(conexao, ana)
        tentativa = inserir_tentativa(conexao, alerta.id, contato_id)

    assert client.delete(f"{COLECAO}/{contato_id}", headers=_token(ana)).status_code == 204
    with banco_migrado.connect() as conexao:
        restante = conexao.execute(
            text("SELECT contato_id FROM tentativas_envio_sos WHERE id = :id"),
            {"id": tentativa.id},
        ).one()
    assert restante.contato_id is None


# --- autenticação e privacidade --------------------------------------------


def criar_contato_com_token_de_usuario_inexistente_deve_responder_401(client):
    resposta = _criar(client, uuid4(), 1)
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def fluxo_de_contatos_nao_deve_registrar_telefone_em_logs(client, ana, caplog):
    caplog.set_level(logging.DEBUG)
    # O SQLAlchemy fixa o próprio logger em WARNING; sem isto, o SQL (e seus
    # parâmetros) nunca chegaria ao caplog e o teste passaria sem provar nada.
    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")

    contato = _criar(client, ana, 1).json()
    client.patch(
        f"{COLECAO}/{contato['id']}", json={"telefone_whatsapp": "+5500788888888"}, headers=_token(ana)
    )
    _criar(client, ana, 2)
    _criar(client, ana, 3)
    _criar(client, ana, 4)  # 409
    client.get(COLECAO, headers=_token(ana))
    client.delete(f"{COLECAO}/{contato['id']}", headers=_token(ana))

    assert "INSERT INTO contatos_emergencia" in caplog.text, "o SQL precisa ser capturado"
    for telefone in ("+5500700000001", "+5500788888888", "+5500700000004", "5500700000004"):
        assert telefone not in caplog.text
