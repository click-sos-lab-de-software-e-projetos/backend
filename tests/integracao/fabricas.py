from itertools import count

from sqlalchemy import Connection, Row, text

_sequencia = count(1)


def inserir_usuario(conexao: Connection, **sobrescritas) -> Row:
    n = next(_sequencia)
    dados = {
        "nome_completo": f"Pessoa Ficticia {n}",
        "email": f"pessoa{n}@example.com",
        "senha_hash": "hash-ficticio",
        "telefone_pessoal": f"+55009{n:08d}",
        **sobrescritas,
    }
    return conexao.execute(
        text(
            "INSERT INTO usuarios (nome_completo, email, senha_hash, telefone_pessoal) "
            "VALUES (:nome_completo, :email, :senha_hash, :telefone_pessoal) "
            "RETURNING id, criado_em"
        ),
        dados,
    ).one()
