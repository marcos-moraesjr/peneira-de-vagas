"""Filtro local de localidade e modalidade (o mesmo para todas as fontes).

As plataformas filtram local e modalidade cada uma a seu jeito (ou nem filtram), então a busca não leva esses
filtros: as vagas listadas é que passam por aqui, sobre campos normalizados."""
import re
import unicodedata

UF_NOMES = {
    "ac": "acre", "al": "alagoas", "ap": "amapa", "am": "amazonas", "ba": "bahia", "ce": "ceara",
    "df": "distrito federal", "es": "espirito santo", "go": "goias", "ma": "maranhao", "mt": "mato grosso",
    "ms": "mato grosso do sul", "mg": "minas gerais", "pa": "para", "pb": "paraiba", "pr": "parana",
    "pe": "pernambuco", "pi": "piaui", "rj": "rio de janeiro", "rn": "rio grande do norte",
    "rs": "rio grande do sul", "ro": "rondonia", "rr": "roraima", "sc": "santa catarina", "sp": "sao paulo",
    "se": "sergipe", "to": "tocantins",
}
_NOME_PARA_UF = {nome: uf for uf, nome in UF_NOMES.items()}
_NOMES_MAIS_LONGOS_PRIMEIRO = sorted(_NOME_PARA_UF, key=len, reverse=True)
_PAISES = {"brasil", "brazil"}
_MODALIDADES = (
    ("hibrido", re.compile(r"\bhibrid[oa]\b|\bhybrid\b")),
    ("remoto", re.compile(r"\bremot[oa]\b|\bremote\b|\bhome[ -]?office\b")),
    ("presencial", re.compile(r"\bpresencial\b|\bon-?site\b")),
)


def _fold(text: str) -> str:
    """Minúsculas e sem acento, mantendo a pontuação (a vírgula separa cidade e UF)."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def detect_modalidade(text: str) -> str:
    """Modalidade citada no texto ("(Presencial)", "Remote", "home office"); híbrido vence remoto; sem citação, `""`."""
    normalized = _fold(text)
    for name, pattern in _MODALIDADES:
        if pattern.search(normalized):
            return name
    return ""


def passes_modalidade(modalidade: str, desejadas: list[str], aceitar_desconhecida: bool) -> bool:
    if not desejadas:
        return True
    if not modalidade:
        return aceitar_desconhecida
    return modalidade in desejadas


def _phrase(phrase: str, text: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _uf_of(text: str) -> str | None:
    """UF citada no texto normalizado: pelo nome do estado ou por uma sigla que seja um trecho inteiro ("…, MG")."""
    for nome in _NOMES_MAIS_LONGOS_PRIMEIRO:
        if _phrase(nome, text):
            return _NOME_PARA_UF[nome]
    for trecho in reversed(re.split(r"[,\-/|·()]+", text)):
        if trecho.strip() in UF_NOMES:
            return trecho.strip()
    return None


def _entry_matches(entry: str, text: str, vaga_uf: str | None) -> bool | None:
    """True/False, ou None quando a vaga não informa o suficiente para decidir (entrada de estado, vaga sem UF)."""
    parts = [" ".join(_fold(part).split()) for part in entry.split(",") if part.strip()]
    first = parts[0]
    if len(parts) == 1 and (first in UF_NOMES or first in _NOME_PARA_UF):
        entry_uf = first if first in UF_NOMES else _NOME_PARA_UF[first]
        return None if vaga_uf is None else vaga_uf == entry_uf
    if not _phrase(first, text):
        return False
    entry_uf = next((_uf_of(part) or (part if part in UF_NOMES else None) for part in parts[1:]), None)
    return not (entry_uf and vaga_uf and entry_uf != vaga_uf)


def passes_localidade(localidade: str, modalidade: str, entradas: list[str], aceitar_desconhecida: bool) -> bool:
    """Vaga passa se casar com alguma entrada ("Campinas, SP", "Minas Gerais", "MG"). Localidade vazia, só o país
    ou vaga remota não permitem decidir: valem `aceitar_desconhecida`."""
    if not entradas:
        return True
    text = " ".join(_fold(localidade).split())
    if not text or text in _PAISES or modalidade == "remoto":
        return aceitar_desconhecida
    vaga_uf = _uf_of(text)
    results = [_entry_matches(entry, text, vaga_uf) for entry in entradas]
    if any(result is True for result in results):
        return True
    return aceitar_desconhecida if any(result is None for result in results) else False


def _uf_do_trecho(trecho: str) -> str | None:
    dobrado = _fold(trecho).strip()
    return dobrado if dobrado in UF_NOMES else _NOME_PARA_UF.get(dobrado)


def split_localidade(text: str) -> tuple[str, str]:
    """(cidade, UF) do texto livre da localidade; o que a fonte não informa fica `""`.

    A cidade é o primeiro trecho (antes da vírgula); a UF vem de um trecho seguinte (sigla ou nome do estado). Um texto
    de um trecho só que é um estado ("Minas Gerais") tem só UF. País e modalidade ("Brasil", "(Presencial)") são descartados."""
    limpo = re.sub(r"\([^)]*\)", "", text)
    trechos = [t.strip() for t in limpo.split(",") if t.strip()]
    trechos = [t for t in trechos if _fold(t).strip() not in _PAISES and not detect_modalidade(t)]
    if not trechos:
        return "", ""
    for trecho in trechos[1:]:
        uf = _uf_do_trecho(trecho)
        if uf:
            return trechos[0], uf.upper()
    uf = _uf_do_trecho(trechos[0])
    if len(trechos) == 1 and uf:
        return "", uf.upper()
    return trechos[0], ""
