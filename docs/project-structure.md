# Estrutura do projeto

Este documento descreve a organização atual do backend do Click S.O.S. As pastas indicam onde cada responsabilidade é implementada; algumas ainda estão vazias, à espera dos próximos tickets.

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

Migrações Alembic do PostgreSQL/PostGIS, em `migrations/versions/`, numeradas em sequência (`0001`, `0002`...). O `env.py` lê a URL de `DATABASE_URL` e usa os modelos de `src/app/db/models.py` como referência do autogenerate. Cada revisão precisa ter `upgrade` e `downgrade`; os testes de integração verificam a subida e a descida de todas.

### `scripts/`

Contém scripts operacionais usados pela equipe. `fetch-env.sh` baixa o arquivo `.env` somente quando uma URL segura for fornecida por meio de `NEON_ENV_URL`. `token_dev.py` cria uma pessoa usuária fictícia num banco local e imprime um JWT para testar as rotas privadas no Swagger; é um paliativo até o AUTH-01.

### `src/`

Contém o código-fonte Python da aplicação. O uso de `src/` separa claramente o pacote da aplicação dos testes, documentos e arquivos de infraestrutura.

### `tests/`

Contém os testes automatizados Python. O pre-commit executa toda esta suíte usando `pytest` antes de cada commit.

## Pacote da aplicação: `src/app/`

### `api/`

Rotas HTTP e dependências de rota. `deps.py` obtém a pessoa usuária do Bearer Token (SOS-01). As rotas versionadas ficam em `v1/`, um módulo por recurso: hoje, `v1/contatos.py` (CONT-01) e `v1/sos.py` (SOS-03). As rotas só traduzem HTTP: validam a entrada pelos schemas, delegam para `services/` e convertem as exceções do serviço em códigos de status.

### `core/`

Centralizará configurações transversais: leitura de variáveis de ambiente, segurança, logging e constantes compartilhadas. Não deve armazenar valores secretos diretamente no código.

### `db/`

Configuração e modelos do PostgreSQL/PostGIS: `config.py` lê `DATABASE_URL`, `base.py` define a base declarativa e `models.py` mapeia `usuarios`, `contatos_emergencia`, `alertas_sos` e `tentativas_envio_sos`. `sessao.py` fornece a dependência `obter_sessao` (uma sessão por requisição) e cria o engine com `hide_parameters`, para que telefones e coordenadas não apareçam em logs nem em mensagens de erro do banco.

### `schemas/`

Conterá os modelos Pydantic que definem os dados recebidos e enviados pela API. Esses contratos ajudam o app mobile e o backend a concordarem sobre formatos de requisição, resposta e erro.

### `services/`

Regras de negócio. `contatos.py` implementa o CONT-01: isolamento por `usuario_id` e limite de contatos ativos, com trava `FOR UPDATE` em `usuarios`. `alertas.py` implementa o SOS-03: exige ao menos um contato ativo com consentimento e grava o alerta como `PENDENTE`, sem chamar serviços externos. Próximo serviço: cálculo de risco de uma região. Rotas HTTP devem delegar a lógica para esta camada em vez de concentrá-la em `api/`.

### `workers/`

Reservada para tarefas executadas fora da resposta HTTP, como despacho do alerta S.O.S para a Evolution API/WhatsApp. Esse desacoplamento é necessário para que o aplicativo receba uma resposta rápida mesmo quando um serviço externo estiver lento.

### `main.py`

É o ponto de entrada da aplicação FastAPI. Registra os routers de `api/v1/` e disponibiliza `GET /health`, usado para verificar que o serviço iniciou corretamente.

## Arquivos importantes na raiz

- `Dockerfile`: define a imagem de desenvolvimento da API.
- `pyproject.toml`: declara metadados, dependências e configuração de testes Python.
- `.pre-commit-config.yaml`: faz o pre-commit executar `pytest`.
- `.env.example`: lista nomes de variáveis de ambiente sem valores secretos.
- `.gitignore`: impede que `.env`, ambientes virtuais e arquivos locais sejam enviados ao Git.
- `README.md`: orienta a preparação e verificação do ambiente.
