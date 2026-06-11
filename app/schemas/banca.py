from typing import Optional

from pydantic import BaseModel


class CriarBanca(BaseModel):
    usuario_id: int
    saldo_inicial: float
    stop_loss: Optional[float] = None
    meta_diaria: Optional[float] = None


class EditarBanca(BaseModel):
    stop_loss: Optional[float] = None
    meta_diaria: Optional[float] = None


class MovimentarBanca(BaseModel):
    valor: float
