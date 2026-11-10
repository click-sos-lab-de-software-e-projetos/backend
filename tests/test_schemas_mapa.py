import pytest
from pydantic import ValidationError

from app.constants import CATEGORIAS_FEEDBACK, LIMITE_TEXTO_FEEDBACK
from app.schemas.mapa import CriarFeedbackRequisicao, FeedbackCriadoResposta


@pytest.mark.parametrize("categoria", CATEGORIAS_FEEDBACK)
def requisicao_feedback_deve_aceitar_cada_categoria_com_texto(categoria):
    feedback = CriarFeedbackRequisicao.model_validate({"categoria": categoria, "texto": "rua escura"})
    assert feedback.categoria == categoria


def requisicao_feedback_sem_texto_deve_ser_aceita():
    assert CriarFeedbackRequisicao.model_validate({"categoria": "ASSALTO"}).texto is None


def requisicao_feedback_com_texto_em_branco_deve_virar_nulo():
    assert CriarFeedbackRequisicao.model_validate({"categoria": "ASSALTO", "texto": "   "}).texto is None


def requisicao_feedback_com_texto_no_limite_deve_ser_aceita():
    corpo = {"categoria": "ASSALTO", "texto": "a" * LIMITE_TEXTO_FEEDBACK}
    assert len(CriarFeedbackRequisicao.model_validate(corpo).texto) == LIMITE_TEXTO_FEEDBACK


@pytest.mark.parametrize(
    "corpo",
    [
        {"categoria": "BARULHO"},
        {"categoria": "assalto"},
        {},
        {"categoria": "ASSALTO", "texto": "a" * (LIMITE_TEXTO_FEEDBACK + 1)},
        {"categoria": "ASSALTO", "usuario_id": "x"},
        {"categoria": "OUTRO"},
        {"categoria": "OUTRO", "texto": "   "},
    ],
    ids=["desconhecida", "minuscula", "sem-categoria", "texto-longo", "campo-extra", "outro-sem-texto", "outro-branco"],
)
def requisicao_feedback_invalida_deve_ser_rejeitada(corpo):
    with pytest.raises(ValidationError):
        CriarFeedbackRequisicao.model_validate(corpo)


def resposta_feedback_criado_nao_deve_conter_texto_nem_usuario():
    assert set(FeedbackCriadoResposta.model_fields) == {"id", "regiao_id", "categoria", "status", "criado_em"}
