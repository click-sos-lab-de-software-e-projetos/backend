# Estrutura do projeto

Este documento descreve a organização atual do backend do Click S.O.S. O projeto ainda é um scaffold: as pastas indicam onde cada responsabilidade será implementada, mas não contêm regras de negócio prontas.

```text
backend/
├── .devcontainer/
├── docs/
├── migrations/
├── scripts/
├── src/
│   └── app/
│       ├── api/
│       ├── core/
│       ├── db/
│       ├── schemas/
│       ├── services/
│       └── workers/
└── tests/
```

## Pastas da raiz

### `.devcontainer/`

Configura o ambiente de desenvolvimento para VS Code Dev Containers. Permite que integrantes da equipe, especialmente em Windows com Docker Desktop, abram o repositório em um container com as dependências e extensões necessárias.

### `docs/`

Armazena documentos técnicos do backend, como este guia. Não deve conter segredos, credenciais ou arquivos `.env`.

### `migrations/`

Reservada para migrações de banco de dados, que serão criadas futuramente com Alembic. As migrações registrarão mudanças estruturais no PostgreSQL/PostGIS de forma versionada.

### `scripts/`

Contém scripts operacionais usados pela equipe. Atualmente, `fetch-env.sh` baixa o arquivo `.env` somente quando uma URL segura for fornecida por meio de `NEON_ENV_URL`.

### `src/`

Contém o código-fonte Python da aplicação. O uso de `src/` separa claramente o pacote da aplicação dos testes, documentos e arquivos de infraestrutura.

### `tests/`

Contém os testes automatizados Python. O pre-commit executa toda esta suíte usando `pytest` antes de cada commit.

## Pacote da aplicação: `src/app/`

### `api/`

Receberá as rotas HTTP versionadas da API, dependências de rota e controladores. Futuramente poderá conter, por exemplo, endpoints de autenticação, contatos, alertas S.O.S e regiões do mapa.

### `core/`

Centralizará configurações transversais: leitura de variáveis de ambiente, segurança, logging e constantes compartilhadas. Não deve armazenar valores secretos diretamente no código.

### `db/`

Receberá a configuração de conexão com PostgreSQL/PostGIS, modelos de persistência e sessões de banco de dados. Nenhuma conexão real com Neon foi implementada ainda.

### `schemas/`

Conterá os modelos Pydantic que definem os dados recebidos e enviados pela API. Esses contratos ajudam o app mobile e o backend a concordarem sobre formatos de requisição, resposta e erro.

### `services/`

Receberá as regras de negócio. Exemplos futuros incluem gestão de contatos de emergência, criação de alertas e cálculo de risco de uma região. Rotas HTTP devem delegar a lógica para esta camada em vez de concentrá-la em `api/`.

### `workers/`

Reservada para tarefas executadas fora da resposta HTTP, como despacho do alerta S.O.S para a Evolution API/WhatsApp. Esse desacoplamento é necessário para que o aplicativo receba uma resposta rápida mesmo quando um serviço externo estiver lento.

### `main.py`

É o ponto de entrada da aplicação FastAPI. Por enquanto, disponibiliza apenas `GET /health`, usado para verificar que o serviço iniciou corretamente.

## Arquivos importantes na raiz

- `Dockerfile`: define a imagem de desenvolvimento da API.
- `pyproject.toml`: declara metadados, dependências e configuração de testes Python.
- `.pre-commit-config.yaml`: faz o pre-commit executar `pytest`.
- `.env.example`: lista nomes de variáveis de ambiente sem valores secretos.
- `.gitignore`: impede que `.env`, ambientes virtuais e arquivos locais sejam enviados ao Git.
- `README.md`: orienta a preparação e verificação do ambiente.
