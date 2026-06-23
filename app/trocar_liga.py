from app.database import SessionLocal
from app.models import Partida, Time
from app.services.importar_partidas_service import importar_partidas

db = SessionLocal()

apagadas_partidas = db.query(Partida).delete()
apagados_times = db.query(Time).delete()
db.commit()

print(f"Removidas {apagadas_partidas} partidas e {apagados_times} times.")

resultado = importar_partidas()
print(resultado)
