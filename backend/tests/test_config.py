import pytest

from backend.app.config import ConfigError, load_settings
from backend.tests.conftest import CONFIG_PATH


def test_config_do_projeto_carrega_com_padrao_de_desenvolvimento():
    settings = load_settings(CONFIG_PATH)
    assert settings.padrao.palavras_chave == ["Engenheiro Mecânico"]
    assert settings.filtro.min_score == 3


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


def test_localidade_padrao_e_vazia_como_na_busca_observada():
    assert load_settings(CONFIG_PATH).busca.localidade == ""


def test_pausa_de_rolagem_valida_minimo_e_maximo():
    import tomllib

    from backend.app.config import settings_from_dict

    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["ritmo"]["rolagem_min_s"] = 2.0
    raw["ritmo"]["rolagem_max_s"] = 1.0
    with pytest.raises(ConfigError, match="rolagem_min_s=2.0"):
        settings_from_dict(raw, CONFIG_PATH.parents[1])
