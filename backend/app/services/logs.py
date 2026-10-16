"""Logs: o da aplicação (`peneira-de-vagas.log`, escrito pelo `logging` configurado em `main`) e um por execução.

Cada execução grava as próprias linhas em `<log_dir>/execucoes/execucao-<id>.log`, e o arquivo some junto com a
execução (excluir uma, limpar o histórico) ou ao limpar os logs.
"""
import logging
from collections import deque
from contextlib import contextmanager
from pathlib import Path

ARQUIVO_LOG = "peneira-de-vagas.log"
PASTA_EXECUCOES = "execucoes"
FORMATO = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def nome_do_arquivo_da_execucao(run_id: int) -> str:
    return f"execucao-{run_id}.log"


def _caminho_da_execucao(pasta: Path, run_id: int) -> Path:
    return pasta / PASTA_EXECUCOES / nome_do_arquivo_da_execucao(run_id)


def ultimas_linhas(pasta: Path, quantidade: int, run_id: int | None = None) -> list[str]:
    """Últimas `quantidade` linhas do log geral (ou o da execução `run_id`); vazia se o arquivo não existe."""
    caminho = pasta / ARQUIVO_LOG if run_id is None else _caminho_da_execucao(pasta, run_id)
    if not caminho.is_file():
        return []
    with caminho.open(encoding="utf-8", errors="replace") as arquivo:
        return [linha.rstrip("\r\n") for linha in deque(arquivo, maxlen=quantidade)]


@contextmanager
def registrar_execucao(pasta: Path, run_id: int):
    """Enquanto a execução roda, copia as linhas de log para o arquivo dela."""
    caminho = _caminho_da_execucao(pasta, run_id)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(caminho, encoding="utf-8")
    handler.setFormatter(logging.Formatter(FORMATO))
    raiz = logging.getLogger()
    raiz.addHandler(handler)
    try:
        yield
    finally:
        raiz.removeHandler(handler)
        handler.close()


def remover_execucao(pasta: Path, run_id: int) -> None:
    _caminho_da_execucao(pasta, run_id).unlink(missing_ok=True)


def remover_execucoes(pasta: Path) -> int:
    """Apaga os logs de todas as execuções; devolve quantos arquivos saíram."""
    removidos = 0
    for arquivo in (pasta / PASTA_EXECUCOES).glob("execucao-*.log"):
        arquivo.unlink(missing_ok=True)
        removidos += 1
    return removidos


def limpar(pasta: Path) -> int:
    """Esvazia o log geral (o arquivo continua aberto pelo `logging`) e apaga os das execuções."""
    caminho = pasta / ARQUIVO_LOG
    if caminho.is_file():
        caminho.write_text("", encoding="utf-8")
    return remover_execucoes(pasta)
