from pydantic import BaseModel


class EditarNome(BaseModel):
    novo_nome: str


class EditarEmail(BaseModel):
    novo_email: str


class AlterarSenha(BaseModel):
    senha_atual: str
    nova_senha: str


class EditarFoto(BaseModel):
    foto_perfil: str
