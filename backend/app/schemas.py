"""Contratos Pydantic da API (viram o OpenAPI de onde saem os tipos do front)."""
from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    db: str


class RunIn(BaseModel):
    fontes: list[str] | None = None  # None = todas as fontes


class RunStarted(BaseModel):
    id: int


class RunsCleared(BaseModel):
    removidas: int


class RunSourceOut(BaseModel):
    fonte: str
    status: str
    motivo: str | None
    detalhe: str | None
    lidas: int
    aprovadas: int
    novas: int
    scanner_versao: str


class VerificationOut(BaseModel):
    fontes: list[str]


class ScannerOut(BaseModel):
    fonte: str
    versao: str
    explorado_em: str
    gerado_por: str
    referencia: str
    status: str
    falhas_consecutivas: int
    ultimo_motivo: str | None
    mensagem: str
    instrucao: str | None


class RunOut(BaseModel):
    id: int
    inicio: str
    fim: str | None
    status: str
    fontes: list[RunSourceOut]


class JobOut(BaseModel):
    id: int
    fonte: str
    id_da_vaga: str
    titulo: str
    empresa: str
    link: str
    trecho: str
    pontos: int
    run_id: int | None
    encontrada_em: str
    localidade: str
    publicada_em: str | None
    visto: bool


class JobsPage(BaseModel):
    items: list[JobOut]
    total: int


class SeenIn(BaseModel):
    visto: bool


class MarkSeenIn(BaseModel):
    fonte: str | None = None
    q: str | None = None
    max_dias: int | None = None


class MarkSeenOut(BaseModel):
    atualizadas: int


class JobsCleared(BaseModel):
    removidas: int


class ConjuntoIn(BaseModel):
    nome: str


class ConjuntoOut(BaseModel):
    id: int
    nome: str
    ativo: bool


class KeywordIn(BaseModel):
    termo: str
    tipo: str


class KeywordOut(BaseModel):
    id: int
    termo: str
    tipo: str
    criada_em: str


class ConfigBusca(BaseModel):
    localidades: list[str]
    modalidade: list[str]
    janela_horas: int
    keyword_max_length: int


class ConfigFiltro(BaseModel):
    peso_titulo: int
    peso_descricao: int
    min_score: int
    trecho_max_chars: int


class ConfigLimites(BaseModel):
    max_paginas_detalhe: int
    max_vagas_lista: int


class ConfigRitmo(BaseModel):
    pausa_min_s: float
    pausa_max_s: float
    rolagem_min_s: float
    rolagem_max_s: float


class ConfigNavegador(BaseModel):
    abas_paralelas: bool


class ConfigApi(BaseModel):
    jobs_page_size: int
    poll_interval_ms: int


class ConfigOut(BaseModel):
    busca: ConfigBusca
    filtro: ConfigFiltro
    limites: ConfigLimites
    ritmo: ConfigRitmo
    navegador: ConfigNavegador
    api: ConfigApi


class BrowserOut(BaseModel):
    aberto: bool


class BrowserOpenOut(BaseModel):
    estado: str


class InstructionOut(BaseModel):
    instrucao: str


