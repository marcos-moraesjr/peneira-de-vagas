import sqlite3

from fastapi import APIRouter, Depends

from ..config import Settings
from ..deps import get_conn, get_now, get_settings
from ..schemas import JobOut, JobsCleared, JobsPage, MarkSeenIn, MarkSeenOut, SeenIn
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
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> dict:
    corte = jobs.cutoff_date(now(), max_dias)
    return jobs.list_jobs(conn, visto, fonte, q, limit or settings.api.jobs_page_size, offset, ordenar, direcao, corte)


@router.delete("/jobs", response_model=JobsCleared)
def clear_jobs(conn: sqlite3.Connection = Depends(get_conn)) -> JobsCleared:
    return JobsCleared(removidas=jobs.clear_all(conn))


@router.post("/jobs/mark-seen", response_model=MarkSeenOut)
def mark_seen(body: MarkSeenIn, conn: sqlite3.Connection = Depends(get_conn), now=Depends(get_now)) -> MarkSeenOut:
    return MarkSeenOut(atualizadas=jobs.mark_seen(conn, body.fonte, body.q, jobs.cutoff_date(now(), body.max_dias)))


@router.patch("/jobs/{job_id}", response_model=JobOut)
def set_seen(job_id: int, body: SeenIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return jobs.set_seen(conn, job_id, body.visto)
