# Plano — Tarefa 5: mapa de risco (MAP-05 a MAP-08, backend)

> Cada passo abaixo é um ciclo de TDD: 🔴 escreva o teste e veja-o falhar → 🟢 escreva o mínimo para passar → 🔵 refatore com os testes verdes.
> **Um commit por ticket**, direto na `main`: MAP-01/02 (passo 0), MAP-05 (passos 1 a 4) e MAP-06 a MAP-08 (passos 5 a 8).

**Tickets:** MAP-05 a MAP-08 · Tarefa 5 de `plans/what-needs-to-be-done.md` (só backend). MAP-03 fica para depois (D1).
**Depende de:** migrações `0006` e `0007` (commit `1bc6e3b`).
**Feature flag:** nenhuma. A rota é nova e só leitura; o app ainda chama `/occurrences`.
**Pronto quando:** um comando recalcula score, cor e raio dos distritos pela regra decidida, e `GET /api/v1/mapa/regioes` devolve os distritos próximos sem expor dado interno.

---

## 1. O que foi apurado (09/11/2026)

- MAP-01/02 já estão no Git (`1bc6e3b`). Os 3 testes de `tests/integracao/test_migracoes_mapa.py` com `_devem_` nunca rodaram: o pytest só coleta `*_deve_*` (`pyproject.toml:33`). Forçados com `-o python_functions`, passam.
- Não há modelo ORM para o mapa. `tests/integracao/test_modelos_orm.py` compara `Base.metadata` com o banco migrado e exige exatamente as 4 tabelas do épico; mapear `regioes_seguranca` puxaria `interno.fontes_geograficas` pela FK.
- `regioes_seguranca`: `id_publico`, `nome`, `limites` (MultiPolygon 4326), `centroide`, `score_oficial` e `score_final` (`Numeric(12,2)`), `cor_hex` (`CHECK ^#[0-9A-F]{6}$`), `raio_metros` (`> 0`), `atualizado_em`. `interno.ocorrencias_ssp`: `localizacao` (Point 4326, GiST), `data_ocorrencia` (pode ser nula), `peso` de 1 a 3.
- Cores já usadas no Neon: verde `#22C55E` (default) e vermelho `#EF4444`.
- Fábricas em `tests/integracao/fabricas.py` só cobrem usuário, contato, alerta e tentativa. `regiao_nova_deve_usar_defaults_do_neon` mostra o SQL mínimo de uma região.
- Padrão de script: `scripts/token_dev.py` (argparse, `main(argv) -> int`, testes em `tests/test_token_dev.py` e `tests/integracao/test_token_dev_banco.py`).
- O `.env` local não tem `DATABASE_URL` do Neon; os testes usam só o PostGIS descartável.

## 2. Decisões

Aprovadas pela Yume em 09/11:

| # | Ponto | Decisão |
|---|-------|---------|
| D1 | MAP-03 (script de carga) | Fica para depois: precisa dos arquivos reais da SSP e do GeoSampa. |
| D2 | Janela de 6 meses | Contada a partir da **ocorrência mais recente** no banco, não de hoje. Ocorrências sem data ficam fora. |
| D3 | Quais distritos a rota devolve | Os que têm a **borda** a até `raio` do ponto, ordenados pela distância até a borda (o distrito onde a pessoa está vem primeiro, com distância 0). Desempate por `id_publico`. |
| D4 | Formato do score | Inteiro de 0 a 100, arredondado. Gravado já inteiro em `score_oficial` e `score_final`. |
| D5 | Neon | Eu crio o comando; a Yume roda no Neon quando quiser. |

Propostas neste plano (confirmar na aprovação):

