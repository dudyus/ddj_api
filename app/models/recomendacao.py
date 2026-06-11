from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    Enum
)

from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import RiscoRecomendacaoEnum


class Recomendacao(Base):
    __tablename__ = "recomendacao"

    id = Column(Integer, primary_key=True)

    analise_id = Column(
        Integer,
        ForeignKey("analise.id")
    )

    usuario_id = Column(
        Integer,
        ForeignKey("usuario.id")
    )

    tipo_aposta = Column(String(100))

    risco = Column(
        Enum(RiscoRecomendacaoEnum)
    )

    justificativa = Column(Text)

    analise = relationship(
        "Analise",
        back_populates="recomendacoes"
    )

    usuario = relationship(
        "Usuario",
        back_populates="recomendacoes"
    )