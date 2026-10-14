import sqlite3

from fastapi import APIRouter, Depends

from ..deps import get_conn
from ..schemas import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(conn: sqlite3.Connection = Depends(get_conn)) -> HealthOut:
    conn.execute("SELECT 1")
    return HealthOut(status="ok", db="ok")
