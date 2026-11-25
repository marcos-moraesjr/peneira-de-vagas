import pytest

from backend.app.sources.types import Job
from backend.tests.api_support import StubSource, make_client


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


def test_local_filtra_por_cidade_estado_ou_modalidade_ignorando_acento_e_maiuscula(client_ordenacao):
    assert titulos(client_ordenacao, "local=CAMPINAS") == ["Engenheiro Mecânico 2"]
    assert titulos(client_ordenacao, "local=recife") == ["Engenheiro Mecânico 1"]
    assert titulos(client_ordenacao, "local=pe") == ["Engenheiro Mecânico 1"]
    assert titulos(client_ordenacao, "local=SP") == ["Engenheiro Mecânico 2"]
    assert titulos(client_ordenacao, "local=Pernambuco") == ["Engenheiro Mecânico 1"]
    assert titulos(client_ordenacao, "local=Remoto") == ["Engenheiro Mecânico 2"]
    assert titulos(client_ordenacao, "local=hibrido") == ["Engenheiro Mecânico 3"]
    assert client_ordenacao.get("/api/jobs?local=campinas").json()["total"] == 1


def test_local_vazio_ou_em_branco_nao_filtra(client_ordenacao):
    assert len(titulos(client_ordenacao, "local=")) == 3
    assert len(titulos(client_ordenacao, "local=%20%20")) == 3


def test_local_combina_com_os_outros_filtros(client_ordenacao):
    assert titulos(client_ordenacao, "local=campinas&q=zeta") == []
    assert titulos(client_ordenacao, "local=pe&q=zeta") == ["Engenheiro Mecânico 1"]


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


def test_marcar_como_vistas_respeita_local(client_ordenacao):
    assert client_ordenacao.post("/api/jobs/mark-seen", json={"local": "recife"}).json() == {"atualizadas": 1}
    assert client_ordenacao.post("/api/jobs/mark-seen", json={"local": "sp"}).json() == {"atualizadas": 1}
    assert client_ordenacao.post("/api/jobs/mark-seen", json={"local": "híbrido"}).json() == {"atualizadas": 1}
    assert client_ordenacao.get("/api/jobs?visto=false").json()["items"] == []
