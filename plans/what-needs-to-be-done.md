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
| Consentimento | Tarefa 1: link de uso único, rotas públicas e migração 0008 | Botão que envia o link pelo WhatsApp; página `tela-consentimento` |
| WhatsApp | SOS-05: cliente da Evolution API v2 (refeito do zero após o PR #9) | — |

---

## Tarefa 1 — Registrar o consentimento dos contatos (CONT-01 · Regra 03 · SOSM-02) ✅

**Entregue em 09/11.** Link de uso único (7 dias) para a página
[`tela-consentimento`](https://github.com/click-sos-lab-de-software-e-projetos/tela-consentimento),
em que o contato aceita ou recusa.

**Backend** (`5db5ce5`)
- [x] Migração 0008: `recusado_em`, hash SHA-256 do token e expiração em `contatos_emergencia`.
- [x] `POST /api/v1/contatos/{id}/consentimento` (JWT) gera ou renova o link `<CONSENTIMENTO_URL_BASE>#token=...`.
- [x] `POST /api/v1/consentimento/pedido` e `POST /api/v1/consentimento/resposta`, públicas, com o token no corpo.
- [x] Mudar o telefone no `PATCH` apaga consentimento, recusa e token.
- [x] Testes: token expirado, reutilizado ou desconhecido; contato de outra pessoa; 409 se já consentiu.

**Página** (`tela-consentimento` `9632ca4`)
- [x] HTML, CSS e JS puros, botões "Aceito" e "Não aceito", telas de link inválido e erro de rede.
- [x] Testada de ponta a ponta com o backend local (aceitar, recusar, link reutilizado, sem rede).

**Frontend** (`6b9ae22`)
- [x] Botão "Enviar pedido de consentimento" no Perfil abre o WhatsApp com o link.
- [x] Os contatos recarregam quando o app volta do WhatsApp.
- [x] Status "Recusou receber alertas" no Perfil e na tela Configurar SOS.

**Falta no deploy:** publicar a página como Static Site no Render, trocar `API_BASE_URL` em
`src/config.js` e configurar `CONSENTIMENTO_URL_BASE` e `CORS_ORIGIN_REGEX` no backend (Tarefa 11).

## Tarefa 2 — Envio por WhatsApp em segundo plano (SOS-05 a SOS-08 · Regra 04)

**Decidido (09/11, YUME-04):**
- Por enquanto o envio usa o número pessoal da Yume, conectado na hora da implementação.
- O envio real pode acontecer em dev local e na demonstração. Os testes automatizados usam sempre a API falsa.
- Credenciais só no `.env` local ou no `.env` do Neon, nunca no Git.

### Como subir a Evolution API (v2)

O cliente do SOS-05 deve chamar `POST {EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}` com o header `apikey` e o corpo `{"number": "5511...", "text": "..."}`. Esse é o contrato da Evolution API v2.

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
- Para a demo fora do seu computador, a Evolution API vai para o Render, junto com o backend (Tarefa 11).

**Backend**
- [x] **SOS-05, refazer do zero.** Entregue em 09/11, seguindo [`SOS-05-cliente-evolution.md`](SOS-05-cliente-evolution.md). O PR #9 foi fechado em 09/11 porque a Yume não se sentiu confiante para fazer o merge. A nova versão vai em um commit direto na `main`, sem reaproveitar o branch `feat/sos-05-cliente-evolution`, e precisa ser fácil de revisar:
  - antes do código, um plano em `plans/SOS-05-cliente-evolution.md`, no mesmo formato dos outros planos, aprovado pela Yume;
  - commit pequeno e só com o cliente: interface `EnviadorWhatsApp`, implementação HTTP da Evolution API e implementação falsa para os testes;
  - variáveis `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` e `EVOLUTION_INSTANCE` no `.env.example`;
  - erros classificados em temporário (timeout, 5xx, 429, que entram no retry do SOS-07) e definitivo (4xx, que não tenta de novo);
  - nem telefone nem texto da mensagem nos logs;
  - testes que mostrem o comportamento sem rede (`httpx.MockTransport`), e um teste manual documentado contra a Evolution API local (passo 5 acima);
  - a mensagem do commit explica como testar em 5 minutos.
- [x] Documentar no README o passo a passo acima, de forma resumida.
- [x] SOS-06: worker que, depois do commit da transação, envia para cada contato ativo com consentimento e grava uma linha em `tentativas_envio_sos`.
- [x] SOS-07: até 5 tentativas, com esperas de 5, 10, 15, 20 e 25 s. Depois da 5ª falha, o alerta vira `ERRO`; com sucesso, vira `ENVIADO`.
- [x] SOS-08:
  - logs estruturados identificados pelo UUID do alerta;
  - teste ponta a ponta com a Evolution API falsa.

**Frontend**
- [x] Nada a mudar no envio: o app já cria o alerta.
- [x] Depende da Tarefa 3 para mostrar o resultado do envio.

## Tarefa 3 — Consultar o status do alerta (Regra 04 · SOSM-05)

**Backend**
- [x] Criar `GET /api/v1/sos/alertas/{id}`, autenticada.
  - Devolve `status_envio`, `tentativas` e `criado_em`.
  - Alerta de outra pessoa retorna 404.
  - Não devolve coordenadas nem telefones.
- [ ] Opcional: `GET /api/v1/sos/alertas` com os últimos alertas da pessoa.

**Frontend**
- [x] Ler o `id` da resposta do `POST /sos/alertas`.
- [x] Consultar o status do alerta a cada 3 s, até `ENVIADO` ou `ERRO` (para depois de 2 min e mostra "ainda enviando").
- [x] Mostrar o estado `PENDENTE`, `ENVIADO` ou `ERRO`.
- [x] Oferecer o `wa.me` só como alternativa explícita (SOSM-05).

## Tarefa 4 — Fluxo S.O.S no app (SOSM-03 · SOSM-04 · Regra 02)

**Backend**
- [x] Nada novo. Só confirmar que a mensagem padrão da Regra 02 é usada quando `mensagem` vem vazia.

**Frontend**
- [x] Antes de pedir a localização no fluxo S.O.S:
  - explicar por que ela é necessária;
  - tratar permissão negada e GPS desligado com mensagens claras.
- [x] ~~Depois de segurar o botão, abrir um diálogo com campo de mensagem livre.~~ Trocado por decisão da Yume: um toque com 5 s para cancelar, sem digitar nada. A mensagem (até **255**) é configurada em Ajustes e salva por usuário no backend (`usuarios.mensagem_sos`, `PATCH /auth/me`).
- [x] O app nunca envia `mensagem`: o backend usa a mensagem salva do usuário ou a padrão.
- [x] Mostrar o aviso de privacidade aprovado: fica fixo na tela de Emergência, abaixo do botão.

## Tarefa 5 — Mapa de risco (MAP-01 a MAP-03 · MAP-05 a MAP-08 · MAPM-01 a MAPM-03)

**Decidido (09/11):**
- **Fonte:** dados criminais da SSP-SP, já carregados no banco **Neon**. Não haverá importação de Excel pelo app.
- **Região:** distrito (96 em São Paulo).
- **Score:** 0 a 100, em 3 faixas: verde abaixo de 34, amarelo de 34 a 66, vermelho a partir de 67.
- **Raio do círculo:** raio de um círculo com a mesma área do distrito, `sqrt(área / π)`.
- **Consulta:** raio padrão de 3 km, raio máximo de 10 km, no máximo 50 regiões por resposta.

### O que já existe no Neon (inspecionado em 09/11, só leitura)

| Tabela | Linhas | Conteúdo |
|--------|--------|----------|
| `interno.cargas_ssp` | 1 | Registro da carga de `SPDadosCriminais_2026.xlsx`: 296.566 linhas lidas, 288.487 inseridas, 8.078 rejeitadas |
| `interno.ocorrencias_ssp` | 288.487 | Uma ocorrência por linha: `localizacao` (Point 4326, índice GiST), `rubrica`, `natureza_apurada`, `data_ocorrencia`, `bairro`, `delegacia`, `peso` de 1 a 3 |
| `interno.fontes_geograficas` | 1 | `distritos-sp.geojson` do GeoSampa (dados abertos da Prefeitura de SP) |
| `public.regioes_seguranca` | 96 | Distritos com `id_publico` (`distrito-sp-N`), `limites` (MultiPolygon 4326, GiST), `centroide`, `score_oficial`, `score_final`, `cor_hex`, `raio_metros` |

Dados úteis das ocorrências:
- **Peso por crime:** furto vale 1; roubo e lesão corporal valem 2; homicídio e estupro valem 3.
- **Datas:** quase todas as ocorrências são de 2026, com cerca de 6 mil de 2025.
- **Território:** 287.871 são do município de São Paulo, e 255.441 caem dentro de algum distrito.

**Problemas encontrados**
- **Migrações fora do Git:** o Neon está na migração `0007`, mas o repositório só vai até a `0005`. As migrações `0006` e `0007` (e o script de carga) não estão em nenhum branch nem PR.
- **Score fora da escala:** `score_final` vai de 131 a 9943, não de 0 a 100, e `score_oficial` é 0 em todos os distritos. A fórmula usada não está no repositório. Não é a simples soma dos pesos (bateu em só 1 distrito).
- **Cor única:** os 96 distritos estão vermelhos (`#EF4444`).
- **Raio:** `raio_metros` já segue a regra decidida (área equivalente).
- **Licença:** a carga da SSP registra "não informada no arquivo fornecido". Decidido: tratar como dado público do portal de transparência da SSP-SP e registrar a URL na carga.

**Credenciais:** o backend não guarda a URL do Neon. O `.env` é baixado com `NEON_ENV_URL=... ./scripts/fetch-env.sh`, e `DATABASE_URL` aponta para o Neon. Os testes continuam no PostGIS descartável, nunca no Neon.

**Backend**
- [x] MAP-01 e MAP-02: trazer para o repositório as migrações `0006` e `0007` exatamente como estão no Neon. Elas criam o schema `interno`, as 3 tabelas internas e `regioes_seguranca`.
  - Decidido: reescrever as migrações a partir do schema atual (colunas, `CHECK`, FKs e índices GiST listados acima).
  - Testar as migrações no PostGIS descartável. No Neon, só rodar `alembic stamp 0007`, sem recriar nada.
- [x] MAP-03: trazer também o script de carga (SSP e GeoSampa), idempotente pelo `arquivo_sha256` e pela `chave_fonte`, com testes.
  - Feito em `scripts/carregar_mapa.py` (plano: `plans/MAP-03-carga-ssp-geosampa.md`). A `chave_fonte` antiga não pôde ser reproduzida, então a recarga no Neon precisa de `--substituir`.
  - Atenção: o `SPDadosCriminais_2026.xlsx` de hoje (sha `c1f9…`) não é o carregado no Neon (sha `a2f0…`). Ele tem 223.191 ocorrências válidas até 31/07/2026, contra cerca de 255 mil até 31/08/2026 no Neon. Com `--substituir`, o mapa perde dados; só recarregue com um arquivo que cubra o período todo.
- [x] MAP-05: função pura que recalcula o score:
  - usar só ocorrências dos últimos 6 meses (`data_ocorrencia`);
  - densidade = soma dos pesos ÷ área do distrito em km²;
  - score = densidade ÷ maior densidade × 100;
  - aplicar as 3 faixas de cor; o raio continua por área equivalente;
  - feedback comunitário tem peso zero;
  - comando que regrava `score_oficial`, `score_final`, `cor_hex` e `raio_metros` dos 96 distritos.
- [x] MAP-06 e MAP-07: `GET /api/v1/mapa/regioes?latitude&longitude&raio`:
  - raio padrão de 3000 m; acima de 10000 m responde 422;
  - no máximo 50 regiões, das mais próximas para as mais distantes;
  - schema público com só ID público, nome, centroide, score, cor e raio.
- [x] MAP-08: teste de integração com PostGIS real.

**Frontend**
- [x] Trocar `HttpOccurrenceRepository` (`/occurrences`, rota que não existe) por um repositório de `/mapa/regioes` (`HttpRegionRepository`, raio de 10 km).
- [x] Desenhar círculos com o centroide, o raio e a cor que vêm da API, no lugar do mapa de calor falso. Tocar mostra nome, score e faixa; legenda no topo.
- [x] Tratar carregamento, lista vazia e falha ("Tentar de novo"). Deslogado: mapa sem círculos e aviso para entrar.
- [x] O mapa precisa funcionar sem permissão de localização (MAPM-03): nunca pede; sem permissão, centro na Praça da Sé.
- [ ] MAPM-01: a chave do Maps já vem de configuração local. Conferir as restrições da chave no Google Cloud (passo manual, documentado no README do frontend).

## Tarefa 6 — Feedback comunitário (MAP-04 · MAPM-04 · Regra 05)

**Decidido (09/11):**
- Categorias: `ILUMINACAO`, `ASSALTO`, `ASSEDIO`, `MOVIMENTO` (pouco movimento), `POLICIAMENTO` (falta de policiamento), `OUTRO`.
- Texto livre de até 500 caracteres.
- Sem fotos.

**Backend**
- [x] Migração `feedbacks_comunidade`, com FKs para `usuarios` e `regioes_seguranca`, e um `CHECK` com as categorias acima.
- [x] `POST /api/v1/mapa/regioes/{id}/feedbacks`, autenticada, sempre com status `PENDENTE`. Texto acima de 500 caracteres responde 422.
- [x] Testes provando que o feedback não altera o score nem aparece em `/mapa/regioes`.

**Frontend**
- [x] Transformar a tela "Registro de ocorrência" em feedback vinculado a uma região selecionada no mapa (folha aberta pelo cartão do distrito; o código de ocorrência foi removido).
- [x] Avisar que o feedback fica pendente e não muda o mapa.
- [x] Não alterar localmente o score nem a cor da região.

## Tarefa 7 — Perfil editável

**Backend**
- [x] `PATCH /api/v1/auth/me` com `nome_completo` e `telefone_pessoal`.
- [x] Opcional: troca de senha, exigindo a senha atual.

**Frontend**
- [x] Hoje `EditProfileScreen` só altera o estado local. Passar a chamar a API.
- [x] Desabilitar a edição do e-mail ou criar um fluxo próprio para ele.

## Tarefa 8 — Edição e remoção de contatos

**Backend**
- [x] Nada novo: `PATCH` e `DELETE /contatos/{id}` já existem.

**Frontend**
- [x] `ContactsController.remove` existe, mas não há botão na interface. Adicionar editar e remover, com confirmação.
- [x] Ao editar o telefone, avisar que o consentimento será pedido de novo (Tarefa 1).

## Tarefa 9 — Sessão segura (Regra 09 · SOSM-01)

**Decidido (09/11):** guardar o login entre aberturas do app com `flutter_secure_storage` (Regra 09).

**Backend**
- [x] Nada no MVP: não há refresh token. Com 24 h de validade, a pessoa faz login de novo uma vez por dia.

**Frontend**
- [x] Adicionar `flutter_secure_storage` e gravar o token no login.
- [x] Ao abrir o app, ler o token e validar com `GET /auth/me`. Se responder 401, apagar o token e ir para o login. (Feito: restauração otimista; o login fica na aba Perfil; falha de rede mantém o token.)
- [x] Apagar o token no logout e quando qualquer requisição autenticada responder 401.
- [x] Testes com um armazenamento falso.

## Tarefa 10 — Retenção e privacidade (Regra 08 · YUME-03)

**Decidido (09/11, YUME-03):**
- Alertas e localização ficam guardados por **180 dias**.
- Depois disso, o alerta é **anonimizado**: as coordenadas e a mensagem são apagadas, e o status e as datas ficam para estatística.
- Haverá exclusão de conta no app.

**Acesso aos dados de produção:** só a Yume.

**Backend**
- [x] Rotina diária (comando ou job) que anonimiza `alertas_sos` com mais de 180 dias e apaga os textos e telefones de `tentativas_envio_sos` ligadas a eles. Precisa ser idempotente e ter testes. *Feito como script manual (`scripts/anonimizar_alertas.py`); o agendamento ficou para depois.*
- [x] `DELETE /api/v1/auth/me`: apaga a pessoa e os contatos dela e anonimiza os alertas na hora.

**Frontend**
- [x] Tela de privacidade explicando a retenção de 180 dias e a anonimização.
- [x] Consentimento LGPD antes do primeiro uso da localização.
- [x] Botão "Excluir conta" com confirmação dupla. Depois de excluir, apagar o token e voltar ao login.

## Tarefa 11 — Qualidade, CI e documentação

**Backend**
- [x] Workflow de CI: `ruff` (E, F, I) e `pytest` com um serviço PostGIS; os 291 testes rodam, incluindo integração.
- [ ] Atualizar `docs/index.html` com o status de cada ticket, incluindo `/me` e CORS.
- [ ] **Deploy no Render** (decidido em 09/11). O `render.yaml` já está pronto; falta criar o Blueprint na conta e preencher os segredos:
  - web service com `uvicorn`;
  - `DATABASE_URL` do Neon, `JWT_SECRET_KEY` e as variáveis da Evolution API configuradas como segredos no Render;
  - rodar `alembic upgrade head` a cada deploy;
  - publicar a URL e usá-la como `API_BASE_URL` no build de demonstração do app.
- [ ] **Evolution API no Render**, como um segundo serviço com a imagem Docker:
  - plano **gratuito** (decidido em 09/11): o app só precisa funcionar por 3 a 4 horas na apresentação;
  - o Postgres dela fica num banco separado no Neon, nunca no `neondb`;
  - ligar `DATABASE_SAVE_DATA_INSTANCE=true` para a sessão do WhatsApp sobreviver a reinícios sem ler o QR code de novo.
- [ ] **Roteiro do dia da apresentação** (o plano gratuito "dorme" depois de cerca de 15 minutos sem requisições):
  - uns 30 minutos antes, abrir `/health` do backend e `/` da Evolution API para acordar os dois;
  - conferir a conexão em `GET /instance/connectionState/{instancia}`; se não estiver `open`, ler o QR code de novo;
  - durante a apresentação, manter os dois acordados com um ping a cada 10 minutos (UptimeRobot, cron-job.org ou um `while sleep 600; do curl ...; done` no notebook);
  - mandar um S.O.S de teste para o seu número antes de começar;
  - desligar o ping depois.

**Frontend**
- [x] CI verde: `lib/screens/` (mapa do Lucas, 28/10) foi formatada e excluída do analyzer, porque importa arquivos da estrutura antiga. Fica como referência para a Tarefa 5.
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
4. **Tarefa 5, depois a 6:** mapa de risco. Primeiro trazer para o Git as migrações e a carga que já estão no Neon, depois recalcular o score.
5. **Tarefas 7, 9 e 10:** perfil, sessão persistente e privacidade, antes de qualquer uso fora da equipe.

## Decisões

Respondidas pela Yume em 09/11/2026.

| Decisão | Resposta | Tarefa |
|---------|----------|--------|
| Como registrar o consentimento sem página web | Link com token de uso único | 1 |
| Evolution API: ambiente e número (YUME-04) | Número pessoal da Yume por enquanto; envio real em dev e na demo | 2 |
| Fonte dos dados do mapa (YUME-05) | SSP-SP, já carregada no Neon (`interno.ocorrencias_ssp`); distritos do GeoSampa | 5 |
| Tamanho da região | Distrito | 5 |
| Score e cores | 0 a 100, em 3 faixas (verde abaixo de 34, amarelo de 34 a 66, vermelho a partir de 67) | 5 |
| Raio do círculo | Área equivalente, `sqrt(área / π)` | 5 |
| Raio e limite da consulta | 3 km padrão, 10 km no máximo, até 50 regiões | 5 |
| Feedback | 6 categorias, até 500 caracteres, sem fotos | 6 |
| Sessão | `flutter_secure_storage` | 9 |
| Retenção (YUME-03) | 180 dias, depois anonimizar; com exclusão de conta | 10 |
| Acesso aos dados de produção | Só a Yume | 10 |
| Hospedagem da demo | Backend e Evolution API no Render, plano gratuito (demo de 3 a 4 h) | 2 e 11 |
| Acesso ao Neon no dev | `NEON_ENV_URL` com `scripts/fetch-env.sh` | 5 |

### Respondidas depois de inspecionar o Neon (09/11)

| Decisão | Resposta | Tarefa |
|---------|----------|--------|
| Migrações `0006`/`0007` e carga fora do Git | Reescrever a partir do schema atual do Neon e marcar com `alembic stamp` | 5 |
| Normalização do score | Soma dos pesos por km², escalada pelo distrito com o maior valor (= 100) | 5 |
| Período do score | Só ocorrências dos últimos 6 meses | 5 |
| Licença dos dados | Dados públicos do portal de transparência da SSP-SP; registrar a URL em `interno.cargas_ssp` | 5 |

Nenhuma decisão trava o trabalho agora.
