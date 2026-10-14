"""Execução REAL contra os sites. Só o usuário roda: pytest -m integration.

Pré-requisitos: Chrome dedicado aberto e logado (scripts/chrome-dedicado.ps1). Não entra em rotina.
"""
import pytest

from backend.app.sources.registry import build_sources

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("nome", ["linkedin", "indeed", "gupy"])
def test_fonte_real_devolve_vagas_no_formato_unico(settings, nome):
    fonte = next(s for s in build_sources(settings) if s.name == nome)
    vagas = fonte.search(settings.padrao.palavras_chave)
    assert vagas, f"{nome}: nenhuma vaga (ver log e motivo da falha)"
    primeira = vagas[0]
    assert primeira.id and primeira.titulo and primeira.link.startswith("http")
    assert primeira.fonte == nome
