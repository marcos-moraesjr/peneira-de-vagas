from backend.app.services.filters import Filter, normalize


def make_filter(keywords=("Engenheiro Mecânico",), exclusions=(), min_score=3):
    return Filter(list(keywords), list(exclusions), peso_titulo=3, peso_descricao=1, min_score=min_score)


def test_normalize_remove_acento_caixa_e_pontuacao():
    assert normalize("  Engenheiro(a)  MECÂNICO – Sênior ") == "engenheiro a mecanico senior"


def test_titulo_com_a_palavra_chave_aprova_com_peso_do_titulo():
    resultado = make_filter().evaluate("Engenheiro Mecânico Pleno", "")
    assert resultado.approved is True
    assert resultado.score == 3


def test_acento_e_caixa_nao_atrapalham():
    assert make_filter().evaluate("ENGENHEIRO MECANICO", "").approved is True


def test_palavras_em_outra_ordem_e_com_genero_casam():
    assert make_filter().evaluate("Mecânico(a) - Engenheiro(a) de Projetos", "").approved is True


def test_so_na_descricao_pontua_menos_e_nao_atinge_o_limiar():
    resultado = make_filter().evaluate("Analista de Projetos", "Buscamos engenheiro mecânico")
    assert resultado.score == 1
    assert resultado.approved is False


def test_palavra_inteira_nao_casa_com_parte_de_outra():
    assert make_filter(["Eng"]).evaluate("Engenheiro", "").score == 0


def test_exclusao_vence_pontuacao_alta():
    resultado = make_filter(exclusions=["estágio"]).evaluate("Engenheiro Mecânico - ESTAGIO", "")
    assert resultado.approved is False


def test_exclusao_na_descricao_tambem_descarta():
    resultado = make_filter(exclusions=["pj"]).evaluate("Engenheiro Mecânico", "Contratação PJ")
    assert resultado.approved is False


def test_texto_vazio_e_sem_palavras_chave_nao_aprova():
    assert make_filter().evaluate("", "").approved is False
    assert make_filter(keywords=[]).evaluate("Engenheiro Mecânico", "").approved is False


def test_cada_termo_conta_uma_vez_no_titulo_e_uma_na_descricao():
    resultado = make_filter().evaluate("Engenheiro Mecânico Engenheiro Mecânico", "engenheiro mecanico engenheiro mecanico")
    assert resultado.score == 4


def test_limiar_na_borda():
    assert make_filter(min_score=3).evaluate("Engenheiro Mecânico", "").approved is True
    assert make_filter(min_score=4).evaluate("Engenheiro Mecânico", "").approved is False


def test_genero_e_plural_nao_atrapalham():
    f = make_filter()
    assert f.evaluate("Engenheira Mecânica Sênior", "").approved is True
    assert f.evaluate("Engenheiros Mecânicos", "").approved is True


def test_engenharia_nao_casa_com_engenheiro():
    assert make_filter().evaluate("Engenharia Mecânica", "").approved is False
