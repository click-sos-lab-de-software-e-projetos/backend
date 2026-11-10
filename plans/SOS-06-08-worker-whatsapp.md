# Plano — SOS-06 a SOS-08: envio do alerta por WhatsApp em segundo plano

> Cada passo abaixo é um ciclo de TDD: 🔴 escreva o teste e veja-o falhar → 🟢 escreva o mínimo para passar → 🔵 refatore com os testes verdes.
> **Um commit por ticket**, direto na `main`: SOS-06 (passos 1 a 4), SOS-07 (passos 5 a 7) e SOS-08 (passos 8 e 9).

**Tickets:** SOS-06, SOS-07 e SOS-08 · Épico 01 · Tarefa 2 de `plans/what-needs-to-be-done.md`
**Depende de:** SOS-05 (`app/services/whatsapp.py`, `tests/whatsapp_falso.py`) e SOS-04 (`app/services/mensagem_sos.py`).
**Feature flag:** nenhuma. Sem as variáveis da Evolution, o alerta vira `ERRO` (D6), e o app já oferece o `wa.me`.
**Pronto quando:** `POST /api/v1/sos/alertas` responde na hora, o envio acontece depois da resposta, cada tentativa fica gravada, a Regra 04 é respeitada e os logs não mostram dado pessoal.

---

## 1. O que foi apurado (09/11/2026)

- `services/alertas.py:criar_alerta` grava o alerta `PENDENTE` e faz o commit antes de devolver: a transação já está confirmada quando a rota responde.
- `api/v1/sos.py` não agenda nada. O teste `criar_alerta_nao_deve_disparar_envio` (`tests/integracao/test_api_alertas.py`) prova isso hoje e **vai mudar** no passo 3.
- `db/sessao.py`: `obter_engine()` com `lru_cache` e `obter_sessao()` por requisição. O worker roda depois da resposta, então precisa de **sessão própria**, nunca a da requisição.
- `montar_mensagem_emergencia(nome_usuario, latitude, longitude, mensagem)` devolve `MensagemEmergencia.texto`. Ler as coordenadas com `ST_Y`/`ST_X`, como `_alertas` em `test_api_alertas.py`.
- `tentativas_envio_sos`: `numero_tentativa` de 1 a 5, `status` `SUCESSO`/`FALHOU`, e unicidade em `(alerta_id, contato_id, numero_tentativa)`. `alertas_sos.tentativas >= 0`.
- Fábricas prontas: `tests/integracao/fabricas.py` (`inserir_usuario`, `inserir_contato`, `inserir_alerta`, `inserir_tentativa`).
- Com o `TestClient`, as `BackgroundTasks` rodam antes de `client.post` voltar. Isso é bom para os testes: o efeito do worker já está no banco quando o teste confere.

## 2. Decisões

Aprovadas pela Yume em 09/11:

| # | Ponto | Decisão |
|---|-------|---------|
| D1 | Esperas | 1ª tentativa imediata, depois esperas de **5, 10, 15 e 20 s**. São no máximo 5 tentativas, então o 25 da Regra 04 nunca é usado. |
| D2 | Quando o alerta vira `ENVIADO` | Assim que **ao menos 1 contato** receber. Quem falhou continua sendo tentado em segundo plano. `ERRO` só se ninguém receber. |
| D3 | Sem Evolution configurada ou sem contato apto no envio | O alerta vira `ERRO` e o caso vai para o log. |
| D4 | Reinício do servidor no meio das retentativas | Fora do escopo do MVP. Limitação conhecida: o alerta fica `PENDENTE`. |
| D5 | Commits | Um por ticket. |

Propostas neste plano, para a Yume conferir na revisão:

