import pytest

from backend.app.routes import runs as runs_route
from backend.app.sources.errors import SourceRateLimited
from backend.app.sources.types import Job
from backend.tests.api_support import StubSource, job, make_client


@pytest.fixture
def dois_conjuntos(settings):
    """Conjunto 1 com as vagas 1 e 2; conjunto "B" (ativo) com a vaga 9."""
    fonte = StubSource(jobs=[job("1"), job("2")])
    with make_client(settings, [fonte]) as test_client:
        test_client.post("/api/runs")
        outro = test_client.post("/api/conjuntos", json={"nome": "B"}).json()["id"]
        test_client.post("/api/keywords", json={"termo": "Engenheiro Mecânico", "tipo": "busca"})
        fonte._jobs = [job("9")]
        test_client.post("/api/runs")
        yield test_client, outro


def ids_da_lista(client, consulta=""):
    return sorted(vaga["id_da_vaga"] for vaga in client.get(f"/api/jobs{consulta}").json()["items"])


def test_lista_mostra_o_conjunto_ativo_e_aceita_escolher_outro(dois_conjuntos):
    client, outro = dois_conjuntos
    assert ids_da_lista(client) == ["9"]
    assert ids_da_lista(client, "?conjunto_id=1") == ["1", "2"]
    assert ids_da_lista(client, f"?conjunto_id={outro}") == ["9"]
    resposta = client.get("/api/jobs?conjunto_id=999")
    assert resposta.status_code == 404 and "999" in resposta.json()["detail"]


def test_lista_de_todos_os_conjuntos_ignora_o_filtro_de_conjunto(dois_conjuntos):
    client, _ = dois_conjuntos
    assert ids_da_lista(client, "?todos_conjuntos=true") == ["1", "2", "9"]
    assert ids_da_lista(client, "?todos_conjuntos=false") == ["9"]


def test_marcar_como_vistas_de_todos_os_conjuntos(dois_conjuntos):
    client, _ = dois_conjuntos
    assert client.post("/api/jobs/mark-seen", json={"todos_conjuntos": True}).json() == {"atualizadas": 3}
    assert client.get("/api/jobs?todos_conjuntos=true&visto=false").json()["total"] == 0


def test_marcar_como_vistas_vale_so_para_o_conjunto_escolhido(dois_conjuntos):
    client, outro = dois_conjuntos
    assert client.post("/api/jobs/mark-seen", json={"conjunto_id": 1}).json() == {"atualizadas": 2}
    assert client.get("/api/jobs?visto=false").json()["total"] == 1
    assert client.post("/api/jobs/mark-seen", json={}).json() == {"atualizadas": 1}
    assert client.get("/api/jobs?visto=false").json()["total"] == 0


def test_excluir_vagas_vale_so_para_o_conjunto_escolhido(dois_conjuntos):
    client, outro = dois_conjuntos
    assert client.delete("/api/jobs").json() == {"removidas": 1}
    assert ids_da_lista(client, "?conjunto_id=1") == ["1", "2"]
    assert client.delete("/api/jobs?conjunto_id=1").json() == {"removidas": 2}
    assert ids_da_lista(client, "?conjunto_id=1") == []


def test_excluir_o_conjunto_exclui_as_vagas_dele_e_mantem_as_dos_outros(dois_conjuntos):
    client, outro = dois_conjuntos
    assert client.delete(f"/api/conjuntos/{outro}").status_code == 204
    assert client.get(f"/api/jobs?conjunto_id={outro}").status_code == 404
    assert ids_da_lista(client) == ["1", "2"]  # o conjunto 1 voltou a ser o ativo


