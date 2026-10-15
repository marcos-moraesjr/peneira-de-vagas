"""Datas relativas do texto de páginas ("há 3 dias", "3 days ago") convertidas em ISO 8601 (UTC)."""
import re
from datetime import datetime, timedelta

from ..services.filters import normalize

_RELATIVE = re.compile(
    r"(?<![a-z])ha\s+(?P<n>\d+)\s+(?P<unit>minutos?|horas?|dias?|semanas?|meses|mes|anos?)(?![a-z])"
    r"|(?<!\d)(?P<n_en>\d+)\s+(?P<unit_en>minute|hour|day|week|month|year)s?\s+ago(?![a-z])"
)
_UNIT_DELTA = {
    "minut": timedelta(minutes=1), "hora": timedelta(hours=1), "hour": timedelta(hours=1), "dia": timedelta(days=1),
    "day": timedelta(days=1), "sema": timedelta(weeks=1), "week": timedelta(weeks=1), "mes": timedelta(days=30),
    "mont": timedelta(days=30), "ano": timedelta(days=365), "year": timedelta(days=365), "minute": timedelta(minutes=1),
}


def parse_relative_date(text: str, now: datetime) -> str | None:
    """"há 3 dias" / "3 days ago" → data ISO (UTC); sem data relativa no texto, `None`. Mês = 30 dias, ano = 365."""
    found = _RELATIVE.search(normalize(text))
    if not found:
        return None
    amount = int(found.group("n") or found.group("n_en"))
    unit = found.group("unit") or found.group("unit_en")
    delta = next(value for prefix, value in _UNIT_DELTA.items() if unit.startswith(prefix))
    return (now - amount * delta).strftime("%Y-%m-%dT%H:%M:%SZ")
