from fastapi import APIRouter, Request, Response

from ..errors import Conflict
from ..schemas import VerificationOut

router = APIRouter()


@router.get("/verificacao", response_model=VerificationOut)
def waiting(request: Request) -> VerificationOut:
    return VerificationOut(fontes=request.app.state.gate.waiting())


@router.post("/verificacao/{fonte}/confirmar", status_code=204)
def confirm(fonte: str, request: Request) -> Response:
    if not request.app.state.gate.confirm(fonte):
        raise Conflict(f"A fonte {fonte} não está esperando verificação")
    return Response(status_code=204)
