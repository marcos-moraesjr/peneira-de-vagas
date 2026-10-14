"""Dependências injetáveis: configuração, conexão por requisição e relógio."""
import sqlite3
from collections.abc import Iterator

from fastapi import Request

from . import db
from .config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.connect(request.app.state.settings.geral.db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_now(request: Request):
    return request.app.state.now
