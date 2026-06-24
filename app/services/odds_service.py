import math
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

SPORT_KEY = "soccer_epl"

BOOKMAKERS = ["betfair_sb_uk", "onexbet"]
BOOKMAKER_TITULO = {"betfair_sb_uk": "Betfair", "onexbet": "1xBet"}

_CACHE_TTL_SEGUNDOS = 1800
_cache: dict = {"indice": None, "buscado_em": 0.0}

_OVERROUND = 1.06
_EXP_CASA_PADRAO = 1.55
_EXP_FORA_PADRAO = 1.20


def _rng(seed: str) -> random.Random:
    return random.Random(seed)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _odd_a_partir_da_prob(prob: float) -> float:
    return round(1 / (prob * _OVERROUND), 2)


def gerar_odds_mock(
    partida_id: int,
    exp_casa: float = _EXP_CASA_PADRAO,
    exp_fora: float = _EXP_FORA_PADRAO,
) -> list[dict]:
    odds_geral = []

    for chave_bm, titulo in BOOKMAKER_TITULO.items():
        r = _rng(f"{partida_id}:{chave_bm}")
        ruido = r.uniform(-0.04, 0.04)

        diff = exp_casa - exp_fora
        p_casa = _clamp(0.40 + diff * 0.18 + ruido, 0.05, 0.88)
        p_fora = _clamp(0.30 - diff * 0.18 - ruido, 0.05, 0.88)
        p_empate = _clamp(1 - p_casa - p_fora, 0.05, 0.45)
        soma = p_casa + p_empate + p_fora
        p_casa, p_empate, p_fora = p_casa / soma, p_empate / soma, p_fora / soma

        exp_total = exp_casa + exp_fora + r.uniform(-0.15, 0.15)
        p_over = _clamp(1 / (1 + math.exp(-(exp_total - 2.5) * 1.1)), 0.05, 0.95)
        p_under = 1 - p_over

        linha_casa = -_clamp(round(diff * 2) / 2, -3.0, 3.0)
        linha_fora = -linha_casa
        margem_necessaria = -linha_casa
        p_casa_cobre = _clamp(1 / (1 + math.exp(-(diff + ruido - margem_necessaria) * 0.9)), 0.05, 0.95)
        p_fora_cobre = 1 - p_casa_cobre

        odds_geral += [
            {"tipo_aposta": "h2h_casa", "mercado": "h2h", "selecao": "Casa", "odd": _odd_a_partir_da_prob(p_casa), "casa_aposta": titulo},
            {"tipo_aposta": "h2h_empate", "mercado": "h2h", "selecao": "Empate", "odd": _odd_a_partir_da_prob(p_empate), "casa_aposta": titulo},
            {"tipo_aposta": "h2h_fora", "mercado": "h2h", "selecao": "Fora", "odd": _odd_a_partir_da_prob(p_fora), "casa_aposta": titulo},
            {"tipo_aposta": "gols_over_2.5", "mercado": "gols", "selecao": "Mais de 2.5", "odd": _odd_a_partir_da_prob(p_over), "casa_aposta": titulo, "ponto": 2.5},
            {"tipo_aposta": "gols_under_2.5", "mercado": "gols", "selecao": "Menos de 2.5", "odd": _odd_a_partir_da_prob(p_under), "casa_aposta": titulo, "ponto": 2.5},
            {"tipo_aposta": f"handicap_casa_{linha_casa:g}", "mercado": "handicap", "selecao": f"Casa ({linha_casa:+g})", "odd": _odd_a_partir_da_prob(p_casa_cobre), "casa_aposta": titulo, "ponto": linha_casa},
            {"tipo_aposta": f"handicap_fora_{linha_fora:g}", "mercado": "handicap", "selecao": f"Fora ({linha_fora:+g})", "odd": _odd_a_partir_da_prob(p_fora_cobre), "casa_aposta": titulo, "ponto": linha_fora},
        ]

    return odds_geral


def _normalizar_time(nome: str) -> str:
    n = nome.lower().replace("&", "and")
    n = re.sub(r"\bafc\b|\bfc\b", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return n.strip()


def _bookmakers_para_mercado(evento: dict, mercado_chave: str):
    bookmakers_por_key = {b["key"]: b for b in evento["bookmakers"]}
    encontrados = []
    for chave_bm in BOOKMAKERS:
        bookmaker = bookmakers_por_key.get(chave_bm)
        if not bookmaker:
            continue
        mercado = next((m for m in bookmaker["markets"] if m["key"] == mercado_chave), None)
        if mercado:
            encontrados.append((bookmaker, mercado))
    return encontrados


def _montar_indice(eventos: list[dict]) -> dict[tuple[str, str], list[dict]]:
    indice: dict[tuple[str, str], list[dict]] = {}

    for evento in eventos:
        odds_evento = []

        for bookmaker_h2h, mercado_h2h in _bookmakers_para_mercado(evento, "h2h"):
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

        for bookmaker_gols, mercado_gols in _bookmakers_para_mercado(evento, "totals"):
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

        for bookmaker_handicap, mercado_handicap in _bookmakers_para_mercado(evento, "spreads"):
            titulo = BOOKMAKER_TITULO.get(bookmaker_handicap["key"], bookmaker_handicap["title"])
            for outcome in mercado_handicap["outcomes"]:
                ponto = outcome["point"]
                lado = "casa" if outcome["name"] == evento["home_team"] else "fora"
                rotulo = "Casa" if lado == "casa" else "Fora"
                odds_evento.append({
                    "tipo_aposta": f"handicap_{lado}_{ponto:g}",
                    "mercado": "handicap",
                    "selecao": f"{rotulo} ({ponto:+g})",
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
            "markets": "h2h,totals,spreads",
            "bookmakers": ",".join(BOOKMAKERS),
        },
        timeout=10,
    )
    resposta.raise_for_status()

    indice = _montar_indice(resposta.json())
    _cache["indice"] = indice
    _cache["buscado_em"] = agora
    return indice


def buscar_odds(
    partida_id: int,
    nome_casa: str,
    nome_fora: str,
    data: Optional[datetime] = None,
    exp_casa: float = _EXP_CASA_PADRAO,
    exp_fora: float = _EXP_FORA_PADRAO,
) -> list[dict]:
    usar_mock = os.getenv("ODDS_API_MOCK", "true").lower() != "false"

    if not usar_mock:
        try:
            indice = _buscar_indice_real()
            chave = (_normalizar_time(nome_casa), _normalizar_time(nome_fora))
            if chave in indice:
                return indice[chave]
        except requests.RequestException:
            pass

    return gerar_odds_mock(partida_id, exp_casa, exp_fora)
