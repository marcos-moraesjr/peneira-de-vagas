"""Versionamento dos scanners (adaptadores de fonte gerados pelo Claude) e aviso de que é hora de refazer.

Regra: conta-se as falhas de "quebra" (config: motivos_de_quebra) seguidas, só da versão atual do scanner.
Sucesso zera a contagem; bloqueios (captcha, login, cloudflare, Chrome fechado) são ignorados, pois pedem
ação do usuário e não um scanner novo.
"""
import re
import sqlite3
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..config import ConfigError, Settings

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
REQUIRED_KEYS = ("versao", "explorado_em", "gerado_por", "referencia")
LABELS = {"linkedin": "LinkedIn", "indeed": "Indeed", "gupy": "Gupy"}

INSTRUCTION = (
    'O scanner da fonte "{label}" (versão {versao}, explorado em {explorado_em} por {gerado_por}) precisa ser refeito.\n'
    "Motivo: {falhas} falhas seguidas na versão atual ({motivo}: {detalhe}).\n"
    "Faça, seguindo TDD (teste vermelho antes do código):\n"
    "1. Explore a plataforma de novo no navegador e atualize a seção da fonte em {referencia}.\n"
    "2. Ajuste o adaptador em backend/app/sources/{fonte}.py e as amostras em backend/tests/samples/.\n"
    '3. Suba a versão de "{fonte}" em backend/scanners.toml (e a data da exploração) e registre a mudança '
    "no changelog de docs/SCANNERS.md.\n"
    "4. Rode os testes do backend e do frontend e me diga o que ainda precisa de validação manual."
)


@dataclass(frozen=True)
class ScannerInfo:
    fonte: str
    versao: str
    explorado_em: date
    gerado_por: str
    referencia: str


@dataclass(frozen=True)
class Manifest:
    scanners: dict[str, ScannerInfo]

    def versions(self) -> dict[str, str]:
        return {fonte: info.versao for fonte, info in self.scanners.items()}


def load_manifest(path: Path) -> Manifest:
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    scanners = {}
    for fonte, entry in raw.items():
        missing = [key for key in REQUIRED_KEYS if key not in entry]
        if missing:
            raise ConfigError(f"Manifesto inválido: [{fonte}] sem as chaves {missing}")
        if not SEMVER.match(str(entry["versao"])):
            raise ConfigError(f"Manifesto inválido: [{fonte}] versao={entry['versao']!r} (esperado MAJOR.MINOR.PATCH)")
        try:
            explored = date.fromisoformat(str(entry["explorado_em"]))
        except ValueError:
            raise ConfigError(
                f"Manifesto inválido: [{fonte}] explorado_em={entry['explorado_em']!r} (esperado AAAA-MM-DD)"
            ) from None
        scanners[fonte] = ScannerInfo(fonte, entry["versao"], explored, entry["gerado_por"], entry["referencia"])
    return Manifest(scanners)


def _count_breakages(conn: sqlite3.Connection, settings: Settings, info: ScannerInfo) -> tuple[int, str | None, str | None]:
    """Falhas de quebra seguidas na versão atual; devolve (contagem, último motivo, último detalhe)."""
    causes = set(settings.versionamento.motivos_de_quebra)
    rows = conn.execute(
        "SELECT status, motivo, detalhe FROM run_sources WHERE fonte=? AND scanner_versao=? "
        "AND status IN ('ok', 'falha') ORDER BY run_id DESC",
        (info.fonte, info.versao),
    )
    count, last_cause, last_detail = 0, None, None
    for row in rows:
        if row["status"] == "ok":
            break
        if row["motivo"] in causes:
            if count == 0:
                last_cause, last_detail = row["motivo"], row["detalhe"]
            count += 1
    return count, last_cause, last_detail


def _instruction(info: ScannerInfo, count: int, cause: str | None, detail: str | None) -> str:
    return INSTRUCTION.format(
        label=LABELS.get(info.fonte, info.fonte),
        versao=info.versao,
        explorado_em=info.explorado_em.isoformat(),
        gerado_por=info.gerado_por,
        falhas=count,
        motivo=cause,
        detalhe=detail or "sem detalhe",
        referencia=info.referencia,
        fonte=info.fonte,
    )


def _state(conn: sqlite3.Connection, settings: Settings, info: ScannerInfo, today: date) -> dict:
    count, cause, detail = _count_breakages(conn, settings, info)
    age = (today - info.explorado_em).days
    base = {
        "fonte": info.fonte,
        "versao": info.versao,
        "explorado_em": info.explorado_em.isoformat(),
        "gerado_por": info.gerado_por,
        "referencia": info.referencia,
        "falhas_consecutivas": count,
        "ultimo_motivo": cause,
        "instrucao": None,
    }
    limits = settings.versionamento
    if count >= limits.falhas_consecutivas:
        message = f"{count} falhas seguidas ({cause}): o scanner provavelmente quebrou e precisa ser refeito."
        return {**base, "status": "refazer", "mensagem": message, "instrucao": _instruction(info, count, cause, detail)}
    if count > 0:
        message = f"{count} falha(s) seguida(s) ({cause}). Se repetir, o scanner precisa ser refeito."
        return {**base, "status": "atencao", "mensagem": message}
    if age > limits.max_idade_dias:
        message = f"Scanner explorado há {age} dias (limite {limits.max_idade_dias}). Confira se a plataforma mudou."
        return {**base, "status": "atencao", "mensagem": message}
    return {**base, "status": "ok", "mensagem": "Scanner em dia."}


def evaluate(conn: sqlite3.Connection, settings: Settings, manifest: Manifest, today: date) -> list[dict]:
    return [_state(conn, settings, info, today) for info in manifest.scanners.values()]
