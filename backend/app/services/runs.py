"""Consulta de execuções e seus resultados por fonte."""
import sqlite3

from ..errors import Conflict, NotFound


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


def ensure_idle(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM runs WHERE status='executando'").fetchone():
        raise Conflict("Há uma execução em andamento")


def ensure_running(conn: sqlite3.Connection, run_id: int) -> None:
    """404 se a execução não existe; 409 se já terminou (não há o que interromper)."""
    if get_run(conn, run_id)["status"] != "executando":
        raise Conflict("A execução já terminou")


def clear_history(conn: sqlite3.Connection) -> int:
    """Apaga todas as execuções e seus resultados por fonte; as vagas ficam, sem execução de origem (`run_id` nulo)."""
    ensure_idle(conn)
    conn.execute("DELETE FROM run_sources")
    removidas = conn.execute("DELETE FROM runs").rowcount
    conn.commit()
    return removidas


def list_runs(conn: sqlite3.Connection, limit: int) -> list[dict]:
    rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_with_sources(conn, row) for row in rows]
