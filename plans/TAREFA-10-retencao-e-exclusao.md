# TAREFA-10: retenção de 180 dias e exclusão de conta

**Goal:** alertas com mais de 180 dias perdem coordenadas, mensagem e vínculo com contatos (script manual idempotente); `DELETE /api/v1/auth/me` apaga a pessoa, os contatos e os feedbacks dela e anonimiza os alertas na hora.
**Source:** `plans/what-needs-to-be-done.md` (Tarefa 10, YUME-03) + decisões da Yume (10/11).
**Feature flag:** nenhuma — rota e script novos.

## Decisões
- D1 Migração 0010 em `alertas_sos`: `usuario_id` vira nullable com FK `ON DELETE SET NULL` (antes CASCADE); `localizacao` vira nullable; nova coluna `anonimizado_em timestamptz NULL`; CHECK `localizacao IS NOT NULL OR anonimizado_em IS NOT NULL`. O downgrade apaga os alertas anonimizados antes de voltar as colunas para NOT NULL (não há como restaurar coordenadas).
- D2 Anonimizar um alerta = `localizacao` e `mensagem` NULL, `anonimizado_em = now()`; nas `tentativas_envio_sos` dele, `contato_id` NULL. Status, tentativas e datas ficam para estatística.
- D3 Retenção: `RETENCAO_ALERTAS_DIAS = 180`, contada por `criado_em`. Alertas já anonimizados não são tocados de novo (idempotente).
- D4 Rotina: só o script `scripts/anonimizar_alertas.py`, rodado à mão; sem `--gravar` mostra quantos seriam anonimizados e não grava (como `recalcular_mapa.py`). Sem agendamento no MVP.
- D5 `DELETE /api/v1/auth/me` com corpo `{senha}` → 204. Senha errada → 400 sem apagar nada. Pessoa do token inexistente → 401. Corpo inválido → 422.
- D6 Alerta `PENDENTE` da pessoa → 409, sem apagar nada (espera o envio terminar).
- D7 Ordem na exclusão, numa transação: trava a linha de `usuarios` (`FOR UPDATE`, como em `services/contatos.py`), confere senha e alerta pendente, anonimiza os alertas (D2), apaga a pessoa. Contatos e feedbacks caem por CASCADE; `alertas_sos.usuario_id` vira NULL por SET NULL; `tentativas.contato_id` já é SET NULL.

## Out of scope
- Agendamento da rotina (GitHub Actions/cron).
- Frontend (tela de privacidade, consentimento LGPD, botão de excluir).
- Exportação dos dados da pessoa.

## Step 1: migração 0010 permite alerta anonimizado
- **Files**: `migrations/versions/0010_anonimizacao_alertas.py` (novo), `src/app/db/models.py` (`AlertaSos`: `usuario_id` e `localizacao` opcionais, `anonimizado_em`, FK SET NULL, CHECK), `tests/integracao/test_migracoes_alertas.py` ou o teste de migração de alertas existente.
- **Test (red)**: integração — depois de `head`, a FK de `usuario_id` é `ON DELETE SET NULL`; `localizacao` e `usuario_id` aceitam NULL; o CHECK recusa `localizacao` NULL sem `anonimizado_em`; apagar a pessoa mantém o alerta com `usuario_id` NULL. `test_modelos_orm.py` (ORM = migração) e `test_migracoes_ida_e_volta.py` seguem verdes. Mirror `tests/integracao/test_migracoes_feedbacks.py`.
- **Implement (green)**: migração com `alter_column`, troca da FK e CHECK nomeado; modelo ORM igual.
- **Refactor**: n/a
- **Demo**: `alembic upgrade head` no banco de teste.
- **Depends on**: none

