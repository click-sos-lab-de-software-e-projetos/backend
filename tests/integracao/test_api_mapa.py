import time
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import obter_segredo_jwt
from app.db.sessao import criar_engine, obter_sessao
from app.main import app
from integracao.fabricas import inserir_fonte_geografica, inserir_regiao

SEGREDO_TESTE = "segredo-apenas-para-testes-com-32-bytes"
ROTA = "/api/v1/mapa/regioes"
# 0,01° ≈ 1,1 km perto do equador. Coordenadas sem significado geográfico.
PONTO = {"latitude": 0.005, "longitude": 0.005}


def _token() -> dict[str, str]:
    payload = {"sub": str(uuid4()), "exp": int(time.time()) + 300}
    return {"Authorization": f"Bearer {jwt.encode(payload, SEGREDO_TESTE, algorithm='HS256')}"}


@pytest.fixture
def client(banco_migrado, url_teste):
    engine = criar_engine(url_teste)

    def _sessao_de_teste():
        with Session(engine) as sessao:
            yield sessao

    app.dependency_overrides[obter_segredo_jwt] = lambda: SEGREDO_TESTE
    app.dependency_overrides[obter_sessao] = _sessao_de_teste
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def _distrito(banco_migrado, oeste, leste, **sobrescritas) -> str:
    """Faixa de 0,01° de altura (latitude 0 a 0,01) entre as longitudes dadas."""
    with banco_migrado.begin() as conexao:
        return inserir_regiao(conexao, oeste, 0.0, leste, 0.01, **sobrescritas).id_publico


def _ids(resposta) -> list[str]:
    assert resposta.status_code == 200
    return [regiao["id"] for regiao in resposta.json()]


def regioes_deve_devolver_o_distrito_do_ponto_primeiro_e_os_vizinhos_em_ordem(client, banco_migrado):
    longe = _distrito(banco_migrado, 0.02, 0.03)  # borda a ~1,7 km do ponto
    onde_estou = _distrito(banco_migrado, 0.0, 0.01)
    vizinho = _distrito(banco_migrado, 0.01, 0.02)  # borda a ~0,6 km

    assert _ids(client.get(ROTA, params=PONTO, headers=_token())) == [onde_estou, vizinho, longe]


def regiao_fora_do_raio_nao_deve_aparecer(client, banco_migrado):
    perto = _distrito(banco_migrado, 0.0, 0.01)
    _distrito(banco_migrado, 0.03, 0.04)  # borda a ~2,8 km: dentro do padrão de 3 km
    _distrito(banco_migrado, 0.04, 0.05)  # borda a ~3,9 km: fora do padrão

    assert len(_ids(client.get(ROTA, params=PONTO, headers=_token()))) == 2
    assert _ids(client.get(ROTA, params={**PONTO, "raio": 1000}, headers=_token())) == [perto]


def regioes_deve_devolver_no_maximo_50(client, banco_migrado):
    with banco_migrado.begin() as conexao:
        fonte = inserir_fonte_geografica(conexao).id
        for i in range(51):
            inserir_regiao(conexao, i * 0.0001, 0.0, (i + 1) * 0.0001, 0.01, fonte_geografica_id=fonte)

    assert len(_ids(client.get(ROTA, params=PONTO, headers=_token()))) == 50


def regioes_deve_expor_so_os_campos_publicos(client, banco_migrado):
    _distrito(
        banco_migrado, 0.0, 0.01, id_publico="distrito-sp-1", nome="Distrito Ficticio", score_final=72,
        cor_hex="#EF4444", raio_metros=640,
    )

    (regiao,) = client.get(ROTA, params=PONTO, headers=_token()).json()

    assert regiao == {
        "id": "distrito-sp-1",
        "nome": "Distrito Ficticio",
        "centroide": {"latitude": pytest.approx(0.005), "longitude": pytest.approx(0.005)},
        "score": 72,
        "cor_hex": "#EF4444",
        "raio_metros": 640,
    }


def regioes_sem_distritos_por_perto_deve_devolver_lista_vazia(client, banco_migrado):
    _distrito(banco_migrado, 0.5, 0.6)

    assert _ids(client.get(ROTA, params=PONTO, headers=_token())) == []
