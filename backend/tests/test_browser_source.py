"""Fluxo de BrowserSource com um navegador simulado (sem Chrome e sem rede)."""
from contextlib import contextmanager

import pytest

from backend.app.sources.browser import BrowserSource
from backend.app.sources.errors import SourceBlocked, SourceLayoutChanged, SourceUnavailable
from backend.app.sources.types import Job


class FakeSite:
    name = "fake"
    page_size = 2
    extract_js = "JS"
    card_selector = "li"
    detail_selectors = ["#desc"]

    def __init__(self, lazy_cards=False):
        self.lazy_cards = lazy_cards

    def search_url(self, termo, start, localidade=""):
        return f"https://site/?q={termo}&start={start}" + (f"&l={localidade}" if localidade else "")

    def classify(self, url, title, text):
        return "login" if "login" in url else ("cloudflare" if "Just a moment" in title else None)

    def is_empty_page(self, text):
        return "sem resultados" in text

    def to_job(self, raw):
        if not raw.get("id") or not raw.get("title"):
            return None
        return Job(raw["id"], raw["title"], "ACME", f"https://site/job/{raw['id']}", raw["text"], self.name)


class FakeNavigator:
    """Responde por URL: pages[url] = {'raw': [...], 'title': '', 'text': '', 'url': redirect}."""

    def __init__(self, pages, details=None):
        self.pages = pages
        self.details = details or {}
        self.opened = []
        self.plain_reads = 0
        self.progressive_reads = 0
        self._current = None

    def open(self, url):
        self.opened.append(url)
        self._current = self.pages.get(url) or self.details.get(url) or {"raw": []}

    def snapshot(self):
        return (
            self._current.get("url", self.opened[-1]),
            self._current.get("title", ""),
            self._current.get("text", ""),
        )

    def extract(self, js):
        self.plain_reads += 1
        return self._current.get("raw", [])

    def extract_progressive(self, js, card_selector, pause):
        self.progressive_reads += 1
        pause()
        return self._current.get("raw", [])

    def first_text(self, selectors):
        return self._current.get("detail", "")


def card(n):
    return {"id": str(n), "title": f"Vaga {n}", "text": f"texto {n}"}


def make_source(settings, navigator, lazy_cards=False):
    @contextmanager
    def session():
        yield navigator

    pauses, scroll_pauses = [], []
    source = BrowserSource(
        FakeSite(lazy_cards), settings, session, pause=lambda: pauses.append(1), scroll_pause=lambda: scroll_pauses.append(1)
    )
    return source, pauses, scroll_pauses


def test_le_paginas_ate_acabar_e_junta_as_vagas(settings):
    nav = FakeNavigator(
        {
            "https://site/?q=x&start=0": {"raw": [card(1), card(2)]},
            "https://site/?q=x&start=2": {"raw": [card(3)]},
            "https://site/?q=x&start=4": {"raw": []},
        }
    )
    source, *_ = make_source(settings, nav)
    assert [j.id for j in source.search(["x"])] == ["1", "2", "3"]


def test_cards_sem_titulo_ainda_nao_renderizados_sao_descartados(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"raw": [card(1), {"id": "2", "title": "", "text": ""}]}})
    source, *_ = make_source(settings, nav)
    assert [j.id for j in source.search(["x"])] == ["1"]


def test_para_quando_a_pagina_so_traz_vagas_repetidas(settings):
    nav = FakeNavigator(
        {
            "https://site/?q=x&start=0": {"raw": [card(1), card(2)]},
            "https://site/?q=x&start=2": {"raw": [card(1), card(2)]},
        }
    )
    source, *_ = make_source(settings, nav)
    assert len(source.search(["x"])) == 2
    assert len(nav.opened) == 2


def test_respeita_o_teto_de_vagas_lidas(settings):
    teto = settings.limites.__class__(settings.limites.max_paginas_detalhe, 3)
    limitada = settings.__class__(**{**settings.__dict__, "limites": teto})
    nav = FakeNavigator({f"https://site/?q=x&start={s}": {"raw": [card(s), card(s + 1)]} for s in (0, 2, 4)})
    source, *_ = make_source(limitada, nav)
    assert len(source.search(["x"])) == 3


def test_site_com_cards_incrementais_le_rolando_e_pausa_a_cada_passo(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"raw": [card(1)]}})
    source, pauses, scroll_pauses = make_source(settings, nav, lazy_cards=True)
    source.search(["x"])
    assert nav.progressive_reads == len(nav.opened) and nav.plain_reads == 0
    assert len(scroll_pauses) == nav.progressive_reads
    assert len(pauses) == len(nav.opened)  # uma pausa humana depois de cada página aberta


def test_site_sem_cards_incrementais_le_de_uma_vez(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"raw": [card(1)]}})
    source, _, scroll_pauses = make_source(settings, nav, lazy_cards=False)
    source.search(["x"])
    assert nav.plain_reads == len(nav.opened) and nav.progressive_reads == 0
    assert scroll_pauses == []


def test_cada_palavra_chave_gera_uma_busca(settings):
    nav = FakeNavigator({})
    source, *_ = make_source(settings, nav)
    nav.pages = {
        "https://site/?q=a&start=0": {"raw": [card(1)]},
        "https://site/?q=b&start=0": {"raw": [card(2)]},
    }
    assert [j.id for j in source.search(["a", "b"])] == ["1", "2"]


