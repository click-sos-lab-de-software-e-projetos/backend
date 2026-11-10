import importlib.util
import math
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import COR_VERDE, COR_VERMELHA
from app.services.mapa import ResumoRecalculo, recalcular_regioes
from integracao.fabricas import inserir_carga_ssp, inserir_ocorrencia, inserir_regiao

MAIS_RECENTE = date(2026, 6, 30)

CAMINHO = Path(__file__).parents[2] / "scripts" / "recalcular_mapa.py"
_spec = importlib.util.spec_from_file_location("recalcular_mapa", CAMINHO)
recalcular_mapa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recalcular_mapa)


@pytest.fixture
def distritos(banco_migrado):
    """A (0,01° x 0,01°) e B, ao lado, com o dobro da área, perto de (0, 0)."""
    with banco_migrado.begin() as conexao:
        a = inserir_regiao(conexao, 0.0, 0.0, 0.01, 0.01).id
        b = inserir_regiao(conexao, 0.01, 0.0, 0.03, 0.01).id
        carga = inserir_carga_ssp(conexao).id
        # Contam: A soma 4; B soma 2 em área dobrada (densidade 1/4 da de A).
        inserir_ocorrencia(conexao, carga, 0.005, 0.005, peso=3, data_ocorrencia=MAIS_RECENTE)
        inserir_ocorrencia(conexao, carga, 0.005, 0.005, peso=1, data_ocorrencia=date(2025, 12, 30))
        inserir_ocorrencia(conexao, carga, 0.005, 0.02, peso=2, data_ocorrencia=date(2026, 1, 15))
        # Não contam: antes da janela de 6 meses, sem data e fora de qualquer distrito.
        inserir_ocorrencia(conexao, carga, 0.005, 0.02, peso=3, data_ocorrencia=date(2025, 12, 29))
        inserir_ocorrencia(conexao, carga, 0.005, 0.02, peso=3, data_ocorrencia=None)
        inserir_ocorrencia(conexao, carga, 0.5, 0.5, peso=3, data_ocorrencia=date(2026, 3, 1))
    return a, b


def _regioes(banco_migrado) -> dict:
    with banco_migrado.connect() as conexao:
        linhas = conexao.execute(
            text(
                "SELECT id, score_oficial, score_final, cor_hex, raio_metros, atualizado_em, "
                "ST_Area(limites::geography) AS area_m2 FROM regioes_seguranca"
            )
        ).all()
    return {linha.id: linha for linha in linhas}


def recalcular_deve_gravar_score_cor_e_raio_dos_distritos(banco_migrado, distritos):
    a, b = distritos
    antes = _regioes(banco_migrado)

    with Session(banco_migrado) as sessao:
        recalcular_regioes(sessao)
        sessao.commit()

    regioes = _regioes(banco_migrado)
    assert (regioes[a].score_oficial, regioes[a].score_final, regioes[a].cor_hex) == (100, 100, COR_VERMELHA)
    assert (regioes[b].score_oficial, regioes[b].score_final, regioes[b].cor_hex) == (25, 25, COR_VERDE)
    for regiao in (a, b):
        assert regioes[regiao].raio_metros == round(math.sqrt(regioes[regiao].area_m2 / math.pi))
        assert regioes[regiao].atualizado_em > antes[regiao].atualizado_em


def recalcular_deve_resumir_a_janela_e_as_cores_sem_dados_pessoais(banco_migrado, distritos):
    with Session(banco_migrado) as sessao:
        resumo = recalcular_regioes(sessao)

    assert resumo == ResumoRecalculo(
        inicio_janela=date(2025, 12, 30),
        fim_janela=MAIS_RECENTE,
        distritos=2,
        por_cor={COR_VERMELHA: 1, COR_VERDE: 1},
    )


def recalcular_sem_ocorrencias_deve_deixar_tudo_verde_com_score_0(banco_migrado):
    with banco_migrado.begin() as conexao:
        inserir_regiao(conexao, 0.0, 0.0, 0.01, 0.01, score_final=80, cor_hex=COR_VERMELHA)

    with Session(banco_migrado) as sessao:
        resumo = recalcular_regioes(sessao)
        sessao.commit()

    (regiao,) = _regioes(banco_migrado).values()
    assert (regiao.score_final, regiao.cor_hex) == (0, COR_VERDE)
    assert (resumo.inicio_janela, resumo.fim_janela) == (None, None)


def _scores(banco_migrado) -> set:
    with banco_migrado.connect() as conexao:
        return set(conexao.execute(text("SELECT id, score_final, cor_hex FROM regioes_seguranca")).all())


def comando_sem_gravar_deve_mostrar_o_resumo_sem_alterar_o_banco(
    banco_migrado, distritos, url_teste, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", url_teste)
    antes = _scores(banco_migrado)

    assert recalcular_mapa.main([]) == 0

    assert _scores(banco_migrado) == antes
    saida = capsys.readouterr().out
    assert "2025-12-30" in saida and "2026-06-30" in saida
    assert "--gravar" in saida
    assert "teste:teste" not in saida  # nunca imprime a URL do banco


def comando_com_gravar_deve_regravar_os_distritos(banco_migrado, distritos, url_teste, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", url_teste)
    a, b = distritos

    assert recalcular_mapa.main(["--gravar"]) == 0

    assert _scores(banco_migrado) == {(a, 100, COR_VERMELHA), (b, 25, COR_VERDE)}