## Step 2: serviço anonimiza alertas vencidos de forma idempotente
- **Files**: `src/app/services/retencao.py` (novo: `anonimizar_alertas_vencidos(sessao, agora) -> ResumoAnonimizacao`, `anonimizar_alertas_da_pessoa`), `src/app/constants.py`, `tests/integracao/test_retencao.py` (novo).
- **Test (red)**: integração — com alertas de 181 e de 179 dias (fábrica `inserir_alerta` com `criado_em`) e tentativas ligadas a contatos: só o de 181 perde coordenadas, mensagem e `contato_id` das tentativas, e ganha `anonimizado_em`; status, `tentativas` e `criado_em` ficam; a 2ª execução não muda nada e devolve 0. Sem commit dentro do serviço (como `recalcular_regioes`).
- **Implement (green)**: dois `UPDATE` (alertas e tentativas) com `RETURNING`/rowcount; `agora` como parâmetro para teste determinístico.
- **Refactor**: n/a
- **Demo**: teste verde.
- **Depends on**: Step 1

## Step 3: script `anonimizar_alertas.py`
- **Files**: `scripts/anonimizar_alertas.py` (novo), teste no padrão dos testes de `scripts/recalcular_mapa.py`.
- **Test (red)**: integração — sem `--gravar` imprime a contagem e não altera nada; com `--gravar` anonimiza e grava. Mirror o teste do `recalcular_mapa.py`.
- **Implement (green)**: igual ao `recalcular_mapa.py` (mesma leitura de `DATABASE_URL`, rollback sem `--gravar`).
- **Refactor**: n/a
- **Demo**: `python scripts/anonimizar_alertas.py` mostra o resumo.
- **Depends on**: Step 2

## Step 4: schema e rota de exclusão respondem 401/422 sem tocar no banco
- **Files**: `src/app/schemas/auth.py` (`ExcluirContaRequisicao {senha}`), `src/app/api/v1/auth.py`, `tests/test_schemas_auth.py`, `tests/test_rotas_auth.py`.
- **Test (red)**: unidade — senha vazia, ausente ou campo extra → inválido; sem token → 401 sem abrir sessão; corpo inválido → 422 sem chamar o serviço; OpenAPI documenta 204/400/401/409/422. Mirror os testes da troca de senha (Tarefa 7).
- **Implement (green)**: `DELETE /me` delegando a `servico.excluir_conta`; `SenhaAtualIncorreta` → 400, `AlertaEmEnvio` → 409, `UsuarioNaoEncontrado` → 401.
- **Refactor**: n/a
- **Demo**: `/docs` mostra a rota.
- **Depends on**: none

## Step 5: exclusão de conta apaga a pessoa e anonimiza os alertas
- **Files**: `src/app/services/auth.py` (`excluir_conta`, `AlertaEmEnvio`), `tests/integracao/test_api_auth.py` (ou `test_exclusao_conta.py` novo).
- **Test (red)**: integração — pessoa com contatos, feedback e alertas `ENVIADO` com tentativas: 204; `usuarios`, `contatos_emergencia` e `feedbacks_comunidade` da pessoa somem; alertas ficam com `usuario_id`, `localizacao`, `mensagem` NULL e `anonimizado_em` preenchido; tentativas sem `contato_id`; o token antigo passa a dar 401 em `/me`; dados de outra pessoa intactos. Senha errada → 400 e nada muda. Alerta `PENDENTE` → 409 e nada muda.
- **Implement (green)**: D7, reusando `anonimizar_alertas_da_pessoa` do Step 2.
- **Refactor**: n/a
- **Demo**: `curl -X DELETE .../auth/me -d '{"senha": ...}'` com token.
- **Depends on**: Steps 2, 4

## Step 6: documentação e checklist
- **Files**: `README.md` (rota, script, retenção de 180 dias, aviso do downgrade), `docs/project-structure.md`, `plans/what-needs-to-be-done.md` (marcar os 2 itens de backend da Tarefa 10, anotando que o agendamento ficou para depois).
- **Demo**: README descreve a retenção e a exclusão.
- **Depends on**: Steps 3, 5

## Open questions / assumptions
- Alerta preso em `PENDENTE` por falha do worker também bloqueia a exclusão (409) até virar `ERRO`; `_marcar_erro_se_pendente` já cobre as falhas conhecidas.
- A rotina anonimiza também alerta `PENDENTE` com mais de 180 dias (privacidade acima do status).
- No Neon, a Yume roda `alembic upgrade head` (0008, 0009 e 0010).
- Commit único `feat(privacidade): retenção de 180 dias e exclusão de conta (Tarefa 10)`.
