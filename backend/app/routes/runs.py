import sqlite3

from fastapi import APIRouter, Depends, Request

from ..config import Settings
from ..deps import get_conn, get_now, get_settings
from ..schemas import RunOut, RunStarted
from ..services import run_service, runs

router = APIRouter()


@router.post("/runs", response_model=RunStarted, status_code=202)
def start_run(
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> RunStarted:
    sources = request.app.state.sources_factory()
    run_id = run_service.start_run(conn, settings, sources, now, request.app.state.spawn, request.app.state.manifest)
    return RunStarted(id=run_id)


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    limit: int | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    return runs.list_runs(conn, limit or settings.api.runs_history_limit)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return runs.get_run(conn, run_id)
