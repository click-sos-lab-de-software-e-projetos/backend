from sqlalchemy import Engine, text


def colunas(engine: Engine, tabela: str) -> dict[str, tuple[str, int | None, bool]]:
    with engine.connect() as conexao:
        linhas = conexao.execute(
            text(
                "SELECT column_name, data_type, character_maximum_length, is_nullable "
                "FROM information_schema.columns WHERE table_name = :tabela"
            ),
            {"tabela": tabela},
        )
        return {nome: (tipo, tamanho, nulo == "YES") for nome, tipo, tamanho, nulo in linhas}


def definicoes_de_indices(engine: Engine, tabela: str) -> list[str]:
    with engine.connect() as conexao:
        return list(
            conexao.execute(
                text("SELECT indexdef FROM pg_indexes WHERE tablename = :tabela"),
                {"tabela": tabela},
            ).scalars()
        )


def tabelas(engine: Engine) -> set[str]:
    with engine.connect() as conexao:
        return set(
            conexao.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            ).scalars()
        )


def restricoes(engine: Engine, tabela: str) -> set[tuple[str, str]]:
    with engine.connect() as conexao:
        linhas = conexao.execute(
            text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = to_regclass(:tabela)"
            ),
            {"tabela": tabela},
        )
        return {(nome, definicao) for nome, definicao in linhas}


def retrato_do_schema(engine: Engine, nomes: list[str]) -> dict:
    return {
        tabela: {
            "colunas": colunas(engine, tabela),
            "indices": sorted(definicoes_de_indices(engine, tabela)),
            "restricoes": restricoes(engine, tabela),
        }
        for tabela in nomes
    }
