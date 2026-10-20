"""Fonte Gupy: API JSON do portal (endpoint não documentado, tratado como instável).

Campos lidos de cada vaga (formato observado no DevTools, aba Network): id, name, description,
careerPageName, jobUrl. Se um deles sumir, é mudança de layout.
"""
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import httpx

from ..config import Settings
from ..services.search_query import platform_params
from .errors import SourceLayoutChanged, SourceUnavailable
from .types import Job

MODALIDADE_DA_GUPY = {"remote": "remoto", "hybrid": "hibrido", "on-site": "presencial"}
REQUIRED_FIELDS = ("id", "name", "jobUrl")


def _plain_text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html or "").split())


def _canonical_link(url: str) -> str:
    return url.split("?", 1)[0]


class GupySource:
    name = "gupy"

    def __init__(
        self, settings: Settings, client: httpx.Client | None = None, clock: Callable[[], datetime] | None = None
    ):
        self._settings = settings
        self._client = client
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def search(self, termos: list[str]) -> list[Job]:
        client = self._client or httpx.Client(timeout=self._settings.gupy.timeout_s)
        try:
            return self._collect_by_page(client, termos, lambda page: [], None, (0, 0), None)
        finally:
            if self._client is None:
                client.close()

    def enrich(self, jobs: list[Job], on_job: Callable[[Job], None] | None = None) -> list[Job]:
        """A lista da Gupy já traz a descrição; não há página de detalhe a abrir."""
        for job in jobs:
            if on_job:
                on_job(job)
        return jobs

    def search_and_enrich(
        self,
        termos: list[str],
        select_jobs: Callable[[list[Job]], list[Job]],
        on_job: Callable[[Job], None] | None = None,
        inicio: tuple[int, int] = (0, 0),
        on_page: Callable[[int, int], None] | None = None,
    ) -> list[Job]:
        """Página a página: entrega as vagas novas de cada página antes de pedir a próxima, para a retomada.

        `inicio` = (índice do termo, página) a pedir primeiro; `on_page(termo, pagina)` recebe a **próxima**
        posição depois de cada página entregue."""
        client = self._client or httpx.Client(timeout=self._settings.gupy.timeout_s)
        try:
            return self._collect_by_page(client, termos, select_jobs, on_job, inicio, on_page)
        finally:
            if self._client is None:
                client.close()

    def _collect_by_page(self, client, termos, select_jobs, on_job, inicio, on_page) -> list[Job]:
        cutoff = self._clock() - timedelta(days=self._settings.busca.janela_dias)
        max_pages = self._settings.limites.max_paginas_por_termo
        first_term, first_page = inicio
        found: dict[str, Job] = {}
        for index, termo in enumerate(termos):
            if index < first_term:
                continue
            for page_number, jobs in self._pages(client, termo, first_page if index == first_term else 0):
                page = []
                for job in jobs:
                    if self._inside_recency_window(job, cutoff) and job.id not in found:
                        found[job.id] = replace(job, palavra_chave=termo)
                        page.append(found[job.id])
                self.enrich(select_jobs(page), on_job)
                if on_page and page_number + 1 < max_pages:
                    on_page(index, page_number + 1)
            if on_page:
                on_page(index + 1, 0)
        return list(found.values())

    def _inside_recency_window(self, job: Job, cutoff: datetime) -> bool:
        """Aceita vagas sem data, pois a API pode omitir o campo, e compara as datadas em UTC.

        Formato inválido é mudança explícita no contrato da API, nunca uma vaga silenciosamente aceita.
        """
        if not job.publicada_em:
            return True
        try:
            published = datetime.fromisoformat(job.publicada_em.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise SourceLayoutChanged(f"publishedDate inválido na vaga {job.id}: {job.publicada_em!r}") from error
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        return published >= cutoff

    def _pages(self, client: httpx.Client, termo: str, first_page: int = 0):
        """Pede até `max_paginas_por_termo` páginas da API (a partir de `first_page`) e entrega `(página, vagas)`;
        para antes se acabarem as vagas do termo."""
        offset = first_page * self._settings.gupy.page_size
        for page_number in range(first_page, self._settings.limites.max_paginas_por_termo):
            payload = self._request(client, termo, offset)
            items = payload["data"]
            yield page_number, [self._to_job(item) for item in items]
            offset += len(items)
            total = (payload.get("pagination") or {}).get("total", 0)
            if not items or offset >= total:
                return

    def _request(self, client: httpx.Client, termo: str, offset: int) -> dict:
        params = {"jobName": termo, "limit": self._settings.gupy.page_size, "offset": offset}
        params.update(platform_params(self.name, self._settings))
        try:
            response = client.get(self._settings.gupy.base_url, params=params)
        except httpx.HTTPError as error:
            raise SourceUnavailable(f"Falha de rede na Gupy: {error}") from error
        if response.status_code != 200:
            raise SourceUnavailable(f"HTTP {response.status_code} na Gupy (esperado 200)")
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise SourceLayoutChanged("Resposta da Gupy sem a lista 'data'")
        return payload

    def _to_job(self, item: dict) -> Job:
        missing = [key for key in REQUIRED_FIELDS if not item.get(key)]
        if missing:
            raise SourceLayoutChanged(f"Vaga da Gupy sem os campos {missing}")
        trecho = _plain_text(item.get("description", ""))[: self._settings.filtro.trecho_max_chars]
        return Job(
            id=str(item["id"]),
            titulo=item["name"].strip(),
            empresa=(item.get("careerPageName") or "").strip(),
            link=_canonical_link(item["jobUrl"]),
            trecho=trecho,
            fonte=self.name,
            localidade=", ".join(part.strip() for part in (item.get("city"), item.get("state")) if part and part.strip()),
            publicada_em=item.get("publishedDate") or None,
            modalidade=MODALIDADE_DA_GUPY.get(item.get("workplaceType"), ""),
        )
