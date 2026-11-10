# TAREFA-07: perfil editável e troca de senha

**Goal:** `PATCH /api/v1/auth/me` altera `nome_completo` e/ou `telefone_pessoal`; `POST /api/v1/auth/me/senha` troca a senha exigindo a atual.
**Source:** `plans/what-needs-to-be-done.md` (Tarefa 7) + decisões da Yume (10/11).
**Feature flag:** nenhuma — rotas novas; o app só passa a chamá-las na Tarefa 7 do frontend.

## Decisões
- D1 PATCH parcial: só os campos enviados mudam. Corpo vazio `{}` → 422.
- D2 `email` (ou qualquer campo extra) no corpo → 422 (`extra="forbid"`). E-mail não é editável no MVP.
- D3 Campo enviado como `null` → 422. Validações iguais às do cadastro (`NomeCompleto`, `TelefoneE164` de `schemas/auth.py`).
- D4 PATCH responde 200 com `UsuarioResposta` (mesmo corpo do `GET /me`).
- D5 Troca de senha: `POST /auth/me/senha` com `{senha_atual, senha_nova}` → 204. Senha atual errada → 400. `senha_nova` segue a política do cadastro (`SenhaNova`: mín. 8, máx. 72 bytes).
- D6 Token válido de pessoa que não existe mais → 401, como no `GET /me`.
- D7 Sem coluna `atualizado_em`; sem migração.

## Out of scope
- Troca de e-mail.
- Revogar tokens emitidos antes da troca de senha (não há lista de revogação; continuam válidos até expirar).
- Frontend.

## Step 1: schemas do PATCH e da troca de senha
- **Files**: `src/app/schemas/auth.py`, `tests/test_schemas_auth.py` (existente ou novo).
- **Test (red)**: unidade — `AtualizarPerfilRequisicao` aceita só nome, só telefone ou ambos; recusa `{}`, `null` em qualquer campo, `email`, nome em branco, telefone fora do E.164. `TrocarSenhaRequisicao` recusa `senha_nova` curta ou acima de 72 bytes e `senha_atual` vazia. Mirror `tests/test_schemas_sos.py`.
- **Implement (green)**: os dois modelos com `extra="forbid"`, reaproveitando `NomeCompleto`, `TelefoneE164` e `SenhaNova`; validador de modelo para corpo vazio e `null`.
- **Refactor**: n/a
- **Demo**: testes verdes.
- **Depends on**: none

## Step 2: rotas respondem 401/422 sem tocar no banco e aparecem no OpenAPI
- **Files**: `src/app/api/v1/auth.py`, `tests/test_rotas_auth.py` (ou o arquivo de unidade de auth existente).
- **Test (red)**: unidade — sem token → 401 sem abrir sessão; corpo inválido → 422 sem chamar o serviço; OpenAPI documenta 200/401/422 no PATCH e 204/400/401/422 na senha. Mirror `tests/test_rotas_mapa.py`.
- **Implement (green)**: `PATCH /me` e `POST /me/senha` delegando a `servico.atualizar_perfil` e `servico.trocar_senha`; `UsuarioNaoEncontrado` → 401, `SenhaAtualIncorreta` → 400.
- **Refactor**: helper para o 401 repetido, se ficar claro.
- **Demo**: `/docs` mostra as rotas.
- **Depends on**: Step 1

## Step 3: PATCH grava só os campos enviados
- **Files**: `src/app/services/auth.py`, `tests/integracao/test_api_auth.py` (existente).
- **Test (red)**: integração — PATCH só com telefone mantém o nome e devolve 200 com o perfil atualizado; `GET /me` em seguida mostra o novo valor; pessoa inexistente → 401. Mirror os testes de `/me` existentes.
- **Implement (green)**: `atualizar_perfil` aplica `model_dump(exclude_unset=True)` no `Usuario` e faz commit.
- **Refactor**: n/a
- **Demo**: `curl -X PATCH .../auth/me` com token.
- **Depends on**: Step 2

## Step 4: troca de senha exige a senha atual
- **Files**: `src/app/services/auth.py`, `tests/integracao/test_api_auth.py`.
- **Test (red)**: integração — com a senha atual certa → 204, login com a nova funciona e com a antiga dá 401; senha atual errada → 400 e a senha não muda; pessoa inexistente → 401.
- **Implement (green)**: `trocar_senha` verifica com `verificar_senha`, grava `gerar_hash_senha(nova)`.
- **Refactor**: n/a
- **Demo**: teste verde.
- **Depends on**: Step 2

## Step 5: documentação e checklist
- **Files**: `README.md`, `docs/project-structure.md`, `plans/what-needs-to-be-done.md` (marcar os 2 itens de backend da Tarefa 7).
- **Demo**: README descreve as duas rotas.
- **Depends on**: Steps 3, 4

## Open questions / assumptions
- `senha_nova` igual à atual é aceita (sem regra extra).
- Tokens antigos seguem válidos após a troca de senha até expirar (24 h por padrão); registrar no README.
- Commit único `feat(auth): perfil editável e troca de senha (Tarefa 7)`.
