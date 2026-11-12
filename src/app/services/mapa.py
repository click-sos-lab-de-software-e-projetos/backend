"""Mapa de risco: recálculo do score (MAP-05), consulta dos distritos (MAP-06/07)
e alertas da comunidade no mapa.

As tabelas do mapa pertencem à carga da SSP e do GeoSampa e não têm modelo
ORM; por isso o acesso é por SQL explícito.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import (
    JANELA_SCORE_MESES,
    LIMITE_ALERTAS_COMUNIDADE_MAPA,
    LIMITE_REGIOES_MAPA,
    VALIDADE_ALERTA_COMUNIDADE_HORAS,
)
from app.db.models import Usuario
from app.schemas.mapa import CriarAlertaComunidadeRequisicao
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


# Distância até a borda, em metros: o distrito onde o ponto está fica com 0 e vem primeiro.
_PROXIMAS = text(
    "WITH ponto AS (SELECT ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography AS g) "
    "SELECT r.id_publico, r.nome, ST_Y(r.centroide) AS latitude, ST_X(r.centroide) AS longitude, "
    "round(r.score_final)::int AS score, r.cor_hex, r.raio_metros "
    "FROM regioes_seguranca r, ponto "
    "WHERE ST_DWithin(r.limites::geography, ponto.g, :raio) "
    "ORDER BY ST_Distance(r.limites::geography, ponto.g), r.id_publico "
    "LIMIT :limite"
)


def listar_regioes_proximas(sessao: Session, latitude: float, longitude: float, raio_metros: int) -> list[dict]:
    linhas = sessao.execute(
        _PROXIMAS,
        {"latitude": latitude, "longitude": longitude, "raio": raio_metros, "limite": LIMITE_REGIOES_MAPA},
    ).all()
    return [
        {
            "id": linha.id_publico,
            "nome": linha.nome,
            "centroide": {"latitude": linha.latitude, "longitude": linha.longitude},
            "score": linha.score,
            "cor_hex": linha.cor_hex,
            "raio_metros": linha.raio_metros,
        }
        for linha in linhas
    ]


class UsuarioNaoEncontrado(Exception):
    """Token válido de uma pessoa que não existe mais."""


# Não entram no score (Regra 05): só aparecem como ícones enquanto valem.
_INSERIR_ALERTA = text(
    "INSERT INTO alertas_comunidade (usuario_id, categoria, texto, localizacao) "
    "VALUES (:usuario_id, :categoria, :texto, ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)) "
    "RETURNING id, criado_em"
)

_ALERTAS_PROXIMOS = text(
    "SELECT id, categoria, texto, ST_Y(localizacao) AS latitude, ST_X(localizacao) AS longitude, criado_em "
    "FROM alertas_comunidade "
    "WHERE criado_em > now() - make_interval(hours => :horas) "
    "AND ST_DWithin(localizacao::geography, ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography, :raio) "
    "ORDER BY criado_em DESC, id "
    "LIMIT :limite"
)


def criar_alerta(sessao: Session, usuario_id: UUID, dados: CriarAlertaComunidadeRequisicao) -> dict:
    if sessao.get(Usuario, usuario_id) is None:
        raise UsuarioNaoEncontrado
    linha = sessao.execute(
        _INSERIR_ALERTA,
        {
            "usuario_id": usuario_id,
            "categoria": dados.categoria,
            "texto": dados.texto,
            "latitude": dados.latitude,
            "longitude": dados.longitude,
        },
    ).one()
    sessao.commit()
    return {
        "id": linha.id,
        "categoria": dados.categoria,
        "texto": dados.texto,
        "latitude": dados.latitude,
        "longitude": dados.longitude,
        "criado_em": linha.criado_em,
    }


def listar_alertas_proximos(sessao: Session, latitude: float, longitude: float, raio_metros: int) -> list[dict]:
    """Alertas das últimas horas de validade, do mais novo ao mais antigo."""
    linhas = sessao.execute(
        _ALERTAS_PROXIMOS,
        {
            "latitude": latitude,
            "longitude": longitude,
            "raio": raio_metros,
            "horas": VALIDADE_ALERTA_COMUNIDADE_HORAS,
            "limite": LIMITE_ALERTAS_COMUNIDADE_MAPA,
        },
    ).all()
    return [dict(linha._mapping) for linha in linhas]
