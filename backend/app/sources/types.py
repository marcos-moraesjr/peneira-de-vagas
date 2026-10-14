from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    """Vaga no formato único devolvido por todas as fontes."""

    id: str
    titulo: str
    empresa: str
    link: str
    trecho: str
    fonte: str
