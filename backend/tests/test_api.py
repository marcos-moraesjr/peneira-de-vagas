import pytest
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.main import create_app
from backend.app.sources.types import Job

NOW = "2026-10-14T12:00:00+00:00"


class StubSource:
    def __init__(self, name="stub", jobs=None):
        self.name = name
        self._jobs = jobs if jobs is not None else []

    def search(self, termos):
        return list(self._jobs)

    def enrich(self, jobs):
        return jobs


def job(id_da_vaga, titulo="Engenheiro Mecânico", fonte="stub", empresa="ACME"):
    return Job(id_da_vaga, titulo, empresa, f"https://x/{id_da_vaga}", "", fonte)


def make_client(settings, sources, spawn=lambda fn: fn()):
    app = create_app(settings, sources_factory=lambda: sources, spawn=spawn, now=lambda: NOW)
    return TestClient(app)


@pytest.fixture
def client(settings):
    sources = [StubSource(jobs=[job("1"), job("2", "Engenheiro Mecânico Sênior", empresa="Zeta Indústria")])]
    with make_client(settings, sources) as test_client:
        yield test_client


def test_health_informa_api_e_banco(client):
    assert client.get("/api/health").json() == {"status": "ok", "db": "ok"}


def test_iniciar_busca_devolve_202_e_resultado_por_fonte(client):
    resposta = client.post("/api/runs")
    assert resposta.status_code == 202
    run = client.get(f"/api/runs/{resposta.json()['id']}").json()
    assert run["status"] == "concluida"
    assert run["fontes"] == [
        {"fonte": "stub", "status": "ok", "motivo": None, "detalhe": None, "lidas": 2, "aprovadas": 2, "novas": 2, "scanner_versao": ""}
    ]


def test_segunda_busca_durante_uma_em_andamento_devolve_409(settings):
    with make_client(settings, [StubSource()], spawn=lambda fn: None) as test_client:
        assert test_client.post("/api/runs").status_code == 202
        resposta = test_client.post("/api/runs")
    assert resposta.status_code == 409
    assert "andamento" in resposta.json()["detail"]


def test_busca_sem_palavra_chave_devolve_422(client):
    for item in client.get("/api/keywords?tipo=busca").json():
        client.delete(f"/api/keywords/{item['id']}")
    resposta = client.post("/api/runs")
    assert resposta.status_code == 422
    assert "palavra-chave" in resposta.json()["detail"]


def test_historico_lista_execucoes_mais_recentes_primeiro(client):
    client.post("/api/runs")
    client.post("/api/runs")
    ids = [run["id"] for run in client.get("/api/runs").json()]
    assert ids == sorted(ids, reverse=True) and len(ids) == 2


def test_execucao_inexistente_devolve_404(client):
    assert client.get("/api/runs/999").status_code == 404


def test_vagas_novas_filtro_fonte_e_busca_sem_acento(client):
    client.post("/api/runs")
    todas = client.get("/api/jobs").json()
    assert todas["total"] == 2
    assert client.get("/api/jobs?fonte=gupy").json()["total"] == 0
    assert client.get("/api/jobs?q=industria").json()["total"] == 1
    assert client.get("/api/jobs?visto=false").json()["total"] == 2


def test_marcar_vaga_como_vista_e_desfazer(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    assert client.patch(f"/api/jobs/{vaga['id']}", json={"visto": True}).json()["visto"] is True
    assert client.get("/api/jobs?visto=false").json()["total"] == 1
    client.patch(f"/api/jobs/{vaga['id']}", json={"visto": False})
    assert client.get("/api/jobs?visto=false").json()["total"] == 2


def test_marcar_vaga_inexistente_devolve_404(client):
    assert client.patch("/api/jobs/999", json={"visto": True}).status_code == 404


def test_marcar_todas_como_vistas_respeita_os_filtros(client):
    client.post("/api/runs")
    resposta = client.post("/api/jobs/mark-seen", json={"q": "industria"})
    assert resposta.json() == {"atualizadas": 1}
    assert client.get("/api/jobs?visto=false").json()["total"] == 1


def test_paginacao_de_vagas(client):
    client.post("/api/runs")
    pagina = client.get("/api/jobs?limit=1&offset=1").json()
    assert pagina["total"] == 2 and len(pagina["items"]) == 1


def test_palavras_chave_crud_e_erros(client):
    padrao = client.get("/api/keywords?tipo=busca").json()
    assert [k["termo"] for k in padrao] == ["Engenheiro Mecânico"]
    criada = client.post("/api/keywords", json={"termo": "Projetista", "tipo": "busca"})
    assert criada.status_code == 201
    assert client.post("/api/keywords", json={"termo": "projetista", "tipo": "busca"}).status_code == 422
    assert client.post("/api/keywords", json={"termo": " ", "tipo": "busca"}).status_code == 422
    assert client.delete(f"/api/keywords/{criada.json()['id']}").status_code == 204
    assert client.delete(f"/api/keywords/{criada.json()['id']}").status_code == 404


def test_config_expoe_parametros_sem_segredos(client):
    corpo = client.get("/api/config").json()
    assert corpo["filtro"]["min_score"] == 3
    assert corpo["api"]["poll_interval_ms"] == 2000
    assert "db_path" not in str(corpo)


def test_ao_abrir_o_app_execucao_pendurada_e_encerrada(settings):
    conn = db.connect(settings.geral.db_path)
    db.init_db(conn, settings)
    run_id = db.create_run(conn, ["stub"], NOW)
    conn.close()
    with make_client(settings, [StubSource()]) as test_client:
        run = test_client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "concluida"
    assert run["fontes"][0]["motivo"] == "interrompida"


def test_serve_o_front_compilado_quando_existe(settings):
    settings.geral.frontend_dist.mkdir(parents=True)
    (settings.geral.frontend_dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    with make_client(settings, [StubSource()]) as test_client:
        assert "app" in test_client.get("/").text
        assert test_client.get("/api/health").status_code == 200


# ---------- scanners ----------

class BrokenLinkedIn:
    name = "linkedin"

    def search(self, termos):
        from backend.app.sources.errors import SourceLayoutChanged

        raise SourceLayoutChanged("Nenhum card encontrado em linkedin")

    def enrich(self, jobs):
        return jobs


def test_scanners_lista_versao_e_estado_de_cada_fonte(client):
    corpo = client.get("/api/scanners").json()
    assert [s["fonte"] for s in corpo] == ["linkedin", "indeed", "gupy"]
    primeiro = corpo[0]
    assert primeiro["status"] == "ok" and primeiro["versao"].count(".") == 2
    assert primeiro["gerado_por"] == "Claude" and primeiro["instrucao"] is None


def test_falhas_de_layout_seguidas_mandam_refazer_o_scanner(settings):
    with make_client(settings, [BrokenLinkedIn()]) as test_client:
        test_client.post("/api/runs")
        assert next(s for s in test_client.get("/api/scanners").json() if s["fonte"] == "linkedin")["status"] == "atencao"
        test_client.post("/api/runs")
        linkedin = next(s for s in test_client.get("/api/scanners").json() if s["fonte"] == "linkedin")
        run = test_client.get("/api/runs").json()[0]
    assert linkedin["status"] == "refazer"
    assert "backend/app/sources/linkedin.py" in linkedin["instrucao"]
    assert run["fontes"][0]["scanner_versao"] == linkedin["versao"]