def with_localidades(settings, localidades):
    busca = settings.busca.__class__(**{**settings.busca.__dict__, "localidades": localidades})
    return settings.__class__(**{**settings.__dict__, "busca": busca})


def test_cada_palavra_chave_e_localidade_gera_uma_busca(settings):
    nav = FakeNavigator(
        {
            "https://site/?q=a&start=0&l=SP": {"raw": [card(1)]},
            "https://site/?q=a&start=0&l=Minas Gerais": {"raw": [card(2), card(1)]},
            "https://site/?q=b&start=0&l=SP": {"raw": [card(3)]},
            "https://site/?q=b&start=0&l=Minas Gerais": {"raw": [card(4)]},
        }
    )
    source, *_ = make_source(with_localidades(settings, ["SP", "Minas Gerais"]), nav)
    assert [j.id for j in source.search(["a", "b"])] == ["1", "2", "3", "4"]
    assert [url for url in nav.opened if "start=0" in url] == [
        "https://site/?q=a&start=0&l=SP",
        "https://site/?q=a&start=0&l=Minas Gerais",
        "https://site/?q=b&start=0&l=SP",
        "https://site/?q=b&start=0&l=Minas Gerais",
    ]


def test_sem_localidades_faz_uma_busca_sem_local(settings):
    nav = FakeNavigator({"https://site/?q=a&start=0": {"raw": [card(1)]}})
    source, *_ = make_source(with_localidades(settings, []), nav)
    assert [j.id for j in source.search(["a"])] == ["1"]
    assert nav.opened[0] == "https://site/?q=a&start=0"


def test_localidades_respeitam_o_teto_de_vagas_lidas(settings):
    teto = settings.limites.__class__(settings.limites.max_paginas_detalhe, 2)
    limitada = with_localidades(settings.__class__(**{**settings.__dict__, "limites": teto}), ["SP", "MG"])
    nav = FakeNavigator(
        {"https://site/?q=a&start=0&l=SP": {"raw": [card(1), card(2)]}, "https://site/?q=a&start=0&l=MG": {"raw": [card(3)]}}
    )
    source, *_ = make_source(limitada, nav)
    assert [j.id for j in source.search(["a"])] == ["1", "2"]
    assert not any("l=MG" in url for url in nav.opened)


@pytest.mark.parametrize("pagina,motivo", [({"url": "https://site/login"}, "login"), ({"title": "Just a moment..."}, "cloudflare")])
def test_bloqueio_interrompe_a_fonte_com_o_motivo(settings, pagina, motivo):
    nav = FakeNavigator({"https://site/?q=x&start=0": pagina})
    source, *_ = make_source(settings, nav)
    with pytest.raises(SourceBlocked) as erro:
        source.search(["x"])
    assert erro.value.motivo == motivo


def test_pagina_sem_cards_e_sem_marcador_de_vazio_e_mudanca_de_layout(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"raw": [], "text": "conteúdo qualquer"}})
    source, *_ = make_source(settings, nav)
    with pytest.raises(SourceLayoutChanged, match="seletor"):
        source.search(["x"])


def test_pagina_com_marcador_de_vazio_devolve_lista_vazia(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"raw": [], "text": "sem resultados"}})
    source, *_ = make_source(settings, nav)
    assert source.search(["x"]) == []


def test_enrich_substitui_o_trecho_pela_descricao_completa(settings):
    job = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    nav = FakeNavigator({}, details={"https://site/job/1": {"detail": "descrição completa"}})
    source, pauses, _ = make_source(settings, nav)
    assert source.enrich([job])[0].trecho == "descrição completa"
    assert pauses


def test_enrich_mantem_a_vaga_quando_nao_acha_a_descricao(settings):
    job = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    source, *_ = make_source(settings, FakeNavigator({}, details={"https://site/job/1": {"detail": ""}}))
    assert source.enrich([job])[0].trecho == "curto"


def test_enrich_trunca_a_descricao_no_limite_da_config(settings):
    job = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    longa = "a" * (settings.filtro.trecho_max_chars + 50)
    nav = FakeNavigator({}, details={"https://site/job/1": {"detail": longa}})
    source, *_ = make_source(settings, nav)
    assert len(source.enrich([job])[0].trecho) == settings.filtro.trecho_max_chars


def test_enrich_sem_vagas_nao_abre_o_navegador(settings):
    abriu = []

    @contextmanager
    def session():
        abriu.append(1)
        yield FakeNavigator({})

    source = BrowserSource(FakeSite(), settings, session, pause=lambda: None, scroll_pause=lambda: None)
    assert source.enrich([]) == []
    assert abriu == []


def test_enrich_com_bloqueio_na_pagina_de_detalhe_interrompe_a_fonte(settings):
    job = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    nav = FakeNavigator({}, details={"https://site/job/1": {"url": "https://site/login"}})
    source, *_ = make_source(settings, nav)
    with pytest.raises(SourceBlocked):
        source.enrich([job])


def test_falha_ao_abrir_o_navegador_propaga_cdp_indisponivel(settings):
    @contextmanager
    def session():
        raise SourceUnavailable("Chrome dedicado não encontrado", motivo="cdp_indisponivel")
        yield

    source = BrowserSource(FakeSite(), settings, session, pause=lambda: None, scroll_pause=lambda: None)
    with pytest.raises(SourceUnavailable) as erro:
        source.search(["x"])
    assert erro.value.motivo == "cdp_indisponivel"
