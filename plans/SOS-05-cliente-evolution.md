# Plano — SOS-05: cliente da Evolution API (refeito do zero)

> Cada passo abaixo é um ciclo de TDD: 🔴 escreva o teste e veja-o falhar → 🟢 escreva o mínimo para passar → 🔵 refatore com os testes verdes.
> Diferente do SOS-02, **não há um commit por ciclo**: o SOS-05 sai num commit único e pequeno, direto na `main`.

**Ticket:** SOS-05 · Épico 01 (Alerta S.O.S) · Tarefa 2 de `plans/what-needs-to-be-done.md`
**Branch:** nenhuma. Commit direto na `main`, sem reaproveitar `feat/sos-05-cliente-evolution` (PR #9, fechado em 09/11).
**Feature flag:** nenhuma. O cliente ainda não é chamado por ninguém; quem liga o envio é o worker do SOS-06.
**Pronto quando:** o cliente envia pela Evolution API v2, classifica cada falha como temporária ou definitiva, não escreve telefone, texto nem chave em log, e está coberto por testes sem rede.

---

## 1. O que foi apurado (09/11/2026)

- `main` em `07f8806`, CI verde (`ruff` + `pytest` com PostGIS).
- `src/app/workers/` só tem o `__init__.py`. Ainda não existe nenhum código de WhatsApp na `main`.
- `.env.example` já tem `EVOLUTION_API_URL=` e `EVOLUTION_API_KEY=`, mas falta `EVOLUTION_INSTANCE=`.
- `httpx` hoje é só dependência de desenvolvimento (`[project.optional-dependencies].dev`).
- Variáveis de ambiente são lidas com `os.environ.get` e o **nome** delas fica em `app/constants.py` (`NOME_VARIAVEL_*`). Siga o mesmo padrão: `src/app/db/config.py:obter_url_banco` (variável ausente → `RuntimeError` com o nome) e `src/app/api/deps.py`.
- `tentativas_envio_sos.erro_codigo` é `VARCHAR(50)` e `status` aceita `SUCESSO`/`FALHOU` (migração `0005`). O código de erro do cliente precisa caber ali.
- O telefone do contato já está em E.164 garantido por `CHECK` (`ck_contatos_telefone_e164`) e por `PADRAO_TELEFONE_E164`.
- Convenção de testes: o pytest só coleta `*_deve_*` (`tests/test_convencoes.py` falha se houver `test_*`). Dados sempre fictícios (`+5500900000001`).

**Por que o PR #9 ficou difícil de revisar, e o que muda aqui**

| PR #9 | Agora |
|-------|-------|
| Dois módulos (`whatsapp.py` + `evolution.py`) | Um módulo, `app/services/whatsapp.py` |
| Assíncrono, com `asyncio.run` nos testes | Síncrono (D1) |
| Fake dentro do pacote da aplicação, com testes próprios | Fake em `tests/`, sem testes próprios (D4) |
| 36 testes, um por status HTTP | Cerca de 10 testes, um por **classe** de resposta |
| Só código de erro, sem dizer se vale tentar de novo | Desfecho `TEMPORARIA`/`DEFINITIVA` (D2) |

## 2. Escopo

**Dentro:**
- interface `EnviadorWhatsApp`, resultado do envio e implementação HTTP `EnviadorEvolution`;
- implementação falsa `EnviadorWhatsAppFalso` em `tests/`;
- leitura de `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` e `EVOLUTION_INSTANCE`;
- `httpx` como dependência da aplicação;
- `EVOLUTION_INSTANCE=` no `.env.example`.

**Fora:**
- worker e gravação em `tentativas_envio_sos` (SOS-06);
- retentativas e mudança do status do alerta (SOS-07);
- logs estruturados por UUID do alerta (SOS-08);
- passo a passo no README (item próprio da Tarefa 2);
- subir a Evolution no Render (Tarefa 11).

## 3. Decisões — para a Yume aprovar

| # | Ponto | Proposta | Motivo |
|---|-------|----------|--------|
| D1 | Síncrono ou assíncrono | **Síncrono**, `httpx.Client` | Mais simples de ler e testar (sem `asyncio.run`). O worker do SOS-06 pode rodar via `BackgroundTasks`, que executa função síncrona numa thread; as esperas de 5 a 25 s não travam a API. |
| D2 | Como o worker sabe se tenta de novo | O envio **devolve** um `ResultadoEnvio` (não levanta exceção) com `desfecho` ∈ `ENVIADO`, `FALHA_TEMPORARIA`, `FALHA_DEFINITIVA` e `erro_codigo` | Falhar faz parte do fluxo normal (Regra 04). O SOS-07 decide só olhando o `desfecho`. |
| D3 | Classificação | **Temporária:** timeout, falha de conexão, 429 e 5xx. **Definitiva:** qualquer outro status fora de 2xx (400, 401, 403, 404...) | Segue a Tarefa 2. Falha de conexão (Evolution fora do ar ou "dormindo" no Render) foi incluída como temporária: é o caso mais comum na demo. |
| D4 | Onde fica a implementação falsa | `tests/whatsapp_falso.py` | Código de teste fora do pacote da aplicação, e o commit fica menor. Ela registra os envios e segue um roteiro de desfechos (sem roteiro, sempre `ENVIADO`). Ganha uso de verdade nos testes do SOS-06; teste só dela repetiria a implementação. |
| D5 | Códigos de erro | `TIMEOUT`, `CONEXAO`, `HTTP_<status>` (ex.: `HTTP_429`) | Curtos, cabem em `erro_codigo VARCHAR(50)` e não carregam dado pessoal. |
| D6 | Timeout | **10 s** por envio | A especificação de arquitetura fala em 3 s, mas a Evolution às vezes demora mais. Timeout conta como falha temporária, e a mensagem pode ter sido entregue mesmo assim. Um timeout curto aumenta o risco de o contato receber o alerta duplicado. |
| D7 | Formato do número | E.164 sem o `+` (`5500900000001`) | É o que a Evolution v2 espera em `number`. |
| D8 | Corpo da resposta de erro | **Descartado**; guarda só o status | O corpo pode ecoar o número e o texto. |
| D9 | Configuração ausente | `RuntimeError` com o **nome** da variável, nunca o valor | Mesmo padrão de `obter_url_banco`. A leitura acontece ao criar o enviador, não na importação do módulo. Assim a API e os testes sobem sem a Evolution configurada. |

> **Atenção, 401/403/404:** chave errada ou instância inexistente viram falha **definitiva** (não adianta tentar de novo). Para quem opera, a pista é o `erro_codigo` gravado na tentativa.

## 4. Ciclos TDD

Arquivos novos:

```text
src/app/services/whatsapp.py     # EnviadorWhatsApp, ResultadoEnvio, EnviadorEvolution, criar_enviador_evolution()
tests/test_whatsapp.py           # testes sem rede (httpx.MockTransport)
tests/whatsapp_falso.py          # EnviadorWhatsAppFalso (sem testes próprios, D4)
```

Nos testes, construa o `EnviadorEvolution` passando um `httpx.Client(transport=httpx.MockTransport(...))`. O `MockTransport` recebe a requisição, e o teste confere URL, cabeçalho e corpo dentro do handler. Assim **nenhum teste usa rede**.

### Ciclo 1 — Envio com sucesso no contrato da Evolution v2

🔴 **Teste** — `tests/test_whatsapp.py`
- `enviar_deve_chamar_send_text_da_instancia_com_apikey_e_numero_sem_mais`: `POST {url}/message/sendText/{instancia}`, cabeçalho `apikey`, corpo JSON `{"number": "5500900000001", "text": ...}`; resposta `201` → `desfecho == ENVIADO` e `erro_codigo is None`.
- `enviar_deve_aceitar_url_base_com_barra_no_final` (`http://evolution.test/` não gera `//message`).

🟢 **Implementação** — `src/app/services/whatsapp.py`
- `Desfecho` (enum de string) e `ResultadoEnvio` (dataclass congelada), como as de `services/consentimento.py`.
- `EnviadorWhatsApp`: `typing.Protocol` com `enviar(telefone_e164, texto) -> ResultadoEnvio`.
- `EnviadorEvolution(url_base, chave, instancia, cliente_http)`, que recebe o `httpx.Client` já pronto.
- Mover `httpx` de `dev` para `dependencies` no `pyproject.toml`.

🔵 **Refatoração:** n/a.
**Demo:** os dois testes verdes.

### Ciclo 2 — Classificação das falhas (D3, D5)

🔴 **Teste** — use `pytest.mark.parametrize` para não duplicar código:
- `resposta_429_ou_5xx_deve_ser_falha_temporaria_com_codigo_http` (429, 500, 503 → `FALHA_TEMPORARIA`, `HTTP_<status>`).
- `resposta_4xx_deve_ser_falha_definitiva_com_codigo_http` (400, 401, 404 → `FALHA_DEFINITIVA`).
- `timeout_deve_ser_falha_temporaria` (o handler levanta `httpx.ReadTimeout` → `TIMEOUT`).
- `falha_de_conexao_deve_ser_falha_temporaria` (`httpx.ConnectError` → `CONEXAO`).

🟢 **Implementação:** capturar `httpx.TimeoutException` antes de `httpx.TransportError` (o timeout é uma subclasse dela). Classificar pelo status. Não ler o corpo da resposta de erro (D8).

🔵 **Refatoração:** isolar a classificação do status numa função pequena, se o `enviar` crescer.
**Demo:** testes verdes. Cada classe de resposta tem um desfecho claro para o SOS-07.

### Ciclo 3 — Nada sensível em log (requisito da Tarefa 2)

🔴 **Teste**
- `enviar_nao_deve_registrar_telefone_texto_nem_chave_em_log`: `caplog.set_level(logging.DEBUG)`, envia com sucesso e com falha 500, e confere que nenhum registro contém o telefone (com e sem `+`), o texto nem a chave. Para o teste não passar no vazio, confira também que existe ao menos um registro do httpx (`HTTP Request: POST ...`).
- `repr_do_enviador_nao_deve_mostrar_a_chave`.

🟢 **Implementação:** o enviador não escreve log nenhum. Os logs do SOS-08 ficam no worker, identificados pelo UUID do alerta. Esconder a chave do `repr` (`field(repr=False)` ou `__repr__` próprio).
🕵️ Se os testes passarem de primeira, **sabote**: inclua o telefone num `logger.debug` e veja o teste ficar vermelho. Depois desfaça.

**Demo:** testes verdes.

### Ciclo 4 — Configuração pelo ambiente (D9)

🔴 **Teste**
- `criar_enviador_evolution_deve_ler_as_tres_variaveis` (`monkeypatch.setenv`; os atributos do enviador refletem as variáveis).
- `criar_enviador_evolution_sem_variavel_deve_lancar_erro_com_o_nome_dela` (parametrizado nas três; a mensagem contém o nome e não contém os valores das outras duas).

🟢 **Implementação**
- `NOME_VARIAVEL_EVOLUTION_URL`, `NOME_VARIAVEL_EVOLUTION_CHAVE` e `NOME_VARIAVEL_EVOLUTION_INSTANCIA` em `app/constants.py`. Também `TIMEOUT_ENVIO_WHATSAPP_S = 10` (D6), com um comentário de uma linha sobre o risco de duplicar.
- `criar_enviador_evolution()` em `whatsapp.py`: lê as variáveis e cria o `httpx.Client(timeout=...)`.
- `EVOLUTION_INSTANCE=` no `.env.example`, com um comentário curto ao lado das outras duas.

**Demo:** testes verdes.

### Ciclo 5 — Implementação falsa (D4)

Sem teste próprio. Escrever `tests/whatsapp_falso.py`:
- `EnviadorWhatsAppFalso(roteiro=None)`;
- guarda `envios` como lista de `(telefone, texto)`;
- devolve os `ResultadoEnvio` do roteiro em ordem e, quando o roteiro acaba ou não existe, `ENVIADO`.

Ela segue o mesmo `Protocol`, então o `ruff`/IDE já acusa assinatura errada. O SOS-06 vai usá-la nos testes do worker.

## 5. Teste manual (5 minutos, contra a Evolution local)

Pré-requisito: Evolution v2 local rodando e a instância conectada (passos 1 a 4 da Tarefa 2), com as três variáveis no `.env`.

```bash
set -a; source .env; set +a
python -c "from app.services.whatsapp import criar_enviador_evolution as c; print(c().enviar('+55SEUNUMERO', 'Teste Click S.O.S'))"
```

O que esperar:
- **Mensagem chega no WhatsApp:** imprime `desfecho=ENVIADO`.
- **`EVOLUTION_API_KEY` errada:** `FALHA_DEFINITIVA`, `HTTP_401`.
- **Evolution parada** (`podman stop evolution-api`): `FALHA_TEMPORARIA`, `CONEXAO`.

Envie só para o seu próprio número e evite rajadas (risco de banimento do número pessoal).

## 6. Fechamento

- [x] `ruff check .` e `pytest`: tudo verde (integração pulada sem banco).
- [x] `git diff --stat` só com: `pyproject.toml`, `.env.example`, `src/app/constants.py`, `src/app/services/whatsapp.py`, `tests/test_whatsapp.py` e `tests/whatsapp_falso.py`.
- [x] Nenhum telefone real, chave nem URL de servidor no diff.
- [x] Commit `feat(sos): cliente da Evolution API (SOS-05)`. A mensagem resume as decisões D1 a D3 e traz o teste manual da seção 5 ("como testar em 5 minutos").
- [x] Marcar o SOS-05 em `plans/what-needs-to-be-done.md`.

## 7. Perguntas em aberto / suposições

- **Timeout de 10 s (D6):** diverge dos 3 s da especificação de arquitetura. Confirmar.
- **Falha de conexão como temporária (D3):** a Tarefa 2 cita só timeout, 5xx e 429. Confirmar.
- **Número que não tem WhatsApp:** confirmado no teste manual de 09/11 (Evolution v2.3.7): responde 400, o que vira falha definitiva.
- **`docs/project-structure.md`:** atualizar a descrição de `services/` neste mesmo commit (uma frase sobre `whatsapp.py`)? Proposta: sim.
