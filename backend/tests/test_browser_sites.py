"""Partes puras das fontes de navegador: URLs, detecção de bloqueio e mapeamento de vagas."""
import pytest

from backend.app.sources.indeed import IndeedSite
from backend.app.sources.linkedin import LinkedInSite


def with_busca(settings, **changes):
    busca = settings.busca.__class__(**{**settings.busca.__dict__, **changes})
    return settings.__class__(**{**settings.__dict__, "busca": busca})


# ---------- LinkedIn ----------

def test_linkedin_url_traz_termo_local_janela_e_pagina(settings):
    url = LinkedInSite(with_busca(settings, localidade="Brasil")).search_url("Engenheiro Mecânico", start=25)
    assert url.startswith("https://www.linkedin.com/jobs/search/?")
    assert "keywords=Engenheiro+Mec%C3%A2nico" in url
    assert "location=Brasil" in url
    assert "f_TPR=r86400" in url
    assert "start=25" in url
    assert "f_WT" not in url


@pytest.mark.parametrize("modalidade,codigo", [("presencial", "1"), ("remoto", "2"), ("hibrido", "3")])
def test_linkedin_modalidade_vira_f_wt(settings, modalidade, codigo):
    url = LinkedInSite(with_busca(settings, modalidade=modalidade)).search_url("x", 0)
    assert f"f_WT={codigo}" in url


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


def test_linkedin_card_sem_id_ou_titulo_e_ignorado(settings):
    site = LinkedInSite(settings)
    assert site.to_job({"id": "", "title": "x", "company": "", "text": ""}) is None
    assert site.to_job({"id": "1", "title": "", "company": "", "text": ""}) is None


# ---------- Indeed ----------

def test_indeed_url_traz_termo_local_dias_e_pagina(settings):
    url = IndeedSite(with_busca(settings, localidade="Brasil")).search_url("Engenheiro Mecânico", start=10)
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
