from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Pergunta(Base):
    __tablename__ = "pergunta"

    id = Column(Integer, primary_key=True)

    texto = Column(String(500))

    alternativas = relationship(
        "Alternativa",
        back_populates="pergunta"
    )