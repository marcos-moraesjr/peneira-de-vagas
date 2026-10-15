"""Traduz critérios canônicos da busca para os parâmetros de cada plataforma."""
from ..config import Settings

ESTADOS_BRASIL = (
    "Acre", "Alagoas", "Amapá", "Amazonas", "Bahia", "Ceará", "Distrito Federal",
    "Espírito Santo", "Goiás", "Maranhão", "Mato Grosso", "Mato Grosso do Sul",
    "Minas Gerais", "Pará", "Paraíba", "Paraná", "Pernambuco", "Piauí",
    "Rio de Janeiro", "Rio Grande do Norte", "Rio Grande do Sul", "Rondônia",
    "Roraima", "Santa Catarina", "São Paulo", "Sergipe", "Tocantins",
)


def location(settings: Settings) -> str:
    return next((item.strip() for item in settings.busca.localidades if item.strip()), "")


def modality(settings: Settings) -> str:
    return next(iter(settings.busca.modalidade), "")


def platform_params(platform: str, settings: Settings) -> dict[str, str]:
    """Converte localidade para o nome de parâmetro observado na plataforma."""
    value = location(settings)
    params: dict[str, str] = {}
    location_parameter = {"linkedin": "location", "indeed": "l"}.get(platform)
    if value and location_parameter:
        params[location_parameter] = value
    selected = modality(settings)
    if selected == "remoto":
        if platform == "linkedin": params["f_WT"] = "1"
        if platform == "gupy": params["workplaceType"] = "remote"
    elif selected == "presencial":
        if platform == "linkedin": params["f_WT"] = "2"
        if platform == "gupy": params["workplaceType"] = "on-site"
    elif selected == "hibrido":
        if platform == "linkedin": params["f_WT"] = "3"
        if platform == "gupy": params["workplaceType"] = "hybrid"
    return params
