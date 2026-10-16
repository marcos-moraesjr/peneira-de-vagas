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


def active_name(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT nome FROM conjuntos WHERE ativo=1").fetchone()["nome"]


def name_of(conn: sqlite3.Connection, conjunto_id: int) -> str:
    row = conn.execute("SELECT nome FROM conjuntos WHERE id=?", (conjunto_id,)).fetchone()
    if row is None:
        raise NotFound(f"Conjunto {conjunto_id} não existe")
    return row["nome"]


def get_sequence(conn: sqlite3.Connection) -> list[int]:
    return [row["conjunto_id"] for row in conn.execute("SELECT conjunto_id FROM sequencia_conjuntos ORDER BY posicao")]


def set_sequence(conn: sqlite3.Connection, conjunto_ids: list[int]) -> None:
    """Salva a ordem da sequência de buscas; valida tudo antes de gravar (lista vazia limpa a sequência)."""
    if len(set(conjunto_ids)) != len(conjunto_ids):
        raise DomainError("Conjunto repetido na sequência")
    for conjunto_id in conjunto_ids:
        name_of(conn, conjunto_id)
    conn.execute("DELETE FROM sequencia_conjuntos")
    conn.executemany(
        "INSERT INTO sequencia_conjuntos (posicao, conjunto_id) VALUES (?, ?)", list(enumerate(conjunto_ids))
    )
    conn.commit()


def _set_active(conn: sqlite3.Connection, conjunto_id: int) -> None:
    conn.execute("UPDATE conjuntos SET ativo=0 WHERE ativo=1")
    conn.execute("UPDATE conjuntos SET ativo=1 WHERE id=?", (conjunto_id,))


def _clean_name(settings: Settings, nome: str) -> tuple[str, str]:
    """Nome com espaços colapsados e sua forma normalizada; levanta `DomainError` se vazio ou longo demais."""
    nome = " ".join(nome.split())
    normalized = normalize(nome)
    if not normalized:
        raise DomainError("Informe um nome")
    limit = settings.busca.keyword_max_length
    if len(nome) > limit:
        raise DomainError(f"Valor inválido: nome={nome[:20]!r}... com {len(nome)} caracteres (esperado <= {limit})")
    return nome, normalized


def add(conn: sqlite3.Connection, settings: Settings, nome: str, now: str) -> dict:
    """Cria um conjunto vazio e o torna o ativo."""
    nome, normalized = _clean_name(settings, nome)
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


def duplicate(conn: sqlite3.Connection, settings: Settings, conjunto_id: int, nome: str, now: str) -> dict:
    """Cria um conjunto com o nome dado e todas as palavras do original (busca, ranking e exclusões); a cópia fica ativa."""
    if not conn.execute("SELECT 1 FROM conjuntos WHERE id=?", (conjunto_id,)).fetchone():
        raise NotFound(f"Conjunto inexistente: id={conjunto_id}")
    copia = add(conn, settings, nome, now)
    conn.execute(
        "INSERT INTO keywords (termo, termo_normalizado, tipo, criada_em, conjunto_id) "
        "SELECT termo, termo_normalizado, tipo, criada_em, ? FROM keywords WHERE conjunto_id=? ORDER BY id",
        (copia["id"], conjunto_id),
    )
    conn.commit()
    return copia


def rename(conn: sqlite3.Connection, settings: Settings, conjunto_id: int, nome: str) -> dict:
    """Troca o nome do conjunto, mantendo palavras e estado ativo; o nome não pode ser o de outro conjunto."""
    row = conn.execute("SELECT ativo FROM conjuntos WHERE id=?", (conjunto_id,)).fetchone()
    if not row:
        raise NotFound(f"Conjunto inexistente: id={conjunto_id}")
    nome, normalized = _clean_name(settings, nome)
    try:
        conn.execute("UPDATE conjuntos SET nome=?, nome_normalizado=? WHERE id=?", (nome, normalized, conjunto_id))
    except sqlite3.IntegrityError:
        conn.rollback()
        raise DomainError(f"Esse conjunto já existe: {nome!r}") from None
    conn.commit()
    return {"id": conjunto_id, "nome": nome, "ativo": bool(row["ativo"])}


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
