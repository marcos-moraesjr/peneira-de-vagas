"""GoogleSource: usa as consultas da config (não as palavras-chave), não abre detalhe e confia na consulta."""
from contextlib import contextmanager

from backend.app.sources.google import GoogleSite, GoogleSource
from backend.tests.test_browser_source import FakeNavigator


def with_consultas(settings, consultas):
    google = settings.google.__class__(**{**settings.google.__dict__, "consultas": consultas})
    return settings.__class__(**{**settings.__dict__, "google": google})


def resultado(n):
    return {"id": f"https://jobs.lever.co/acme/{n}", "title": f"Dev {n}", "text": f"texto {n}"}


def make_source(settings, navigator):
    @contextmanager
    def session():
        yield navigator

    return GoogleSource(GoogleSite(settings), settings, session, pause=lambda: None, scroll_pause=lambda: None)


def test_busca_as_consultas_da_config_ignorando_as_palavras_chave(settings):
    settings = with_consultas(settings, ["site:lever.co c#", "site:ashbyhq.com .net"])
    site = GoogleSite(settings)
    nav = FakeNavigator(
        {
            site.search_url("site:lever.co c#", 0): {"raw": [resultado(1)]},
            site.search_url("site:lever.co c#", 10): {"raw": []},
            site.search_url("site:ashbyhq.com .net", 0): {"raw": [resultado(2)]},
            site.search_url("site:ashbyhq.com .net", 10): {"raw": []},
        }
    )
    jobs = make_source(settings, nav).search(["engenheiro mecânico"])
    assert [job.id for job in jobs] == ["https://jobs.lever.co/acme/1", "https://jobs.lever.co/acme/2"]
    assert not any("engenheiro" in url for url in nav.opened)


def test_nao_abre_pagina_de_detalhe(settings):
    nav = FakeNavigator({})
    jobs = [GoogleSite(settings).to_job(resultado(1))]
    assert make_source(settings, nav).enrich(jobs) == jobs
    assert nav.opened == []


def test_confia_na_consulta_e_nao_aplica_o_filtro_local(settings):
    assert make_source(settings, FakeNavigator({})).local_filter is False


def test_localidades_nao_multiplicam_as_consultas_do_google(settings):
    busca = settings.busca.__class__(**{**settings.busca.__dict__, "localidades": ["SP", "MG"]})
    settings = with_consultas(settings.__class__(**{**settings.__dict__, "busca": busca}), ["site:lever.co"])
    site = GoogleSite(settings)
    nav = FakeNavigator({site.search_url("site:lever.co", 0): {"raw": [resultado(1)]}})
    make_source(settings, nav).search(["x"])
    assert [url for url in nav.opened if "start=0" in url] == [site.search_url("site:lever.co", 0)]
