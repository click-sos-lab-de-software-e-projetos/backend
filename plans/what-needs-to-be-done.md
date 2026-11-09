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

**Decidido (09/11):** link com token de uso único, que o contato abre e confirma. A página web completa fica para depois.

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

**Decidido (09/11, YUME-04):**
- Por enquanto o envio usa o número pessoal da Yume, conectado na hora da implementação.
- O envio real pode acontecer em dev local e na demonstração. Os testes automatizados usam sempre a API falsa.
- Credenciais só no `.env` local ou no `.env` do Neon, nunca no Git.

### Como subir a Evolution API (v2)

O cliente do PR #9 chama `POST {EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}` com o header `apikey` e o corpo `{"number": "5511...", "text": "..."}`. Esse é o contrato da Evolution API v2.

1. **Subir o servidor localmente** com Podman. A v2 precisa de um Postgres próprio; use um banco separado, nunca o Neon nem o banco de testes.
   ```bash
   podman network create evolution
   podman run -d --name evolution-db --network evolution \
     -e POSTGRES_USER=evolution -e POSTGRES_PASSWORD=evolution -e POSTGRES_DB=evolution \
     postgres:16
   podman run -d --name evolution-api --network evolution -p 8080:8080 \
     -e AUTHENTICATION_API_KEY=<gere-uma-chave-longa> \
     -e DATABASE_PROVIDER=postgresql \
     -e DATABASE_CONNECTION_URI=postgresql://evolution:evolution@evolution-db:5432/evolution \
     -e CACHE_REDIS_ENABLED=false -e CACHE_LOCAL_ENABLED=true \
     evoapicloud/evolution-api:latest
   ```
   Fixe uma tag de versão v2 em vez de `latest` quando a integração estiver estável.
2. **Criar a instância:**
   ```bash
   curl -X POST http://localhost:8080/instance/create \
     -H "apikey: <chave>" -H "Content-Type: application/json" \
     -d '{"instanceName": "click-sos-dev", "integration": "WHATSAPP-BAILEYS", "qrcode": true}'
   ```
3. **Conectar o número:** abra `GET /instance/connect/click-sos-dev` (ou o painel em `http://localhost:8080/manager`) e leia o QR code no WhatsApp do celular em *Aparelhos conectados*.
4. **Configurar o backend** no `.env`:
   ```
   EVOLUTION_API_URL=http://localhost:8080
   EVOLUTION_API_KEY=<chave>
   EVOLUTION_INSTANCE=click-sos-dev
   ```
5. **Testar à mão** enviando para o seu próprio número antes de ligar o worker:
   ```bash
   curl -X POST http://localhost:8080/message/sendText/click-sos-dev \
     -H "apikey: <chave>" -H "Content-Type: application/json" \
     -d '{"number": "5511999999999", "text": "Teste Click S.O.S"}'
   ```

**Cuidados com o número pessoal**
- O WhatsApp pode banir números que enviam muitas mensagens automáticas. Envie só para contatos que consentiram e evite rajadas nos testes.
- Desconecte a instância (`DELETE /instance/logout/click-sos-dev`) quando não estiver usando.
- Para a demonstração, avaliar um chip dedicado no lugar do número pessoal.
- Para a demo fora do seu computador, a Evolution API precisa ficar num servidor acessível pelo backend (VPS ou serviço de containers). Decidir junto com o deploy (Tarefa 11).

**Backend**
- [ ] Revisar e fazer merge do PR #9 (SOS-05). Ele já adiciona `EVOLUTION_INSTANCE` ao `.env.example`.
- [ ] Documentar no README o passo a passo acima, de forma resumida.
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

**Decidido (09/11):**
- **Fonte:** a planilha já foi exportada para uma tabela no banco **Neon**. Não haverá importação de Excel.
- **Região:** distrito (96 em São Paulo).
- **Score:** 0 a 100, em 3 faixas: verde abaixo de 34, amarelo de 34 a 66, vermelho a partir de 67.
- **Consulta:** raio padrão de 3 km, raio máximo de 10 km, no máximo 50 regiões por resposta.

**Ainda pendente:**
- Nome da tabela no Neon e o significado de cada coluna.
- Fonte original e licença dos dados.
- Regra do raio do círculo. Proposta: o raio de um círculo com a mesma área do distrito (`sqrt(área / π)`).

**Credenciais:** o backend não guarda a URL do Neon. O `.env` é baixado com `NEON_ENV_URL=... ./scripts/fetch-env.sh`, e `DATABASE_URL` aponta para o Neon. Os testes continuam no PostGIS descartável, nunca no Neon.

**Backend**
- [ ] MAP-01: inspecionar a tabela exportada no Neon e documentar o contrato (colunas, tipos, geometria em SRID 4326). Incluir um exemplo sem dados sensíveis nos testes.
- [ ] MAP-02: migração `regioes_seguranca` (MultiPolygon 4326, centroide, índice GiST).
- [ ] MAP-03: script idempotente (upsert pelo ID público) que lê a tabela exportada e preenche `regioes_seguranca`, com relatório de linhas importadas, atualizadas e rejeitadas. Ele substitui a importação de Excel.
- [ ] MAP-05: função pura que calcula score, cor e raio com as faixas acima. Feedback comunitário tem peso zero.
- [ ] MAP-06 e MAP-07: `GET /api/v1/mapa/regioes?latitude&longitude&raio`:
  - raio padrão de 3000 m; acima de 10000 m responde 422;
  - no máximo 50 regiões, das mais próximas para as mais distantes;
  - schema público com só ID público, nome, centroide, score, cor e raio.
