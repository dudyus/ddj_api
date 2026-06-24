from app.database import Base, engine
from app.models import *
from sqlalchemy import text


def migrar():
    Base.metadata.create_all(bind=engine)
    print("OK Tabelas criadas/verificadas")

    with engine.connect() as conn:
        resultado = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'historico_banca'
              AND column_name = 'aposta_multipla_id'
        """)).fetchone()

        if resultado is None:
            conn.execute(text("""
                ALTER TABLE historico_banca
                ADD COLUMN aposta_multipla_id INTEGER
                REFERENCES aposta_multipla(id)
            """))
            conn.commit()
            print("OK Coluna aposta_multipla_id adicionada em historico_banca")
        else:
            print("OK Coluna aposta_multipla_id já existe em historico_banca")

        resultado_item = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'item_aposta_multipla'
              AND column_name = 'resultado'
        """)).fetchone()

        if resultado_item is None:
            conn.execute(text("""
                ALTER TABLE item_aposta_multipla
                ADD COLUMN resultado resultadoapostaenum NOT NULL DEFAULT 'PENDENTE'
            """))
            conn.commit()
            print("OK Coluna resultado adicionada em item_aposta_multipla")
        else:
            print("OK Coluna resultado já existe em item_aposta_multipla")

    print("\nMigração concluída com sucesso.")


if __name__ == "__main__":
    migrar()
