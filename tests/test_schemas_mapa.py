import pytest
from pydantic import ValidationError

from app.constants import CATEGORIAS_ALERTA_COMUNIDADE, LIMITE_TEXTO_ALERTA_COMUNIDADE
from app.schemas.mapa import AlertaComunidadeResposta, CriarAlertaComunidadeRequisicao

PONTO = {"latitude": -23.55, "longitude": -46.63}


def _validar(**campos) -> CriarAlertaComunidadeRequisicao:
    return CriarAlertaComunidadeRequisicao.model_validate(PONTO | campos)


@pytest.mark.parametrize("categoria", CATEGORIAS_ALERTA_COMUNIDADE)
def requisicao_alerta_deve_aceitar_cada_categoria_com_texto(categoria):
    assert _validar(categoria=categoria, texto="rua escura").categoria == categoria


def requisicao_alerta_sem_texto_deve_ser_aceita():
    assert _validar(categoria="ASSALTO").texto is None


def requisicao_alerta_com_texto_em_branco_deve_virar_nulo():
    assert _validar(categoria="ASSALTO", texto="   ").texto is None


def requisicao_alerta_com_texto_no_limite_deve_ser_aceita():
    texto = "a" * LIMITE_TEXTO_ALERTA_COMUNIDADE
    assert len(_validar(categoria="ASSALTO", texto=texto).texto) == LIMITE_TEXTO_ALERTA_COMUNIDADE


@pytest.mark.parametrize(
    "corpo",
    [
        PONTO | {"categoria": "BARULHO"},
        PONTO | {"categoria": "assalto"},
        PONTO,
        PONTO | {"categoria": "ASSALTO", "texto": "a" * (LIMITE_TEXTO_ALERTA_COMUNIDADE + 1)},
        PONTO | {"categoria": "ASSALTO", "usuario_id": "x"},
        PONTO | {"categoria": "OUTRO"},
        PONTO | {"categoria": "OUTRO", "texto": "   "},
        {"categoria": "ASSALTO", "latitude": -23.55},
        {"categoria": "ASSALTO", "latitude": 91, "longitude": 0},
        {"categoria": "ASSALTO", "latitude": 0, "longitude": -181},
    ],
    ids=[
        "desconhecida",
        "minuscula",
        "sem-categoria",
        "texto-longo",
        "campo-extra",
        "outro-sem-texto",
        "outro-branco",
        "sem-longitude",
        "latitude-fora",
        "longitude-fora",
    ],
)
def requisicao_alerta_invalida_deve_ser_rejeitada(corpo):
    with pytest.raises(ValidationError):
        CriarAlertaComunidadeRequisicao.model_validate(corpo)


def resposta_alerta_nao_deve_dizer_quem_criou():
    assert set(AlertaComunidadeResposta.model_fields) == {
        "id",
        "categoria",
        "texto",
        "latitude",
        "longitude",
        "criado_em",
    }
