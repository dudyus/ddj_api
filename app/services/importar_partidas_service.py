from datetime import datetime

from app.database import SessionLocal

from app.models import Time, Partida

from app.services.football_data_service import buscar_partidas


def importar_partidas():

    db = SessionLocal()

    dados = buscar_partidas()

    partidas_importadas = 0
    partidas_ignoradas = 0

    for jogo in dados["matches"]:

        nome_casa = jogo["homeTeam"]["name"]
        nome_fora = jogo["awayTeam"]["name"]

        time_casa = db.query(Time).filter(
            Time.nome == nome_casa
        ).first()

        if not time_casa:
            time_casa = Time(nome=nome_casa)
            db.add(time_casa)
            db.commit()
            db.refresh(time_casa)

        time_fora = db.query(Time).filter(
            Time.nome == nome_fora
        ).first()

        if not time_fora:
            time_fora = Time(nome=nome_fora)
            db.add(time_fora)
            db.commit()
            db.refresh(time_fora)

        data_partida = datetime.fromisoformat(
            jogo["utcDate"].replace("Z", "+00:00")
        )

        partida_existente = db.query(Partida).filter(
            Partida.time_casa_id == time_casa.id,
            Partida.time_fora_id == time_fora.id,
            Partida.data == data_partida
        ).first()

        if partida_existente:
            partidas_ignoradas += 1
            continue

        partida = Partida(
            time_casa_id=time_casa.id,
            time_fora_id=time_fora.id,
            data=data_partida,
            rodada=jogo["matchday"],
            gols_casa=jogo["score"]["fullTime"]["home"],
            gols_fora=jogo["score"]["fullTime"]["away"]
        )

        db.add(partida)

        partidas_importadas += 1

    db.commit()

    return {
        "sucesso": True,
        "partidas_importadas": partidas_importadas,
        "partidas_ignoradas": partidas_ignoradas,
        "total_recebido_api": len(dados["matches"])
    }