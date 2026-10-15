"""Comando `peneira`: prepara a pasta de dados do usuário, sobe a API e abre a interface no navegador."""
import os
import shutil
import socket
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .config import load_settings
from .main import DEFAULT_CONFIG, create_app, setup_logging

HOST = "127.0.0.1"  # a API nunca escuta além do localhost (AI_GUIDELINES §5)


def prepare_home(home: Path, template: Path) -> Path:
    """Cria a pasta de dados e copia o config padrão só se ainda não existir (nunca sobrescreve o do usuário)."""
    home.mkdir(parents=True, exist_ok=True)
    config = home / "config.toml"
    if not config.exists():
        shutil.copyfile(template, config)
    return config


def run(home: Path, *, template: Path, app_root: Path, serve, open_browser, port_in_use, configure_logging) -> None:
    """Sobe a API com a config da pasta do usuário e abre a interface; se a porta já está em uso, só abre o navegador."""
    config = prepare_home(home, template)
    settings = load_settings(config, root=home, app_root=app_root, defaults=template)
    url = f"http://{HOST}:{settings.geral.porta}"
    if port_in_use(settings.geral.porta):
        open_browser(url)
        return
    configure_logging(settings)
    app = create_app(settings=settings, config_path=config)
    serve(app, settings.geral.porta, lambda: open_browser(url))



def default_home(env) -> Path:
    """Pasta de dados do usuário (banco, config, logs, perfil do Chrome): fora do app, sobrevive a atualizações."""
    return Path(env["LOCALAPPDATA"]) / "PeneiraDeVagas"


def _port_in_use(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex((HOST, port)) == 0


def _serve(app, port: int, on_ready) -> None:
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning"))

    def _when_started() -> None:
        while not server.started and not server.should_exit:
            time.sleep(0.1)
        if server.started:
            on_ready()

    threading.Thread(target=_when_started, daemon=True).start()
    server.run()


def main() -> None:
    print("Peneira de Vagas: abrindo a interface (Ctrl+C encerra).")
    run(
        default_home(os.environ),
        template=DEFAULT_CONFIG,
        app_root=DEFAULT_CONFIG.parents[1],
        serve=_serve,
        open_browser=webbrowser.open,
        port_in_use=_port_in_use,
        configure_logging=setup_logging,
    )


if __name__ == "__main__":
    main()
