from dataclasses import asdict

from fastapi import APIRouter, Depends

from ..config import Settings
from ..deps import get_settings
from ..schemas import ConfigOut

router = APIRouter()


@router.get("/config", response_model=ConfigOut)
def get_config(settings: Settings = Depends(get_settings)) -> dict:
    """Parâmetros em vigor, só leitura; caminhos e URLs internas ficam de fora."""
    return {name: asdict(getattr(settings, name)) for name in ("busca", "filtro", "limites", "ritmo", "api")}
