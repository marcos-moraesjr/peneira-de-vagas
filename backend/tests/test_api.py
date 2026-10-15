import threading

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

    def enrich(self, jobs, on_job=None):
        for j in jobs:
            if on_job:
                on_job(j)
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


@pytest.fixture
def client_ordenacao(settings):
    vagas = [
        Job("1", "Engenheiro Mecânico 1", "Zeta", "https://x/1", "", "stub", localidade="Recife, PE", publicada_em="2026-10-01T10:00:00Z", modalidade="presencial", palavra_chave="Projetista"),
        Job("2", "Engenheiro Mecânico 2", "Álamo", "https://x/2", "", "stub", localidade="Campinas, SP", publicada_em="2026-10-09T10:00:00Z", modalidade="remoto", palavra_chave="Analista de projetos"),
        Job("3", "Engenheiro Mecânico 3", "Beta", "https://x/3", "", "stub", localidade="", publicada_em=None, modalidade="hibrido", palavra_chave="Engenheiro Mecânico"),
    ]
    with make_client(settings, [StubSource(jobs=vagas)]) as test_client:
        test_client.post("/api/runs")
        yield test_client


def titulos(client, query):
    return [j["titulo"] for j in client.get(f"/api/jobs?{query}").json()["items"]]


def test_ordena_por_texto_ignorando_acento_e_maiuscula(client_ordenacao):
    assert titulos(client_ordenacao, "ordenar=empresa&direcao=asc") == ["Engenheiro Mecânico 2", "Engenheiro Mecânico 3", "Engenheiro Mecânico 1"]
    assert titulos(client_ordenacao, "ordenar=empresa&direcao=desc") == ["Engenheiro Mecânico 1", "Engenheiro Mecânico 3", "Engenheiro Mecânico 2"]


def test_ordena_por_data_de_publicacao_e_vagas_sem_data_ficam_no_fim_nas_duas_direcoes(client_ordenacao):
    assert titulos(client_ordenacao, "ordenar=publicada_em&direcao=desc") == ["Engenheiro Mecânico 2", "Engenheiro Mecânico 1", "Engenheiro Mecânico 3"]
    assert titulos(client_ordenacao, "ordenar=publicada_em&direcao=asc") == ["Engenheiro Mecânico 1", "Engenheiro Mecânico 2", "Engenheiro Mecânico 3"]


def test_ordenacao_vale_na_paginacao(client_ordenacao):
    pagina2 = titulos(client_ordenacao, "ordenar=localidade&direcao=asc&limit=1&offset=1")
    assert pagina2 == ["Engenheiro Mecânico 2"]  # ordem: '' (sem local), Campinas, Recife


def test_ordenacao_invalida_devolve_422_com_valor_e_esperado(client_ordenacao):
    resposta = client_ordenacao.get("/api/jobs?ordenar=senha&direcao=asc")
    assert resposta.status_code == 422 and "senha" in resposta.json()["detail"] and "titulo" in resposta.json()["detail"]
    assert client_ordenacao.get("/api/jobs?ordenar=titulo&direcao=lateral").status_code == 422


def test_sem_ordenacao_mantem_a_ordem_padrao(client_ordenacao):
    assert titulos(client_ordenacao, "") == ["Engenheiro Mecânico 3", "Engenheiro Mecânico 2", "Engenheiro Mecânico 1"]


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


def test_instrucao_de_documentacao_usa_as_palavras_chave_cadastradas(client):
    corpo = client.get("/api/scanners/instrucao").json()
    assert '"Engenheiro Mecânico"' in corpo["instrucao"]
    for rotulo in ("LinkedIn", "Indeed", "Gupy"):
        assert rotulo in corpo["instrucao"]


