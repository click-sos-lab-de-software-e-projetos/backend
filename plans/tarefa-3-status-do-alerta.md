# Plano — Tarefa 3: consultar o status do alerta S.O.S

> Cada passo abaixo é um ciclo de TDD: 🔴 escreva o teste e veja-o falhar → 🟢 escreva o mínimo para passar → 🔵 refatore com os testes verdes.
> **Um commit só**, direto na `main`, com rota, testes e documentação.

**Tickets:** Regra 04 · SOSM-05 · Tarefa 3 de `plans/what-needs-to-be-done.md` (só a parte de backend)
**Depende de:** SOS-06 a SOS-08 (o worker é quem muda `status_envio` e `tentativas`).
**Feature flag:** nenhuma. A rota é nova e só leitura; nenhum cliente a usa ainda.
**Pronto quando:** `GET /api/v1/sos/alertas/{id}` devolve o estado do alerta da própria pessoa, 404 para qualquer outro, sem coordenadas, mensagem nem telefones.

---

## 1. O que foi apurado (09/11/2026)

- `api/v1/sos.py` só tem o `POST /alertas`. `UsuarioId` vem antes de `Sessao`: sem token válido, o banco nem é aberto. Manter essa ordem na rota nova.
- O padrão de "ver um recurso da própria pessoa" já existe em contatos: `services/contatos.py:obter` filtra por `id` **e** `usuario_id` e lança `ContatoNaoEncontrado`; `api/v1/contatos.py:obter_contato` converte em 404 com `R_404`. Copiar esse formato.
- `AlertaSos` (`db/models.py`) tem `id`, `usuario_id`, `localizacao`, `mensagem`, `status_envio`, `tentativas` e `criado_em`. Não há `atualizado_em`.
- `schemas/sos.py:AlertaCriadoResposta` tem `id`, `status_envio: Literal["PENDENTE"]` e `criado_em`.
- Testes: unitários de rota sem banco em `tests/test_rotas_alertas.py` (sessão proibida, OpenAPI); integração em `tests/integracao/test_api_alertas.py` (fixtures `client`, `ana`, `_usuario`, `_token`; `fabricas.inserir_alerta`). Os 404 de contatos ficam em `tests/integracao/test_api_contatos.py:137` e `:156`.

## 2. Decisões

Aprovadas pela Yume em 09/11:

| # | Ponto | Decisão |
|---|-------|---------|
| D1 | Campos da resposta | `id`, `status_envio` (`PENDENTE`, `ENVIADO` ou `ERRO`), `tentativas` e `criado_em`. Nada de coordenadas, mensagem, telefones nem resultado por contato. |
| D2 | Alerta de outra pessoa | 404 com o **mesmo corpo** de um id inexistente: a resposta não revela que o alerta existe. |
| D3 | `GET /sos/alertas` (listagem) | Fora por enquanto. O app não precisa dela. |
| D4 | Id inválido (não é UUID) | 422 padrão do FastAPI, como em contatos. |
| D5 | Commits | Um commit só, com rota, testes e documentação. |

## 3. Fora do escopo

- Listagem de alertas (D3).
- Frontend: ler o `id`, consultar o status a cada poucos segundos, mostrar o estado e oferecer o `wa.me` (SOSM-05).
- Rate limit da consulta: o app consulta a cada poucos segundos, só até `ENVIADO` ou `ERRO`.

## 4. Passos

### Passo 1 — Sem token, a consulta responde 401 sem abrir o banco
- **Arquivos:** `src/app/api/v1/sos.py`, `tests/test_rotas_alertas.py`.
- **Teste (🔴):** unitário de rota, `consultar_alerta_sem_token_valido_deve_responder_401_sem_tocar_no_banco`, parametrizado como o do `POST` (sem cabeçalho e com token inválido). Hoje a rota não existe e responde 405.
- **Implementar (🟢):** rota `GET /alertas/{alerta_id}` com `UsuarioId` antes de `Sessao`.
- **Demo:** `curl` sem token → 401 com `WWW-Authenticate: Bearer`.

### Passo 2 — A dona do alerta vê id, status, tentativas e data
- **Arquivos:** `src/app/schemas/sos.py`, `src/app/services/alertas.py`, `src/app/api/v1/sos.py`, `tests/integracao/test_api_alertas.py`.
- **Teste (🔴):** integração, `consultar_alerta_deve_devolver_id_status_tentativas_e_data`. Inserir o alerta com `fabricas.inserir_alerta` já como `ENVIADO` e `tentativas=2`, e conferir que o corpo tem **exatamente** as 4 chaves de D1.
- **Implementar (🟢):** schema `AlertaStatusResposta` com `status_envio: Literal["PENDENTE", "ENVIADO", "ERRO"]`; `servico.obter_alerta(sessao, usuario_id, alerta_id)` filtrando por `id` e `usuario_id`, como `contatos.obter`.
- **Refatorar (🔵):** se ficar natural, criar um tipo `StatusEnvio` comum ao schema e às constantes do worker; senão, deixar.
- **Demo:** depois do `POST`, o `GET` mostra o alerta `ENVIADO` (ou `ERRO` sem Evolution).

### Passo 3 — Alerta inexistente ou de outra pessoa responde 404 igual
- **Arquivos:** `src/app/services/alertas.py`, `src/app/api/v1/sos.py`, `tests/integracao/test_api_alertas.py`.
- **Teste (🔴):** integração, `consultar_alerta_de_outra_pessoa_deve_responder_404_igual_ao_inexistente`. Compara status e corpo das duas respostas.
- **Implementar (🟢):** `AlertaNaoEncontrado` no serviço; a rota converte em 404 com uma mensagem fixa.
- **Demo:** `curl` com o token de outra pessoa → 404.

### Passo 4 — OpenAPI documenta 200, 401, 404 e 422
- **Arquivos:** `tests/test_rotas_alertas.py`, `src/app/api/v1/sos.py`.
- **Teste (🔴):** unitário, `openapi_deve_documentar_respostas_200_401_404_e_422_da_consulta`, com o `$ref` de `AlertaStatusResposta` no 200. Mirror `openapi_deve_documentar_respostas_201_401_e_422_do_alerta`.
- **Implementar (🟢):** `summary`, `description` e `responses` na rota.
- **Demo:** `/docs` mostra a rota nova.

### Passo 5 — Documentação
- `README.md`: na seção do S.O.S, como consultar o status depois do `POST`.
- `docs/project-structure.md`: só se a descrição de `api/v1/sos.py` listar as rotas.
- `plans/what-needs-to-be-done.md`: marcar o item de backend da Tarefa 3 e deixar a listagem como opcional pendente.

## 5. Fechamento

- [x] `ruff check src tests migrations` e `pytest` verdes; com `TEST_DATABASE_URL`, a suíte inteira verde.
- [x] Nada de coordenada, mensagem ou telefone na resposta (o teste do passo 2 confere as chaves exatas).
- [x] Commit `feat(sos): consulta do status do alerta (Tarefa 3)` com como testar e o trailer.
