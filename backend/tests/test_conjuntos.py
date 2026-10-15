import sqlite3

import pytest

from backend.app import db
from backend.app.db import init_db
from backend.app.errors import DomainError, NotFound
from backend.app.services import conjuntos, keywords

NOW = "2026-10-14T12:00:00+00:00"


def test_banco_novo_tem_um_conjunto_padrao_ativo_com_as_palavras_semeadas(conn):
    todos = conjuntos.list_all(conn)
    assert [(c["nome"], c["ativo"]) for c in todos] == [("Padrão", True)]
    assert [k["termo"] for k in keywords.list_all(conn, "busca")] == ["Engenheiro Mecânico"]


def test_migracao_4_move_exclusoes_existentes_para_o_conjunto_padrao_e_a_8_apaga_a_busca_antiga(settings, abrir_conexao):
    arquivo = settings.geral.db_path
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    antigo = sqlite3.connect(arquivo)
    antigo.executescript(db.MIGRATIONS[1] + db.MIGRATIONS[2] + db.MIGRATIONS[3])
    antigo.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    antigo.execute("INSERT INTO schema_version VALUES (3)")
    antigo.execute("INSERT INTO meta VALUES ('seeded', '1')")
    antigo.execute("INSERT INTO keywords (termo, termo_normalizado, tipo, criada_em) VALUES ('Projetista','projetista','busca','x')")
    antigo.execute("INSERT INTO keywords (termo, termo_normalizado, tipo, criada_em) VALUES ('estágio','estagio','exclusao','x')")
    antigo.commit()
    antigo.close()
    connection = abrir_conexao(arquivo)
    init_db(connection, settings)
    assert [c["nome"] for c in conjuntos.list_all(connection)] == ["Padrão"]
    assert keywords.list_all(connection, "busca") == []  # a migração 8 apaga as palavras de busca antigas
    assert [k["termo"] for k in keywords.list_all(connection, "exclusao")] == ["estágio"]


def test_criar_conjunto_o_ativa_e_comeca_vazio(conn, settings):
    novo = conjuntos.add(conn, settings, "  Tecnologia ", NOW)
    assert (novo["nome"], novo["ativo"]) == ("Tecnologia", True)
    assert [c["nome"] for c in conjuntos.list_all(conn) if c["ativo"]] == ["Tecnologia"]
    assert keywords.list_all(conn) == []


def test_palavras_ficam_no_conjunto_ativo_e_o_mesmo_termo_vale_em_outro(conn, settings):
    padrao = conjuntos.list_all(conn)[0]
    conjuntos.add(conn, settings, "Tecnologia", NOW)
    keywords.add(conn, settings, "Engenheiro Mecânico", "busca", NOW)  # mesmo termo do Padrão, outro conjunto
    keywords.add(conn, settings, "Cientista de dados", "busca", NOW)
    assert [k["termo"] for k in keywords.list_all(conn, "busca")] == ["Engenheiro Mecânico", "Cientista de dados"]
    conjuntos.activate(conn, padrao["id"])
    assert [k["termo"] for k in keywords.list_all(conn, "busca")] == ["Engenheiro Mecânico"]


def test_ativar_inexistente_levanta_not_found(conn):
    with pytest.raises(NotFound):
        conjuntos.activate(conn, 999)


@pytest.mark.parametrize("nome", ["   ", "x" * 81, "padrão"])
def test_nome_invalido_ou_duplicado_levanta_domain_error(conn, settings, nome):
    with pytest.raises(DomainError):
        conjuntos.add(conn, settings, nome, NOW)


def test_remover_conjunto_apaga_suas_palavras_e_ativa_outro(conn, settings):
    padrao = conjuntos.list_all(conn)[0]
    tec = conjuntos.add(conn, settings, "Tecnologia", NOW)
    keywords.add(conn, settings, "Dados", "busca", NOW)
    conjuntos.remove(conn, tec["id"])
    assert [(c["id"], c["ativo"]) for c in conjuntos.list_all(conn)] == [(padrao["id"], True)]
    assert conn.execute("SELECT COUNT(*) FROM keywords WHERE termo='Dados'").fetchone()[0] == 0


