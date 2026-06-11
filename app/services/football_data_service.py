import requests
import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")


def buscar_partidas():

    response = requests.get(
        "https://api.football-data.org/v4/competitions/BSA/matches",
        headers={
            "X-Auth-Token": API_KEY
        }
    )

    return response.json()