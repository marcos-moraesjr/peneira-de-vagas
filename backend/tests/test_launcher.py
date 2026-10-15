from backend.app.launcher import prepare_home


def test_prepare_home_cria_a_pasta_e_copia_o_config_padrao(tmp_path):
    modelo = tmp_path / "modelo.toml"
    modelo.write_text("[geral]\n", encoding="utf-8")
    home = tmp_path / "dados" / "PeneiraDeVagas"

    config = prepare_home(home, modelo)

    assert config == home / "config.toml"
    assert config.read_text(encoding="utf-8") == "[geral]\n"


def test_prepare_home_nunca_sobrescreve_o_config_do_usuario(tmp_path):
    modelo = tmp_path / "modelo.toml"
    modelo.write_text("padrao", encoding="utf-8")
    home = tmp_path / "dados"
    home.mkdir()
    (home / "config.toml").write_text("ajustado pelo usuário", encoding="utf-8")

    prepare_home(home, modelo)

    assert (home / "config.toml").read_text(encoding="utf-8") == "ajustado pelo usuário"


def _run(home, **overrides):
    from backend.app.launcher import run
    from backend.tests.conftest import CONFIG_PATH

    chamadas = {"serve": [], "abrir": []}

    def serve(app, port, on_ready):
        chamadas["serve"].append((app, port))
        on_ready()

    run(
        home,
        template=CONFIG_PATH,
        app_root=CONFIG_PATH.parents[1],
        serve=overrides.get("serve", serve),
        open_browser=chamadas["abrir"].append,
        port_in_use=overrides.get("port_in_use", lambda port: False),
        configure_logging=lambda settings: None,
    )
    return chamadas


def test_run_sobe_a_api_com_a_config_da_pasta_do_usuario_e_abre_o_navegador(tmp_path):
    chamadas = _run(tmp_path / "dados")

    (app, port), = chamadas["serve"]
    assert port == 8100
    assert app.state.config_path == tmp_path / "dados" / "config.toml"
    assert app.state.settings.geral.db_path == tmp_path / "dados" / "data" / "peneira-de-vagas.db"
    assert chamadas["abrir"] == ["http://127.0.0.1:8100"]


def test_run_com_porta_ocupada_so_abre_o_navegador_na_instancia_existente(tmp_path):
    chamadas = _run(tmp_path / "dados", port_in_use=lambda port: port == 8100)

    assert chamadas["serve"] == []
    assert chamadas["abrir"] == ["http://127.0.0.1:8100"]


def test_default_home_fica_em_localappdata(tmp_path):
    from backend.app.launcher import default_home

    assert default_home({"LOCALAPPDATA": str(tmp_path)}) == tmp_path / "PeneiraDeVagas"


def test_run_completa_o_config_antigo_do_usuario_com_as_chaves_novas_do_app(tmp_path):
    import re

    from backend.tests.conftest import CONFIG_PATH

    home = tmp_path / "dados"
    home.mkdir()
    antigo = re.sub(r"(?m)^porta = .*\n", "", CONFIG_PATH.read_text(encoding="utf-8"))
    (home / "config.toml").write_text(antigo, encoding="utf-8")

    chamadas = _run(home)

    assert chamadas["abrir"] == ["http://127.0.0.1:8100"]