def test_instrucao_de_documentacao_de_uma_fonte_e_fonte_invalida(client):
    gupy = client.get("/api/scanners/instrucao?fonte=gupy").json()["instrucao"]
    assert "Gupy" in gupy and "LinkedIn" not in gupy
    resposta = client.get("/api/scanners/instrucao?fonte=orkut")
    assert resposta.status_code == 422 and "orkut" in resposta.json()["detail"]


def test_busca_numa_fonte_especifica_roda_so_ela(settings):
    sources = [StubSource("a", [job("1", fonte="a")]), StubSource("b", [job("2", fonte="b")])]
    with make_client(settings, sources) as test_client:
        resposta = test_client.post("/api/runs", json={"fontes": ["b"]})
        run = test_client.get(f"/api/runs/{resposta.json()['id']}").json()
    assert [fonte["fonte"] for fonte in run["fontes"]] == ["b"]


def test_busca_em_varias_fontes_roda_so_as_escolhidas_na_ordem_do_registro(settings):
    sources = [StubSource("a"), StubSource("b"), StubSource("c")]
    with make_client(settings, sources) as test_client:
        resposta = test_client.post("/api/runs", json={"fontes": ["c", "a"]})
        run = test_client.get(f"/api/runs/{resposta.json()['id']}").json()
    assert [fonte["fonte"] for fonte in run["fontes"]] == ["a", "c"]


def test_busca_com_lista_vazia_devolve_422(settings):
    with make_client(settings, [StubSource("a")]) as test_client:
        resposta = test_client.post("/api/runs", json={"fontes": []})
    assert resposta.status_code == 422 and "fontes" in resposta.json()["detail"]


def test_busca_com_fonte_nula_roda_todas(settings):
    sources = [StubSource("a"), StubSource("b")]
    with make_client(settings, sources) as test_client:
        resposta = test_client.post("/api/runs", json={"fontes": None})
        run = test_client.get(f"/api/runs/{resposta.json()['id']}").json()
    assert [fonte["fonte"] for fonte in run["fontes"]] == ["a", "b"]


def test_busca_numa_fonte_inexistente_devolve_422_com_valor_e_esperado(settings):
    with make_client(settings, [StubSource("a"), StubSource("b")]) as test_client:
        resposta = test_client.post("/api/runs", json={"fontes": ["a", "x"]})
    assert resposta.status_code == 422
    assert "x" in resposta.json()["detail"] and "['a', 'b']" in resposta.json()["detail"]


def test_conjuntos_criar_ativar_e_remover(client):
    lista = client.get("/api/conjuntos").json()
    assert [(c["nome"], c["ativo"]) for c in lista] == [("Padrão", True)]
    padrao_id = lista[0]["id"]

    criado = client.post("/api/conjuntos", json={"nome": "Tecnologia"})
    assert criado.status_code == 201 and criado.json()["ativo"] is True
    assert client.get("/api/keywords?tipo=busca").json() == []  # as palavras seguem o conjunto ativo
    client.post("/api/keywords", json={"termo": "Dados", "tipo": "busca"})

    assert client.post(f"/api/conjuntos/{padrao_id}/ativar").status_code == 204
    assert [k["termo"] for k in client.get("/api/keywords?tipo=busca").json()] == ["Engenheiro Mecânico"]

    assert client.delete(f"/api/conjuntos/{criado.json()['id']}").status_code == 204
    assert client.delete(f"/api/conjuntos/{padrao_id}").status_code == 422  # é o último
    assert client.delete("/api/conjuntos/999").status_code == 404
    assert client.post("/api/conjuntos/999/ativar").status_code == 404
    assert client.post("/api/conjuntos", json={"nome": " "}).status_code == 422
    assert client.post("/api/conjuntos", json={"nome": "padrão"}).status_code == 422


