from fastapi import APIRouter, Depends, Request

from ..config import Settings
from ..deps import get_settings
from ..schemas import AtualizacaoOut
from ..services import atualizacao

router = APIRouter()


@router.get("/atualizacao", response_model=AtualizacaoOut)
def get_update(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """Há Release mais nova no GitHub? Só consulta quando instalado e `[atualizacao] verificar = true`."""
    state = request.app.state
    return atualizacao.check(state.app_version(), settings.atualizacao, state.latest_fetch)
