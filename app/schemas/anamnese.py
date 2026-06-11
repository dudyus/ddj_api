from pydantic import BaseModel

class RespostaSchema(BaseModel):
    pergunta_id: int
    alternativa_id: int

class AnamneseSchema(BaseModel):
    usuario_id: int
    respostas: list[RespostaSchema]