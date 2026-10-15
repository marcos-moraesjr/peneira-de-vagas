"""Base comum das fontes de navegador (LinkedIn e Indeed): Chrome dedicado via CDP, ritmo humano,
detecção de bloqueio e leitura da lista. Nada aqui tenta contornar bloqueio: ao detectá-lo, a fonte para.
"""
import logging
import random
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from ..config import Settings
from .errors import SourceBlocked, SourceLayoutChanged, SourceUnavailable
from .relative_date import find_published_line
from .types import Job
from .verification import VerificationGate

log = logging.getLogger(__name__)

SNAPSHOT_TEXT_CHARS = 3000


class Site(Protocol):
    """O que muda de um site para outro; o fluxo de leitura é o mesmo."""

    name: str
    page_size: int
    extract_js: str
    card_selector: str
    lazy_cards: bool  # True: os cards só renderizam ao rolar até eles (LinkedIn)
    detail_selectors: list[str]

    def search_url(self, termo: str, start: int) -> str: ...

    def classify(self, url: str, title: str, text: str) -> str | None: ...

    def is_empty_page(self, text: str) -> bool: ...

    def to_job(self, raw: dict) -> Job | None: ...


class Navigator(Protocol):
    def open(self, url: str) -> None: ...

    def snapshot(self) -> tuple[str, str, str]: ...

    def extract(self, js: str) -> list[dict]: ...

    def extract_progressive(self, js: str, card_selector: str, pause: Callable[[], None]) -> list[dict]: ...

    def first_text(self, selectors: list[str]) -> str: ...


class PlaywrightNavigator:
    def __init__(self, page, timeout_ms: int):
        self._page = page
        self._timeout_ms = timeout_ms

    def open(self, url: str) -> None:
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
        except PlaywrightTimeout as error:
            raise SourceUnavailable(f"Tempo esgotado ao abrir {url}", motivo="http_erro") from error
        except PlaywrightError as error:
            raise SourceUnavailable(f"Falha ao abrir {url}: {error}", motivo="http_erro") from error

    def snapshot(self) -> tuple[str, str, str]:
        try:
            text = self._page.inner_text("body", timeout=self._timeout_ms)
        except PlaywrightError:
            text = ""
        return self._page.url, self._page.title(), text[:SNAPSHOT_TEXT_CHARS]

    def extract(self, js: str) -> list[dict]:
        return self._page.evaluate(js)

    def extract_progressive(self, js: str, card_selector: str, pause: Callable[[], None]) -> list[dict]:
        """Rola até cada card e lê o que já renderizou, sem depender de o card continuar renderizado depois.

        Um card só substitui o já lido se tiver título (o card ainda vazio tem o ID mas nada mais).
        """
        merged: dict[str, dict] = {}
        cards = self._page.locator(card_selector)
        for index in range(cards.count()):
            cards.nth(index).scroll_into_view_if_needed(timeout=self._timeout_ms)
            pause()
            for raw in self._page.evaluate(js):
                if raw.get("id") and (raw["id"] not in merged or raw.get("title")):
                    merged[raw["id"]] = raw
        return list(merged.values())

    def first_text(self, selectors: list[str]) -> str:
        for selector in selectors:
            locator = self._page.locator(selector).first
            if locator.count():
                return locator.inner_text(timeout=self._timeout_ms)
        return ""


def make_pause(minimum_s: float, maximum_s: float) -> Callable[[], None]:
    """Pausa aleatória (ritmo humano) entre minimum_s e maximum_s, vindos da config."""
    return lambda: time.sleep(random.uniform(minimum_s, maximum_s))


def playwright_session(settings: Settings) -> AbstractContextManager[Navigator]:
    """Conecta ao Chrome dedicado já aberto pelo usuário e usa uma aba por vez; nunca fecha o Chrome.

    A aba é fechada ao terminar, exceto em bloqueio (`SourceBlocked`): fica aberta para o usuário concluir a
    verificação à mão; a próxima execução abre uma aba nova."""

    @contextmanager
    def session():
        timeout_ms = settings.navegador.timeout_s * 1000
        playwright = sync_playwright().start()
        try:
            try:
                browser = playwright.chromium.connect_over_cdp(settings.navegador.cdp_url, timeout=timeout_ms)
            except Exception as error:  # noqa: BLE001 - qualquer falha de conexão é "Chrome indisponível"
                raise SourceUnavailable(
                    f"Chrome dedicado não encontrado em {settings.navegador.cdp_url}", motivo="cdp_indisponivel"
                ) from error
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            keep_open = False
            try:
                yield PlaywrightNavigator(page, timeout_ms)
            except SourceBlocked:
                keep_open = True  # o usuário resolve a verificação à mão nesta aba
                raise
            finally:
                if not keep_open:
                    page.close()
        finally:
            playwright.stop()

    return session()


