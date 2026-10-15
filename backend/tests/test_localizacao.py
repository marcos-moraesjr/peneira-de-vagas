import pytest

from backend.app.services.localizacao import detect_modalidade, passes_localidade, passes_modalidade, split_localidade


# ---------- modalidade ----------

@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Belo Horizonte e Região (Presencial)", "presencial"),
        ("São Paulo, SP (Híbrido)", "hibrido"),
        ("Brasil (Remoto)", "remoto"),
        ("Remote", "remoto"),
        ("Trabalho em home office", "remoto"),
        ("Hybrid · São Paulo", "hibrido"),
        ("On-site em Recife", "presencial"),
        ("Remoto ou híbrido", "hibrido"),
        ("Campinas, SP", ""),
        ("", ""),
    ],
)
def test_detecta_a_modalidade_no_texto(texto, esperado):
    assert detect_modalidade(texto) == esperado


def test_modalidade_vazia_na_config_aceita_todas():
    assert passes_modalidade("presencial", [], False) is True


def test_modalidade_precisa_estar_entre_as_desejadas():
    assert passes_modalidade("remoto", ["remoto", "hibrido"], False) is True
    assert passes_modalidade("presencial", ["remoto", "hibrido"], False) is False


def test_modalidade_desconhecida_segue_a_chave_da_config():
    assert passes_modalidade("", ["remoto"], True) is True
    assert passes_modalidade("", ["remoto"], False) is False


# ---------- localidade ----------

def local(vaga, entradas, modalidade="", aceitar=True):
    return passes_localidade(vaga, modalidade, entradas, aceitar)


def test_sem_localidade_na_config_aceita_qualquer_vaga():
    assert local("Recife, PE", []) is True


@pytest.mark.parametrize(
    "vaga,esperado",
    [
        ("Campinas, SP", True),
        ("CAMPINAS, SP", True),
        ("Campinas e Região", True),
        ("Campinas, São Paulo, Brasil", True),
        ("Campinas, MG", False),
        ("Recife, PE", False),
    ],
)
def test_entrada_cidade_e_uf_casa_a_cidade_e_nao_aceita_outra_uf(vaga, esperado):
    assert local(vaga, ["Campinas, SP"]) is esperado


@pytest.mark.parametrize(
    "vaga,esperado",
    [
        ("Belo Horizonte, Minas Gerais, Brasil", True),
        ("Belo Horizonte, MG", True),
        ("Campo Grande, MS", False),
        ("Campo Grande, Mato Grosso do Sul", False),
        ("Recife, PE", False),
    ],
)
def test_entrada_estado_casa_pela_uf_ou_pelo_nome(vaga, esperado):
    assert local(vaga, ["Minas Gerais"]) is esperado
    assert local(vaga, ["MG"]) is esperado


def test_mato_grosso_nao_casa_mato_grosso_do_sul():
    assert local("Cuiabá, Mato Grosso", ["Mato Grosso"]) is True
    assert local("Campo Grande, Mato Grosso do Sul", ["Mato Grosso"]) is False


def test_entrada_de_estado_com_vaga_sem_uf_segue_a_chave_da_config():
    assert local("Belo Horizonte e Região", ["Minas Gerais"], aceitar=True) is True
    assert local("Belo Horizonte e Região", ["Minas Gerais"], aceitar=False) is False


@pytest.mark.parametrize("vaga", ["", "Brasil", "Brazil"])
def test_localidade_vazia_ou_so_o_pais_segue_a_chave_da_config(vaga):
    assert local(vaga, ["Campinas, SP"], aceitar=True) is True
    assert local(vaga, ["Campinas, SP"], aceitar=False) is False


def test_vaga_remota_ignora_a_localidade_e_segue_a_chave_da_config():
    assert local("Recife, PE", ["Campinas, SP"], modalidade="remoto", aceitar=True) is True
    assert local("Recife, PE", ["Campinas, SP"], modalidade="remoto", aceitar=False) is False


def test_basta_uma_das_entradas_casar():
    assert local("Recife, PE", ["Campinas, SP", "Pernambuco"]) is True
    assert local("Recife, PE", ["Campinas, SP", "Minas Gerais"]) is False


def test_entrada_com_cidade_e_uf_nao_vira_o_estado_inteiro():
    assert local("Campinas, SP", ["São Paulo, SP"]) is False
    assert local("São Paulo, SP", ["São Paulo, SP"]) is True
    assert local("Campinas, SP", ["São Paulo"]) is True


# ---------- cidade e estado ----------

@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("Campinas, São Paulo", ("Campinas", "SP")),
        ("Campinas, SP", ("Campinas", "SP")),
        ("São Paulo, São Paulo, Brasil", ("São Paulo", "SP")),
        ("Recife, PE (Híbrido)", ("Recife", "PE")),
        ("Espírito Santo do Pinhal, SP", ("Espírito Santo do Pinhal", "SP")),
        ("Minas Gerais", ("", "MG")),
        ("Belo Horizonte e Região (Presencial)", ("Belo Horizonte e Região", "")),
        ("Brasil", ("", "")),
        ("Remote", ("", "")),
        ("", ("", "")),
    ],
)
def test_separa_cidade_e_estado_da_localidade(texto, esperado):
    assert split_localidade(texto) == esperado
