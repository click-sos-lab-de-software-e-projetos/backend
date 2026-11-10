"""Score de risco dos distritos (MAP-05). Funções puras, sem banco.

Densidade = soma dos pesos das ocorrências ÷ área em km². O distrito mais
denso vale 100 e os demais são proporcionais a ele. Feedback comunitário
tem peso zero (Regra 05), então não entra aqui.
"""

import math
from collections.abc import Hashable, Mapping
from dataclasses import dataclass

from app.constants import COR_AMARELA, COR_VERDE, COR_VERMELHA, SCORE_MINIMO_AMARELO, SCORE_MINIMO_VERMELHO


@dataclass(frozen=True)
class ScoreDistrito:
    score: int
    cor_hex: str


def cor_do_score(score: int) -> str:
    if score >= SCORE_MINIMO_VERMELHO:
        return COR_VERMELHA
    if score >= SCORE_MINIMO_AMARELO:
        return COR_AMARELA
    return COR_VERDE


def calcular_scores[K: Hashable](pesos_e_areas_km2: Mapping[K, tuple[float, float]]) -> dict[K, ScoreDistrito]:
    densidades = {chave: pesos / area for chave, (pesos, area) in pesos_e_areas_km2.items()}
    maior = max(densidades.values(), default=0)
    resultado = {}
    for chave, densidade in densidades.items():
        score = _arredondar(densidade / maior * 100) if maior > 0 else 0
        resultado[chave] = ScoreDistrito(score, cor_do_score(score))
    return resultado


def raio_equivalente_metros(area_m2: float) -> int:
    """Raio do círculo com a mesma área do distrito; o banco exige raio > 0."""
    return max(1, _arredondar(math.sqrt(area_m2 / math.pi)))


def _arredondar(valor: float) -> int:
    # round() do Python arredonda 0,5 para o par; aqui 0,5 sempre sobe.
    return math.floor(valor + 0.5)