class BrowserSource:
    def __init__(
        self,
        site: Site,
        settings: Settings,
        session: Callable[[], AbstractContextManager],
        pause: Callable[[], None],
        scroll_pause: Callable[[], None],
        gate: VerificationGate | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._site = site
        self._settings = settings
        self._session = session
        self._pause = pause
        self._scroll_pause = scroll_pause
        self._gate = gate
        self._clock = clock
        self.name = site.name

    def search(self, termos: list[str]) -> list[Job]:
        found: dict[str, Job] = {}
        with self._session() as navigator:
            for termo in termos:
                self._search_term(navigator, termo, found)
        return list(found.values())

    def enrich(self, jobs: list[Job], on_job: Callable[[Job], None] | None = None) -> list[Job]:
        """Abre a página de cada vaga e troca o trecho pela descrição completa (quando encontrada).

        `on_job` recebe cada vaga assim que o detalhe dela é lido (antes de abrir a próxima)."""
        if not jobs:
            return jobs
        max_chars = self._settings.filtro.trecho_max_chars
        enriched = []
        with self._session() as navigator:
            for job in jobs:
                self._open_checked(navigator, job.link)
                text = " ".join(navigator.first_text(self._site.detail_selectors).split())[:max_chars]
                detailed = self._with_detail(navigator, job, text)
                enriched.append(detailed)
                if on_job:
                    on_job(detailed)
        if getattr(self._site, "published_selectors", None):
            undated = sum(1 for job in enriched if not job.publicada_em)
            if undated:
                log.warning(
                    "Fonte %s: %d de %d vagas abertas no detalhe ficaram sem data de publicação (o texto da página pode ter mudado)",
                    self.name, undated, len(enriched),
                )
        return enriched

    def _with_detail(self, navigator: Navigator, job: Job, text: str) -> Job:
        """Troca o trecho pela descrição e, se o site mostra a data no detalhe (LinkedIn), preenche `publicada_em`."""
        changes = {"trecho": text} if text else {}
        selectors = getattr(self._site, "published_selectors", [])
        if selectors:
            published = self._published_at(navigator, selectors)
            if published:
                changes["publicada_em"] = published
        return replace(job, **changes) if changes else job

    def _published_at(self, navigator: Navigator, selectors: list[str]) -> str | None:
        """Cada seletor do site, em ordem; sem data em nenhum (classe mudou), procura a linha da data no texto da página."""
        now = self._clock()
        for selector in selectors:
            published = self._site.parse_published(navigator.first_text([selector]), now)
            if published:
                return published
        return find_published_line(navigator.first_text(["body"]), now)

    def _search_term(self, navigator: Navigator, termo: str, found: dict[str, Job]) -> None:
        """Abre até `max_paginas_por_termo` páginas de resultados do termo; para antes se a página vier vazia
        ou só repetir vagas que este termo já viu. Vaga já achada por outro termo fica com o primeiro."""
        seen: set[str] = set()
        for page_number in range(self._settings.limites.max_paginas_por_termo):
            start = page_number * self._site.page_size
            self._open_checked(navigator, self._site.search_url(termo, start))
            raws = self._read_cards(navigator)
            if not raws:
                self._check_layout(navigator, start)
                return
            page = [replace(job, palavra_chave=termo) for job in map(self._site.to_job, raws) if job and job.id not in seen]
            if not page:
                return
            for job in page:
                seen.add(job.id)
                found.setdefault(job.id, job)

    def _read_cards(self, navigator: Navigator) -> list[dict]:
        if self._site.lazy_cards:
            return navigator.extract_progressive(self._site.extract_js, self._site.card_selector, self._scroll_pause)
        return navigator.extract(self._site.extract_js)

    def _open_checked(self, navigator: Navigator, url: str) -> None:
        """Abre a página; se bloqueada, espera o usuário concluir a verificação à mão e reabre **a mesma página**
        (a busca segue de onde parou). Sem portão, sem confirmação ou com o prazo esgotado, a fonte para."""
        navigator.open(url)
        self._pause()
        while True:
            try:
                self._check_block(navigator)
                return
            except SourceBlocked:
                if self._gate is None or not self._gate.wait(self.name, self._settings.navegador.espera_verificacao_s):
                    raise
            self._reopen_after_verification(navigator, url)
            self._pause()

    def _reopen_after_verification(self, navigator: Navigator, url: str) -> None:
        """Ao concluir a verificação o site ainda redireciona e o `goto` pode ser abortado: uma nova tentativa, após a pausa."""
        try:
            navigator.open(url)
        except SourceUnavailable:
            self._pause()
            navigator.open(url)

    def _check_block(self, navigator: Navigator) -> None:
        url, title, text = navigator.snapshot()
        motivo = self._site.classify(url, title, text)
        if motivo:
            raise SourceBlocked(f"Página de bloqueio detectada ({motivo}) em {url}", motivo=motivo)

    def _check_layout(self, navigator: Navigator, start: int) -> None:
        """Sem cards na primeira página e sem aviso de 'nenhum resultado' = seletor provavelmente mudou."""
        _, _, text = navigator.snapshot()
        if start == 0 and not self._site.is_empty_page(text):
            raise SourceLayoutChanged(f"Nenhum card encontrado em {self._site.name}: o seletor pode ter mudado")
