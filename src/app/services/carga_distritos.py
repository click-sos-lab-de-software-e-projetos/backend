"""Carga dos distritos do GeoSampa (MAP-03).

Cada feature do geojson vira uma linha de regioes_seguranca com
id_publico = distrito-sp-{código} (sem zeros à esquerda). Idempotente pelo
sha256 do arquivo; um arquivo novo atualiza nome e limites dos distritos pelo
id_publico e mantém o score, que só o recálculo (MAP-05) altera.
"""

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.score_mapa import raio_equivalente_metros

CAMPO_CODIGO_PADRAO = "cd_distrito_municipal"
CAMPO_NOME_PADRAO = "nm_distrito_municipal"
_TIPOS_ACEITOS = {"Polygon", "MultiPolygon"}


@dataclass(frozen=True)
class ResumoDistritos:
    fonte_id: UUID
    ja_carregada: bool
    inseridos: int = 0
    atualizados: int = 0


@dataclass(frozen=True)
class _Distrito:
    id_publico: str
    nome: str
    geometria: str


_BUSCAR_FONTE = text("SELECT id FROM interno.fontes_geograficas WHERE arquivo_sha256 = :sha")
_CRIAR_FONTE = text(
    "INSERT INTO interno.fontes_geograficas (arquivo_sha256, nome_arquivo, fonte_url, licenca) "
    "VALUES (:sha, :nome, :fonte_url, :licenca) RETURNING id"
)
# Geometria sem CRS é tratada como WGS84 (padrão do GeoJSON); com CRS, é reprojetada.
_GEOMETRIA = (
    "ST_Multi(CASE WHEN ST_SRID(ST_GeomFromGeoJSON(:geometria)) = 0 "
    "THEN ST_SetSRID(ST_GeomFromGeoJSON(:geometria), 4326) "
    "ELSE ST_Transform(ST_GeomFromGeoJSON(:geometria), 4326) END)"
)
_AREA = text(f"SELECT ST_Area({_GEOMETRIA}::geography)")
_GRAVAR = text(
    f"WITH g AS (SELECT {_GEOMETRIA} AS limites) "
    "INSERT INTO regioes_seguranca (id_publico, fonte_geografica_id, nome, limites, centroide, raio_metros) "
    "SELECT :id_publico, :fonte_id, :nome, g.limites, ST_Centroid(g.limites), :raio FROM g "
    "ON CONFLICT (id_publico) DO UPDATE SET fonte_geografica_id = EXCLUDED.fonte_geografica_id, "
    "nome = EXCLUDED.nome, limites = EXCLUDED.limites, centroide = EXCLUDED.centroide, "
    "raio_metros = EXCLUDED.raio_metros, atualizado_em = now() "
    "RETURNING (xmax = 0) AS inserido"
)


def carregar_distritos(
    sessao: Session,
    geojson: dict,
    arquivo_sha256: str,
    nome_arquivo: str,
    fonte_url: str,
    licenca: str,
    campo_codigo: str = CAMPO_CODIGO_PADRAO,
    campo_nome: str = CAMPO_NOME_PADRAO,
) -> ResumoDistritos:
    """Grava a fonte e os distritos. Não faz commit."""
    existente = sessao.execute(_BUSCAR_FONTE, {"sha": arquivo_sha256}).scalar_one_or_none()
    if existente is not None:
        return ResumoDistritos(existente, True)
    distritos = _interpretar(geojson, campo_codigo, campo_nome)

    fonte_id = sessao.execute(
        _CRIAR_FONTE, {"sha": arquivo_sha256, "nome": nome_arquivo, "fonte_url": fonte_url, "licenca": licenca}
    ).scalar_one()
    inseridos = 0
    for distrito in distritos:
        area_m2 = sessao.execute(_AREA, {"geometria": distrito.geometria}).scalar_one()
        inseridos += sessao.execute(
            _GRAVAR,
            {
                "id_publico": distrito.id_publico,
                "fonte_id": fonte_id,
                "nome": distrito.nome,
                "geometria": distrito.geometria,
                "raio": raio_equivalente_metros(area_m2),
            },
        ).scalar_one()
    return ResumoDistritos(fonte_id, False, inseridos, len(distritos) - inseridos)


def _interpretar(geojson: dict, campo_codigo: str, campo_nome: str) -> list[_Distrito]:
    """Valida o arquivo inteiro antes de gravar qualquer coisa."""
    crs = geojson.get("crs")
    distritos = []
    for posicao, feature in enumerate(geojson.get("features") or [], start=1):
        propriedades = feature.get("properties") or {}
        geometria = feature.get("geometry") or {}
        codigo, nome = propriedades.get(campo_codigo), propriedades.get(campo_nome)
        if codigo is None or str(codigo).strip() == "" or not nome:
            raise ValueError(f"feature {posicao} sem {campo_codigo} ou {campo_nome}")
        if geometria.get("type") not in _TIPOS_ACEITOS:
            raise ValueError(f"feature {posicao} com geometria {geometria.get('type')!r}; esperado Polygon")
        if crs and "crs" not in geometria:
            geometria = {**geometria, "crs": crs}
        codigo = str(codigo).strip()
        codigo = str(int(codigo)) if codigo.isdigit() else codigo
        distritos.append(_Distrito(f"distrito-sp-{codigo}", str(nome).strip()[:160], json.dumps(geometria)))
    if not distritos:
        raise ValueError("geojson sem features")
    return distritos
