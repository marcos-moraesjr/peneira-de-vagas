"""Orquestra uma execução: busca por fonte (isolada), filtro, deduplicação e registro do resultado."""
import logging
import sqlite3
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Protocol

from .. import db
from ..config import Settings
from ..errors import DomainError
from ..sources.errors import SourceEmpty, SourceError
from ..sources.types import Job
from . import keywords, scanners
from .filters import Filter
from .localizacao import passes_localidade, passes_modalidade
from .scanners import Manifest

log = logging.getLogger(__name__)


class Source(Protocol):
    name: str

    def search(self, termos: list[str]) -> list[Job]: ...

    def enrich(self, jobs: list[Job], on_job: Callable[[Job], None] | None = None) -> list[Job]: ...


def _build_filter(conn: sqlite3.Connection, settings: Settings) -> tuple[list[str], Filter]:
    termos = [k["termo"] for k in keywords.list_all(conn, "busca")]
    exclusoes = [k["termo"] for k in keywords.list_all(conn, "exclusao")]
    f = settings.filtro
    return termos, Filter(termos, exclusoes, f.peso_titulo, f.peso_descricao, f.min_score)


def _update_source(conn: sqlite3.Connection, run_id: int, fonte: str, **fields) -> None:
    sets = ", ".join(f"{key}=?" for key in fields)
    conn.execute(f"UPDATE run_sources SET {sets} WHERE run_id=? AND fonte=?", (*fields.values(), run_id, fonte))
    conn.commit()


def _approve(jobs: list[Job], flt: Filter, settings: Settings) -> tuple[list[Job], dict[str, int]]:
    """Palavras-chave/exclusões (título e trecho) e, igual para todas as fontes, localidade e modalidade da config."""
    busca, aceitar = settings.busca, settings.filtro.aceitar_desconhecido
    approved, scores = [], {}
    for job in jobs:
        result = flt.evaluate(job.titulo, job.trecho)
        if (
            result.approved
            and passes_localidade(job.localidade, job.modalidade, busca.localidades, aceitar)
            and passes_modalidade(job.modalidade, busca.modalidade, aceitar)
        ):
            approved.append(job)
            scores[job.id] = result.score
    return approved, scores


def _run_source(conn, settings, source: Source, termos, flt, run_id: int, now: str) -> None:
    jobs = source.search(termos)
    if not jobs:
        raise SourceEmpty("A fonte não devolveu nenhuma vaga")
    local_filter = getattr(source, "local_filter", True)
    approved, scores = _approve(jobs, flt, settings) if local_filter else (jobs, {})
    unknown = db.filter_unknown(conn, approved)
    novas = 0

    def save(job: Job) -> None:
        """Grava a vaga assim que o detalhe dela é lido, para aparecer na lista antes de a fonte terminar."""
        nonlocal novas
        ok, pontos = _approve([job], flt, settings) if local_filter else ([job], {})
        novas += db.insert_new_jobs(conn, ok, pontos, run_id, now)

    source.enrich(unknown, on_job=save)
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
    """Roda cada fonte isolada: a falha de uma é registrada e a execução segue para a próxima.

    Em sequência por padrão; com `navegador.abas_paralelas` todas rodam ao mesmo tempo, uma aba por fonte."""
    conn = db.connect(settings.geral.db_path)
    try:
        termos, flt = _build_filter(conn, settings)
        if settings.navegador.abas_paralelas and len(sources) > 1:
            _run_sources_in_parallel(settings, run_id, sources, termos, flt, now)
        else:
            for source in sources:
                _run_isolated(conn, settings, source, termos, flt, run_id, now)
        conn.execute("UPDATE runs SET status='concluida', fim=? WHERE id=?", (now(), run_id))
        conn.commit()
        if manifest:
            _warn_scanners_to_redo(conn, settings, manifest, now())
    finally:
        conn.close()


def _run_isolated(conn, settings, source: Source, termos, flt, run_id: int, now) -> None:
    _update_source(conn, run_id, source.name, status="buscando")
    try:
        _run_source(conn, settings, source, termos, flt, run_id, now())
    except SourceError as error:
        log.warning("Fonte %s falhou: %s (%s)", source.name, error.motivo, error.detalhe)
        _update_source(conn, run_id, source.name, status="falha", motivo=error.motivo, detalhe=error.detalhe)
    except Exception as error:  # noqa: BLE001 - uma fonte nunca derruba as demais
        log.exception("Erro inesperado na fonte %s", source.name)
        _update_source(conn, run_id, source.name, status="falha", motivo="erro_interno", detalhe=str(error))


def _run_sources_in_parallel(settings, run_id: int, sources, termos, flt, now) -> None:
    """Uma thread, uma conexão de banco e uma aba por fonte; cada uma segue com as próprias pausas."""

    def work(source: Source) -> None:
        conn = db.connect(settings.geral.db_path)
        try:
            _run_isolated(conn, settings, source, termos, flt, run_id, now)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        list(pool.map(work, sources))


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
