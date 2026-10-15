"""Partes puras das fontes de navegador: URLs, detecção de bloqueio e mapeamento de vagas."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.app.sources.indeed import IndeedSite
from backend.app.sources.linkedin import LinkedInSite
from backend.app.sources.relative_date import find_published_line, parse_relative_date


def with_busca(settings, **changes):
    busca = settings.busca.__class__(**{**settings.busca.__dict__, **changes})
    return settings.__class__(**{**settings.__dict__, "busca": busca})


# ---------- LinkedIn ----------

def test_linkedin_url_traz_termo_janela_e_pagina(settings):
    url = LinkedInSite(settings).search_url("Engenheiro Mecânico", start=25)
    assert url.startswith("https://www.linkedin.com/jobs/search/?")
    assert "keywords=Engenheiro+Mec%C3%A2nico" in url
    assert "f_TPR=r86400" in url
    assert "start=25" in url


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

def test_indeed_url_traz_termo_dias_e_pagina(settings):
    url = IndeedSite(settings).search_url("Engenheiro Mecânico", start=10)
    assert url.startswith("https://br.indeed.com/jobs?")
    assert "q=Engenheiro+Mec%C3%A2nico" in url
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


# ---------- Localidade e modalidade não vão para a busca (o filtro local decide) ----------

def test_localidade_e_modalidade_da_config_nao_entram_na_url_de_busca(settings):
    configurada = with_busca(settings, localidades=["Campinas, SP"], modalidade=["remoto", "hibrido"])
    for url in (LinkedInSite(configurada).search_url("x", 0), IndeedSite(configurada).search_url("x", 0)):
        assert "location" not in url and "f_WT" not in url and "l=" not in url and "Campinas" not in url


def test_linkedin_card_nao_renderizado_so_com_id_e_ignorado(settings):
    assert LinkedInSite(settings).to_job({"id": "3900000003", "title": "", "company": "", "text": ""}) is None


def test_somente_o_linkedin_le_cards_de_forma_incremental(settings):
    assert LinkedInSite(settings).lazy_cards is True
    assert IndeedSite(settings).lazy_cards is False
    assert LinkedInSite(settings).card_selector == "li[data-occludable-job-id]"


# ---------- LinkedIn: data de publicação relativa do detalhe ----------

AGORA = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Santana, São Paulo, Brasil · Anunciada novamente há 8 horas · 95 candidaturas", "2026-10-14T04:00:00Z"),
        ("Brasil · Há 3 dias · Mais de 100 candidaturas", "2026-10-11T12:00:00Z"),
        ("Brasil · Publicada há 1 semana", "2026-10-07T12:00:00Z"),
        ("Brasil · há 2 meses", "2026-08-15T12:00:00Z"),
        ("Brasil · há 45 minutos", "2026-10-14T11:15:00Z"),
        ("Brazil · Reposted 5 days ago · 20 applicants", "2026-10-09T12:00:00Z"),
    ],
)
def test_linkedin_converte_data_relativa_em_iso(texto, esperado):
    assert parse_relative_date(texto, AGORA) == esperado


def test_linkedin_sem_data_relativa_devolve_none():
    assert parse_relative_date("Brasil · 95 candidaturas", AGORA) is None
    assert parse_relative_date("", AGORA) is None


# ---------- Indeed: data de publicação no texto do detalhe ----------

@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Engenheiro Mecânico\nACME\nPublicada há 3 dias\nDescrição…", "2026-10-11T12:00:00Z"),
        ("Posted 5 days ago · Active 2 days ago", "2026-10-09T12:00:00Z"),
        ("Postado há 3 dias", "2026-10-11T12:00:00Z"),
        ("Vaga publicado há 2 semanas", "2026-09-30T12:00:00Z"),
        ("Publicada hoje", "2026-10-14T12:00:00Z"),
        ("Postado hoje", "2026-10-14T12:00:00Z"),
        ("Just posted", "2026-10-14T12:00:00Z"),
        ("Publicada há mais de 30 dias", None),
        ("Vaga sem data. Ativa há 2 dias", None),
        ("", None),
    ],
)
def test_indeed_converte_a_data_publicada_do_detalhe(settings, texto, esperado):
    assert IndeedSite(settings).parse_published(texto, AGORA) == esperado


def test_indeed_le_a_data_do_json_ld_e_depois_do_corpo_da_pagina_de_detalhe(settings):
    assert IndeedSite(settings).published_selectors == ['script[type="application/ld+json"]', "body"]


def test_indeed_le_a_data_exata_do_json_ld_do_detalhe(settings):
    amostra = (Path(__file__).parent / "samples" / "indeed_detail_jsonld.json").read_text(encoding="utf-8")
    assert IndeedSite(settings).parse_published(amostra, AGORA) == "2026-10-14T21:58:45.795Z"


@pytest.mark.parametrize("texto", ['{"@type": "JobPosting"}', '{"datePosted": "ontem"}', "{quebrado"])
def test_indeed_json_ld_sem_data_valida_nao_gera_data(settings, texto):
    assert IndeedSite(settings).parse_published(texto, AGORA) is None


# ---------- data por linha: independe de classe CSS ----------

@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Engenheiro\nACME\nBelo Horizonte, MG · Há 3 dias · 95 candidaturas\nSobre a vaga", "2026-10-11T12:00:00Z"),
        ("ACME\nAnunciada novamente há 8 horas\nSobre a vaga", "2026-10-14T04:00:00Z"),
        ("ACME\nPostado há 4 dias\nDescrição", "2026-10-10T12:00:00Z"),
        ("ACME\nReposted 5 days ago\nDescription", "2026-10-09T12:00:00Z"),
        ("ACME\nBelo Horizonte\nHá 1 semana", "2026-10-07T12:00:00Z"),
    ],
)
def test_data_por_linha_acha_a_linha_que_e_so_a_data(texto, esperado):
    assert find_published_line(texto, AGORA) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "Precisamos de quem trabalha há 2 anos com projetos de HVAC e quer crescer na empresa",
        "ACME\nAtiva há 2 dias\nDescrição",
        "ACME\nPublicada há mais de 30 dias",
        "",
    ],
)
def test_data_por_linha_ignora_frase_de_descricao_reativacao_e_texto_sem_data(texto):
    assert find_published_line(texto, AGORA) is None


# ---------- modalidade lida do card (o filtro local decide) ----------

@pytest.mark.parametrize(
    "legenda,esperado",
    [
        ("Belo Horizonte e Região (Presencial)", "presencial"),
        ("São Paulo, SP (Híbrido)", "hibrido"),
        ("Brasil (Remoto)", "remoto"),
        ("Campinas", ""),
    ],
)
def test_linkedin_modalidade_vem_da_legenda_do_card(settings, legenda, esperado):
    raw = {"id": "1", "title": "Engenheiro", "company": "ACME", "text": legenda}
    assert LinkedInSite(settings).to_job(raw).modalidade == esperado


@pytest.mark.parametrize(
    "location,texto,esperado",
    [
        ("Remoto", "", "remoto"),
        ("Campinas, SP", "Híbrido | R$ 8 mil por mês", "hibrido"),
        ("Campinas, SP", "Presencial", "presencial"),
        ("Campinas, SP", "Salário a combinar", ""),
    ],
)
def test_indeed_modalidade_vem_da_localidade_e_dos_itens_do_card(settings, location, texto, esperado):
    raw = {"id": "a", "title": "Engenheiro", "company": "ACME", "location": location, "text": texto}
    assert IndeedSite(settings).to_job(raw).modalidade == esperado
