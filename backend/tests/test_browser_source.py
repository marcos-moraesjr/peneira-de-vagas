"""Fluxo de BrowserSource com um navegador simulado (sem Chrome e sem rede)."""
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from backend.app.sources.browser import BrowserSource
from backend.app.sources.errors import SourceBlocked, SourceLayoutChanged, SourceUnavailable
from backend.app.sources.types import Job
from backend.app.sources.verification import VerificationGate


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
    teto = settings.limites.__class__(max_vagas_lista=3)
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