def test_recalcular_pontuacao_usa_as_palavras_atuais_e_nao_apaga_vagas(settings):
    vagas = [
        Job("1", "Engenheiro Mecânico Projetista", "ACME", "https://x/1", "", "stub"),
        Job("2", "Engenheiro Mecânico", "Beta", "https://x/2", "", "stub"),
    ]
    with make_client(settings, [StubSource(jobs=vagas)]) as client:
        client.post("/api/runs")
        antes = {v["id_da_vaga"]: v["pontos"] for v in client.get("/api/jobs").json()["items"]}
        client.post("/api/keywords", json={"termo": "Projetista", "tipo": "ranking"})
        resposta = client.post("/api/jobs/recalcular")
        depois = {v["id_da_vaga"]: v["pontos"] for v in client.get("/api/jobs").json()["items"]}
    assert resposta.status_code == 200
    assert resposta.json() == {"atualizadas": 1, "total": 2}
    assert depois["1"] == antes["1"] + settings.filtro.peso_titulo
    assert depois["2"] == antes["2"]


def test_recalcular_pontuacao_durante_uma_busca_devolve_409(settings):
    with make_client(settings, [StubSource()], spawn=lambda fn: None) as test_client:
        test_client.post("/api/runs")
        assert test_client.post("/api/jobs/recalcular").status_code == 409


def test_recalcular_pontuacao_vale_para_todos_os_conjuntos_cada_um_com_as_suas_palavras(settings):
    vagas = [
        Job("1", "Engenheiro Mecânico Projetista", "ACME", "https://x/1", "", "stub"),
        Job("2", "Engenheiro Mecânico", "Beta", "https://x/2", "", "stub"),
    ]
    with make_client(settings, [StubSource(jobs=vagas)]) as client:
        ativo_a = next(c["id"] for c in client.get("/api/conjuntos").json() if c["ativo"])
        client.post("/api/runs")  # conjunto A (palavras padrão): 2 vagas
        b = client.post("/api/conjuntos", json={"nome": "B"}).json()["id"]
        client.post(f"/api/conjuntos/{b}/ativar")
        client.post("/api/keywords", json={"termo": "Projetista", "tipo": "busca"})
        client.post("/api/runs")  # conjunto B: 1 vaga, 3 pontos
        client.post("/api/keywords", json={"termo": "Engenheiro", "tipo": "ranking"})
        client.post(f"/api/conjuntos/{ativo_a}/ativar")
        resposta = client.post("/api/jobs/recalcular")
        pontos_b = [v["pontos"] for v in client.get(f"/api/jobs?conjunto_id={b}").json()["items"]]
    assert resposta.json() == {"atualizadas": 1, "total": 3}
    assert pontos_b == [3 + settings.filtro.peso_titulo]


def test_filtro_de_pontuacao_minima_na_lista_e_em_marcar_como_vistas(settings):
    vagas = [
        Job("1", "Engenheiro Mecânico Projetista", "ACME", "https://x/1", "", "stub"),
        Job("2", "Engenheiro Mecânico", "Beta", "https://x/2", "", "stub"),
    ]
    with make_client(settings, [StubSource(jobs=vagas)]) as client:
        client.post("/api/keywords", json={"termo": "Projetista", "tipo": "ranking"})
        client.post("/api/runs")
        peso = settings.filtro.peso_titulo
        todas = client.get("/api/jobs").json()
        filtradas = client.get(f"/api/jobs?min_pontos={2 * peso}").json()
        marcadas = client.post("/api/jobs/mark-seen", json={"min_pontos": 2 * peso}).json()
        invalida = client.get("/api/jobs?min_pontos=-1")
    assert todas["total"] == 2
    assert [v["titulo"] for v in filtradas["items"]] == ["Engenheiro Mecânico Projetista"]
    assert filtradas["total"] == 1
    assert marcadas == {"atualizadas": 1}
    assert invalida.status_code == 422


def test_busca_aceita_sequencia_de_conjuntos_e_gera_uma_execucao_por_conjunto(client):
    primeiro = client.get("/api/conjuntos").json()[0]["id"]
    segundo = client.post("/api/conjuntos", json={"nome": "Soldador"}).json()["id"]
    client.post("/api/keywords", json={"termo": "soldador", "tipo": "busca"})
    resposta = client.post("/api/runs", json={"conjunto_ids": [segundo, primeiro]})
    assert resposta.status_code == 202
    historico = client.get("/api/runs").json()
    assert [run["conjunto"] for run in reversed(historico)] == ["Soldador", "Padrão"]
    assert resposta.json()["id"] == historico[-1]["id"]


