from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database import Base


class Anamnese(Base):
    __tablename__ = "anamnese"

    id = Column(Integer, primary_key=True)

    usuario_id = Column(
        Integer,
        ForeignKey("usuario.id")
    )

    perfil_calculado = Column(String(50))

    usuario = relationship(
        "Usuario",
        back_populates="anamneses"
    )

    respostas = relationship(
        "RespostaUsuario",
        back_populates="anamnese"
    )