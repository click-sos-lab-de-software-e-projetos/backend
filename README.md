# Click S.O.S — Backend

Base técnica inicial do backend do Click S.O.S. Neste estágio existem o cadastro e login com JWT em `/api/v1/auth` (AUTH-01), a autenticação Bearer (SOS-01), as migrações das tabelas de usuários, contatos, alertas e tentativas (SOS-02) o CRUD de contatos de emergência em `/api/v1/contatos` (CONT-01), o consentimento do contato por link de uso único, a criação do alerta em `POST /api/v1/sos/alertas` (SOS-03), que grava o alerta como `PENDENTE`. As tabelas do mapa (`regioes_seguranca` e o schema `interno` com as ocorrências da SSP) já existem, mas ainda não há rota do mapa. Depois da resposta, o alerta é enviado pelo WhatsApp aos contatos aptos, pela Evolution API (SOS-05 e SOS-06).

## Requisitos

- Git
- Docker Desktop com Docker Compose v2
- VS Code com as extensões **Dev Containers** e **Docker**

Para executar sem container, também são necessários Python 3.12+ e `pip`.

## Desenvolvimento no VS Code — recomendado no Windows

1. Instale e inicie o Docker Desktop.
2. Abra a pasta `backend` no VS Code.
3. Escolha **Reopen in Container** quando o VS Code sugerir; se necessário, use o comando `Dev Containers: Reopen in Container`.
4. O ambiente instala as dependências, configura o pre-commit e disponibiliza a porta `8000`.

## Execução local

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\\Scripts\\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -e '.[dev]'
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Com a aplicação iniciada, consulte `http://localhost:8000/health`. A documentação automática está em `http://localhost:8000/docs` (Swagger) e `http://localhost:8000/redoc`.

## Testar as rotas privadas no Swagger

As rotas de `/api/v1/contatos` e `/api/v1/sos/alertas` exigem um banco migrado e um JWT, obtido pelo cadastro e login de `/api/v1/auth` (AUTH-01). O token vale 24 horas (ajuste com `JWT_EXPIRACAO_MIN`) e não é renovado: ao expirar, faça login de novo. `GET /api/v1/auth/me` devolve o perfil da pessoa dona do token.

### Consentimento do contato

