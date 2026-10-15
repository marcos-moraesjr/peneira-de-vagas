import logging
import tomllib
from datetime import date
from pathlib import Path

import pytest

from backend.app import db
from backend.app.config import ConfigError, settings_from_dict
from backend.app.errors import DomainError
from backend.app.services import run_service, scanners
from backend.app.services.scanners import Manifest, ScannerInfo, load_manifest
from backend.app.sources.errors import SourceLayoutChanged
from backend.tests.conftest import CONFIG_PATH

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "scanners.toml"
NOW = "2026-10-20T12:00:00+00:00"
TODAY = date(2026, 10, 20)


def make_manifest(explorado_em=date(2026, 10, 14), versao="1.0.0"):
    info = ScannerInfo("linkedin", versao, explorado_em, "Claude", "docs/EXPLORACAO_PLATAFORMAS.md")
    return Manifest({"linkedin": info})


def add_run(conn, resultado, versao="1.0.0", fonte="linkedin", motivo=None, detalhe=None):
    run_id = conn.execute("INSERT INTO runs (inicio, fim, status) VALUES (?, ?, 'concluida')", (NOW, NOW)).lastrowid
    conn.execute(
        "INSERT INTO run_sources (run_id, fonte, status, motivo, detalhe, scanner_versao) VALUES (?,?,?,?,?,?)",
        (run_id, fonte, resultado, motivo, detalhe, versao),
    )
    conn.commit()


def evaluate(conn, settings, manifest=None, today=TODAY):
    return scanners.evaluate(conn, settings, manifest or make_manifest(), today)[0]


# ---------- manifesto ----------

def test_manifesto_do_projeto_cobre_as_tres_fontes_com_versao_e_data():
    manifest = load_manifest(MANIFEST_PATH)
    assert list(manifest.scanners) == ["linkedin", "indeed", "gupy"]
    for info in manifest.scanners.values():
        assert info.versao.count(".") == 2 and info.gerado_por and info.referencia
        assert info.explorado_em >= date(2026, 10, 14)


