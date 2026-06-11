from sqlalchemy import Column, Integer, String

from app.database import Base


class Time(Base):
    __tablename__ = "time"

    id = Column(Integer, primary_key=True)

    nome = Column(
        String(150),
        nullable=False,
        unique=True
    )