# Click S.O.S — Backend

Base técnica inicial do backend do Click S.O.S. Neste estágio existe apenas uma API FastAPI mínima para verificar que o ambiente está funcionando. Não há autenticação, banco de dados, geolocalização, integração com WhatsApp, mapa ou fluxo S.O.S implementados.

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

## Plano

O plano incremental de scaffold está em [`../PLAN.md`](../PLAN.md). As próximas funcionalidades devem ser implementadas somente após concluir e revisar esse plano.

## Verificação do scaffold

Execute estas verificações antes de iniciar a fase funcional:

```bash
pytest
pre-commit run --all-files
docker build -t click-sos-backend .
```

No VS Code, abra o projeto com **Reopen in Container** e confirme que a porta `8000`, os testes e a rota `/health` estão disponíveis. O build Docker deve ser executado em uma máquina com Docker Desktop ou Docker Engine instalado.
