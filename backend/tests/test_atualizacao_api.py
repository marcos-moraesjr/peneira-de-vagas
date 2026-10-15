from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.tests.test_api import NOW


def _client(settings, instalada, tag, chamadas=None):
    def fetch(repositorio, timeout_s):
        if chamadas is not None:
            chamadas.append((repositorio, timeout_s))
        if isinstance(tag, Exception):
            raise tag
        return tag

    app = create_app(settings, now=lambda: NOW, app_version=lambda: instalada, latest_fetch=fetch)
    return TestClient(app)


def test_atualizacao_avisa_quando_ha_release_mais_nova(settings):
    with _client(settings, "0.1.0", "v0.2.0") as client:
        resposta = client.get("/api/atualizacao")
    assert resposta.status_code == 200
    assert resposta.json() == {
        "estado": "disponivel", "instalada": "0.1.0", "disponivel": "0.2.0", "comando": "peneira atualizar",
    }


def test_atualizacao_em_desenvolvimento_nao_consulta_ninguem(settings):
    chamadas = []
    with _client(settings, None, "v9.9.9", chamadas) as client:
        corpo = client.get("/api/atualizacao").json()
    assert corpo["estado"] == "desenvolvimento" and corpo["instalada"] is None
    assert chamadas == []
