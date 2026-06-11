from app.database import Base, engine
from app.models import *

Base.metadata.create_all(bind=engine)

print("Tabelas criadas com sucesso!")