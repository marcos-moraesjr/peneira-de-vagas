"""Base comum das fontes de navegador (LinkedIn e Indeed): Chrome dedicado via CDP, ritmo humano,
detecção de bloqueio e leitura da lista. Nada aqui tenta contornar bloqueio: ao detectá-lo, a fonte para.
"""
import logging
import json
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

    def expand_detail(self, js: str) -> bool: ...

    def open_detail(self, js: str) -> bool: ...


class NavigationResponse:
    """Captura o status da resposta principal sem manter listener depois da navegação."""

    def __init__(self, page, url: str):
        self.status: int | None = None
        self._page = page
        self._url = url
        self._listener = self._record
        self._listening = callable(getattr(page, "on", None))
        if self._listening:
            page.on("response", self._listener)

    def _record(self, response) -> None:
        if response.url == self._url:
            self.status = response.status

    def close(self) -> None:
        if self._listening:
            self._page.remove_listener("response", self._listener)


class PlaywrightNavigator:
    def __init__(self, page, timeout_ms: int, max_tentativas_abertura: int = 1):
        self._page = page
        self._timeout_ms = timeout_ms
        self._max_tentativas_abertura = max_tentativas_abertura

    def open(self, url: str) -> None:
        for attempt in range(self._max_tentativas_abertura):
            response = NavigationResponse(self._page, url)
            try:
                self._page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                return
            except PlaywrightTimeout as error:
                raise SourceUnavailable(
                    f"Tempo esgotado ao abrir {url} após {attempt + 1} tentativa(s)"
                    f" de {self._max_tentativas_abertura}",
                    motivo="http_erro",
                ) from error
            except PlaywrightError as error:
                detail = f"HTTP {response.status}: " if response.status else ""
                if "ERR_ABORTED" not in str(error).upper() or attempt + 1 == self._max_tentativas_abertura:
                    raise SourceUnavailable(
                        f"Falha ao abrir {url} após {attempt + 1} tentativa(s)"
                        f" de {self._max_tentativas_abertura}: {detail}{error}",
                        motivo="http_erro",
                    ) from error
                log.warning(
                    "Abertura abortada em %s; nova tentativa %d/%d",
                    url, attempt + 2, self._max_tentativas_abertura,
                )
            finally:
                response.close()

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

        def merge(raws: list[dict]) -> None:
            for raw in raws:
                if raw.get("id") and (raw["id"] not in merged or raw.get("title")):
                    merged[raw["id"]] = raw

        # Muitos cards do LinkedIn já vêm completos no primeiro DOM. Evita
        # rolagem e pausa nesses cards, mantendo a rolagem dos lazy cards.
        merge(self._page.evaluate(js))
        for index in range(cards.count()):
            card = cards.nth(index)
            card_id = card.get_attribute("data-occludable-job-id")
            if card_id and merged.get(card_id, {}).get("title"):
                continue
            card.scroll_into_view_if_needed(timeout=self._timeout_ms)
            pause()
            merge(self._page.evaluate(js))
        return list(merged.values())

    def first_text(self, selectors: list[str]) -> str:
        for selector in selectors:
            locator = self._page.locator(selector).first
            if locator.count():
                return locator.text_content(timeout=self._timeout_ms) or ""
        return ""

    def expand_detail(self, js: str) -> bool:
        expanded = bool(self._page.evaluate(js))
        if expanded:
            self._page.wait_for_timeout(100)
        return expanded

    def open_detail(self, js: str) -> bool:
        opened = bool(self._page.evaluate(js))
        if opened:
            self._page.wait_for_timeout(250)
        return opened


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
                yield PlaywrightNavigator(page, timeout_ms, settings.navegador.max_tentativas_abertura)
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

    def search_and_enrich(
        self,
        termos: list[str],
        select_jobs: Callable[[list[Job]], list[Job]],
        on_job: Callable[[Job], None] | None = None,
    ) -> list[Job]:
        """Busca por páginas e abre os detalhes elegíveis antes da próxima página.

        `select_jobs` recebe somente vagas novas da página; a fonte mantém a mesma aba
        para a busca e para os detalhes, reduzindo a espera visível no navegador.
        """
        found: dict[str, Job] = {}
        enriched = []

        def deliver(job: Job) -> None:
            enriched.append(job)
            if on_job:
                on_job(job)

        with self._session() as navigator:
            for termo in termos:
                self._search_term(navigator, termo, found, select_jobs, deliver)
        self._warn_missing_publication(enriched)
        return list(found.values())

    def enrich(self, jobs: list[Job], on_job: Callable[[Job], None] | None = None) -> list[Job]:
        """Abre a página de cada vaga e troca o trecho pela descrição completa (quando encontrada).

        `on_job` recebe cada vaga assim que o detalhe dela é lido (antes de abrir a próxima)."""
        if not jobs:
            return jobs
        max_chars = self._settings.filtro.trecho_max_chars
        enriched = []
        with self._session() as navigator:
            enriched.extend(self._enrich_jobs(navigator, jobs, max_chars, on_job))
        self._warn_missing_publication(enriched)
        return enriched

    def _warn_missing_publication(self, jobs: list[Job]) -> None:
        """Registra quando a fonte abriu detalhes mas não encontrou suas datas."""
        if not getattr(self._site, "published_selectors", None):
            return
        undated = sum(1 for job in jobs if not job.publicada_em)
        if undated:
            log.warning(
                "Fonte %s: %d de %d vagas abertas no detalhe ficaram sem data de publicação (o texto da página pode ter mudado)",
                self.name, undated, len(jobs),
            )

    def _enrich_jobs(
        self,
        navigator: Navigator,
        jobs: list[Job],
        max_chars: int,
        on_job: Callable[[Job], None] | None,
    ) -> list[Job]:
        """Abre uma sequência de detalhes usando a aba já conectada."""
        enriched = []
        for job in jobs:
            self._open_job_detail(navigator, job)
            expand_detail = getattr(self._site, "expand_detail_js", None)
            if expand_detail:
                navigator.expand_detail(expand_detail)
            text = " ".join(navigator.first_text(self._site.detail_selectors).split())[:max_chars]
            detailed = self._with_detail(navigator, job, text)
            enriched.append(detailed)
            if on_job:
                on_job(detailed)
        return enriched

    def _open_job_detail(self, navigator: Navigator, job: Job) -> None:
        """Abre o painel da lista ou, apenas quando permitido pela fonte, a URL do detalhe."""
        open_detail = getattr(self._site, "open_detail_js", None)
        if not open_detail:
            self._open_checked(navigator, job.link, "detalhe")
            return
        script = open_detail.replace("__JOB_ID__", json.dumps(job.id))
        for attempt in range(self._settings.navegador.max_tentativas_painel):
            if navigator.open_detail(script):
                self._scroll_pause()
                return
            if attempt + 1 < self._settings.navegador.max_tentativas_painel:
                log.warning(
                    "Painel da vaga %s em %s não abriu; nova tentativa %d/%d",
                    job.id, self.name, attempt + 2, self._settings.navegador.max_tentativas_painel,
                )
                self._scroll_pause()
        if not getattr(self._site, "detail_navigation_fallback", True):
            raise SourceLayoutChanged(
                f"Não abriu o painel da vaga {job.id} em {self.name} após "
                f"{self._settings.navegador.max_tentativas_painel} tentativa(s)"
            )
        self._open_checked(navigator, job.link, "detalhe")

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

    def _search_term(
        self,
        navigator: Navigator,
        termo: str,
        found: dict[str, Job],
        select_jobs: Callable[[list[Job]], list[Job]] | None = None,
        on_job: Callable[[Job], None] | None = None,
    ) -> None:
        """Abre até `max_paginas_por_termo` páginas de resultados do termo; para antes se a página vier vazia
        ou só repetir vagas que este termo já viu. Vaga já achada por outro termo fica com o primeiro."""
        seen: set[str] = set()
        for page_number in range(self._settings.limites.max_paginas_por_termo):
            start = page_number * self._site.page_size
            self._open_checked(navigator, self._site.search_url(termo, start), "busca")
            raws = self._read_cards(navigator)
            if not raws:
                self._check_layout(navigator, start)
                return
            page = [
                replace(job, palavra_chave=termo)
                for job in map(self._site.to_job, raws)
                if job and job.id not in seen and job.id not in found
            ]
            if not page:
                return
            for job in page:
                seen.add(job.id)
                found.setdefault(job.id, job)
            if select_jobs:
                selected = select_jobs(page)
                self._enrich_jobs(navigator, selected, self._settings.filtro.trecho_max_chars, on_job)

    def _read_cards(self, navigator: Navigator) -> list[dict]:
        if self._site.lazy_cards:
            return navigator.extract_progressive(self._site.extract_js, self._site.card_selector, self._scroll_pause)
        return navigator.extract(self._site.extract_js)

    def _open_checked(self, navigator: Navigator, url: str, etapa: str = "abertura") -> None:
        """Abre a página; se bloqueada, espera o usuário concluir a verificação à mão e reabre **a mesma página**
        (a busca segue de onde parou). Sem portão, sem confirmação ou com o prazo esgotado, a fonte para."""
        try:
            navigator.open(url)
        except SourceUnavailable as error:
            raise SourceUnavailable(
                f"Fonte {self.name}: falha na etapa {etapa}: {error.detalhe}",
                motivo=error.motivo,
            ) from error
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
