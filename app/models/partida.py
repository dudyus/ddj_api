from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database import Base


class Partida(Base):
    __tablename__ = "partida"

    id = Column(Integer, primary_key=True)

    time_casa_id = Column(
        Integer,
        ForeignKey("time.id"),
        nullable=False
    )

    time_fora_id = Column(
        Integer,
        ForeignKey("time.id"),
        nullable=False
    )

    data = Column(DateTime)

    rodada = Column(Integer)

    gols_casa = Column(Integer)
    gols_fora = Column(Integer)

    time_casa = relationship(
        "Time",
        foreign_keys=[time_casa_id]
    )

    time_fora = relationship(
        "Time",
        foreign_keys=[time_fora_id]
    )

    estatisticas = relationship(
        "EstatisticasPartida",
        back_populates="partida"
    )

    odds = relationship(
        "Odds",
        back_populates="partida"
    )

    analises = relationship(
        "Analise",
        back_populates="partida"
    )

    apostas = relationship(
        "Aposta",
        back_populates="partida"
    )