O contato só recebe alertas depois de consentir (Regra 03). O fluxo usa a página do repositório [`tela-consentimento`](https://github.com/click-sos-lab-de-software-e-projetos/tela-consentimento):

1. O app chama `POST /api/v1/contatos/{id}/consentimento` (com JWT) e recebe `{url, expira_em}`. A URL é `CONSENTIMENTO_URL_BASE#token=...` e vale 7 dias; gerar outra invalida a anterior.
2. A pessoa envia a URL ao contato pelo WhatsApp.
3. A página chama `POST /api/v1/consentimento/pedido` com `{token}` para mostrar quem pediu, e `POST /api/v1/consentimento/resposta` com `{token, aceito}`. Essas duas rotas são públicas; o token vai no corpo para não aparecer em logs, e só o SHA-256 dele fica no banco.
4. Aceitar grava `consentido_em`; recusar grava `recusado_em`. O link deixa de valer depois da resposta. Trocar o telefone do contato apaga o consentimento.

A origem da página precisa estar liberada em `CORS_ORIGIN_REGEX`.

Para o app web (Flutter no Chrome) chamar a API, libere a origem com `CORS_ORIGIN_REGEX`, por exemplo `CORS_ORIGIN_REGEX=http://localhost:\d+`. Vazio (padrão) desliga o CORS; o app Android/iOS não precisa dele. No emulador Android, a API local fica em `http://10.0.2.2:8000`.

1. **Suba um PostGIS de desenvolvimento**, separado do banco de testes (que é apagado a cada execução):

   ```bash
   docker run -d --name click-sos-dev-db -p 5432:5432 \
     -e POSTGRES_DB=click_sos -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
     postgis/postgis:16-3.4
   ```

2. **Preencha o `.env`** (de dentro do Dev Container, troque `localhost` por `host.docker.internal`):

   ```dotenv
   DATABASE_URL=postgresql+psycopg://dev:dev@localhost:5432/click_sos
   JWT_SECRET_KEY=<gere com: python -c "import secrets; print(secrets.token_urlsafe(32))">
   ```

3. **Carregue o `.env` no terminal.** O Alembic, o pytest e o script leem só variáveis de ambiente, não o arquivo:

   ```powershell
   # Windows (PowerShell)
   Get-Content .env | Where-Object { $_ -match '^[A-Z_]+=.' } | ForEach-Object { $n, $v = $_ -split '=', 2; Set-Item "env:$n" $v }
   ```

   ```bash
   # Linux/macOS/Dev Container
   set -a; source .env; set +a
   ```

4. **Migre e suba a API:**

   ```bash
   alembic upgrade head
   uvicorn app.main:app --reload --port 8000
   ```

5. **No Swagger** (`http://localhost:8000/docs`), crie uma conta em `POST /api/v1/auth/cadastro` (e-mail `@example.com`, senha com ao menos 8 caracteres) e entre em `POST /api/v1/auth/login`. Copie o `access_token` da resposta, clique em **Authorize**, cole-o (sem a palavra `Bearer`) e use **Try it out** nas rotas de contatos.

   Atalho opcional: `python scripts/token_dev.py` cria uma pessoa fictícia e imprime um token dela, sem senha (ela não consegue fazer login). Para reaproveitá-la: `--usuario-id <uuid>`. O script recusa bancos fora da sua máquina.

Comportamentos esperados: e-mail já cadastrado responde `409`; senha errada ou e-mail inexistente respondem o mesmo `401`; o quarto contato ativo responde `409`; o contato de outra pessoa responde `404`; sem token, `401`. Use só telefones fictícios (DDD `00`), mesmo no banco local.

6. **Para acionar o S.O.S**, a pessoa precisa de ao menos um contato ativo **com consentimento**. Enquanto a forma de registrar o consentimento não for decidida, marque-o direto no banco local, usando o `id` devolvido pelo cadastro do contato:

   ```bash
   docker exec click-sos-dev-db psql -U dev -d click_sos -c \
     "UPDATE contatos_emergencia SET consentido_em = now() WHERE id = '<id-do-contato>'"
   ```

   Sem isso, `POST /api/v1/sos/alertas` responde `422`. Com isso, responde `201` com o alerta `PENDENTE`; logo depois o worker envia a mensagem pelo WhatsApp a cada contato apto (veja "Envio por WhatsApp"). Sem as variáveis da Evolution, o alerta vira `ERRO`. Use coordenadas sem significado também no banco local.

## Envio por WhatsApp (Evolution API v2)

O cliente do SOS-05 (`app/services/whatsapp.py`) envia texto pela Evolution API. Os testes automatizados nunca usam rede; para um envio real em dev, suba a Evolution localmente com um Postgres próprio (nunca o Neon nem o banco de testes):

```bash
podman network create evolution
podman run -d --name evolution-db --network evolution \
  -e POSTGRES_USER=evolution -e POSTGRES_PASSWORD=evolution -e POSTGRES_DB=evolution postgres:16
podman run -d --name evolution-api --network evolution -p 8080:8080 \
  -e AUTHENTICATION_API_KEY=<chave longa, ex.: openssl rand -hex 32> \
  -e DATABASE_PROVIDER=postgresql \
  -e DATABASE_CONNECTION_URI=postgresql://evolution:evolution@evolution-db:5432/evolution \
  -e CACHE_REDIS_ENABLED=false -e CACHE_LOCAL_ENABLED=true \
  evoapicloud/evolution-api:latest
```

(Com Docker, troque `podman` por `docker`.) Depois:

1. No `.env`: `EVOLUTION_API_URL=http://localhost:8080`, `EVOLUTION_API_KEY=<a mesma chave>` e `EVOLUTION_INSTANCE=click-sos-dev`. Carregue-o com `set -a; source .env; set +a`.
2. Crie a instância:
   ```bash
   curl -X POST "$EVOLUTION_API_URL/instance/create" -H "apikey: $EVOLUTION_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"instanceName": "click-sos-dev", "integration": "WHATSAPP-BAILEYS", "qrcode": true}'
   ```
3. Leia o QR code no celular (WhatsApp → *Aparelhos conectados*). O QR aparece no painel `http://localhost:8080/manager` ou em `GET /instance/connect/click-sos-dev`. Confira com `GET /instance/connectionState/click-sos-dev`: o estado deve ser `open`.
4. Envie só para o seu próprio número:
   ```bash
   python -c "from app.services.whatsapp import criar_enviador_evolution as c; print(c().enviar('+55SEUNUMERO', 'Teste Click S.O.S'))"
   ```
   Espera-se `ENVIADO`. Chave errada dá `FALHA_DEFINITIVA`/`HTTP_401`, e a Evolution parada dá `FALHA_TEMPORARIA`/`CONEXAO`.
5. Ao terminar, desconecte o número:
   ```bash
   curl -X DELETE "$EVOLUTION_API_URL/instance/logout/click-sos-dev" -H "apikey: $EVOLUTION_API_KEY"
   ```

Com um número pessoal, evite rajadas de mensagens: o WhatsApp pode banir números que enviam muitas mensagens automáticas.

O worker registra cada envio no logger `app.workers.despacho_sos`, sempre pelo UUID do alerta (`alerta_id=...`): início, uma linha por rodada e o `status_envio` final. Telefone, nome, texto e coordenadas nunca aparecem no log. Limitação conhecida: se o servidor reiniciar durante o envio, o alerta fica `PENDENTE` e não é retomado.

## Testes e pre-commit

```bash
ruff check src tests migrations
pytest
pre-commit install
```

Depois de instalado, o hook executa todos os testes Python antes de cada commit. O CI (`.github/workflows/ci.yml`) roda `ruff` e `pytest` com um PostGIS, incluindo os testes de integração.

### Testes de integração (PostgreSQL/PostGIS)

Os testes em `tests/integracao/` rodam as migrações contra um PostGIS real e **apagam todas as tabelas** do banco usado. Sem `TEST_DATABASE_URL` eles são pulados, então o pre-commit continua funcionando sem banco. A suíte se recusa a rodar se `TEST_DATABASE_URL` for igual a `DATABASE_URL`.

```bash
docker run -d --name click-sos-test-db -p 5433:5432 \
  -e POSTGRES_DB=click_sos_test -e POSTGRES_USER=teste -e POSTGRES_PASSWORD=teste \
  postgis/postgis:16-3.4

# no .env local; de dentro do Dev Container use host.docker.internal no lugar de localhost
TEST_DATABASE_URL=postgresql+psycopg://teste:teste@localhost:5433/click_sos_test

pytest -m integracao
```

Use apenas dados fictícios nos testes: e-mails `@example.com`, telefones com DDD `00` e coordenadas sem significado.

### Migrações

A URL do banco vem de `DATABASE_URL`; o `alembic.ini` não guarda URL.

```bash
alembic upgrade head        # aplica todas as migrações
alembic downgrade base      # desfaz todas
alembic upgrade head --sql  # mostra o SQL sem executar
alembic check               # confirma que os modelos em src/app/db/models.py batem com as migrações
```

As revisões `0006` e `0007` (schema `interno` e `regioes_seguranca`) foram aplicadas no Neon antes de estarem no Git e depois reescritas a partir do schema real. No Neon, `alembic upgrade head` parte da `0007`; não rode `downgrade` lá.

## Variáveis de ambiente

O arquivo `.env` é local e não deve ser versionado. Copie o exemplo antes de configurar valores reais:

```bash
cp .env.example .env
```

Quando a URL segura for fornecida, defina `NEON_ENV_URL` e execute:

```bash
./scripts/fetch-env.sh
```

O script baixa o arquivo para `.env`; não inclua essa URL nem segredos no Git.

## Deploy no Render

O `render.yaml` descreve o web service no plano gratuito. No Render, crie um **Blueprint** apontando para este repositório e preencha as variáveis marcadas como `sync: false`:

- `DATABASE_URL`: URL do Neon (`postgresql://...`; o driver `psycopg` é colocado automaticamente);
- `CORS_ORIGIN_REGEX`: origens da página de consentimento e do app web, separadas por `|`;
- `CONSENTIMENTO_URL_BASE`: endereço da página `tela-consentimento`;
- `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` e `EVOLUTION_INSTANCE`: quando o envio por WhatsApp existir.

`JWT_SECRET_KEY` é gerada pelo Render. Cada deploy roda `alembic upgrade head` antes de subir o `uvicorn`. O serviço gratuito dorme depois de uns 15 minutos sem requisições; veja o roteiro da apresentação na Tarefa 11 de `plans/what-needs-to-be-done.md`.

## Verificação do scaffold

Execute estas verificações antes de iniciar a fase funcional:

```bash
pytest
pre-commit run --all-files
docker build -t click-sos-backend .
```

No VS Code, abra o projeto com **Reopen in Container** e confirme que a porta `8000`, os testes e a rota `/health` estão disponíveis. O build Docker deve ser executado em uma máquina com Docker Desktop ou Docker Engine instalado.

## Documentação e GitHub Pages

As páginas estáticas do projeto estão em `docs/`:

- `docs/index.html`: lista técnica de tarefas backend;
- `docs/business-rules.html`: regras de negócio;
- `docs/project-structure.md`: organização do repositório.

No GitHub, configure o Pages para publicar a branch `main` a partir da pasta `/docs`. A página inicial será `index.html`.
