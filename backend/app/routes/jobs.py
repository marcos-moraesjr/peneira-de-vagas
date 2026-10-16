import sqlite3

from fastapi import APIRouter, Depends

from ..config import Settings
from ..deps import get_conn, get_now, get_settings
from ..schemas import JobOut, JobsCleared, JobsPage, MarkSeenIn, MarkSeenOut, RecalcularOut, SeenIn
from ..services import jobs

router = APIRouter()


@router.get("/jobs", response_model=JobsPage)
def list_jobs(
    visto: bool | None = None,
    fonte: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    ordenar: str | None = None,
    direcao: str | None = None,
    max_dias: int | None = None,
    local: str | None = None,
    modalidade: str | None = None,
    conjunto_id: int | None = None,
    todos_conjuntos: bool = False,
    excluidas: bool = False,
    candidatadas: bool = False,
    min_pontos: int | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> dict:
    corte = jobs.cutoff_date(now(), max_dias)
    return jobs.list_jobs(
        conn, visto, fonte, q, limit or settings.api.jobs_page_size, offset, ordenar, direcao, corte, local, modalidade, conjunto_id, todos_conjuntos, excluidas, candidatadas, min_pontos
    )


@router.delete("/jobs", response_model=JobsCleared)
def clear_jobs(conjunto_id: int | None = None, conn: sqlite3.Connection = Depends(get_conn)) -> JobsCleared:
    return JobsCleared(removidas=jobs.clear_all(conn, conjunto_id))


@router.post("/jobs/mark-seen", response_model=MarkSeenOut)
def mark_seen(body: MarkSeenIn, conn: sqlite3.Connection = Depends(get_conn), now=Depends(get_now)) -> MarkSeenOut:
    return MarkSeenOut(
        atualizadas=jobs.mark_seen(conn, body.fonte, body.q, jobs.cutoff_date(now(), body.max_dias), body.local, body.modalidade, body.conjunto_id, body.todos_conjuntos, body.min_pontos)
    )


@router.post("/jobs/recalcular", response_model=RecalcularOut)
def recalcular(conn: sqlite3.Connection = Depends(get_conn), settings: Settings = Depends(get_settings)) -> dict:
    return jobs.recalcular_pontuacao(conn, settings)


@router.patch("/jobs/{job_id}", response_model=JobOut)
def set_seen(job_id: int, body: SeenIn, conn: sqlite3.Connection = Depends(get_conn), now=Depends(get_now)) -> dict:
    return jobs.update_job(conn, job_id, body.visto, body.excluida, body.candidatada, now())
