"""Conjuntos de palavras-chave: cada um guarda suas buscas e exclusões; só um fica ativo por vez."""
import sqlite3

from ..config import Settings
from ..errors import DomainError, NotFound
from .filters import normalize


def _row(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "nome": row["nome"], "ativo": bool(row["ativo"])}


def list_all(conn: sqlite3.Connection) -> list[dict]:
    return [_row(row) for row in conn.execute("SELECT id, nome, ativo FROM conjuntos ORDER BY id")]


def active_id(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT id FROM conjuntos WHERE ativo=1").fetchone()["id"]


def _set_active(conn: sqlite3.Connection, conjunto_id: int) -> None:
    conn.execute("UPDATE conjuntos SET ativo=0 WHERE ativo=1")
    conn.execute("UPDATE conjuntos SET ativo=1 WHERE id=?", (conjunto_id,))


def add(conn: sqlite3.Connection, settings: Settings, nome: str, now: str) -> dict:
    """Cria um conjunto vazio e o torna o ativo."""
    nome = " ".join(nome.split())
    normalized = normalize(nome)
    if not normalized:
        raise DomainError("Informe um nome")
    limit = settings.busca.keyword_max_length
    if len(nome) > limit:
        raise DomainError(f"Valor inválido: nome={nome[:20]!r}... com {len(nome)} caracteres (esperado <= {limit})")
    try:
        conn.execute("UPDATE conjuntos SET ativo=0 WHERE ativo=1")
        cursor = conn.execute(
            "INSERT INTO conjuntos (nome, nome_normalizado, ativo, criada_em) VALUES (?,?,1,?)", (nome, normalized, now)
        )
    except sqlite3.IntegrityError:
        conn.rollback()
        raise DomainError(f"Esse conjunto já existe: {nome!r}") from None
    conn.commit()
    return {"id": cursor.lastrowid, "nome": nome, "ativo": True}


def activate(conn: sqlite3.Connection, conjunto_id: int) -> None:
    if not conn.execute("SELECT 1 FROM conjuntos WHERE id=?", (conjunto_id,)).fetchone():
        raise NotFound(f"Conjunto inexistente: id={conjunto_id}")
    _set_active(conn, conjunto_id)
    conn.commit()


def remove(conn: sqlite3.Connection, conjunto_id: int) -> None:
    """Apaga o conjunto e suas palavras; se era o ativo, ativa o primeiro que sobrar. O último não sai."""
    row = conn.execute("SELECT ativo FROM conjuntos WHERE id=?", (conjunto_id,)).fetchone()
    if not row:
        raise NotFound(f"Conjunto inexistente: id={conjunto_id}")
    if conn.execute("SELECT COUNT(*) FROM conjuntos").fetchone()[0] == 1:
        raise DomainError("Mantenha ao menos um conjunto")
    conn.execute("DELETE FROM conjuntos WHERE id=?", (conjunto_id,))
    if row["ativo"]:
        _set_active(conn, conn.execute("SELECT MIN(id) FROM conjuntos").fetchone()[0])
    conn.commit()
