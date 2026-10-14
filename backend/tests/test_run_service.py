import pytest

from backend.app import db
from backend.app.errors import Conflict, DomainError
from backend.app.services import keywords, run_service
from backend.app.sources.errors import SourceBlocked
from backend.app.sources.types import Job

NOW = "2026-10-14T12:00:00+00:00"


def now():
    return NOW


def job(id_da_vaga, titulo="Engenheiro Mecânico", fonte="fake", trecho=""):
    return Job(id=id_da_vaga, titulo=titulo, empresa="ACME", link=f"https://x/{id_da_vaga}", trecho=trecho, fonte=fonte)


class FakeSource:
    def __init__(self, name="fake", jobs=None, error=None, enriched_trecho=None):
        self.name = name
        self._jobs = jobs or []
        self._error = error
        self._enriched_trecho = enriched_trecho
        self.search_calls = []
        self.enrich_calls = []

    def search(self, termos):
        self.search_calls.append(termos)
        if self._error:
            raise self._error
        return list(self._jobs)

    def enrich(self, jobs):
        self.enrich_calls.append([j.id for j in jobs])
        if self._enriched_trecho is None:
            return jobs
        return [Job(j.id, j.titulo, j.empresa, j.link, self._enriched_trecho, j.fonte) for j in jobs]


def run_all(conn, settings, sources):
    run_id = db.create_run(conn, [s.name for s in sources], NOW)
    run_service.execute_run(settings, run_id, sources, now)
    return run_id


def sources_of(conn, run_id):
    rows = conn.execute("SELECT * FROM run_sources WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
    return {row["fonte"]: dict(row) for row in rows}


def test_grava_apenas_vagas_aprovadas_e_conta_lidas_aprovadas_novas(conn, settings):
    fonte = FakeSource(jobs=[job("1"), job("2", titulo="Pintor")])
    run_id = run_all(conn, settings, [fonte])
    linha = sources_of(conn, run_id)["fake"]
    assert (linha["status"], linha["lidas"], linha["aprovadas"], linha["novas"]) == ("ok", 2, 1, 1)
    assert [r["id_da_vaga"] for r in conn.execute("SELECT id_da_vaga FROM jobs")] == ["1"]
    assert conn.execute("SELECT status FROM runs").fetchone()[0] == "concluida"


def test_falha_de_uma_fonte_nao_impede_as_outras(conn, settings):
    ruim = FakeSource("ruim", error=SourceBlocked("verificação", motivo="captcha"))
    boa = FakeSource("boa", jobs=[job("1", fonte="boa")])
    run_id = run_all(conn, settings, [ruim, boa])
    fontes = sources_of(conn, run_id)
    assert (fontes["ruim"]["status"], fontes["ruim"]["motivo"]) == ("falha", "captcha")
    assert fontes["boa"]["status"] == "ok"
    assert fontes["boa"]["novas"] == 1


def test_excecao_inesperada_vira_erro_interno_sem_derrubar_a_execucao(conn, settings):
    fonte = FakeSource("quebra", error=RuntimeError("bug"))
    run_id = run_all(conn, settings, [fonte])
    assert sources_of(conn, run_id)["quebra"]["motivo"] == "erro_interno"
    assert conn.execute("SELECT status FROM runs").fetchone()[0] == "concluida"


def test_zero_resultados_e_falha_e_nao_sucesso_vazio(conn, settings):
    run_id = run_all(conn, settings, [FakeSource(jobs=[])])
    linha = sources_of(conn, run_id)["fake"]
    assert (linha["status"], linha["motivo"]) == ("falha", "zero_resultados")


def test_segunda_execucao_nao_duplica_e_nao_conta_novas(conn, settings):
    fonte = FakeSource(jobs=[job("1")])
    run_all(conn, settings, [fonte])
    run_id = run_all(conn, settings, [fonte])
    linha = sources_of(conn, run_id)["fake"]
    assert (linha["aprovadas"], linha["novas"]) == (1, 0)
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_vaga_ja_conhecida_nao_abre_pagina_de_detalhe(conn, settings):
    fonte = FakeSource(jobs=[job("1"), job("2")])
    run_all(conn, settings, [fonte])
    fonte.enrich_calls.clear()
    run_all(conn, settings, [fonte])
    assert fonte.enrich_calls == [[]]


def test_detalhe_respeita_o_teto_por_execucao(conn, settings):
    teto = settings.limites.__class__(2, settings.limites.max_vagas_lista)
    limitada = settings.__class__(**{**settings.__dict__, "limites": teto})
    fonte = FakeSource(jobs=[job(str(n)) for n in range(5)])
    run_all(conn, limitada, [fonte])
    assert len(fonte.enrich_calls[0]) == 2
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 5


def test_detalhe_com_exclusao_na_descricao_completa_descarta_a_vaga(conn, settings):
    keywords.add(conn, settings, "estágio", "exclusao", NOW)
    fonte = FakeSource(jobs=[job("1")], enriched_trecho="Programa de estágio para estudantes")
    run_id = run_all(conn, settings, [fonte])
    assert sources_of(conn, run_id)["fake"]["novas"] == 0
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_palavras_chave_do_banco_sao_enviadas_a_fonte(conn, settings):
    keywords.add(conn, settings, "Engenheiro de Manutenção", "busca", NOW)
    fonte = FakeSource(jobs=[job("1")])
    run_all(conn, settings, [fonte])
    assert fonte.search_calls == [["Engenheiro Mecânico", "Engenheiro de Manutenção"]]


def test_start_run_sem_palavra_chave_e_rejeitado(conn, settings):
    for item in keywords.list_all(conn, "busca"):
        keywords.remove(conn, item["id"])
    with pytest.raises(DomainError, match="palavra-chave"):
        run_service.start_run(conn, settings, [FakeSource()], now, spawn=lambda fn: None)


def test_start_run_com_outra_em_andamento_levanta_conflito(conn, settings):
    spawned = []
    run_service.start_run(conn, settings, [FakeSource()], now, spawn=spawned.append)
    with pytest.raises(Conflict):
        run_service.start_run(conn, settings, [FakeSource()], now, spawn=spawned.append)
    assert len(spawned) == 1
