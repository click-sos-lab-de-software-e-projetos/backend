"""Anonimiza os alertas com mais de 180 dias (Regra 08, YUME-03).

Sem argumentos, só conta o que seria anonimizado, sem gravar nada. Rodar de
novo não muda os alertas já anonimizados.

    python scripts/anonimizar_alertas.py
    python scripts/anonimizar_alertas.py --gravar

Lê DATABASE_URL do ambiente. Para o Neon, baixe o .env com
./scripts/fetch-env.sh antes. A URL do banco nunca é impressa.
"""

import argparse
import sys
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.constants import RETENCAO_ALERTAS_DIAS
from app.db.config import obter_url_banco
from app.db.sessao import criar_engine
from app.services.retencao import anonimizar_alertas_vencidos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gravar", action="store_true", help="grava a anonimização no banco")
    args = parser.parse_args(argv)

    engine = criar_engine(obter_url_banco())
    try:
        with Session(engine) as sessao:
            resumo = anonimizar_alertas_vencidos(sessao, datetime.now(UTC))
            if args.gravar:
                sessao.commit()
            else:
                sessao.rollback()
    finally:
        engine.dispose()

    print(f"Alertas com mais de {RETENCAO_ALERTAS_DIAS} dias")
    print(f"Alertas: {resumo.alertas}\nTentativas desvinculadas dos contatos: {resumo.tentativas}")
    if args.gravar:
        print("Alertas anonimizados.")
    else:
        print("Nada foi gravado. Para gravar, rode de novo com --gravar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
