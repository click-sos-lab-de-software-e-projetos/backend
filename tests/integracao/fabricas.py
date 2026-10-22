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


def inserir_contato(conexao: Connection, usuario_id, **sobrescritas) -> Row:
    n = next(_sequencia)
    dados = {
        "usuario_id": usuario_id,
        "nome": f"Contato Ficticio {n}",
        "telefone_whatsapp": f"+55008{n:08d}",
        **sobrescritas,
    }
    colunas = ", ".join(dados)
    valores = ", ".join(f":{coluna}" for coluna in dados)
    return conexao.execute(
        text(
            f"INSERT INTO contatos_emergencia ({colunas}) VALUES ({valores}) "
            "RETURNING id, ativo, consentido_em"
        ),
        dados,
    ).one()


def inserir_alerta(
    conexao: Connection,
    usuario_id,
    latitude: float = 0.25,
    longitude: float = 0.75,
    srid: int = 4326,
    **sobrescritas,
) -> Row:
    dados = {"usuario_id": usuario_id, **sobrescritas}
    colunas = ", ".join(["localizacao", *dados])
    valores = ", ".join(
        ["ST_SetSRID(ST_MakePoint(:longitude, :latitude), :srid)", *(f":{c}" for c in dados)]
    )
    return conexao.execute(
        text(
            f"INSERT INTO alertas_sos ({colunas}) VALUES ({valores}) "
            "RETURNING id, status_envio, tentativas, mensagem, criado_em"
        ),
        {**dados, "latitude": latitude, "longitude": longitude, "srid": srid},
    ).one()


def inserir_tentativa(
    conexao: Connection,
    alerta_id,
    contato_id,
    numero_tentativa: int = 1,
    status: str = "FALHOU",
    **sobrescritas,
) -> Row:
    dados = {
        "alerta_id": alerta_id,
        "contato_id": contato_id,
        "numero_tentativa": numero_tentativa,
        "status": status,
        **sobrescritas,
    }
    colunas = ", ".join(dados)
    valores = ", ".join(f":{coluna}" for coluna in dados)
    return conexao.execute(
        text(
            f"INSERT INTO tentativas_envio_sos ({colunas}) VALUES ({valores}) "
            "RETURNING id, executado_em"
        ),
        dados,
    ).one()