| # | Ponto | Proposta | Motivo |
|---|-------|----------|--------|
| D6 | Como rodar em segundo plano | `BackgroundTasks` do FastAPI, com função **síncrona** (vai para uma thread) | Já está no framework, roda depois que a resposta sai, e o cliente do SOS-05 é síncrono. Sem fila nem processo extra. |
| D7 | O que é uma "tentativa" | Uma **rodada** sobre os contatos ainda não atendidos. Cada contato ganha uma linha por rodada, e `alertas_sos.tentativas` = número de rodadas feitas. | Encaixa na unicidade `(alerta, contato, numero_tentativa)` e no `CHECK` de 1 a 5. |
| D8 | Falha definitiva (SOS-05) | O contato sai das próximas rodadas. Quando não sobra ninguém para tentar, o worker termina antes da 5ª rodada. | Não adianta repetir um 400 ou 401. |
| D9 | Quais contatos | Lidos **no momento do envio**: ativos, com `consentido_em`, da dona do alerta | Quem foi desativado ou trocou o telefone (o que apaga o consentimento) depois do POST não recebe. |
| D10 | Injeção para testes | Uma dependência `obter_despacho()` devolve a função já montada (fábrica de sessão + enviador + `esperar`). A rota só faz `add_task(despacho, alerta.id)`, e os testes trocam a dependência. | Uma dependência só, no lugar de três. O "relógio controlado" do SOS-07 é o `esperar` injetado, que nos testes só registra os segundos pedidos. |
| D11 | Enviador real | Criado uma vez, com `lru_cache`, como `obter_engine()`. O `httpx.Client` é seguro entre threads. | Não abre um cliente HTTP por alerta. |
| D12 | "Fake lento não aumenta a resposta" | Garantido pelo Starlette: `BackgroundTasks` rodam depois do envio da resposta. O teste prova que o envio foi **agendado** e não feito dentro do serviço. A medição de tempo fica no teste manual (seção 5). | Cronometrar no `TestClient` não mede nada, porque ele espera as tarefas terminarem. Testes com relógio também ficaram instáveis no PR #9. |
| D13 | Formato dos logs | `logger` `app.workers.despacho_sos`, mensagens `chave=valor` (`alerta_id=... rodada=2 enviados=1 falhas=2`). Também `extra={"alerta_id": ...}` para quem quiser formatar em JSON. | O projeto não tem configuração de log estruturado; `chave=valor` é legível e fácil de filtrar no Render. Nunca telefone, nome, texto nem coordenadas. `contato_id` é UUID e pode aparecer. |
| D14 | Exceção inesperada no worker (ex.: banco fora do ar) | Captura, registra `alerta_id` + **tipo** da exceção (sem a mensagem) e tenta marcar `ERRO` | Uma thread de background que estoura não aparece para ninguém. A mensagem da exceção pode carregar dados. |

## 3. Escopo

**Dentro:**
- `src/app/workers/despacho_sos.py`;
- dependência `obter_despacho` e agendamento em `api/v1/sos.py`;
- testes de integração do worker e da rota;
- logs.

**Fora:**
- consulta de status pelo app (Tarefa 3);
- retomar alertas após reinício (D4);
- fila externa (Redis/Celery);
- Evolution no Render (Tarefa 11).

## 4. Ciclos TDD

Arquivos novos:

```text
src/app/workers/despacho_sos.py                 # despachar_alerta(alerta_id, fabrica_sessao, enviador, esperar)
tests/integracao/test_despacho_sos.py           # worker contra PostGIS real + EnviadorWhatsAppFalso
```

O worker é testado direto, chamando `despachar_alerta` com `sessionmaker(engine_de_teste)`, `EnviadorWhatsAppFalso` e um `esperar` que só registra. A rota é testada em `test_api_alertas.py`. Para importar o falso dentro de `tests/integracao/`, conferir se `tests/` está no `pythonpath`. Se não estiver, mover `whatsapp_falso.py` para `tests/integracao/` (o SOS-05 ainda não tem outro uso para ele).

---

### SOS-06 — worker (commit 1)

