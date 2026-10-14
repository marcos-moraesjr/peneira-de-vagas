"""Erros de domínio traduzidos para HTTP em main.py."""


class DomainError(Exception):
    """Entrada ou estado inválido (422). A mensagem traz o valor ofensor e o esperado."""


class NotFound(Exception):
    """Recurso inexistente (404)."""


class Conflict(Exception):
    """Operação incompatível com o estado atual, ex.: execução já em andamento (409)."""
