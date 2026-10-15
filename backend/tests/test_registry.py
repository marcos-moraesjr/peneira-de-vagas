import pytest

from backend.app.sources.browser import playwright_session
from backend.app.sources.errors import SourceBlocked, SourceUnavailable
from backend.app.sources.registry import build_sources


def test_fontes_ativas_na_ordem_navegador_primeiro_e_api_por_ultimo(settings):
    assert [source.name for source in build_sources(settings)] == ["linkedin", "indeed", "gupy"]


def test_chrome_dedicado_fechado_falha_com_cdp_indisponivel(settings):
    fechado = settings.navegador.__class__(**{**settings.navegador.__dict__, "cdp_url": "http://127.0.0.1:9", "timeout_s": 3})
    sem_chrome = settings.__class__(**{**settings.__dict__, "navegador": fechado})
    with pytest.raises(SourceUnavailable) as erro:
        with playwright_session(sem_chrome):
            pass
    assert erro.value.motivo == "cdp_indisponivel"
    assert "9" in erro.value.detalhe


class _PaginaFalsa:
    def __init__(self):
        self.fechada = False

    def close(self):
        self.fechada = True


def _playwright_falso(monkeypatch, pagina):
    class Contexto:
        def new_page(self):
            return pagina

    class Navegador:
        contexts = [Contexto()]

    class Chromium:
        def connect_over_cdp(self, *args, **kwargs):
            return Navegador()

    class Playwright:
        chromium = Chromium()

        def stop(self):
            pass

    class Inicio:
        def start(self):
            return Playwright()

    monkeypatch.setattr("backend.app.sources.browser.sync_playwright", lambda: Inicio())


def test_bloqueio_mantem_a_aba_aberta_para_o_usuario_resolver(settings, monkeypatch):
    pagina = _PaginaFalsa()
    _playwright_falso(monkeypatch, pagina)
    with pytest.raises(SourceBlocked):
        with playwright_session(settings):
            raise SourceBlocked("bloqueio", motivo="cloudflare")
    assert pagina.fechada is False


@pytest.mark.parametrize("erro", [None, SourceUnavailable("fora", motivo="http_erro")])
def test_aba_fecha_ao_terminar_sem_bloqueio(settings, monkeypatch, erro):
    pagina = _PaginaFalsa()
    _playwright_falso(monkeypatch, pagina)
    try:
        with playwright_session(settings):
            if erro:
                raise erro
    except SourceUnavailable:
        pass
    assert pagina.fechada is True
