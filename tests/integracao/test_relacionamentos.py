from sqlalchemy import text

from integracao.fabricas import inserir_alerta, inserir_contato, inserir_tentativa, inserir_usuario

TABELAS = ["usuarios", "contatos_emergencia", "alertas_sos", "tentativas_envio_sos"]


def _cenario_completo(conexao):
    usuario = inserir_usuario(conexao)
    contatos = [inserir_contato(conexao, usuario.id).id for _ in range(3)]
    alerta = inserir_alerta(conexao, usuario.id)
    for contato_id in contatos:
        inserir_tentativa(conexao, alerta.id, contato_id, status="SUCESSO")
    return usuario.id, alerta.id, set(contatos)


def usuario_com_tres_contatos_e_um_alerta_deve_relacionar_tentativas_a_cada_contato(
    banco_migrado,
):
    with banco_migrado.begin() as conexao:
        usuario_id, alerta_id, contatos = _cenario_completo(conexao)
        linhas = conexao.execute(
            text(
                "SELECT c.id, c.usuario_id FROM tentativas_envio_sos t "
                "JOIN alertas_sos a ON a.id = t.alerta_id "
                "JOIN contatos_emergencia c ON c.id = t.contato_id "
                "WHERE a.id = :alerta_id"
            ),
            {"alerta_id": alerta_id},
        ).all()
    assert {contato_id for contato_id, _ in linhas} == contatos
    assert {dono for _, dono in linhas} == {usuario_id}


def remover_usuario_deve_limpar_contatos_alertas_e_tentativas_em_cascata(banco_migrado):
    with banco_migrado.begin() as conexao:
        usuario_id, _, _ = _cenario_completo(conexao)
        conexao.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario_id})
        restantes = {
            tabela: conexao.execute(text(f"SELECT count(*) FROM {tabela}")).scalar()
            for tabela in TABELAS
        }
    assert restantes == dict.fromkeys(TABELAS, 0)
