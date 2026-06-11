from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import relationship

from app.database import Base


class Odds(Base):
    __tablename__ = "odds"

    id = Column(Integer, primary_key=True)

    partida_id = Column(
        Integer,
        ForeignKey("partida.id")
    )

    tipo_aposta = Column(String(100))

    odd = Column(Numeric(10, 2))

    casa_aposta = Column(String(150))

    data_coleta = Column(
        DateTime,
        default=datetime.utcnow
    )

    partida = relationship(
        "Partida",
        back_populates="odds"
    )