# MAP-03: carga das ocorrências da SSP e dos distritos do GeoSampa

**Goal:** script reproduzível que carrega o xlsx da SSP e o geojson do GeoSampa nas tabelas do mapa, idempotente por `arquivo_sha256` e `chave_fonte`, e recalcula os distritos no fim.
**Source:** `plans/what-needs-to-be-done.md` (MAP-03) + auditoria só-leitura do Neon (10/11) + decisões da Yume.
**Feature flag:** nenhuma — script offline, não muda rota.

## Auditoria do Neon (fatos que o plano segue)
- `cargas_ssp`: 1 carga `SPDadosCriminais_2026.xlsx`, sha `a2f0…`, 296.566 lidas / 288.487 inseridas / 8.078 rejeitadas (`{"coordenadas_invalidas": 8078}`).
- Todas as ocorrências têm `municipio_ibge = 3550308` (filtro pela coluna `COD IBGE`); `municipio_nome` vem de `NOME_MUNICIPIO`.
- 32.781 ocorrências gravadas em `POINT(0 0)` (lat/long `0` inteiro no xlsx). Não afetam score (fora dos distritos).
- **Peso** = maior entre peso da `NATUREZA_APURADA` e da `RUBRICA`, por palavra-chave sem acento/maiúsculas: 3 = homicídio, latrocínio, estupro, feminicídio, extorsão mediante sequestro, vicaricídio; 2 = roubo, lesão corporal, arma; senão 1. Bate em 100% das 288.487 linhas.
- **`chave_fonte` antiga não reproduzível** (~260 mil fórmulas testadas). Não existe `NUM_BO` no banco.
- xlsx atual (`~/Downloads`, sha `c1f9…`): abas `JAN-JUN_2026` e `JUL-DEZ_2026` com 30 colunas + aba de dicionário. 260.355 linhas da capital; 29.109 em (0,0); 7.935 com `'-'`/`'NULL'`. Chave natural `(NOME_DELEGACIA, NUM_BO, ANO_BO, RUBRICA, DESCR_CONDUTA, NATUREZA_APURADA)` é única.
- `HORA_OCORRENCIA_BO` vem como texto (`'NULL'` quando vazio); datas como `datetime`; lat/long como float, int ou texto.
- Distritos: 96, `id_publico = distrito-sp-{cd_distrito_municipal}`, `nome` = `nm_distrito_municipal`, `limites` MultiPolygon 4326, `centroide = ST_Centroid(limites)`.

## Decisões
- D1 `chave_fonte` = sha256 hex de `delegacia|num_bo|ano_bo|rubrica|conduta|natureza` (texto com strip, `NULL`/vazio → ""). Documentada no módulo.
- D2 Arquivo com `arquivo_sha256` já `CONCLUIDA` → no-op, informa a carga existente. `FALHOU` → reprocessa a mesma linha de `cargas_ssp`.
- D3 `chave_fonte` repetida → atualiza a linha (todos os campos + `carga_id` da carga nova), conta em `atualizadas`.
- D4 Ignora município ≠ 3550308 (fora de `linhas_lidas`). Rejeita: coordenada ausente/não numérica, (0,0) ou fora de lat [-90,90]/long [-180,180]. `erros_amostra` = contagem por motivo (`coordenadas_invalidas`, `campos_obrigatorios`).
- D5 `--substituir`: na mesma transação, apaga ocorrências cujo `carga_id` ≠ carga atual. Registros de `cargas_ssp` antigos ficam.
- D6 Dry-run por padrão (rollback + resumo); `--gravar` faz commit. Após carga gravada, roda `recalcular_regioes` na mesma transação.
- D7 `fonte_url`/`licenca` por argumento com padrão SSP-SP (portal de transparência, dados públicos) e GeoSampa (dados abertos).
- D8 `openpyxl` vai no extra `dev` do `pyproject.toml` (script e testes rodam com dev; imagem de produção não precisa).
- D9 Sem ORM para as tabelas do mapa (`test_modelos_orm.py` espera 4 tabelas): SQL com `text()`, como `services/mapa.py`.

