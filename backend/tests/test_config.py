import pytest

from backend.app.config import ConfigError, load_settings
from backend.tests.conftest import CONFIG_PATH


def test_config_do_projeto_carrega_com_padrao_de_desenvolvimento():
    settings = load_settings(CONFIG_PATH)
    assert settings.padrao.palavras_chave == ["Engenheiro Mecânico"]


def test_config_padrao_limita_a_6_termos_e_3_paginas_por_termo():
    settings = load_settings(CONFIG_PATH)
    assert settings.busca.max_termos_busca == 6
    assert settings.limites.max_paginas_por_termo == 3


def test_config_resolve_caminhos_relativos_a_partir_da_raiz():
    settings = load_settings(CONFIG_PATH)
    assert settings.geral.db_path.is_absolute()
    assert settings.geral.db_path.name == "jobscanner.db"


def test_config_com_chave_ausente_informa_secao_e_chave(tmp_path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text("[geral]\ndb_path = 'x.db'\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="geral"):
        load_settings(arquivo)


def test_config_com_valor_invalido_informa_valor_e_esperado():
    import tomllib

    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["ritmo"]["pausa_min_s"] = 9.0
    raw["ritmo"]["pausa_max_s"] = 1.0
    from backend.app.config import settings_from_dict

    with pytest.raises(ConfigError, match=r"pausa_min_s=9.0.*pausa_max_s"):
        settings_from_dict(raw, CONFIG_PATH.parents[1])


def test_gupy_aponta_para_o_endpoint_observado_no_portal():
    settings = load_settings(CONFIG_PATH)
    assert settings.gupy.base_url == "https://portal.gupy.io/api/job-search/jobs"


def test_localidades_padrao_e_lista_vazia_como_na_busca_observada():
    assert load_settings(CONFIG_PATH).busca.localidades == []


def test_localidades_aceita_cidades_e_estados():
    import tomllib

    from backend.app.config import settings_from_dict

    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["busca"]["localidades"] = ["Campinas, SP", "Minas Gerais", "Brasil"]
    assert settings_from_dict(raw, CONFIG_PATH.parents[1]).busca.localidades == ["Campinas, SP", "Minas Gerais", "Brasil"]


@pytest.mark.parametrize("valor", ["Campinas", [""], ["  "], [1], ["SP", "sp"], ["Campinas", " campinas "]])
def test_localidades_invalidas_informam_valor_e_esperado(valor):
    import tomllib

    from backend.app.config import settings_from_dict

    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["busca"]["localidades"] = valor
    with pytest.raises(ConfigError, match="localidades"):
        settings_from_dict(raw, CONFIG_PATH.parents[1])


def test_pausa_de_rolagem_valida_minimo_e_maximo():
    import tomllib

    from backend.app.config import settings_from_dict

    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["ritmo"]["rolagem_min_s"] = 2.0
    raw["ritmo"]["rolagem_max_s"] = 1.0
    with pytest.raises(ConfigError, match="rolagem_min_s=2.0"):
        settings_from_dict(raw, CONFIG_PATH.parents[1])


@pytest.mark.parametrize(
    ("secao", "chave", "valor"),
    [
        ("busca", "janela_horas", 0),
        ("busca", "max_termos_busca", 0),
        ("limites", "max_paginas_por_termo", 0),
        ("api", "poll_interval_ms", 0),
        ("filtro", "trecho_max_chars", 0),
        ("filtro", "peso_titulo", -1),
        ("filtro", "peso_descricao", -1),
        ("filtro", "min_score", -1),
        ("ritmo", "pausa_min_s", -0.5),
        ("ritmo", "rolagem_min_s", -0.5),
    ],
)
def test_config_rejeita_valores_fora_do_intervalo(secao, chave, valor):
    import tomllib

    from backend.app.config import settings_from_dict

    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw[secao][chave] = valor
    with pytest.raises(ConfigError, match=rf"{chave}={valor}"):
        settings_from_dict(raw, CONFIG_PATH.parents[1])


def test_modalidade_e_lista_vazia_por_padrao_e_aceita_varias():
    import tomllib

    from backend.app.config import settings_from_dict

    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert settings_from_dict(raw, CONFIG_PATH.parents[1]).busca.modalidade == []
    raw["busca"]["modalidade"] = ["remoto", "hibrido"]
    assert settings_from_dict(raw, CONFIG_PATH.parents[1]).busca.modalidade == ["remoto", "hibrido"]


@pytest.mark.parametrize("valor", [["voando"], ["remoto", "remoto"], "remoto"])
def test_modalidade_invalida_informa_valor_e_esperado(valor):
    import tomllib

    from backend.app.config import settings_from_dict

    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["busca"]["modalidade"] = valor
    with pytest.raises(ConfigError, match=r"modalidade=.*esperado"):
        settings_from_dict(raw, CONFIG_PATH.parents[1])




def test_filtro_traz_aceitar_desconhecido_como_booleano():
    assert load_settings(CONFIG_PATH).filtro.aceitar_desconhecido is True
