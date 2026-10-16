"""Carrega e valida config.toml em objetos tipados. Valores vêm só do arquivo."""
import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import urlsplit

from .sources.errors import MOTIVOS


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Geral:
    db_path: Path
    backup_dir: Path
    frontend_dist: Path
    log_dir: Path
    chrome_profile_dir: Path
    porta: int


@dataclass(frozen=True)
class Atualizacao:
    verificar: bool
    repositorio: str
    timeout_s: float


@dataclass(frozen=True)
class Padrao:
    palavras_chave: list[str]
    exclusoes: list[str]


@dataclass(frozen=True)
class Busca:
    keyword_max_length: int
    max_termos_busca: int
    janela_dias: int
    localidades: list[str]
    modalidade: list[str]


@dataclass(frozen=True)
class Filtro:
    peso_titulo: int
    peso_descricao: int
    min_score: int
    trecho_max_chars: int
    aceitar_desconhecido: bool


@dataclass(frozen=True)
class Limites:
    max_paginas_por_termo: int


@dataclass(frozen=True)
class Ritmo:
    pausa_min_s: float
    pausa_max_s: float
    rolagem_min_s: float
    rolagem_max_s: float
    pausa_detalhe_min_s: float
    pausa_detalhe_max_s: float


@dataclass(frozen=True)
class Navegador:
    cdp_url: str
    timeout_s: int
    probe_timeout_s: float
    chrome_paths: list[str]
    abas_paralelas: bool
    espera_verificacao_s: int
    max_tentativas_abertura: int
    max_tentativas_painel: int
    intervalo_tentativa_painel_s: float
    max_falhas_termo_seguidas: int
    max_falhas_detalhe_seguidas: int


@dataclass(frozen=True)
class Api:
    jobs_page_size: int
    runs_history_limit: int
    poll_interval_ms: int
    logs_linhas: int


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
    atualizacao: Atualizacao


LOCAL_HOSTS = ("127.0.0.1", "localhost")
MODALIDADES = ("remoto", "hibrido", "presencial")
_PATH_KEYS = ("db_path", "backup_dir", "frontend_dist", "log_dir", "chrome_profile_dir")


def _section(cls, raw: dict, name: str, root: Path, app_root: Path):
    section = raw.get(name)
    if not isinstance(section, dict):
        raise ConfigError(f"Config inválida: seção [{name}] ausente")
    expected = {f.name for f in fields(cls)}
    missing = expected - section.keys()
    if missing:
        raise ConfigError(f"Config inválida: [{name}] sem as chaves {sorted(missing)}")
    values = {key: section[key] for key in expected}
    if name == "geral":
        base = {"frontend_dist": app_root}  # o front acompanha o app; o resto são dados do usuário
        values = {key: (base.get(key, root) / Path(val) if key in _PATH_KEYS else val) for key, val in values.items()}
    return cls(**values)


