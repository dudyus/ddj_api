from typing import List, Optional
from pydantic import BaseModel, field_validator


class ItemMultiplaInput(BaseModel):
    partida_id: Optional[int] = None
    tipo_aposta: str
    odd: float

    @field_validator("odd")
    @classmethod
    def odd_valida(cls, v: float) -> float:
        if v < 1.01:
            raise ValueError("Odd deve ser no mínimo 1.01")
        return v

    @field_validator("tipo_aposta")
    @classmethod
    def tipo_aposta_valido(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Tipo de aposta não pode ser vazio")
        if len(v) > 100:
            raise ValueError("Tipo de aposta muito longo")
        return v.strip()


class CriarApostaMultipla(BaseModel):
    banca_id: int
    usuario_id: int
    valor: float
    itens: List[ItemMultiplaInput]

    @field_validator("valor")
    @classmethod
    def valor_valido(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Valor da aposta deve ser maior que 0")
        return v

    @field_validator("itens")
    @classmethod
    def itens_validos(cls, v: List[ItemMultiplaInput]) -> List[ItemMultiplaInput]:
        if len(v) < 2:
            raise ValueError("Múltipla requer pelo menos 2 seleções")
        return v


class ResultadoApostaMultipla(BaseModel):
    resultado: str