| # | Ponto | Proposta |
|---|-------|----------|
| D6 | Acesso ao banco | `services/mapa.py` com SQL explícito (`text()`), sem modelo ORM: as tabelas são da carga, e o teste de `Base.metadata` continua valendo. |
| D7 | Cor amarela | `#EAB308` (mesma paleta do verde e do vermelho já usados). |
| D8 | Distrito sem ocorrências ou maior densidade 0 | Score 0, verde. |
| D9 | Ocorrência na divisa | Conta para cada distrito que a contém (`ST_Covers`). Efeito desprezível em 96 distritos. |
| D10 | Comando de recálculo | `scripts/recalcular_mapa.py`: sem `--gravar`, só mostra o resumo (distritos por cor, janela usada); com `--gravar`, regrava `score_oficial`, `score_final`, `cor_hex`, `raio_metros` e `atualizado_em` numa transação. Funciona contra o Neon (diferente do `token_dev.py`). O resumo não imprime a URL do banco. |
| D11 | Autenticação da rota | Exige Bearer, como as demais rotas privadas. O app só abre o mapa logado. |
| D12 | Corpo da resposta | Lista de `{id, nome, centroide: {latitude, longitude}, score, cor_hex, raio_metros}`; `id` é o `id_publico`. Nunca o UUID interno, os limites nem dados das ocorrências. |
| D13 | Validação | `latitude` e `longitude` obrigatórias e no intervalo; `raio` inteiro, padrão 3000, de 1 a 10000; fora disso, 422. |

## 3. Fora do escopo

- MAP-03 (D1). Feedback comunitário (Tarefa 6): hoje o score final é igual ao oficial.
- Frontend do mapa. Rodar o recálculo no Neon (D5).

## 4. Passos

### Passo 0 — MAP-01/02: os testes do schema do Neon passam a rodar
- **Arquivos:** `tests/integracao/test_migracoes_mapa.py`, `plans/what-needs-to-be-done.md`.
- Renomear `_devem_` → `_deve_` nas 3 funções. Conferir que a coleta sobe de 3 testes (mais os parametrizados). Marcar MAP-01/02.
- Não mexer em `tests/test_mensagem_sos.py:60` (fora da Tarefa 5; avisar).
- **Commit:** `test(db): testes do schema do mapa voltam a ser coletados (MAP-01/02)`.

### Passo 1 — Faixa de cor a partir do score
- **Arquivos:** `src/app/services/score_mapa.py` (novo), `src/app/constants.py`, `tests/test_score_mapa.py` (novo).
- **Teste (🔴):** unitário, `cor_deve_seguir_as_3_faixas_do_score`, parametrizado nas bordas 0, 33, 34, 66, 67 e 100.
- **Implementar (🟢):** constantes das cores (D7) e dos limites 34/67; função pura da cor.
- **Demo:** teste verde.

### Passo 2 — Score por densidade relativa à maior densidade
- **Arquivos:** os mesmos.
- **Teste (🔴):** unitário, `score_deve_ser_densidade_sobre_a_maior_densidade_vezes_100` (o mais denso vale 100, metade da densidade vale 50, arredondamento inteiro) e `sem_ocorrencias_todos_devem_ter_score_0_e_cor_verde` (D8).
- **Implementar (🟢):** função pura que recebe, por distrito, soma dos pesos e área em km², e devolve score e cor.
- **Demo:** teste verde.

### Passo 3 — Recálculo no banco com a janela de 6 meses
- **Arquivos:** `src/app/services/mapa.py` (novo), `tests/integracao/fabricas.py`, `tests/integracao/test_recalculo_mapa.py` (novo).
- **Teste (🔴):** integração, `recalcular_deve_gravar_score_cor_e_raio_dos_distritos`. Dois distritos quadrados perto de (0, 0), com ocorrências de pesos diferentes, uma fora da janela (mais de 6 meses antes da mais recente, D2), uma sem data e uma fora de qualquer distrito. Confere score, cor, raio por área equivalente e `atualizado_em`. Fábricas novas: `inserir_fonte_geografica`, `inserir_regiao`, `inserir_carga_ssp`, `inserir_ocorrencia`.
- **Implementar (🟢):** uma consulta agrega pesos por distrito (`ST_Covers`, D9) e área (`ST_Area(limites::geography)`); a função pura do passo 2 calcula; um `UPDATE` por distrito grava. Devolve um resumo (contagem por cor e janela) para o comando.
- **Demo:** teste verde.

