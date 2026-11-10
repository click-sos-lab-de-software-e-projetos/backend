# MAP-04: feedback comunitário das regiões

**Goal:** `POST /api/v1/mapa/regioes/{id}/feedbacks` grava um feedback `PENDENTE` de uma pessoa autenticada sobre um distrito, sem afetar score nem a consulta do mapa (Regra 05).
**Source:** `plans/what-needs-to-be-done.md` (Tarefa 6) + decisões da Yume (10/11).
**Feature flag:** nenhuma — rota nova; o app só passa a chamá-la na Tarefa 6 do frontend.

## Decisões
- D1 `{id}` na rota é o `id_publico` (`distrito-sp-1`), o mesmo que `/mapa/regioes` devolve. Desconhecido → 404.
- D2 Categorias: `ILUMINACAO`, `ASSALTO`, `ASSEDIO`, `MOVIMENTO`, `POLICIAMENTO`, `OUTRO`. Texto opcional, até 500 caracteres, com strip; vazio vira nulo; obrigatório quando a categoria é `OUTRO`. Acima de 500 → 422. Corpo com campo extra → 422.
- D3 Resposta 201: `{id, regiao_id (id_publico), categoria, status: "PENDENTE", criado_em}`. Não devolve texto nem usuário.
- D4 Tabela `feedbacks_comunidade`: `usuario_id` FK `usuarios` ON DELETE CASCADE (prepara a exclusão de conta da Tarefa 10); `regiao_id` FK `regioes_seguranca` ON DELETE RESTRICT; `status` com CHECK `PENDENTE`/`APROVADO`/`REJEITADO` (só `PENDENTE` é usado agora; moderação fica para depois); CHECK das categorias; CHECK "OUTRO exige texto"; índices em `regiao_id` e `usuario_id`.
- D5 Sem modelo ORM: a FK aponta para `regioes_seguranca`, que não está em `Base.metadata`. SQL com `text()`, como `services/mapa.py`; `test_modelos_orm.py` continua esperando 4 tabelas.
- D6 Token válido de pessoa que não existe mais → 401, como em `POST /sos/alertas`.
- D7 Sem limite de envios no MVP.

## Out of scope
- Moderação, listagem e edição de feedbacks.
- Uso do feedback no score (peso zero; `score_oficial = score_final`).
- Frontend.

## Step 1: migração 0009 cria `feedbacks_comunidade`
- **Files**: `migrations/versions/0009_cria_feedbacks_comunidade.py` (novo), `tests/integracao/test_migracoes_feedbacks.py` (novo).
- **Test (red)**: integração — depois de `head`, a tabela tem PK, as 2 FKs (CASCADE em usuário, RESTRICT em região), CHECK de categorias, status e "OUTRO exige texto", e índices em `regiao_id`/`usuario_id`; apagar a pessoa apaga o feedback dela; categoria fora da lista é recusada pelo banco. Mirror `tests/integracao/test_migracoes_mapa.py` (`restricoes`, `definicoes_de_indices` de `integracao/inspecao.py`). O ida-e-volta de `test_migracoes_ida_e_volta.py` já cobre a nova revisão.
- **Implement (green)**: migração no estilo de `0006`/`0007` (`gen_random_uuid()`, `criado_em` com `now()`), `downgrade` removendo a tabela.
- **Refactor**: n/a
- **Demo**: `alembic upgrade head` no banco de teste cria a tabela.
- **Depends on**: none

## Step 2: schema da requisição valida categoria e texto
- **Files**: `src/app/schemas/mapa.py`, `src/app/constants.py` (`CATEGORIAS_FEEDBACK`, `LIMITE_TEXTO_FEEDBACK = 500`), `tests/test_schemas_mapa.py` (novo).
- **Test (red)**: unidade — aceita cada categoria; recusa categoria desconhecida, texto com 501 caracteres, campo extra e `OUTRO` sem texto (ou só com espaços); texto em branco vira `None`; texto com 500 é aceito. Mirror `tests/test_schemas_sos.py`.
- **Implement (green)**: `CriarFeedbackRequisicao` (categoria `Literal`, texto como `MensagemLivre` de `schemas/sos.py`, `extra="forbid"`, validador de modelo para `OUTRO`) e `FeedbackCriadoResposta`.
- **Refactor**: n/a
- **Demo**: testes verdes.
- **Depends on**: none

## Step 3: rota responde 401/422 sem tocar no banco e aparece no OpenAPI
- **Files**: `src/app/api/v1/mapa.py`, `tests/test_rotas_mapa.py`.
- **Test (red)**: unidade — sem token ou com token inválido → 401 sem abrir sessão; corpo inválido → 422 sem chamar o serviço (com `obter_sessao` sobrescrito por `lambda: None`, pelo quirk do FastAPI registrado no MAP-05); OpenAPI documenta 201, 401, 404 e 422. Mirror os testes de `/regioes` no mesmo arquivo.
- **Implement (green)**: `POST /regioes/{regiao_id}/feedbacks` com `status_code=201`, delegando para `servico.criar_feedback`; `RegiaoNaoEncontrada` → 404, `UsuarioNaoEncontrado` → 401 com `WWW-Authenticate`, como em `api/v1/sos.py`.
- **Refactor**: n/a
- **Demo**: `/docs` mostra a rota.
- **Depends on**: Step 2

## Step 4: feedback é gravado como PENDENTE
- **Files**: `src/app/services/mapa.py` (`criar_feedback`, exceções), `tests/integracao/test_api_feedbacks.py` (novo).
- **Test (red)**: integração — `POST` com distrito existente responde 201 com o corpo de D3; a linha gravada tem a pessoa do token, o UUID interno da região, categoria, texto e `PENDENTE`; `id` desconhecido → 404 sem gravar; token de pessoa inexistente → 401 sem gravar. Mirror `tests/integracao/test_api_mapa.py` (cliente) e `test_api_alertas.py` (`inserir_usuario` + `_token(usuario_id)`).
- **Implement (green)**: buscar a região por `id_publico` e a pessoa; `INSERT ... RETURNING id, criado_em`.
- **Refactor**: n/a
- **Demo**: `curl -X POST .../regioes/distrito-sp-1/feedbacks` com token devolve 201.
- **Depends on**: Steps 1, 3

## Step 5: feedback não altera score nem aparece no mapa
- **Files**: `tests/integracao/test_api_feedbacks.py`.
- **Test (red)**: integração — com ocorrências e distritos (fábricas), recalcular, guardar `GET /mapa/regioes`; enviar feedbacks em todas as categorias; recalcular de novo → resposta de `/mapa/regioes` idêntica e `score_oficial`/`score_final`/`cor_hex` iguais. Deve passar sem código novo (garantia da Regra 05); conferir com sabotagem temporária (ex.: somar feedbacks no score) para provar que o teste pega.
- **Implement (green)**: n/a esperado.
- **Refactor**: n/a
- **Demo**: teste verde.
- **Depends on**: Step 4

## Step 6: documentação e checklist
- **Files**: `README.md` (seção Mapa de risco + frase inicial), `docs/project-structure.md`, `plans/what-needs-to-be-done.md` (marcar os 3 itens de backend da Tarefa 6).
- **Demo**: README descreve a rota, as categorias e que o feedback não muda o mapa.
- **Depends on**: Step 5

## Open questions / assumptions
- No Neon, a Yume roda `alembic upgrade head` (0009) antes do app usar a rota.
- Commit único (`feat(mapa): feedback comunitário (MAP-04)`), como MAP-05.
