"""Fonte simulada e fábricas usadas pelos testes da API."""
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.sources.types import Job

NOW = "2026-10-14T12:00:00+00:00"


class StubSource:
    def __init__(self, name="stub", jobs=None):
        self.name = name
        self._jobs = jobs if jobs is not None else []

    def search(self, termos):
        return list(self._jobs)

    def enrich(self, jobs, on_job=None):
        for j in jobs:
            if on_job:
                on_job(j)
        return jobs


def job(id_da_vaga, titulo="Engenheiro Mecânico", fonte="stub", empresa="ACME"):
    return Job(id_da_vaga, titulo, empresa, f"https://x/{id_da_vaga}", "", fonte)


def make_client(settings, sources, spawn=lambda fn: fn()):
    app = create_app(settings, sources_factory=lambda: sources, spawn=spawn, now=lambda: NOW)
    return TestClient(app)