## Out of scope
- Rodar no Neon (a Yume roda: `distritos`, depois `ssp --substituir`, sempre dry-run antes).
- Apagar as ocorrências em (0,0) já gravadas no Neon (somem com `--substituir`).
- Baixar arquivos da internet; agendamento.

## Step 1: regras puras de peso e chave da ocorrência
- **Files**: `src/app/services/carga_ssp.py` (novo), `tests/test_carga_ssp.py` (novo).
- **Test (red)**: unidade — peso usa o maior entre natureza e rubrica (casos auditados: `FURTO - OUTROS` + rubrica Roubo → 2; `APREENSÃO DE ENTORPECENTES` + Homicídio → 3; furto puro → 1; acento/caixa ignorados); `chave_fonte` é estável, 64 hex, muda se qualquer campo da chave natural muda, e trata `'NULL'`/None/espaços igual. Mirror `tests/test_score_mapa.py`.
- **Implement (green)**: funções puras `calcular_peso(natureza, rubrica)` e `calcular_chave_fonte(...)`; palavras-chave como constantes no módulo.
- **Refactor**: n/a
- **Demo**: testes de unidade verdes.
- **Depends on**: none

## Step 2: linha do xlsx vira ocorrência ou motivo de rejeição
- **Files**: `src/app/services/carga_ssp.py`, `tests/test_carga_ssp.py`.
- **Test (red)**: unidade — dicionário com as colunas da SSP vira ocorrência normalizada (data, hora `HH:MM` ou `'NULL'`→None, período, bairro, lat/long de float/int/texto com vírgula); fora da capital → ignorada; `'-'`, `'NULL'`, (0,0) e fora do intervalo → rejeitada com `coordenadas_invalidas`.
- **Implement (green)**: dataclass de ocorrência + função `interpretar_linha(linha) -> Ocorrencia | Rejeicao | None`.
- **Refactor**: n/a
- **Demo**: testes de unidade verdes.
- **Depends on**: Step 1

## Step 3: leitura de todas as abas de dados do xlsx
- **Files**: `src/app/services/carga_ssp.py`, `tests/test_carga_ssp.py`, `pyproject.toml` (openpyxl no dev).
- **Test (red)**: unidade — xlsx gerado com openpyxl em `tmp_path` com aba de dicionário + 2 abas de dados → itera só as linhas das abas cujo cabeçalho tem as colunas da SSP, ignora linhas vazias; sha256 do arquivo calculado em streaming.
- **Implement (green)**: `ler_linhas_xlsx(caminho)` (read_only) e `sha256_arquivo(caminho)`.
- **Refactor**: n/a
- **Demo**: testes verdes.
- **Depends on**: Step 2

## Step 4: carga grava ocorrências e registra a carga
- **Files**: `src/app/services/carga_ssp.py`, `tests/integracao/test_carga_ssp.py` (novo), `tests/integracao/fabricas.py` (se precisar).
- **Test (red)**: integração — `carregar_ssp(sessao, linhas, sha, nome, fonte_url, licenca)` insere ocorrências com geometria 4326 e peso, cria `cargas_ssp` `CONCLUIDA` com lidas/inseridas/rejeitadas/`erros_amostra` e `finalizado_em`. Mirror `tests/integracao/test_recalculo_mapa.py`.
- **Implement (green)**: insert em lotes (~5 mil) com `ON CONFLICT (chave_fonte) DO UPDATE`; contar inseridas × atualizadas.
- **Refactor**: n/a
- **Demo**: teste de integração verde.
- **Depends on**: Step 3

