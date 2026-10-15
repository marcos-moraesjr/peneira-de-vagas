import sqlite3
from dataclasses import replace
from fastapi import APIRouter, Depends, Request

from ..config import MODALIDADES, Settings
from ..deps import get_conn, get_now, get_settings
from ..errors import DomainError
from ..schemas import RunIn, RunOut, RunsCleared, RunStarted
from ..services import run_service, runs
from ..services.search_query import ESTADOS_BRASIL
from ..sources.registry import build_sources

router = APIRouter()


@router.post("/runs", response_model=RunStarted, status_code=202)
def start_run(
    request: Request,
    body: RunIn | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> RunStarted:
    run_settings = settings
    custom_search = bool(body and (body.localidade is not None or body.modalidade is not None or body.janela_dias is not None))
    if body and body.localidade is not None:
        localidade = body.localidade.strip()
        if localidade and localidade not in ESTADOS_BRASIL:
            raise DomainError(f"localidade={localidade!r}: esperado um estado brasileiro da lista oficial")
        run_settings = replace(run_settings, busca=replace(run_settings.busca, localidades=[localidade] if localidade else []))
    if body and body.modalidade is not None:
        modalidade = body.modalidade.strip()
        if modalidade and modalidade not in MODALIDADES:
            raise DomainError(f"modalidade={modalidade!r}: esperado um de {list(MODALIDADES)}")
        run_settings = replace(run_settings, busca=replace(run_settings.busca, modalidade=[modalidade] if modalidade else []))
    if body and body.janela_dias is not None:
        if body.janela_dias < 1:
            raise DomainError(f"janela_dias={body.janela_dias}: esperado um inteiro maior ou igual a 1")
        run_settings = replace(run_settings, busca=replace(run_settings.busca, janela_dias=body.janela_dias))
    sources = build_sources(run_settings, request.app.state.gate) if custom_search else request.app.state.sources_factory()
    fontes = body.fontes if body else None
    if fontes is not None:
        names = [source.name for source in sources]
        unknown = [fonte for fonte in fontes if fonte not in names]
        if not fontes or unknown:
            raise DomainError(f"fontes={unknown or fontes}: esperado ao menos uma entre {names}")
        sources = [source for source in sources if source.name in fontes]
    run_id = run_service.start_run(conn, run_settings, sources, now, request.app.state.spawn, request.app.state.manifest)
    return RunStarted(id=run_id)


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    limit: int | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    return runs.list_runs(conn, limit or settings.api.runs_history_limit)


@router.delete("/runs", response_model=RunsCleared)
def clear_runs(conn: sqlite3.Connection = Depends(get_conn)) -> RunsCleared:
    return RunsCleared(removidas=runs.clear_history(conn))


@router.delete("/runs/{run_id}", response_model=RunsCleared)
def delete_run(run_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> RunsCleared:
    return RunsCleared(removidas=runs.delete_run(conn, run_id))


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return runs.get_run(conn, run_id)
