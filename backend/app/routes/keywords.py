import sqlite3

from fastapi import APIRouter, Depends, Response

from ..config import Settings
from ..deps import get_conn, get_now, get_settings
from ..schemas import KeywordIn, KeywordOut
from ..services import keywords

router = APIRouter()


@router.get("/keywords", response_model=list[KeywordOut])
def list_keywords(tipo: str | None = None, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return keywords.list_all(conn, tipo)


@router.post("/keywords", response_model=KeywordOut, status_code=201)
def add_keyword(
    body: KeywordIn,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> dict:
    return keywords.add(conn, settings, body.termo, body.tipo, now())


@router.delete("/keywords/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    keywords.remove(conn, keyword_id)
    return Response(status_code=204)
