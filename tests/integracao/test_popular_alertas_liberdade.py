import importlib.util
import random
from pathlib import Path

import pytest
from sqlalchemy import text

from app.constants import CATEGORIAS_ALERTA_COMUNIDADE, VALIDADE_ALERTA_COMUNIDADE_HORAS
from integracao.fabricas import inserir_regiao

CAMINHO = Path(__file__).parents[2] / "scripts" / "popular_alertas_liberdade.py"
_spec = importlib.util.spec_from_file_location("popular_alertas_liberdade", CAMINHO)
popular_alertas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(popular_alertas)


@pytest.fixture
def liberdade(banco_migrado, url_teste, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", url_teste)
    with banco_migrado.begin() as conexao:
        inserir_regiao(conexao, 0.0, 0.0, 0.01, 0.01, nome="Liberdade")
        inserir_regiao(conexao, 0.01, 0.0, 0.02, 0.01, nome="Sé")


def _alertas(banco_migrado) -> list:
    with banco_migrado.connect() as conexao:
        return conexao.execute(
            text(
                "SELECT a.categoria, a.texto, ST_Y(a.localizacao) AS latitude, ST_X(a.localizacao) AS longitude, "
                "a.criado_em > now() - make_interval(hours => :horas) AS valido, u.email "
                "FROM alertas_comunidade a JOIN usuarios u ON u.id = a.usuario_id"
            ),
            {"horas": VALIDADE_ALERTA_COMUNIDADE_HORAS},
        ).all()


def montar_alertas_deve_respeitar_as_regras_do_alerta():
    alertas = popular_alertas.montar_alertas([(0.0, 0.0)] * 200, random.Random(1))

    assert {a["categoria"] for a in alertas} == set(CATEGORIAS_ALERTA_COMUNIDADE)
    assert all(a["texto"] for a in alertas if a["categoria"] == "OUTRO")
    assert all(len(a["texto"]) <= 500 for a in alertas if a["texto"])
    assert all(1 <= a["minutos"] < VALIDADE_ALERTA_COMUNIDADE_HORAS * 60 for a in alertas)


def comando_sem_gravar_deve_simular_sem_alterar_o_banco(banco_migrado, liberdade, capsys):
    assert popular_alertas.main([]) == 0

    assert _alertas(banco_migrado) == []
    saida = capsys.readouterr().out
    assert "Alertas em Liberdade: 20" in saida and "--gravar" in saida
    assert "teste:teste" not in saida  # nunca imprime a URL do banco


def comando_com_gravar_deve_criar_alertas_validos_dentro_da_liberdade(banco_migrado, liberdade):
    assert popular_alertas.main(["--quantidade", "12", "--gravar"]) == 0

    alertas = _alertas(banco_migrado)
    assert len(alertas) == 12
    assert all(0 <= a.latitude <= 0.01 and 0 <= a.longitude <= 0.01 for a in alertas)
    assert all(a.valido and a.email == popular_alertas.EMAIL_DEMO for a in alertas)


def limpar_deve_trocar_os_alertas_anteriores_da_conta_de_demonstracao(banco_migrado, liberdade):
    assert popular_alertas.main(["--quantidade", "5", "--gravar"]) == 0
    assert popular_alertas.main(["--quantidade", "5", "--gravar"]) == 0
    assert len(_alertas(banco_migrado)) == 10

    assert popular_alertas.main(["--quantidade", "3", "--limpar", "--gravar"]) == 0

    assert len(_alertas(banco_migrado)) == 3
    with banco_migrado.connect() as conexao:
        contas = conexao.execute(text("SELECT count(*) FROM usuarios")).scalar_one()
    assert contas == 1


def distrito_inexistente_deve_falhar_sem_gravar(banco_migrado, liberdade, capsys):
    assert popular_alertas.main(["--distrito", "Atlântida", "--gravar"]) == 2

    assert _alertas(banco_migrado) == []
    assert "não encontrado" in capsys.readouterr().err
