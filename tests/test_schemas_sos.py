from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.constants import LIMITE_MENSAGEM_SOS
from app.schemas.sos import AlertaCriadoResposta, CriarAlertaRequisicao

CORPO_VALIDO = {"latitude": -23.55, "longitude": -46.63}


def requisicao_alerta_sem_mensagem_deve_ser_aceita():
    assert CriarAlertaRequisicao.model_validate(CORPO_VALIDO).mensagem is None


def requisicao_alerta_com_mensagem_no_limite_deve_ser_aceita():
    corpo = {**CORPO_VALIDO, "mensagem": "a" * LIMITE_MENSAGEM_SOS}
    assert len(CriarAlertaRequisicao.model_validate(corpo).mensagem) == LIMITE_MENSAGEM_SOS


def requisicao_alerta_com_mensagem_acima_do_limite_deve_ser_rejeitada():
    corpo = {**CORPO_VALIDO, "mensagem": "a" * (LIMITE_MENSAGEM_SOS + 1)}
    with pytest.raises(ValidationError):
        CriarAlertaRequisicao.model_validate(corpo)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("latitude", 90.1), ("latitude", -90.1), ("longitude", 180.1), ("longitude", -180.1)],
)
def requisicao_alerta_com_coordenada_fora_do_intervalo_deve_ser_rejeitada(campo, valor):
    with pytest.raises(ValidationError):
        CriarAlertaRequisicao.model_validate({**CORPO_VALIDO, campo: valor})


@pytest.mark.parametrize("campo", ["latitude", "longitude"])
def requisicao_alerta_sem_coordenada_deve_ser_rejeitada(campo):
    corpo = {k: v for k, v in CORPO_VALIDO.items() if k != campo}
    with pytest.raises(ValidationError):
        CriarAlertaRequisicao.model_validate(corpo)


def requisicao_alerta_com_usuario_id_no_corpo_deve_ser_rejeitada():
    with pytest.raises(ValidationError):
        CriarAlertaRequisicao.model_validate({**CORPO_VALIDO, "usuario_id": str(uuid4())})


def requisicao_alerta_no_json_schema_deve_documentar_limite_da_mensagem():
    mensagem = CriarAlertaRequisicao.model_json_schema()["properties"]["mensagem"]
    assert any(opcao.get("maxLength") == LIMITE_MENSAGEM_SOS for opcao in mensagem["anyOf"])


def resposta_alerta_criado_nao_deve_conter_coordenadas():
    campos = set(AlertaCriadoResposta.model_fields)
    assert campos == {"id", "status_envio", "criado_em"}
