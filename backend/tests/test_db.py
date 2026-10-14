import sqlite3

import pytest

from backend.app import db
from backend.app.db import connect, init_db
from backend.app.errors import Conflict
from backend.app.sources.types import Job

NOW = "2026-10-14T12:00:00+00:00"


def make_job(id_da_vaga="1", fonte="gupy", titulo="Engenheiro Mecânico"):
    return Job(id=id_da_vaga, titulo=titulo, empresa="ACME", link=f"https://x/{id_da_vaga}", trecho="texto", fonte=fonte)


def test_init_db_cria_tabelas_e_semeia_palavra_chave_padrao(conn):
    termos = [linha["termo"] for linha in conn.execute("SELECT termo FROM keywords WHERE tipo='busca'")]
    assert termos == ["Engenheiro Mecânico"]


def test_init_db_nao_semeia_de_novo_se_a_tabela_tem_dados(settings):
    connection = connect(settings.geral.db_path)
    init_db(connection, settings)
    connection.execute("DELETE FROM keywords")
    connection.execute(
        "INSERT INTO keywords (termo, termo_normalizado, tipo, criada_em) VALUES ('x','x','busca',?)", (NOW,)
    )
    connection.commit()
    init_db(connection, settings)
    assert connection.execute("SELECT COUNT(*) FROM keywords").fetchone()[0] == 1


def test_init_db_nao_semeia_se_usuario_apagou_tudo_depois_do_primeiro_uso(settings):
    connection = connect(settings.geral.db_path)
    init_db(connection, settings)
    connection.execute("DELETE FROM keywords")
    connection.commit()
    init_db(connection, settings)
    assert connection.execute("SELECT COUNT(*) FROM keywords").fetchone()[0] == 0


def test_mesma_vaga_nao_e_gravada_duas_vezes(conn):
    run_id = db.create_run(conn, ["gupy"], NOW)
    assert db.insert_new_jobs(conn, [make_job()], {"1": 3}, run_id, NOW) == 1
    assert db.insert_new_jobs(conn, [make_job()], {"1": 3}, run_id, NOW) == 0
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_mesmo_id_em_fontes_diferentes_nao_colide(conn):
    run_id = db.create_run(conn, ["gupy"], NOW)
    jobs = [make_job("7", "gupy"), make_job("7", "linkedin")]
    assert db.insert_new_jobs(conn, jobs, {"7": 3}, run_id, NOW) == 2


def test_vaga_ja_gravada_nao_volta_a_nao_vista(conn):
    run_id = db.create_run(conn, ["gupy"], NOW)
    db.insert_new_jobs(conn, [make_job()], {"1": 3}, run_id, NOW)
    conn.execute("UPDATE jobs SET visto=1")
    db.insert_new_jobs(conn, [make_job()], {"1": 3}, run_id, NOW)
    assert conn.execute("SELECT visto FROM jobs").fetchone()[0] == 1


def test_criar_execucao_com_outra_em_andamento_levanta_conflito(conn):
    db.create_run(conn, ["gupy"], NOW)
    with pytest.raises(Conflict):
        db.create_run(conn, ["gupy"], NOW)


def test_abrir_o_app_encerra_execucao_que_ficou_pendurada(conn):
    run_id = db.create_run(conn, ["gupy"], NOW)
    db.close_stale_runs(conn, NOW)
    run = conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
    fonte = conn.execute("SELECT status, motivo FROM run_sources WHERE run_id=?", (run_id,)).fetchone()
    assert run["status"] == "concluida"
    assert (fonte["status"], fonte["motivo"]) == ("falha", "interrompida")


def test_esquema_antigo_gera_copia_do_banco_antes_de_migrar(settings):
    arquivo = settings.geral.db_path
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    antigo = sqlite3.connect(arquivo)
    antigo.execute("CREATE TABLE schema_version (version INTEGER)")
    antigo.execute("INSERT INTO schema_version VALUES (0)")
    antigo.commit()
    antigo.close()
    connection = connect(arquivo)
    init_db(connection, settings)
    assert list(settings.geral.backup_dir.glob("*.db"))
