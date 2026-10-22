# Click S.O.S — Backend

Base técnica inicial do backend do Click S.O.S. Neste estágio existem a autenticação Bearer (SOS-01) e as migrações das tabelas de usuários, contatos, alertas e tentativas (SOS-02). Ainda não há rotas de negócio, integração com WhatsApp ou mapa.

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

Com a aplicação iniciada, consulte `http://localhost:8000/health`. A documentação automática está em `http://localhost:8000/docs`.

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
