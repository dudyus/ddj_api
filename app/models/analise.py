from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Text,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database import Base


class Analise(Base):
    __tablename__ = "analise"

    id = Column(Integer, primary_key=True)

    partida_id = Column(
        Integer,
        ForeignKey("partida.id")
    )

    probabilidade = Column(Numeric(5, 2))
    confianca = Column(Numeric(5, 2))

    modelo_usado = Column(String(150))

    descricao = Column(Text)

    data = Column(
        DateTime,
        default=datetime.utcnow
    )

    partida = relationship(
        "Partida",
        back_populates="analises"
    )

    recomendacoes = relationship(
        "Recomendacao",
        back_populates="analise"
    )