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


def inserir_fonte_geografica(conexao: Connection, **sobrescritas) -> Row:
    n = next(_sequencia)
    dados = {
        "arquivo_sha256": f"{n:064x}",
        "nome_arquivo": f"distritos-{n}.geojson",
        "fonte_url": "https://example.com/distritos.geojson",
        "licenca": "aberta",
        **sobrescritas,
    }
    return conexao.execute(
        text(
            "INSERT INTO interno.fontes_geograficas (arquivo_sha256, nome_arquivo, fonte_url, licenca) "
            "VALUES (:arquivo_sha256, :nome_arquivo, :fonte_url, :licenca) RETURNING id"
        ),
        dados,
    ).one()


def inserir_regiao(
    conexao: Connection, oeste: float, sul: float, leste: float, norte: float, **sobrescritas
) -> Row:
    """Distrito retangular (graus, SRID 4326); o centroide é o centro do retângulo."""
    n = next(_sequencia)
    dados = {
        "id_publico": f"distrito-teste-{n}",
        "nome": f"Distrito Ficticio {n}",
        "raio_metros": 100,
        **sobrescritas,
    }
    if "fonte_geografica_id" not in dados:
        dados["fonte_geografica_id"] = inserir_fonte_geografica(conexao).id
    colunas = ", ".join(["limites", "centroide", *dados])
    valores = ", ".join(
        [
            "ST_Multi(ST_MakeEnvelope(:oeste, :sul, :leste, :norte, 4326))",
            "ST_Centroid(ST_MakeEnvelope(:oeste, :sul, :leste, :norte, 4326))",
            *(f":{c}" for c in dados),
        ]
    )
    return conexao.execute(
        text(f"INSERT INTO regioes_seguranca ({colunas}) VALUES ({valores}) RETURNING id, id_publico"),
        {**dados, "oeste": oeste, "sul": sul, "leste": leste, "norte": norte},
    ).one()


def inserir_carga_ssp(conexao: Connection, **sobrescritas) -> Row:
    n = next(_sequencia)
    dados = {"arquivo_sha256": f"{n:064x}", "nome_arquivo": f"ssp-{n}.xlsx", **sobrescritas}
    colunas = ", ".join(dados)
    valores = ", ".join(f":{coluna}" for coluna in dados)
    return conexao.execute(
        text(f"INSERT INTO interno.cargas_ssp ({colunas}) VALUES ({valores}) RETURNING id"), dados
    ).one()


def inserir_ocorrencia(
    conexao: Connection, carga_id, latitude: float, longitude: float, peso: int = 1, **sobrescritas
) -> Row:
    n = next(_sequencia)
    dados = {
        "carga_id": carga_id,
        "chave_fonte": f"ocorrencia-{n}",
        "municipio_ibge": "0000000",
        "municipio_nome": "Municipio Ficticio",
        "peso": peso,
        **sobrescritas,
    }
    colunas = ", ".join(["localizacao", *dados])
    valores = ", ".join(["ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)", *(f":{c}" for c in dados)])
    return conexao.execute(
        text(f"INSERT INTO interno.ocorrencias_ssp ({colunas}) VALUES ({valores}) RETURNING id"),
        {**dados, "latitude": latitude, "longitude": longitude},
    ).one()
