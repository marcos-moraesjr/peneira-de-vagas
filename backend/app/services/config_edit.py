"""Grava valores no config.toml trocando só o valor da linha: comentários e demais chaves ficam intactos."""
import json
import os
import re
from dataclasses import replace
from pathlib import Path

from ..config import ConfigError, Settings, validate
from ..errors import DomainError

_SECTION = re.compile(r"^\s*\[([^\[\]]+)\]\s*(#.*)?$")
_VALUE = r'("(?:[^"\\]|\\.)*"|\[[^\]]*\]|[^\s#]+)'


def _format(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(_format(item) for item in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def write_values(path: Path, values: dict[str, dict[str, object]]) -> None:
    """`values` = {seção: {chave: valor}}. Chave ausente no arquivo: erro, sem gravar nada."""
    lines = Path(path).read_text(encoding="utf-8").splitlines(keepends=True)
    pending = {(section, key) for section, keys in values.items() for key in keys}
    section = None
    for index, line in enumerate(lines):
        header = _SECTION.match(line)
        if header:
            section = header.group(1).strip()
            continue
        if section not in values:
            continue
        for key, value in values[section].items():
            match = re.match(rf"^(\s*{re.escape(key)}\s*=\s*){_VALUE}", line)
            if match:
                lines[index] = match.group(1) + _format(value) + line[match.end():]
                pending.discard((section, key))
                break
    if pending:
        missing = ", ".join(f"{section}.{key}" for section, key in sorted(pending))
        raise DomainError(f"config.toml sem as chaves: {missing}")
    temp = Path(path).with_suffix(".toml.tmp")
    temp.write_text("".join(lines), encoding="utf-8", newline="")
    os.replace(temp, path)


def update_config(settings: Settings, path: Path, values: dict[str, dict[str, object]]) -> Settings:
    """Valida os valores sobre a config em vigor e só então grava o arquivo; devolve a nova config."""
    sections = {name: replace(getattr(settings, name), **keys) for name, keys in values.items()}
    updated = replace(settings, **sections)
    try:
        validate(updated)
    except ConfigError as error:
        raise DomainError(str(error)) from error
    write_values(path, values)
    return updated