def test_busca_rejeita_sequencia_com_conjunto_inexistente(client):
    primeiro = client.get("/api/conjuntos").json()[0]["id"]
    assert client.post("/api/runs", json={"conjunto_ids": [primeiro, 999]}).status_code == 404
    assert client.post("/api/runs", json={"conjunto_ids": [primeiro, primeiro]}).status_code == 422


def test_sequencia_salva_e_devolve_a_ordem(client):
    assert client.get("/api/conjuntos/sequencia").json() == {"conjunto_ids": []}
    primeiro = client.get("/api/conjuntos").json()[0]["id"]
    segundo = client.post("/api/conjuntos", json={"nome": "Soldador"}).json()["id"]
    resposta = client.put("/api/conjuntos/sequencia", json={"conjunto_ids": [segundo, primeiro]})
    assert resposta.status_code == 200
    assert resposta.json() == {"conjunto_ids": [segundo, primeiro]}
    assert client.get("/api/conjuntos/sequencia").json() == {"conjunto_ids": [segundo, primeiro]}


def test_sequencia_rejeita_conjunto_inexistente_ou_repetido(client):
    primeiro = client.get("/api/conjuntos").json()[0]["id"]
    assert client.put("/api/conjuntos/sequencia", json={"conjunto_ids": [999]}).status_code == 404
    assert client.put("/api/conjuntos/sequencia", json={"conjunto_ids": [primeiro, primeiro]}).status_code == 422


class FonteQueFalhaUmaVez:
    """Fonte paginada que cai na segunda página na primeira vez; guarda a configuração e a posição que recebeu."""

    def __init__(self, run_settings=None):
        self.name = "stub"
        self.settings = run_settings
        self.falhou = False
        self.inicios = []

    def search_and_enrich(self, termos, select_jobs, on_job=None, inicio=(0, 0), on_page=None):
        self.inicios.append(inicio)
        if not self.falhou:
            self.falhou = True
            for vaga in select_jobs([job("1")]):
                on_job(vaga)
            on_page(0, 1)
            raise SourceRateLimited("HTTP 429", motivo="http_erro")
        for vaga in select_jobs([job("2")]):
            on_job(vaga)
        on_page(1, 0)
        return [job("2")]


def test_retomar_continua_a_mesma_execucao_da_pagina_gravada_com_os_parametros_originais(settings, monkeypatch):
    fonte = FonteQueFalhaUmaVez()
    configuracoes = []

    def build(run_settings, gate):
        configuracoes.append(run_settings.busca)
        return [fonte]

    monkeypatch.setattr(runs_route, "build_sources", build)
    with make_client(settings, [fonte]) as test_client:
        primeira = test_client.post("/api/runs", json={"localidade": "São Paulo", "modalidade": "remoto", "janela_dias": 7}).json()["id"]
        assert test_client.get(f"/api/runs/{primeira}").json()["fontes"][0]["status"] == "falha"

        # a barra mudou depois da falha: a retomada ignora e refaz a mesma busca
        resposta = test_client.post("/api/runs", json={"retomar_run_id": primeira, "janela_dias": 1, "localidade": "Bahia"})

        assert (resposta.status_code, resposta.json()["id"]) == (202, primeira)
        run = test_client.get(f"/api/runs/{primeira}").json()
    assert fonte.inicios == [(0, 0), (0, 1)]
    assert (configuracoes[-1].janela_dias, configuracoes[-1].localidades, configuracoes[-1].modalidade) == (7, ["São Paulo"], ["remoto"])
    assert (run["status"], run["fontes"][0]["status"], run["fontes"][0]["novas"]) == ("concluida", "ok", 2)


def test_retomar_execucao_inexistente_ou_sem_falha_e_rejeitado(client):
    assert client.post("/api/runs", json={"retomar_run_id": 999}).status_code == 404
    ok = client.post("/api/runs").json()["id"]
    resposta = client.post("/api/runs", json={"retomar_run_id": ok})
    assert resposta.status_code == 422
