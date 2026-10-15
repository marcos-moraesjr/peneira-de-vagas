"""GoogleSource: busca pelas palavras-chave e localidades do painel e não abre a página de detalhe."""
from contextlib import contextmanager

from backend.app.sources.google import GoogleSite, GoogleSource
from backend.tests.test_browser_source import FakeNavigator


def resultado(n):
    return {"id": f"https://jobs.lever.co/acme/{n}", "title": f"Dev {n}", "text": f"texto {n}"}


def make_source(settings, navigator):
    @contextmanager
    def session():
        yield navigator

    return GoogleSource(GoogleSite(settings), settings, session, pause=lambda: None, scroll_pause=lambda: None)


def test_busca_uma_consulta_por_palavra_chave_do_painel(settings):
    site = GoogleSite(settings)
    nav = FakeNavigator(
        {
            site.search_url("engenheiro mecânico", 0): {"raw": [resultado(1)]},
            site.search_url("engenheiro mecânico", 10): {"raw": []},
            site.search_url("projetista", 0): {"raw": [resultado(2)]},
            site.search_url("projetista", 10): {"raw": []},
        }
    )
    jobs = make_source(settings, nav).search(["engenheiro mecânico", "projetista"])
    assert [job.id for job in jobs] == ["https://jobs.lever.co/acme/1", "https://jobs.lever.co/acme/2"]

def test_nao_abre_pagina_de_detalhe(settings):
    nav = FakeNavigator({})
    jobs = [GoogleSite(settings).to_job(resultado(1))]
    assert make_source(settings, nav).enrich(jobs) == jobs
    assert nav.opened == []


def test_aplica_o_filtro_local_como_as_demais_fontes(settings):
    assert getattr(make_source(settings, FakeNavigator({})), "local_filter", True) is True


def test_uma_consulta_por_localidade_da_tela(settings):
    busca = settings.busca.__class__(**{**settings.busca.__dict__, "localidades": ["SP", "MG"]})
    settings = settings.__class__(**{**settings.__dict__, "busca": busca})
    site = GoogleSite(settings)
    nav = FakeNavigator(
        {
            site.search_url("x", 0, "SP"): {"raw": [resultado(1)]},
            site.search_url("x", 10, "SP"): {"raw": []},
            site.search_url("x", 0, "MG"): {"raw": [resultado(2)]},
            site.search_url("x", 10, "MG"): {"raw": []},
        }
    )
    jobs = make_source(settings, nav).search(["x"])
    assert len(jobs) == 2
    assert [url for url in nav.opened if "start=0" in url] == [site.search_url("x", 0, "SP"), site.search_url("x", 0, "MG")]