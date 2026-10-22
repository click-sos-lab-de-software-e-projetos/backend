from app.db.config import normalizar_url

NOME_VARIAVEL_URL_BANCO_TESTE = "TEST_DATABASE_URL"


class BancoDeTesteInseguro(RuntimeError):
    pass


def validar_url_de_teste(url_teste: str, url_app: str | None) -> str:
    url_teste = normalizar_url(url_teste)
    if url_app and url_teste == normalizar_url(url_app):
        raise BancoDeTesteInseguro(
            f"{NOME_VARIAVEL_URL_BANCO_TESTE} aponta para o mesmo banco da aplicação; "
            "os testes de integração apagam todas as tabelas."
        )
    return url_teste
