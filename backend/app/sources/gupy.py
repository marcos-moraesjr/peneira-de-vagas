"""Fonte Gupy: API JSON do portal (endpoint não documentado, tratado como instável).

Campos lidos de cada vaga (formato observado no DevTools, aba Network): id, name, description,
careerPageName, jobUrl. Se um deles sumir, é mudança de layout.
"""
import re
from collections.abc import Callable
from dataclasses import replace

import httpx

from ..config import Settings
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

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self._settings = settings
        self._client = client

    def search(self, termos: list[str]) -> list[Job]:
        client = self._client or httpx.Client(timeout=self._settings.gupy.timeout_s)
        try:
            return self._collect(client, termos)
        finally:
            if self._client is None:
                client.close()

    def enrich(self, jobs: list[Job], on_job: Callable[[Job], None] | None = None) -> list[Job]:
        """A lista da Gupy já traz a descrição; não há página de detalhe a abrir."""
        for job in jobs:
            if on_job:
                on_job(job)
        return jobs

    def _collect(self, client: httpx.Client, termos: list[str]) -> list[Job]:
        found: dict[str, Job] = {}
        for termo in termos:
            for job in self._pages(client, termo):
                if job.id not in found:
                    found[job.id] = replace(job, palavra_chave=termo)
        return list(found.values())

    def _pages(self, client: httpx.Client, termo: str):
        """Pede até `max_paginas_por_termo` páginas da API; para antes se acabarem as vagas do termo."""
        offset = 0
        for _ in range(self._settings.limites.max_paginas_por_termo):
            payload = self._request(client, termo, offset)
            items = payload["data"]
            for item in items:
                yield self._to_job(item)
            offset += len(items)
            total = (payload.get("pagination") or {}).get("total", 0)
            if not items or offset >= total:
                return

    def _request(self, client: httpx.Client, termo: str, offset: int) -> dict:
        params = {"jobName": termo, "limit": self._settings.gupy.page_size, "offset": offset}
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
