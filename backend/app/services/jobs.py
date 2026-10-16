"""Consulta e marcação de vagas."""
import sqlite3
from datetime import date, timedelta

from ..errors import DomainError, NotFound
from . import conjuntos, runs
from .filters import normalize
from .localizacao import UF_NOMES, split_localidade
from .run_service import build_filter


def cutoff_date(now: str, max_dias: int | None) -> str | None:
    """Data (AAAA-MM-DD) a partir da qual uma vaga ainda vale; `None` = sem filtro de idade."""
    if max_dias is None:
        return None
    if max_dias < 1:
        raise DomainError(f"max_dias={max_dias}: esperado um inteiro maior ou igual a 1")
    return (date.fromisoformat(now[:10]) - timedelta(days=max_dias)).isoformat()


def resolve_conjunto(conn: sqlite3.Connection, conjunto_id: int | None) -> int:
    """Conjunto pedido (precisa existir) ou, sem pedido, o ativo."""
    if conjunto_id is None:
        return conjuntos.active_id(conn)
    if not conn.execute("SELECT 1 FROM conjuntos WHERE id=?", (conjunto_id,)).fetchone():
        raise NotFound(f"Conjunto inexistente: id={conjunto_id}")
    return conjunto_id


def _where(
    conjunto_id: int | None, visto: bool | None, fonte: str | None, q: str | None, corte: str | None = None,
    local: str | None = None, modalidade: str | None = None, excluidas: bool = False, candidatadas: bool = False,
    min_pontos: int | None = None,
) -> tuple[str, list]:
    if modalidade and modalidade not in MODALIDADES:
        raise DomainError(f"modalidade={modalidade!r}: esperado um de {list(MODALIDADES)}")
    if min_pontos is not None and min_pontos < 0:
        raise DomainError(f"min_pontos={min_pontos}: esperado um inteiro maior ou igual a 0")
    clauses, params = ([], []) if conjunto_id is None else (["conjunto_id=?"], [conjunto_id])  # None: todos os conjuntos
    clauses.append("excluida=?")  # a lista comum esconde as excluídas; `excluidas` mostra só elas
    params.append(int(excluidas))
    clauses.append("candidatada=?")  # idem para as candidaturas (categoria própria)
    params.append(int(candidatadas))
    if visto is not None:
        clauses.append("visto=?")
        params.append(int(visto))
    if fonte:
        clauses.append("fonte=?")
        params.append(fonte)
    if q and normalize(q):
        clauses.append("(norm(titulo) LIKE ? OR norm(empresa) LIKE ?)")
        params += [f"%{normalize(q)}%"] * 2
    if local and normalize(local):
        termo = normalize(local)
        uf = next((sigla for sigla, nome in UF_NOMES.items() if nome == termo), None)  # "Pernambuco" casa a UF PE
        clauses.append("(cidade_de(localidade) LIKE ? OR lower(estado_de(localidade)) LIKE ? OR modalidade LIKE ?)")
        params += [f"%{termo}%", f"%{uf or termo}%", f"%{termo}%"]
    if modalidade:
        clauses.append("modalidade=?")
        params.append(modalidade)
    if min_pontos:
        clauses.append("pontos>=?")
        params.append(min_pontos)
    if corte:  # vaga sem data de publicação (LinkedIn/Indeed) nunca é descartada por idade
        clauses.append("(publicada_em IS NULL OR substr(publicada_em, 1, 10) >= ?)")
        params.append(corte)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _to_dict(row: sqlite3.Row) -> dict:
    cidade, estado = split_localidade(row["localidade"])
    return {**dict(row), "cidade": cidade, "estado": estado, "visto": bool(row["visto"]), "excluida": bool(row["excluida"]), "candidatada": bool(row["candidatada"])}


