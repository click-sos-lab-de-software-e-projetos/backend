import math

import pytest

from app.constants import COR_AMARELA, COR_VERDE, COR_VERMELHA
from app.services.score_mapa import ScoreDistrito, calcular_scores, cor_do_score, raio_equivalente_metros


@pytest.mark.parametrize(
    ("score", "cor"),
    [(0, COR_VERDE), (33, COR_VERDE), (34, COR_AMARELA), (66, COR_AMARELA), (67, COR_VERMELHA), (100, COR_VERMELHA)],
)
def cor_deve_seguir_as_3_faixas_do_score(score, cor):
    assert cor_do_score(score) == cor


def score_deve_ser_densidade_sobre_a_maior_densidade_vezes_100():
    # Densidades: a = 10/1 = 10, b = 10/2 = 5, c = 1/3 ≈ 0,33, d = 2/3 ≈ 0,67.
    scores = calcular_scores({"a": (10, 1.0), "b": (10, 2.0), "c": (1, 3.0), "d": (2, 3.0)})

    assert scores == {
        "a": ScoreDistrito(100, COR_VERMELHA),
        "b": ScoreDistrito(50, COR_AMARELA),
        "c": ScoreDistrito(3, COR_VERDE),
        "d": ScoreDistrito(7, COR_VERDE),
    }


def sem_ocorrencias_todo_distrito_deve_ter_score_0_e_cor_verde():
    assert calcular_scores({"a": (0, 1.0), "b": (0, 5.0)}) == {
        "a": ScoreDistrito(0, COR_VERDE),
        "b": ScoreDistrito(0, COR_VERDE),
    }


def sem_distritos_deve_devolver_vazio():
    assert calcular_scores({}) == {}


def raio_deve_ser_o_de_um_circulo_com_a_mesma_area():
    assert raio_equivalente_metros(math.pi * 1000**2) == 1000
    assert raio_equivalente_metros(1_000_000) == 564  # sqrt(1 km² / π) ≈ 564,19 m


def raio_de_area_minuscula_deve_ser_ao_menos_1_metro():
    # regioes_seguranca exige raio_metros > 0.
    assert raio_equivalente_metros(0.1) == 1
