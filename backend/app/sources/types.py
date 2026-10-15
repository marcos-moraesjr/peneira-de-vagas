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
    localidade: str = ""
    modalidade: str = ""  # remoto | hibrido | presencial; vazio quando a fonte não informa
    publicada_em: str | None = None  # data de publicação em ISO 8601, quando a fonte informa
    palavra_chave: str = ""  # primeira palavra-chave buscada cuja busca devolveu a vaga
