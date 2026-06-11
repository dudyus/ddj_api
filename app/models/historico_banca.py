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
from app.models.enums import TipoMovimentacaoEnum


class HistoricoBanca(Base):
    __tablename__ = "historico_banca"

    id = Column(Integer, primary_key=True)

    banca_id = Column(
        Integer,
        ForeignKey("banca.id"),
        nullable=True
    )

    aposta_id = Column(
        Integer,
        ForeignKey("aposta.id"),
        nullable=True
    )

    aposta_multipla_id = Column(
        Integer,
        ForeignKey("aposta_multipla.id"),
        nullable=True
    )

    usuario_id = Column(
        Integer,
        ForeignKey("usuario.id")
    )

    saldo = Column(Numeric(12, 2))

    valor = Column(Numeric(12, 2))

    tipo_movimentacao = Column(
        Enum(TipoMovimentacaoEnum),
        nullable=False
    )

    data = Column(
        DateTime,
        default=datetime.utcnow
    )

    banca = relationship("Banca")
    aposta = relationship("Aposta")
    aposta_multipla = relationship("ApostaMultipla")
    usuario = relationship("Usuario")