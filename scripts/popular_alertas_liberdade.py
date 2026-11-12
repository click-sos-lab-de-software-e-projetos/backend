"""Popula o distrito da Liberdade com alertas da comunidade de demonstração.

Sorteia pontos dentro dos limites do distrito e cria alertas de categorias
variadas, com idades espalhadas nas últimas horas para que todos ainda
apareçam no mapa (eles valem 24 horas). Os alertas ficam numa conta fixa de
demonstração, sem senha, que ninguém consegue usar para entrar.

Sem argumentos, só simula e mostra o resumo, sem gravar nada.

    python scripts/popular_alertas_liberdade.py
    python scripts/popular_alertas_liberdade.py --gravar
    python scripts/popular_alertas_liberdade.py --quantidade 30 --limpar --gravar

--limpar apaga antes os alertas anteriores da conta de demonstração. Lê
DATABASE_URL do ambiente (por exemplo, dentro de scripts/run.sh shell dev).
A URL do banco nunca é impressa.
"""

import argparse
import random
import sys
from collections import Counter
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.constants import VALIDADE_ALERTA_COMUNIDADE_HORAS
from app.db.config import obter_url_banco
from app.db.sessao import criar_engine

EMAIL_DEMO = "alertas-demo@clicksos.invalid"

# Ruas e pontos conhecidos do bairro, só para os textos soarem reais.
LUGARES = [
    "na Praça da Liberdade",
    "na Rua Galvão Bueno",
    "na saída da estação Japão-Liberdade",
    "na Rua dos Estudantes",
    "na Rua da Glória",
    "na Rua Tomás Gonzaga",
    "na Rua Conde de Sarzedas",
    "na Avenida da Liberdade",
    "perto da Rua Américo de Campos",
]

TEXTOS = {
    "ILUMINACAO": ["Poste apagado {lugar}.", "Trecho bem escuro {lugar} à noite.", None],
    "ASSALTO": ["Celular roubado {lugar}.", "Dois caras de moto abordando pedestres {lugar}.", None],
    "ASSEDIO": ["Homem seguindo mulheres {lugar}.", "Assédio verbal {lugar}, cuidado.", None],
    "MOVIMENTO": ["Rua vazia {lugar} depois que as lojas fecham.", None],
    "POLICIAMENTO": ["Nenhuma viatura {lugar} a noite toda.", None],
    "OUTRO": ["Calçada quebrada {lugar}, fácil de tropeçar.", "Briga {lugar}, melhor desviar."],
}

_DISTRITO = text("SELECT id FROM regioes_seguranca WHERE lower(nome) = lower(:nome) LIMIT 1")

# A semente deixa os pontos iguais entre execuções com a mesma --semente.
_PONTOS = text(
    "SELECT ST_Y(p.geom) AS latitude, ST_X(p.geom) AS longitude "
    "FROM regioes_seguranca r, ST_Dump(ST_GeneratePoints(r.limites, :quantidade, :semente)) AS p "
    "WHERE r.id = :id ORDER BY p.path"
)

_CONTA_DEMO = text(
    "INSERT INTO usuarios (nome_completo, email, senha_hash, telefone_pessoal) "
    "VALUES ('Alertas de Demonstração', :email, 'sem-login', '+5500900000000') "
    "ON CONFLICT ((lower(email))) DO UPDATE SET nome_completo = EXCLUDED.nome_completo "
    "RETURNING id"
)

_LIMPAR = text("DELETE FROM alertas_comunidade WHERE usuario_id = :usuario_id")

_INSERIR = text(
    "INSERT INTO alertas_comunidade (usuario_id, categoria, texto, localizacao, criado_em) "
    "VALUES (:usuario_id, :categoria, :texto, ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326), "
    "now() - make_interval(mins => :minutos))"
)


def montar_alertas(pontos: list[tuple[float, float]], sorteio: random.Random) -> list[dict]:
    """Um alerta por ponto (latitude, longitude), com categoria, texto e idade sorteados."""
    # Uma hora de folga para o alerta ainda estar no mapa quando o app abrir.
    idade_maxima = (VALIDADE_ALERTA_COMUNIDADE_HORAS - 1) * 60
    alertas = []
    for latitude, longitude in pontos:
        categoria = sorteio.choice(list(TEXTOS))
        modelo = sorteio.choice(TEXTOS[categoria])
        alertas.append(
            {
                "categoria": categoria,
                "texto": modelo.format(lugar=sorteio.choice(LUGARES)) if modelo else None,
                "latitude": latitude,
                "longitude": longitude,
                "minutos": sorteio.randint(1, idade_maxima),
            }
        )
    return alertas


def popular(conexao: Connection, distrito: str, quantidade: int, semente: int, limpar: bool) -> list[dict] | None:
    """Cria os alertas no distrito; None se ele não existir. Não faz commit."""
    regiao = conexao.execute(_DISTRITO, {"nome": distrito}).scalar_one_or_none()
    if regiao is None:
        return None
    usuario_id: UUID = conexao.execute(_CONTA_DEMO, {"email": EMAIL_DEMO}).scalar_one()
    if limpar:
        conexao.execute(_LIMPAR, {"usuario_id": usuario_id})
    pontos = conexao.execute(_PONTOS, {"id": regiao, "quantidade": quantidade, "semente": semente}).all()
    alertas = montar_alertas([(p.latitude, p.longitude) for p in pontos], random.Random(semente))
    if alertas:
        conexao.execute(_INSERIR, [{**a, "usuario_id": usuario_id} for a in alertas])
    return alertas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--distrito", default="Liberdade", help="nome do distrito (padrão: Liberdade)")
    parser.add_argument("--quantidade", type=int, default=20, help="padrão: 20")
    parser.add_argument("--semente", type=int, default=42, help="mesma semente, mesmos pontos (padrão: 42)")
    parser.add_argument("--limpar", action="store_true", help="apaga antes os alertas da conta de demonstração")
    parser.add_argument("--gravar", action="store_true", help="grava no banco")
    args = parser.parse_args(argv)
    if args.quantidade < 1:
        parser.error("--quantidade precisa ser pelo menos 1")

    engine = criar_engine(obter_url_banco())
    try:
        with engine.connect() as conexao:
            alertas = popular(conexao, args.distrito, args.quantidade, args.semente, args.limpar)
            if args.gravar and alertas is not None:
                conexao.commit()
            else:
                conexao.rollback()
    finally:
        engine.dispose()

    if alertas is None:
        print(f"Distrito '{args.distrito}' não encontrado. Rode scripts/carregar_mapa.py antes.", file=sys.stderr)
        return 2
    por_categoria = ", ".join(f"{c}: {n}" for c, n in sorted(Counter(a["categoria"] for a in alertas).items()))
    print(f"Alertas em {args.distrito}: {len(alertas)} ({por_categoria})")
    if args.gravar:
        print(f"Gravados. Somem do mapa {VALIDADE_ALERTA_COMUNIDADE_HORAS} horas depois de criados.")
    else:
        print("Nada foi gravado. Para gravar, rode de novo com --gravar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
