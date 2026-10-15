"""Portão de verificação: a fonte bloqueada espera o usuário confirmar que concluiu a verificação à mão."""
import threading

import pytest

from backend.app.sources.errors import SourceInterrupted
from backend.app.sources.verification import VerificationGate


def wait_in_thread(gate, fonte, timeout_s=5):
    result = {}
    thread = threading.Thread(target=lambda: result.update(value=_safe_wait(gate, fonte, timeout_s)))
    thread.start()
    return thread, result


def _safe_wait(gate, fonte, timeout_s):
    try:
        return gate.wait(fonte, timeout_s)
    except SourceInterrupted:
        return "interrompida"


def wait_until_waiting(gate, fonte):
    for _ in range(200):
        if fonte in gate.waiting():
            return
        threading.Event().wait(0.01)
    pytest.fail(f"{fonte} não entrou em espera")


def test_confirmar_libera_a_fonte_que_esperava():
    gate = VerificationGate()
    thread, result = wait_in_thread(gate, "indeed")
    wait_until_waiting(gate, "indeed")
    assert gate.confirm("indeed") is True
    thread.join(2)
    assert result["value"] is True
    assert gate.waiting() == []


def test_confirmar_fonte_que_nao_espera_devolve_falso():
    assert VerificationGate().confirm("indeed") is False


def test_tempo_esgotado_devolve_falso_e_sai_da_espera():
    gate = VerificationGate()
    assert gate.wait("indeed", 0.05) is False
    assert gate.waiting() == []


def test_cancelar_acorda_quem_espera_com_interrupcao():
    gate = VerificationGate()
    thread, result = wait_in_thread(gate, "indeed")
    wait_until_waiting(gate, "indeed")
    gate.cancel()
    thread.join(2)
    assert result["value"] == "interrompida"


def test_reset_limpa_o_cancelamento_da_execucao_anterior():
    gate = VerificationGate()
    gate.cancel()
    gate.reset()
    assert gate.wait("indeed", 0.05) is False
