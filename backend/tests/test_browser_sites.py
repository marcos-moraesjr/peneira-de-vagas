"""Partes puras das fontes de navegador: URLs, detecção de bloqueio e mapeamento de vagas."""
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.app.sources.google import GoogleSite
from backend.app.sources.indeed import IndeedSite
from backend.app.sources.linkedin import LinkedInSite


def with_busca(settings, **changes):
    busca = settings.busca.__class__(**{**settings.busca.__dict__, **changes})
    return settings.__class__(**{**settings.__dict__, "busca": busca})


# ---------- LinkedIn ----------

def test_linkedin_url_traz_termo_local_janela_e_pagina(settings):
    url = LinkedInSite(settings).search_url("Engenheiro Mecânico", start=25, localidade="Brasil")
    assert url.startswith("https://www.linkedin.com/jobs/search/?")
    assert "keywords=Engenheiro+Mec%C3%A2nico" in url
    assert "location=Brasil" in url
    assert "f_TPR=r86400" in url
    assert "start=25" in url
    assert "f_WT" not in url


@pytest.mark.parametrize("modalidade,codigo", [("presencial", "1"), ("remoto", "2"), ("hibrido", "3")])
def test_linkedin_modalidade_vira_f_wt(settings, modalidade, codigo):
    url = LinkedInSite(with_busca(settings, modalidade=[modalidade])).search_url("x", 0)
    assert f"f_WT={codigo}" in url


def test_linkedin_varias_modalidades_viram_f_wt_separado_por_virgula(settings):
    url = LinkedInSite(with_busca(settings, modalidade=["hibrido", "remoto"])).search_url("x", 0)
    assert "f_WT=2%2C3" in url


@pytest.mark.parametrize(
    "url,motivo",
    [
        ("https://www.linkedin.com/checkpoint/challenge/abc", "captcha"),
        ("https://www.linkedin.com/authwall?trk=x", "login"),
        ("https://www.linkedin.com/login?session_redirect=x", "login"),
        ("https://www.linkedin.com/uas/login", "login"),
        ("https://www.linkedin.com/jobs/search/?keywords=x", None),
    ],
)
def test_linkedin_detecta_login_e_verificacao_pela_url(settings, url, motivo):
    assert LinkedInSite(settings).classify(url, "LinkedIn", "") == motivo


def test_linkedin_mapeia_card_para_vaga_com_link_canonico(settings):
    raw = {"id": "3900000001", "title": "Engenheiro Mecânico", "company": "ACME", "text": "Campinas"}
    job = LinkedInSite(settings).to_job(raw)
    assert job.link == "https://www.linkedin.com/jobs/view/3900000001/"
    assert (job.fonte, job.empresa, job.trecho) == ("linkedin", "ACME", "Campinas")
    assert job.localidade == "Campinas" and job.publicada_em is None  # o card não traz data


def test_linkedin_card_sem_id_ou_titulo_e_ignorado(settings):
    site = LinkedInSite(settings)
    assert site.to_job({"id": "", "title": "x", "company": "", "text": ""}) is None
    assert site.to_job({"id": "1", "title": "", "company": "", "text": ""}) is None


# ---------- Indeed ----------

def test_indeed_url_traz_termo_local_dias_e_pagina(settings):
    url = IndeedSite(settings).search_url("Engenheiro Mecânico", start=10, localidade="Brasil")
    assert url.startswith("https://br.indeed.com/jobs?")
    assert "q=Engenheiro+Mec%C3%A2nico" in url
    assert "l=Brasil" in url
    assert "fromage=1" in url
    assert "start=10" in url


def test_indeed_janela_em_horas_vira_dias_arredondando_para_cima(settings):
    assert "fromage=2" in IndeedSite(with_busca(settings, janela_horas=30)).search_url("x", 0)


@pytest.mark.parametrize(
    "url,title,text,motivo",
    [
        ("https://br.indeed.com/jobs?q=x", "Just a moment...", "", "cloudflare"),
        ("https://br.indeed.com/jobs?q=x", "Um momento…", "", "cloudflare"),
        ("https://br.indeed.com/jobs?q=x", "Indeed", "Verifique se você é humano", "cloudflare"),
        ("https://br.indeed.com/jobs?q=x", "Indeed", "Additional Verification Required", "captcha"),
        ("https://secure.indeed.com/auth?x=1", "Entrar", "", "login"),
        ("https://br.indeed.com/jobs?q=x", "Vagas de engenheiro", "100 vagas", None),
    ],
)
def test_indeed_detecta_bloqueios(settings, url, title, text, motivo):
    assert IndeedSite(settings).classify(url, title, text) == motivo


def test_indeed_mapeia_card_para_vaga_com_link_canonico(settings):
    raw = {"id": "abc123", "title": "Engenheiro Mecânico", "company": "ACME", "text": "Projetos"}
    job = IndeedSite(settings).to_job(raw)
    assert job.link == "https://br.indeed.com/viewjob?jk=abc123"
    assert job.fonte == "indeed"
    assert job.publicada_em is None  # o card não traz data