#### Passo 1 — Uma rodada com sucesso grava a tentativa e marca `ENVIADO`

🔴 **Teste** — `tests/integracao/test_despacho_sos.py`
- `despachar_alerta_deve_enviar_o_texto_da_mensagem_a_cada_contato_apto`: uma pessoa com 2 contatos aptos, 1 inativo, 1 sem consentimento e 1 apto de **outra** pessoa (D9). O falso recebe exatamente 2 envios, com os telefones certos e o texto de `montar_mensagem_emergencia` (nome, coordenadas e mensagem do alerta; mensagem `NULL` → padrão).
- `despachar_alerta_com_sucesso_deve_gravar_tentativa_e_marcar_enviado`: uma linha `SUCESSO`, `numero_tentativa = 1` por contato; o alerta fica `ENVIADO` com `tentativas = 1`.

🟢 **Implementação** — `despachar_alerta`:
1. abre uma sessão pela fábrica;
2. carrega o alerta, o nome da dona e as coordenadas (`ST_Y`/`ST_X`) e os contatos aptos;
3. monta o texto uma vez;
4. envia a cada contato;
5. grava `TentativaEnvioSos` e atualiza `AlertaSos`;
6. faz o commit.

Siga o estilo de consulta de `services/alertas.py:_contar_contatos_aptos`.
🔵 **Refatoração:** extrair a consulta de contatos aptos, que agora é usada em dois lugares (o filtro é o mesmo de `alertas.py`).
**Demo:** testes verdes.

#### Passo 2 — Sem contato apto no envio, o alerta vira `ERRO` (D3)

🔴 **Teste**
- `despachar_alerta_sem_contato_apto_deve_marcar_erro_sem_enviar` (contato desativado depois do POST): o falso não recebe nada, não há tentativas, e o alerta fica `ERRO` com `tentativas = 0`.

🟢 **Implementação:** sair cedo, marcando `ERRO`.
**Demo:** teste verde.

#### Passo 3 — A rota agenda o envio depois de responder (D6, D10, D12)

🔴 **Teste** — `tests/integracao/test_api_alertas.py`
- Trocar `criar_alerta_nao_deve_disparar_envio` por `criar_alerta_deve_agendar_o_envio_do_alerta_criado`: a fixture `client` sobrescreve `obter_despacho` com uma função que registra os IDs. Depois do POST, o ID registrado é o `id` da resposta.
- `servico_criar_alerta_nao_deve_chamar_o_despacho` não é necessário: `services/alertas.py` não recebe o despacho, e é isso que garante a resposta rápida (D12).
- A fixture `client` padrão passa a sobrescrever `obter_despacho` com uma função que não faz nada. Assim os testes existentes não tentam a Evolution real.

🟢 **Implementação**
- `api/deps.py` (ou `workers/despacho_sos.py`): `obter_despacho()` devolve `functools.partial(despachar_alerta, fabrica_sessao=..., enviador=..., esperar=time.sleep)`.
- `obter_enviador_whatsapp()` com `lru_cache` (D11).
- A rota recebe `BackgroundTasks` e o despacho, e chama `add_task` depois de `servico.criar_alerta`.
- Atualizar a `description` da rota (já diz "em segundo plano").

**Demo:** teste verde. Com a Evolution local, um POST no Swagger faz a mensagem chegar (seção 5).

#### Passo 4 — Evolution sem configuração vira `ERRO`, sem derrubar a API (D3)

🔴 **Teste**
- `despacho_sem_variaveis_da_evolution_deve_marcar_o_alerta_como_erro`. Sem as variáveis (`monkeypatch.delenv`), o despacho real (não sobrescrito) marca o alerta como `ERRO`, e o POST continua respondendo 201.

🟢 **Implementação:** `obter_despacho` captura o `RuntimeError` de `criar_enviador_evolution` e devolve uma função que só marca `ERRO` e registra o caso. Limpar o `lru_cache` entre testes (`cache_clear()` na fixture).
**Demo:** subir a API sem as variáveis da Evolution, acionar o S.O.S e ver o alerta `ERRO` no banco.

