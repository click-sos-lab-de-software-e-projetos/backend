LIMITE_MENSAGEM_SOS = 255
# Regra 02: usada quando a mensagem livre do alerta vem vazia.
MENSAGEM_PADRAO_SOS = (
    "Olá, por favor, com urgência, verifique se está tudo bem comigo. "
    "Minha localização é a informada acima."
)
NOME_VARIAVEL_SEGREDO_JWT = "JWT_SECRET_KEY"
NOME_VARIAVEL_URL_BANCO = "DATABASE_URL"
LIMITE_CONTATOS_ATIVOS = 3
LIMITE_NOME_CONTATO = 100
# E.164: "+", código de país sem zero à esquerda e de 8 a 15 dígitos no total.
# Mesmo padrão do CHECK ck_contatos_telefone_e164 da migração 0003.
PADRAO_TELEFONE_E164 = r"^\+[1-9][0-9]{7,14}$"
