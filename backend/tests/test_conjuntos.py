import sqlite3

import pytest

from backend.app import db
from backend.app.db import connect, init_db
from backend.app.errors import DomainError, NotFound
from backend.app.services import conjuntos, keywords

NOW = "2026-10-14T12:00:00+00:00"


def test_banco_novo_tem_um_conjunto_padrao_ativo_com_as_palavras_semeadas(conn):
    todos = conjuntos.list_all(conn)
    assert [(c["nome"], c["ativo"]) for c in todos] == [("Padrão", True)]
    assert [k["termo"] for k in keywords.list_all(conn, "busca")] == ["Engenheiro Mecânico"]


def test_migracao_4_move_palavras_existentes_para_o_conjunto_padrao(settings):
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
    connection = connect(arquivo)
    init_db(connection, settings)
    assert [c["nome"] for c in conjuntos.list_all(connection)] == ["Padrão"]
    assert [k["termo"] for k in keywords.list_all(connection, "busca")] == ["Projetista"]
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