📦 `feat(sos): worker que envia o alerta aos contatos depois da resposta (SOS-06)`

---

### SOS-07 — retentativas (commit 2)

#### Passo 5 — Falha temporária é tentada de novo, com as esperas de D1

🔴 **Teste** — use roteiros no `EnviadorWhatsAppFalso`
- `falha_temporaria_deve_ser_tentada_de_novo_apos_5_segundos`: 1 contato; o roteiro é temporária e depois sucesso. Resultado: 2 linhas (`FALHOU` com `erro_codigo`, depois `SUCESSO`), `esperar` chamado com `[5]`, e o alerta `ENVIADO` com `tentativas = 2`.
- `alerta_deve_continuar_pendente_entre_rodadas`: o `esperar` de teste lê o `status_envio` no banco quando é chamado e anota `PENDENTE`.

🟢 **Implementação:** laço de até 5 rodadas. Commit **ao fim de cada rodada** (atualiza `tentativas` e as linhas). Chamar `esperar(ESPERAS[rodada])` antes da próxima, sem esperar depois da última. Criar `ESPERAS_RETENTATIVA_S = (5, 10, 15, 20)` e `MAXIMO_TENTATIVAS_ENVIO = 5` em `app/constants.py`, com um comentário citando a Regra 04 e D1.
**Demo:** testes verdes.

#### Passo 6 — Cinco falhas viram `ERRO`; falha definitiva não se repete (D8)

🔴 **Teste**
- `cinco_falhas_temporarias_devem_marcar_erro_apos_esperas_5_10_15_20`: 5 linhas `FALHOU` com `numero_tentativa` de 1 a 5, esperas `[5, 10, 15, 20]`, e o alerta `ERRO` com `tentativas = 5`.
- `falha_definitiva_nao_deve_ser_tentada_de_novo`: só 1 linha, nenhuma espera, e o alerta `ERRO` com `tentativas = 1`.

🟢 **Implementação:** tirar da rodada seguinte os contatos com falha definitiva ou já atendidos, e parar quando não sobrar ninguém.
🕵️ Se passar de primeira, **sabote**: troque o `<` do laço por `<=` e veja o teste das cinco falhas acusar a 6ª rodada (que viola o `CHECK`).
**Demo:** testes verdes.

#### Passo 7 — Um contato atendido já basta para `ENVIADO`; os outros seguem (D2)

🔴 **Teste**
- `alerta_deve_virar_enviado_na_primeira_rodada_com_sucesso_e_seguir_tentando_os_demais`: contato A com sucesso; contato B com temporária, temporária e sucesso. Ao fim da rodada 1, o alerta já está `ENVIADO` (lido pelo `esperar` de teste). B ganha 3 linhas, A só 1, e no fim o alerta continua `ENVIADO`, com `tentativas = 3`.
- `alerta_enviado_nao_deve_voltar_para_erro_se_os_demais_esgotarem`: A com sucesso, B falha 5 vezes. No fim, o alerta continua `ENVIADO`.

🟢 **Implementação:** `ENVIADO` quando houver o primeiro `SUCESSO` e nunca mais muda. `ERRO` só no fim, se ninguém recebeu.
**Demo:** testes verdes.

📦 `feat(sos): retentativas da Regra 04 no envio do alerta (SOS-07)`

---

### SOS-08 — observabilidade e ponta a ponta (commit 3)

#### Passo 8 — Logs pelo UUID do alerta, sem dado pessoal (D13, D14)

