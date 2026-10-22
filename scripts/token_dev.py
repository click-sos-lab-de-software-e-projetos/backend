"""Emite um JWT de desenvolvimento para testar rotas privadas no Swagger.

Paliativo até o AUTH-01 (cadastro e login) existir. Sem argumentos, cria uma
pessoa usuária fictícia em DATABASE_URL e imprime um token dela; com
--usuario-id, só emite o token, sem tocar no banco.

    python scripts/token_dev.py
    python scripts/token_dev.py --usuario-id <uuid> --validade-min 120

Lê DATABASE_URL e JWT_SECRET_KEY do ambiente. Por segurança, recusa bancos
fora desta máquina (como o Neon da equipe) a menos que se passe
--permitir-banco-remoto. Nunca cole o token em commit, issue ou log.
"""

import argparse
import sys
import time
from uuid import UUID, uuid4

import jwt
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.api.deps import obter_segredo_jwt
from app.db.config import obter_url_banco
from app.db.sessao import criar_engine

HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def emitir_token_dev(
    usuario_id: UUID, segredo: str, validade_min: int = 60, agora: int | None = None
) -> str:
    emitido_em = int(time.time()) if agora is None else agora
    payload = {"sub": str(usuario_id), "exp": emitido_em + validade_min * 60}
    return jwt.encode(payload, segredo, algorithm="HS256")


def banco_e_local(url: str) -> bool:
    return make_url(url).host in HOSTS_LOCAIS


def criar_usuario_ficticio(url: str) -> UUID:
    engine = criar_engine(url)
    try:
        with engine.begin() as conexao:
            return conexao.execute(
                text(
                    "INSERT INTO usuarios (nome_completo, email, senha_hash, telefone_pessoal) "
                    "VALUES (:nome, :email, :senha_hash, :telefone) RETURNING id"
                ),
                {
                    "nome": "Pessoa Ficticia Dev",
                    "email": f"dev-{uuid4().hex[:12]}@example.com",
                    "senha_hash": "sem-login-ate-o-auth-01",
                    "telefone": "+5500900000000",
                },
            ).scalar_one()
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--usuario-id", type=UUID, help="reaproveita uma pessoa já criada")
    parser.add_argument("--validade-min", type=int, default=60, help="padrão: 60")
    parser.add_argument("--permitir-banco-remoto", action="store_true")
    args = parser.parse_args(argv)

    segredo = obter_segredo_jwt()
    usuario_id = args.usuario_id
    if usuario_id is None:
        url = obter_url_banco()
        if not banco_e_local(url) and not args.permitir_banco_remoto:
            print(
                "DATABASE_URL aponta para um banco remoto; o script criaria uma pessoa "
                "fictícia nele. Use um PostGIS local ou passe --permitir-banco-remoto.",
                file=sys.stderr,
            )
            return 2
        usuario_id = criar_usuario_ficticio(url)
        print(f"Pessoa fictícia criada: {usuario_id}", file=sys.stderr)

    print(emitir_token_dev(usuario_id, segredo, args.validade_min))
    return 0


if __name__ == "__main__":
    sys.exit(main())
