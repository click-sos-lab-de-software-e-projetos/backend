"""Recalcula score, cor e raio dos distritos do mapa de risco (MAP-05).

Sem argumentos, só calcula e mostra o resumo, sem gravar nada. Confira a
janela de datas e as cores; se fizerem sentido, rode de novo com --gravar.

    python scripts/recalcular_mapa.py
    python scripts/recalcular_mapa.py --gravar

Lê DATABASE_URL do ambiente. Para o Neon, baixe o .env com
./scripts/fetch-env.sh antes. A URL do banco nunca é impressa.
"""

import argparse
import sys

from sqlalchemy.orm import Session

from app.db.config import obter_url_banco
from app.db.sessao import criar_engine
from app.services.mapa import ResumoRecalculo, recalcular_regioes


def formatar_resumo(resumo: ResumoRecalculo) -> str:
    if resumo.fim_janela is None:
        janela = "nenhuma ocorrência com data: todos os distritos ficam com score 0"
    else:
        janela = f"{resumo.inicio_janela.isoformat()} a {resumo.fim_janela.isoformat()}"
    cores = ", ".join(f"{cor}: {total}" for cor, total in sorted(resumo.por_cor.items())) or "nenhuma"
    return f"Janela das ocorrências: {janela}\nDistritos: {resumo.distritos}\nPor cor: {cores}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gravar", action="store_true", help="regrava os distritos no banco")
    args = parser.parse_args(argv)

    engine = criar_engine(obter_url_banco())
    try:
        with Session(engine) as sessao:
            resumo = recalcular_regioes(sessao)
            if args.gravar:
                sessao.commit()
            else:
                sessao.rollback()
    finally:
        engine.dispose()

    print(formatar_resumo(resumo))
    if args.gravar:
        print("Distritos regravados.")
    else:
        print("Nada foi gravado. Para gravar, rode de novo com --gravar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
