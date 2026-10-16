"""Palavras-chave e exclusões editáveis pelo front, guardadas no SQLite, sempre no conjunto ativo."""
import sqlite3

from ..config import Settings
from ..errors import DomainError, NotFound
from . import conjuntos
from .filters import normalize

TIPOS = ("busca", "ranking", "exclusao")


def _check_type(tipo: str) -> None:
    if tipo not in TIPOS:
        raise DomainError(f"Valor inválido: tipo={tipo!r} (esperado {TIPOS})")


def list_all(conn: sqlite3.Connection, tipo: str | None = None, conjunto_id: int | None = None) -> list[dict]:
    """Palavras do conjunto pedido (padrão: o ativo)."""
    sql = "SELECT id, termo, tipo, criada_em FROM keywords WHERE conjunto_id=?"
    params: tuple = (conjuntos.active_id(conn) if conjunto_id is None else conjunto_id,)
    if tipo is not None:
        _check_type(tipo)
        sql += " AND tipo=?"
        params += (tipo,)
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
    if tipo == "busca":
        max_terms = settings.busca.max_termos_busca
        count = conn.execute(
            "SELECT COUNT(*) FROM keywords WHERE conjunto_id=? AND tipo='busca'", (conjuntos.active_id(conn),)
        ).fetchone()[0]
        if count >= max_terms:
            raise DomainError(f"Valor inválido: {count + 1} palavras-chave de busca no conjunto (esperado <= {max_terms})")
    try:
        cursor = conn.execute(
            "INSERT INTO keywords (termo, termo_normalizado, tipo, criada_em, conjunto_id) VALUES (?,?,?,?,?)",
            (termo, normalized, tipo, now, conjuntos.active_id(conn)),
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
