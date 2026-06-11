from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Enum
)

from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import ResultadoApostaEnum


class Aposta(Base):
    __tablename__ = "aposta"

    id = Column(Integer, primary_key=True)

    banca_id = Column(
        Integer,
        ForeignKey("banca.id")
    )

    usuario_id = Column(
        Integer,
        ForeignKey("usuario.id")
    )

    partida_id = Column(
        Integer,
        ForeignKey("partida.id")
    )

    tipo_aposta = Column(String(100))

    odd = Column(Numeric(10, 2))

    valor = Column(Numeric(12, 2))

    lucro_prejuizo = Column(Numeric(12, 2))

    resultado = Column(
        Enum(ResultadoApostaEnum),
        default=ResultadoApostaEnum.PENDENTE
    )

    data = Column(
        DateTime,
        default=datetime.utcnow
    )

    banca = relationship(
        "Banca",
        back_populates="apostas"
    )

    usuario = relationship(
        "Usuario",
        back_populates="apostas"
    )

    partida = relationship(
        "Partida",
        back_populates="apostas"
    )