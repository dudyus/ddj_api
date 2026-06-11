from sqlalchemy import (
    Column,
    Integer,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database import Base


class RespostaUsuario(Base):
    __tablename__ = "resposta_usuario"

    id = Column(Integer, primary_key=True)

    anamnese_id = Column(
        Integer,
        ForeignKey("anamnese.id")
    )

    pergunta_id = Column(
        Integer,
        ForeignKey("pergunta.id")
    )

    alternativa_id = Column(
        Integer,
        ForeignKey("alternativa.id")
    )

    anamnese = relationship(
        "Anamnese",
        back_populates="respostas"
    )

    pergunta = relationship("Pergunta")

    alternativa = relationship("Alternativa")