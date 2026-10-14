"""Chrome dedicado do JobScanner: detecta se está aberto (CDP) e o abre com perfil próprio.

A porta de depuração só escuta em 127.0.0.1 e o perfil é sempre o dedicado, nunca o pessoal.
"""
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from ..config import Settings
from ..errors import DomainError

DEBUG_ADDRESS = "127.0.0.1"


def is_open(settings: Settings, client: httpx.Client | None = None) -> bool:
    """True se o Chrome dedicado responde no endereço CDP configurado."""
    owned = client is None
    client = client or httpx.Client(timeout=settings.navegador.probe_timeout_s)
    try:
        return client.get(f"{settings.navegador.cdp_url}/json/version").status_code == 200
    except httpx.HTTPError:
        return False
    finally:
        if owned:
            client.close()


def find_chrome(settings: Settings) -> Path:
    candidates = settings.navegador.chrome_paths
    for candidate in candidates:
        if Path(candidate).is_file():
            return Path(candidate)
    raise DomainError(f"Chrome não encontrado em {candidates}. Ajuste chrome_paths no config.toml")


def _command(settings: Settings, executable: Path) -> list[str]:
    port = urlsplit(settings.navegador.cdp_url).port
    return [
        str(executable),
        f"--remote-debugging-port={port}",
        f"--remote-debugging-address={DEBUG_ADDRESS}",
        f"--user-data-dir={settings.geral.chrome_profile_dir}",
        "--no-first-run",
    ]


def launch_detached(command: list[str]) -> None:
    """Abre o Chrome desligado deste processo, para ele continuar aberto se a API for fechada."""
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(command, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_chrome(
    settings: Settings,
    already_open: Callable[[], bool],
    launcher: Callable[[list[str]], None] = launch_detached,
) -> str:
    """Abre o Chrome dedicado se ainda não estiver aberto. Devolve 'aberto' ou 'ja_aberto'."""
    if already_open():
        return "ja_aberto"
    launcher(_command(settings, find_chrome(settings)))
    return "aberto"