def test_conjuntos_copiar(client):
    padrao = client.get("/api/conjuntos").json()[0]
    client.post("/api/keywords", json={"termo": "AutoCAD", "tipo": "ranking"})

    resposta = client.post(f"/api/conjuntos/{padrao['id']}/copiar", json={"nome": " Cópia  do padrão "})
    assert resposta.status_code == 201
    copia = resposta.json()
    assert (copia["nome"], copia["ativo"]) != ("", False) and copia["nome"] == "Cópia do padrão" and copia["ativo"] is True
    assert [(c["nome"], c["ativo"]) for c in client.get("/api/conjuntos").json()] == [("Padrão", False), ("Cópia do padrão", True)]
    assert [k["termo"] for k in client.get("/api/keywords?tipo=ranking").json()] == ["AutoCAD"]  # as palavras vieram junto

    assert client.post(f"/api/conjuntos/{padrao['id']}/copiar", json={"nome": "padrão"}).status_code == 422
    assert client.post(f"/api/conjuntos/{padrao['id']}/copiar", json={"nome": " "}).status_code == 422
    assert client.post("/api/conjuntos/999/copiar", json={"nome": "Qualquer"}).status_code == 404


def test_conjuntos_renomear(client):
    padrao_id = client.get("/api/conjuntos").json()[0]["id"]
    outro = client.post("/api/conjuntos", json={"nome": "Tecnologia"}).json()

    resposta = client.patch(f"/api/conjuntos/{padrao_id}", json={"nome": " Engenharia  mecânica "})
    assert resposta.status_code == 200
    assert resposta.json() == {"id": padrao_id, "nome": "Engenharia mecânica", "ativo": False}
    assert [(c["nome"], c["ativo"]) for c in client.get("/api/conjuntos").json()] == [
        ("Engenharia mecânica", False),
        ("Tecnologia", True),
    ]

    assert client.patch(f"/api/conjuntos/{padrao_id}", json={"nome": "tecnologia"}).status_code == 422  # de outro conjunto
    assert client.patch(f"/api/conjuntos/{outro['id']}", json={"nome": " "}).status_code == 422
    assert client.patch("/api/conjuntos/999", json={"nome": "Qualquer"}).status_code == 404


def test_verificacao_lista_as_fontes_esperando_o_usuario(client):
    assert client.get("/api/verificacao").json() == {"fontes": []}
    gate = client.app.state.gate
    esperando = threading.Thread(target=lambda: gate.wait("indeed", 5))
    esperando.start()
    for _ in range(200):
        if gate.waiting():
            break
        threading.Event().wait(0.01)
    assert client.get("/api/verificacao").json() == {"fontes": ["indeed"]}
    assert client.post("/api/verificacao/indeed/confirmar").status_code == 204
    esperando.join(2)
    assert client.get("/api/verificacao").json() == {"fontes": []}


def test_confirmar_fonte_que_nao_espera_devolve_409(client):
    resposta = client.post("/api/verificacao/indeed/confirmar")
    assert resposta.status_code == 409
    assert "indeed" in resposta.json()["detail"]


def test_max_dias_descarta_vagas_publicadas_ha_mais_de_x_dias_e_mantem_as_sem_data(client_ordenacao):
    # "agora" = 2026-10-14: 7 dias → corte em 2026-10-07 (a vaga de 10-01 sai; a sem data fica)
    assert sorted(titulos(client_ordenacao, "max_dias=7")) == ["Engenheiro Mecânico 2", "Engenheiro Mecânico 3"]
    assert client_ordenacao.get("/api/jobs?max_dias=7").json()["total"] == 2
    assert len(titulos(client_ordenacao, "max_dias=30")) == 3


def test_max_dias_invalido_devolve_422(client_ordenacao):
    assert client_ordenacao.get("/api/jobs?max_dias=0").status_code == 422


def test_marcar_como_vistas_respeita_max_dias(client_ordenacao):
    resposta = client_ordenacao.post("/api/jobs/mark-seen", json={"max_dias": 7})
    assert resposta.json() == {"atualizadas": 2}
    restantes = client_ordenacao.get("/api/jobs?visto=false").json()["items"]
    assert [j["titulo"] for j in restantes] == ["Engenheiro Mecânico 1"]


