import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "run.sh"
CHAVE_EVOLUTION = "chave-evolution-que-nao-pode-aparecer"
SENHA_BANCO = "senha-que-nao-pode-aparecer"
URL_PROD = f'"postgresql://app:{SENHA_BANCO}@ep-prod.neon.tech/neondb?sslmode=require&x=1"'

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="exige bash")


def _rodar(tmp_path, *args, **variaveis):
    conteudo = {
        "JWT_SECRET_KEY": "segredo",
        "DATABASE_URL_LOCAL": f"postgresql+psycopg://dev:{SENHA_BANCO}@localhost:5432/click_sos",
        "EVOLUTION_API_KEY_LOCAL": CHAVE_EVOLUTION,
        "API_BASE_URL_LOCAL": "http://localhost:8000/api/v1",
        "DATABASE_URL_PROD": URL_PROD,
        **variaveis,
    }
    arquivo = tmp_path / ".env"
    arquivo.write_text("".join(f"{k}={v}\n" for k, v in conteudo.items()))
    ambiente = {"PATH": os.environ["PATH"], "CLICK_SOS_ENV_FILE": str(arquivo)}
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=ambiente, check=False
    )


def verificar_local_deve_exportar_as_variaveis_do_perfil_sem_mostrar_segredos(tmp_path):
    resultado = _rodar(tmp_path, "verificar", "local")

    assert resultado.returncode == 0, resultado.stderr
    assert "DATABASE_URL: localhost:5432" in resultado.stdout
    assert "EVOLUTION_API_KEY: definida" in resultado.stdout
    assert "API_BASE_URL: localhost:8000" in resultado.stdout
    assert CHAVE_EVOLUTION not in resultado.stdout
    assert SENHA_BANCO not in resultado.stdout


def verificar_dev_sem_database_url_dev_deve_recusar(tmp_path):
    resultado = _rodar(tmp_path, "verificar", "dev")

    assert resultado.returncode != 0
    assert "DATABASE_URL_DEV" in resultado.stderr


@pytest.mark.parametrize(
    "url_dev",
    [URL_PROD, '"postgresql://outra:senha@ep-prod.neon.tech/outro_banco?sslmode=require"'],
)
def verificar_dev_apontando_para_o_banco_de_producao_deve_recusar(tmp_path, url_dev):
    resultado = _rodar(tmp_path, "verificar", "dev", DATABASE_URL_DEV=url_dev)

    assert resultado.returncode != 0
    assert "produção" in resultado.stderr


def verificar_dev_com_branch_proprio_deve_aceitar(tmp_path):
    url_dev = '"postgresql://app:senha@ep-dev.neon.tech/neondb?sslmode=require&x=1"'

    resultado = _rodar(tmp_path, "verificar", "dev", DATABASE_URL_DEV=url_dev)

    assert resultado.returncode == 0, resultado.stderr
    assert "DATABASE_URL: ep-dev.neon.tech" in resultado.stdout
