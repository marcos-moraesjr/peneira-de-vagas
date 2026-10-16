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
from . import conjuntos, keywords, logs, scanners
from .filters import Filter, normalize
from .localizacao import passes_localidade, passes_modalidade
from .scanners import Manifest

log = logging.getLogger(__name__)

# Falha que encerra a sequência de conjuntos: bloqueio, login ou limitação de taxa (nunca contornados).
MOTIVOS_DE_BLOQUEIO = ("captcha", "login", "http_erro")


class Source(Protocol):
    name: str

    def search(self, termos: list[str]) -> list[Job]: ...

    def enrich(self, jobs: list[Job], on_job: Callable[[Job], None] | None = None) -> list[Job]: ...


def build_filter(conn: sqlite3.Connection, settings: Settings, conjunto_id: int | None = None) -> tuple[list[str], Filter]:
    """Termos enviados às fontes (só os `busca`, os primeiros `max_termos_busca`) e o filtro, que pontua com
    `busca` + `ranking` (um termo nos dois grupos conta uma vez). Palavras do conjunto pedido (padrão: o ativo)."""
    termos = [k["termo"] for k in keywords.list_all(conn, "busca", conjunto_id)]
    ranking = [k["termo"] for k in keywords.list_all(conn, "ranking", conjunto_id)]
    pontuam = list({normalize(termo): termo for termo in termos + ranking}.values())
    exclusoes = [k["termo"] for k in keywords.list_all(conn, "exclusao", conjunto_id)]
    f = settings.filtro
    return termos[: settings.busca.max_termos_busca], Filter(pontuam, exclusoes, f.peso_titulo, f.peso_descricao, f.min_score)


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


def _pre_approve(jobs: list[Job], flt: Filter, settings: Settings) -> list[Job]:
    """Triagem pela lista (título e trecho do card): só exclusões, localidade e modalidade. A pontuação fica para
    depois do detalhe, porque o card quase não traz texto e cortaria vagas cujas palavras só estão na descrição."""
    busca, aceitar = settings.busca, settings.filtro.aceitar_desconhecido
    return [
        job
        for job in jobs
        if not flt.excluded(job.titulo, job.trecho)
        and passes_localidade(job.localidade, job.modalidade, busca.localidades, aceitar)
        and passes_modalidade(job.modalidade, busca.modalidade, aceitar)
    ]


def _run_source(conn, settings, source: Source, termos, flt, conjunto_id: int, run_id: int, now: str) -> None:
    local_filter = getattr(source, "local_filter", True)
    lidas = 0
    aprovadas = 0
    novas = 0

    def save(job: Job) -> None:
        """Avalia a vaga com o detalhe (pontuação completa) e grava assim que ele é lido, para aparecer na lista antes de a fonte terminar."""
        nonlocal aprovadas, novas
        ok, pontos = _approve([job], flt, settings) if local_filter else ([job], {})
        aprovadas += len(ok)
        novas += db.insert_new_jobs(conn, ok, pontos, run_id, now, conjunto_id)

    def select_page(page: list[Job]) -> list[Job]:
        """Triagem e deduplicação da página antes de abrir os detalhes."""
        nonlocal aprovadas, lidas
        lidas += len(page)
        candidates = _pre_approve(page, flt, settings) if local_filter else page
        unknown = db.filter_unknown(conn, candidates, conjunto_id)
        aprovadas += len(candidates) - len(unknown)
        return unknown

    search_and_enrich = getattr(source, "search_and_enrich", None)
    try:
        if callable(search_and_enrich):
            jobs = search_and_enrich(termos, select_page, on_job=save)
        else:
            jobs = source.search(termos)
            if not jobs:
                raise SourceEmpty("A fonte não devolveu nenhuma vaga")
            candidates = _pre_approve(jobs, flt, settings) if local_filter else jobs
            unknown = db.filter_unknown(conn, candidates, conjunto_id)
            aprovadas = len(candidates) - len(unknown)
            source.enrich(unknown, on_job=save)
    except SourceError:
        # o que já foi lido e gravado antes da falha continua contado na linha da fonte
        _update_source(conn, run_id, source.name, lidas=lidas, aprovadas=aprovadas, novas=novas)
        raise
    if not jobs:
        raise SourceEmpty("A fonte não devolveu nenhuma vaga")
    _update_source(conn, run_id, source.name, status="ok", lidas=len(jobs), aprovadas=aprovadas, novas=novas)


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
    conjunto_id: int | None = None,
) -> None:
    """Roda cada fonte isolada: a falha de uma é registrada e a execução segue para a próxima.

    Em sequência por padrão; com `navegador.abas_paralelas` todas rodam ao mesmo tempo, uma aba por fonte."""
    conn = db.connect(settings.geral.db_path)
    try:
        with logs.registrar_execucao(settings.geral.log_dir, run_id):
            conjunto_id = conjunto_id or conjuntos.active_id(conn)  # as vagas vão para o conjunto cujas palavras foram lidas agora
            termos, flt = build_filter(conn, settings, conjunto_id)
            if settings.navegador.abas_paralelas and len(sources) > 1:
                _run_sources_in_parallel(settings, run_id, sources, termos, flt, conjunto_id, now)
            else:
                for source in sources:
                    _run_isolated(conn, settings, source, termos, flt, conjunto_id, run_id, now)
            conn.execute("UPDATE runs SET status='concluida', fim=? WHERE id=?", (now(), run_id))
            conn.commit()
            if manifest:
                _warn_scanners_to_redo(conn, settings, manifest, now())
    finally:
        conn.close()


