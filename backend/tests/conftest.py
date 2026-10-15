from dataclasses import replace
from pathlib import Path

import pytest

from backend.app.config import Settings, load_settings
from backend.app.db import connect, init_db

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.toml"


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Config real do projeto, com banco e pastas apontados para um diretório temporário."""
    base = load_settings(CONFIG_PATH)
    geral = base.geral.__class__(
        **{
            **base.geral.__dict__,
            "db_path": tmp_path / "test.db",
            "backup_dir": tmp_path / "backups",
            "frontend_dist": tmp_path / "dist",
            "log_dir": tmp_path / "logs",
        }
    )
    # Linha de base fixa: os testes não dependem do que o usuário ajustou no config.toml.
    busca = replace(base.busca, janela_dias=1)
    filtro = replace(base.filtro, min_score=3, trecho_max_chars=4000)
    api = replace(base.api, poll_interval_ms=2000)
    return base.__class__(**{**base.__dict__, "geral": geral, "busca": busca, "filtro": filtro, "api": api})


@pytest.fixture
def conn(settings):
    connection = connect(settings.geral.db_path)
    init_db(connection, settings)
    yield connection
    connection.close()


@pytest.fixture
def abrir_conexao():
    """`connect` para testes que abrem o próprio banco; fecha todas as conexões ao final."""
    abertas = []

    def _abrir(path):
        connection = connect(path)
        abertas.append(connection)
        return connection

    yield _abrir
    for connection in abertas:
        connection.close()
