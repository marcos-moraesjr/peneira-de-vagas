from dataclasses import replace

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.tests.test_api import NOW


def _client(settings, linhas, logs_linhas=3):
    pasta = settings.geral.log_dir
    pasta.mkdir(parents=True, exist_ok=True)
    if linhas is not None:
        (pasta / "peneira-de-vagas.log").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    api = replace(settings.api, logs_linhas=logs_linhas)
    return TestClient(create_app(replace(settings, api=api), now=lambda: NOW))


def test_logs_devolve_so_as_ultimas_linhas_do_arquivo(settings):
    with _client(settings, [f"linha {n}" for n in range(1, 6)]) as client:
        resposta = client.get("/api/logs")
    assert resposta.status_code == 200
    assert resposta.json() == {"arquivo": "peneira-de-vagas.log", "linhas": ["linha 3", "linha 4", "linha 5"]}


def test_logs_com_menos_linhas_que_o_limite_devolve_todas(settings):
    with _client(settings, ["so uma"]) as client:
        assert client.get("/api/logs").json()["linhas"] == ["so uma"]


def test_logs_sem_arquivo_devolve_lista_vazia(settings):
    with _client(settings, None) as client:
        # O lifespan cria o arquivo ao configurar o logging; removê-lo simula um log apagado.
        (settings.geral.log_dir / "peneira-de-vagas.log").unlink(missing_ok=True)
        resposta = client.get("/api/logs")
    assert resposta.status_code == 200
    assert resposta.json()["linhas"] == []


# ---------- log por execução, sincronizado com o histórico ----------

def _log_da_execucao(settings, run_id, linhas):
    pasta = settings.geral.log_dir / "execucoes"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"execucao-{run_id}.log").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def test_logs_de_uma_execucao_devolve_so_o_arquivo_dela(settings):
    _log_da_execucao(settings, 7, [f"exec {n}" for n in range(1, 6)])
    with _client(settings, ["geral"]) as client:
        resposta = client.get("/api/logs?execucao_id=7")
    assert resposta.json() == {"arquivo": "execucao-7.log", "linhas": ["exec 3", "exec 4", "exec 5"]}


def test_logs_de_execucao_sem_arquivo_devolve_lista_vazia(settings):
    with _client(settings, ["geral"]) as client:
        resposta = client.get("/api/logs?execucao_id=99")
    assert resposta.status_code == 200 and resposta.json()["linhas"] == []


def test_limpar_logs_esvazia_o_geral_e_apaga_os_das_execucoes(settings):
    _log_da_execucao(settings, 1, ["a"])
    _log_da_execucao(settings, 2, ["b"])
    with _client(settings, ["geral 1", "geral 2"]) as client:
        resposta = client.delete("/api/logs")
        assert resposta.status_code == 200 and resposta.json() == {"execucoes_removidas": 2}
        assert client.get("/api/logs").json()["linhas"] == []
        assert client.get("/api/logs?execucao_id=1").json()["linhas"] == []
    assert not list((settings.geral.log_dir / "execucoes").glob("*.log"))


def test_excluir_uma_execucao_apaga_o_log_dela(settings):
    from backend.app import db

    conn = db.connect(settings.geral.db_path)
    db.init_db(conn, settings)
    run_id = db.create_run(conn, ["stub"], NOW)
    conn.execute("UPDATE runs SET status='concluida', fim=? WHERE id=?", (NOW, run_id))
    conn.commit()
    conn.close()
    _log_da_execucao(settings, run_id, ["x"])
    _log_da_execucao(settings, 999, ["outra"])
    with _client(settings, ["geral"]) as client:
        assert client.delete(f"/api/runs/{run_id}").status_code == 200
    pasta = settings.geral.log_dir / "execucoes"
    assert not (pasta / f"execucao-{run_id}.log").exists()
    assert (pasta / "execucao-999.log").exists()


def test_limpar_o_historico_apaga_os_logs_das_execucoes(settings):
    _log_da_execucao(settings, 1, ["a"])
    with _client(settings, ["geral"]) as client:
        assert client.delete("/api/runs").status_code == 200
    assert not list((settings.geral.log_dir / "execucoes").glob("*.log"))
