import importlib.util
from pathlib import Path

from sqlalchemy import text

from app.core.security import extrair_usuario_id

CAMINHO = Path(__file__).parents[2] / "scripts" / "token_dev.py"
_spec = importlib.util.spec_from_file_location("token_dev", CAMINHO)
token_dev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(token_dev)

SEGREDO = "segredo-apenas-para-testes-com-32-bytes"


def main_sem_usuario_id_deve_criar_usuario_ficticio_e_emitir_token_dele(
    banco_migrado, url_teste, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", url_teste)
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)

    assert token_dev.main([]) == 0

    usuario_id = extrair_usuario_id(capsys.readouterr().out.strip(), SEGREDO)
    with banco_migrado.connect() as conexao:
        email = conexao.execute(
            text("SELECT email FROM usuarios WHERE id = :id"), {"id": usuario_id}
        ).scalar_one()
    assert email.endswith("@example.com")
