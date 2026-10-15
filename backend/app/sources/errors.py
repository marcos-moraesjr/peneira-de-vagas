"""Falhas explícitas de fonte. Cada uma carrega o motivo padronizado exibido no front."""

MOTIVOS = (
    "captcha",
    "login",
    "cloudflare",
    "seletor_nao_encontrado",
    "zero_resultados",
    "cdp_indisponivel",
    "http_erro",
    "interrompida",
    "erro_interno",
)


class SourceError(Exception):
    motivo = "erro_interno"

    def __init__(self, detalhe: str = "", motivo: str | None = None):
        super().__init__(detalhe or self.motivo)
        if motivo is not None:
            if motivo not in MOTIVOS:
                raise ValueError(f"Motivo inválido: {motivo!r} (esperado um de {MOTIVOS})")
            self.motivo = motivo
        self.detalhe = detalhe


class SourceBlocked(SourceError):
    """CAPTCHA, login inesperado ou Cloudflare. Nunca contornado."""

    motivo = "captcha"


class SourceLayoutChanged(SourceError):
    motivo = "seletor_nao_encontrado"


class SourceEmpty(SourceError):
    motivo = "zero_resultados"


class SourceUnavailable(SourceError):
    motivo = "http_erro"
