import copy
import shutil

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.tests.conftest import CONFIG_PATH
from backend.tests.test_api import NOW, StubSource, job


@pytest.fixture
def arquivo(tmp_path):
    copia = tmp_path / "config.toml"
    shutil.copy(CONFIG_PATH, copia)
    return copia


def _client(settings, arquivo, sources=None, spawn=lambda fn: fn()):
    app = create_app(
        settings, sources_factory=lambda: sources or [StubSource()], spawn=spawn, now=lambda: NOW, config_path=arquivo
    )
    return TestClient(app)


def test_config_expoe_todos_os_campos_editaveis(settings, arquivo):
    with _client(settings, arquivo) as client:
        corpo = client.get("/api/config").json()
    assert corpo["ritmo"]["rolagem_min_s"] == 0.25
    assert corpo["filtro"]["trecho_max_chars"] == 4000


def test_put_grava_no_arquivo_e_vale_na_hora(settings, arquivo):
    with _client(settings, arquivo, [StubSource(jobs=[job("1")])]) as client:
        novo = client.get("/api/config").json()
        novo["filtro"]["min_score"] = 99
        novo["busca"]["localidades"] = ["Campinas, SP", "Minas Gerais"]
        resposta = client.put("/api/config", json=novo)
        assert resposta.status_code == 200
        assert resposta.json() == novo
        assert client.get("/api/config").json() == novo
        run = client.get(f"/api/runs/{client.post('/api/runs').json()['id']}").json()
    assert run["fontes"][0]["aprovadas"] == 0
    texto = arquivo.read_text(encoding="utf-8")
    assert 'localidades = ["Campinas, SP", "Minas Gerais"]' in texto and "min_score = 99" in texto
    assert "# pausa ao rolar a lista" in texto


def test_abas_paralelas_e_editavel_e_grava_so_o_valor(settings, arquivo):
    with _client(settings, arquivo) as client:
        novo = client.get("/api/config").json()
        atual = novo["navegador"]["abas_paralelas"]
        assert set(novo["navegador"]) == {"abas_paralelas", "max_tentativas_painel", "intervalo_tentativa_painel_s"}
        novo["navegador"]["abas_paralelas"] = not atual
        resposta = client.put("/api/config", json=novo)
        assert resposta.status_code == 200
        assert client.get("/api/config").json()["navegador"]["abas_paralelas"] == (not atual)
    texto = arquivo.read_text(encoding="utf-8")
    assert f"abas_paralelas = {str(not atual).lower()}" in texto and "# true: uma aba por fonte" in texto


def test_tentativas_e_intervalo_do_painel_sao_editaveis_e_gravam_so_o_valor(settings, arquivo):
    with _client(settings, arquivo) as client:
        novo = client.get("/api/config").json()
        assert novo["navegador"]["max_tentativas_painel"] == 3
        assert novo["navegador"]["intervalo_tentativa_painel_s"] == 15
        novo["navegador"]["max_tentativas_painel"] = 5
        novo["navegador"]["intervalo_tentativa_painel_s"] = 20.5
        assert client.put("/api/config", json=novo).status_code == 200
        atual = client.get("/api/config").json()["navegador"]
        novo["navegador"]["max_tentativas_painel"] = 0
        assert client.put("/api/config", json=novo).status_code == 422
    assert atual["max_tentativas_painel"] == 5 and atual["intervalo_tentativa_painel_s"] == 20.5
    texto = arquivo.read_text(encoding="utf-8")
    assert "max_tentativas_painel = 5 " in texto and "intervalo_tentativa_painel_s = 20.5 " in texto
    assert "# espera entre uma tentativa" in texto


def test_put_invalido_devolve_422_e_nao_altera_nada(settings, arquivo):
    original = arquivo.read_text(encoding="utf-8")
    with _client(settings, arquivo) as client:
        novo = client.get("/api/config").json()
        antes = copy.deepcopy(novo)
        novo["ritmo"]["pausa_min_s"] = 9.0
        novo["ritmo"]["pausa_max_s"] = 1.0
        resposta = client.put("/api/config", json=novo)
        assert resposta.status_code == 422
        assert "pausa_min_s=9.0" in resposta.json()["detail"]
        assert client.get("/api/config").json()["ritmo"] == antes["ritmo"]
    assert arquivo.read_text(encoding="utf-8") == original


def test_put_com_execucao_em_andamento_devolve_409(settings, arquivo):
    with _client(settings, arquivo, spawn=lambda fn: None) as client:
        client.post("/api/runs")
        resposta = client.put("/api/config", json=client.get("/api/config").json())
    assert resposta.status_code == 409
    assert "andamento" in resposta.json()["detail"]


def test_busca_seguinte_usa_a_config_nova_nas_fontes_reais(settings, arquivo):
    app = create_app(settings, now=lambda: NOW, config_path=arquivo)
    with TestClient(app) as client:
        novo = client.get("/api/config").json()
        novo["limites"]["max_paginas_por_termo"] = 7
        client.put("/api/config", json=novo)
        gupy = next(source for source in app.state.sources_factory() if source.name == "gupy")
    assert gupy._settings.limites.max_paginas_por_termo == 7


def test_limite_de_termos_fica_fixo_e_so_paginas_por_termo_e_editavel(settings, arquivo):
    with _client(settings, arquivo) as client:
        novo = client.get("/api/config").json()
        assert "max_termos_busca" not in novo["busca"]
        assert "keyword_max_length" not in novo["busca"]
        novo["busca"]["max_termos_busca"] = 3  # campo forjado não pode baixar o teto fixo
        novo["busca"]["keyword_max_length"] = 3  # proteção técnica também não é configurável pela API
        novo["limites"]["max_paginas_por_termo"] = 5
        assert client.put("/api/config", json=novo).status_code == 200
        atual = client.get("/api/config").json()
    assert "max_termos_busca" not in atual["busca"]
    assert "keyword_max_length" not in atual["busca"]
    assert atual["limites"]["max_paginas_por_termo"] == 5
    texto = arquivo.read_text(encoding="utf-8")
    assert "max_termos_busca = 6 " in texto and "max_paginas_por_termo = 5 " in texto


def test_put_grava_varias_modalidades_como_lista(settings, arquivo):
    with _client(settings, arquivo) as client:
        novo = client.get("/api/config").json()
        novo["busca"]["modalidade"] = ["remoto", "hibrido"]
        assert client.put("/api/config", json=novo).status_code == 200
        novo["busca"]["modalidade"] = ["voando"]
        assert client.put("/api/config", json=novo).status_code == 422
        assert client.get("/api/config").json()["busca"]["modalidade"] == ["remoto", "hibrido"]
    assert 'modalidade = ["remoto", "hibrido"]' in arquivo.read_text(encoding="utf-8")


def test_config_antigo_sem_a_chave_nova_do_painel_ainda_grava(settings, arquivo):
    linhas = arquivo.read_text(encoding="utf-8").splitlines(keepends=True)
    arquivo.write_text("".join(x for x in linhas if not x.startswith("intervalo_tentativa_painel_s")), encoding="utf-8")
    with _client(settings, arquivo) as client:
        novo = client.get("/api/config").json()
        novo["navegador"]["intervalo_tentativa_painel_s"] = 30
        assert client.put("/api/config", json=novo).status_code == 200
    assert "intervalo_tentativa_painel_s = 30" in arquivo.read_text(encoding="utf-8")
