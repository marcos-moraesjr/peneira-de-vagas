"""Normalização, pontuação e exclusões. Não conhece fontes nem banco."""
import re
import unicodedata
from dataclasses import dataclass


def normalize(text: str) -> str:
    """Minúsculas, sem acento, só letras/dígitos separados por um espaço."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


MIN_STEM_LENGTH = 4


def _stem(word: str) -> str:
    """Ignora plural e gênero (engenheira/engenheiros → engenheir); palavras curtas ficam como estão."""
    if len(word) >= MIN_STEM_LENGTH and word.endswith("s"):
        word = word[:-1]
    if len(word) >= MIN_STEM_LENGTH and word[-1] in "ao":
        word = word[:-1]
    return word


def _contains_all_words(normalized_text: str, normalized_term: str) -> bool:
    words = {_stem(word) for word in normalized_text.split()}
    term_words = [_stem(word) for word in normalized_term.split()]
    return bool(term_words) and all(word in words for word in term_words)


@dataclass(frozen=True)
class Evaluation:
    score: int
    approved: bool


class Filter:
    """Um termo casa quando todas as suas palavras aparecem, em qualquer ordem, ignorando plural e gênero."""

    def __init__(self, keywords: list[str], exclusions: list[str], peso_titulo: int, peso_descricao: int, min_score: int):
        self._keywords = [normalize(k) for k in keywords]
        self._exclusions = [normalize(e) for e in exclusions]
        self._peso_titulo = peso_titulo
        self._peso_descricao = peso_descricao
        self._min_score = min_score

    def evaluate(self, titulo: str, trecho: str) -> Evaluation:
        title, body = normalize(titulo), normalize(trecho)
        if any(_contains_all_words(f"{title} {body}", term) for term in self._exclusions):
            return Evaluation(0, False)
        score = 0
        for term in self._keywords:
            if _contains_all_words(title, term):
                score += self._peso_titulo
            if _contains_all_words(body, term):
                score += self._peso_descricao
        return Evaluation(score, bool(self._keywords) and score >= self._min_score)
