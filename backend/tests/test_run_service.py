from dataclasses import replace
import threading
import time

import pytest

from backend.app import db
from backend.app.errors import Conflict, DomainError
from backend.app.services import conjuntos, keywords, run_service
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

    def enrich(self, jobs, on_job=None):
        self.enrich_calls.append([j.id for j in jobs])
        enriched = []
        for j in jobs:
            if self._enriched_trecho is not None:
                j = Job(j.id, j.titulo, j.empresa, j.link, self._enriched_trecho, j.fonte)
            enriched.append(j)
            if on_job:
                on_job(j)
        return enriched


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


def test_fonte_paginada_enriquece_durante_a_busca(conn, settings):
    eventos = []

    class FontePaginada(FakeSource):
        def search_and_enrich(self, termos, select_jobs, on_job=None):
            eventos.append("pagina")
            selecionadas = select_jobs(self._jobs)
            eventos.append("detalhe")
            for vaga in selecionadas:
                if on_job:
                    on_job(vaga)
            return list(self._jobs)

    fonte = FontePaginada(jobs=[job("1")])
    run_all(conn, settings, [fonte])

    assert eventos == ["pagina", "detalhe"]
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_vaga_detalhada_e_gravada_na_hora_mesmo_se_a_fonte_falha_depois(conn, settings):
    class FalhaNoSegundoDetalhe(FakeSource):
        def enrich(self, jobs, on_job=None):
            on_job(jobs[0])
            raise SourceBlocked("bloqueio no detalhe", motivo="captcha")

    fonte = FalhaNoSegundoDetalhe(jobs=[job("1", trecho="engenheiro mecânico"), job("2", trecho="engenheiro mecânico")])
    run_id = run_all(conn, settings, [fonte])
    assert sources_of(conn, run_id)["fake"]["status"] == "falha"
    assert [r["id_da_vaga"] for r in conn.execute("SELECT id_da_vaga FROM jobs")] == ["1"]


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


def test_detalhe_abre_todas_as_vagas_novas_sem_teto(conn, settings):
    fonte = FakeSource(jobs=[job(str(n)) for n in range(20)])
    run_all(conn, settings, [fonte])
    assert len(fonte.enrich_calls[0]) == 20
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 20


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


def test_busca_envia_so_os_primeiros_termos_ate_o_teto_da_config(conn, settings):
    for termo in ("Segundo", "Terceiro"):
        keywords.add(conn, settings, termo, "busca", NOW)
    menor = replace(settings, busca=replace(settings.busca, max_termos_busca=2))
    fonte = FakeSource(jobs=[job("1")])
    run_all(conn, menor, [fonte])
    assert fonte.search_calls == [["Engenheiro Mecânico", "Segundo"]]


def com_pontuacao(settings, min_score):
    return replace(settings, filtro=replace(settings.filtro, peso_titulo=3, peso_descricao=1, min_score=min_score))


def test_palavras_de_ranking_nao_vao_para_a_busca_mas_pontuam(conn, settings):
    keywords.add(conn, settings, "Cálculo", "ranking", NOW)
    config = com_pontuacao(settings, 4)
    com_ranking = job("1", trecho="exige cálculo estrutural")
    sem_ranking = job("2", trecho="sem o outro termo")
    fonte = FakeSource(jobs=[com_ranking, sem_ranking])
    run_id = run_all(conn, config, [fonte])
    assert fonte.search_calls == [["Engenheiro Mecânico"]]
    assert sources_of(conn, run_id)["fake"]["aprovadas"] == 1
    assert conn.execute("SELECT id_da_vaga, pontos FROM jobs").fetchall()[0]["pontos"] == 4


def test_termo_nos_dois_grupos_pontua_uma_vez(conn, settings):
    keywords.add(conn, settings, "Engenheiro Mecânico", "ranking", NOW)
    run_all(conn, com_pontuacao(settings, 0), [FakeSource(jobs=[job("1")])])
    assert conn.execute("SELECT pontos FROM jobs").fetchone()["pontos"] == 3


def test_busca_usa_so_o_conjunto_ativo(conn, settings):
    padrao = conjuntos.list_all(conn)[0]
    conjuntos.add(conn, settings, "Tecnologia", NOW)
    keywords.add(conn, settings, "Cientista de dados", "busca", NOW)
    fonte = FakeSource(jobs=[job("1", titulo="Cientista de dados")])
    run_all(conn, settings, [fonte])
    assert fonte.search_calls == [["Cientista de dados"]]
    conjuntos.activate(conn, padrao["id"])
    fonte = FakeSource(jobs=[job("2")])
    run_all(conn, settings, [fonte])
    assert fonte.search_calls == [["Engenheiro Mecânico"]]


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


