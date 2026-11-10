import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import COR_VERMELHA
from app.services.carga_distritos import ResumoDistritos, carregar_distritos

CAMINHO = Path(__file__).parents[2] / "scripts" / "carregar_mapa.py"
_spec = importlib.util.spec_from_file_location("carregar_mapa", CAMINHO)
carregar_mapa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(carregar_mapa)

QUADRADO = [[[-46.64, -23.56], [-46.63, -23.56], [-46.63, -23.55], [-46.64, -23.55], [-46.64, -23.56]]]
VIZINHO = [[[-46.63, -23.56], [-46.62, -23.56], [-46.62, -23.55], [-46.63, -23.55], [-46.63, -23.56]]]


def _geojson(nome_1="AGUA RASA", quadrado=QUADRADO) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"cd_distrito_municipal": "01", "nm_distrito_municipal": nome_1},
                "geometry": {"type": "Polygon", "coordinates": quadrado},
            },
            {
                "type": "Feature",
                "properties": {"cd_distrito_municipal": 10, "nm_distrito_municipal": "BRAS"},
                "geometry": {"type": "MultiPolygon", "coordinates": [VIZINHO]},
            },
        ],
    }


def _carregar(engine, geojson=None, sha="d" * 64) -> ResumoDistritos:
    with Session(engine) as sessao:
        resumo = carregar_distritos(
            sessao, geojson or _geojson(), sha, "distritos.geojson", "https://geosampa.example", "aberta"
        )
        sessao.commit()
    return resumo


def _regioes(engine) -> dict:
    with engine.connect() as conexao:
        linhas = conexao.execute(
            text(
                "SELECT id_publico, nome, fonte_geografica_id, GeometryType(limites) AS tipo, "
                "ST_SRID(limites) AS srid, ST_Equals(centroide, ST_Centroid(limites)) AS centroide_ok, "
                "raio_metros, score_final, cor_hex, "
                "ST_AsText(limites) AS wkt FROM regioes_seguranca"
            )
        ).all()
    return {linha.id_publico: linha for linha in linhas}


def _fontes(engine) -> list:
    with engine.connect() as conexao:
        return conexao.execute(text("SELECT * FROM interno.fontes_geograficas ORDER BY criado_em")).all()


def carga_deve_gravar_a_fonte_e_os_distritos(banco_migrado):
    resumo = _carregar(banco_migrado)

    (fonte,) = _fontes(banco_migrado)
    assert (fonte.arquivo_sha256, fonte.nome_arquivo, fonte.fonte_url, fonte.licenca) == (
        "d" * 64,
        "distritos.geojson",
        "https://geosampa.example",
        "aberta",
    )
    regioes = _regioes(banco_migrado)
    assert set(regioes) == {"distrito-sp-1", "distrito-sp-10"}
    assert regioes["distrito-sp-1"].nome == "AGUA RASA"
    for regiao in regioes.values():
        assert (regiao.tipo, regiao.srid, regiao.centroide_ok, regiao.fonte_geografica_id) == (
            "MULTIPOLYGON",
            4326,
            True,
            fonte.id,
        )
        assert 500 < regiao.raio_metros < 700  # quadrado de ~1,1 km de lado
    assert resumo == ResumoDistritos(fonte.id, False, inseridos=2, atualizados=0)


def mesmo_arquivo_nao_deve_alterar_nada(banco_migrado):
    primeira = _carregar(banco_migrado)
    antes = (_fontes(banco_migrado), _regioes(banco_migrado))

    segunda = _carregar(banco_migrado, _geojson(nome_1="OUTRO NOME"))

    assert (_fontes(banco_migrado), _regioes(banco_migrado)) == antes
    assert segunda == ResumoDistritos(primeira.fonte_id, True)


def arquivo_novo_deve_atualizar_nome_e_limites_sem_zerar_o_score(banco_migrado):
    _carregar(banco_migrado)
    with banco_migrado.begin() as conexao:
        conexao.execute(text("UPDATE regioes_seguranca SET score_final = 80, cor_hex = :cor"), {"cor": COR_VERMELHA})
    maior = [[[-46.65, -23.57], [-46.63, -23.57], [-46.63, -23.55], [-46.65, -23.55], [-46.65, -23.57]]]
    antes = _regioes(banco_migrado)["distrito-sp-1"]

    resumo = _carregar(banco_migrado, _geojson(nome_1="AGUA RASA NOVA", quadrado=maior), sha="e" * 64)

    depois = _regioes(banco_migrado)["distrito-sp-1"]
    assert (depois.nome, depois.score_final, depois.cor_hex) == ("AGUA RASA NOVA", 80, COR_VERMELHA)
    assert depois.wkt != antes.wkt and depois.raio_metros > antes.raio_metros
    assert depois.fonte_geografica_id == resumo.fonte_id
    assert (resumo.inseridos, resumo.atualizados) == (0, 2)


def feature_sem_codigo_deve_impedir_a_carga(banco_migrado):
    geojson = _geojson()
    del geojson["features"][1]["properties"]["cd_distrito_municipal"]

    with Session(banco_migrado) as sessao, pytest.raises(ValueError, match="cd_distrito_municipal"):
        carregar_distritos(sessao, geojson, "d" * 64, "distritos.geojson", None, None)


def comando_distritos_com_gravar_deve_gravar_os_distritos(banco_migrado, tmp_path, url_teste, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", url_teste)
    caminho = tmp_path / "distritos-sp.geojson"
    caminho.write_text(json.dumps(_geojson()), encoding="utf-8")

    assert carregar_mapa.main(["distritos", str(caminho), "--gravar"]) == 0

    assert set(_regioes(banco_migrado)) == {"distrito-sp-1", "distrito-sp-10"}
    (fonte,) = _fontes(banco_migrado)
    assert fonte.nome_arquivo == "distritos-sp.geojson"
    saida = capsys.readouterr().out
    assert "Inseridos: 2" in saida
    assert "teste:teste" not in saida
