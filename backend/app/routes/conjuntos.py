import sqlite3

from fastapi import APIRouter, Depends, Response

from ..config import Settings
from ..deps import get_conn, get_now, get_settings
from ..schemas import ConjuntoIn, ConjuntoOut, SequenciaIO
from ..services import conjuntos

router = APIRouter()


@router.get("/conjuntos", response_model=list[ConjuntoOut])
def list_conjuntos(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return conjuntos.list_all(conn)


@router.get("/conjuntos/sequencia", response_model=SequenciaIO)
def get_sequencia(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return {"conjunto_ids": conjuntos.get_sequence(conn)}


@router.put("/conjuntos/sequencia", response_model=SequenciaIO)
def put_sequencia(body: SequenciaIO, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    conjuntos.set_sequence(conn, body.conjunto_ids)
    return {"conjunto_ids": conjuntos.get_sequence(conn)}


@router.post("/conjuntos", response_model=ConjuntoOut, status_code=201)
def add_conjunto(
    body: ConjuntoIn,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> dict:
    return conjuntos.add(conn, settings, body.nome, now())


@router.post("/conjuntos/{conjunto_id}/copiar", response_model=ConjuntoOut, status_code=201)
def copy_conjunto(
    conjunto_id: int,
    body: ConjuntoIn,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
    now=Depends(get_now),
) -> dict:
    return conjuntos.duplicate(conn, settings, conjunto_id, body.nome, now())


@router.patch("/conjuntos/{conjunto_id}", response_model=ConjuntoOut)
def rename_conjunto(
    conjunto_id: int,
    body: ConjuntoIn,
    conn: sqlite3.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> dict:
    return conjuntos.rename(conn, settings, conjunto_id, body.nome)


@router.post("/conjuntos/{conjunto_id}/ativar", status_code=204)
def activate_conjunto(conjunto_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    conjuntos.activate(conn, conjunto_id)
    return Response(status_code=204)


@router.delete("/conjuntos/{conjunto_id}", status_code=204)
def delete_conjunto(conjunto_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    conjuntos.remove(conn, conjunto_id)
    return Response(status_code=204)
