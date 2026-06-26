from sqlalchemy import Column, Integer, String, Text, Enum
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import PerfilRiscoEnum


class Usuario(Base):
    __tablename__ = "usuario"

    id = Column(Integer, primary_key=True)

    nome = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    senha = Column(String(255), nullable=False)

    foto_perfil = Column(Text, nullable=True)

    perfil_risco = Column(
        Enum(PerfilRiscoEnum),
        nullable=True
    )

    bancas = relationship("Banca", back_populates="usuario")
    apostas = relationship("Aposta", back_populates="usuario")
    apostas_multiplas = relationship("ApostaMultipla", back_populates="usuario")
    anamneses = relationship("Anamnese", back_populates="usuario")
    recomendacoes = relationship("Recomendacao", back_populates="usuario")