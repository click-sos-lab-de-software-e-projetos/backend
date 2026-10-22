# Plano — SOS-01: fechar a revisão da Yume no PR #3

> *"O caso parecia encerrado — sete 'Feito.' alinhados como testemunhas. Mas uma frase do resumo ficou sem resposta, e é sempre a frase esquecida que reabre o inquérito."*

**PR:** #3 `feat(sos): define schemas do alerta e autenticação por JWT` · branch `feat/sos-01-contrato-alerta`
**Revisão:** Dehrangerz9 (Yume) — **CHANGES_REQUESTED** em 21/10, 20h37, sobre o commit `54b4fcc`
**Estado atual:** `12de97f` enviado, 19 testes verdes, merge com `main` sem conflito, nova revisão solicitada e ainda não feita.

---

## 1. Diagnóstico: o que a Yume pediu × o que está em `12de97f`

| # | Onde (`54b4fcc`) | Pedido | Situação em `12de97f` |
|---|------------------|--------|-----------------------|
| R1 | `api/v1/sos.py:15` | "se um serviço não é implementado ele não deveria estar no código" (`_ServicoAindaNaoImplementado` → 501) | ✅ Serviço removido. ⚠️ **A rota, o `Protocol` e `api/v1/` também saíram** — foi além do pedido (ver §2). |
| R2 | `core/security.py:1` | remover (docstring do módulo) | ✅ |
| R3 | `core/security.py:7` | variável desnecessária (`ALGORITMO`) | ✅ `"HS256"` direto no `decode` |
| R4 | `schemas/sos.py:9` | criar `constants` com as variáveis do projeto | ✅ `src/app/constants.py` com `LIMITE_MENSAGEM_SOS` |
| R5 | `tests/test_sos_contrato.py:58` | nome do teste = componente + ação + resultado esperado | ✅ ex.: `requisicao_alerta_com_mensagem_acima_do_limite_deve_ser_rejeitada` |
| R6 | idem (resposta) | remover o prefixo `test_` | ✅ + `python_functions = ["*_deve_*"]` |
| R7 | `schemas/sos.py:17` e `:35` | remover comentário (docstrings das classes) | ✅ |
| **R8** | **resumo da revisão** | **"Cada PR deve buscar ter uma entrega de valor."** | ❌ **Sem resposta.** Ninguém respondeu, e o código caminhou no sentido oposto (ver §2). |

Verificado também:
- **Testes:** `pytest` → 19 passando. O único aviso é o do `httpx`, já registrado como dívida técnica com ticket próprio.
- **Comentários:** não sobrou comentário nem docstring em nenhum arquivo do PR. Os docstrings que restam (`main.py` e os `__init__.py`) vieram do scaffold e não fazem parte do diff, por isso ficam fora deste PR.

## 2. O problema que sobrou (R8)

A rota saiu e não voltou. Com isso, o PR entrega um schema e uma dependência de autenticação que **nenhuma rota da aplicação usa**: a dependência só é exercitada por um app de teste. E o card do SOS-01 em `docs/index.html` continua prometendo outra coisa:

- título: **"Definir schemas e rota de criação"**;
- *Pronto quando*: **"OpenAPI documentar corpos, respostas 201/401/422"** — isso só existe com a rota.

Ou seja, hoje o PR **não cumpre o próprio card**. A descrição do PR já faz as duas perguntas certas, mas nenhuma foi respondida:
1. Aceitar `test_*` além de `*_deve_*` como rede de segurança?
2. Mover o critério de OpenAPI 201/401/422 para o SOS-03?

Não existe código que resolva isso sozinho: uma rota sem persistência ou devolve 501 (o que a Yume rejeitou) ou mente com 201. **A saída é uma decisão de escopo.** É o passo 0.

## 3. Passo 0 — Obter a decisão (sem código)

Responder no PR, no fio do resumo da revisão. Rascunho:

> Yume, os pontos de linha estão aplicados em `12de97f`. Sobre "entrega de valor": sem a tabela `alertas_sos` (SOS-02), a rota só poderia devolver 501 ou um 201 falso. Por isso proponho:
> **(B)** este PR entrega a autenticação Bearer e o contrato do alerta. O valor está em desbloquear o AUTH-01, cujo critério de pronto exige que "um token emitido aqui seja aceito pela dependência de autenticação do SOS-01". A rota e a OpenAPI 201/401/422 vão para o SOS-03, já com persistência, e eu atualizo os cards no mesmo PR.
> **(C)** se preferir rota + persistência juntas, eu fecho este PR e o conteúdo dele entra no PR do SOS-03, depois do SOS-02.
> Qual prefere? E sobre `python_functions`: proponho manter só `*_deve_*` e acrescentar um teste que falha se aparecer um `test_` no projeto (ciclo 1).

**Recomendação: (B).** O motivo é que o AUTH-01 depende dessa autenticação, e a opção (C) segura o AUTH-01 até o SOS-03 ficar pronto.

## 4. Preparação

Seu working tree está na branch do SOS-02 com mudanças sem commit. **Não troque de branch ali.** O `pyproject.toml` e o `test_health.py` modificados colidem com a versão do SOS-01, e os arquivos novos do Alembic iriam junto, como passageiros clandestinos. Use um *worktree* separado:

