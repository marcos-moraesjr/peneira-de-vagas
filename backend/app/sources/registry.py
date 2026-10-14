"""Fontes ativas, na ordem de execução (navegador primeiro, API por último)."""
from ..config import Settings
from .browser import BrowserSource, make_pause, playwright_session
from .google import GoogleSite, GoogleSource
from .gupy import GupySource
from .indeed import IndeedSite
from .linkedin import LinkedInSite


def build_sources(settings: Settings) -> list:
    ritmo = settings.ritmo
    pause = make_pause(ritmo.pausa_min_s, ritmo.pausa_max_s)
    scroll_pause = make_pause(ritmo.rolagem_min_s, ritmo.rolagem_max_s)

    def session():
        return playwright_session(settings)

    return [
        BrowserSource(LinkedInSite(settings), settings, session, pause, scroll_pause),
        BrowserSource(IndeedSite(settings), settings, session, pause, scroll_pause),
        GoogleSource(GoogleSite(settings), settings, session, pause, scroll_pause),
        GupySource(settings),
    ]
