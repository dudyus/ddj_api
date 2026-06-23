from typing import Optional

from pydantic import BaseModel


class CriarAposta(BaseModel):
    banca_id: int
    usuario_id: int
    partida_id: Optional[int] = None
    tipo_aposta: str
    odd: float
    valor: float


class ResultadoAposta(BaseModel):
    resultado: str
