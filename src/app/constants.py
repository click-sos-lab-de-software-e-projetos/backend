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
# Regex das origens liberadas no CORS; vazio desliga o CORS.
NOME_VARIAVEL_CORS = "CORS_ORIGIN_REGEX"
LIMITE_CONTATOS_ATIVOS = 3
LIMITE_NOME_CONTATO = 100
# E.164: "+", código de país sem zero à esquerda e de 8 a 15 dígitos no total.
# Mesmo padrão do CHECK ck_contatos_telefone_e164 da migração 0003.
PADRAO_TELEFONE_E164 = r"^\+[1-9][0-9]{7,14}$"
# Endereço da página pública de consentimento (repositório tela-consentimento).
NOME_VARIAVEL_URL_CONSENTIMENTO = "CONSENTIMENTO_URL_BASE"
VALIDADE_LINK_CONSENTIMENTO_DIAS = 7
NOME_VARIAVEL_EVOLUTION_URL = "EVOLUTION_API_URL"
NOME_VARIAVEL_EVOLUTION_CHAVE = "EVOLUTION_API_KEY"
NOME_VARIAVEL_EVOLUTION_INSTANCIA = "EVOLUTION_INSTANCE"
# Timeout conta como falha temporária, mas a mensagem pode ter chegado; um
# valor curto aumenta o risco de o contato receber o alerta duplicado.
TIMEOUT_ENVIO_WHATSAPP_S = 10
# Regra 04: no máximo 5 tentativas. A 1ª é imediata, então só cabem 4 esperas
# (5, 10, 15 e 20 s); o 25 da regra nunca é usado.
MAXIMO_TENTATIVAS_ENVIO = 5
ESPERAS_RETENTATIVA_S = (5, 10, 15, 20)
# Mapa de risco (MAP-05): score de 0 a 100 em 3 faixas.
COR_VERDE = "#22C55E"
COR_AMARELA = "#EAB308"
COR_VERMELHA = "#EF4444"
SCORE_MINIMO_AMARELO = 34
SCORE_MINIMO_VERMELHO = 67
# Janela contada a partir da ocorrência mais recente no banco, não de hoje:
# a carga da SSP é esporádica e o mapa não pode esvaziar entre cargas.
JANELA_SCORE_MESES = 6
# Consulta do mapa (MAP-06/07).
RAIO_PADRAO_MAPA_M = 3000
RAIO_MAXIMO_MAPA_M = 10000
LIMITE_REGIOES_MAPA = 50
# Alertas da comunidade no mapa (estilo Waze). Não entram no score (Regra 05).
CATEGORIAS_ALERTA_COMUNIDADE = ("ILUMINACAO", "ASSALTO", "ASSEDIO", "MOVIMENTO", "POLICIAMENTO", "OUTRO")
LIMITE_TEXTO_ALERTA_COMUNIDADE = 500
VALIDADE_ALERTA_COMUNIDADE_HORAS = 24
LIMITE_ALERTAS_COMUNIDADE_MAPA = 200
# Retenção dos alertas (Regra 08, YUME-03): depois disso, o alerta é anonimizado.
RETENCAO_ALERTAS_DIAS = 180
