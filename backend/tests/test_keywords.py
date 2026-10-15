import pytest

from backend.app.errors import DomainError, NotFound
from backend.app.services import keywords

NOW = "2026-10-14T12:00:00+00:00"


def test_adicionar_e_listar(conn, settings):
    novo = keywords.add(conn, settings, "  Engenheiro de Projetos ", "busca", NOW)
    termos = [k["termo"] for k in keywords.list_all(conn, "busca")]
    assert novo["termo"] == "Engenheiro de Projetos"
    assert "Engenheiro de Projetos" in termos


def test_termo_vazio_e_rejeitado(conn, settings):
    with pytest.raises(DomainError, match="Informe um termo"):
        keywords.add(conn, settings, "   ", "busca", NOW)


def test_termo_longo_demais_informa_valor_e_esperado(conn, settings):
    with pytest.raises(DomainError, match=r"termo=.*esperado <= 80"):
        keywords.add(conn, settings, "a" * 81, "busca", NOW)


def test_duplicata_ignora_caixa_e_acento(conn, settings):
    with pytest.raises(DomainError, match="já existe"):
        keywords.add(conn, settings, "ENGENHEIRO MECANICO", "busca", NOW)


def test_mesmo_termo_em_busca_e_exclusao_e_permitido(conn, settings):
    keywords.add(conn, settings, "Engenheiro Mecânico", "exclusao", NOW)


def test_tipo_invalido_e_rejeitado(conn, settings):
    with pytest.raises(DomainError, match="tipo"):
        keywords.add(conn, settings, "x", "outro", NOW)


def test_remover_e_remover_inexistente(conn, settings):
    existente = keywords.list_all(conn, "busca")[0]
    keywords.remove(conn, existente["id"])
    assert keywords.list_all(conn, "busca") == []
    with pytest.raises(NotFound):
        keywords.remove(conn, existente["id"])


def test_limite_de_termos_de_busca_por_conjunto(conn, settings):
    limite = settings.busca.max_termos_busca
    existentes = len(keywords.list_all(conn, "busca"))
    for n in range(limite - existentes):
        keywords.add(conn, settings, f"termo {n}", "busca", NOW)
    with pytest.raises(DomainError, match=rf"esperado <= {limite}"):
        keywords.add(conn, settings, "um a mais", "busca", NOW)
    keywords.add(conn, settings, "exclusão livre", "exclusao", NOW)


def test_ranking_e_um_grupo_separado_da_busca(conn, settings):
    keywords.add(conn, settings, "Cálculo estrutural", "ranking", NOW)
    assert [k["termo"] for k in keywords.list_all(conn, "ranking")] == ["Cálculo estrutural"]
    assert "Cálculo estrutural" not in [k["termo"] for k in keywords.list_all(conn, "busca")]


def test_mesmo_termo_em_busca_e_ranking_e_permitido_mas_nao_repete_no_ranking(conn, settings):
    keywords.add(conn, settings, "Engenheiro Mecânico", "ranking", NOW)
    with pytest.raises(DomainError, match="já existe"):
        keywords.add(conn, settings, "ENGENHEIRO MECANICO", "ranking", NOW)


def test_limite_de_termos_vale_so_para_a_busca_e_nao_para_o_ranking(conn, settings):
    for n in range(settings.busca.max_termos_busca + 3):
        keywords.add(conn, settings, f"ranking {n}", "ranking", NOW)
    assert len(keywords.list_all(conn, "ranking")) == settings.busca.max_termos_busca + 3
