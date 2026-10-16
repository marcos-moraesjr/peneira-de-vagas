"""Fluxo de BrowserSource com um navegador simulado (sem Chrome e sem rede)."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.app.sources.browser import BrowserSource, PlaywrightNavigator
from backend.app.sources.errors import SourceBlocked, SourceLayoutChanged, SourceRateLimited, SourceUnavailable
from backend.app.sources.types import Job
from backend.app.sources.verification import VerificationGate
from playwright.sync_api import Error as PlaywrightError


class FakeSite:
    name = "fake"
    page_size = 2
    extract_js = "JS"
    card_selector = "li"
    detail_selectors = ["#desc"]

    def __init__(self, lazy_cards=False):
        self.lazy_cards = lazy_cards

    def search_url(self, termo, start):
        return f"https://site/?q={termo}&start={start}"

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
        if selectors == ["#when"]:
            return self._current.get("published", "")
        return self._current.get("detail", "")

    def expand_detail(self, js):
        self.expanded = getattr(self, "expanded", [])
        self.expanded.append(js)
        return True

    def open_detail(self, js):
        self.opened_details = getattr(self, "opened_details", [])
        self.opened_details.append(js)
        self._current = next(iter(self.details.values()), {})
        return True


class ExpandableSite(FakeSite):
    open_detail_js = "OPEN __JOB_ID__"
    expand_detail_js = "EXPAND"


class PanelOnlySite(FakeSite):
    open_detail_js = "OPEN __JOB_ID__"
    detail_navigation_fallback = False


class ProgressiveCard:
    def __init__(self, page, card_id):
        self.page = page
        self.card_id = card_id

    def get_attribute(self, name):
        return self.card_id if name == "data-occludable-job-id" else None

    def scroll_into_view_if_needed(self, timeout):
        self.page.scrolled.append(self.card_id)
        self.page.loaded.add(self.card_id)


class ProgressivePage:
    def __init__(self, card_ids, loaded):
        self.card_ids = card_ids
        self.loaded = set(loaded)
        self.scrolled = []

    def locator(self, selector):
        return self

    def count(self):
        return len(self.card_ids)

    def nth(self, index):
        return ProgressiveCard(self, self.card_ids[index])

    def evaluate(self, js):
        return [
            {"id": card_id, "title": f"Vaga {card_id}" if card_id in self.loaded else "", "company": "ACME", "text": ""}
            for card_id in self.card_ids
        ]


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


def com_paginas(settings, paginas):
    return replace(settings, limites=replace(settings.limites, max_paginas_por_termo=paginas))


def paginas_do_termo(termo, base, quantas=4):
    return {f"https://site/?q={termo}&start={2 * n}": {"raw": [card(base + 2 * n), card(base + 2 * n + 1)]} for n in range(quantas)}


def test_abre_so_o_numero_de_paginas_configurado(settings):
    nav = FakeNavigator(paginas_do_termo("x", 0))
    source, *_ = make_source(com_paginas(settings, 2), nav)
    assert [j.id for j in source.search(["x"])] == ["0", "1", "2", "3"]
    assert nav.opened == ["https://site/?q=x&start=0", "https://site/?q=x&start=2"]


def test_cada_termo_abre_as_proprias_paginas(settings):
    nav = FakeNavigator(paginas_do_termo("a", 0) | paginas_do_termo("b", 100))
    source, *_ = make_source(com_paginas(settings, 2), nav)
    assert [j.id for j in source.search(["a", "b"])] == ["0", "1", "2", "3", "100", "101", "102", "103"]
    assert len(nav.opened) == 4


def test_vaga_achada_por_dois_termos_aparece_uma_vez(settings):
    nav = FakeNavigator(
        {
            "https://site/?q=a&start=0": {"raw": [card(1), card(2)]},
            "https://site/?q=b&start=0": {"raw": [card(2), card(3)]},
        }
    )
    source, *_ = make_source(com_paginas(settings, 1), nav)
    assert [j.id for j in source.search(["a", "b"])] == ["1", "2", "3"]


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


def test_navegador_progressivo_nao_rola_cards_ja_renderizados():
    page = ProgressivePage(["1", "2", "3"], loaded=["1"])
    pauses = []
    navigator = PlaywrightNavigator(page, timeout_ms=1000)

    jobs = navigator.extract_progressive("JS", "li", lambda: pauses.append(1))

    assert [job["id"] for job in jobs] == ["1", "2", "3"]
    assert page.scrolled == ["2", "3"]
    assert len(pauses) == 2


def test_cada_palavra_chave_gera_uma_busca(settings):
    nav = FakeNavigator({})
    source, *_ = make_source(settings, nav)
    nav.pages = {
        "https://site/?q=a&start=0": {"raw": [card(1)]},
        "https://site/?q=b&start=0": {"raw": [card(2)]},
    }
    assert [j.id for j in source.search(["a", "b"])] == ["1", "2"]


def test_cada_vaga_guarda_a_palavra_chave_que_a_trouxe_e_repetida_fica_com_a_primeira(settings):
    nav = FakeNavigator({})
    source, *_ = make_source(settings, nav)
    nav.pages = {
        "https://site/?q=a&start=0": {"raw": [card(1)]},
        "https://site/?q=b&start=0": {"raw": [card(1), card(2)]},
    }
    assert [(j.id, j.palavra_chave) for j in source.search(["a", "b"])] == [("1", "a"), ("2", "b")]


def test_busca_abre_o_detalhe_de_cada_pagina_antes_de_continuar_a_paginar(settings):
    nav = FakeNavigator(
        {
            "https://site/?q=x&start=0": {"raw": [card(1)]},
            "https://site/?q=x&start=2": {"raw": []},
        },
        details={"https://site/job/1": {"detail": "descrição completa"}},
    )
    source, *_ = make_source(settings, nav)
    recebidas = []

    source.search_and_enrich(["x"], lambda jobs: jobs, on_job=recebidas.append)

    assert recebidas[0].trecho == "descrição completa"
    assert nav.opened == [
        "https://site/?q=x&start=0",
        "https://site/job/1",
        "https://site/?q=x&start=2",
    ]


def with_localidades(settings, localidades):
    busca = settings.busca.__class__(**{**settings.busca.__dict__, "localidades": localidades})
    return settings.__class__(**{**settings.__dict__, "busca": busca})


def test_localidades_da_config_nao_multiplicam_as_buscas(settings):
    nav = FakeNavigator({"https://site/?q=a&start=0": {"raw": [card(1)]}, "https://site/?q=b&start=0": {"raw": [card(2)]}})
    source, *_ = make_source(with_localidades(settings, ["SP", "Minas Gerais"]), nav)
    assert [j.id for j in source.search(["a", "b"])] == ["1", "2"]
    assert [url for url in nav.opened if "start=0" in url] == ["https://site/?q=a&start=0", "https://site/?q=b&start=0"]


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


def test_enrich_expande_o_detalhe_antes_de_ler_o_texto(settings):
    job = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    nav = FakeNavigator({}, details={"https://site/job/1": {"detail": "descriÃ§Ã£o completa"}})

    @contextmanager
    def session():
        yield nav

    source = BrowserSource(ExpandableSite(), settings, session, lambda: None, lambda: None)
    source.enrich([job])

    assert nav.opened_details == ['OPEN "1"']
    assert nav.expanded == ["EXPAND"]


def test_fonte_de_painel_sem_fallback_nao_abre_a_url_individual(settings):
    job = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    nav = FakeNavigator({}, details={job.link: {"detail": "não deve abrir"}})
    nav.open_detail = lambda js: False

    @contextmanager
    def session():
        yield nav

    source = BrowserSource(PanelOnlySite(), settings, session, pause=lambda: None, scroll_pause=lambda: None, sleep=lambda s: None)
    with pytest.raises(SourceLayoutChanged, match="painel"):
        source.enrich([job])
    assert nav.opened == []


def test_painel_e_tentado_ate_o_limite_configurado_antes_da_falha(settings):
    job = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    nav = FakeNavigator({})
    attempts = []
    nav.open_detail = lambda js: attempts.append(js) and False

    @contextmanager
    def session():
        yield nav

    pauses = []
    source = BrowserSource(
        PanelOnlySite(), settings, session, pause=lambda: None, scroll_pause=lambda: pauses.append(1), sleep=lambda s: None
    )
    with pytest.raises(SourceLayoutChanged, match="3 tentativa"):
        source.enrich([job])
    assert len(attempts) == settings.navegador.max_tentativas_painel == 3


def test_tentativas_do_painel_esperam_o_intervalo_configurado_entre_si(settings):
    job = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    nav = FakeNavigator({})
    nav.open_detail = lambda js: False

    @contextmanager
    def session():
        yield nav

    esperas = []
    source = BrowserSource(
        PanelOnlySite(), settings, session, pause=lambda: None, scroll_pause=lambda: None, sleep=esperas.append
    )
    with pytest.raises(SourceLayoutChanged):
        source.enrich([job])
    assert settings.navegador.intervalo_tentativa_painel_s == 15
    assert esperas == [15, 15]  # entre 3 tentativas há 2 intervalos; nenhum depois da última


def test_cada_painel_aberto_espera_a_pausa_de_detalhe_e_nao_a_de_rolagem(settings):
    nav = FakeNavigator({})
    nav._current = {"detail": "descrição"}

    @contextmanager
    def session():
        yield nav

    detail_pauses, scroll_pauses = [], []
    source = BrowserSource(
        PanelOnlySite(), settings, session, pause=lambda: None,
        scroll_pause=lambda: scroll_pauses.append(1), detail_pause=lambda: detail_pauses.append(1),
    )
    source.enrich([Job(i, f"Vaga {i}", "ACME", f"https://site/job/{i}", "curto", "fake") for i in ("1", "2", "3")])
    assert len(detail_pauses) == 3
    assert scroll_pauses == []


def test_enrich_entrega_cada_vaga_ao_callback_assim_que_o_detalhe_e_lido(settings):
    um = Job("1", "Vaga 1", "ACME", "https://site/job/1", "curto", "fake")
    dois = Job("2", "Vaga 2", "ACME", "https://site/job/2", "curto", "fake")
    nav = FakeNavigator({}, details={
        "https://site/job/1": {"detail": "descrição 1"},
        "https://site/job/2": {"url": "https://site/login"},
    })
    source, *_ = make_source(settings, nav)
    entregues = []
    with pytest.raises(SourceBlocked):
        source.enrich([um, dois], on_job=entregues.append)
    assert [(j.id, j.trecho) for j in entregues] == [("1", "descrição 1")]


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


class FakeGate:
    """Simula o usuário: ao esperar, 'conclui a verificação' trocando a página bloqueada pela real."""

    def __init__(self, nav, url, liberada, confirma=True):
        self.nav, self.url, self.liberada, self.confirma = nav, url, liberada, confirma
        self.calls = []

    def wait(self, fonte, timeout_s):
        self.calls.append((fonte, timeout_s))
        if self.confirma:
            self.nav.pages[self.url] = self.liberada
        return self.confirma

    def check(self):
        pass


def make_source_with_gate(settings, nav, gate):
    @contextmanager
    def session():
        yield nav

    return BrowserSource(FakeSite(), settings, session, pause=lambda: None, scroll_pause=lambda: None, gate=gate)


def test_bloqueio_com_confirmacao_retoma_a_busca_de_onde_parou(settings):
    bloqueada = {"url": "https://site/login", "raw": []}
    nav = FakeNavigator(
        {
            "https://site/?q=x&start=0": {"raw": [card(1), card(2)]},
            "https://site/?q=x&start=2": bloqueada,
            "https://site/?q=x&start=4": {"raw": []},
        }
    )
    gate = FakeGate(nav, "https://site/?q=x&start=2", {"raw": [card(3)]})
    source = make_source_with_gate(settings, nav, gate)
    assert [j.id for j in source.search(["x"])] == ["1", "2", "3"]
    assert nav.opened.count("https://site/?q=x&start=0") == 1  # não recomeçou da primeira página
    assert nav.opened.count("https://site/?q=x&start=2") == 2  # reabriu só a página que bloqueou
    assert gate.calls == [("fake", settings.navegador.espera_verificacao_s)]


def test_bloqueio_sem_confirmacao_dentro_do_prazo_interrompe_a_fonte(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"url": "https://site/login", "raw": []}})
    gate = FakeGate(nav, "https://site/?q=x&start=0", {"raw": []}, confirma=False)
    source = make_source_with_gate(settings, nav, gate)
    with pytest.raises(SourceBlocked):
        source.search(["x"])


def test_bloqueio_que_continua_apos_a_confirmacao_volta_a_esperar(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"url": "https://site/login", "raw": []}})
    gate = FakeGate(nav, "https://site/?q=x&start=0", {"url": "https://site/login", "raw": []}, confirma=False)
    respostas = iter([True, False])
    gate.wait = lambda fonte, timeout_s: next(respostas)
    source = make_source_with_gate(settings, nav, gate)
    with pytest.raises(SourceBlocked):
        source.search(["x"])
    assert nav.opened.count("https://site/?q=x&start=0") == 2


def test_reabertura_interrompida_logo_apos_a_verificacao_tenta_de_novo(settings):
    """Ao concluir o CAPTCHA o Chrome ainda está redirecionando; o `goto` da reabertura pode ser abortado."""
    nav = FakeNavigator({"https://site/?q=x&start=0": {"url": "https://site/login", "raw": []}})
    gate = FakeGate(nav, "https://site/?q=x&start=0", {"raw": [card(1)]})
    abertas = nav.open

    def open_interrompido_uma_vez(url):
        abertas(url)
        if nav.opened.count(url) == 2:
            raise SourceUnavailable(f"Falha ao abrir {url}: net::ERR_ABORTED", motivo="http_erro")

    nav.open = open_interrompido_uma_vez
    source = make_source_with_gate(settings, nav, gate)
    assert [j.id for j in source.search(["x"])] == ["1"]


def test_reabertura_que_continua_falhando_apos_a_verificacao_interrompe_a_fonte(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"url": "https://site/login", "raw": []}})
    gate = FakeGate(nav, "https://site/?q=x&start=0", {"raw": [card(1)]})
    abertas = nav.open

    def open_sempre_falha_apos_bloqueio(url):
        abertas(url)
        if nav.opened.count(url) >= 2:
            raise SourceUnavailable(f"Falha ao abrir {url}", motivo="http_erro")

    nav.open = open_sempre_falha_apos_bloqueio
    source = make_source_with_gate(settings, nav, gate)
    with pytest.raises(SourceUnavailable):
        source.search(["x"])


def test_navegador_repete_goto_abortado_ate_ter_sucesso():
    class Page:
        def __init__(self):
            self.calls = 0

        def goto(self, url, wait_until, timeout):
            self.calls += 1
            if self.calls < 3:
                raise PlaywrightError("net::ERR_ABORTED")

    page = Page()
    PlaywrightNavigator(page, timeout_ms=1000, max_tentativas_abertura=3).open("https://indeed.test/job")
    assert page.calls == 3


def test_navegador_informa_status_http_e_nao_repete_resposta_de_erro():
    """O código do Chromium esconde o status HTTP que explica a falha da página."""
    url = "https://linkedin.test/jobs?start=25"

    class Response:
        def __init__(self, response_url):
            self.url = response_url
            self.status = 429

    class Page:
        def __init__(self):
            self.calls = 0
            self.listener = None

        def on(self, event, listener):
            assert event == "response"
            self.listener = listener

        def remove_listener(self, event, listener):
            assert event == "response"
            assert listener is self.listener
            self.listener = None

        def goto(self, url, wait_until, timeout):
            self.calls += 1
            self.listener(Response(url))
            raise PlaywrightError("net::ERR_HTTP_RESPONSE_CODE_FAILURE")

    page = Page()
    with pytest.raises(SourceUnavailable, match=r"HTTP 429.*ERR_HTTP_RESPONSE_CODE_FAILURE"):
        PlaywrightNavigator(page, timeout_ms=1000, max_tentativas_abertura=3).open(url)
    assert page.calls == 1
    assert page.listener is None


def test_navegador_aborta_depois_do_limite_de_gotos_abortados():
    class Page:
        def goto(self, url, wait_until, timeout):
            raise PlaywrightError("net::ERR_ABORTED")

    with pytest.raises(SourceUnavailable, match="ERR_ABORTED"):
        PlaywrightNavigator(Page(), timeout_ms=1000, max_tentativas_abertura=2).open("https://indeed.test/job")


def test_falha_de_abertura_informa_fonte_etapa_e_url(settings):
    nav = FakeNavigator({"https://site/?q=x&start=0": {"raw": []}})

    def open_falha(url):
        raise SourceUnavailable(
            f"Falha ao abrir {url} após 3 tentativas: net::ERR_ABORTED",
            motivo="http_erro",
        )

    nav.open = open_falha
    source, *_ = make_source(settings, nav)

    with pytest.raises(SourceUnavailable) as erro:
        source.search(["x"])

    assert erro.value.detalhe == (
        "Fonte fake: falha na etapa busca: Falha ao abrir "
        "https://site/?q=x&start=0 após 3 tentativas: net::ERR_ABORTED"
    )


def test_bloqueio_no_detalhe_com_confirmacao_retoma_a_vaga(settings):
    detalhe = "https://site/job/1"
    nav = FakeNavigator({}, details={detalhe: {"url": "https://site/login", "detail": ""}})
    gate = FakeGate(nav, detalhe, {"detail": "descrição completa"})
    nav.details = nav.pages  # a página liberada vale também para o detalhe
    nav.pages[detalhe] = {"url": "https://site/login"}
    source = make_source_with_gate(settings, nav, gate)
    job = Job("1", "Vaga 1", "ACME", detalhe, "resumo", "fake")
    assert source.enrich([job])[0].trecho == "descrição completa"


class FakeDatedSite(FakeSite):
    published_selectors = ["#when"]

    def parse_published(self, text, now):
        return f"{now.date().isoformat()}|{text}" if text else None


def test_enrich_le_a_data_de_publicacao_do_detalhe_quando_o_site_a_informa(settings):
    link = "https://site/job/1"
    nav = FakeNavigator({}, details={link: {"detail": "descrição", "published": "há 3 dias"}})

    @contextmanager
    def session():
        yield nav

    agora = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    source = BrowserSource(
        FakeDatedSite(), settings, session, pause=lambda: None, scroll_pause=lambda: None, clock=lambda: agora
    )
    job = Job("1", "Vaga 1", "ACME", link, "curto", "fake")
    assert source.enrich([job])[0].publicada_em == "2026-10-14|há 3 dias"


def test_enrich_sem_data_no_detalhe_mantem_publicada_em_vazia(settings):
    link = "https://site/job/1"
    nav = FakeNavigator({}, details={link: {"detail": "descrição"}})

    @contextmanager
    def session():
        yield nav

    source = BrowserSource(FakeDatedSite(), settings, session, pause=lambda: None, scroll_pause=lambda: None)
    assert source.enrich([Job("1", "Vaga 1", "ACME", link, "curto", "fake")])[0].publicada_em is None


def _fonte_datada(settings, nav, site=None):
    @contextmanager
    def session():
        yield nav

    agora = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    return BrowserSource(
        site or FakeDatedSite(), settings, session, pause=lambda: None, scroll_pause=lambda: None, clock=lambda: agora
    )


def test_enrich_sem_data_no_seletor_procura_a_linha_da_data_no_texto_da_pagina(settings):
    link = "https://site/job/1"
    corpo = "Engenheiro\nACME\nBelo Horizonte · Há 3 dias · 95 candidaturas\nSobre a vaga"
    nav = FakeNavigator({}, details={link: {"detail": corpo, "published": ""}})
    job = Job("1", "Vaga 1", "ACME", link, "curto", "fake")
    assert _fonte_datada(settings, nav).enrich([job])[0].publicada_em == "2026-10-11T12:00:00Z"


def test_enrich_avisa_no_log_quantas_vagas_ficaram_sem_data(settings, caplog):
    um, dois = "https://site/job/1", "https://site/job/2"
    nav = FakeNavigator({}, details={um: {"detail": "d", "published": "há 3 dias"}, dois: {"detail": "d"}})
    jobs = [Job("1", "V1", "ACME", um, "c", "fake"), Job("2", "V2", "ACME", dois, "c", "fake")]
    with caplog.at_level("WARNING"):
        _fonte_datada(settings, nav).enrich(jobs)
    assert "1 de 2 vagas abertas no detalhe ficaram sem data" in caplog.text


def test_enrich_nao_avisa_quando_todas_as_vagas_tem_data(settings, caplog):
    um = "https://site/job/1"
    nav = FakeNavigator({}, details={um: {"detail": "d", "published": "há 3 dias"}})
    with caplog.at_level("WARNING"):
        _fonte_datada(settings, nav).enrich([Job("1", "V1", "ACME", um, "c", "fake")])
    assert "sem data" not in caplog.text


class FakeNavigatorPorSeletor(FakeNavigator):
    def first_text(self, selectors):
        if selectors == ["body"]:
            return self._current.get("detail", "")
        return self._current.get("por_seletor", {}).get(selectors[0], "")


class FakeDoisSeletores(FakeDatedSite):
    published_selectors = ["#a", "#b"]


def test_enrich_tenta_cada_seletor_da_data_ate_um_dar_data(settings):
    link = "https://site/job/1"
    nav = FakeNavigatorPorSeletor({}, details={link: {"detail": "descrição", "por_seletor": {"#a": "", "#b": "há 2 dias"}}})
    job = Job("1", "Vaga 1", "ACME", link, "curto", "fake")
    assert _fonte_datada(settings, nav, FakeDoisSeletores()).enrich([job])[0].publicada_em == "2026-10-14|há 2 dias"


def _com_falhas_seguidas(settings, limite):
    return replace(settings, navegador=replace(settings.navegador, max_falhas_termo_seguidas=limite))


def _nav_que_falha_em(urls, erro, pages):
    nav = FakeNavigator(pages)
    abertas = nav.open

    def open_com_falha(url):
        abertas(url)
        if url in urls:
            raise erro(f"Falha ao abrir {url}: net::ERR_ABORTED")

    nav.open = open_com_falha
    return nav


def test_termo_que_falha_por_erro_transitorio_e_pulado_e_a_busca_segue(settings):
    nav = _nav_que_falha_em(
        {"https://site/?q=a&start=0"},
        SourceUnavailable,
        {"https://site/?q=b&start=0": {"raw": [card(1)]}, "https://site/?q=b&start=2": {"raw": []}},
    )
    source, *_ = make_source(_com_falhas_seguidas(settings, 2), nav)
    assert [j.id for j in source.search(["a", "b"])] == ["1"]
    assert "https://site/?q=b&start=0" in nav.opened


def test_falhas_seguidas_acima_do_limite_encerram_a_fonte(settings):
    nav = _nav_que_falha_em(
        {"https://site/?q=a&start=0", "https://site/?q=b&start=0"}, SourceUnavailable, {}
    )
    source, *_ = make_source(_com_falhas_seguidas(settings, 2), nav)
    with pytest.raises(SourceUnavailable):
        source.search(["a", "b", "c"])
    assert "https://site/?q=c&start=0" not in nav.opened


def test_termo_com_sucesso_zera_a_contagem_de_falhas_seguidas(settings):
    nav = _nav_que_falha_em(
        {"https://site/?q=a&start=0", "https://site/?q=c&start=0"},
        SourceUnavailable,
        {"https://site/?q=b&start=0": {"raw": [card(1)]}, "https://site/?q=b&start=2": {"raw": []}},
    )
    source, *_ = make_source(_com_falhas_seguidas(settings, 2), nav)
    assert [j.id for j in source.search(["a", "b", "c"])] == ["1"]


def test_limitacao_de_taxa_encerra_a_fonte_sem_pular_para_o_proximo_termo(settings):
    nav = _nav_que_falha_em({"https://site/?q=a&start=0"}, SourceRateLimited, {})
    source, *_ = make_source(_com_falhas_seguidas(settings, 5), nav)
    with pytest.raises(SourceRateLimited):
        source.search(["a", "b"])
    assert nav.opened == ["https://site/?q=a&start=0"]


def test_navegador_classifica_http_429_como_limitacao_de_taxa():
    class Response:
        def __init__(self, response_url):
            self.url = response_url
            self.status = 429

    class Page:
        listener = None

        def on(self, event, listener):
            self.listener = listener

        def remove_listener(self, event, listener):
            self.listener = None

        def goto(self, url, wait_until, timeout):
            self.listener(Response(url))
            raise PlaywrightError("net::ERR_HTTP_RESPONSE_CODE_FAILURE")

    with pytest.raises(SourceRateLimited):
        PlaywrightNavigator(Page(), timeout_ms=1000, max_tentativas_abertura=3).open("https://linkedin.test/jobs")


def _painel_que_falha_em(settings, falham, limite=3):
    nav = FakeNavigator({})
    nav._current = {"detail": "descrição"}
    nav.open_detail = lambda js: not any(f'"{id_}"' in js for id_ in falham)

    @contextmanager
    def session():
        yield nav

    config = replace(settings, navegador=replace(settings.navegador, max_falhas_detalhe_seguidas=limite))
    return BrowserSource(PanelOnlySite(), config, session, pause=lambda: None, scroll_pause=lambda: None, sleep=lambda s: None)


def _vagas(*ids):
    return [Job(i, f"Vaga {i}", "ACME", f"https://site/job/{i}", "curto", "fake") for i in ids]


def test_vaga_cujo_painel_nao_abre_e_pulada_e_as_demais_seguem(settings):
    source = _painel_que_falha_em(settings, {"2"})
    entregues = []
    source.enrich(_vagas("1", "2", "3"), on_job=entregues.append)
    assert [j.id for j in entregues] == ["1", "3"]


def test_paineis_seguidos_acima_do_limite_encerram_a_fonte(settings):
    source = _painel_que_falha_em(settings, {"1", "2", "3", "4"}, limite=2)
    entregues = []
    with pytest.raises(SourceLayoutChanged):
        source.enrich(_vagas("1", "2", "3", "4"), on_job=entregues.append)


def test_painel_que_abre_zera_a_contagem_de_falhas_seguidas(settings):
    source = _painel_que_falha_em(settings, {"1", "3"}, limite=2)
    entregues = []
    source.enrich(_vagas("1", "2", "3", "4"), on_job=entregues.append)
    assert [j.id for j in entregues] == ["2", "4"]
