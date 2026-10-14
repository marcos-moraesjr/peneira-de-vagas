from fastapi import APIRouter, Depends, Request

from ..config import Settings
from ..deps import get_settings
from ..schemas import BrowserOpenOut, BrowserOut
from ..services import chrome

router = APIRouter()


@router.get("/browser", response_model=BrowserOut)
def browser_status(request: Request) -> BrowserOut:
    """Se o Chrome dedicado (LinkedIn/Indeed) está aberto e respondendo."""
    return BrowserOut(aberto=request.app.state.chrome_probe())


@router.post("/browser/open", response_model=BrowserOpenOut)
def open_browser(request: Request, settings: Settings = Depends(get_settings)) -> BrowserOpenOut:
    """Abre o Chrome dedicado (perfil próprio, porta de depuração só local), se ainda não estiver aberto."""
    state = chrome.open_chrome(settings, request.app.state.chrome_probe, request.app.state.chrome_launcher)
    return BrowserOpenOut(estado=state)
