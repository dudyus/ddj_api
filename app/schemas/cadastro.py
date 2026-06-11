from pydantic import BaseModel

class Cadastro(BaseModel):
    nome: str
    email: str
    senha: str