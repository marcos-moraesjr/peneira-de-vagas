"""Adaptador do Indeed. Seletores OBSERVADOS no DOM real em 14/10/2026 (docs/SCANNERS.md §Indeed); frágeis.
Cloudflare e verificações são detectados e tratados como falha da fonte; nunca contornados.

O card não traz data de publicação; o filtro de recência é só o `fromage` da URL (efeito não confirmado)
mais a deduplicação. A descrição completa é lida no painel da listagem, sem abrir `/viewjob`.
"""
from urllib.parse import urlencode, urlsplit

from ..config import Settings
from ..services.filters import normalize
from ..services.localizacao import detect_modalidade
from ..services.search_query import platform_params
from .types import Job

CARD_SELECTOR = "div.job_seen_beacon"
EMPTY_MARKERS = ("nao encontrou nenhum resultado", "did not match any jobs", "nenhuma vaga")
CLOUDFLARE_TITLES = ("just a moment", "um momento", "attention required")
CLOUDFLARE_TEXTS = ("verifique que voce e humano", "verifique se voce e humano", "verify you are human", "checking your browser")
CAPTCHA_TEXTS = ("additional verification required", "captcha")

EXTRACT_JS = """() => {
  const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const text = (root, selector) => { const e = root.querySelector(selector); return e ? clean(e.innerText || e.textContent) : ''; };
  // A listagem real traz cards-isca 0x0 (id falso, link `/viewjob`) que o usuário não vê; clicá-los
  // tira a página da listagem. Só entram cards com área visível.
  const visible = (card) => { const box = card.getBoundingClientRect(); return box.width > 0 && box.height > 0; };
  return [...document.querySelectorAll('div.job_seen_beacon')].filter(visible).map((card) => {
  // `jcs-JobTitle` é uma classe de apresentação e mudou no site. `data-jk`
  // é o identificador estável usado também para abrir o painel.
  const link = card.querySelector('a[data-jk]');
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

OPEN_DETAIL_JS = """() => {
  const jobId = __JOB_ID__;
  const title = [...document.querySelectorAll('a[data-jk]')]
    .find((link) => link.getAttribute('data-jk') === jobId);
  if (!title) return false;
  title.click();
  return true;
}"""


class IndeedSite:
    name = "indeed"
    extract_js = EXTRACT_JS
    card_selector = CARD_SELECTOR
    lazy_cards = False
    open_detail_js = OPEN_DETAIL_JS
    detail_navigation_fallback = False
    detail_selectors = [".simple-job-description-html", "#jobDescriptionText", ".jobsearch-JobComponent-description"]

    def __init__(self, settings: Settings):
        self._settings = settings
        self.page_size = settings.indeed.page_size
        parts = urlsplit(settings.indeed.base_url)
        self._origin = f"{parts.scheme}://{parts.netloc}"

    def search_url(self, termo: str, start: int) -> str:
        """Monta a URL com a localidade adaptada; modalidade permanece no filtro local."""
        params = {
            "q": termo,
            "fromage": self._settings.busca.janela_dias,
            "start": start,
        }
        params.update(platform_params(self.name, self._settings))
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
            modalidade=detect_modalidade(f"{raw.get('location', '')} {raw.get('text', '')}"),
        )
