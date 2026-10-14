"""SQLite (stdlib): esquema versionado, deduplicação e consultas de execução."""
import shutil
import sqlite3
from pathlib import Path

from .config import Settings
from .errors import Conflict
from .services import keywords
from .services.filters import normalize
from .sources.types import Job

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    inicio TEXT NOT NULL,
    fim TEXT,
    status TEXT NOT NULL CHECK (status IN ('executando', 'concluida'))
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    fonte TEXT NOT NULL,
    id_da_vaga TEXT NOT NULL,
    titulo TEXT NOT NULL,
    empresa TEXT NOT NULL,
    link TEXT NOT NULL,
    trecho TEXT NOT NULL,
    pontos INTEGER NOT NULL,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    encontrada_em TEXT NOT NULL,
    visto INTEGER NOT NULL DEFAULT 0,
    UNIQUE (fonte, id_da_vaga)
);
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY,
    termo TEXT NOT NULL,
    termo_normalizado TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('busca', 'exclusao')),
    criada_em TEXT NOT NULL,
    UNIQUE (termo_normalizado, tipo)
);
CREATE TABLE IF NOT EXISTS run_sources (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    fonte TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('aguardando', 'buscando', 'ok', 'falha')),
    motivo TEXT,
    detalhe TEXT,
    lidas INTEGER NOT NULL DEFAULT 0,
    aprovadas INTEGER NOT NULL DEFAULT 0,
    novas INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, fonte)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


_MIGRATION_V2 = "ALTER TABLE run_sources ADD COLUMN scanner_versao TEXT NOT NULL DEFAULT '';"

_MIGRATION_V3 = """
ALTER TABLE jobs ADD COLUMN localidade TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN publicada_em TEXT;
"""

_MIGRATION_V4 = """
CREATE TABLE conjuntos (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    nome_normalizado TEXT NOT NULL UNIQUE,
    ativo INTEGER NOT NULL DEFAULT 0,
    criada_em TEXT NOT NULL
);
CREATE UNIQUE INDEX um_conjunto_ativo ON conjuntos (ativo) WHERE ativo = 1;
INSERT INTO conjuntos (id, nome, nome_normalizado, ativo, criada_em) VALUES (1, 'Padrão', 'padrao', 1, '1970-01-01T00:00:00+00:00');
CREATE TABLE keywords_novo (
    id INTEGER PRIMARY KEY,
    termo TEXT NOT NULL,
    termo_normalizado TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('busca', 'exclusao')),
    criada_em TEXT NOT NULL,
    conjunto_id INTEGER NOT NULL REFERENCES conjuntos(id) ON DELETE CASCADE,
    UNIQUE (conjunto_id, termo_normalizado, tipo)
);
INSERT INTO keywords_novo (id, termo, termo_normalizado, tipo, criada_em, conjunto_id)
    SELECT id, termo, termo_normalizado, tipo, criada_em, 1 FROM keywords;
DROP TABLE keywords;
ALTER TABLE keywords_novo RENAME TO keywords;
"""

# V5: a vaga sobrevive à execução que a originou (limpar o histórico não apaga vagas): run_id passa a aceitar vazio.
_MIGRATION_V5 = """
CREATE TABLE jobs_novo (
    id INTEGER PRIMARY KEY,
    fonte TEXT NOT NULL,
    id_da_vaga TEXT NOT NULL,
    titulo TEXT NOT NULL,
    empresa TEXT NOT NULL,
    link TEXT NOT NULL,
    trecho TEXT NOT NULL,
    pontos INTEGER NOT NULL,
    run_id INTEGER REFERENCES runs(id) ON DELETE SET NULL,
    encontrada_em TEXT NOT NULL,
    visto INTEGER NOT NULL DEFAULT 0,
    localidade TEXT NOT NULL DEFAULT '',
    publicada_em TEXT,
    UNIQUE (fonte, id_da_vaga)
);
INSERT INTO jobs_novo (id, fonte, id_da_vaga, titulo, empresa, link, trecho, pontos, run_id, encontrada_em, visto, localidade, publicada_em)
    SELECT id, fonte, id_da_vaga, titulo, empresa, link, trecho, pontos, run_id, encontrada_em, visto, localidade, publicada_em FROM jobs;
DROP TABLE jobs;
ALTER TABLE jobs_novo RENAME TO jobs;
"""

# Versão do esquema → script. Banco existente é copiado para backup_dir antes de qualquer migração.
MIGRATIONS = {1: _SCHEMA_V1, 2: _MIGRATION_V2, 3: _MIGRATION_V3, 4: _MIGRATION_V4, 5: _MIGRATION_V5}
SCHEMA_VERSION = max(MIGRATIONS)


