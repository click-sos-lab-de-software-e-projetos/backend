"""Interface do serviço de alertas (implementação real no SOS-03)."""

from typing import Protocol
from uuid import UUID

from app.schemas.sos import AlertaCriadoResposta, CriarAlertaRequisicao


class ServicoAlertas(Protocol):
    def criar_alerta(
        self, usuario_id: UUID, dados: CriarAlertaRequisicao
    ) -> AlertaCriadoResposta: ...