import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, Request

from ..config import Settings
from ..deps import get_conn, get_now, get_settings
from ..schemas import InstructionOut, ScannerOut
from ..services import keywords, scanners

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


@router.get("/scanners/instrucao", response_model=InstructionOut)
def documentation_instruction(
    request: Request,
    fonte: str | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
) -> InstructionOut:
    """Instrução pronta para o Claude Code refazer a documentação das plataformas (uma ou todas)."""
    terms = [item["termo"] for item in keywords.list_all(conn, "busca")]
    return InstructionOut(instrucao=scanners.documentation_instruction(request.app.state.manifest, fonte, terms))