def validate(settings: Settings) -> None:
    ritmo = settings.ritmo
    if ritmo.pausa_min_s > ritmo.pausa_max_s:
        raise ConfigError(
            f"Config inválida: pausa_min_s={ritmo.pausa_min_s} (esperado <= pausa_max_s={ritmo.pausa_max_s})"
        )
    host = urlsplit(settings.navegador.cdp_url).hostname
    if host not in LOCAL_HOSTS:
        raise ConfigError(
            f"Config inválida: cdp_url={settings.navegador.cdp_url!r} (esperado host {' ou '.join(LOCAL_HOSTS)}; "
            "a porta de depuração nunca pode sair da máquina)"
        )
    if ritmo.rolagem_min_s > ritmo.rolagem_max_s:
        raise ConfigError(
            f"Config inválida: rolagem_min_s={ritmo.rolagem_min_s} (esperado <= rolagem_max_s={ritmo.rolagem_max_s})"
        )
    if ritmo.pausa_detalhe_min_s > ritmo.pausa_detalhe_max_s:
        raise ConfigError(
            f"Config inválida: pausa_detalhe_min_s={ritmo.pausa_detalhe_min_s} "
            f"(esperado <= pausa_detalhe_max_s={ritmo.pausa_detalhe_max_s})"
        )
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", str(settings.atualizacao.repositorio)):
        raise ConfigError(
            f"Config inválida: repositorio={settings.atualizacao.repositorio!r} (esperado 'dono/nome' do GitHub)"
        )
    localidades = settings.busca.localidades
    names = [" ".join(item.split()).casefold() for item in localidades] if isinstance(localidades, list) and all(
        isinstance(item, str) for item in localidades
    ) else None
    if names is None or "" in names or len(set(names)) != len(names):
        raise ConfigError(
            f"Config inválida: localidades={localidades!r} (esperado lista de textos não vazios e sem repetição; vazia = sem filtro de local)"
        )
    modalidade = settings.busca.modalidade
    if (
        not isinstance(modalidade, list)
        or any(item not in MODALIDADES for item in modalidade)
        or len(set(modalidade)) != len(modalidade)
    ):
        raise ConfigError(
            f"Config inválida: modalidade={modalidade!r} (esperado lista sem repetição de {MODALIDADES}; vazia = todas)"
        )
    positives = {
        "keyword_max_length": settings.busca.keyword_max_length,
        "max_termos_busca": settings.busca.max_termos_busca,
        "janela_dias": settings.busca.janela_dias,
        "trecho_max_chars": settings.filtro.trecho_max_chars,
        "poll_interval_ms": settings.api.poll_interval_ms,
        "logs_linhas": settings.api.logs_linhas,
        "max_paginas_por_termo": settings.limites.max_paginas_por_termo,
        "jobs_page_size": settings.api.jobs_page_size,
        "gupy.page_size": settings.gupy.page_size,
        "max_tentativas_abertura": settings.navegador.max_tentativas_abertura,
        "max_tentativas_painel": settings.navegador.max_tentativas_painel,
        "max_falhas_termo_seguidas": settings.navegador.max_falhas_termo_seguidas,
        "max_falhas_detalhe_seguidas": settings.navegador.max_falhas_detalhe_seguidas,
        "atualizacao.timeout_s": settings.atualizacao.timeout_s,
    }
    for name, value in positives.items():
        if value <= 0:
            raise ConfigError(f"Config inválida: {name}={value} (esperado > 0)")
    non_negatives = {
        "peso_titulo": settings.filtro.peso_titulo,
        "peso_descricao": settings.filtro.peso_descricao,
        "min_score": settings.filtro.min_score,
        "pausa_min_s": ritmo.pausa_min_s,
        "rolagem_min_s": ritmo.rolagem_min_s,
        "intervalo_tentativa_painel_s": settings.navegador.intervalo_tentativa_painel_s,
        "pausa_detalhe_min_s": ritmo.pausa_detalhe_min_s,
    }
    for name, value in non_negatives.items():
        if value < 0:
            raise ConfigError(f"Config inválida: {name}={value} (esperado >= 0)")
    versionamento = settings.versionamento
    for name in ("falhas_consecutivas", "max_idade_dias"):
        if getattr(versionamento, name) <= 0:
            raise ConfigError(f"Config inválida: {name}={getattr(versionamento, name)} (esperado > 0)")
    invalid = [motivo for motivo in versionamento.motivos_de_quebra if motivo not in MOTIVOS]
    if invalid:
        raise ConfigError(f"Config inválida: motivos_de_quebra={invalid} (esperado subconjunto de {MOTIVOS})")


def settings_from_dict(raw: dict, root: Path, app_root: Path | None = None) -> Settings:
    sections = {}
    for field in fields(Settings):
        cls = {"linkedin": SearchSite, "indeed": SearchSite}.get(field.name, field.type)
        sections[field.name] = _section(cls, raw, field.name, root, app_root or root)
    settings = Settings(**sections)
    validate(settings)
    return settings


def _read_toml(path: Path) -> dict:
    with open(path, "rb") as handle:
        return tomllib.load(handle)


def load_settings(
    path: Path, root: Path | None = None, app_root: Path | None = None, defaults: Path | None = None
) -> Settings:
    """Lê o TOML; caminhos relativos partem de `root` (padrão: raiz do projeto, pai da pasta backend/).

    `frontend_dist` parte de `app_root` (padrão: `root`): instalado, o app e os dados do usuário ficam em pastas distintas.
    `defaults` (o config.toml que vem com o app) completa, em memória, seções e chaves que o arquivo do usuário
    ainda não tem: assim uma versão nova do app, com chaves novas, não quebra o config copiado na instalação."""
    raw = _read_toml(path)
    if defaults is not None:
        base = _read_toml(defaults)
        raw = {name: {**base.get(name, {}), **raw.get(name, {})} for name in {**base, **raw}}
    return settings_from_dict(raw, root or Path(path).resolve().parents[1], app_root)
