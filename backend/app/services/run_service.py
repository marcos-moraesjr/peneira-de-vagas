"""Orquestra uma execução: busca por fonte (isolada), filtro, deduplicação e registro do resultado."""
import logging
import sqlite3
import threading
from collections.abc import Callable
from datetime import date
from typing import Protocol

from .. import db
from ..config import Settings
from ..errors import DomainError
from ..sources.errors import SourceEmpty, SourceError
from ..sources.types import Job
from . import keywords, scanners
from .filters import Filter
from .scanners import Manifest

log = logging.getLogger(__name__)


class Source(Protocol):
    name: str

    def search(self, termos: list[str]) -> list[Job]: ...

    def enrich(self, jobs: list[Job]) -> list[Job]: ...


def _build_filter(conn: sqlite3.Connection, settings: Settings) -> tuple[list[str], Filter]:
    termos = [k["termo"] for k in keywords.list_all(conn, "busca")]
    exclusoes = [k["termo"] for k in keywords.list_all(conn, "exclusao")]
    f = settings.filtro
    return termos, Filter(termos, exclusoes, f.peso_titulo, f.peso_descricao, f.min_score)


def _update_source(conn: sqlite3.Connection, run_id: int, fonte: str, **fields) -> None:
    sets = ", ".join(f"{key}=?" for key in fields)
    conn.execute(f"UPDATE run_sources SET {sets} WHERE run_id=? AND fonte=?", (*fields.values(), run_id, fonte))
    conn.commit()


def _approve(jobs: list[Job], flt: Filter) -> tuple[list[Job], dict[str, int]]:
    approved, scores = [], {}
    for job in jobs:
        result = flt.evaluate(job.titulo, job.trecho)
        if result.approved:
            approved.append(job)
            scores[job.id] = result.score
    return approved, scores


def _run_source(conn, settings, source: Source, termos, flt, run_id: int, now: str) -> None:
    jobs = source.search(termos)
    if not jobs:
        raise SourceEmpty("A fonte não devolveu nenhuma vaga")
    approved, scores = _approve(jobs, flt)
    unknown = db.filter_unknown(conn, approved)
    cap = settings.limites.max_paginas_detalhe
    detailed = source.enrich(unknown[:cap])
    detailed_ok, detailed_scores = _approve(detailed, flt)
    final = detailed_ok + unknown[cap:]
    scores.update(detailed_scores)
    novas = db.insert_new_jobs(conn, final, scores, run_id, now)
    _update_source(conn, run_id, source.name, status="ok", lidas=len(jobs), aprovadas=len(approved), novas=novas)


def _warn_scanners_to_redo(conn: sqlite3.Connection, settings: Settings, manifest: Manifest, now: str) -> None:
    for state in scanners.evaluate(conn, settings, manifest, date.fromisoformat(now[:10])):
        if state["status"] == "refazer":
            log.warning(
                "Scanner %s: refazer (v%s, %d falhas seguidas, motivo %s)",
                state["fonte"], state["versao"], state["falhas_consecutivas"], state["ultimo_motivo"],
            )


def execute_run(
    settings: Settings,
    run_id: int,
    sources: list[Source],
    now: Callable[[], str],
    manifest: Manifest | None = None,
) -> None:
    """Roda cada fonte isolada: a falha de uma é registrada e a execução segue para a próxima."""
    conn = db.connect(settings.geral.db_path)
    try:
        termos, flt = _build_filter(conn, settings)
        for source in sources:
            _update_source(conn, run_id, source.name, status="buscando")
            try:
                _run_source(conn, settings, source, termos, flt, run_id, now())
            except SourceError as error:
                log.warning("Fonte %s falhou: %s (%s)", source.name, error.motivo, error.detalhe)
                _update_source(conn, run_id, source.name, status="falha", motivo=error.motivo, detalhe=error.detalhe)
            except Exception as error:  # noqa: BLE001 - uma fonte nunca derruba as demais
                log.exception("Erro inesperado na fonte %s", source.name)
                _update_source(conn, run_id, source.name, status="falha", motivo="erro_interno", detalhe=str(error))
        conn.execute("UPDATE runs SET status='concluida', fim=? WHERE id=?", (now(), run_id))
        conn.commit()
        if manifest:
            _warn_scanners_to_redo(conn, settings, manifest, now())
    finally:
        conn.close()


def spawn_thread(target: Callable[[], None]) -> None:
    threading.Thread(target=target, daemon=True).start()


def start_run(
    conn: sqlite3.Connection,
    settings: Settings,
    sources: list[Source],
    now: Callable[[], str],
    spawn: Callable[[Callable[[], None]], None] = spawn_thread,
    manifest: Manifest | None = None,
) -> int:
    """Valida, abre a execução (uma por vez) e a dispara em segundo plano, gravando a versão de cada scanner."""
    if not keywords.list_all(conn, "busca"):
        raise DomainError("Adicione ao menos uma palavra-chave para buscar")
    versions = manifest.versions() if manifest else None
    run_id = db.create_run(conn, [source.name for source in sources], now(), versions)
    spawn(lambda: execute_run(settings, run_id, sources, now, manifest))
    return run_id
