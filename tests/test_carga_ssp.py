import hashlib
from datetime import date, datetime, time

import openpyxl
import pytest

from app.services.carga_ssp import (
    MOTIVO_COORDENADAS_INVALIDAS,
    Ocorrencia,
    Rejeicao,
    calcular_chave_fonte,
    calcular_peso,
    interpretar_linha,
    ler_linhas_xlsx,
    sha256_arquivo,
)

CABECALHO = (
    "NOME_DEPARTAMENTO", "NOME_SECCIONAL", "NOME_DELEGACIA", "NOME_MUNICIPIO", "NUM_BO", "ANO_BO",
    "DATA_OCORRENCIA_BO", "HORA_OCORRENCIA_BO", "DESC_PERIODO", "BAIRRO", "LATITUDE", "LONGITUDE",
    "RUBRICA", "DESCR_CONDUTA", "NATUREZA_APURADA", "COD IBGE",
)  # fmt: skip


def linha_ssp(**sobrescritas) -> dict:
    """Linha como sai do xlsx da SSP (só as colunas que a carga usa)."""
    return {
        "NOME_DEPARTAMENTO": "DECAP",
        "NOME_SECCIONAL": "DEL.SEC.1º CENTRO",
        "NOME_DELEGACIA": "01º D.P. SE",
        "NOME_MUNICIPIO": "S.PAULO",
        "NUM_BO": "AB1234",
        "ANO_BO": 2026,
        "DATA_OCORRENCIA_BO": datetime(2026, 1, 17),
        "HORA_OCORRENCIA_BO": "15:00",
        "DESC_PERIODO": "A tarde",
        "BAIRRO": "Liberdade",
        "LATITUDE": -23.5582629,
        "LONGITUDE": -46.6338813,
        "RUBRICA": "Roubo (art. 157)",
        "DESCR_CONDUTA": "Transeunte",
        "NATUREZA_APURADA": "FURTO - OUTROS",
        "COD IBGE": 3550308,
        **sobrescritas,
    }


@pytest.mark.parametrize(
    ("natureza", "rubrica", "peso"),
    [
        ("FURTO - OUTROS", "Furto (art. 155)", 1),
        ("FURTO - OUTROS", "Roubo (art. 157)", 2),
        ("APREENSÃO DE ENTORPECENTES", "Homicídio (art. 121)", 3),
        ("LESÃO CORPORAL DOLOSA", None, 2),
        ("PORTE DE ARMA", None, 2),
        (None, "Extorsão mediante seqüestro (art. 159)", 3),
        ("latrocínio", None, 3),
        ("ESTUPRO DE VULNERÁVEL", "Estupro de vulneravel (art.217-A)", 3),
        (None, None, 1),
    ],
)
def peso_deve_ser_o_maior_entre_natureza_e_rubrica(natureza, rubrica, peso):
    assert calcular_peso(natureza, rubrica) == peso


CHAVE = ("01º D.P. SE", "AB1234", 2026, "Roubo (art. 157)", "Transeunte", "FURTO - OUTROS")


def chave_fonte_deve_ser_um_sha256_estavel():
    chave = calcular_chave_fonte(*CHAVE)

    assert len(chave) == 64 and int(chave, 16) >= 0
    assert calcular_chave_fonte(*CHAVE) == chave


@pytest.mark.parametrize("posicao", range(len(CHAVE)))
def chave_fonte_deve_mudar_quando_qualquer_campo_da_chave_natural_muda(posicao):
    outra = list(CHAVE)
    outra[posicao] = f"{outra[posicao]}x"

    assert calcular_chave_fonte(*outra) != calcular_chave_fonte(*CHAVE)


