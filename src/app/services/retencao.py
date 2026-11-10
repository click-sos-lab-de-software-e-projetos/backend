"""Retenção dos alertas (Regra 08, YUME-03).

Anonimizar um alerta apaga as coordenadas, a mensagem e o vínculo das
tentativas com os contatos; status, tentativas e datas ficam para estatística.
Alertas já anonimizados não são tocados de novo.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import RETENCAO_ALERTAS_DIAS


@dataclass(frozen=True)
class ResumoAnonimizacao:
    alertas: int
    tentativas: int


def _anonimizar(filtro: str):
    return text(
        "WITH alvo AS ("
        "  UPDATE alertas_sos SET localizacao = NULL, mensagem = NULL, anonimizado_em = :agora"
        f"  WHERE anonimizado_em IS NULL AND {filtro} RETURNING id"
        "), tentativas AS ("
        "  UPDATE tentativas_envio_sos t SET contato_id = NULL FROM alvo"
        "  WHERE t.alerta_id = alvo.id AND t.contato_id IS NOT NULL RETURNING t.id"
        ") SELECT (SELECT count(*) FROM alvo) AS alertas, (SELECT count(*) FROM tentativas) AS tentativas"
    )


_VENCIDOS = _anonimizar("criado_em < :limite")
_DA_PESSOA = _anonimizar("usuario_id = :usuario_id")


def anonimizar_alertas_vencidos(sessao: Session, agora: datetime) -> ResumoAnonimizacao:
    """Alertas com mais de RETENCAO_ALERTAS_DIAS. Não faz commit."""
    limite = agora - timedelta(days=RETENCAO_ALERTAS_DIAS)
    linha = sessao.execute(_VENCIDOS, {"agora": agora, "limite": limite}).one()
    return ResumoAnonimizacao(alertas=linha.alertas, tentativas=linha.tentativas)


def anonimizar_alertas_da_pessoa(sessao: Session, usuario_id: UUID, agora: datetime) -> ResumoAnonimizacao:
    """Todos os alertas da pessoa, na exclusão da conta. Não faz commit."""
    linha = sessao.execute(_DA_PESSOA, {"agora": agora, "usuario_id": usuario_id}).one()
    return ResumoAnonimizacao(alertas=linha.alertas, tentativas=linha.tentativas)
