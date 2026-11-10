"""Carga das ocorrências criminais da SSP-SP (MAP-03).

O xlsx da SSP tem uma aba de dicionário e uma ou mais abas de dados. Só
entram ocorrências da capital (COD IBGE 3550308) com coordenada válida.

Idempotência:
- arquivo: o sha256 do xlsx é único em interno.cargas_ssp; arquivo já
  CONCLUIDO não é processado de novo;
- ocorrência: chave_fonte = sha256 da chave natural
  delegacia|NUM_BO|ANO_BO|rubrica|conduta|natureza (valores sem espaços nas
  pontas; vazio e "NULL" viram ""). Se a chave já existe, a linha é atualizada.

A chave da carga de 27/10/2026 no Neon usava outra fórmula, que não se
consegue reproduzir; por isso a carga nova deve ser feita com substituir=True.
"""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import astuple, dataclass, field, fields
from datetime import date, datetime, time
from itertools import batched
from pathlib import Path
from uuid import UUID

import openpyxl
from sqlalchemy import text
from sqlalchemy.orm import Session

CODIGO_IBGE_CAPITAL = "3550308"
MOTIVO_COORDENADAS_INVALIDAS = "coordenadas_invalidas"
MOTIVO_CAMPOS_OBRIGATORIOS = "campos_obrigatorios"
TAMANHO_LOTE = 5000

# Peso = o maior entre a natureza apurada e a rubrica, comparados sem acento e
# em maiúsculas. Bate com 100% das 288.487 ocorrências da carga original.
_PALAVRAS_PESO_3 = re.compile(r"HOMICIDIO|LATROCINIO|ESTUPRO|FEMINICIDIO|EXTORSAO MEDIANTE SEQUESTRO|VICARICIDIO")
_PALAVRAS_PESO_2 = re.compile(r"ROUBO|LESAO CORPORAL|\bARMA")

# Colunas do xlsx que identificam uma aba de dados.
_COLUNAS_OBRIGATORIAS = {"NUM_BO", "NOME_DELEGACIA", "LATITUDE", "LONGITUDE", "COD IBGE"}
_VAZIOS = {"", "NULL"}


@dataclass(frozen=True)
class Ocorrencia:
    chave_fonte: str
    municipio_ibge: str
    municipio_nome: str
    departamento: str | None
    seccional: str | None
    delegacia: str | None
    data_ocorrencia: date | None
    hora_ocorrencia: time | None
    periodo: str | None
    bairro: str | None
    rubrica: str | None
    conduta: str | None
    natureza_apurada: str | None
    peso: int
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Rejeicao:
    motivo: str


@dataclass(frozen=True)
class ResumoCarga:
    carga_id: UUID
    ja_carregada: bool
    linhas_lidas: int = 0
    inseridas: int = 0
    atualizadas: int = 0
    rejeitadas: int = 0
    removidas: int = 0
    erros: dict[str, int] = field(default_factory=dict)


def calcular_peso(natureza: str | None, rubrica: str | None) -> int:
    return max(_peso_do_texto(natureza), _peso_do_texto(rubrica))


def _peso_do_texto(valor: str | None) -> int:
    normalizado = _sem_acento(valor or "").upper()
    if _PALAVRAS_PESO_3.search(normalizado):
        return 3
    if _PALAVRAS_PESO_2.search(normalizado):
        return 2
    return 1


