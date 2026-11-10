"""Mapa de risco: recálculo do score dos distritos (MAP-05).

As tabelas do mapa pertencem à carga da SSP e do GeoSampa e não têm modelo
ORM; por isso o acesso é por SQL explícito.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import JANELA_SCORE_MESES
from app.services.score_mapa import calcular_scores, raio_equivalente_metros

_JANELA = text(
    "SELECT (max(data_ocorrencia) - make_interval(months => :meses))::date AS inicio, "
    "max(data_ocorrencia) AS fim FROM interno.ocorrencias_ssp"
)

# ST_Covers usa o índice GiST das ocorrências; quem está na divisa conta para os dois distritos.
_PESOS_POR_DISTRITO = text(
    "SELECT r.id, ST_Area(r.limites::geography) AS area_m2, COALESCE(sum(o.peso), 0) AS pesos "
    "FROM regioes_seguranca r "
    "LEFT JOIN interno.ocorrencias_ssp o "
    "ON ST_Covers(r.limites, o.localizacao) AND o.data_ocorrencia BETWEEN :inicio AND :fim "
    "GROUP BY r.id"
)

_GRAVAR = text(
    "UPDATE regioes_seguranca SET score_oficial = :score, score_final = :score, "
    "cor_hex = :cor_hex, raio_metros = :raio_metros, atualizado_em = now() WHERE id = :id"
)


@dataclass(frozen=True)
class ResumoRecalculo:
    inicio_janela: date | None
    fim_janela: date | None
    distritos: int
    por_cor: dict[str, int] = field(default_factory=dict)


def recalcular_regioes(sessao: Session) -> ResumoRecalculo:
    """Regrava score, cor e raio de todos os distritos. Não faz commit."""
    janela = sessao.execute(_JANELA, {"meses": JANELA_SCORE_MESES}).one()
    linhas = sessao.execute(_PESOS_POR_DISTRITO, {"inicio": janela.inicio, "fim": janela.fim}).all()
    scores = calcular_scores({linha.id: (float(linha.pesos), linha.area_m2 / 1_000_000) for linha in linhas})
    if linhas:
        sessao.execute(
            _GRAVAR,
            [
                {
                    "id": linha.id,
                    "score": scores[linha.id].score,
                    "cor_hex": scores[linha.id].cor_hex,
                    "raio_metros": raio_equivalente_metros(linha.area_m2),
                }
                for linha in linhas
            ],
        )
    return ResumoRecalculo(
        inicio_janela=janela.inicio,
        fim_janela=janela.fim,
        distritos=len(linhas),
        por_cor=dict(Counter(score.cor_hex for score in scores.values())),
    )
