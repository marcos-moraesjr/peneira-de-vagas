from fastapi import APIRouter, Depends

from ..config import Settings
from ..deps import get_settings
from ..schemas import LogsCleared, LogsOut
from ..services import logs

router = APIRouter()


@router.get("/logs", response_model=LogsOut)
def get_logs(execucao_id: int | None = None, settings: Settings = Depends(get_settings)) -> dict:
    """Fim do log da aplicação, ou o da execução `execucao_id` (`[api] logs_linhas` linhas, as mais recentes por último)."""
    arquivo = logs.ARQUIVO_LOG if execucao_id is None else logs.nome_do_arquivo_da_execucao(execucao_id)
    return {"arquivo": arquivo, "linhas": logs.ultimas_linhas(settings.geral.log_dir, settings.api.logs_linhas, execucao_id)}


@router.delete("/logs", response_model=LogsCleared)
def clear_logs(settings: Settings = Depends(get_settings)) -> LogsCleared:
    """Esvazia o log da aplicação e apaga os logs de todas as execuções."""
    return LogsCleared(execucoes_removidas=logs.limpar(settings.geral.log_dir))
