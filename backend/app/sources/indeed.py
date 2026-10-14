"""Adaptador do Indeed. Seletores OBSERVADOS no DOM real em 14/10/2026 (EXPLORACAO_PLATAFORMAS.md §2.3); frágeis.
Cloudflare e verificações são detectados e tratados como falha da fonte; nunca contornados.

O card não traz data de publicação; o filtro de recência é só o `fromage` da URL (efeito não confirmado)
mais a deduplicação. O trecho é o conjunto de itens <li> do card (tipo de vaga, salário, resumo).
"""
import math
from urllib.parse import urlencode, urlsplit

from ..config import Settings
from ..services.filters import normalize
from .types import Job

HOURS_PER_DAY = 24
CARD_SELECTOR = "div.job_seen_beacon"
EMPTY_MARKERS = ("nao encontrou nenhum resultado", "did not match any jobs", "nenhuma vaga")
CLOUDFLARE_TITLES = ("just a moment", "um momento", "attention required")
CLOUDFLARE_TEXTS = ("verifique que voce e humano", "verifique se voce e humano", "verify you are human", "checking your browser")
CAPTCHA_TEXTS = ("additional verification required", "captcha")

EXTRACT_JS = """() => {
  const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const text = (root, selector) => { const e = root.querySelector(selector); return e ? clean(e.innerText || e.textContent) : ''; };
  return [...document.querySelectorAll('div.job_seen_beacon')].map((card) => {
    const link = card.querySelector('a.jcs-JobTitle[data-jk]');
    const titled = link && link.querySelector('span[title]');
    return {
      id: link ? link.getAttribute('data-jk') || '' : '',
      title: clean((titled && titled.getAttribute('title')) || (link && link.innerText) || ''),
      company: text(card, '[data-testid="company-name"]'),
      location: text(card, '[data-testid="text-location"]'),
      text: [...card.querySelectorAll('li')].map((li) => clean(li.innerText || li.textContent)).filter(Boolean).join(' | '),
    };
  });
}"""


class IndeedSite:
    name = "indeed"
    extract_js = EXTRACT_JS
    card_selector = CARD_SELECTOR
    lazy_cards = False
    detail_selectors = ["#jobDescriptionText", ".jobsearch-JobComponent-description"]

    def __init__(self, settings: Settings):
        self._settings = settings
        self.page_size = settings.indeed.page_size
        parts = urlsplit(settings.indeed.base_url)
        self._origin = f"{parts.scheme}://{parts.netloc}"

    def search_url(self, termo: str, start: int, localidade: str = "") -> str:
        busca = self._settings.busca
        params = {"q": termo}
        if localidade:
            params["l"] = localidade
        params["fromage"] = max(1, math.ceil(busca.janela_horas / HOURS_PER_DAY))
        params["start"] = start
        return f"{self._settings.indeed.base_url}?{urlencode(params)}"

    def classify(self, url: str, title: str, text: str) -> str | None:
        title_n, text_n = normalize(title), normalize(text)
        if "/auth" in url:
            return "login"
        if title_n.startswith(CLOUDFLARE_TITLES) or any(marker in text_n for marker in CLOUDFLARE_TEXTS):
            return "cloudflare"
        if any(marker in text_n for marker in CAPTCHA_TEXTS):
            return "captcha"
        return None

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
            link=f"{self._origin}/viewjob?jk={raw['id']}",
            trecho=raw.get("text", ""),
            fonte=self.name,
            localidade=raw.get("location", ""),
        )
