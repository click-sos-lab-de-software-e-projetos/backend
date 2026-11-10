import importlib.util
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_carga_ssp import CABECALHO, linha_ssp

from app.constants import COR_VERDE, COR_VERMELHA
from app.services.carga_ssp import MOTIVO_COORDENADAS_INVALIDAS, ResumoCarga, carregar_ssp
from integracao.fabricas import inserir_carga_ssp, inserir_ocorrencia, inserir_regiao

CAMINHO = Path(__file__).parents[2] / "scripts" / "carregar_mapa.py"
_spec = importlib.util.spec_from_file_location("carregar_mapa", CAMINHO)
carregar_mapa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(carregar_mapa)

SHA = "a" * 64

LINHAS = [
    linha_ssp(NUM_BO="A1"),
    linha_ssp(NUM_BO="A2", RUBRICA="Homicídio (art. 121)", NATUREZA_APURADA="HOMICÍDIO DOLOSO"),
    linha_ssp(NUM_BO="A3", LATITUDE=0, LONGITUDE=0),
    linha_ssp(NUM_BO="A4", **{"COD IBGE": 3509502}),
]


def _carregar(engine, linhas=LINHAS, sha=SHA, **kwargs) -> ResumoCarga:
    with Session(engine) as sessao:
        resumo = carregar_ssp(sessao, linhas, sha, "ssp.xlsx", "https://ssp.example", "pública", **kwargs)
        sessao.commit()
    return resumo


def _ocorrencias(engine) -> list:
    with engine.connect() as conexao:
        return conexao.execute(
            text(
                "SELECT carga_id, chave_fonte, delegacia, bairro, peso, data_ocorrencia, "
                "ST_SRID(localizacao) AS srid, ST_X(localizacao) AS longitude, ST_Y(localizacao) AS latitude "
                "FROM interno.ocorrencias_ssp ORDER BY peso"
            )
        ).all()


def _cargas(engine) -> list:
    with engine.connect() as conexao:
        return conexao.execute(text("SELECT * FROM interno.cargas_ssp ORDER BY iniciado_em")).all()


def carga_deve_gravar_as_ocorrencias_da_capital_e_registrar_a_carga(banco_migrado):
    resumo = _carregar(banco_migrado)

    ocorrencias = _ocorrencias(banco_migrado)
    assert [(o.peso, o.srid, o.delegacia) for o in ocorrencias] == [(2, 4326, "01º D.P. SE"), (3, 4326, "01º D.P. SE")]
    assert (ocorrencias[0].latitude, ocorrencias[0].longitude) == (-23.5582629, -46.6338813)
    (carga,) = _cargas(banco_migrado)
    assert {o.carga_id for o in ocorrencias} == {carga.id}
    assert (carga.arquivo_sha256, carga.status, carga.fonte_url, carga.licenca) == (
        SHA,
        "CONCLUIDA",
        "https://ssp.example",
        "pública",
    )
    assert (carga.linhas_lidas, carga.inseridas, carga.atualizadas, carga.rejeitadas) == (3, 2, 0, 1)
    assert carga.erros_amostra == {MOTIVO_COORDENADAS_INVALIDAS: 1}
    assert carga.finalizado_em is not None
    assert resumo == ResumoCarga(carga.id, False, 3, 2, 0, 1, 0, {MOTIVO_COORDENADAS_INVALIDAS: 1})


def mesmo_arquivo_ja_concluido_nao_deve_alterar_nada(banco_migrado):
    primeira = _carregar(banco_migrado)
    antes = (_ocorrencias(banco_migrado), _cargas(banco_migrado))

    segunda = _carregar(banco_migrado, linhas=[linha_ssp(NUM_BO="NOVA")])

    assert (_ocorrencias(banco_migrado), _cargas(banco_migrado)) == antes
    assert segunda == ResumoCarga(primeira.carga_id, True, 3, 2, 0, 1, 0, {MOTIVO_COORDENADAS_INVALIDAS: 1})


