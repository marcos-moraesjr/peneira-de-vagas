import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Request

from ..config import Settings
from ..deps import get_conn, get_now, get_settings
from ..schemas import ScannerOut
from ..services import scanners

router = APIRouter()


@router.get("/scanners", response_model=list[ScannerOut])
def list_scanners(
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> list[dict]:
    """Versão e estado de cada scanner; 'refazer' traz a instrução pronta para o Claude."""
    return scanners.evaluate(conn, settings, request.app.state.manifest, date.fromisoformat(now()[:10]))
