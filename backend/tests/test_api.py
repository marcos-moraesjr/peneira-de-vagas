from fastapi.testclient import TestClient

from backend.app import db
from backend.app.main import create_app
from backend.app.routes import runs as runs_route
from backend.tests.api_support import NOW, StubSource, job, make_client


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


def test_busca_padrao_registra_as_tres_fontes(settings):
    """A execução sem filtro explícito não pode perder a Gupy da lista de fontes."""
    with TestClient(create_app(settings, spawn=lambda fn: None, now=lambda: NOW)) as test_client:
        resposta = test_client.post("/api/runs")
        run = test_client.get(f"/api/runs/{resposta.json()['id']}").json()
    assert [fonte["fonte"] for fonte in run["fontes"]] == ["linkedin", "indeed", "gupy"]


def test_busca_aceita_janela_de_recencia_em_dias(settings, monkeypatch):
    source = StubSource(jobs=[job("1")])
    monkeypatch.setattr(runs_route, "build_sources", lambda run_settings, gate: [source])
    with make_client(settings, [source]) as test_client:
        response = test_client.post("/api/runs", json={"janela_dias": 7})
    assert response.status_code == 202


def test_busca_rejeita_janela_de_recencia_invalida(client):
    response = client.post("/api/runs", json={"janela_dias": 0})
    assert response.status_code == 422
    assert "janela_dias=0" in response.json()["detail"]


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


def test_limpar_historico_remove_execucoes_sem_vagas(settings):
    with make_client(settings, [StubSource()]) as test_client:
        test_client.post("/api/runs")
        test_client.post("/api/runs")
        resposta = test_client.delete("/api/runs")
        assert resposta.status_code == 200
        assert resposta.json() == {"removidas": 2}
        assert test_client.get("/api/runs").json() == []


def test_limpar_historico_apaga_tambem_execucoes_que_originaram_vagas_e_mantem_as_vagas(client):
    client.post("/api/runs")
    resposta = client.delete("/api/runs")
    assert resposta.json() == {"removidas": 1}
    assert client.get("/api/runs").json() == []
    vagas = client.get("/api/jobs").json()
    assert vagas["total"] == 2
    assert all(vaga["run_id"] is None for vaga in vagas["items"])


def test_limpar_historico_com_execucao_em_andamento_devolve_409(settings):
    with make_client(settings, [StubSource()], spawn=lambda fn: None) as test_client:
        test_client.post("/api/runs")
        resposta = test_client.delete("/api/runs")
    assert resposta.status_code == 409
    assert "andamento" in resposta.json()["detail"]


def test_excluir_uma_execucao_remove_so_ela_e_mantem_as_vagas(client):
    primeira = client.post("/api/runs").json()["id"]
    segunda = client.post("/api/runs").json()["id"]
    resposta = client.delete(f"/api/runs/{primeira}")
    assert resposta.status_code == 200
    assert resposta.json() == {"removidas": 1}
    assert [run["id"] for run in client.get("/api/runs").json()] == [segunda]
    assert client.get(f"/api/runs/{primeira}").status_code == 404
    assert client.get("/api/jobs").json()["total"] == 2


def test_excluir_execucao_inexistente_devolve_404(client):
    assert client.delete("/api/runs/999").status_code == 404


def test_excluir_execucao_em_andamento_devolve_409(settings):
    with make_client(settings, [StubSource()], spawn=lambda fn: None) as test_client:
        run_id = test_client.post("/api/runs").json()["id"]
        resposta = test_client.delete(f"/api/runs/{run_id}")
    assert resposta.status_code == 409
    assert "andamento" in resposta.json()["detail"]


def test_nao_ha_rota_para_interromper_uma_execucao(client):
    run_id = client.post("/api/runs").json()["id"]
    assert client.post(f"/api/runs/{run_id}/cancel").status_code in (404, 405)


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


