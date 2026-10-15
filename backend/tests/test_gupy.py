import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from backend.app.sources.errors import SourceLayoutChanged, SourceUnavailable
from backend.app.sources.gupy import GupySource

SAMPLE = json.loads((Path(__file__).parent / "samples" / "gupy_jobs.json").read_text(encoding="utf-8"))


def make_source(settings, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GupySource(settings, client=client, clock=lambda: datetime(2022, 3, 1, tzinfo=timezone.utc))


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


def test_gupy_descarta_vaga_publicada_antes_da_janela_de_recencia(settings):
    recente = {**SAMPLE["data"][0], "id": 1003, "publishedDate": "2026-10-12T12:00:00.000Z"}
    antiga = {**SAMPLE["data"][1], "publishedDate": "2022-03-01T10:00:00.000Z"}
    source = GupySource(
        replace(settings, busca=replace(settings.busca, janela_dias=3)),
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, json={"data": [recente, antiga], "pagination": {"total": 2}}
        ))),
        clock=lambda: datetime(2026, 10, 15, 12, tzinfo=timezone.utc),
    )

    assert [job.id for job in source.search(["x"])] == ["1003"]


def test_cada_vaga_guarda_a_palavra_chave_que_a_trouxe_e_repetida_fica_com_a_primeira(settings):
    def handler(request):
        termo = request.url.params["jobName"]
        itens = [SAMPLE["data"][0]] if termo == "a" else SAMPLE["data"]
        return httpx.Response(200, json={"data": itens, "pagination": {"total": len(itens)}})

    jobs = make_source(settings, handler).search(["a", "b"])
    assert [(j.id, j.palavra_chave) for j in jobs] == [("1001", "a"), ("1002", "b")]


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


def com_paginas(settings, paginas, page_size=1):
    gupy = replace(settings.gupy, page_size=page_size)
    return replace(settings, gupy=gupy, limites=replace(settings.limites, max_paginas_por_termo=paginas))


def paginas_por_termo(vistos, total=10, base=None):
    """Cada página traz 1 vaga (id = base do termo + offset, base padrão 1000); `vistos` registra (termo, offset)."""
    base = base or {}

    def handler(request):
        termo, offset = request.url.params["jobName"], int(request.url.params["offset"])
        vistos.append((termo, offset))
        item = {**SAMPLE["data"][0], "id": base.get(termo, 1000) + offset}
        return httpx.Response(200, json={"data": [item], "pagination": {"total": total}})

    return handler


def test_abre_so_o_numero_de_paginas_configurado_na_gupy(settings):
    vistos = []
    jobs = make_source(com_paginas(settings, 2), paginas_por_termo(vistos)).search(["a"])
    assert vistos == [("a", 0), ("a", 1)]
    assert [job.id for job in jobs] == ["1000", "1001"]


def test_cada_termo_pagina_por_conta_propria_na_gupy(settings):
    vistos = []
    handler = paginas_por_termo(vistos, base={"a": 1000, "b": 2000})
    jobs = make_source(com_paginas(settings, 2), handler).search(["a", "b"])
    assert vistos == [("a", 0), ("a", 1), ("b", 0), ("b", 1)]
    assert [job.id for job in jobs] == ["1000", "1001", "2000", "2001"]


def test_vaga_achada_por_dois_termos_aparece_uma_vez_na_gupy(settings):
    jobs = make_source(com_paginas(settings, 1), paginas_por_termo([])).search(["a", "b"])
    assert [job.id for job in jobs] == ["1000"]


def test_mesma_vaga_em_duas_palavras_chave_aparece_uma_vez(settings):
    source = make_source(settings, lambda request: httpx.Response(200, json=SAMPLE))
    ids = [job.id for job in source.search(["a", "b"])]
    assert sorted(ids) == ["1001", "1002"]


def test_modalidade_vai_para_a_api_mas_localidade_nao(settings):
    vistos = []

    def handler(request):
        vistos.append(dict(request.url.params))
        return httpx.Response(200, json=SAMPLE)

    busca = replace(settings.busca, localidades=["Campinas, SP"], modalidade=["remoto", "hibrido"])
    jobs = make_source(replace(settings, busca=busca), handler).search(["x"])
    assert len(vistos) == 1
    assert vistos[0]["workplaceType"] == "remote" and "location" not in vistos[0]
    assert sorted(job.id for job in jobs) == ["1001", "1002"]


def test_modalidade_da_config_vai_para_a_api_da_gupy(settings):
    vistos = []

    def handler(request):
        vistos.append(dict(request.url.params))
        return httpx.Response(200, json=SAMPLE)

    busca = replace(settings.busca, modalidade=["remoto"])
    make_source(replace(settings, busca=busca), handler).search(["x"])
    assert vistos[0]["workplaceType"] == "remote"


def test_gupy_omite_localidade_na_api_e_deixa_o_filtro_local_decidir(settings):
    vistos = []

    def handler(request):
        vistos.append(dict(request.url.params))
        return httpx.Response(200, json=SAMPLE)

    busca = replace(settings.busca, localidades=["Campinas, SP"])
    jobs = make_source(replace(settings, busca=busca), handler).search(["x"])
    assert "location" not in vistos[0]
    assert len(jobs) == 2


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
