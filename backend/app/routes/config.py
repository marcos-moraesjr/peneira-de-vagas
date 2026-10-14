import sqlite3
from dataclasses import asdict

from fastapi import APIRouter, Depends, Request

from ..config import Settings
from ..deps import get_conn, get_settings
from ..schemas import ConfigOut
from ..services import config_edit, runs

router = APIRouter()
EDITABLE = ("busca", "filtro", "limites", "ritmo", "api")


@router.get("/config", response_model=ConfigOut)
def get_config(settings: Settings = Depends(get_settings)) -> dict:
    """Parâmetros de comportamento em vigor; caminhos, cdp_url e URLs das fontes ficam de fora."""
    return {name: asdict(getattr(settings, name)) for name in EDITABLE}


@router.put("/config", response_model=ConfigOut)
def put_config(
    body: ConfigOut,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Valida, grava no config.toml e passa a valer na hora; recusa durante uma execução."""
    runs.ensure_idle(conn)
    values = body.model_dump()
    request.app.state.settings = config_edit.update_config(settings, request.app.state.config_path, values)
    return values
