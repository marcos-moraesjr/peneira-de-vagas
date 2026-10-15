import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from backend.app.sources.errors import SourceLayoutChanged, SourceUnavailable
from backend.app.sources.gupy import GupySource

SAMPLE = json.loads((Path(__file__).parent / "samples" / "gupy_jobs.json").read_text(encoding="utf-8"))


def make_source(settings, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GupySource(settings, client=client)


def test_converte_resposta_da_gupy_para_o_formato_unico(settings):
    source = make_source(settings, lambda request: httpx.Response(200, json=SAMPLE))
    jobs = source.search(["Engenheiro Mecânico"])
    primeira = jobs[0]
    assert (primeira.id, primeira.fonte, primeira.empresa) == ("1001", "gupy", "Metalúrgica Exemplo")
    assert primeira.titulo == "Engenheiro(a) Mecânico(a) Pleno"
    assert primeira.link == "https://metalurgicaexemplo.gupy.io/job/eyJqb2JJZCI6MTAwMX0="
    assert "equipamentos industriais" in primeira.trecho
    assert primeira.localidade == "Campinas, São Paulo"
    assert primeira.publicada_em == "2026-10-08T11:04:27.057Z"


def test_vaga_da_gupy_sem_cidade_ou_data_fica_sem_localidade_e_sem_publicacao(settings):
    item = {k: v for k, v in SAMPLE["data"][0].items() if k not in ("city", "state", "publishedDate")}
    source = make_source(settings, lambda request: httpx.Response(200, json={**SAMPLE, "data": [item]}))
    job = source.search(["x"])[0]
    assert job.localidade == "" and job.publicada_em is None


def test_envia_termo_limite_e_offset_da_config(settings):
    vistos = []

    def handler(request):
        vistos.append(dict(request.url.params))
        return httpx.Response(200, json=SAMPLE)

    make_source(settings, handler).search(["Engenheiro Mecânico"])
    assert vistos[0]["jobName"] == "Engenheiro Mecânico"
    assert vistos[0]["limit"] == str(settings.gupy.page_size)
    assert vistos[0]["offset"] == "0"


def test_pagina_ate_o_total_informado(settings):
    paginas = []

    def handler(request):
        offset = int(request.url.params["offset"])
        paginas.append(offset)
        corpo = {"data": [{**SAMPLE["data"][0], "id": 2000 + offset}], "pagination": {"total": 3}}
        return httpx.Response(200, json=corpo)

    pequena = settings.__class__(**{**settings.__dict__, "gupy": settings.gupy.__class__(settings.gupy.base_url, 1, 5)})
    jobs = make_source(pequena, handler).search(["x"])
    assert paginas == [0, 1, 2]
    assert len(jobs) == 3


def test_respeita_o_teto_de_vagas_lidas(settings):
    teto = settings.limites.__class__(max_vagas_lista=1)
    limitada = settings.__class__(**{**settings.__dict__, "limites": teto})
    source = make_source(limitada, lambda request: httpx.Response(200, json=SAMPLE))
    assert len(source.search(["x"])) == 1


def test_mesma_vaga_em_duas_palavras_chave_aparece_uma_vez(settings):
    source = make_source(settings, lambda request: httpx.Response(200, json=SAMPLE))
    ids = [job.id for job in source.search(["a", "b"])]
    assert sorted(ids) == ["1001", "1002"]


def test_modalidade_e_localidade_da_config_nao_vao_para_a_api(settings):
    vistos = []

    def handler(request):
        vistos.append(dict(request.url.params))
        return httpx.Response(200, json=SAMPLE)

    busca = replace(settings.busca, localidades=["Campinas, SP"], modalidade=["remoto", "hibrido"])
    jobs = make_source(replace(settings, busca=busca), handler).search(["x"])
    assert len(vistos) == 1
    assert "workplaceType" not in vistos[0] and "location" not in vistos[0]
    assert sorted(job.id for job in jobs) == ["1001", "1002"]


def test_resposta_sem_data_e_mudanca_de_layout(settings):
    source = make_source(settings, lambda request: httpx.Response(200, json={"vagas": []}))
    with pytest.raises(SourceLayoutChanged, match="data"):
        source.search(["x"])


def test_vaga_sem_campo_obrigatorio_e_mudanca_de_layout(settings):
    corpo = {"data": [{"id": 1}], "pagination": {"total": 1}}
    source = make_source(settings, lambda request: httpx.Response(200, json=corpo))
    with pytest.raises(SourceLayoutChanged, match="name"):
        source.search(["x"])


def test_status_http_de_erro_vira_falha_http(settings):
    source = make_source(settings, lambda request: httpx.Response(503))
    with pytest.raises(SourceUnavailable, match="503"):
        source.search(["x"])


def test_falha_de_rede_vira_falha_http(settings):
    def handler(request):
        raise httpx.ConnectError("sem rede")

    with pytest.raises(SourceUnavailable):
        make_source(settings, handler).search(["x"])


def test_enrich_devolve_as_vagas_sem_tocar_na_rede(settings):
    def handler(request):
        raise AssertionError("não deveria chamar a rede")

    jobs = make_source(settings, lambda r: httpx.Response(200, json=SAMPLE)).search(["x"])
    assert make_source(settings, handler).enrich(jobs) == jobs


def test_modalidade_da_gupy_vem_do_workplace_type(settings):
    source = make_source(settings, lambda request: httpx.Response(200, json=SAMPLE))
    jobs = source.search(["x"])
    assert [j.modalidade for j in jobs[:2]] == ["presencial", "remoto"]


def test_vaga_da_gupy_com_workplace_type_ausente_ou_desconhecido_fica_sem_modalidade(settings):
    sem = {k: v for k, v in SAMPLE["data"][0].items() if k != "workplaceType"}
    outro = {**SAMPLE["data"][1], "workplaceType": "nova-forma"}
    source = make_source(settings, lambda request: httpx.Response(200, json={**SAMPLE, "data": [sem, outro]}))
    assert [j.modalidade for j in source.search(["x"])] == ["", ""]


def test_enrich_entrega_cada_vaga_ao_callback(settings):
    jobs = make_source(settings, lambda r: httpx.Response(200, json=SAMPLE)).search(["x"])
    entregues = []
    make_source(settings, lambda r: None).enrich(jobs, on_job=entregues.append)
    assert entregues == jobs
