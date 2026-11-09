from uuid import uuid4

import jwt

from app.core.security import (
    emitir_token,
    extrair_usuario_id,
    gerar_hash_senha,
    verificar_senha,
)

SEGREDO = "segredo-apenas-para-testes-com-32-bytes"


def gerar_hash_senha_deve_usar_bcrypt_sem_guardar_a_senha_em_texto():
    senha_hash = gerar_hash_senha("senha-ficticia")
    assert senha_hash.startswith("$2b$")
    assert "senha-ficticia" not in senha_hash


def verificar_senha_deve_aceitar_a_senha_certa_e_recusar_a_errada():
    senha_hash = gerar_hash_senha("senha-ficticia")
    assert verificar_senha("senha-ficticia", senha_hash)
    assert not verificar_senha("senha-errada", senha_hash)


def verificar_senha_com_hash_que_nao_e_bcrypt_deve_recusar():
    assert not verificar_senha("senha-ficticia", "hash-ficticio")


def emitir_token_deve_ser_aceito_pela_autenticacao_das_rotas_privadas():
    usuario_id = uuid4()
    assert extrair_usuario_id(emitir_token(usuario_id, SEGREDO, 60), SEGREDO) == usuario_id


def emitir_token_deve_usar_hs256_com_sub_e_exp_da_validade_pedida():
    usuario_id = uuid4()
    token = emitir_token(usuario_id, SEGREDO, validade_min=30, agora=1_000)
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload == {"sub": str(usuario_id), "iat": 1_000, "exp": 1_000 + 30 * 60}
