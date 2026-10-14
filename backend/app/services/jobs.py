"""Consulta e marcação de vagas."""
import sqlite3

from ..errors import NotFound
from .filters import normalize


def _where(visto: bool | None, fonte: str | None, q: str | None) -> tuple[str, list]:
    clauses, params = [], []
    if visto is not None:
        clauses.append("visto=?")
        params.append(int(visto))
    if fonte:
        clauses.append("fonte=?")
        params.append(fonte)
    if q and normalize(q):
        clauses.append("(norm(titulo) LIKE ? OR norm(empresa) LIKE ?)")
        params += [f"%{normalize(q)}%"] * 2
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _to_dict(row: sqlite3.Row) -> dict:
    return {**dict(row), "visto": bool(row["visto"])}


def list_jobs(conn, visto: bool | None, fonte: str | None, q: str | None, limit: int, offset: int) -> dict:
    where, params = _where(visto, fonte, q)
    total = conn.execute(f"SELECT COUNT(*) FROM jobs{where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM jobs{where} ORDER BY run_id DESC, pontos DESC, id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [_to_dict(row) for row in rows], "total": total}


def set_seen(conn, job_id: int, visto: bool) -> dict:
    cursor = conn.execute("UPDATE jobs SET visto=? WHERE id=?", (int(visto), job_id))
    conn.commit()
    if cursor.rowcount == 0:
        raise NotFound(f"Vaga inexistente: id={job_id}")
    return _to_dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def mark_seen(conn, fonte: str | None, q: str | None) -> int:
    """Marca como vistas as ainda não vistas que casam com os filtros."""
    where, params = _where(False, fonte, q)
    cursor = conn.execute(f"UPDATE jobs SET visto=1{where}", params)
    conn.commit()
    return cursor.rowcount