```bash
cd "C:\Users\Lucas Perrone\Desktop\Estudos de Programação\Click S.O.S - Backend\backend"
git fetch origin
git worktree add ../backend-sos-01 feat/sos-01-contrato-alerta
cd ../backend-sos-01
git pull --ff-only                       # garante que está em 12de97f
pip install -e ".[dev]" && pre-commit install
pytest                                   # deve mostrar 19 passando antes de começar
```

## 5. Caminho B — ciclos (se a Yume aprovar)

### Ciclo 1 — Rede de segurança contra testes invisíveis
Responde à pergunta 1 do PR sem afrouxar a convenção que a Yume pediu (R5/R6).

🔴 **Teste** — `tests/test_convencoes.py`
- `arquivos_de_teste_nao_deve_conter_funcao_com_prefixo_test`: percorre `tests/**/*.py` com `ast` e falha listando arquivo:linha de cada `def test_*`.
- 🕵️ Ele passa de primeira, porque o projeto já está limpo. **Sabote**: crie um `def test_qualquer(): assert False` temporário. O pytest nem roda essa função (é a prova do perigo), mas o teste de convenção fica vermelho. Depois apague a sabotagem.

🟢 **Implementação:** só o próprio teste. Nenhum código de produção muda.

🔵 **Refatoração:** mensagem de falha clara, ex.: `"Renomeie para <componente>_<ação>_deve_<resultado>: tests/x.py:12 test_algo"`.

📦 `test(convencoes): impede testes com prefixo test_ que o pytest ignoraria`

### Ciclo 2 — Cobrir o segredo vindo do ambiente
Lacuna real: todo teste atual **substitui** `obter_segredo_jwt` por `dependency_overrides`, então a leitura de `JWT_SECRET_KEY` nunca é exercitada. E é justamente ela que o AUTH-01 vai usar.

🔴 **Testes** — em `tests/test_autenticacao.py`
- `obter_segredo_jwt_com_variavel_definida_deve_retornar_o_valor` (via `monkeypatch.setenv`, com valor fictício)
- `obter_segredo_jwt_sem_variavel_deve_lancar_erro`
- `obter_usuario_id_com_segredo_do_ambiente_deve_aceitar_token_assinado_com_ele`: ponta a ponta, **sem** override do segredo. Este é o teste que o AUTH-01 vai reaproveitar como garantia.
- São testes de caracterização: o código já existe. 🕵️ Sabote (`os.environ.get("JWT_SECRET")`) para vê-los falhar.

🟢 **Implementação:** nenhuma, se tudo passar.

🔵 **Refatoração:** se `"JWT_SECRET_KEY"` aparecer repetido entre código e teste, ele vira `NOME_VARIAVEL_SEGREDO_JWT` em `constants.py`, aplicando o espírito do R4. Se aparecer uma vez só, fica onde está, porque a Yume chamou de desnecessária uma variável de uso único (R3).

⚠️ **Fora do escopo:** fazer a API recusar subir sem `JWT_SECRET_KEY` (hoje ela sobe e responde 500). Isso já é dívida técnica registrada, com ticket próprio.

📦 `test(auth): cobre a leitura de JWT_SECRET_KEY do ambiente`

### Passo 3 — Alinhar os cards ao que o PR entrega (documentação, sem TDD)
Em `docs/index.html`:
- **SOS-01:** título → "Definir contrato do alerta e autenticação Bearer". *Pronto quando* → schemas aceitam 255 e rejeitam 256 caracteres, rejeitam `usuario_id` no corpo, e a dependência responde 401 para token ausente, expirado, mal assinado ou com `sub` inválido.
- **SOS-03:** acrescentar a rota `POST /api/v1/sos/alertas` e o critério "OpenAPI documenta corpos e respostas 201/401/422".

📦 `docs(tarefas): move rota e OpenAPI do SOS-01 para o SOS-03`

### Passo 4 — Fechar o PR
- [ ] `pytest` e `pre-commit run --all-files` verdes.
- [ ] `git push`. **Não** reescrever o histórico já revisado: os commits novos vão por cima de `12de97f`.
- [ ] Título do PR: tirar os três espaços antes de `feat(` (hoje está `"   feat(sos): ..."`).
- [ ] Descrição do PR: trocar "Pontos para decisão" pelas decisões tomadas e listar R1–R8 com os commits de cada um.
- [ ] Responder ao fio do R8 com o link do commit de documentação.
- [ ] Pedir nova revisão.

## 6. Caminho C — se a Yume preferir rota + persistência juntas
1. Fechar o PR #3 com um comentário apontando para o SOS-03. **Não apague a branch.**
2. Terminar o SOS-02 (`plans/SOS-02-migracoes-alertas.md`) e fazer merge.
3. Criar `feat/sos-03-persistir-alerta` a partir de `main` e fazer `git cherry-pick 54b4fcc 12de97f`.
4. Os ciclos 1 e 2 acima continuam válidos. A rota volta com o serviço real, e o fake fica restrito aos testes.
5. Avisar no card do AUTH-01 que a dependência de autenticação só chega com o SOS-03.

## 7. Pendência que não é deste PR
`src/app/workers/0001-refactor-sos-aplica-a-revis-o-do-PR-3.patch`, no working tree do SOS-02, é **byte a byte igual** ao `.patch` da pasta-mãe, e o conteúdo dele já está no GitHub em `12de97f`. Pode ser apagado sem perda.