def test_indeed_localidade_vem_do_card(settings):
    raw = {"id": "abc123", "title": "Engenheiro", "company": "ACME", "text": "Projetos", "location": "São Paulo, SP"}
    assert IndeedSite(settings).to_job(raw).localidade == "São Paulo, SP"
    assert IndeedSite(settings).to_job({**raw, "location": ""}).localidade == ""


def test_marcadores_de_pagina_sem_resultado(settings):
    assert LinkedInSite(settings).is_empty_page("Nenhuma vaga correspondente foi encontrada")
    assert IndeedSite(settings).is_empty_page("Sua busca não encontrou nenhum resultado")
    assert not LinkedInSite(settings).is_empty_page("Resultados da busca")


# ---------- Busca como observada (sem localidade) ----------

def test_sem_localidade_a_url_nao_envia_location_nem_l(settings):
    assert "location" not in LinkedInSite(settings).search_url("x", 0)
    assert "l=" not in IndeedSite(settings).search_url("x", 0)


def test_linkedin_card_nao_renderizado_so_com_id_e_ignorado(settings):
    assert LinkedInSite(settings).to_job({"id": "3900000003", "title": "", "company": "", "text": ""}) is None


def test_somente_o_linkedin_le_cards_de_forma_incremental(settings):
    assert LinkedInSite(settings).lazy_cards is True
    assert IndeedSite(settings).lazy_cards is False
    assert LinkedInSite(settings).card_selector == "li[data-occludable-job-id]"


# ---------- Google (busca booleana) ----------

def test_google_url_traz_consulta_booleana_inteira_janela_em_dias_e_pagina(settings):
    consulta = 'site:lever.co OR site:greenhouse.io intitle:(".net" OR "developer") -"US only" -india'
    url = GoogleSite(settings).search_url(consulta, start=10)
    assert url.startswith("https://www.google.com/search?")
    assert parse_qs(urlsplit(url).query) == {"q": [consulta], "tbs": ["qdr:d"], "start": ["10"]}


def test_google_janela_em_horas_vira_dias_arredondando_para_cima(settings):
    query = parse_qs(urlsplit(GoogleSite(with_busca(settings, janela_horas=30)).search_url("x", 0)).query)
    assert query["tbs"] == ["qdr:d2"]


@pytest.mark.parametrize(
    "url,title,text,motivo",
    [
        ("https://www.google.com/sorry/index?continue=x", "https://www.google.com/search", "", "captcha"),
        ("https://www.google.com/search?q=x", "Google", "Nossos sistemas detectaram tráfego incomum", "captcha"),
        ("https://www.google.com/search?q=x", "Google", "Our systems have detected unusual traffic", "captcha"),
        ("https://consent.google.com/m?continue=x", "Antes de continuar", "", "login"),
        ("https://accounts.google.com/signin", "Fazer login", "", "login"),
        ("https://www.google.com/search?q=x", "x - Pesquisa Google", "Resultados da pesquisa", None),
    ],
)
def test_google_detecta_bloqueios(settings, url, title, text, motivo):
    assert GoogleSite(settings).classify(url, title, text) == motivo


def test_google_marcadores_de_pagina_sem_resultado(settings):
    site = GoogleSite(settings)
    assert site.is_empty_page("Sua pesquisa - x - não encontrou nenhum documento correspondente.")
    assert site.is_empty_page("Your search - x - did not match any documents.")
    assert not site.is_empty_page("Resultados da pesquisa")


def test_google_mapeia_resultado_para_vaga_com_link_canonico_sem_rastreio(settings):
    raw = {"id": "https://jobs.lever.co/acme/123-abc?lever-source=x#apply", "title": "Senior .NET Engineer", "text": "Remote, LATAM"}
    job = GoogleSite(settings).to_job(raw)
    assert (job.id, job.link) == ("https://jobs.lever.co/acme/123-abc",) * 2
    assert (job.titulo, job.trecho, job.fonte, job.empresa) == ("Senior .NET Engineer", "Remote, LATAM", "google", "")


def test_google_desembrulha_link_de_redirecionamento(settings):
    raw = {"id": "/url?q=https://boards.greenhouse.io/acme/jobs/9%3Fgh_src%3Dx&sa=U", "title": "Dev", "text": ""}
    assert GoogleSite(settings).to_job(raw).link == "https://boards.greenhouse.io/acme/jobs/9"


@pytest.mark.parametrize(
    "raw",
    [
        {"id": "", "title": "x", "text": ""},
        {"id": "https://jobs.lever.co/acme/1", "title": "", "text": ""},
        {"id": "https://www.google.com/search?q=outra", "title": "x", "text": ""},
        {"id": "javascript:void(0)", "title": "x", "text": ""},
    ],
)
def test_google_resultado_sem_link_valido_ou_titulo_e_ignorado(settings, raw):
    assert GoogleSite(settings).to_job(raw) is None


def test_google_ignora_a_localidade_e_a_consulta_vai_inteira(settings):
    assert GoogleSite(settings).search_url("q", 0, "Brasil") == GoogleSite(settings).search_url("q", 0)
