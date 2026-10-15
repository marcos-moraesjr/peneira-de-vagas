"""Portão de verificação: a fonte bloqueada espera o usuário concluir a verificação à mão e confirmar.

Nada aqui resolve nem contorna o bloqueio: quem o resolve é o usuário, no Chrome dedicado."""
import threading

from .errors import SourceInterrupted


class VerificationGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._waiting: dict[str, threading.Event] = {}
        self._cancelled = threading.Event()

    def wait(self, fonte: str, timeout_s: float) -> bool:
        """Bloqueia até o usuário confirmar (True) ou o tempo esgotar (False); cancelar levanta `SourceInterrupted`."""
        released = threading.Event()
        with self._lock:
            self._waiting[fonte] = released
        try:
            confirmed = released.wait(timeout_s)
        finally:
            with self._lock:
                self._waiting.pop(fonte, None)
        if self._cancelled.is_set():
            raise SourceInterrupted("Execução interrompida pelo usuário")
        return confirmed

    def confirm(self, fonte: str) -> bool:
        with self._lock:
            released = self._waiting.get(fonte)
        if released is None:
            return False
        released.set()
        return True

    def waiting(self) -> list[str]:
        with self._lock:
            return sorted(self._waiting)

    def check(self) -> None:
        """Levanta `SourceInterrupted` se a execução foi cancelada (chamado entre páginas e pausas)."""
        if self._cancelled.is_set():
            raise SourceInterrupted("Execução interrompida pelo usuário")

    def cancel(self) -> None:
        self._cancelled.set()
        with self._lock:
            for released in self._waiting.values():
                released.set()

    def reset(self) -> None:
        self._cancelled.clear()