def chave_fonte_deve_tratar_null_vazio_e_espacos_como_iguais():
    assert (
        calcular_chave_fonte(" 01º D.P. SE ", "AB1234", "2026", "Roubo (art. 157)", None, "FURTO - OUTROS")
        == calcular_chave_fonte("01º D.P. SE", "AB1234", 2026, "Roubo (art. 157)", "NULL", "FURTO - OUTROS")
        == calcular_chave_fonte("01º D.P. SE", "AB1234", 2026, "Roubo (art. 157)", "", "FURTO - OUTROS")
    )


def linha_valida_deve_virar_ocorrencia_normalizada():
    ocorrencia = interpretar_linha(linha_ssp())

    assert ocorrencia == Ocorrencia(
        chave_fonte=calcular_chave_fonte(*CHAVE),
        municipio_ibge="3550308",
        municipio_nome="S.PAULO",
        departamento="DECAP",
        seccional="DEL.SEC.1º CENTRO",
        delegacia="01º D.P. SE",
        data_ocorrencia=date(2026, 1, 17),
        hora_ocorrencia=time(15, 0),
        periodo="A tarde",
        bairro="Liberdade",
        rubrica="Roubo (art. 157)",
        conduta="Transeunte",
        natureza_apurada="FURTO - OUTROS",
        peso=2,
        latitude=-23.5582629,
        longitude=-46.6338813,
    )


def campo_null_deve_virar_vazio():
    ocorrencia = interpretar_linha(linha_ssp(HORA_OCORRENCIA_BO="NULL", BAIRRO="NULL", DESCR_CONDUTA=None))

    assert (ocorrencia.hora_ocorrencia, ocorrencia.bairro, ocorrencia.conduta) == (None, None, None)


def coordenada_em_texto_com_virgula_deve_ser_aceita():
    ocorrencia = interpretar_linha(linha_ssp(LATITUDE="-23,55", LONGITUDE="-46,63"))

    assert (ocorrencia.latitude, ocorrencia.longitude) == (-23.55, -46.63)


def linha_fora_da_capital_deve_ser_ignorada():
    assert interpretar_linha(linha_ssp(**{"COD IBGE": 3509502, "NOME_MUNICIPIO": "CAMPINAS"})) is None


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [("-", "-"), ("NULL", "NULL"), (None, None), (0, 0), (0.0, 0.0), (-123.5, -46.6), (-23.5, -246.6)],
)
def coordenada_ausente_zerada_ou_fora_do_intervalo_deve_ser_rejeitada(latitude, longitude):
    assert interpretar_linha(linha_ssp(LATITUDE=latitude, LONGITUDE=longitude)) == Rejeicao(
        MOTIVO_COORDENADAS_INVALIDAS
    )


def leitura_do_xlsx_deve_trazer_as_linhas_de_todas_as_abas_de_dados(tmp_path):
    caminho = tmp_path / "ssp.xlsx"
    livro = openpyxl.Workbook()
    dicionario = livro.active
    dicionario.title = "Campos da Tabela_SPDADOS"
    dicionario.append(["Campos", "Descrição"])
    dicionario.append(["NUM_BO", "Número do boletim de ocorrência"])
    for titulo, num_bo in (("JAN-JUN_2026", "A1"), ("JUL-DEZ_2026", "B2")):
        aba = livro.create_sheet(titulo)
        aba.append(CABECALHO)
        aba.append([linha_ssp(NUM_BO=num_bo)[coluna] for coluna in CABECALHO])
        aba.append([None] * len(CABECALHO))
    livro.save(caminho)

    linhas = list(ler_linhas_xlsx(caminho))

    assert [linha["NUM_BO"] for linha in linhas] == ["A1", "B2"]
    assert interpretar_linha(linhas[0]).delegacia == "01º D.P. SE"


def sha256_do_arquivo_deve_ser_o_do_conteudo(tmp_path):
    caminho = tmp_path / "qualquer.bin"
    caminho.write_bytes(b"conteudo" * 100_000)

    assert sha256_arquivo(caminho) == hashlib.sha256(b"conteudo" * 100_000).hexdigest()
