from datetime import datetime

from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import ResultadoApostaEnum


class ItemApostaMultipla(Base):
    __tablename__ = "item_aposta_multipla"

    id = Column(Integer, primary_key=True)

    multipla_id = Column(Integer, ForeignKey("aposta_multipla.id"), nullable=False)
    partida_id = Column(Integer, ForeignKey("partida.id"), nullable=True)

    tipo_aposta = Column(String(100), nullable=False)
    odd = Column(Numeric(10, 2), nullable=False)

    multipla = relationship("ApostaMultipla", back_populates="itens")


class ApostaMultipla(Base):
    __tablename__ = "aposta_multipla"

    id = Column(Integer, primary_key=True)

    banca_id = Column(Integer, ForeignKey("banca.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)

    valor = Column(Numeric(12, 2), nullable=False)
    odd_total = Column(Numeric(10, 2), nullable=False)

    lucro_prejuizo = Column(Numeric(12, 2), nullable=True)

    resultado = Column(
        Enum(ResultadoApostaEnum),
        default=ResultadoApostaEnum.PENDENTE,
        nullable=False,
    )

    data = Column(DateTime, default=datetime.utcnow)

    banca = relationship("Banca", back_populates="apostas_multiplas")
    usuario = relationship("Usuario", back_populates="apostas_multiplas")
    itens = relationship(
        "ItemApostaMultipla",
        back_populates="multipla",
        cascade="all, delete-orphan",
    )