def connect(path: Path) -> sqlite3.Connection:
    """Conexão própria por requisição; linhas acessíveis por nome. Usada por uma thread de cada vez (dependência e rota podem cair em threads diferentes do pool)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.create_function("norm", 1, normalize, deterministic=True)
    return conn


def _current_version(conn: sqlite3.Connection) -> int | None:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='schema_version'").fetchone():
        return None
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    return row[0] if row else 0


def _backup_database(settings: Settings) -> None:
    settings.geral.backup_dir.mkdir(parents=True, exist_ok=True)
    count = len(list(settings.geral.backup_dir.glob("*.db")))
    shutil.copy2(settings.geral.db_path, settings.geral.backup_dir / f"jobscanner-pre-migracao-{count + 1}.db")


def _seed_keywords(conn: sqlite3.Connection, settings: Settings, now: str) -> None:
    """Semeia com o padrão da config uma única vez (apagar tudo depois não ressemeia)."""
    if conn.execute("SELECT 1 FROM meta WHERE key='seeded'").fetchone():
        return
    for termo in settings.padrao.palavras_chave:
        keywords.add(conn, settings, termo, "busca", now)
    for termo in settings.padrao.exclusoes:
        keywords.add(conn, settings, termo, "exclusao", now)
    conn.execute("INSERT INTO meta (key, value) VALUES ('seeded', '1')")
    conn.commit()


def init_db(conn: sqlite3.Connection, settings: Settings, now: str = "1970-01-01T00:00:00+00:00") -> None:
    """Cria/atualiza o esquema (com cópia do .db antes de migrar) e semeia as palavras-chave."""
    version = _current_version(conn)
    if version is None:
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version VALUES (0)")
        version = 0
    elif version < SCHEMA_VERSION:
        _backup_database(settings)
    for target in range(version + 1, SCHEMA_VERSION + 1):
        conn.executescript(MIGRATIONS[target])
        conn.execute("UPDATE schema_version SET version=?", (target,))
    conn.commit()
    _seed_keywords(conn, settings, now)


def create_run(conn: sqlite3.Connection, fontes: list[str], now: str, versions: dict[str, str] | None = None) -> int:
    """Abre uma execução (uma por vez), gravando a versão do scanner de cada fonte."""
    versions = versions or {}
    conn.execute("BEGIN IMMEDIATE")
    try:
        if conn.execute("SELECT 1 FROM runs WHERE status='executando'").fetchone():
            raise Conflict("Já existe uma execução em andamento")
        run_id = conn.execute("INSERT INTO runs (inicio, status) VALUES (?, 'executando')", (now,)).lastrowid
        conn.executemany(
            "INSERT INTO run_sources (run_id, fonte, status, scanner_versao) VALUES (?, ?, 'aguardando', ?)",
            [(run_id, fonte, versions.get(fonte, "")) for fonte in fontes],
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return run_id


def close_stale_runs(conn: sqlite3.Connection, now: str) -> None:
    """Execução que ficou 'executando' (processo caiu) vira concluída com falha 'interrompida'."""
    conn.execute(
        "UPDATE run_sources SET status='falha', motivo='interrompida' "
        "WHERE status IN ('aguardando','buscando') AND run_id IN (SELECT id FROM runs WHERE status='executando')"
    )
    conn.execute("UPDATE runs SET status='concluida', fim=? WHERE status='executando'", (now,))
    conn.commit()


def filter_unknown(conn: sqlite3.Connection, jobs: list[Job]) -> list[Job]:
    """Mantém só as vagas cujo (fonte, id_da_vaga) ainda não está no banco."""
    known = {(row["fonte"], row["id_da_vaga"]) for row in conn.execute("SELECT fonte, id_da_vaga FROM jobs")}
    return [job for job in jobs if (job.fonte, job.id) not in known]


def insert_new_jobs(conn: sqlite3.Connection, jobs: list[Job], scores: dict[str, int], run_id: int, now: str) -> int:
    """Grava só as vagas desconhecidas (fonte, id_da_vaga); devolve quantas eram novas."""
    inserted = 0
    for job in jobs:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO jobs (fonte, id_da_vaga, titulo, empresa, link, trecho, pontos, run_id, encontrada_em, localidade, publicada_em) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                job.fonte, job.id, job.titulo, job.empresa, job.link, job.trecho,
                scores.get(job.id, 0), run_id, now, job.localidade, job.publicada_em,
            ),
        )
        inserted += cursor.rowcount
    conn.commit()
    return inserted