def test_manifesto_com_versao_invalida_informa_valor_e_esperado(tmp_path):
    arquivo = tmp_path / "m.toml"
    arquivo.write_text('[gupy]\nversao = "1.0"\nexplorado_em = "2026-10-14"\ngerado_por = "Claude"\nreferencia = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match=r"versao='1.0'.*MAJOR.MINOR.PATCH"):
        load_manifest(arquivo)


def test_manifesto_com_chave_ausente_informa_a_fonte(tmp_path):
    arquivo = tmp_path / "m.toml"
    arquivo.write_text('[gupy]\nversao = "1.0.0"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="gupy"):
        load_manifest(arquivo)


def test_manifesto_com_data_invalida(tmp_path):
    arquivo = tmp_path / "m.toml"
    arquivo.write_text('[gupy]\nversao = "1.0.0"\nexplorado_em = "ontem"\ngerado_por = "Claude"\nreferencia = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="explorado_em='ontem'"):
        load_manifest(arquivo)


def test_config_de_versionamento_valida_motivos(tmp_path):
    raw = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["versionamento"]["motivos_de_quebra"] = ["inventado"]
    with pytest.raises(ConfigError, match="inventado"):
        settings_from_dict(raw, CONFIG_PATH.parents[1])


# ---------- estado do scanner ----------

def test_sem_execucoes_o_scanner_esta_ok(conn, settings):
    estado = evaluate(conn, settings)
    assert (estado["status"], estado["falhas_consecutivas"]) == ("ok", 0)
    assert estado["instrucao"] is None and estado["versao"] == "1.0.0"


def test_uma_falha_de_quebra_pede_atencao(conn, settings):
    add_run(conn, "falha", motivo="seletor_nao_encontrado")
    estado = evaluate(conn, settings)
    assert (estado["status"], estado["falhas_consecutivas"]) == ("atencao", 1)
    assert estado["ultimo_motivo"] == "seletor_nao_encontrado"


def test_falhas_seguidas_no_limite_mandam_refazer_com_instrucao_para_o_claude(conn, settings):
    add_run(conn, "falha", motivo="seletor_nao_encontrado", detalhe="Nenhum card encontrado em linkedin")
    add_run(conn, "falha", motivo="seletor_nao_encontrado", detalhe="Nenhum card encontrado em linkedin")
    estado = evaluate(conn, settings)
    assert estado["status"] == "refazer"
    instrucao = estado["instrucao"]
    for trecho in ("LinkedIn", "1.0.0", "2026-10-14", "seletor_nao_encontrado", "Nenhum card encontrado",
                   "docs/EXPLORACAO_PLATAFORMAS.md", "backend/app/sources/linkedin.py", "backend/scanners.toml", "docs/SCANNERS.md", "TDD"):
        assert trecho in instrucao


def test_sucesso_interrompe_a_contagem(conn, settings):
    add_run(conn, "falha", motivo="zero_resultados")
    add_run(conn, "ok")
    add_run(conn, "falha", motivo="zero_resultados")
    assert evaluate(conn, settings)["falhas_consecutivas"] == 1


def test_bloqueio_nao_conta_como_quebra_nem_interrompe_a_contagem(conn, settings):
    add_run(conn, "falha", motivo="http_erro")
    add_run(conn, "falha", motivo="captcha")
    add_run(conn, "falha", motivo="http_erro")
    assert evaluate(conn, settings)["falhas_consecutivas"] == 2


def test_so_bloqueios_nunca_pedem_para_refazer(conn, settings):
    for motivo in ("captcha", "login", "cloudflare", "cdp_indisponivel"):
        add_run(conn, "falha", motivo=motivo)
    assert evaluate(conn, settings)["status"] == "ok"


def test_falhas_de_versao_anterior_nao_contam_depois_de_refazer(conn, settings):
    add_run(conn, "falha", versao="0.9.0", motivo="seletor_nao_encontrado")
    add_run(conn, "falha", versao="0.9.0", motivo="seletor_nao_encontrado")
    estado = evaluate(conn, settings, make_manifest(versao="1.0.0"))
    assert (estado["status"], estado["falhas_consecutivas"]) == ("ok", 0)


def test_scanner_antigo_pede_atencao_e_o_limite_e_da_config(conn, settings):
    limite = settings.versionamento.max_idade_dias
    antigo = make_manifest(explorado_em=date(2026, 10, 20).replace(year=2026, month=1, day=1))
    estado = evaluate(conn, settings, antigo)
    assert estado["status"] == "atencao" and "dias" in estado["mensagem"]
    recente = make_manifest(explorado_em=date.fromordinal(TODAY.toordinal() - limite))
    assert evaluate(conn, settings, recente)["status"] == "ok"


def test_refazer_tem_prioridade_sobre_scanner_antigo(conn, settings):
    add_run(conn, "falha", motivo="http_erro")
    add_run(conn, "falha", motivo="http_erro")
    assert evaluate(conn, settings, make_manifest(explorado_em=date(2026, 1, 1)))["status"] == "refazer"


def test_execucao_em_andamento_e_ignorada(conn, settings):
    run_id = db.create_run(conn, ["linkedin"], NOW, {"linkedin": "1.0.0"})
    assert run_id and evaluate(conn, settings)["falhas_consecutivas"] == 0


# ---------- versão gravada por execução e migração ----------

def test_execucao_grava_a_versao_do_scanner_usada(conn):
    run_id = db.create_run(conn, ["linkedin", "gupy"], NOW, {"linkedin": "1.2.3"})
    linhas = {r["fonte"]: r["scanner_versao"] for r in conn.execute("SELECT fonte, scanner_versao FROM run_sources WHERE run_id=?", (run_id,))}
    assert linhas == {"linkedin": "1.2.3", "gupy": ""}


def test_migracao_v1_para_v2_adiciona_a_coluna_e_faz_copia(conn, settings):
    conn.execute("ALTER TABLE run_sources DROP COLUMN scanner_versao")
    conn.execute("ALTER TABLE jobs DROP COLUMN localidade")  # colunas da migração 3, que também roda neste teste
    conn.execute("ALTER TABLE jobs DROP COLUMN publicada_em")
    conn.execute("DROP TABLE keywords")  # volta ao esquema 1 (migração 4 também roda neste teste)
    conn.execute("DROP TABLE conjuntos")
    conn.executescript(db.MIGRATIONS[1])
    conn.execute("UPDATE schema_version SET version=1")
    conn.commit()
    db.init_db(conn, settings)
    colunas = [row["name"] for row in conn.execute("PRAGMA table_info(run_sources)")]
    assert "scanner_versao" in colunas
    assert list(settings.geral.backup_dir.glob("*.db"))


# ---------- aviso no log ao fim da execução ----------

class BrokenSource:
    name = "linkedin"

    def search(self, termos):
        raise SourceLayoutChanged("Nenhum card encontrado em linkedin")

    def enrich(self, jobs):
        return jobs


def test_ao_atingir_o_limite_a_execucao_registra_aviso_de_refazer_no_log(conn, settings, caplog):
    manifest = make_manifest()
    add_run(conn, "falha", motivo="seletor_nao_encontrado")
    run_id = db.create_run(conn, ["linkedin"], NOW, {"linkedin": "1.0.0"})
    with caplog.at_level(logging.WARNING):
        run_service.execute_run(settings, run_id, [BrokenSource()], lambda: NOW, manifest=manifest)
    assert any("refazer" in record.message and "linkedin" in record.message for record in caplog.records)


def test_start_run_grava_as_versoes_do_manifesto(conn, settings):
    spawned = []
    run_id = run_service.start_run(conn, settings, [BrokenSource()], lambda: NOW, spawn=spawned.append, manifest=make_manifest(versao="2.0.1"))
    assert conn.execute("SELECT scanner_versao FROM run_sources WHERE run_id=?", (run_id,)).fetchone()[0] == "2.0.1"


# ---------- instrução para refazer a documentação das plataformas ----------

def full_manifest():
    return load_manifest(MANIFEST_PATH)


def test_instrucao_de_documentacao_cobre_todas_as_plataformas_com_versao_e_data():
    manifesto = full_manifest()
    texto = scanners.documentation_instruction(manifesto, None, ["Engenheiro Mecânico"])
    for rotulo in ("LinkedIn", "Indeed", "Gupy"):
        assert rotulo in texto
    assert all(info.versao in texto for info in manifesto.scanners.values()) and "2026-10-14" in texto
    assert "Google" not in texto
    for arquivo in ("backend/app/sources/linkedin.py", "backend/app/sources/indeed.py", "backend/app/sources/gupy.py"):
        assert arquivo in texto


def test_instrucao_de_documentacao_traz_termos_destino_e_o_que_registrar():
    texto = scanners.documentation_instruction(full_manifest(), None, ["Engenheiro Mecânico", "Projetista"])
    assert '"Engenheiro Mecânico"' in texto and '"Projetista"' in texto
    assert "docs/EXPLORACAO_PLATAFORMAS.md" in texto
    for item in ("seletores", "paginação", "ID estável", "filtro de data", "bloqueio"):
        assert item in texto
    assert "verificado" in texto and "não verificado" in texto


def test_instrucao_de_documentacao_repete_as_regras_de_seguranca():
    texto = scanners.documentation_instruction(full_manifest(), None, ["x"])
    assert "Chrome dedicado" in texto
    assert "candidatura" in texto and "cookies" in texto and "CAPTCHA" in texto
    assert "não contorne" in texto.lower() or "sem contornar" in texto.lower()


def test_instrucao_de_documentacao_so_documenta_e_pede_as_divergencias_antes_de_mexer_no_codigo():
    texto = scanners.documentation_instruction(full_manifest(), None, ["x"])
    assert "Não altere o código" in texto
    assert "divergências" in texto and "docs/SCANNERS.md" in texto


def test_instrucao_de_uma_so_plataforma_nao_menciona_as_outras():
    texto = scanners.documentation_instruction(full_manifest(), "gupy", ["x"])
    assert "Gupy" in texto and "backend/app/sources/gupy.py" in texto
    assert "LinkedIn" not in texto and "Indeed" not in texto


def test_instrucao_de_fonte_desconhecida_informa_valor_e_esperado():
    with pytest.raises(DomainError, match=r"fonte='orkut'.*linkedin"):
        scanners.documentation_instruction(full_manifest(), "orkut", ["x"])


def test_instrucao_sem_palavras_chave_orienta_a_usar_a_do_config():
    texto = scanners.documentation_instruction(full_manifest(), None, [])
    assert "nenhuma palavra-chave cadastrada" in texto