def test_nao_remove_o_unico_conjunto_nem_um_inexistente(conn):
    unico = conjuntos.list_all(conn)[0]
    with pytest.raises(DomainError):
        conjuntos.remove(conn, unico["id"])
    with pytest.raises(NotFound):
        conjuntos.remove(conn, 999)


def test_renomear_conjunto_mantem_palavras_e_ativo(conn, settings):
    padrao = conjuntos.list_all(conn)[0]
    renomeado = conjuntos.rename(conn, settings, padrao["id"], "  Engenharia   mecânica ")
    assert renomeado == {"id": padrao["id"], "nome": "Engenharia mecânica", "ativo": True}
    assert [(c["nome"], c["ativo"]) for c in conjuntos.list_all(conn)] == [("Engenharia mecânica", True)]
    assert [k["termo"] for k in keywords.list_all(conn, "busca")] == ["Engenheiro Mecânico"]


def test_renomear_so_a_caixa_ou_o_acento_do_proprio_nome_e_permitido(conn, settings):
    padrao = conjuntos.list_all(conn)[0]
    assert conjuntos.rename(conn, settings, padrao["id"], "PADRAO")["nome"] == "PADRAO"


@pytest.mark.parametrize("nome", ["   ", "x" * 81, "tecnologia"])
def test_renomear_para_nome_invalido_ou_de_outro_conjunto_levanta_domain_error(conn, settings, nome):
    padrao = conjuntos.list_all(conn)[0]
    conjuntos.add(conn, settings, "Tecnologia", NOW)
    with pytest.raises(DomainError):
        conjuntos.rename(conn, settings, padrao["id"], nome)
    assert conjuntos.list_all(conn)[0]["nome"] == "Padrão"


def test_renomear_inexistente_levanta_not_found(conn, settings):
    with pytest.raises(NotFound):
        conjuntos.rename(conn, settings, 999, "Qualquer")


def test_copiar_conjunto_leva_todas_as_palavras_ativa_a_copia_e_nao_altera_o_original(conn, settings):
    padrao = conjuntos.list_all(conn)[0]
    keywords.add(conn, settings, "Projetista", "busca", NOW)
    keywords.add(conn, settings, "AutoCAD", "ranking", NOW)
    keywords.add(conn, settings, "estágio", "exclusao", NOW)
    copia = conjuntos.duplicate(conn, settings, padrao["id"], "  Cópia   do padrão ", NOW)
    assert (copia["nome"], copia["ativo"]) == ("Cópia do padrão", True)
    assert copia["id"] != padrao["id"]
    assert [(c["nome"], c["ativo"]) for c in conjuntos.list_all(conn)] == [("Padrão", False), ("Cópia do padrão", True)]
    por_tipo = lambda tipo: [k["termo"] for k in keywords.list_all(conn, tipo)]  # noqa: E731 - conjunto ativo = a cópia
    assert (por_tipo("busca"), por_tipo("ranking"), por_tipo("exclusao")) == (["Engenheiro Mecânico", "Projetista"], ["AutoCAD"], ["estágio"])
    keywords.add(conn, settings, "Só na cópia", "busca", NOW)
    conjuntos.activate(conn, padrao["id"])
    assert [k["termo"] for k in keywords.list_all(conn, "busca")] == ["Engenheiro Mecânico", "Projetista"]


def test_copiar_com_nome_invalido_ou_repetido_ou_de_conjunto_inexistente_nao_cria_nada(conn, settings):
    padrao = conjuntos.list_all(conn)[0]
    for nome in ("   ", "x" * 81, "padrão"):
        with pytest.raises(DomainError):
            conjuntos.duplicate(conn, settings, padrao["id"], nome, NOW)
    with pytest.raises(NotFound):
        conjuntos.duplicate(conn, settings, 999, "Qualquer", NOW)
    assert [(c["nome"], c["ativo"]) for c in conjuntos.list_all(conn)] == [("Padrão", True)]