- [ ] MAP-08: teste de integração com PostGIS real.

**Frontend**
- [ ] Trocar `HttpOccurrenceRepository` (`/occurrences`, rota que não existe) por um repositório de `/mapa/regioes`.
- [ ] Desenhar círculos com o centroide, o raio e a cor que vêm da API, no lugar do mapa de calor falso.
- [ ] Tratar carregamento, lista vazia e falha.
- [ ] O mapa precisa funcionar sem permissão de localização (MAPM-03).
- [ ] MAPM-01: a chave do Maps já vem de configuração local. Conferir as restrições da chave no Google Cloud.

## Tarefa 6 — Feedback comunitário (MAP-04 · MAPM-04 · Regra 05)

**Decidido (09/11):**
- Categorias: `ILUMINACAO`, `ASSALTO`, `ASSEDIO`, `MOVIMENTO` (pouco movimento), `POLICIAMENTO` (falta de policiamento), `OUTRO`.
- Texto livre de até 500 caracteres.
- Sem fotos.

**Backend**
- [ ] Migração `feedbacks_comunidade`, com FKs para `usuarios` e `regioes_seguranca`, e um `CHECK` com as categorias acima.
- [ ] `POST /api/v1/mapa/regioes/{id}/feedbacks`, autenticada, sempre com status `PENDENTE`. Texto acima de 500 caracteres responde 422.
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

**Decidido (09/11):** guardar o login entre aberturas do app com `flutter_secure_storage` (Regra 09).

**Backend**
- [ ] Nada no MVP: não há refresh token. Com 24 h de validade, a pessoa faz login de novo uma vez por dia.

**Frontend**
- [ ] Adicionar `flutter_secure_storage` e gravar o token no login.
- [ ] Ao abrir o app, ler o token e validar com `GET /auth/me`. Se responder 401, apagar o token e ir para o login.
- [ ] Apagar o token no logout e quando qualquer requisição autenticada responder 401.
- [ ] Testes com um armazenamento falso.

## Tarefa 10 — Retenção e privacidade (Regra 08 · YUME-03)

**Decidido (09/11, YUME-03):**
- Alertas e localização ficam guardados por **180 dias**.
- Depois disso, o alerta é **anonimizado**: as coordenadas e a mensagem são apagadas, e o status e as datas ficam para estatística.
- Haverá exclusão de conta no app.

**Ainda pendente:** quem da equipe pode acessar os dados de produção.

**Backend**
- [ ] Rotina diária (comando ou job) que anonimiza `alertas_sos` com mais de 180 dias e apaga os textos e telefones de `tentativas_envio_sos` ligadas a eles. Precisa ser idempotente e ter testes.
- [ ] `DELETE /api/v1/auth/me`: apaga a pessoa e os contatos dela e anonimiza os alertas na hora.

**Frontend**
- [ ] Tela de privacidade explicando a retenção de 180 dias e a anonimização.
- [ ] Consentimento LGPD antes do primeiro uso da localização.
- [ ] Botão "Excluir conta" com confirmação dupla. Depois de excluir, apagar o token e voltar ao login.

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
4. **Tarefa 5, depois a 6:** mapa de risco, a partir da tabela já exportada no Neon.
5. **Tarefas 7, 9 e 10:** perfil, sessão persistente e privacidade, antes de qualquer uso fora da equipe.

## Decisões

Respondidas pela Yume em 09/11/2026.

| Decisão | Resposta | Tarefa |
|---------|----------|--------|
| Como registrar o consentimento sem página web | Link com token de uso único | 1 |
| Evolution API: ambiente e número (YUME-04) | Número pessoal da Yume por enquanto; envio real em dev e na demo | 2 |
| Fonte dos dados do mapa (YUME-05) | Tabela exportada no Neon | 5 |
| Tamanho da região | Distrito | 5 |
| Score e cores | 0 a 100, em 3 faixas (verde abaixo de 34, amarelo de 34 a 66, vermelho a partir de 67) | 5 |
| Raio e limite da consulta | 3 km padrão, 10 km no máximo, até 50 regiões | 5 |
| Feedback | 6 categorias, até 500 caracteres, sem fotos | 6 |
| Sessão | `flutter_secure_storage` | 9 |
| Retenção (YUME-03) | 180 dias, depois anonimizar; com exclusão de conta | 10 |

### Ainda em aberto

| Decisão | Trava |
|---------|-------|
| Nome da tabela no Neon e significado das colunas | Tarefa 5 (MAP-01) |
| Fonte original e licença dos dados | Tarefa 5 (antes da demo pública) |
| Regra do raio do círculo (proposta: raio de área equivalente) | Tarefa 5 (MAP-05) |
| Onde hospedar a Evolution API e o backend para a demo | Tarefas 2 e 11 |
| Quem pode acessar os dados de produção | Tarefa 10 |
