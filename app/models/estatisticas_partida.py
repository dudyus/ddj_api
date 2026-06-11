from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database import Base


class EstatisticasPartida(Base):
    __tablename__ = "estatisticas_partida"

    id = Column(Integer, primary_key=True)

    partida_id = Column(
        Integer,
        ForeignKey("partida.id")
    )

    posse_casa = Column(Numeric(5, 2))
    posse_fora = Column(Numeric(5, 2))

    chutes_casa = Column(Integer)
    chutes_fora = Column(Integer)

    escanteios_casa = Column(Integer)
    escanteios_fora = Column(Integer)

    partida = relationship(
        "Partida",
        back_populates="estatisticas"
    )