"""Adaptador do Google: executa consultas booleanas completas (`[google] consultas`) que apontam para páginas de
vagas de ATS (lever, greenhouse…). O seletor do JS de extração NÃO foi observado no DOM real (ver SCANNERS.md);
frágil. CAPTCHA ("tráfego incomum"), consentimento e login são detectados e tratados como falha da fonte; nunca
contornados.

Cada resultado vira uma vaga cujo `id` é o link canônico (sem query nem fragmento). A empresa fica vazia: a página
de resultados não a traz de forma estável.
"""
import math
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from ..config import Settings
from ..services.filters import normalize
from .browser import BrowserSource
from .types import Job

HOURS_PER_DAY = 24
CARD_SELECTOR = "#search a h3"
EMPTY_MARKERS = ("nao encontrou nenhum documento", "did not match any documents")
CAPTCHA_TEXTS = ("trafego incomum", "unusual traffic")
LOGIN_HOSTS = ("consent.google.com", "accounts.google.com")
GOOGLE_HOST = re.compile(r"(^|\.)google\.")

EXTRACT_JS = """() => {
  const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  return [...document.querySelectorAll('#search a')].filter((a) => a.querySelector('h3')).map((a) => {
    const box = a.closest('div.g') || a.parentElement.parentElement.parentElement;
    const snippet = box && box.querySelector('[data-sncf], .VwiC3b, [style*="line-clamp"]');
    return {
      id: a.getAttribute('href') || '',
      title: clean(a.querySelector('h3').innerText),
      text: snippet ? clean(snippet.innerText) : '',
    };
  });
}"""


def _canonical(href: str) -> str | None:
    """Link da vaga sem rastreio: desembrulha `/url?q=`, aceita só http(s) e recusa páginas do próprio Google."""
    parts = urlsplit(href)
    if parts.path == "/url" and not parts.netloc:
        target = parse_qs(parts.query).get("q")
        if not target:
            return None
        parts = urlsplit(target[0])
    if parts.scheme not in ("http", "https") or not parts.netloc or GOOGLE_HOST.search(parts.hostname or ""):
        return None
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


class GoogleSite:
    name = "google"
    extract_js = EXTRACT_JS
    card_selector = CARD_SELECTOR
    lazy_cards = False
    detail_selectors: list[str] = []

    def __init__(self, settings: Settings):
        self._settings = settings
        self.page_size = settings.google.page_size

    def search_url(self, termo: str, start: int, localidade: str = "") -> str:
        days = math.ceil(self._settings.busca.janela_horas / HOURS_PER_DAY)
        params = {"q": termo, "tbs": "qdr:d" if days == 1 else f"qdr:d{days}", "start": start}
        return f"{self._settings.google.base_url}?{urlencode(params)}"

    def classify(self, url: str, title: str, text: str) -> str | None:
        parts = urlsplit(url)
        if parts.hostname in LOGIN_HOSTS:
            return "login"
        if parts.path.startswith("/sorry") or any(marker in normalize(text) for marker in CAPTCHA_TEXTS):
            return "captcha"
        return None

    def is_empty_page(self, text: str) -> bool:
        normalized = normalize(text)
        return any(marker in normalized for marker in EMPTY_MARKERS)

    def to_job(self, raw: dict) -> Job | None:
        link = _canonical(raw.get("id", ""))
        if not link or not raw.get("title"):
            return None
        return Job(id=link, titulo=raw["title"], empresa="", link=link, trecho=raw.get("text", ""), fonte=self.name)


class GoogleSource(BrowserSource):
    """A consulta booleana já é o filtro: lê `[google] consultas` (não as palavras-chave do painel), não abre a
    página de cada vaga e pede ao serviço de execução que não reaplique o filtro local."""

    local_filter = False

    def search(self, termos: list[str]) -> list[Job]:
        return super().search(self._settings.google.consultas)

    def _localidades(self) -> list[str]:
        return [""]  # a localidade, se houver, já está escrita na consulta booleana

    def enrich(self, jobs: list[Job]) -> list[Job]:
        return jobs