def chave_repetida_em_arquivo_novo_deve_atualizar_a_ocorrencia(banco_migrado):
    _carregar(banco_migrado, linhas=[linha_ssp(NUM_BO="A1", BAIRRO="Antigo")])

    resumo = _carregar(banco_migrado, linhas=[linha_ssp(NUM_BO="A1", BAIRRO="Novo")], sha="b" * 64)

    (ocorrencia,) = _ocorrencias(banco_migrado)
    assert (ocorrencia.bairro, ocorrencia.carga_id) == ("Novo", resumo.carga_id)
    assert (resumo.inseridas, resumo.atualizadas) == (0, 1)


def arquivo_que_falhou_deve_ser_processado_de_novo(banco_migrado):
    with banco_migrado.begin() as conexao:
        falhou = inserir_carga_ssp(conexao, arquivo_sha256=SHA, status="FALHOU").id

    resumo = _carregar(banco_migrado)

    (carga,) = _cargas(banco_migrado)
    assert (resumo.carga_id, resumo.ja_carregada, resumo.inseridas) == (falhou, False, 2)
    assert (carga.status, carga.inseridas) == ("CONCLUIDA", 2)


@pytest.mark.parametrize(("substituir", "restantes"), [(True, 2), (False, 3)])
def substituir_deve_apagar_so_as_ocorrencias_das_cargas_anteriores(banco_migrado, substituir, restantes):
    with banco_migrado.begin() as conexao:
        antiga = inserir_carga_ssp(conexao).id
        inserir_ocorrencia(conexao, antiga, -23.5, -46.6)

    resumo = _carregar(banco_migrado, substituir=substituir)

    assert len(_ocorrencias(banco_migrado)) == restantes
    assert resumo.removidas == (1 if substituir else 0)
    assert antiga in {carga.id for carga in _cargas(banco_migrado)}


def _salvar_xlsx(caminho: Path, linhas: list[dict]) -> Path:
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.append(CABECALHO)
    for linha in linhas:
        aba.append([linha[coluna] for coluna in CABECALHO])
    livro.save(caminho)
    return caminho


@pytest.fixture
def xlsx_no_distrito(banco_migrado, tmp_path) -> Path:
    """Distrito A tem um homicídio; o B, ao lado, fica vazio."""
    with banco_migrado.begin() as conexao:
        inserir_regiao(conexao, -46.64, -23.56, -46.63, -23.55, id_publico="distrito-a")
        inserir_regiao(conexao, -46.63, -23.56, -46.62, -23.55, id_publico="distrito-b", cor_hex=COR_VERMELHA)
    linha = linha_ssp(LATITUDE=-23.555, LONGITUDE=-46.635, RUBRICA="Homicídio (art. 121)")
    return _salvar_xlsx(tmp_path / "SPDadosCriminais.xlsx", [linha, linha_ssp(NUM_BO="X", LATITUDE="-")])


def _cores(engine) -> dict:
    with engine.connect() as conexao:
        return dict(conexao.execute(text("SELECT id_publico, cor_hex FROM regioes_seguranca")).all())


def comando_ssp_sem_gravar_deve_mostrar_o_resumo_sem_alterar_o_banco(
    banco_migrado, xlsx_no_distrito, url_teste, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", url_teste)

    assert carregar_mapa.main(["ssp", str(xlsx_no_distrito)]) == 0

    assert (_ocorrencias(banco_migrado), _cargas(banco_migrado)) == ([], [])
    saida = capsys.readouterr().out
    assert "Linhas lidas: 2" in saida and "Inseridas: 1" in saida and "Rejeitadas: 1" in saida
    assert "--gravar" in saida
    assert "teste:teste" not in saida  # nunca imprime a URL do banco


def comando_ssp_com_gravar_deve_gravar_e_recalcular_os_distritos(
    banco_migrado, xlsx_no_distrito, url_teste, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", url_teste)

    assert carregar_mapa.main(["ssp", str(xlsx_no_distrito), "--gravar", "--substituir"]) == 0

    (carga,) = _cargas(banco_migrado)
    assert carga.nome_arquivo == "SPDadosCriminais.xlsx" and len(carga.arquivo_sha256) == 64
    assert len(_ocorrencias(banco_migrado)) == 1
    assert _cores(banco_migrado) == {"distrito-a": COR_VERMELHA, "distrito-b": COR_VERDE}