MODALIDADES = ("remoto", "hibrido", "presencial")
DEFAULT_ORDER = "run_id DESC, pontos DESC, id DESC"
# coluna ordenável → expressão SQL (texto compara sem acento nem maiúscula)
SORT_COLUMNS = {
    "titulo": "norm(titulo)",
    "empresa": "norm(empresa)",
    "localidade": "norm(localidade)",
    "cidade": "cidade_de(localidade)",
    "estado": "estado_de(localidade)",
    "modalidade": "modalidade",
    "palavra_chave": "norm(palavra_chave)",
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
    local: str | None = None, modalidade: str | None = None,
    conjunto_id: int | None = None, todos_conjuntos: bool = False, excluidas: bool = False, candidatadas: bool = False,
    min_pontos: int | None = None,
) -> dict:
    """Vagas do conjunto pedido (padrão: o ativo); `todos_conjuntos` tira o filtro de conjunto."""
    order = "candidatada_em DESC, id DESC" if candidatadas and ordenar is None else _order_by(ordenar, direcao)  # candidaturas: a mais recente primeiro
    where, params = _where(None if todos_conjuntos else resolve_conjunto(conn, conjunto_id), visto, fonte, q, corte, local, modalidade, excluidas, candidatadas, min_pontos)
    total = conn.execute(f"SELECT COUNT(*) FROM jobs{where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM jobs{where} ORDER BY {order} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {"items": [_to_dict(row) for row in rows], "total": total}


def update_job(conn, job_id: int, visto: bool | None, excluida: bool | None, candidatada: bool | None = None, agora: str | None = None) -> dict:
    """Muda `visto`, `excluida` e/ou `candidatada` (lógico: a vaga fica no banco e a deduplicação a reconhece).
    Marcar uma de `excluida`/`candidatada` desmarca a outra: a vaga está numa categoria só."""
    campos = {"visto": visto, "excluida": excluida, "candidatada": candidatada}
    campos = {nome: int(valor) for nome, valor in campos.items() if valor is not None}
    if not campos:
        raise DomainError("Informe visto, excluida e/ou candidatada")
    if campos.get("excluida") and "candidatada" not in campos:
        campos["candidatada"] = 0
    if campos.get("candidatada") and "excluida" not in campos:
        campos["excluida"] = 0
    if "candidatada" in campos:  # a data registra quando a candidatura foi marcada; desfazer a limpa
        campos["candidatada_em"] = agora if campos["candidatada"] else None
    atribuicoes = ", ".join(f"{nome}=?" for nome in campos)
    cursor = conn.execute(f"UPDATE jobs SET {atribuicoes} WHERE id=?", [*campos.values(), job_id])
    conn.commit()
    if cursor.rowcount == 0:
        raise NotFound(f"Vaga inexistente: id={job_id}")
    return _to_dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def clear_all(conn, conjunto_id: int | None = None) -> int:
    """Apaga as vagas (vistas e novas) do conjunto pedido (padrão: o ativo); recusa durante uma execução. Voltam como novas se reaparecerem."""
    runs.ensure_idle(conn)
    removidas = conn.execute("DELETE FROM jobs WHERE conjunto_id=?", (resolve_conjunto(conn, conjunto_id),)).rowcount
    conn.commit()
    return removidas


def mark_seen(
    conn, fonte: str | None, q: str | None, corte: str | None = None,
    local: str | None = None, modalidade: str | None = None,
    conjunto_id: int | None = None, todos_conjuntos: bool = False, min_pontos: int | None = None,
) -> int:
    """Marca como vistas as ainda não vistas do conjunto pedido (padrão: o ativo; `todos_conjuntos`: de todos) que casam com os filtros."""
    where, params = _where(None if todos_conjuntos else resolve_conjunto(conn, conjunto_id), False, fonte, q, corte, local, modalidade, min_pontos=min_pontos)
    cursor = conn.execute(f"UPDATE jobs SET visto=1{where}", params)
    conn.commit()
    return cursor.rowcount


def recalcular_pontuacao(conn, settings) -> dict:
    """Reescreve `pontos` das vagas de todos os conjuntos, cada um com as palavras (busca + ranking + exclusões) do próprio
    conjunto e os pesos atuais, sobre o título e o trecho gravados. Só muda a pontuação: nenhuma vaga é apagada nem
    reprovada; recusa durante uma execução."""
    runs.ensure_idle(conn)
    mudaram, total = [], 0
    for conjunto in conn.execute("SELECT id FROM conjuntos").fetchall():
        _, flt = build_filter(conn, settings, conjunto["id"])
        rows = conn.execute("SELECT id, titulo, trecho, pontos FROM jobs WHERE conjunto_id=?", (conjunto["id"],)).fetchall()
        total += len(rows)
        for row in rows:
            novo = flt.evaluate(row["titulo"], row["trecho"]).score
            if novo != row["pontos"]:
                mudaram.append((novo, row["id"]))
    conn.executemany("UPDATE jobs SET pontos=? WHERE id=?", mudaram)
    conn.commit()
    return {"atualizadas": len(mudaram), "total": total}
