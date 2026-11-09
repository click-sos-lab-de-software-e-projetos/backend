LIMITE_MENSAGEM_SOS = 255
# Regra 02: usada quando a mensagem livre do alerta vem vazia.
MENSAGEM_PADRAO_SOS = (
    "Olá, por favor, com urgência, verifique se está tudo bem comigo. "
    "Minha localização é a informada acima."
)
NOME_VARIAVEL_SEGREDO_JWT = "JWT_SECRET_KEY"
NOME_VARIAVEL_EXPIRACAO_JWT = "JWT_EXPIRACAO_MIN"
# Regra 09: o token vale 24 horas e não há renovação (refresh) no MVP.
EXPIRACAO_JWT_PADRAO_MIN = 24 * 60
TAMANHO_MINIMO_SENHA = 8
# O bcrypt só considera os primeiros 72 bytes; acima disso a senha é recusada.
LIMITE_BYTES_SENHA = 72
LIMITE_NOME_COMPLETO = 120
LIMITE_EMAIL = 150
NOME_VARIAVEL_URL_BANCO = "DATABASE_URL"
LIMITE_CONTATOS_ATIVOS = 3
LIMITE_NOME_CONTATO = 100
# E.164: "+", código de país sem zero à esquerda e de 8 a 15 dígitos no total.
# Mesmo padrão do CHECK ck_contatos_telefone_e164 da migração 0003.
PADRAO_TELEFONE_E164 = r"^\+[1-9][0-9]{7,14}$"
