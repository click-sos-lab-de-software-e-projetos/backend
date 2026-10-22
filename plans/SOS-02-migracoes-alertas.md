# Plano — SOS-02: migrações de usuários, contatos e alertas

> *"A ordem e o método, mon ami. Primeiro a prova; depois, o culpado."*
> Cada passo abaixo é um ciclo de TDD: 🔴 escreva o teste e veja-o falhar → 🟢 escreva o mínimo para passar → 🔵 refatore com os testes verdes → commit.

**Ticket:** SOS-02 · Épico 01 (Alerta S.O.S)
**Branch:** `feat/sos-02-migracoes-alertas` (já criada a partir de `main`)
**Pronto quando:** as migrações sobem e descem em PostgreSQL/PostGIS e os relacionamentos são cobertos por teste de integração.

---

## 1. O que foi apurado (21/10/2026)

**Repositório:** `Desktop\Estudos de Programação\Click S.O.S - Backend\backend`
**Branch:** `feat/sos-02-migracoes-alertas`, criada a partir do `main` em `1daf711`. O `main` local está atualizado com o remoto (PRs #1 e #2 incluídos, `.gitattributes` com LF presente).

**Já feito neste ticket, ainda sem commit:**
- `pyproject.toml`:
  - dependências `alembic`, `geoalchemy2`, `psycopg[binary]` e `sqlalchemy`;
  - `python_functions = ["*_deve_*"]`;
  - marker `integracao`.
- `alembic init migrations`:
  - `alembic.ini` na raiz, **sem `sqlalchemy.url`** ✔;
  - `migrations/env.py` ainda no padrão gerado: lê a URL do `.ini` e tem `target_metadata = None`;
  - `script.py.mako`;
  - `versions/` vazio.
- `migrations/.gitkeep` removido.
- `tests/test_health.py` renomeado para o padrão `_deve_`.

**Pontos de atenção:**
- 🚨 **Um arquivo não pode entrar no commit:** `src/app/workers/0001-refactor-sos-aplica-a-revis-o-do-PR-3.patch`. É o patch do SOS-01, esquecido dentro do pacote da aplicação. Um `git add .` o levaria junto. Mova-o para a pasta-mãe, onde já estão os outros `.patch`.
- ⚔️ **Conflito anunciado com o PR #3 (SOS-01).** Aquele PR também adiciona `python_functions` ao `pyproject.toml` e também renomeia `tests/test_health.py`, mas com um corpo diferente (`getattr(route, "path", None)`). Quem fizer merge por último terá de resolver. Para reduzir o atrito, há duas saídas: copiar para cá exatamente a versão do PR #3 desses dois trechos, ou fazer rebase desta branch depois que o PR #3 entrar.
- **O SOS-02 não depende do código do SOS-01** (`pyjwt`, `api/deps.py`, `schemas/sos.py`).
- **Ainda não há nenhuma tabela, revisão ou `docker-compose`.** O Dev Container também não tem PostGIS.
- **Convenções do repositório que os testes precisam seguir:**
  - o pytest só coleta funções `*_deve_*`; um teste com outro nome **não roda e não avisa**;
  - o pre-commit roda a suíte inteira, então só se commita no verde, e os testes de integração precisam ser *pulados* (não falhar) quando não houver banco.
- **O AUTH-01 depende deste ticket:** `usuarios` precisa ter `nome_completo`, `email` único, `senha_hash` e `telefone_pessoal`.

## 2. Escopo

**Dentro:** configuração do Alembic; quatro tabelas (`usuarios`, `contatos_emergencia`, `alertas_sos`, `tentativas_envio_sos`); FKs, índices e restrições; testes de integração contra PostGIS real; modelos ORM (ciclo 9, opcional).

**Fora:** serviços e rotas (SOS-03 em diante), `regioes_seguranca` (MAP-02), campos de retenção (Regra 08 ainda pendente), validação de env na inicialização, aviso do `httpx` no pytest e checagem de tipos no pre-commit. Esses três últimos são dívidas técnicas com ticket próprio.

## 3. Decisões de schema — para a Yume revisar no PR

As fontes divergem em alguns pontos. A regra adotada aqui: **ticket e regras de negócio prevalecem sobre o PDF de arquitetura** (as próprias regras se declaram "fonte de verdade").

| # | Ponto | Decisão proposta | Motivo / conflito |
|---|-------|------------------|-------------------|
| D1 | Nome da tabela | `alertas_sos` | O PDF diz `alertas_de_sos`; o ticket e o modelo de dados dizem `alertas_sos`. |
| D2 | Valores de `status_envio` | `PENDENTE`, `ENVIADO`, `ERRO` | O PDF diz `ENTREGUE`; a Regra 04 e o critério do épico dizem `ENVIADO`. |
| D3 | Tipo dos status | `VARCHAR` + `CHECK`, não `ENUM` do Postgres | O downgrade fica trivial, e incluir um valor depois não exige `ALTER TYPE`. |
| D4 | Valores de `tentativas_envio_sos.status` | `SUCESSO`, `FALHOU` | **Suposição.** O modelo de dados só mostra `FALHOU`. |
| D5 | Unicidade do e-mail | índice único em `lower(email)` | Evita `Ana@x.com` e `ana@x.com` como duas contas (ajuda o AUTH-01). |
| D6 | `contatos → usuarios` | `ON DELETE CASCADE` | Segue o PDF de arquitetura. |
| D7 | `alertas_sos → usuarios` | `ON DELETE CASCADE` | Minimização de dados: apagar a pessoa apaga suas coordenadas. **Revisar junto com a Regra 08.** |
| D8 | `tentativas → alertas` | `ON DELETE CASCADE` | Uma tentativa não existe sem o alerta. |
| D9 | `tentativas → contatos` | `ON DELETE SET NULL` (`contato_id` anulável) | Com `RESTRICT`, o CONT-01 não conseguiria remover um contato que já recebeu alerta. **Pendente de confirmação.** |
| D10 | Nome do contato | coluna `nome` | O modelo do ticket diz `nome`; o PDF diz `nome_contato`. `grau_parentesco` (só no PDF) fica de fora até alguém pedir. |
| D11 | Telefone | `VARCHAR(20)` + `CHECK` E.164 (`^\+[1-9][0-9]{7,14}$`) | Segunda linha de defesa; a validação principal fica no CONT-01. |
| D12 | Limite de 3 contatos ativos | regra de aplicação (CONT-01) | Contagem entre linhas não cabe bem em `CHECK`. |
| D13 | Geometria | `geometry(Point, 4326)` | Segue o ticket e o PDF. Atenção: `ST_MakePoint(lng, lat)` recebe **longitude primeiro**. |
| D14 | IDs | `UUID` com `server_default gen_random_uuid()` | Nativo no PostgreSQL 13+, não precisa de `pgcrypto`. |
| D15 | Retenção | nenhum campo agora | YUME-03 está pendente. Quando a regra existir, entra uma migração nova. |

## 4. Passo 0 — Preparação (sem ciclo TDD)

1. **Arrumar a cena antes do primeiro commit.**
   ```bash
   mv src/app/workers/0001-refactor-sos-aplica-a-revis-o-do-PR-3.patch ../
   git status   # devem sobrar só: pyproject.toml, tests/test_health.py,
                # migrations/.gitkeep (removido), alembic.ini e migrations/
   ```
   Essas mudanças entram no commit do ciclo 1, junto com os testes que as justificam.
2. **Banco de teste PostGIS descartável.** Ele nunca deve ser o Neon, porque os testes apagam tudo.
   ```bash
   docker run -d --name click-sos-test-db -p 5433:5432 \
     -e POSTGRES_DB=click_sos_test -e POSTGRES_USER=teste -e POSTGRES_PASSWORD=teste \
     postgis/postgis:16-3.4
   ```
   No `.env` local (nunca no Git): `TEST_DATABASE_URL=postgresql+psycopg://teste:teste@localhost:5433/click_sos_test`.
   De dentro do Dev Container no Windows, use `host.docker.internal` no lugar de `localhost`.
3. **Dados de teste fictícios (regra 4 da equipe).**
   - Telefones com DDD inexistente, ex.: `+5500900000001`.
   - Coordenadas sem significado, ex.: `(0.5, 0.5)`.
   - E-mails `@example.com`.
   - Nunca usar o número ou a localização de alguém da equipe.

## 5. Ciclos TDD

Estrutura de testes proposta:

```text
tests/
├── test_alembic_config.py      # unitários, sem banco: rodam sempre
└── integracao/
    ├── conftest.py             # fixtures de banco; pula tudo sem TEST_DATABASE_URL
    ├── fabricas.py             # inserir_usuario(), inserir_contato()... com dados fictícios
    └── test_migracoes_*.py
```

### Ciclo 1 — Alembic configurado, URL vinda do ambiente

> **Situação:** dependências, `alembic init` e marker já existem (seção 1). Falta o essencial: o `env.py` ainda espera a URL dentro do `alembic.ini`, e não há nenhum teste.

🔴 **Teste** — `tests/test_alembic_config.py` (sem banco)
- `obter_url_banco_deve_ler_database_url_do_ambiente` (via `monkeypatch.setenv`)
- `obter_url_banco_sem_variavel_deve_lancar_erro_claro`
- `obter_url_banco_deve_usar_driver_psycopg` (converte `postgresql://` e `postgres://` em `postgresql+psycopg://`)
- `alembic_ini_nao_deve_conter_url_de_banco` (lê o `.ini`; `sqlalchemy.url` ausente ou vazio — protege contra vazamento)
- `historico_de_migracoes_deve_ter_no_maximo_uma_head` (via `ScriptDirectory`)

🕵️ Os dois últimos testes vão passar de primeira, porque o `.ini` já está limpo e `versions/` está vazio. **Sabote** para vê-los falhar: ponha uma URL fictícia no `.ini`, ou crie duas revisões com o mesmo `down_revision`. Depois desfaça a sabotagem.

🟢 **Implementação**
- `src/app/db/config.py` com `obter_url_banco()`.
- Em `migrations/env.py`, trocar a leitura da URL por `config.get_main_option("sqlalchemy.url") or obter_url_banco()`, nos modos online **e** offline. O teste injeta a URL de teste e a aplicação usa `DATABASE_URL`.

🔵 **Refatoração:** remover os comentários de exemplo do `alembic.ini` e do `env.py` que não se aplicam. Isso segue o mesmo estilo enxuto pedido na revisão do PR #3.

📦 `build(db): configura Alembic com URL lida do ambiente`. Este commit leva junto as dependências, o `alembic init` e a configuração do pytest que já estão no working tree.

### Ciclo 2 — Fixtures de integração e PostGIS habilitado

🔴 **Teste** — `tests/integracao/test_migracoes_base.py`
- `upgrade_head_deve_habilitar_extensao_postgis` (`SELECT 1 FROM pg_extension WHERE extname = 'postgis'`)
- `conftest_deve_recusar_test_database_url_igual_a_database_url`. Teste unitário da função de guarda: a suíte apaga tabelas e não pode tocar o banco real.

🟢 **Implementação**
- `tests/integracao/conftest.py`:
  - `pytestmark`/hook marca tudo como `integracao`;
  - `pytest.skip` se `TEST_DATABASE_URL` estiver ausente;
  - fixture `config_alembic`;
  - fixture `banco_migrado` (`upgrade head` → `yield engine` → `downgrade base`).
- Registrar o marker `integracao` no `pyproject.toml`.
- Revisão `0001_habilita_postgis`:
  - `upgrade`: `CREATE EXTENSION IF NOT EXISTS postgis`;
  - `downgrade`: **não remove** a extensão (o MAP-02 também usa). Deixar um comentário explicando.

📦 `feat(db): habilita PostGIS na primeira migração`

### Ciclo 3 — Tabela `usuarios`

🔴 **Teste** — `test_migracoes_usuarios.py`
- `tabela_usuarios_deve_ter_colunas_tipos_e_nulidade_esperados`: `id uuid`, `nome_completo varchar(120)`, `email varchar(150)`, `senha_hash varchar(255)`, `telefone_pessoal varchar(20)` (todos `NOT NULL`), `criado_em timestamptz`
- `usuario_inserido_sem_id_deve_receber_uuid_e_criado_em_automaticos`
- `email_duplicado_deve_violar_unicidade`
- `email_igual_com_caixa_diferente_deve_violar_unicidade` (D5)

🟢 **Implementação:** revisão `0002_cria_usuarios`, com `upgrade` e `downgrade` (`drop_table`).

🔵 **Refatoração:** extrair `inserir_usuario(conn, **sobrescritas)` para `fabricas.py`.

📦 `feat(db): cria tabela usuarios`

### Ciclo 4 — Tabela `contatos_emergencia`

🔴 **Teste** — `test_migracoes_contatos.py`
- `tabela_contatos_deve_ter_colunas_esperadas`: `id`, `usuario_id`, `nome varchar(100)`, `telefone_whatsapp varchar(20)`, `ativo bool default true`, `consentido_em timestamptz NULL`, `criado_em`
- `contato_com_usuario_inexistente_deve_violar_fk`
- `remover_usuario_deve_remover_seus_contatos` (D6)
- `contato_novo_deve_nascer_ativo_e_sem_consentimento`
- `telefone_fora_do_formato_e164_deve_violar_check` (D11)
- `contatos_deve_ter_indice_por_usuario_id`

🟢 **Implementação:** revisão `0003_cria_contatos_emergencia`.

📦 `feat(db): cria tabela contatos_emergencia`

### Ciclo 5 — Tabela `alertas_sos` (o coração do ticket)

🔴 **Teste** — `test_migracoes_alertas.py`
- `localizacao_deve_ser_point_com_srid_4326` (consultar `geometry_columns`: `type = 'POINT'`, `srid = 4326`)
- `ponto_gravado_deve_preservar_longitude_e_latitude` (inserir `ST_SetSRID(ST_MakePoint(lng, lat), 4326)` e ler `ST_X`/`ST_Y`; pega a inversão lat/lng)
- `ponto_com_outro_srid_deve_ser_rejeitado`
- `alertas_deve_ter_indice_gist_em_localizacao` (`pg_indexes.indexdef ILIKE '%USING gist (localizacao)%'`)
- `alerta_novo_deve_nascer_pendente_com_zero_tentativas`
- `status_envio_fora_do_dominio_deve_violar_check` (ex.: `'ENTREGUE'`, D2)
- `tentativas_negativas_deve_violar_check`
- `mensagem_nula_deve_ser_aceita` (nula usa a mensagem padrão no SOS-04)
- `mensagem_com_256_caracteres_deve_ser_rejeitada` (`varchar(255)`, mesmo limite do SOS-01)
- `criado_em_deve_ser_timestamp_com_fuso`
- `remover_usuario_deve_remover_seus_alertas` (D7)

🟢 **Implementação:** revisão `0004_cria_alertas_sos`.
⚠️ **Armadilha:** a coluna `Geometry` do GeoAlchemy2 cria um índice espacial automático. Use `Geometry("POINT", srid=4326, spatial_index=False)` e crie o índice GiST explicitamente com um nome fixo (`ix_alertas_sos_localizacao`). Sem isso, há risco de índice duplicado e de um `downgrade` que não sabe o que apagar.

📦 `feat(db): cria tabela alertas_sos com ponto SRID 4326`

### Ciclo 6 — Tabela `tentativas_envio_sos`

🔴 **Teste** — `test_migracoes_tentativas.py`
- `tabela_tentativas_deve_ter_colunas_esperadas`: `id`, `alerta_id NOT NULL`, `contato_id NULL`, `numero_tentativa int`, `status varchar`, `erro_codigo varchar(50) NULL`, `executado_em timestamptz default now()`
- `tentativas_deve_ter_indice_por_alerta_id` (exigido pelo ticket)
- `numero_tentativa_fora_de_1_a_5_deve_violar_check` (Regra 04: no máximo 5)
- `status_de_tentativa_fora_do_dominio_deve_violar_check` (D4)
- `tentativa_repetida_para_mesmo_alerta_contato_e_numero_deve_violar_unicidade`
- `remover_alerta_deve_remover_suas_tentativas` (D8)
- `remover_contato_deve_anular_contato_id_nas_tentativas` (D9)

🟢 **Implementação:** revisão `0005_cria_tentativas_envio_sos`.

📦 `feat(db): cria tabela tentativas_envio_sos`

### Ciclo 7 — Ida e volta (primeira metade do critério de pronto)

🔴 **Teste** — `test_migracoes_ida_e_volta.py`
- `downgrade_base_deve_remover_todas_as_tabelas_do_epico`
- `cada_revisao_deve_subir_descer_e_subir_novamente` (*stairway*: para cada revisão em ordem, `upgrade rev` → `downgrade -1` → `upgrade rev`)
- `schema_recriado_apos_downgrade_deve_ser_identico_ao_original` (compara um retrato do `inspect()`: tabelas, colunas, índices, FKs)

🟢 **Implementação:** corrigir os `downgrade` que falharem.
🕵️ Se os testes passarem de primeira, **sabote** de propósito: comente um `drop_index` e confirme que algum teste fica vermelho. Um teste que nunca falhou ainda não provou nada.

📦 `test(db): cobre subida e descida de todas as migrações`

### Ciclo 8 — Relacionamentos de ponta a ponta (segunda metade do critério de pronto)

🔴 **Teste** — `test_relacionamentos.py`
- `usuario_com_tres_contatos_e_um_alerta_deve_relacionar_tentativas_a_cada_contato`: cria uma pessoa, 3 contatos, 1 alerta e 1 tentativa por contato; um `JOIN` devolve as 3 linhas certas.
- `remover_usuario_deve_limpar_contatos_alertas_e_tentativas_em_cascata`

🟢 **Implementação:** normalmente nada. Se algo falhar, o defeito está numa FK dos ciclos 4–6.

📦 `test(db): cobre relacionamentos entre usuarios, contatos, alertas e tentativas`

### Ciclo 9 — Modelos ORM sem divergência (opcional; pode ir para o SOS-03 se o PR crescer)

🔴 **Teste**
- `metadados_orm_deve_coincidir_com_banco_migrado`: `alembic.autogenerate.compare_metadata` retorna lista vazia. Usar um `include_object` que ignore tabelas do PostGIS, como `spatial_ref_sys`; sem isso, o autogenerate tenta apagá-las.

🟢 **Implementação**
- `src/app/db/base.py`: `DeclarativeBase` com `naming_convention`.
- `src/app/db/models.py`.
- `target_metadata = Base.metadata` no `env.py`.

📦 `feat(db): adiciona modelos SQLAlchemy das tabelas do alerta`

## 6. Fechamento

1. **Documentação**
   - `.env.example`: adicionar `TEST_DATABASE_URL=` (sem valor).
   - `README.md`: seção "Testes de integração" (subir o PostGIS, `pytest -m integracao`, `alembic upgrade head`).
   - `docs/project-structure.md`: atualizar `migrations/` e `db/`, que hoje dizem "será criado futuramente".
   - 📦 `docs(db): explica migrações e testes de integração`
2. **Checklist antes do PR**
   - [ ] `pytest`: unitários verdes, integração *pulada* sem banco (o pre-commit continua funcionando para todos).
   - [ ] `TEST_DATABASE_URL=... pytest -m integracao`: tudo verde.
   - [ ] `alembic upgrade head --sql`: o SQL gerado foi lido, linha a linha.
   - [ ] `git diff origin/main --stat` sem `.env`, URL, telefone ou coordenada real.
   - [ ] Os testes de integração rodam no CI? **Hoje não há CI no repositório.** Registrar no PR que eles só rodam localmente.
3. **Descrição do PR:** copiar a tabela da seção 3 e marcar D4, D7 e D9 como pontos que pedem resposta da Yume.
