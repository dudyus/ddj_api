from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database import Base


class Alternativa(Base):
    __tablename__ = "alternativa"

    id = Column(Integer, primary_key=True)

    pergunta_id = Column(
        Integer,
        ForeignKey("pergunta.id")
    )

    texto = Column(String(300))

    peso = Column(Integer)

    pergunta = relationship(
        "Pergunta",
        back_populates="alternativas"
    )