def test_fonte_sem_filtro_local_grava_tudo_sem_exclusoes_nem_pontuacao(conn, settings):
    keywords.add(conn, settings, "pintor", "exclusao", NOW)
    fonte = FakeSource(jobs=[job("1", titulo="Pintor"), job("2", titulo="Dev .NET")])
    fonte.local_filter = False
    run_id = run_all(conn, settings, [fonte])
    linha = sources_of(conn, run_id)["fake"]
    assert (linha["status"], linha["lidas"], linha["aprovadas"], linha["novas"]) == ("ok", 2, 2, 2)
    assert [r["pontos"] for r in conn.execute("SELECT pontos FROM jobs")] == [0, 0]


def com_abas_paralelas(settings, valor):
    return replace(settings, navegador=replace(settings.navegador, abas_paralelas=valor))


class EncontroNaBusca(FakeSource):
    """Só termina a busca se as outras fontes também estiverem buscando ao mesmo tempo."""

    def __init__(self, name, barreira, **kwargs):
        super().__init__(name, **kwargs)
        self._barreira = barreira

    def search(self, termos):
        self._barreira.wait(timeout=5)
        return super().search(termos)


def test_abas_paralelas_buscam_todas_as_fontes_ao_mesmo_tempo(conn, settings):
    barreira = threading.Barrier(2)
    a = EncontroNaBusca("a", barreira, jobs=[job("1", fonte="a")])
    b = EncontroNaBusca("b", barreira, jobs=[job("2", fonte="b")])
    run_id = run_all(conn, com_abas_paralelas(settings, True), [a, b])
    fontes = sources_of(conn, run_id)
    assert [f["status"] for f in fontes.values()] == ["ok", "ok"]
    assert conn.execute("SELECT status FROM runs").fetchone()[0] == "concluida"


def test_abas_paralelas_isolam_a_falha_de_uma_fonte(conn, settings):
    ruim = FakeSource("ruim", error=SourceBlocked("verificação", motivo="captcha"))
    boa = FakeSource("boa", jobs=[job("1", fonte="boa")])
    run_id = run_all(conn, com_abas_paralelas(settings, True), [ruim, boa])
    fontes = sources_of(conn, run_id)
    assert (fontes["ruim"]["status"], fontes["ruim"]["motivo"]) == ("falha", "captcha")
    assert (fontes["boa"]["status"], fontes["boa"]["novas"]) == ("ok", 1)


def test_sem_abas_paralelas_as_fontes_rodam_uma_por_vez(conn, settings):
    ativas, pico, trava = [], [0], threading.Lock()

    class Mede(FakeSource):
        def search(self, termos):
            with trava:
                ativas.append(self.name)
                pico[0] = max(pico[0], len(ativas))
            time.sleep(0.05)
            with trava:
                ativas.remove(self.name)
            return super().search(termos)

    a, b = Mede("a", jobs=[job("1", fonte="a")]), Mede("b", jobs=[job("2", fonte="b")])
    run_id = run_all(conn, com_abas_paralelas(settings, False), [a, b])
    assert pico[0] == 1
    assert [f["status"] for f in sources_of(conn, run_id).values()] == ["ok", "ok"]


# ---------- filtro local de localidade e modalidade ----------

def com_busca(settings, **campos):
    return replace(settings, busca=replace(settings.busca, **campos))


def vaga(id_da_vaga, localidade="", modalidade=""):
    return replace(job(id_da_vaga), localidade=localidade, modalidade=modalidade)


def ids_gravados(conn):
    return sorted(row[0] for row in conn.execute("SELECT id_da_vaga FROM jobs"))


def test_filtro_local_descarta_vaga_de_outra_localidade(conn, settings):
    fonte = FakeSource(jobs=[vaga("1", "Campinas, SP"), vaga("2", "Recife, PE")])
    run_id = run_all(conn, com_busca(settings, localidades=["Campinas, SP"]), [fonte])
    assert ids_gravados(conn) == ["1"]
    linha = sources_of(conn, run_id)["fake"]
    assert (linha["lidas"], linha["aprovadas"], linha["novas"]) == (2, 1, 1)


def test_filtro_local_descarta_vaga_de_outra_modalidade(conn, settings):
    fonte = FakeSource(jobs=[vaga("1", modalidade="remoto"), vaga("2", modalidade="presencial")])
    run_all(conn, com_busca(settings, modalidade=["remoto"]), [fonte])
    assert ids_gravados(conn) == ["1"]


