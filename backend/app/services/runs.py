"""Consulta de execuções e seus resultados por fonte."""
import sqlite3

from ..errors import NotFound


def _with_sources(conn: sqlite3.Connection, run: sqlite3.Row) -> dict:
    fontes = conn.execute(
        "SELECT fonte, status, motivo, detalhe, lidas, aprovadas, novas, scanner_versao FROM run_sources WHERE run_id=? ORDER BY rowid",
        (run["id"],),
    ).fetchall()
    return {**dict(run), "fontes": [dict(f) for f in fontes]}


def get_run(conn: sqlite3.Connection, run_id: int) -> dict:
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if run is None:
        raise NotFound(f"Execução inexistente: id={run_id}")
    return _with_sources(conn, run)


def list_runs(conn: sqlite3.Connection, limit: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_with_sources(conn, row) for row in rows]
