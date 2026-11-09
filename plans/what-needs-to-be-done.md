# Plano — o que falta no backend e no frontend

**Situação em 09/11/2026**

Cada tarefa abaixo traz o lado **backend** (este repositório) e o lado
**frontend** (app Flutter em `../frontend`). Os IDs entre parênteses remetem a
[`docs/index.html`](../docs/index.html) (backend) e
[`docs/mobile-epic.html`](../docs/mobile-epic.html) (mobile).

## Já entregue

| Área | Backend | Frontend |
|------|---------|----------|
| Conta | AUTH-01: cadastro, login, JWT de 24 h, `GET /auth/me`, CORS opcional | Login, tela de cadastro, sessão em memória, logout ao receber 401 |
| Contatos | CONT-01: CRUD em `/contatos`, até 3 ativos, telefone E.164 | Listar, adicionar, ativar e desativar contatos; mostra o status de consentimento; o telefone digitado é convertido para E.164 |
| S.O.S | SOS-01 a SOS-04: contrato, migrações, `POST /sos/alertas` grava o alerta como `PENDENTE`, montagem da mensagem | Segurar o botão por 3 s envia latitude, longitude e mensagem; mostra a mensagem de erro da API; WhatsApp manual por `wa.me` |
| Em aberto | SOS-05 (cliente Evolution API) está no PR #9 | — |

---

## Tarefa 1 — Registrar o consentimento dos contatos (CONT-01 · Regra 03 · SOSM-02)

> **Bloqueia o S.O.S de verdade:** sem consentimento, `POST /sos/alertas` responde 422 para todo mundo.

**Decisão pendente (Yume):** como registrar o consentimento enquanto não existe a página web.

**Opção sugerida:** link com token de uso único que o contato abre e confirma.

**Backend**
- [ ] Migração com um token de consentimento por contato:
  - guardar só o hash do token;
  - prazo de expiração.
- [ ] Rotas novas:
  - `POST /api/v1/contatos/{id}/consentimento/link`, autenticada, gera ou renova o link;
  - `POST /api/v1/consentimento/{token}`, pública, grava `consentido_em`.
- [ ] Quando o telefone de um contato mudar no `PATCH`, apagar o `consentido_em` dele.
- [ ] Testes:
  - token expirado ou reutilizado;
  - contato de outra pessoa retorna 404;
  - telefone e token não aparecem em logs.

**Frontend**
- [ ] Botão "Enviar pedido de consentimento", que abre o WhatsApp com o link para o contato.
- [ ] Atualizar o status do contato ao voltar para a tela.
- [ ] Explicar que o contato só recebe alertas depois de consentir (Regra 03).

## Tarefa 2 — Envio por WhatsApp em segundo plano (SOS-05 a SOS-08 · Regra 04)

**Decisões pendentes:**
- YUME-04: ambiente e credenciais da Evolution API.
- Quais ambientes podem usar o chip de demonstração.

**Backend**
- [ ] Revisar e fazer merge do PR #9 (SOS-05).
- [ ] SOS-06: worker que, depois do commit da transação, envia para cada contato ativo com consentimento e grava uma linha em `tentativas_envio_sos`.
- [ ] SOS-07: até 5 tentativas, com esperas de 5, 10, 15, 20 e 25 s. Depois da 5ª falha, o alerta vira `ERRO`; com sucesso, vira `ENVIADO`.
- [ ] SOS-08:
  - logs estruturados identificados pelo UUID do alerta;
  - teste ponta a ponta com a Evolution API falsa.

**Frontend**
- [ ] Nada a mudar no envio: o app já cria o alerta.
- [ ] Depende da Tarefa 3 para mostrar o resultado do envio.

## Tarefa 3 — Consultar o status do alerta (Regra 04 · SOSM-05)

**Backend**
- [ ] Criar `GET /api/v1/sos/alertas/{id}`, autenticada.
  - Devolve `status_envio`, `tentativas` e `criado_em`.
  - Alerta de outra pessoa retorna 404.
  - Não devolve coordenadas nem telefones.
