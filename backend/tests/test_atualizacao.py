from dataclasses import replace

from backend.app.services.atualizacao import check

COMANDO = "peneira atualizar"


def _check(settings, instalada, tag):
    return check(instalada, settings.atualizacao, lambda repositorio, timeout_s: tag)


def test_ha_atualizacao_quando_a_release_e_mais_nova(settings):
    assert _check(settings, "0.1.0", "v0.2.0") == {
        "estado": "disponivel", "instalada": "0.1.0", "disponivel": "0.2.0", "comando": COMANDO,
    }


def test_compara_numericamente_e_nao_como_texto(settings):
    assert _check(settings, "0.9.0", "v0.10.0")["estado"] == "disponivel"


def test_esta_atualizado_quando_a_versao_e_igual_ou_maior(settings):
    assert _check(settings, "0.2.0", "v0.2.0")["estado"] == "atualizado"
    assert _check(settings, "0.3.0", "v0.2.0")["estado"] == "atualizado"


def _sem_chamada(repositorio, timeout_s):
    raise AssertionError("não devia consultar o GitHub")


def test_desligado_no_config_nao_consulta_o_github(settings):
    desligada = replace(settings.atualizacao, verificar=False)
    assert check("0.1.0", desligada, _sem_chamada) == {"estado": "desligado"}


def test_em_desenvolvimento_sem_versao_instalada_nao_consulta_o_github(settings):
    assert check(None, settings.atualizacao, _sem_chamada) == {"estado": "desenvolvimento"}


def test_consulta_o_repositorio_e_o_timeout_do_config(settings):
    visto = []
    check("0.1.0", settings.atualizacao, lambda repositorio, timeout_s: visto.append((repositorio, timeout_s)) or "v0.1.0")
    assert visto == [("marcos-moraesjr/peneira-de-vagas", 5)]


def test_sem_rede_ou_resposta_invalida_vira_indisponivel_sem_erro(settings):
    import httpx

    def sem_rede(repositorio, timeout_s):
        raise httpx.ConnectError("sem rede")

    assert check("0.1.0", settings.atualizacao, sem_rede) == {"estado": "indisponivel"}
    assert _check(settings, "0.1.0", "nightly") == {"estado": "indisponivel"}


def _cliente(handler):
    import httpx

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_latest_tag_le_a_tag_da_ultima_release_do_repositorio():
    import httpx

    from backend.app.services.atualizacao import fetch_latest_tag

    pedidos = []

    def handler(request):
        pedidos.append(request)
        return httpx.Response(200, json={"tag_name": "v0.2.0"})

    assert fetch_latest_tag("dono/repo", 5, client=_cliente(handler)) == "v0.2.0"
    (pedido,) = pedidos
    assert str(pedido.url) == "https://api.github.com/repos/dono/repo/releases/latest"
    assert not {"cookie", "authorization"} & {nome.lower() for nome in pedido.headers}


def test_fetch_latest_tag_com_limite_de_taxa_ou_erro_http_levanta_erro_http():
    import httpx
    import pytest

    from backend.app.services.atualizacao import fetch_latest_tag

    with pytest.raises(httpx.HTTPError):
        fetch_latest_tag("dono/repo", 5, client=_cliente(lambda request: httpx.Response(403)))


def test_app_version_le_o_versao_txt_e_e_none_em_desenvolvimento(tmp_path):
    from backend.app.services.atualizacao import app_version

    assert app_version(tmp_path) is None
    (tmp_path / "versao.txt").write_text("0.3.1\n", encoding="utf-8")
    assert app_version(tmp_path) == "0.3.1"


def test_resposta_do_github_sem_tag_vira_indisponivel(settings):
    import httpx

    from backend.app.services.atualizacao import fetch_latest_tag

    cliente = _cliente(lambda request: httpx.Response(200, json={"message": "outra coisa"}))
    resultado = check("0.1.0", settings.atualizacao, lambda repo, t: fetch_latest_tag(repo, t, client=cliente))
    assert resultado == {"estado": "indisponivel"}