## Step 5: idempotência por arquivo e por chave
- **Files**: idem Step 4.
- **Test (red)**: integração — mesmo sha `CONCLUIDA` não altera nada e retorna a carga existente; arquivo novo com chave repetida atualiza a linha (campos e `carga_id`) e conta em `atualizadas`; sha `FALHOU` é reprocessado.
- **Implement (green)**: checagem do sha antes de processar; reaproveitar linha `FALHOU`.
- **Refactor**: n/a
- **Demo**: teste verde.
- **Depends on**: Step 4

## Step 6: --substituir apaga ocorrências de cargas anteriores
- **Files**: idem Step 4.
- **Test (red)**: integração — com carga antiga (fábrica) + carga nova `substituir=True`, só sobram ocorrências da nova; registro antigo de `cargas_ssp` continua; sem a flag, as antigas ficam.
- **Implement (green)**: `DELETE` por `carga_id <> :atual` na mesma transação; contar removidas no resumo.
- **Refactor**: n/a
- **Demo**: teste verde.
- **Depends on**: Step 5

## Step 7: carga dos distritos do GeoSampa
- **Files**: `src/app/services/carga_distritos.py` (novo), `tests/integracao/test_carga_distritos.py` (novo).
- **Test (red)**: integração — geojson inventado (2 features, Polygon e MultiPolygon, propriedades `cd_distrito_municipal`/`nm_distrito_municipal`) cria `fontes_geograficas` e 2 regiões `distrito-sp-N` com MultiPolygon, `centroide = ST_Centroid`, raio > 0; repetir o mesmo sha é no-op; arquivo novo atualiza nome/limites por `id_publico` sem zerar score.
- **Implement (green)**: `json` da stdlib + `ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(...),4326))`; raio inicial via `score_mapa`.
- **Refactor**: n/a
- **Demo**: teste verde.
- **Depends on**: none

## Step 8: script `scripts/carregar_mapa.py`
- **Files**: `scripts/carregar_mapa.py` (novo), `tests/integracao/test_carga_ssp.py` (teste do script).
- **Test (red)**: integração — `main(["ssp", xlsx])` não grava e imprime resumo; com `--gravar` grava e recalcula os distritos; `distritos geojson --gravar` grava; a saída nunca contém a URL do banco. Mirror carregamento por `importlib` de `test_recalculo_mapa.py`.
- **Implement (green)**: argparse com subcomandos `ssp` (`--substituir`, `--fonte-url`, `--licenca`) e `distritos`; `--gravar`; padrão de `scripts/recalcular_mapa.py`.
- **Refactor**: n/a
- **Demo**: `python scripts/carregar_mapa.py ssp ~/Downloads/SPDadosCriminais_2026.xlsx` no banco de teste mostra lidas/inseridas/rejeitadas.
- **Depends on**: Steps 6, 7

## Step 9: documentação e checklist
- **Files**: `README.md` (seção Mapa de risco), `docs/project-structure.md`, `plans/what-needs-to-be-done.md` (marcar MAP-03).
- **Test (red)**: n/a (docs).
- **Implement (green)**: ordem de execução no Neon (dry-run → `--gravar`; `distritos` antes de `ssp --substituir`), regra de peso e chave.
- **Demo**: README.
- **Depends on**: Step 8

## Open questions / assumptions
- Arquivo GeoSampa original não está na máquina; assumo propriedades `cd_distrito_municipal`/`nm_distrito_municipal` (confirmado pela Yume). Se diferente, flags `--campo-codigo`/`--campo-nome`.
- `linhas_lidas` conta só linhas da capital (o Neon parece ter feito assim; não dá para confirmar sem o arquivo antigo).
- Commit único no fim (MAP-03) ou um por step? Assumo um só, como MAP-05.

## Implementação
- Testes de integração da carga SSP em `tests/integracao/test_carga_ssp_banco.py` (padrão de `test_token_dev_banco.py`), para não confundir com o teste de unidade de mesmo nome.
- Carga real no banco de teste local: 260.355 linhas da capital, 223.191 inseridas e 37.164 rejeitadas, em cerca de 1m17s; a segunda execução é no-op.