def test_cidade_e_estado_filtram_as_vagas_ja_encontradas_ignorando_acento_e_maiuscula(client_ordenacao):
    assert titulos(client_ordenacao, "cidade=CAMPINAS") == ["Engenheiro Mecânico 2"]
    assert titulos(client_ordenacao, "cidade=recife") == ["Engenheiro Mecânico 1"]
    assert titulos(client_ordenacao, "estado=pe") == ["Engenheiro Mecânico 1"]
    assert titulos(client_ordenacao, "estado=SP") == ["Engenheiro Mecânico 2"]
    assert client_ordenacao.get("/api/jobs?cidade=campinas").json()["total"] == 1


def test_cidade_e_estado_vazios_ou_em_branco_nao_filtram(client_ordenacao):
    assert len(titulos(client_ordenacao, "cidade=&estado=")) == 3
    assert len(titulos(client_ordenacao, "cidade=%20%20")) == 3


def test_cidade_e_estado_combinam_entre_si_e_com_os_outros_filtros(client_ordenacao):
    assert titulos(client_ordenacao, "cidade=campinas&estado=pe") == []
    assert titulos(client_ordenacao, "cidade=campinas&q=zeta") == []
    assert titulos(client_ordenacao, "estado=pe&q=zeta") == ["Engenheiro Mecânico 1"]


def test_vagas_trazem_a_modalidade(client_ordenacao):
    itens = {j["titulo"]: j["modalidade"] for j in client_ordenacao.get("/api/jobs").json()["items"]}
    assert itens == {"Engenheiro Mecânico 1": "presencial", "Engenheiro Mecânico 2": "remoto", "Engenheiro Mecânico 3": "hibrido"}


def test_modalidade_filtra_e_valor_invalido_devolve_422(client_ordenacao):
    assert titulos(client_ordenacao, "modalidade=remoto") == ["Engenheiro Mecânico 2"]
    assert titulos(client_ordenacao, "modalidade=") != []
    resposta = client_ordenacao.get("/api/jobs?modalidade=nuvem")
    assert resposta.status_code == 422 and "nuvem" in resposta.json()["detail"] and "remoto" in resposta.json()["detail"]


def test_ordena_por_modalidade(client_ordenacao):
    assert titulos(client_ordenacao, "ordenar=modalidade&direcao=asc") == ["Engenheiro Mecânico 3", "Engenheiro Mecânico 1", "Engenheiro Mecânico 2"]


def test_vagas_trazem_a_palavra_chave_que_as_encontrou(client_ordenacao):
    itens = {j["titulo"]: j["palavra_chave"] for j in client_ordenacao.get("/api/jobs").json()["items"]}
    assert itens == {
        "Engenheiro Mecânico 1": "Projetista",
        "Engenheiro Mecânico 2": "Analista de projetos",
        "Engenheiro Mecânico 3": "Engenheiro Mecânico",
    }


def test_ordena_por_palavra_chave(client_ordenacao):
    assert titulos(client_ordenacao, "ordenar=palavra_chave&direcao=asc") == ["Engenheiro Mecânico 2", "Engenheiro Mecânico 3", "Engenheiro Mecânico 1"]


def test_marcar_como_vistas_respeita_cidade_estado_e_modalidade(client_ordenacao):
    assert client_ordenacao.post("/api/jobs/mark-seen", json={"cidade": "recife"}).json() == {"atualizadas": 1}
    assert client_ordenacao.post("/api/jobs/mark-seen", json={"estado": "sp"}).json() == {"atualizadas": 1}
    assert client_ordenacao.post("/api/jobs/mark-seen", json={"modalidade": "hibrido"}).json() == {"atualizadas": 1}
    assert client_ordenacao.get("/api/jobs?visto=false").json()["items"] == []


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