def test_vaga_sem_localidade_ou_modalidade_passa_quando_aceitar_desconhecido(conn, settings):
    fonte = FakeSource(jobs=[vaga("1"), vaga("2", "Recife, PE")])
    run_all(conn, com_busca(settings, localidades=["Campinas, SP"], modalidade=["remoto"]), [fonte])
    assert ids_gravados(conn) == ["1"]


def test_vaga_sem_localidade_ou_modalidade_cai_quando_nao_aceita_desconhecido(conn, settings):
    estrito = replace(
        com_busca(settings, localidades=["Campinas, SP"]), filtro=replace(settings.filtro, aceitar_desconhecido=False)
    )
    fonte = FakeSource(jobs=[vaga("1"), vaga("2", "Campinas, SP")])
    run_all(conn, estrito, [fonte])
    assert ids_gravados(conn) == ["2"]


def test_sem_localidade_nem_modalidade_na_config_nada_e_descartado(conn, settings):
    sem = com_busca(settings, localidades=[], modalidade=[])
    run_all(conn, sem, [FakeSource(jobs=[vaga("1", "Recife, PE", "presencial"), vaga("2")])])
    assert ids_gravados(conn) == ["1", "2"]


def test_vaga_sem_palavra_no_card_e_avaliada_depois_do_detalhe_e_gravada(conn, settings):
    keywords.add(conn, settings, "Cálculo", "ranking", NOW)
    fonte = FakeSource(jobs=[job("1", titulo="Projetista")], enriched_trecho="exige cálculo estrutural")
    run_id = run_all(conn, com_pontuacao(settings, 1), [fonte])
    assert fonte.enrich_calls == [["1"]]
    assert ids_gravados(conn) == ["1"]
    linha = sources_of(conn, run_id)["fake"]
    assert (linha["lidas"], linha["aprovadas"], linha["novas"]) == (1, 1, 1)


def test_vaga_reprovada_so_depois_do_detalhe_tem_a_pagina_aberta_mas_nao_e_gravada(conn, settings):
    fonte = FakeSource(jobs=[job("1", titulo="Projetista")], enriched_trecho="nada relevante")
    run_id = run_all(conn, com_pontuacao(settings, 1), [fonte])
    assert fonte.enrich_calls == [["1"]]
    assert ids_gravados(conn) == []
    linha = sources_of(conn, run_id)["fake"]
    assert (linha["lidas"], linha["aprovadas"], linha["novas"]) == (1, 0, 0)


def test_exclusao_no_card_evita_abrir_o_detalhe(conn, settings):
    keywords.add(conn, settings, "estágio", "exclusao", NOW)
    fonte = FakeSource(jobs=[job("1", titulo="Estágio em Engenharia Mecânica")])
    run_all(conn, com_pontuacao(settings, 1), [fonte])
    assert fonte.enrich_calls == [[]]


def test_localidade_fora_da_config_evita_abrir_o_detalhe(conn, settings):
    fonte = FakeSource(jobs=[vaga("1", "Campinas, SP"), vaga("2", "Recife, PE")])
    run_all(conn, com_busca(com_pontuacao(settings, 1), localidades=["Campinas, SP"]), [fonte])
    assert fonte.enrich_calls == [["1"]]


def test_vagas_ficam_atreladas_ao_conjunto_ativo_na_hora_da_busca(conn, settings):
    run_all(conn, settings, [FakeSource(jobs=[job("1")])])
    assert [row["conjunto_id"] for row in conn.execute("SELECT conjunto_id FROM jobs")] == [conjuntos.active_id(conn)]


def test_mesma_vaga_em_outro_conjunto_e_gravada_de_novo_e_o_detalhe_e_aberto(conn, settings):
    primeiro = conjuntos.active_id(conn)
    run_all(conn, settings, [FakeSource(jobs=[job("1")])])
    segundo = conjuntos.add(conn, settings, "Tecnologia", NOW)["id"]
    keywords.add(conn, settings, "Engenheiro Mecânico", "busca", NOW)
    fonte = FakeSource(jobs=[job("1")])
    run_id = run_all(conn, settings, [fonte])
    assert fonte.enrich_calls == [["1"]]
    assert sources_of(conn, run_id)["fake"]["novas"] == 1
    assert sorted(row["conjunto_id"] for row in conn.execute("SELECT conjunto_id FROM jobs")) == [primeiro, segundo]
    fonte = FakeSource(jobs=[job("1")])
    run_all(conn, settings, [fonte])
    assert fonte.enrich_calls == [[]]
