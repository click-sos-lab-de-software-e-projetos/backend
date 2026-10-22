import importlib.util
from pathlib import Path
from uuid import uuid4

import jwt
import pytest

from app.core.security import extrair_usuario_id

CAMINHO = Path(__file__).parents[1] / "scripts" / "token_dev.py"
_spec = importlib.util.spec_from_file_location("token_dev", CAMINHO)
token_dev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(token_dev)

SEGREDO = "segredo-apenas-para-testes-com-32-bytes"


def emitir_token_dev_deve_ser_aceito_pela_autenticacao_da_api():
    usuario_id = uuid4()
    assert extrair_usuario_id(token_dev.emitir_token_dev(usuario_id, SEGREDO), SEGREDO) == usuario_id


def emitir_token_dev_deve_expirar_apos_a_validade_pedida():
    token = token_dev.emitir_token_dev(uuid4(), SEGREDO, validade_min=30, agora=1_000)
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["exp"] == 1_000 + 30 * 60


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:s@localhost:5432/click_sos",
        "postgresql+psycopg://u:s@127.0.0.1:5433/click_sos",
        "postgresql://u:s@host.docker.internal:5432/click_sos",
    ],
)
def banco_e_local_com_host_da_maquina_deve_aceitar(url):
    assert token_dev.banco_e_local(url) is True


def banco_e_local_com_host_remoto_deve_recusar():
    assert token_dev.banco_e_local("postgresql://u:s@ep-exemplo.neon.tech/neondb") is False


def main_com_banco_remoto_sem_permissao_deve_abortar_sem_conectar(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:s@ep-exemplo.neon.tech/neondb")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    monkeypatch.setattr(token_dev, "criar_engine", lambda url: pytest.fail("conectou"))

    assert token_dev.main([]) == 2
    assert "remoto" in capsys.readouterr().err


def main_com_usuario_id_informado_deve_emitir_token_sem_tocar_no_banco(monkeypatch, capsys):
    usuario_id = uuid4()
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert token_dev.main(["--usuario-id", str(usuario_id)]) == 0
    token = capsys.readouterr().out.strip()
    assert extrair_usuario_id(token, SEGREDO) == usuario_id