🔴 **Teste**
- `despacho_deve_registrar_inicio_rodadas_e_fim_pelo_uuid_do_alerta`: com `caplog`, toda mensagem do logger `app.workers.despacho_sos` contém `alerta_id=<uuid>`, e o fim traz o status final.
- `despacho_nao_deve_registrar_telefone_nome_texto_nem_coordenadas`: `caplog` em DEBUG, inclusive `sqlalchemy.engine`, mirando `criar_alerta_nao_deve_registrar_coordenadas_nem_mensagem_em_logs`. Nenhum dado fictício da pessoa aparece em nenhuma mensagem.
- `erro_inesperado_no_despacho_deve_registrar_tipo_e_marcar_erro`: um enviador que levanta `RuntimeError("+5500900000001")` resulta em log com `RuntimeError` e **sem** o telefone, e o alerta fica `ERRO`.

🟢 **Implementação:** `logger.info` no início (`contatos=N`), um por rodada e um no fim. `logger.warning` com `type(erro).__name__` no `except Exception` geral (D14).
🕵️ **Sabote** o teste de vazamento: logue o texto e veja ficar vermelho.
**Demo:** testes verdes. No terminal do `uvicorn`, as linhas `alerta_id=...` aparecem.

#### Passo 9 — Ponta a ponta: POST → worker → banco (critério do SOS-08)

🔴 **Teste** — `tests/integracao/test_api_alertas.py` (ou `test_fluxo_sos.py`)
- `fluxo_sos_deve_enviar_a_ate_3_contatos_e_gravar_estados_finais`. Uma pessoa com 3 contatos aptos e `obter_despacho` sobrescrito com o despacho **real**, montado com `EnviadorWhatsAppFalso`, a fábrica de teste e `esperar` que só registra. Roteiro: dois sucessos e um contato com temporária e depois sucesso.
- Resultado esperado:
  - 201 com o `id`;
  - 3 envios na rodada 1 e 1 na rodada 2;
  - 4 linhas em `tentativas_envio_sos`;
  - alerta `ENVIADO` com `tentativas = 2`;
  - nenhum dado sensível em `caplog`.
- O banco é preparado e limpo pelas fixtures existentes (`banco_migrado`).

🟢 **Implementação:** normalmente nada. Se falhar, o defeito está na ligação do passo 3.
**Demo:** teste verde. É o critério de pronto do SOS-08.

📦 `test(sos): logs por alerta e fluxo S.O.S de ponta a ponta (SOS-08)`

## 5. Teste manual (depois do SOS-06 e de novo depois do SOS-07)

Com o PostGIS de dev, a Evolution local conectada (README, "Envio por WhatsApp") e **um único contato apto com o seu próprio número**:

1. Medir a resposta: `curl -w '%{time_total}\n' -X POST .../api/v1/sos/alertas ...` deve voltar em menos de 1 s, e a mensagem chega logo depois (D12).
2. Depois do SOS-07, com a Evolution parada:
   - acionar o S.O.S: as linhas `rodada=` saem com 5, 10, 15 e 20 s de intervalo, e o alerta termina `ERRO`;
   - religar a Evolution no meio: o alerta termina `ENVIADO`.
3. Desconectar a instância no fim.

## 6. Fechamento (a cada commit)

- [x] `ruff check .` e `pytest` verdes; com `TEST_DATABASE_URL`, `pytest -m integracao` verde.
- [x] Nada de telefone real, chave ou URL de servidor no diff.
- [x] Marcar o ticket em `plans/what-needs-to-be-done.md`; no SOS-06, atualizar `workers/` em `docs/project-structure.md` e o passo 6 do README ("nenhuma mensagem é enviada").

## 7. Perguntas em aberto / suposições

- **Duplicidade:** se a Evolution entregar e mesmo assim der timeout, o contato pode receber o alerta duas vezes. Aceito para o MVP (ver D6 do SOS-05).
- **Limitação D4:** escrever uma frase no README dizendo que alerta `PENDENTE` órfão após reinício não é retomado.
- **Render gratuito:** o serviço só dorme após ~15 min sem requisições. As retentativas levam ~50 s, então não devem ser interrompidas.
