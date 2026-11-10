"""Carrega os dados do mapa de risco: ocorrências da SSP e distritos do GeoSampa (MAP-03).

Sem --gravar, só processa e mostra o resumo, sem gravar nada. Depois de cada
carga, recalcula score, cor e raio dos distritos (MAP-05).

    python scripts/carregar_mapa.py distritos distritos-sp.geojson
    python scripts/carregar_mapa.py distritos distritos-sp.geojson --gravar
    python scripts/carregar_mapa.py ssp SPDadosCriminais_2026.xlsx --substituir
    python scripts/carregar_mapa.py ssp SPDadosCriminais_2026.xlsx --substituir --gravar

--substituir apaga as ocorrências das cargas anteriores na mesma transação
(o registro delas em interno.cargas_ssp fica como histórico). Use sempre que o
arquivo novo cobrir o período das cargas anteriores.

Lê DATABASE_URL do ambiente. Para o Neon, baixe o .env com
./scripts/fetch-env.sh antes. A URL do banco nunca é impressa.
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.config import obter_url_banco
from app.db.sessao import criar_engine
from app.services.carga_distritos import CAMPO_CODIGO_PADRAO, CAMPO_NOME_PADRAO, carregar_distritos
from app.services.carga_ssp import carregar_ssp, ler_linhas_xlsx, sha256_arquivo
from app.services.mapa import recalcular_regioes

FONTE_SSP = "https://www.ssp.sp.gov.br/estatistica/consultas"
LICENCA_SSP = "Dados públicos de transparência da SSP-SP (Lei 12.527/2011)"
FONTE_GEOSAMPA = "https://geosampa.prefeitura.sp.gov.br"
LICENCA_GEOSAMPA = "Dados abertos GeoSampa / Prefeitura de São Paulo"


def _carregar_ssp(sessao: Session, args) -> list[str]:
    resumo = carregar_ssp(
        sessao,
        ler_linhas_xlsx(args.arquivo),
        sha256_arquivo(args.arquivo),
        args.arquivo.name,
        args.fonte_url or FONTE_SSP,
        args.licenca or LICENCA_SSP,
        substituir=args.substituir,
    )
    if resumo.ja_carregada:
        return [f"Arquivo já carregado (carga {resumo.carga_id}); nada a fazer."]
    erros = ", ".join(f"{motivo}: {total}" for motivo, total in sorted(resumo.erros.items())) or "nenhum"
    return [
        f"Linhas lidas: {resumo.linhas_lidas} (só a capital)",
        f"Inseridas: {resumo.inseridas}",
        f"Atualizadas: {resumo.atualizadas}",
        f"Rejeitadas: {resumo.rejeitadas} ({erros})",
        f"Removidas de cargas anteriores: {resumo.removidas}",
    ]


def _carregar_distritos(sessao: Session, args) -> list[str]:
    resumo = carregar_distritos(
        sessao,
        json.loads(args.arquivo.read_text(encoding="utf-8")),
        sha256_arquivo(args.arquivo),
        args.arquivo.name,
        args.fonte_url or FONTE_GEOSAMPA,
        args.licenca or LICENCA_GEOSAMPA,
        campo_codigo=args.campo_codigo,
        campo_nome=args.campo_nome,
    )
    if resumo.ja_carregada:
        return [f"Arquivo já carregado (fonte {resumo.fonte_id}); nada a fazer."]
    return [f"Inseridos: {resumo.inseridos}", f"Atualizados: {resumo.atualizados}"]


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    ssp = subcomandos.add_parser("ssp", help="xlsx de ocorrências da SSP-SP")
    ssp.add_argument("--substituir", action="store_true", help="apaga as ocorrências das cargas anteriores")
    ssp.set_defaults(carregar=_carregar_ssp)

    distritos = subcomandos.add_parser("distritos", help="geojson de distritos do GeoSampa")
    distritos.add_argument("--campo-codigo", default=CAMPO_CODIGO_PADRAO)
    distritos.add_argument("--campo-nome", default=CAMPO_NOME_PADRAO)
    distritos.set_defaults(carregar=_carregar_distritos)

    for subcomando in (ssp, distritos):
        subcomando.add_argument("arquivo", type=Path)
        subcomando.add_argument("--fonte-url", help="URL de onde o arquivo foi baixado")
        subcomando.add_argument("--licenca")
        subcomando.add_argument("--gravar", action="store_true", help="grava no banco")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)

    engine = criar_engine(obter_url_banco())
    try:
        with Session(engine) as sessao:
            linhas = args.carregar(sessao, args)
            recalculo = recalcular_regioes(sessao)
            if args.gravar:
                sessao.commit()
            else:
                sessao.rollback()
    finally:
        engine.dispose()

    cores = ", ".join(f"{cor}: {total}" for cor, total in sorted(recalculo.por_cor.items())) or "nenhuma"
    print("\n".join([*linhas, f"Distritos recalculados: {recalculo.distritos} ({cores})"]))
    if args.gravar:
        print("Gravado.")
    else:
        print("Nada foi gravado. Para gravar, rode de novo com --gravar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
