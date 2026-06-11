"""
Migração: cria tabelas de aposta múltipla e adiciona coluna em historico_banca.

Seguro para rodar múltiplas vezes (idempotente).
"""

from app.database import Base, engine
from app.models import *  # garante que todos os models estão registrados no metadata
from sqlalchemy import text


def migrar():
    # 1. Cria tabelas novas (create_all ignora as que já existem)
    Base.metadata.create_all(bind=engine)
    print("OK Tabelas criadas/verificadas")

    # 2. Adiciona coluna aposta_multipla_id em historico_banca (se não existir)
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

    print("\nMigração concluída com sucesso.")


if __name__ == "__main__":
    migrar()
