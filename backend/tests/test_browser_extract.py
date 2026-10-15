"""Extração dos cards sobre HTML salvo, com Chrome local headless (sem rede). Pulado se o Chrome faltar."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from backend.app.sources.browser import PlaywrightNavigator
from backend.app.sources.indeed import IndeedSite
from backend.app.sources.linkedin import LinkedInSite

SAMPLES = Path(__file__).parent / "samples"
pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def page():
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(channel="chrome", headless=True)
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"Chrome local indisponível: {error}")
    yield browser.new_page()
    browser.close()
    playwright.stop()


def load(page, name):
    page.set_content((SAMPLES / name).read_text(encoding="utf-8"))
    return PlaywrightNavigator(page, timeout_ms=5000)


def test_linkedin_le_cards_rolando_um_a_um_e_ignora_o_nao_renderizado(page, settings):
    site = LinkedInSite(settings)
    pausas = []
    raws = load(page, "linkedin_list.html").extract_progressive(site.extract_js, site.card_selector, lambda: pausas.append(1))
    jobs = [job for job in map(site.to_job, raws) if job]
    assert [j.id for j in jobs] == ["3900000001", "3900000002"]
    assert jobs[0].titulo == "Engenheiro Mecânico Pleno"
    assert jobs[0].empresa == "Metalúrgica Exemplo"
    assert jobs[0].trecho == "Campinas, São Paulo, Brasil (Presencial)"
    assert jobs[0].link == "https://www.linkedin.com/jobs/view/3900000001/"
    assert jobs[0].localidade == "Campinas, São Paulo, Brasil (Presencial)"
    assert len(pausas) == 1  # apenas o card ainda não renderizado precisa de rolagem


def test_linkedin_card_que_renderiza_depois_de_rolar_e_aproveitado(page, settings):
    site = LinkedInSite(settings)
    page.set_content(
        """<ul><li data-occludable-job-id="77"></li></ul>
        <script>
          const li = document.querySelector('li');
          li.addEventListener('mouseenter', () => {});
          window.fill = () => { li.innerHTML = '<a href="/jobs/view/77/"><strong>Projetista Mecânico</strong></a>'; };
        </script>"""
    )
    navigator = PlaywrightNavigator(page, timeout_ms=5000)
    raws = navigator.extract_progressive(site.extract_js, site.card_selector, lambda: page.evaluate("window.fill()"))
    assert [j.titulo for j in map(site.to_job, raws) if j] == ["Projetista Mecânico"]


def test_linkedin_abre_o_painel_com_id_sem_quebrar_o_seletor(page, settings):
    page.set_content(
        """<ul><li data-occludable-job-id="4477569627">
        <a href="/jobs/view/4477569627/"><strong>Vaga</strong></a></li></ul>
        <script>window.opened = false; const link = document.querySelector('a'); link.addEventListener('click', (event) => { event.preventDefault(); window.opened = true; });</script>"""
    )
    site = LinkedInSite(settings)
    script = site.open_detail_js.replace("__JOB_ID__", json.dumps("4477569627"))

    assert PlaywrightNavigator(page, timeout_ms=5000).open_detail(script) is True
    assert page.evaluate("window.opened") is True


def test_indeed_extrai_cards_da_lista_salva(page, settings):
    site = IndeedSite(settings)
    jobs = [site.to_job(raw) for raw in load(page, "indeed_list.html").extract(site.extract_js)]
    assert [j.id for j in jobs] == ["a1b2c3d4e5f60001", "a1b2c3d4e5f60002"]
    assert jobs[0].titulo == "Engenheiro Mecânico de Projetos"
    assert jobs[0].empresa == "Fábrica Exemplo"
    assert jobs[0].trecho == "Tempo integral | Projetos mecânicos e manutenção industrial"
    assert jobs[0].link == "https://br.indeed.com/viewjob?jk=a1b2c3d4e5f60001"
    assert [j.localidade for j in jobs] == ["São Paulo, SP", "Belo Horizonte, MG"]


def test_indeed_ignora_card_isca_invisivel_da_listagem(page, settings):
    """Observado na listagem real: cards 0x0 com id falso e link `/viewjob` que não aparecem ao usuário.
    Clicá-los navega para fora da listagem e o painel das vagas seguintes não abre."""
    page.set_content(
        """<div class="job_seen_beacon"><a data-jk="a1b2c3d4e5f60001" href="/rc/clk?jk=a1b2c3d4e5f60001"><span title="Vaga Real">Vaga Real</span></a></div>
        <div class="job_seen_beacon" style="width:0;height:0;overflow:hidden"><a data-jk="f1e2d3c4b5a67890" href="/viewjob?jk=f1e2d3c4b5a67890"><span title="Vaga Real">Vaga Real</span></a></div>
        <div class="job_seen_beacon"><a data-jk="a1b2c3d4e5f60002" href="/rc/clk?jk=a1b2c3d4e5f60002"><span title="Outra Vaga">Outra Vaga</span></a></div>"""
    )
    site = IndeedSite(settings)
    raws = PlaywrightNavigator(page, timeout_ms=5000).extract(site.extract_js)
    assert [raw["id"] for raw in raws] == ["a1b2c3d4e5f60001", "a1b2c3d4e5f60002"]


def test_indeed_le_a_descricao_do_painel_na_estrutura_atual(page, settings):
    """Painel observado em 15/10/2026: sem `#jobDescriptionText`; a descrição fica em `.simple-job-description-html`."""
    page.set_content(
        """<div class="jobsearch-RightPane"><div data-testid="viewjob-job-content">
        <h4 data-testid="vj-job-description-heading">Descrição completa da vaga</h4>
        <div class="css-g5y9jx"><div class="react-native-html-content simple-job-description-html">Ensino superior em engenharia.\nExperiência com CAD.</div></div>
        <div data-testid="vj-report-job">Denunciar anúncio</div></div></div>"""
    )
    site = IndeedSite(settings)
    text = PlaywrightNavigator(page, timeout_ms=5000).first_text(site.detail_selectors)
    assert "Experiência com CAD" in text
    assert "Denunciar" not in text


def test_indeed_abre_o_painel_do_card_sem_navegar_para_a_vaga(page, settings):
    page.set_content(
        """<div class="job_seen_beacon"><a class="jcs-JobTitle" data-jk="a1b2c3d4" href="/viewjob?jk=a1b2c3d4">Vaga</a></div>
        <script>
          window.opened = false;
          document.querySelector('a').addEventListener('click', (event) => {
            event.preventDefault();
            window.opened = true;
          });
        </script>"""
    )
    site = IndeedSite(settings)
    script = site.open_detail_js.replace("__JOB_ID__", json.dumps("a1b2c3d4"))

    assert PlaywrightNavigator(page, timeout_ms=5000).open_detail(script) is True
    assert page.evaluate("window.opened") is True


def test_indeed_abre_o_painel_quando_o_site_remove_a_classe_do_link(page, settings):
    """A classe visual muda com frequência; o id estável da vaga é data-jk."""
    page.set_content(
        """<div class="job_seen_beacon"><a data-jk="a1b2c3d4" href="/viewjob?jk=a1b2c3d4">Vaga</a></div>
        <script>
          window.opened = false;
          document.querySelector('a').addEventListener('click', (event) => {
            event.preventDefault();
            window.opened = true;
          });
        </script>"""
    )
    site = IndeedSite(settings)
    script = site.open_detail_js.replace("__JOB_ID__", json.dumps("a1b2c3d4"))

    assert PlaywrightNavigator(page, timeout_ms=5000).open_detail(script) is True
    assert page.evaluate("window.opened") is True


def test_pagina_sem_cards_devolve_lista_vazia(page, settings):
    page.set_content("<html><body>nada</body></html>")
    navigator = PlaywrightNavigator(page, timeout_ms=5000)
    assert navigator.extract(LinkedInSite(settings).extract_js) == []
    assert navigator.extract_progressive(LinkedInSite(settings).extract_js, "li[data-occludable-job-id]", lambda: None) == []


def test_first_text_devolve_o_primeiro_seletor_que_existe(page):
    page.set_content("<div id='b'>segundo</div><div id='a'>primeiro</div>")
    navigator = PlaywrightNavigator(page, timeout_ms=5000)
    assert navigator.first_text(["#nao-existe", "#a", "#b"]) == "primeiro"
    assert navigator.first_text(["#nao-existe"]) == ""


def test_first_text_le_texto_completo_mesmo_quando_a_interface_o_limita(page):
    page.set_content(
        """<p data-testid='expandable-text-box' style='max-height: 3rem; overflow: hidden'>
        Parte visível. Requisitos completos e benefícios que ficam atrás do botão mais.
        </p><button>mais</button>"""
    )
    navigator = PlaywrightNavigator(page, timeout_ms=5000)

    assert "Requisitos completos" in navigator.first_text(['[data-testid="expandable-text-box"]'])
