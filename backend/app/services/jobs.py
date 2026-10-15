"""Consulta e marcação de vagas."""
import sqlite3
from datetime import date, timedelta

from ..errors import DomainError, NotFound
from . import runs
from .filters import normalize


def cutoff_date(now: str, max_dias: int | None) -> str | None:
    """Data (AAAA-MM-DD) a partir da qual uma vaga ainda vale; `None` = sem filtro de idade."""
    if max_dias is None:
        return None
    if max_dias < 1:
        raise DomainError(f"max_dias={max_dias}: esperado um inteiro maior ou igual a 1")
    return (date.fromisoformat(now[:10]) - timedelta(days=max_dias)).isoformat()


def _where(visto: bool | None, fonte: str | None, q: str | None, corte: str | None = None) -> tuple[str, list]:
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
    if corte:  # vaga sem data de publicação (LinkedIn/Indeed/Google) nunca é descartada por idade
        clauses.append("(publicada_em IS NULL OR substr(publicada_em, 1, 10) >= ?)")
        params.append(corte)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _to_dict(row: sqlite3.Row) -> dict:
    return {**dict(row), "visto": bool(row["visto"])}


DEFAULT_ORDER = "run_id DESC, pontos DESC, id DESC"
# coluna ordenável → expressão SQL (texto compara sem acento nem maiúscula)
SORT_COLUMNS = {
    "titulo": "norm(titulo)",
    "empresa": "norm(empresa)",
    "localidade": "norm(localidade)",
    "publicada_em": "publicada_em",
    "encontrada_em": "encontrada_em",
    "fonte": "fonte",
    "pontos": "pontos",
}
DIRECTIONS = ("asc", "desc")


def _order_by(ordenar: str | None, direcao: str | None) -> str:
    if direcao is not None and direcao not in DIRECTIONS:
        raise DomainError(f"direcao={direcao!r}: esperado um de {list(DIRECTIONS)}")
    if ordenar is None:
        return DEFAULT_ORDER
    if ordenar not in SORT_COLUMNS:
        raise DomainError(f"ordenar={ordenar!r}: esperado um de {list(SORT_COLUMNS)}")
    # vagas sem data de publicação ficam no fim nas duas direções
    nulls_last = "publicada_em IS NULL, " if ordenar == "publicada_em" else ""
    return f"{nulls_last}{SORT_COLUMNS[ordenar]} {(direcao or 'asc').upper()}, id DESC"


def list_jobs(
    conn, visto: bool | None, fonte: str | None, q: str | None, limit: int, offset: int,
    ordenar: str | None = None, direcao: str | None = None, corte: str | None = None,
) -> dict:
    order = _order_by(ordenar, direcao)
    where, params = _where(visto, fonte, q, corte)
    total = conn.execute(f"SELECT COUNT(*) FROM jobs{where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM jobs{where} ORDER BY {order} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [_to_dict(row) for row in rows], "total": total}


def set_seen(conn, job_id: int, visto: bool) -> dict:
    cursor = conn.execute("UPDATE jobs SET visto=? WHERE id=?", (int(visto), job_id))
    conn.commit()
    if cursor.rowcount == 0:
        raise NotFound(f"Vaga inexistente: id={job_id}")
    return _to_dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def clear_all(conn) -> int:
    """Apaga todas as vagas (vistas e novas); recusa durante uma execução. Voltam como novas se reaparecerem."""
    runs.ensure_idle(conn)
    removidas = conn.execute("DELETE FROM jobs").rowcount
    conn.commit()
    return removidas


def mark_seen(conn, fonte: str | None, q: str | None, corte: str | None = None) -> int:
    """Marca como vistas as ainda não vistas que casam com os filtros."""
    where, params = _where(False, fonte, q, corte)
    cursor = conn.execute(f"UPDATE jobs SET visto=1{where}", params)
    conn.commit()
    return cursor.rowcount
