from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def somente_tabelas_mapeadas(objeto, nome, tipo, refletido, comparado_com) -> bool:
    return not (tipo == "table" and refletido and comparado_com is None)
