import sqlite3

from fastapi import APIRouter, Depends

from ..config import Settings
from ..deps import get_conn, get_settings
from ..schemas import JobOut, JobsPage, MarkSeenIn, MarkSeenOut, SeenIn
from ..services import jobs

router = APIRouter()


@router.get("/jobs", response_model=JobsPage)
def list_jobs(
    visto: bool | None = None,
    fonte: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> dict:
    return jobs.list_jobs(conn, visto, fonte, q, limit or settings.api.jobs_page_size, offset)


@router.post("/jobs/mark-seen", response_model=MarkSeenOut)
def mark_seen(body: MarkSeenIn, conn: sqlite3.Connection = Depends(get_conn)) -> MarkSeenOut:
    return MarkSeenOut(atualizadas=jobs.mark_seen(conn, body.fonte, body.q))


@router.patch("/jobs/{job_id}", response_model=JobOut)
def set_seen(job_id: int, body: SeenIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return jobs.set_seen(conn, job_id, body.visto)
