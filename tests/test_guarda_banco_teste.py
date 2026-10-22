import pytest

from integracao.banco import BancoDeTesteInseguro, validar_url_de_teste

URL_APP = "postgresql+psycopg://app:senha@host:5432/click_sos"


def validar_url_de_teste_igual_a_database_url_deve_recusar():
    with pytest.raises(BancoDeTesteInseguro):
        validar_url_de_teste(URL_APP, URL_APP)


def validar_url_de_teste_igual_a_database_url_sem_driver_deve_recusar():
    with pytest.raises(BancoDeTesteInseguro):
        validar_url_de_teste(URL_APP, "postgresql://app:senha@host:5432/click_sos")


def validar_url_de_teste_diferente_da_database_url_deve_aceitar():
    url_teste = "postgresql+psycopg://teste:teste@localhost:5433/click_sos_test"
    assert validar_url_de_teste(url_teste, URL_APP) == url_teste


def validar_url_de_teste_sem_database_url_deve_aceitar():
    url_teste = "postgresql://teste:teste@localhost:5433/click_sos_test"
    esperado = "postgresql+psycopg://teste:teste@localhost:5433/click_sos_test"
    assert validar_url_de_teste(url_teste, None) == esperado