- [ ] Opcional: `GET /api/v1/sos/alertas` com os últimos alertas da pessoa.

**Frontend**
- [ ] Ler o `id` da resposta do `POST /sos/alertas`. Hoje o `AlertRepository.send` descarta a resposta.
- [ ] Consultar o status do alerta a cada poucos segundos, até `ENVIADO` ou `ERRO`.
- [ ] Mostrar o estado `PENDENTE`, `ENVIADO` ou `ERRO`.
- [ ] Oferecer o `wa.me` só como alternativa explícita (SOSM-05).

## Tarefa 4 — Fluxo S.O.S no app (SOSM-03 · SOSM-04 · Regra 02)

**Backend**
- [ ] Nada novo. Só confirmar que a mensagem padrão da Regra 02 é usada quando `mensagem` vem vazia.

**Frontend**
- [ ] Antes de pedir a localização no fluxo S.O.S:
  - explicar por que ela é necessária;
  - tratar permissão negada e GPS desligado com mensagens claras.
- [ ] Depois de segurar o botão:
  - abrir um diálogo de confirmação;
  - incluir um campo de mensagem livre de até **255** caracteres. Hoje o limite em Ajustes é 160 e o texto é fixo.
- [ ] Enviar `mensagem` vazia quando a pessoa não escrever nada, para o backend usar a mensagem padrão. Hoje o app sempre envia o texto de Ajustes.
- [ ] Mostrar o aviso de privacidade aprovado antes do primeiro envio.

## Tarefa 5 — Mapa de risco (MAP-01 a MAP-03 · MAP-05 a MAP-08 · MAPM-01 a MAPM-03)

**Decisões pendentes:**
- YUME-05: planilha de São Paulo e regra do raio.
- Fórmula do score e faixas de cor.
- Raio padrão e máximo, e limite de regiões por resposta.

**Backend**
- [ ] MAP-01: contrato e validador da planilha, com um exemplo sem dados sensíveis.
- [ ] MAP-02: migração `regioes_seguranca` (MultiPolygon 4326, centroide, índice GiST).
- [ ] MAP-03: importação idempotente (upsert) com relatório de linhas importadas, atualizadas e rejeitadas.
- [ ] MAP-05: função pura que calcula score, cor e raio. Feedback comunitário tem peso zero.
- [ ] MAP-06 e MAP-07: `GET /api/v1/mapa/regioes?latitude&longitude&raio`, com schema público que devolve só ID público, nome, centroide, score, cor e raio.
- [ ] MAP-08: teste de integração com PostGIS real.

**Frontend**
- [ ] Trocar `HttpOccurrenceRepository` (`/occurrences`, rota que não existe) por um repositório de `/mapa/regioes`.
- [ ] Desenhar círculos com o centroide, o raio e a cor que vêm da API, no lugar do mapa de calor falso.
- [ ] Tratar carregamento, lista vazia e falha.
- [ ] O mapa precisa funcionar sem permissão de localização (MAPM-03).
- [ ] MAPM-01: a chave do Maps já vem de configuração local. Conferir as restrições da chave no Google Cloud.

## Tarefa 6 — Feedback comunitário (MAP-04 · MAPM-04 · Regra 05)

**Decisão pendente:** categorias aceitas, tamanho máximo do texto e se fotos são permitidas.

**Backend**
- [ ] Migração `feedbacks_comunidade`, com FKs para `usuarios` e `regioes_seguranca`.
- [ ] `POST /api/v1/mapa/regioes/{id}/feedbacks`, autenticada, sempre com status `PENDENTE`.
- [ ] Testes provando que o feedback não altera o score nem aparece em `/mapa/regioes`.

**Frontend**
- [ ] Transformar a tela "Registro de ocorrência" em feedback vinculado a uma região selecionada no mapa.
- [ ] Avisar que o feedback fica pendente e não muda o mapa.
- [ ] Não alterar localmente o score nem a cor da região.

