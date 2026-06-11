"""
Serviço de odds.

Hoje retorna odds MOCKADAS no formato da Betano (mercados h2h e gols),
determinísticas por partida (seed = partida_id) para não mudarem a cada request.

Para trocar pela The Odds API real depois:
  - sport: soccer_brazil_campeonato
  - markets: h2h, totals
  - bookmaker: betano
  - preencher ODDS_API_KEY no .env e setar ODDS_API_MOCK=false
"""

import os
import random

CASA_APOSTA = "Betano"


def _rng(partida_id: int) -> random.Random:
    return random.Random(partida_id * 7919 + 13)


def gerar_odds_mock(partida_id: int) -> list[dict]:
    """Lista de odds no formato da tabela `odds` (sem persistir)."""
    r = _rng(partida_id)

    # h2h — vantagem leve pro mandante
    odd_casa = round(r.uniform(1.55, 2.60), 2)
    odd_empate = round(r.uniform(2.90, 3.60), 2)
    odd_fora = round(r.uniform(2.40, 5.50), 2)

    # gols — over/under 2.5
    over_25 = round(r.uniform(1.65, 2.30), 2)
    under_25 = round(r.uniform(1.55, 2.20), 2)

    return [
        {"tipo_aposta": "h2h_casa", "mercado": "h2h", "selecao": "Casa", "odd": odd_casa, "casa_aposta": CASA_APOSTA},
        {"tipo_aposta": "h2h_empate", "mercado": "h2h", "selecao": "Empate", "odd": odd_empate, "casa_aposta": CASA_APOSTA},
        {"tipo_aposta": "h2h_fora", "mercado": "h2h", "selecao": "Fora", "odd": odd_fora, "casa_aposta": CASA_APOSTA},
        {"tipo_aposta": "gols_over_2_5", "mercado": "gols", "selecao": "Mais de 2.5", "odd": over_25, "casa_aposta": CASA_APOSTA},
        {"tipo_aposta": "gols_under_2_5", "mercado": "gols", "selecao": "Menos de 2.5", "odd": under_25, "casa_aposta": CASA_APOSTA},
    ]


def buscar_odds(partida_id: int) -> list[dict]:
    usar_mock = os.getenv("ODDS_API_MOCK", "true").lower() != "false"
    if usar_mock:
        return gerar_odds_mock(partida_id)
    # TODO: integrar The Odds API real aqui usando ODDS_API_KEY
    return gerar_odds_mock(partida_id)
