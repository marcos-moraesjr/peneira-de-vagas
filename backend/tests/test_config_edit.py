import tomllib

import pytest

from backend.app.errors import DomainError
from backend.app.services.config_edit import write_values

TOML = """# cabeçalho
[busca]
localidade = "São Paulo # centro"   # local da busca
janela_dias = 1
[filtro]
min_score = 3     # mínimo
[ritmo]
pausa_min_s = 2.0
[outra]
min_score = 99
"""


def _ler(path):
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_troca_so_o_valor_e_preserva_comentarios_e_outras_secoes(tmp_path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(TOML, encoding="utf-8")
    write_values(
        arquivo,
        {"busca": {"localidade": "Campinas", "janela_dias": 2}, "filtro": {"min_score": 5}, "ritmo": {"pausa_min_s": 1.5}},
    )
    texto = arquivo.read_text(encoding="utf-8")
    assert '# local da busca' in texto and "# mínimo" in texto and "# cabeçalho" in texto
    dados = _ler(arquivo)
    assert dados["busca"] == {"localidade": "Campinas", "janela_dias": 2}
    assert dados["filtro"]["min_score"] == 5
    assert dados["ritmo"]["pausa_min_s"] == 1.5
    assert dados["outra"]["min_score"] == 99


def test_lista_de_textos_e_gravada_como_array_e_lida_de_volta(tmp_path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text("[busca]\nmodalidade = []   # vazio = todas\nx = 1\n", encoding="utf-8")
    write_values(arquivo, {"busca": {"modalidade": ["remoto", "hibrido"]}})
    assert "# vazio = todas" in arquivo.read_text(encoding="utf-8")
    assert _ler(arquivo)["busca"] == {"modalidade": ["remoto", "hibrido"], "x": 1}
    write_values(arquivo, {"busca": {"modalidade": []}})
    assert _ler(arquivo)["busca"]["modalidade"] == []


def test_aspas_e_barras_no_texto_sao_escapadas(tmp_path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(TOML, encoding="utf-8")
    write_values(arquivo, {"busca": {"localidade": 'Rua "A" \\ B'}})
    assert _ler(arquivo)["busca"]["localidade"] == 'Rua "A" \\ B'


def test_chave_inexistente_nao_altera_o_arquivo(tmp_path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(TOML, encoding="utf-8")
    with pytest.raises(DomainError, match="busca.nao_existe"):
        write_values(arquivo, {"filtro": {"min_score": 7}, "busca": {"nao_existe": 1}})
    assert arquivo.read_text(encoding="utf-8") == TOML


def test_chave_ausente_e_acrescentada_ao_fim_da_secao_quando_pedido(tmp_path):
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(TOML, encoding="utf-8")
    write_values(arquivo, {"filtro": {"min_score": 7, "nova": 15}}, adicionar_ausentes=True)
    dados = _ler(arquivo)
    assert dados["filtro"] == {"min_score": 7, "nova": 15}
    assert dados["ritmo"] == {"pausa_min_s": 2.0} and dados["outra"] == {"min_score": 99}
    assert "# mínimo" in arquivo.read_text(encoding="utf-8")
