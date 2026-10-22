# Click S.O.S — Backend

Base técnica inicial do backend do Click S.O.S. Neste estágio existem a autenticação Bearer (SOS-01), as migrações das tabelas de usuários, contatos, alertas e tentativas (SOS-02) e o CRUD de contatos de emergência em `/api/v1/contatos` (CONT-01). Ainda não há cadastro/login (AUTH-01), rota de alerta, integração com WhatsApp ou mapa.

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

As rotas de `/api/v1/contatos` exigem um banco migrado e um JWT. Enquanto o AUTH-01 não existir, o token vem de `scripts/token_dev.py`, que cria uma pessoa usuária fictícia e imprime um token dela.

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

4. **Migre, gere o token e suba a API:**

   ```bash
   alembic upgrade head
   python scripts/token_dev.py          # imprime o token; guarde-o
   uvicorn app.main:app --reload --port 8000
   ```

   Para reaproveitar a mesma pessoa depois: `python scripts/token_dev.py --usuario-id <uuid>`. O UUID é exibido quando ela é criada. O script recusa bancos fora da sua máquina para não criar pessoas fictícias no banco da equipe.

5. **No Swagger** (`http://localhost:8000/docs`), clique em **Authorize**, cole o token (sem a palavra `Bearer`) e use **Try it out** nas rotas de contatos.

Comportamentos esperados: o quarto contato ativo responde `409`; o contato de outra pessoa responde `404`; sem token, `401`. Use só telefones fictícios (DDD `00`), mesmo no banco local.

## Testes e pre-commit

```bash
pytest
pre-commit install
```

Depois de instalado, o hook executa todos os testes Python antes de cada commit.

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
