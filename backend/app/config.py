"""Carrega e valida config.toml em objetos tipados. Valores vêm só do arquivo."""
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from .sources.errors import MOTIVOS


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Geral:
    db_path: Path
    backup_dir: Path
    frontend_dist: Path
    log_dir: Path


@dataclass(frozen=True)
class Padrao:
    palavras_chave: list[str]
    exclusoes: list[str]


@dataclass(frozen=True)
class Busca:
    keyword_max_length: int
    janela_horas: int
    localidade: str
    modalidade: str


@dataclass(frozen=True)
class Filtro:
    peso_titulo: int
    peso_descricao: int
    min_score: int
    trecho_max_chars: int


@dataclass(frozen=True)
class Limites:
    max_paginas_detalhe: int
    max_vagas_lista: int


@dataclass(frozen=True)
class Ritmo:
    pausa_min_s: float
    pausa_max_s: float
    rolagem_min_s: float
    rolagem_max_s: float


@dataclass(frozen=True)
class Navegador:
    cdp_url: str
    timeout_s: int


@dataclass(frozen=True)
class Api:
    jobs_page_size: int
    runs_history_limit: int
    poll_interval_ms: int


@dataclass(frozen=True)
class Gupy:
    base_url: str
    page_size: int
    timeout_s: int


@dataclass(frozen=True)
class SearchSite:
    base_url: str
    page_size: int


@dataclass(frozen=True)
class Versionamento:
    falhas_consecutivas: int
    max_idade_dias: int
    motivos_de_quebra: list[str]


@dataclass(frozen=True)
class Settings:
    geral: Geral
    padrao: Padrao
    busca: Busca
    filtro: Filtro
    limites: Limites
    ritmo: Ritmo
    navegador: Navegador
    api: Api
    gupy: Gupy
    linkedin: SearchSite
    indeed: SearchSite
    versionamento: Versionamento


MODALIDADES = ("", "remoto", "hibrido", "presencial")
_PATH_KEYS = ("db_path", "backup_dir", "frontend_dist", "log_dir")


def _section(cls, raw: dict, name: str, root: Path):
    section = raw.get(name)
    if not isinstance(section, dict):
        raise ConfigError(f"Config inválida: seção [{name}] ausente")
    expected = {f.name for f in fields(cls)}
    missing = expected - section.keys()
    if missing:
        raise ConfigError(f"Config inválida: [{name}] sem as chaves {sorted(missing)}")
    values = {key: section[key] for key in expected}
    if name == "geral":
        values = {key: (root / Path(val) if key in _PATH_KEYS else val) for key, val in values.items()}
    return cls(**values)


def _validate(settings: Settings) -> None:
    ritmo = settings.ritmo
    if ritmo.pausa_min_s > ritmo.pausa_max_s:
        raise ConfigError(
            f"Config inválida: pausa_min_s={ritmo.pausa_min_s} (esperado <= pausa_max_s={ritmo.pausa_max_s})"
        )
    if ritmo.rolagem_min_s > ritmo.rolagem_max_s:
        raise ConfigError(
            f"Config inválida: rolagem_min_s={ritmo.rolagem_min_s} (esperado <= rolagem_max_s={ritmo.rolagem_max_s})"
        )
    if settings.busca.modalidade not in MODALIDADES:
        raise ConfigError(f"Config inválida: modalidade={settings.busca.modalidade!r} (esperado {MODALIDADES})")
    positives = {
        "keyword_max_length": settings.busca.keyword_max_length,
        "max_vagas_lista": settings.limites.max_vagas_lista,
        "jobs_page_size": settings.api.jobs_page_size,
        "gupy.page_size": settings.gupy.page_size,
    }
    for name, value in positives.items():
        if value <= 0:
            raise ConfigError(f"Config inválida: {name}={value} (esperado > 0)")
    versionamento = settings.versionamento
    for name in ("falhas_consecutivas", "max_idade_dias"):
        if getattr(versionamento, name) <= 0:
            raise ConfigError(f"Config inválida: {name}={getattr(versionamento, name)} (esperado > 0)")
    invalid = [motivo for motivo in versionamento.motivos_de_quebra if motivo not in MOTIVOS]
    if invalid:
        raise ConfigError(f"Config inválida: motivos_de_quebra={invalid} (esperado subconjunto de {MOTIVOS})")
    if settings.limites.max_paginas_detalhe < 0:
        raise ConfigError(
            f"Config inválida: max_paginas_detalhe={settings.limites.max_paginas_detalhe} (esperado >= 0)"
        )


def settings_from_dict(raw: dict, root: Path) -> Settings:
    sections = {}
    for field in fields(Settings):
        cls = {"linkedin": SearchSite, "indeed": SearchSite}.get(field.name, field.type)
        sections[field.name] = _section(cls, raw, field.name, root)
    settings = Settings(**sections)
    _validate(settings)
    return settings


def load_settings(path: Path) -> Settings:
    """Lê o TOML; caminhos relativos partem da raiz do projeto (pai da pasta backend/)."""
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    return settings_from_dict(raw, Path(path).resolve().parents[1])
