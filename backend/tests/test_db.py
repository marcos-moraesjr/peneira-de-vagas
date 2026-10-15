import sqlite3

import pytest

from backend.app import db
from backend.app.db import init_db
from backend.app.errors import Conflict
from backend.app.sources.types import Job

NOW = "2026-10-14T12:00:00+00:00"


def make_job(id_da_vaga="1", fonte="gupy", titulo="Engenheiro Mecânico"):
    return Job(id=id_da_vaga, titulo=titulo, empresa="ACME", link=f"https://x/{id_da_vaga}", trecho="texto", fonte=fonte)


def test_init_db_cria_tabelas_e_semeia_palavra_chave_padrao(conn):
    termos = [linha["termo"] for linha in conn.execute("SELECT termo FROM keywords WHERE tipo='busca'")]
    assert termos == ["Engenheiro Mecânico"]


def test_init_db_nao_semeia_de_novo_se_a_tabela_tem_dados(settings, abrir_conexao):
    connection = abrir_conexao(settings.geral.db_path)
    init_db(connection, settings)
    connection.execute("DELETE FROM keywords")
    connection.execute(
        "INSERT INTO keywords (termo, termo_normalizado, tipo, criada_em, conjunto_id) VALUES ('x','x','busca',?,1)", (NOW,)
    )
    connection.commit()
    init_db(connection, settings)
    assert connection.execute("SELECT COUNT(*) FROM keywords").fetchone()[0] == 1


def test_init_db_nao_semeia_se_usuario_apagou_tudo_depois_do_primeiro_uso(settings, abrir_conexao):
    connection = abrir_conexao(settings.geral.db_path)
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


def test_vaga_grava_localidade_e_data_de_publicacao(conn):
    run_id = db.create_run(conn, ["gupy"], NOW)
    job = Job("1", "Eng", "ACME", "https://x/1", "t", "gupy", localidade="Campinas, São Paulo", publicada_em="2026-10-08T11:04:27.057Z")
    db.insert_new_jobs(conn, [job, make_job("2")], {}, run_id, NOW)
    linhas = {r["id_da_vaga"]: (r["localidade"], r["publicada_em"]) for r in conn.execute("SELECT * FROM jobs")}
    assert linhas == {"1": ("Campinas, São Paulo", "2026-10-08T11:04:27.057Z"), "2": ("", None)}


def test_migracao_3_preserva_vagas_antigas_com_localidade_vazia_e_sem_data(settings, abrir_conexao):
    arquivo = settings.geral.db_path
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    antigo = sqlite3.connect(arquivo)
    antigo.executescript(db.MIGRATIONS[1] + db.MIGRATIONS[2])
    antigo.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    antigo.execute("INSERT INTO schema_version VALUES (2)")
    antigo.execute("INSERT INTO runs (inicio, status) VALUES ('x', 'concluida')")
    antigo.execute(
        "INSERT INTO jobs (fonte, id_da_vaga, titulo, empresa, link, trecho, pontos, run_id, encontrada_em) "
        "VALUES ('gupy','9','Antiga','ACME','https://x/9','t',1,1,'x')"
    )
    antigo.commit()
    antigo.close()
    connection = abrir_conexao(arquivo)
    init_db(connection, settings)
    linha = connection.execute("SELECT localidade, publicada_em, titulo FROM jobs").fetchone()
    assert (linha["titulo"], linha["localidade"], linha["publicada_em"]) == ("Antiga", "", None)


def test_migracao_5_deixa_a_vaga_sem_execucao_quando_a_execucao_e_apagada_e_preserva_as_vagas(settings, abrir_conexao):
    arquivo = settings.geral.db_path
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    antigo = sqlite3.connect(arquivo)
    antigo.executescript("".join(db.MIGRATIONS[versao] for versao in (1, 2, 3, 4)))
    antigo.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    antigo.execute("INSERT INTO schema_version VALUES (4)")
    antigo.execute("INSERT INTO runs (inicio, status) VALUES ('x', 'concluida')")
    antigo.execute(
        "INSERT INTO jobs (fonte, id_da_vaga, titulo, empresa, link, trecho, pontos, run_id, encontrada_em, visto) "
        "VALUES ('gupy','9','Antiga','ACME','https://x/9','t',1,1,'x',1)"
    )
    antigo.commit()
    antigo.close()
    connection = abrir_conexao(arquivo)
    init_db(connection, settings)
    linha = connection.execute("SELECT titulo, visto, run_id FROM jobs").fetchone()
    assert (linha["titulo"], linha["visto"], linha["run_id"]) == ("Antiga", 1, 1)
    connection.execute("DELETE FROM runs")
    assert connection.execute("SELECT run_id FROM jobs").fetchone()["run_id"] is None
    assert list(settings.geral.backup_dir.glob("*.db"))


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


def test_esquema_antigo_gera_copia_do_banco_antes_de_migrar(settings, abrir_conexao):
    arquivo = settings.geral.db_path
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    antigo = sqlite3.connect(arquivo)
    antigo.execute("CREATE TABLE schema_version (version INTEGER)")
    antigo.execute("INSERT INTO schema_version VALUES (0)")
    antigo.commit()
    antigo.close()
    connection = abrir_conexao(arquivo)
    init_db(connection, settings)
    assert list(settings.geral.backup_dir.glob("*.db"))


def test_conexao_pode_ser_usada_em_outra_thread(settings, abrir_conexao):
    """O FastAPI abre a conexão (dependência) e roda a rota em threads diferentes do pool."""
    import threading

    connection = abrir_conexao(settings.geral.db_path)
    erros = []

    def usar():
        try:
            connection.execute("SELECT 1").fetchone()
        except sqlite3.ProgrammingError as exc:
            erros.append(exc)

    thread = threading.Thread(target=usar)
    thread.start()
    thread.join()
    assert erros == []
