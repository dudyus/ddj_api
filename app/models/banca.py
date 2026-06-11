from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    Enum
)

from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import StatusBancaEnum


class Banca(Base):
    __tablename__ = "banca"

    id = Column(Integer, primary_key=True)

    usuario_id = Column(
        Integer,
        ForeignKey("usuario.id"),
        nullable=False
    )

    saldo_inicial = Column(Numeric(12, 2), nullable=False)
    saldo_atual = Column(Numeric(12, 2), nullable=False)

    stop_loss = Column(Numeric(12, 2))
    meta_diaria = Column(Numeric(12, 2))

    status = Column(
        Enum(StatusBancaEnum),
        nullable=False,
        default=StatusBancaEnum.ATIVA
    )

    data_criacao = Column(
        DateTime,
        default=datetime.utcnow
    )

    data_fechamento = Column(DateTime, nullable=True)

    usuario = relationship(
        "Usuario",
        back_populates="bancas"
    )

    apostas = relationship(
        "Aposta",
        back_populates="banca"
    )