def _sem_acento(valor: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", valor) if not unicodedata.combining(c))


def calcular_chave_fonte(delegacia, num_bo, ano_bo, rubrica, conduta, natureza) -> str:
    partes = (_texto(valor) or "" for valor in (delegacia, num_bo, ano_bo, rubrica, conduta, natureza))
    return hashlib.sha256("|".join(partes).encode()).hexdigest()


def _texto(valor, limite: int | None = None) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    if texto in _VAZIOS:
        return None
    return texto[:limite] if limite else texto


def _codigo_ibge(valor) -> str | None:
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return _texto(valor)


def _coordenada(valor) -> float | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        numero = float(valor)
    else:
        texto = _texto(valor)
        if texto is None:
            return None
        try:
            numero = float(texto.replace(",", "."))
        except ValueError:
            return None
    return numero if math.isfinite(numero) else None


def _data(valor) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = _texto(valor)
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(texto, formato).date()
        except (TypeError, ValueError):
            continue
    return None


def _hora(valor) -> time | None:
    if isinstance(valor, datetime):
        return valor.time()
    if isinstance(valor, time):
        return valor
    texto = _texto(valor)
    for formato in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(texto, formato).time()
        except (TypeError, ValueError):
            continue
    return None


def interpretar_linha(linha: Mapping[str, object]) -> Ocorrencia | Rejeicao | None:
    """None para linha fora da capital; Rejeicao para linha da capital inválida."""
    if _codigo_ibge(linha.get("COD IBGE")) != CODIGO_IBGE_CAPITAL:
        return None
    latitude, longitude = _coordenada(linha.get("LATITUDE")), _coordenada(linha.get("LONGITUDE"))
    if (
        latitude is None
        or longitude is None
        or (latitude == 0 and longitude == 0)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return Rejeicao(MOTIVO_COORDENADAS_INVALIDAS)
    municipio_nome = _texto(linha.get("NOME_MUNICIPIO"), 120)
    if municipio_nome is None:
        return Rejeicao(MOTIVO_CAMPOS_OBRIGATORIOS)

    rubrica = _texto(linha.get("RUBRICA"), 255)
    conduta = _texto(linha.get("DESCR_CONDUTA"), 255)
    natureza = _texto(linha.get("NATUREZA_APURADA"), 255)
    return Ocorrencia(
        chave_fonte=calcular_chave_fonte(
            linha.get("NOME_DELEGACIA"),
            linha.get("NUM_BO"),
            linha.get("ANO_BO"),
            linha.get("RUBRICA"),
            linha.get("DESCR_CONDUTA"),
            linha.get("NATUREZA_APURADA"),
        ),
        municipio_ibge=CODIGO_IBGE_CAPITAL,
        municipio_nome=municipio_nome,
        departamento=_texto(linha.get("NOME_DEPARTAMENTO"), 160),
        seccional=_texto(linha.get("NOME_SECCIONAL"), 160),
        delegacia=_texto(linha.get("NOME_DELEGACIA"), 160),
        data_ocorrencia=_data(linha.get("DATA_OCORRENCIA_BO")),
        hora_ocorrencia=_hora(linha.get("HORA_OCORRENCIA_BO")),
        periodo=_texto(linha.get("DESC_PERIODO"), 80),
        bairro=_texto(linha.get("BAIRRO"), 120),
        rubrica=rubrica,
        conduta=conduta,
        natureza_apurada=natureza,
        peso=calcular_peso(natureza, rubrica),
        latitude=latitude,
        longitude=longitude,
    )


def ler_linhas_xlsx(caminho: Path | str) -> Iterator[dict]:
    """Linhas de todas as abas cujo cabeçalho tem as colunas da SSP; ignora linhas vazias."""
    livro = openpyxl.load_workbook(caminho, read_only=True)
    try:
        for aba in livro.worksheets:
            linhas = aba.iter_rows(values_only=True)
            cabecalho = next(linhas, None) or ()
            colunas = [str(c).strip() if c is not None else "" for c in cabecalho]
            if not _COLUNAS_OBRIGATORIAS <= set(colunas):
                continue
            for valores in linhas:
                if any(valor is not None for valor in valores):
                    yield dict(zip(colunas, valores, strict=False))
    finally:
        livro.close()


def sha256_arquivo(caminho: Path | str) -> str:
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


_BUSCAR_CARGA = text("SELECT id, status FROM interno.cargas_ssp WHERE arquivo_sha256 = :sha")
_RESUMO_CARGA = text(
    "SELECT id, linhas_lidas, inseridas, atualizadas, rejeitadas, erros_amostra FROM interno.cargas_ssp WHERE id = :id"
)
_CRIAR_CARGA = text(
    "INSERT INTO interno.cargas_ssp (arquivo_sha256, nome_arquivo, fonte_url, licenca) "
    "VALUES (:sha, :nome, :fonte_url, :licenca) RETURNING id"
)
_REINICIAR_CARGA = text(
    "UPDATE interno.cargas_ssp SET status = 'PROCESSANDO', nome_arquivo = :nome, fonte_url = :fonte_url, "
    "licenca = :licenca, iniciado_em = now(), finalizado_em = NULL WHERE id = :id"
)
_CONCLUIR_CARGA = text(
    "UPDATE interno.cargas_ssp SET status = 'CONCLUIDA', finalizado_em = now(), linhas_lidas = :lidas, "
    "inseridas = :inseridas, atualizadas = :atualizadas, rejeitadas = :rejeitadas, "
    "erros_amostra = CAST(:erros AS json) WHERE id = :id"
)
_REMOVER_ANTERIORES = text("DELETE FROM interno.ocorrencias_ssp WHERE carga_id <> :id")

_CAMPOS = [campo.name for campo in fields(Ocorrencia)]
_TIPOS = {
    "data_ocorrencia": "date",
    "hora_ocorrencia": "time",
    "peso": "int",
    "latitude": "float8",
    "longitude": "float8",
}
_COLUNAS = [c for c in _CAMPOS if c not in ("latitude", "longitude")]
# Um INSERT por lote, com os campos em arrays: bem mais rápido que executemany no Neon.
_GRAVAR_LOTE = text(
    f"INSERT INTO interno.ocorrencias_ssp (carga_id, {', '.join(_COLUNAS)}, localizacao) "
    f"SELECT :carga_id, {', '.join(f't.{c}' for c in _COLUNAS)}, "
    "ST_SetSRID(ST_MakePoint(t.longitude, t.latitude), 4326) "
    f"FROM unnest({', '.join(f'CAST(:{c} AS {_TIPOS.get(c, "text")}[])' for c in _CAMPOS)}) "
    f"AS t({', '.join(_CAMPOS)}) "
    "ON CONFLICT (chave_fonte) DO UPDATE SET carga_id = EXCLUDED.carga_id, "
    f"{', '.join(f'{c} = EXCLUDED.{c}' for c in _COLUNAS if c != 'chave_fonte')}, "
    "localizacao = EXCLUDED.localizacao "
    "RETURNING (xmax = 0) AS inserida"
)


def carregar_ssp(
    sessao: Session,
    linhas: Iterable[Mapping[str, object]],
    arquivo_sha256: str,
    nome_arquivo: str,
    fonte_url: str | None,
    licenca: str | None,
    substituir: bool = False,
) -> ResumoCarga:
    """Grava as ocorrências e registra a carga. Não faz commit."""
    existente = sessao.execute(_BUSCAR_CARGA, {"sha": arquivo_sha256}).one_or_none()
    dados_carga = {"sha": arquivo_sha256, "nome": nome_arquivo, "fonte_url": fonte_url, "licenca": licenca}
    if existente is not None and existente.status == "CONCLUIDA":
        return _resumo_existente(sessao, existente.id)
    if existente is None:
        carga_id = sessao.execute(_CRIAR_CARGA, dados_carga).scalar_one()
    else:
        carga_id = existente.id
        sessao.execute(_REINICIAR_CARGA, {**dados_carga, "id": carga_id})

    lidas = inseridas = atualizadas = 0
    erros: Counter[str] = Counter()
    for lote in batched(_interpretar(linhas, erros), TAMANHO_LOTE):
        # Na mesma instrução, a mesma chave duas vezes é erro no ON CONFLICT; fica a última.
        unicas = list({ocorrencia.chave_fonte: ocorrencia for ocorrencia in lote}.values())
        lidas += len(lote)
        atualizadas += len(lote) - len(unicas)
        resultado = sessao.execute(_GRAVAR_LOTE, _parametros_lote(carga_id, unicas)).scalars().all()
        inseridas += sum(resultado)
        atualizadas += len(resultado) - sum(resultado)
    rejeitadas = sum(erros.values())
    lidas += rejeitadas

    removidas = sessao.execute(_REMOVER_ANTERIORES, {"id": carga_id}).rowcount if substituir else 0
    sessao.execute(
        _CONCLUIR_CARGA,
        {
            "id": carga_id,
            "lidas": lidas,
            "inseridas": inseridas,
            "atualizadas": atualizadas,
            "rejeitadas": rejeitadas,
            "erros": json.dumps(dict(erros)),
        },
    )
    return ResumoCarga(carga_id, False, lidas, inseridas, atualizadas, rejeitadas, removidas, dict(erros))


def _interpretar(linhas: Iterable[Mapping[str, object]], erros: Counter) -> Iterator[Ocorrencia]:
    for linha in linhas:
        resultado = interpretar_linha(linha)
        if isinstance(resultado, Rejeicao):
            erros[resultado.motivo] += 1
        elif resultado is not None:
            yield resultado


def _parametros_lote(carga_id: UUID, ocorrencias: list[Ocorrencia]) -> dict:
    colunas = zip(*(astuple(ocorrencia) for ocorrencia in ocorrencias), strict=True)
    return {"carga_id": carga_id, **{nome: list(valores) for nome, valores in zip(_CAMPOS, colunas, strict=True)}}


def _resumo_existente(sessao: Session, carga_id: UUID) -> ResumoCarga:
    carga = sessao.execute(_RESUMO_CARGA, {"id": carga_id}).one()
    return ResumoCarga(
        carga.id,
        True,
        carga.linhas_lidas,
        carga.inseridas,
        carga.atualizadas,
        carga.rejeitadas,
        erros=dict(carga.erros_amostra),
    )
