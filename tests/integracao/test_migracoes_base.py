from sqlalchemy import text


def upgrade_head_deve_habilitar_extensao_postgis(banco_migrado):
    with banco_migrado.connect() as conexao:
        extensao = conexao.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'postgis'")
        ).scalar()
    assert extensao == 1
