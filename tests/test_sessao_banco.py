import pytest
from sqlalchemy.orm import Session

from app.constants import NOME_VARIAVEL_URL_BANCO
from app.db import sessao as modulo_sessao
from app.db.sessao import criar_engine, obter_engine, obter_sessao

URL_FICTICIA = "postgresql://app:senha@host-ficticio:5432/click_sos"


@pytest.fixture(autouse=True)
def limpar_cache_do_engine():
    obter_engine.cache_clear()
    yield
    obter_engine.cache_clear()


def criar_engine_deve_esconder_parametros_de_logs_e_erros():
    assert criar_engine(URL_FICTICIA).hide_parameters is True


def criar_engine_deve_usar_driver_psycopg_mesmo_sem_prefixo():
    assert criar_engine(URL_FICTICIA).url.drivername == "postgresql+psycopg"


def obter_engine_deve_ler_database_url_e_reaproveitar_a_instancia(monkeypatch):
    monkeypatch.setenv(NOME_VARIAVEL_URL_BANCO, URL_FICTICIA)
    engine = obter_engine()
    assert engine.url.host == "host-ficticio"
    assert obter_engine() is engine


def obter_engine_sem_database_url_deve_lancar_erro(monkeypatch):
    monkeypatch.delenv(NOME_VARIAVEL_URL_BANCO, raising=False)
    with pytest.raises(RuntimeError):
        obter_engine()


def obter_sessao_deve_entregar_sessao_e_fechar_ao_final(monkeypatch):
    monkeypatch.setenv(NOME_VARIAVEL_URL_BANCO, URL_FICTICIA)
    fechadas = []
    monkeypatch.setattr(modulo_sessao.Session, "close", lambda self: fechadas.append(self))

    gerador = obter_sessao()
    sessao = next(gerador)
    assert isinstance(sessao, Session)
    gerador.close()

    assert fechadas == [sessao]