def test_excluir_uma_vaga_esconde_da_lista_e_aparece_em_excluidas(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    assert client.patch(f"/api/jobs/{vaga['id']}", json={"excluida": True}).json()["excluida"] is True
    assert client.get("/api/jobs").json()["total"] == 1
    excluidas = client.get("/api/jobs?excluidas=true").json()
    assert excluidas["total"] == 1 and excluidas["items"][0]["id"] == vaga["id"]
    assert client.patch(f"/api/jobs/{vaga['id']}", json={"excluida": False}).json()["excluida"] is False
    assert client.get("/api/jobs").json()["total"] == 2
    assert client.get("/api/jobs?excluidas=true").json()["total"] == 0


def test_vaga_excluida_nao_volta_como_nova_numa_busca_e_nao_entra_em_marcar_como_vistas(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    client.patch(f"/api/jobs/{vaga['id']}", json={"excluida": True})
    client.post("/api/runs")
    assert client.get("/api/jobs").json()["total"] == 1
    assert client.post("/api/jobs/mark-seen", json={}).json() == {"atualizadas": 1}
    assert client.get("/api/jobs?excluidas=true").json()["items"][0]["visto"] is False


def test_candidatar_uma_vaga_tira_da_lista_e_leva_para_candidaturas(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    assert client.patch(f"/api/jobs/{vaga['id']}", json={"candidatada": True}).json()["candidatada"] is True
    assert client.get("/api/jobs").json()["total"] == 1
    assert client.get("/api/jobs?excluidas=true").json()["total"] == 0
    candidatadas = client.get("/api/jobs?candidatadas=true").json()
    assert candidatadas["total"] == 1 and candidatadas["items"][0]["id"] == vaga["id"]
    assert client.patch(f"/api/jobs/{vaga['id']}", json={"candidatada": False}).json()["candidatada"] is False
    assert client.get("/api/jobs").json()["total"] == 2
    assert client.get("/api/jobs?candidatadas=true").json()["total"] == 0


def test_candidatada_e_excluida_sao_excludentes(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    client.patch(f"/api/jobs/{vaga['id']}", json={"excluida": True})
    marcada = client.patch(f"/api/jobs/{vaga['id']}", json={"candidatada": True}).json()
    assert (marcada["candidatada"], marcada["excluida"]) == (True, False)
    marcada = client.patch(f"/api/jobs/{vaga['id']}", json={"excluida": True}).json()
    assert (marcada["candidatada"], marcada["excluida"]) == (False, True)


def test_vaga_candidatada_nao_volta_como_nova_nem_entra_em_marcar_como_vistas(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    client.patch(f"/api/jobs/{vaga['id']}", json={"candidatada": True})
    client.post("/api/runs")
    assert client.get("/api/jobs").json()["total"] == 1
    assert client.post("/api/jobs/mark-seen", json={}).json() == {"atualizadas": 1}
    assert client.get("/api/jobs?candidatadas=true").json()["items"][0]["visto"] is False


def test_candidatura_registra_a_data_e_desfazer_limpa(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    assert client.get("/api/jobs").json()["items"][0]["candidatada_em"] is None
    marcada = client.patch(f"/api/jobs/{vaga['id']}", json={"candidatada": True}).json()
    assert marcada["candidatada_em"] == NOW
    assert client.get("/api/jobs?candidatadas=true").json()["items"][0]["candidatada_em"] == NOW
    assert client.patch(f"/api/jobs/{vaga['id']}", json={"candidatada": False}).json()["candidatada_em"] is None


def test_exclusao_registra_a_data_e_restaurar_limpa(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    assert vaga["excluida_em"] is None
    assert client.patch(f"/api/jobs/{vaga['id']}", json={"excluida": True}).json()["excluida_em"] == NOW
    assert client.get("/api/jobs?excluidas=true").json()["items"][0]["excluida_em"] == NOW
    candidatada = client.patch(f"/api/jobs/{vaga['id']}", json={"candidatada": True}).json()
    assert (candidatada["excluida"], candidatada["excluida_em"]) == (False, None)
    client.patch(f"/api/jobs/{vaga['id']}", json={"excluida": True})
    assert client.patch(f"/api/jobs/{vaga['id']}", json={"excluida": False}).json()["excluida_em"] is None


def test_candidaturas_vem_da_mais_recente_para_a_mais_antiga(settings):
    relogio = [NOW]
    sources = [StubSource(jobs=[job("1"), job("2")])]
    app = create_app(settings, sources_factory=lambda: sources, spawn=lambda fn: fn(), now=lambda: relogio[0])
    with TestClient(app) as c:
        c.post("/api/runs")
        ids = [v["id"] for v in c.get("/api/jobs").json()["items"]]
        for id_, data in zip(ids, ["2026-10-15T10:00:00+00:00", "2026-10-16T10:00:00+00:00"]):
            relogio[0] = data
            c.patch(f"/api/jobs/{id_}", json={"candidatada": True})
        itens = c.get("/api/jobs?candidatadas=true").json()["items"]
    assert [i["id"] for i in itens] == ids[::-1]


def test_marcar_vaga_inexistente_devolve_404(client):
    assert client.patch("/api/jobs/999", json={"visto": True}).status_code == 404


def test_marcar_todas_como_vistas_respeita_os_filtros(client):
    client.post("/api/runs")
    resposta = client.post("/api/jobs/mark-seen", json={"q": "industria"})
    assert resposta.json() == {"atualizadas": 1}
    assert client.get("/api/jobs?visto=false").json()["total"] == 1


def test_excluir_todas_as_vagas_apaga_vistas_e_novas(client):
    client.post("/api/runs")
    vaga = client.get("/api/jobs").json()["items"][0]
    client.patch(f"/api/jobs/{vaga['id']}", json={"visto": True})
    resposta = client.delete("/api/jobs")
    assert resposta.status_code == 200 and resposta.json() == {"removidas": 2}
    assert client.get("/api/jobs").json()["total"] == 0


def test_excluir_todas_as_vagas_recusa_durante_execucao(settings):
    with make_client(settings, [StubSource(jobs=[job("1")])], spawn=lambda fn: None) as test_client:
        test_client.post("/api/runs")
        assert test_client.delete("/api/jobs").status_code == 409


def test_vagas_excluidas_voltam_como_novas_na_proxima_busca(client):
    client.post("/api/runs")
    client.delete("/api/jobs")
    client.post("/api/runs")
    assert client.get("/api/jobs?visto=false").json()["total"] == 2
