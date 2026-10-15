import tomllib

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.config import ConfigError, settings_from_dict
from backend.app.errors import DomainError
from backend.app.main import create_app
from backend.app.services import chrome
from backend.tests.conftest import CONFIG_PATH


def probe_client(status=200, error=False):
    def handler(request):
        if error:
            raise httpx.ConnectError("fechado")
        assert request.url.path == "/json/version"
        return httpx.Response(status, json={"Browser": "Chrome/155"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def with_navegador(settings, **changes):
    navegador = settings.navegador.__class__(**{**settings.navegador.__dict__, **changes})
    return settings.__class__(**{**settings.__dict__, "navegador": navegador})


# ---------- config ----------

def test_cdp_fora_da_maquina_e_recusado_na_config():
    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["navegador"]["cdp_url"] = "http://192.168.0.10:9222"
    with pytest.raises(ConfigError, match=r"cdp_url='http://192.168.0.10:9222'.*127.0.0.1"):
        settings_from_dict(raw, CONFIG_PATH.parents[1])


def test_config_traz_perfil_dedicado_e_caminhos_do_chrome(settings):
    assert settings.geral.chrome_profile_dir.parts[-2:] == ("data", "chrome-profile")
    assert settings.navegador.chrome_paths


# ---------- sonda e descoberta ----------

def test_is_open_true_quando_o_cdp_responde(settings):
    assert chrome.is_open(settings, probe_client()) is True


def test_is_open_false_quando_a_porta_esta_fechada_ou_responde_erro(settings):
    assert chrome.is_open(settings, probe_client(error=True)) is False
    assert chrome.is_open(settings, probe_client(status=500)) is False


def test_find_chrome_devolve_o_primeiro_caminho_existente(settings, tmp_path):
    existente = tmp_path / "chrome.exe"
    existente.write_text("x")
    cfg = with_navegador(settings, chrome_paths=[str(tmp_path / "nao-existe.exe"), str(existente)])
    assert chrome.find_chrome(cfg) == existente


def test_find_chrome_sem_nenhum_caminho_informa_os_testados(settings, tmp_path):
    cfg = with_navegador(settings, chrome_paths=[str(tmp_path / "a.exe")])
    with pytest.raises(DomainError, match=r"Chrome não encontrado.*a\.exe.*chrome_paths"):
        chrome.find_chrome(cfg)


# ---------- abrir ----------

def test_abrir_lanca_o_chrome_com_perfil_dedicado_e_porta_so_local(settings, tmp_path):
    exe = tmp_path / "chrome.exe"
    exe.write_text("x")
    cfg = with_navegador(settings, chrome_paths=[str(exe)])
    lancados = []
    estado = chrome.open_chrome(cfg, lambda: False, launcher=lancados.append)
    assert estado == "aberto"
    comando = lancados[0]
    assert comando[0] == str(exe)
    assert "--remote-debugging-port=9222" in comando
    assert "--remote-debugging-address=127.0.0.1" in comando
    assert f"--user-data-dir={cfg.geral.chrome_profile_dir}" in comando


def test_abrir_com_chrome_ja_aberto_nao_lanca_outro(settings):
    lancados = []
    assert chrome.open_chrome(settings, lambda: True, launcher=lancados.append) == "ja_aberto"
    assert lancados == []


# ---------- API ----------

class FakeChrome:
    def __init__(self, aberto):
        self.aberto = aberto
        self.lancados = []

    def probe(self):
        return self.aberto

    def launch(self, comando):
        self.lancados.append(comando)
        self.aberto = True


def make_client(settings, fake, tmp_path):
    exe = tmp_path / "chrome.exe"
    exe.write_text("x")
    cfg = with_navegador(settings, chrome_paths=[str(exe)])
    app = create_app(cfg, sources_factory=list, chrome_probe=fake.probe, chrome_launcher=fake.launch)
    return TestClient(app)


def test_api_informa_se_o_chrome_dedicado_esta_aberto(settings, tmp_path):
    with make_client(settings, FakeChrome(False), tmp_path) as client:
        assert client.get("/api/browser").json() == {"aberto": False}


def test_api_abre_o_chrome_e_depois_informa_aberto(settings, tmp_path):
    fake = FakeChrome(False)
    with make_client(settings, fake, tmp_path) as client:
        assert client.post("/api/browser/open").json() == {"estado": "aberto"}
        assert client.get("/api/browser").json() == {"aberto": True}
    assert len(fake.lancados) == 1


def test_api_abrir_com_chrome_ja_aberto_nao_duplica(settings, tmp_path):
    fake = FakeChrome(True)
    with make_client(settings, fake, tmp_path) as client:
        assert client.post("/api/browser/open").json() == {"estado": "ja_aberto"}
    assert fake.lancados == []


def test_api_nao_oferece_copia_de_perfil(settings, tmp_path):
    with make_client(settings, FakeChrome(False), tmp_path) as client:
        assert client.get("/api/browser/profiles").status_code == 404
        assert client.post("/api/browser/profile/copy", json={"pasta": "Default", "substituir": False}).status_code == 404


def test_config_nao_tem_mais_chaves_da_copia_de_perfil(settings):
    assert not hasattr(settings.navegador, "chrome_user_data_dirs")
    assert not hasattr(settings.navegador, "copy_ignore")


def test_api_sem_chrome_instalado_devolve_422_com_orientacao(settings, tmp_path):
    cfg = with_navegador(settings, chrome_paths=[str(tmp_path / "x.exe")])
    app = create_app(cfg, sources_factory=list, chrome_probe=lambda: False, chrome_launcher=lambda c: None)
    with TestClient(app) as client:
        resposta = client.post("/api/browser/open")
    assert resposta.status_code == 422 and "chrome_paths" in resposta.json()["detail"]
