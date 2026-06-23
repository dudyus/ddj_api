import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

CASA_APOSTA_MOCK = "Betano"

SPORT_KEY = "soccer_epl"

BOOKMAKERS = ["betfair_sb_uk", "onexbet"]
BOOKMAKER_TITULO = {"betfair_sb_uk": "Betfair", "onexbet": "1xBet"}

_CACHE_TTL_SEGUNDOS = 1800
_cache: dict = {"indice": None, "buscado_em": 0.0}


def _rng(partida_id: int) -> random.Random:
    return random.Random(partida_id * 7919 + 13)


def gerar_odds_mock(partida_id: int) -> list[dict]:
    r = _rng(partida_id)

    odd_casa = round(r.uniform(1.55, 2.60), 2)
    odd_empate = round(r.uniform(2.90, 3.60), 2)
    odd_fora = round(r.uniform(2.40, 5.50), 2)

    over_25 = round(r.uniform(1.65, 2.30), 2)
    under_25 = round(r.uniform(1.55, 2.20), 2)

    return [
        {"tipo_aposta": "h2h_casa", "mercado": "h2h", "selecao": "Casa", "odd": odd_casa, "casa_aposta": CASA_APOSTA_MOCK},
        {"tipo_aposta": "h2h_empate", "mercado": "h2h", "selecao": "Empate", "odd": odd_empate, "casa_aposta": CASA_APOSTA_MOCK},
        {"tipo_aposta": "h2h_fora", "mercado": "h2h", "selecao": "Fora", "odd": odd_fora, "casa_aposta": CASA_APOSTA_MOCK},
        {"tipo_aposta": "gols_over_2.5", "mercado": "gols", "selecao": "Mais de 2.5", "odd": over_25, "casa_aposta": CASA_APOSTA_MOCK, "ponto": 2.5},
        {"tipo_aposta": "gols_under_2.5", "mercado": "gols", "selecao": "Menos de 2.5", "odd": under_25, "casa_aposta": CASA_APOSTA_MOCK, "ponto": 2.5},
    ]


def _normalizar_time(nome: str) -> str:
    n = nome.lower().replace("&", "and")
    n = re.sub(r"\bafc\b|\bfc\b", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return n.strip()


def _melhor_bookmaker_para_mercado(evento: dict, mercado_chave: str):
    bookmakers_por_key = {b["key"]: b for b in evento["bookmakers"]}
    for chave_bm in BOOKMAKERS:
        bookmaker = bookmakers_por_key.get(chave_bm)
        if not bookmaker:
            continue
        mercado = next((m for m in bookmaker["markets"] if m["key"] == mercado_chave), None)
        if mercado:
            return bookmaker, mercado
    return None, None


def _montar_indice(eventos: list[dict]) -> dict[tuple[str, str], list[dict]]:
    indice: dict[tuple[str, str], list[dict]] = {}

    for evento in eventos:
        odds_evento = []

        bookmaker_h2h, mercado_h2h = _melhor_bookmaker_para_mercado(evento, "h2h")
        if bookmaker_h2h:
            titulo = BOOKMAKER_TITULO.get(bookmaker_h2h["key"], bookmaker_h2h["title"])
            for outcome in mercado_h2h["outcomes"]:
                if outcome["name"] == evento["home_team"]:
                    tipo, selecao = "h2h_casa", "Casa"
                elif outcome["name"] == evento["away_team"]:
                    tipo, selecao = "h2h_fora", "Fora"
                else:
                    tipo, selecao = "h2h_empate", "Empate"
                odds_evento.append({
                    "tipo_aposta": tipo,
                    "mercado": "h2h",
                    "selecao": selecao,
                    "odd": outcome["price"],
                    "casa_aposta": titulo,
                })

        bookmaker_gols, mercado_gols = _melhor_bookmaker_para_mercado(evento, "totals")
        if bookmaker_gols:
            titulo = BOOKMAKER_TITULO.get(bookmaker_gols["key"], bookmaker_gols["title"])
            for outcome in mercado_gols["outcomes"]:
                ponto = outcome["point"]
                lado = "over" if outcome["name"] == "Over" else "under"
                odds_evento.append({
                    "tipo_aposta": f"gols_{lado}_{ponto:g}",
                    "mercado": "gols",
                    "selecao": f"{'Mais' if lado == 'over' else 'Menos'} de {ponto:g}",
                    "odd": outcome["price"],
                    "casa_aposta": titulo,
                    "ponto": ponto,
                })

        if odds_evento:
            chave = (_normalizar_time(evento["home_team"]), _normalizar_time(evento["away_team"]))
            indice[chave] = odds_evento

    return indice


def _buscar_indice_real() -> dict:
    agora = time.time()
    if _cache["indice"] is not None and (agora - _cache["buscado_em"]) < _CACHE_TTL_SEGUNDOS:
        return _cache["indice"]

    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        return {}

    resposta = requests.get(
        f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds/",
        params={
            "apiKey": api_key,
            "regions": "uk,eu",
            "markets": "h2h,totals",
            "bookmakers": ",".join(BOOKMAKERS),
        },
        timeout=10,
    )
    resposta.raise_for_status()

    indice = _montar_indice(resposta.json())
    _cache["indice"] = indice
    _cache["buscado_em"] = agora
    return indice


def buscar_odds(partida_id: int, nome_casa: str, nome_fora: str, data: Optional[datetime] = None) -> list[dict]:
    usar_mock = os.getenv("ODDS_API_MOCK", "true").lower() != "false"

    if not usar_mock:
        try:
            indice = _buscar_indice_real()
            chave = (_normalizar_time(nome_casa), _normalizar_time(nome_fora))
            if chave in indice:
                return indice[chave]
        except requests.RequestException:
            pass

    return gerar_odds_mock(partida_id)