def _run_isolated(conn, settings, source: Source, termos, flt, conjunto_id: int, run_id: int, now) -> None:
    _update_source(conn, run_id, source.name, status="buscando")
    try:
        _run_source(conn, settings, source, termos, flt, conjunto_id, run_id, now())
    except SourceError as error:
        log.warning("Fonte %s falhou: %s (%s)", source.name, error.motivo, error.detalhe)
        _update_source(conn, run_id, source.name, status="falha", motivo=error.motivo, detalhe=error.detalhe)
    except Exception as error:  # noqa: BLE001 - uma fonte nunca derruba as demais
        log.exception("Erro inesperado na fonte %s", source.name)
        _update_source(conn, run_id, source.name, status="falha", motivo="erro_interno", detalhe=str(error))


def _run_sources_in_parallel(settings, run_id: int, sources, termos, flt, conjunto_id: int, now) -> None:
    """Uma thread, uma conexão de banco e uma aba por fonte; cada uma segue com as próprias pausas."""

    def work(source: Source) -> None:
        conn = db.connect(settings.geral.db_path)
        try:
            _run_isolated(conn, settings, source, termos, flt, conjunto_id, run_id, now)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        list(pool.map(work, sources))


def spawn_thread(target: Callable[[], None]) -> None:
    threading.Thread(target=target, daemon=True).start()


def _blocked(conn: sqlite3.Connection, run_id: int) -> bool:
    marks = ",".join("?" * len(MOTIVOS_DE_BLOQUEIO))
    row = conn.execute(
        f"SELECT 1 FROM run_sources WHERE run_id=? AND status='falha' AND motivo IN ({marks})", (run_id, *MOTIVOS_DE_BLOQUEIO)
    ).fetchone()
    return row is not None


def execute_sequence(
    settings: Settings,
    run_id: int,
    conjunto_ids: list[int],
    sources: list[Source],
    now: Callable[[], str],
    manifest: Manifest | None = None,
) -> None:
    """Roda um conjunto por execução, na ordem pedida; cada um tem a própria linha no histórico."""
    conn = db.connect(settings.geral.db_path)
    try:
        for position, conjunto_id in enumerate(conjunto_ids):
            if position:
                run_id = db.create_run(
                    conn, [source.name for source in sources], now(), manifest.versions() if manifest else None,
                    conjuntos.name_of(conn, conjunto_id),
                )
            execute_run(settings, run_id, sources, now, manifest, conjunto_id)
            if _blocked(conn, run_id):
                log.warning("Sequência interrompida: fonte bloqueada no conjunto %s", conjuntos.name_of(conn, conjunto_id))
                return
    finally:
        conn.close()


def start_run(
    conn: sqlite3.Connection,
    settings: Settings,
    sources: list[Source],
    now: Callable[[], str],
    spawn: Callable[[Callable[[], None]], None] = spawn_thread,
    manifest: Manifest | None = None,
    conjunto_ids: list[int] | None = None,
) -> int:
    """Valida, abre a execução (uma por vez) e a dispara em segundo plano, gravando a versão de cada scanner.

    Com `conjunto_ids`, roda uma execução por conjunto, em sequência; devolve o id da primeira."""
    ids = conjunto_ids or [conjuntos.active_id(conn)]
    if len(set(ids)) != len(ids):
        raise DomainError("Conjunto repetido na sequência")
    for conjunto_id in ids:
        if not keywords.list_all(conn, "busca", conjunto_id):
            raise DomainError(f"Adicione ao menos uma palavra-chave para buscar no conjunto {conjuntos.name_of(conn, conjunto_id)!r}")
    versions = manifest.versions() if manifest else None
    run_id = db.create_run(conn, [source.name for source in sources], now(), versions, conjuntos.name_of(conn, ids[0]))
    spawn(lambda: execute_sequence(settings, run_id, ids, sources, now, manifest))
    return run_id
