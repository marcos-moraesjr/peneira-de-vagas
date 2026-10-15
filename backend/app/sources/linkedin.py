"""Adaptador do LinkedIn. Seletores OBSERVADOS no DOM real em 14/10/2026 (EXPLORACAO_PLATAFORMAS.md §2.2); frágeis,
mudam sem aviso. Ao quebrar, a fonte falha com 'seletor_nao_encontrado' em vez de devolver lista vazia.

A renderização é incremental: o <li> já traz o ID, mas título/empresa só aparecem depois de rolar até ele
(por isso lazy_cards=True). As classes dos contêineres têm hash aleatório e não são usadas.
"""
from datetime import datetime
from urllib.parse import urlencode

from ..config import Settings
from ..services.filters import normalize
from ..services.localizacao import detect_modalidade
from .relative_date import parse_relative_date
from .types import Job

SECONDS_PER_HOUR = 3600
CARD_SELECTOR = "li[data-occludable-job-id]"
EMPTY_MARKERS = ("nenhuma vaga correspondente", "no matching jobs", "nenhum resultado")

# Na página de detalhe: "Cidade · Anunciada novamente há 8 horas · 95 candidaturas" (observado em 14/10/2026).
PUBLISHED_SELECTORS = [".job-details-jobs-unified-top-card__tertiary-description-container"]


EXTRACT_JS = """() => {
  const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const text = (root, selector) => { const e = root.querySelector(selector); return e ? clean(e.innerText || e.textContent) : ''; };
  return [...document.querySelectorAll('li[data-occludable-job-id]')].map((li) => ({
    id: li.getAttribute('data-occludable-job-id') || '',
    title: text(li, 'a[href*="/jobs/view/"] strong'),
    company: text(li, '.artdeco-entity-lockup__subtitle'),
    text: text(li, '.artdeco-entity-lockup__caption'),
  }));
}"""


class LinkedInSite:
    name = "linkedin"
    extract_js = EXTRACT_JS
    card_selector = CARD_SELECTOR
    lazy_cards = True
    published_selectors = PUBLISHED_SELECTORS
    detail_selectors = [
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
        """Só termo, janela e página: localidade e modalidade não vão na busca (o filtro local decide)."""
        params = {
            "keywords": termo,
            "f_TPR": f"r{self._settings.busca.janela_horas * SECONDS_PER_HOUR}",
            "start": start,
        }
        return f"{self._settings.linkedin.base_url}?{urlencode(params)}"

    def classify(self, url: str, title: str, text: str) -> str | None:
        if "/checkpoint" in url:
            return "captcha"
        if any(part in url for part in ("/authwall", "/login", "/uas/")):
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
