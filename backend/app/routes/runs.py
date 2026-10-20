import sqlite3
from dataclasses import replace
from fastapi import APIRouter, Depends, Request

from ..config import MODALIDADES, Settings
from ..deps import get_conn, get_now, get_settings
from ..errors import DomainError
from ..schemas import RunIn, RunOut, RunsCleared, RunStarted
from ..services import logs, run_service, runs
from ..services.search_query import ESTADOS_BRASIL
from ..sources.registry import build_sources

router = APIRouter()


def _com_parametros(settings: Settings, localidade: str | None, modalidade: str | None, janela_dias: int | None) -> Settings:
    """Valida e aplica os parâmetros da busca sobre a config (`None` = valor da config)."""
    if localidade is not None:
        localidade = localidade.strip()
        if localidade and localidade not in ESTADOS_BRASIL:
            raise DomainError(f"localidade={localidade!r}: esperado um estado brasileiro da lista oficial")
        settings = replace(settings, busca=replace(settings.busca, localidades=[localidade] if localidade else []))
    if modalidade is not None:
        modalidade = modalidade.strip()
        if modalidade and modalidade not in MODALIDADES:
            raise DomainError(f"modalidade={modalidade!r}: esperado um de {list(MODALIDADES)}")
        settings = replace(settings, busca=replace(settings.busca, modalidade=[modalidade] if modalidade else []))
    if janela_dias is not None:
        if janela_dias < 1:
            raise DomainError(f"janela_dias={janela_dias}: esperado um inteiro maior ou igual a 1")
        settings = replace(settings, busca=replace(settings.busca, janela_dias=janela_dias))
    return settings


def _fontes_pedidas(sources: list, fontes: list[str] | None) -> list:
    if fontes is None:
        return sources
    names = [source.name for source in sources]
    unknown = [fonte for fonte in fontes if fonte not in names]
    if not fontes or unknown:
        raise DomainError(f"fontes={unknown or fontes}: esperado ao menos uma entre {names}")
    return [source for source in sources if source.name in fontes]


@router.post("/runs", response_model=RunStarted, status_code=202)
def start_run(
    request: Request,
    body: RunIn | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> RunStarted:
    if body and body.retomar_run_id is not None:
        return _resume_run(request, body, conn, settings, now)
    parametros = {
        "localidade": body.localidade.strip() if body and body.localidade is not None else None,
        "modalidade": body.modalidade.strip() if body and body.modalidade is not None else None,
        "janela_dias": body.janela_dias if body else None,
    }
    run_settings = _com_parametros(settings, **parametros)
    custom_search = any(value is not None for value in parametros.values())
    sources = build_sources(run_settings, request.app.state.gate) if custom_search else request.app.state.sources_factory()
    sources = _fontes_pedidas(sources, body.fontes if body else None)
    run_id = run_service.start_run(
        conn, run_settings, sources, now, request.app.state.spawn, request.app.state.manifest,
        body.conjunto_ids if body else None, parametros,
    )
    return RunStarted(id=run_id)


def _resume_run(request: Request, body: RunIn, conn: sqlite3.Connection, settings: Settings, now) -> RunStarted:
    """Retoma a execução que falhou com os parâmetros gravados nela (a barra de busca pode ter mudado desde então)."""
    saved = runs.get_run(conn, body.retomar_run_id)
    run_settings = _com_parametros(settings, saved["localidade"], saved["modalidade"], saved["janela_dias"])
    custom_search = any(saved[key] is not None for key in ("localidade", "modalidade", "janela_dias"))
    sources = build_sources(run_settings, request.app.state.gate) if custom_search else request.app.state.sources_factory()
    sources = _fontes_pedidas(sources, body.fontes)
    run_id = run_service.resume_run(
        conn, run_settings, sources, now, body.retomar_run_id, request.app.state.spawn, request.app.state.manifest
    )
    return RunStarted(id=run_id)


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    limit: int | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    return runs.list_runs(conn, limit or settings.api.runs_history_limit)


@router.delete("/runs", response_model=RunsCleared)
def clear_runs(conn: sqlite3.Connection = Depends(get_conn), settings: Settings = Depends(get_settings)) -> RunsCleared:
    removidas = runs.clear_history(conn)
    logs.remover_execucoes(settings.geral.log_dir)
    return RunsCleared(removidas=removidas)


@router.delete("/runs/{run_id}", response_model=RunsCleared)
def delete_run(run_id: int, conn: sqlite3.Connection = Depends(get_conn), settings: Settings = Depends(get_settings)) -> RunsCleared:
    removidas = runs.delete_run(conn, run_id)
    logs.remover_execucao(settings.geral.log_dir, run_id)
    return RunsCleared(removidas=removidas)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return runs.get_run(conn, run_id)
