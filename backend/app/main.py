"""create_app(): rotas sob /api, abertura do banco, tradução de erros e build estático em /."""
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import Settings, load_settings
from .errors import Conflict, DomainError, NotFound
from .routes import config as config_routes
from .routes import browser, conjuntos, health, jobs, keywords, runs, scanners, verificacao
from .services import chrome
from .services.run_service import spawn_thread
from .services.scanners import Manifest, load_manifest
from .sources.registry import build_sources
from .sources.verification import VerificationGate

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.toml"
DEFAULT_MANIFEST = DEFAULT_CONFIG.parent / "scanners.toml"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _setup_logging(settings: Settings) -> None:
    settings.geral.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(settings.geral.log_dir / "peneira-de-vagas.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def _handler(status_code: int):
    async def handle(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=status_code)

    return handle


def create_app(
    settings: Settings | None = None,
    sources_factory: Callable[[], list] | None = None,
    spawn: Callable | None = None,
    now: Callable[[], str] | None = None,
    manifest: Manifest | None = None,
    chrome_probe: Callable[[], bool] | None = None,
    chrome_launcher: Callable[[list[str]], None] | None = None,
    config_path: Path | None = None,
) -> FastAPI:
    if settings is None:
        settings = load_settings(DEFAULT_CONFIG)
        _setup_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.migrate_legacy_database(settings.geral.db_path)
        conn = db.connect(settings.geral.db_path)
        try:
            db.init_db(conn, settings, app.state.now())
            db.close_stale_runs(conn, app.state.now())
        finally:
            conn.close()
        yield

    app = FastAPI(title="Peneira de Vagas", lifespan=lifespan)
    app.state.settings = settings
    app.state.sources_factory = sources_factory or (lambda: build_sources(app.state.settings, app.state.gate))
    app.state.spawn = spawn or spawn_thread
    app.state.gate = VerificationGate()
    app.state.now = now or utc_now
    app.state.config_path = config_path or DEFAULT_CONFIG
    app.state.manifest = manifest or load_manifest(DEFAULT_MANIFEST)
    app.state.chrome_probe = chrome_probe or (lambda: chrome.is_open(settings))
    app.state.chrome_launcher = chrome_launcher or chrome.launch_detached

    for status_code, error in ((422, DomainError), (404, NotFound), (409, Conflict)):
        app.add_exception_handler(error, _handler(status_code))
    for module in (health, runs, jobs, keywords, conjuntos, scanners, browser, config_routes, verificacao):
        app.include_router(module.router, prefix="/api")

    if (settings.geral.frontend_dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=settings.geral.frontend_dist, html=True), name="front")
    return app