### Passo 4 — Comando `scripts/recalcular_mapa.py`
- **Arquivos:** `scripts/recalcular_mapa.py` (novo), `tests/integracao/test_recalculo_mapa.py`.
- **Teste (🔴):** integração, `comando_sem_gravar_nao_deve_alterar_o_banco` e `comando_com_gravar_deve_regravar_os_distritos`, chamando `main([...])` como em `test_token_dev_banco.py`.
- **Implementar (🟢):** D10.
- **Docs:** README (como rodar no Neon, com `--gravar` só depois de olhar o resumo), `docs/project-structure.md` (`services/mapa.py`, `score_mapa.py`, o script), marcar MAP-05.
- **Commit:** `feat(mapa): recálculo do score dos distritos (MAP-05)`.

### Passo 5 — Sem token, a rota responde 401 sem abrir o banco
- **Arquivos:** `src/app/api/v1/mapa.py` (novo), `src/app/main.py`, `tests/test_rotas_mapa.py` (novo).
- **Teste (🔴):** unitário, mirror `tests/test_rotas_alertas.py` (sessão proibida).
- **Implementar (🟢):** router `/api/v1/mapa`, `GET /regioes`, `UsuarioId` antes de `Sessao`.

### Passo 6 — Parâmetros validados
- **Arquivos:** `src/app/schemas/mapa.py` (novo), `src/app/api/v1/mapa.py`, `tests/test_rotas_mapa.py`.
- **Teste (🔴):** unitário, `consulta_com_parametro_invalido_deve_responder_422` (sem latitude, latitude 91, raio 0, raio 10001) sem tocar no banco; OpenAPI documenta 200, 401 e 422.
- **Implementar (🟢):** D13.

### Passo 7 — Distritos próximos, do mais perto ao mais longe, no máximo 50
- **Arquivos:** `src/app/services/mapa.py`, `src/app/schemas/mapa.py`, `tests/integracao/test_api_mapa.py` (novo).
- **Teste (🔴):** integração (MAP-08), com distritos quadrados perto de (0, 0):
  - `regioes_deve_devolver_o_distrito_do_ponto_primeiro_e_os_vizinhos_em_ordem`;
  - `regioes_fora_do_raio_nao_devem_aparecer` (inclui o raio padrão de 3000 m);
  - `regioes_deve_devolver_no_maximo_50`;
  - `regioes_deve_expor_so_os_campos_publicos` (chaves exatas, D12).
- **Implementar (🟢):** consulta com `ST_DWithin` e `ST_Distance` em `geography` (D3), `LIMIT` 50; schema `RegiaoResposta`.
- **Demo:** depois do recálculo no banco local, `curl` com token devolve os distritos coloridos.

### Passo 8 — Documentação e fechamento
- README: rota do mapa e o fluxo "carga (fora do Git por enquanto) → recálculo → rota". `docs/project-structure.md`: `v1/mapa.py`. Marcar MAP-06, MAP-07 e MAP-08.
- **Commit:** `feat(mapa): rota das regiões de risco próximas (MAP-06 a MAP-08)`.

## 5. Fechamento

- [ ] `ruff check src tests migrations scripts` e `pytest` verdes; com `TEST_DATABASE_URL`, a suíte inteira verde.
- [ ] Nada de URL do Neon ou credencial no diff.
- [ ] Avisar a Yume: rodar `python scripts/recalcular_mapa.py` no Neon, conferir o resumo e só então `--gravar`.

## 6. Riscos

- **Data mais recente errada:** se a carga tiver uma ocorrência com data futura por erro, a janela anda para frente e esvazia o mapa. O resumo do comando mostra a janela usada, para conferir antes de `--gravar`.
- **Desempenho:** o `cast` para `geography` não usa o índice GiST, mas são 96 distritos e 288 mil pontos agregados só no recálculo, fora da requisição.
