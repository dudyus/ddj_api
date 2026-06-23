from typing import List, Optional
from pydantic import BaseModel


class ItemMultiplaInput(BaseModel):
    partida_id: Optional[int] = None
    tipo_aposta: str
    odd: float


class CriarApostaMultipla(BaseModel):
    banca_id: int
    usuario_id: int
    valor: float
    itens: List[ItemMultiplaInput]


class ResultadoApostaMultipla(BaseModel):
    resultado: str
