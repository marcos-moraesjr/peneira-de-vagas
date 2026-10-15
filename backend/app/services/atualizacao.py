"""Aviso de versão nova do app (scanners incluídos): compara a versão instalada com a última Release do GitHub."""
import re
from pathlib import Path

import httpx

COMANDO = "peneira atualizar"
_VERSAO = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = _VERSAO.match(text.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def check(installed, atualizacao, fetch_latest_tag) -> dict:
    """`fetch_latest_tag(repositorio, timeout_s)` devolve a tag da última Release (ex.: "v0.2.0")."""
    if not atualizacao.verificar:
        return {"estado": "desligado"}
    if installed is None:
        return {"estado": "desenvolvimento"}
    try:
        latest = fetch_latest_tag(atualizacao.repositorio, atualizacao.timeout_s)
    except (httpx.HTTPError, ValueError, KeyError):
        return {"estado": "indisponivel"}
    latest_version, installed_version = parse_version(latest), parse_version(installed)
    if latest_version is None or installed_version is None:
        return {"estado": "indisponivel"}
    return {
        "estado": "disponivel" if latest_version > installed_version else "atualizado",
        "instalada": installed.removeprefix("v"),
        "disponivel": latest.removeprefix("v"),
        "comando": COMANDO,
    }


def app_version(app_root: Path) -> str | None:
    """Versão gravada no pacote pelo build (`versao.txt`); ausente em desenvolvimento."""
    file = app_root / "versao.txt"
    return file.read_text(encoding="utf-8").strip() if file.is_file() else None


def fetch_latest_tag(repositorio: str, timeout_s: float, client: httpx.Client | None = None) -> str:
    """Tag da última Release do GitHub. Só pede a versão: nenhum dado do usuário vai na requisição."""
    url = f"https://api.github.com/repos/{repositorio}/releases/latest"
    headers = {"Accept": "application/vnd.github+json"}
    if client is None:
        with httpx.Client(timeout=timeout_s) as own:
            return _tag(own.get(url, headers=headers))
    return _tag(client.get(url, headers=headers, timeout=timeout_s))


def _tag(response: httpx.Response) -> str:
    response.raise_for_status()
    return str(response.json()["tag_name"])
