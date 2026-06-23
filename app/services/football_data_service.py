import requests
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")

COMPETICAO = "PL"

TEMPORADA_HISTORICO = 2025


def _get(params: dict) -> dict:
    response = requests.get(
        f"https://api.football-data.org/v4/competitions/{COMPETICAO}/matches",
        headers={"X-Auth-Token": API_KEY},
        params=params,
    )
    return response.json()


def buscar_partidas():
    historico = _get({"season": TEMPORADA_HISTORICO})
    agendadas = _get({"status": "SCHEDULED"})

    return {
        "matches": historico.get("matches", []) + agendadas.get("matches", [])
    }
