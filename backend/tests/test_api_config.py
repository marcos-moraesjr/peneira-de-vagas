import threading

from backend.app import db
from backend.tests.api_support import NOW, StubSource, job, make_client


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


def test_rota_de_aba_devolve_o_front_mas_api_desconhecida_continua_404(settings):
    settings.geral.frontend_dist.mkdir(parents=True)
    (settings.geral.frontend_dist / "index.html").write_text("<html>app</html>", encoding="utf-8")
    with make_client(settings, [StubSource()]) as test_client:
        resposta = test_client.get("/como-usar")
        assert resposta.status_code == 200 and "app" in resposta.text
        assert test_client.get("/execucoes").status_code == 200
        assert test_client.get("/api/nao-existe").status_code == 404
        assert test_client.get("/arquivo-inexistente.js").status_code == 404


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


def test_rota_de_instrucao_para_refazer_a_documentacao_foi_removida(client):
    assert client.get("/api/scanners/instrucao").status_code == 404


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


def test_localidade_da_execucao_somente_aceita_estado_brasileiro(client):
    resposta = client.post("/api/runs", json={"localidade": "Campinas, SP"})
    assert resposta.status_code == 422
    assert "estado brasileiro" in resposta.json()["detail"]


def test_modalidade_da_execucao_somente_aceita_valor_conhecido(client):
    resposta = client.post("/api/runs", json={"modalidade": "nuvem"})
    assert resposta.status_code == 422
    assert "modalidade" in resposta.json()["detail"]


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
