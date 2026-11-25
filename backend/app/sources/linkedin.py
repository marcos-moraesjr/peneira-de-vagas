"""Adaptador do LinkedIn. Seletores OBSERVADOS no DOM real em 15/11/2026 (docs/SCANNERS.md §LinkedIn); frágeis,
mudam sem aviso. Ao quebrar, a fonte falha com 'seletor_nao_encontrado' em vez de devolver lista vazia.

Layout atual: cada card é um div[componentkey="job-card-component-ref-<id>"] (sem <li>, sem link /jobs/view/ e
sem classes estáveis, que têm hash). O card só traz título/empresa depois de renderizar (lazy_cards=True).
"""
from datetime import datetime
from urllib.parse import urlencode

from ..config import Settings
from ..services.filters import normalize
from ..services.localizacao import detect_modalidade
from ..services.search_query import platform_params
from .relative_date import parse_relative_date
from .types import Job

SECONDS_PER_HOUR = 3600
CARD_PREFIX = "job-card-component-ref-"
CARD_SELECTOR = f'[componentkey^="{CARD_PREFIX}"]'
# Linhas do cabeçalho da página pública (sem sessão): o LinkedIn serve a busca sem redirecionar para /login.
LOGGED_OUT_LINES = ("cadastre se agora", "join now")
EMPTY_MARKERS = ("nenhuma vaga correspondente", "no matching jobs", "nenhum resultado")

# Na página de detalhe: "Cidade · há 2 dias · 11 candidaturas" (observado em 15/11/2026), num <p> com <span><strong>.
PUBLISHED_SELECTORS = ["p:has(> span > strong)"]

OPEN_DETAIL_JS = """() => {
  const jobId = __JOB_ID__;
  const card = document.querySelector('[componentkey="job-card-component-ref-' + jobId + '"]');
  if (!card) return false;
  const target = card.querySelector('[role="button"]') || card;
  target.click();
  return true;
}"""


EXTRACT_JS = """() => {
  const prefix = 'job-card-component-ref-';
  const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  return [...document.querySelectorAll('[componentkey^="' + prefix + '"]')].map((card) => {
    const titleBox = card.querySelector('div[data-display-contents="true"] > p');
    const spans = titleBox ? [...titleBox.children].filter((e) => e.tagName === 'SPAN') : [];
    const lockup = titleBox ? titleBox.parentElement.parentElement : null;
    const company = titleBox && titleBox.parentElement.nextElementSibling;
    const place = lockup && [...lockup.children].find((e) => e.tagName === 'P');
    return {
      id: (card.getAttribute('componentkey') || '').slice(prefix.length),
      title: spans.length ? clean(spans[spans.length - 1].innerText || spans[spans.length - 1].textContent) : '',
      company: company ? clean(company.innerText || company.textContent) : '',
      text: place ? clean(place.innerText || place.textContent) : '',
    };
  });
}"""


class LinkedInSite:
    name = "linkedin"
    extract_js = EXTRACT_JS
    card_selector = CARD_SELECTOR
    lazy_cards = True
    published_selectors = PUBLISHED_SELECTORS
    open_detail_js = OPEN_DETAIL_JS
    detail_selectors = [
        '[data-testid="expandable-text-box"]',
        "article",
        ".jobs-description__content",
        ".jobs-box__html-content",
        "#job-details",
        ".show-more-less-html__markup",
        ".jobs-description",
    ]

    def __init__(self, settings: Settings):
        self._settings = settings
        self.page_size = settings.linkedin.page_size

    def search_url(self, termo: str, start: int) -> str:
        """Monta a URL com os parâmetros canônicos adaptados para o LinkedIn."""
        params = {
            "keywords": termo,
            "f_TPR": f"r{self._settings.busca.janela_dias * 24 * SECONDS_PER_HOUR}",
            "start": start,
        }
        params.update(platform_params(self.name, self._settings))
        return f"{self._settings.linkedin.base_url}?{urlencode(params)}"

    def classify(self, url: str, title: str, text: str) -> str | None:
        if "/checkpoint" in url:
            return "captcha"
        if any(part in url for part in ("/authwall", "/login", "/uas/")):
            return "login"
        lines = {normalize(line) for line in text.splitlines()}
        if any(marker in lines for marker in LOGGED_OUT_LINES):
            return "login"
        return None

    def parse_published(self, text: str, now: datetime) -> str | None:
        return parse_relative_date(text, now)

    def is_empty_page(self, text: str) -> bool:
        normalized = normalize(text)
        return any(marker in normalized for marker in EMPTY_MARKERS)

    def to_job(self, raw: dict) -> Job | None:
        if not raw.get("id") or not raw.get("title"):
            return None
        return Job(
            id=raw["id"],
            titulo=raw["title"],
            empresa=raw.get("company", ""),
            link=f"https://www.linkedin.com/jobs/view/{raw['id']}/",
            trecho=raw.get("text", ""),
            fonte=self.name,
            localidade=raw.get("text", ""),  # a legenda do card é a localidade (e a modalidade, entre parênteses)
            modalidade=detect_modalidade(raw.get("text", "")),
        )
