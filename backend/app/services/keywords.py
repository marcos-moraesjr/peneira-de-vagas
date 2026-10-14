"""Palavras-chave e exclusões editáveis pelo front, guardadas no SQLite."""
import sqlite3

from ..config import Settings
from ..errors import DomainError, NotFound
from .filters import normalize

TIPOS = ("busca", "exclusao")


def _check_type(tipo: str) -> None:
    if tipo not in TIPOS:
        raise DomainError(f"Valor inválido: tipo={tipo!r} (esperado {TIPOS})")


def list_all(conn: sqlite3.Connection, tipo: str | None = None) -> list[dict]:
    sql = "SELECT id, termo, tipo, criada_em FROM keywords"
    params: tuple = ()
    if tipo is not None:
        _check_type(tipo)
        sql += " WHERE tipo=?"
        params = (tipo,)
    return [dict(row) for row in conn.execute(sql + " ORDER BY id", params)]


def add(conn: sqlite3.Connection, settings: Settings, termo: str, tipo: str, now: str) -> dict:
    _check_type(tipo)
    termo = " ".join(termo.split())
    normalized = normalize(termo)
    if not normalized:
        raise DomainError("Informe um termo")
    limit = settings.busca.keyword_max_length
    if len(termo) > limit:
        raise DomainError(f"Valor inválido: termo={termo[:20]!r}... com {len(termo)} caracteres (esperado <= {limit})")
    try:
        cursor = conn.execute(
            "INSERT INTO keywords (termo, termo_normalizado, tipo, criada_em) VALUES (?,?,?,?)",
            (termo, normalized, tipo, now),
        )
    except sqlite3.IntegrityError:
        raise DomainError(f"Esse termo já existe: {termo!r}") from None
    conn.commit()
    return {"id": cursor.lastrowid, "termo": termo, "tipo": tipo, "criada_em": now}


def remove(conn: sqlite3.Connection, keyword_id: int) -> None:
    cursor = conn.execute("DELETE FROM keywords WHERE id=?", (keyword_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise NotFound(f"Palavra-chave inexistente: id={keyword_id}")