## Tarefa 7 — Perfil editável

**Backend**
- [ ] `PATCH /api/v1/auth/me` com `nome_completo` e `telefone_pessoal`.
- [ ] Opcional: troca de senha, exigindo a senha atual.

**Frontend**
- [ ] Hoje `EditProfileScreen` só altera o estado local. Passar a chamar a API.
- [ ] Desabilitar a edição do e-mail ou criar um fluxo próprio para ele.

## Tarefa 8 — Edição e remoção de contatos

**Backend**
- [ ] Nada novo: `PATCH` e `DELETE /contatos/{id}` já existem.

**Frontend**
- [ ] `ContactsController.remove` existe, mas não há botão na interface. Adicionar editar e remover, com confirmação.
- [ ] Ao editar o telefone, avisar que o consentimento será pedido de novo (Tarefa 1).

## Tarefa 9 — Sessão segura (Regra 09 · SOSM-01)

**Backend**
- [ ] Nada no MVP: não há refresh token.
- [ ] Rever a decisão se o login a cada abertura do app incomodar.

**Frontend**
- [ ] Hoje o token fica só em memória, como decidido para este MVP.
- [ ] A Regra 09 pede guardar o token com segurança. Avaliar `flutter_secure_storage` e restaurar a sessão com `GET /auth/me` ao abrir o app.

## Tarefa 10 — Retenção e privacidade (Regra 08 · YUME-03)

**Decisão pendente:** prazo de retenção de alertas e localização, e quem pode acessar esses dados.

**Backend**
- [ ] Rotina de exclusão ou anonimização de `alertas_sos` e `tentativas_envio_sos` vencidos.
- [ ] Opcional: `DELETE /api/v1/auth/me` para excluir a conta (LGPD).

**Frontend**
- [ ] Tela de privacidade com a política de retenção.
- [ ] Consentimento LGPD antes do primeiro uso da localização.
- [ ] Botão para excluir a conta, se a rota existir.

## Tarefa 11 — Qualidade, CI e documentação

**Backend**
- [ ] Criar um workflow de CI: lint e `pytest` com um serviço PostGIS, para que os testes de integração rodem.
- [ ] Atualizar `docs/index.html` com o status de cada ticket, incluindo `/me` e CORS.
- [ ] Definir onde a API será publicada (deploy) e qual `API_BASE_URL` o app vai usar.

**Frontend**
- [ ] A pasta legada `lib/screens/` quebra `dart format` e `flutter analyze`, então o CI está vermelho. Remover a pasta ou corrigi-la.
- [ ] `docs/mobile-epic.html` descreve Kotlin, Compose e Retrofit, mas o app é Flutter. Atualizar o épico.
- [ ] SOSM-06 e MAPM-05:
  - acessibilidade: contraste, área de toque, leitor de tela;
  - teste de integração do fluxo S.O.S e do mapa com backend falso.
- [ ] Definir o nome oficial do app e o `applicationId`.

---

## Ordem sugerida

1. **Tarefas 1 e 11:** destravam o S.O.S real e deixam o CI verde nos dois repositórios.
2. **Tarefas 2 e 3:** envio por WhatsApp e status do alerta, para o fluxo de emergência completo.
3. **Tarefas 4 e 8:** acabamento do fluxo S.O.S e dos contatos no app.
4. **Tarefa 5, depois a 6:** mapa de risco, que depende da planilha (YUME-05).
5. **Tarefas 7, 9 e 10:** perfil, sessão persistente e privacidade, antes de qualquer uso fora da equipe.

## Decisões que travam o trabalho (Yume)

| Decisão | Trava |
|---------|-------|
| Como registrar o consentimento sem página web | Tarefa 1 |
| Evolution API: ambiente e credenciais (YUME-04) | Tarefa 2 |
| Planilha de SP, regra do raio e fórmula do score (YUME-05) | Tarefa 5 |
| Categorias e limites do feedback | Tarefa 6 |
| Retenção de localização (YUME-03) | Tarefa 10 |
