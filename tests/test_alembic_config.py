from configparser import RawConfigParser
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.constants import NOME_VARIAVEL_URL_BANCO
from app.db.config import obter_url_banco

RAIZ = Path(__file__).resolve().parents[1]
ALEMBIC_INI = RAIZ / "alembic.ini"


def obter_url_banco_deve_ler_database_url_do_ambiente(monkeypatch):
    monkeypatch.setenv(NOME_VARIAVEL_URL_BANCO, "postgresql+psycopg://u:s@host:5432/banco")
    assert obter_url_banco() == "postgresql+psycopg://u:s@host:5432/banco"


def obter_url_banco_sem_variavel_deve_lancar_erro_claro(monkeypatch):
    monkeypatch.delenv(NOME_VARIAVEL_URL_BANCO, raising=False)
    with pytest.raises(RuntimeError, match=NOME_VARIAVEL_URL_BANCO):
        obter_url_banco()


@pytest.mark.parametrize("esquema", ["postgresql", "postgres"])
def obter_url_banco_deve_usar_driver_psycopg(monkeypatch, esquema):
    monkeypatch.setenv(NOME_VARIAVEL_URL_BANCO, f"{esquema}://u:s@host:5432/banco")
    assert obter_url_banco() == "postgresql+psycopg://u:s@host:5432/banco"


def alembic_ini_nao_deve_conter_url_de_banco():
    ini = RawConfigParser()
    ini.read(ALEMBIC_INI, encoding="utf-8")
    assert not ini.get("alembic", "sqlalchemy.url", fallback="").strip()


def historico_de_migracoes_deve_ter_no_maximo_uma_head():
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    assert len(script.get_heads()) <= 1


def alembic_offline_deve_usar_database_url_do_ambiente(monkeypatch, capsys):
    monkeypatch.setenv(NOME_VARIAVEL_URL_BANCO, "postgresql://u:s@host:5432/banco")
    command.upgrade(Config(str(ALEMBIC_INI)), "head", sql=True)
    assert "BEGIN;" in capsys.readouterr().out
