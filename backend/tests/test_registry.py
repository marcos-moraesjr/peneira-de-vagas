import pytest

from backend.app.sources.browser import playwright_session
from backend.app.sources.errors import SourceUnavailable
from backend.app.sources.registry import build_sources


def test_fontes_ativas_na_ordem_linkedin_indeed_gupy(settings):
    assert [source.name for source in build_sources(settings)] == ["linkedin", "indeed", "gupy"]


def test_chrome_dedicado_fechado_falha_com_cdp_indisponivel(settings):
    fechado = settings.navegador.__class__("http://127.0.0.1:9", 3)
    sem_chrome = settings.__class__(**{**settings.__dict__, "navegador": fechado})
    with pytest.raises(SourceUnavailable) as erro:
        with playwright_session(sem_chrome):
            pass
    assert erro.value.motivo == "cdp_indisponivel"
    assert "9" in erro.value.detalhe
