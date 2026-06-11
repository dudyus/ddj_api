"""
Recomendação de melhor aposta — estatística simples sobre o histórico
de partidas finalizadas (já no Neon) comparada com as odds (mock Betano).

Ideia: estimar gols esperados e probabilidades a partir do desempenho
casa/fora de cada time, converter odd em probabilidade implícita
(1/odd) e recomendar a seleção com maior "valor" (edge = prob_modelo
- prob_implícita).
"""

import math

from app.models import Partida, Time
from app.services.odds_service import buscar_odds


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def calcular_estatisticas(db) -> dict:
    """Agrega desempenho casa/fora por time usando partidas finalizadas."""
    partidas = (
        db.query(Partida)
        .filter(Partida.gols_casa.isnot(None), Partida.gols_fora.isnot(None))
        .all()
    )

    stats: dict[int, dict] = {}

    def slot(tid):
        if tid not in stats:
            stats[tid] = {
                "casa_jogos": 0, "casa_gf": 0, "casa_ga": 0, "casa_pts": 0,
                "fora_jogos": 0, "fora_gf": 0, "fora_ga": 0, "fora_pts": 0,
            }
        return stats[tid]

    for p in partidas:
        gc, gf = p.gols_casa, p.gols_fora
        c, f = slot(p.time_casa_id), slot(p.time_fora_id)

        c["casa_jogos"] += 1
        c["casa_gf"] += gc
        c["casa_ga"] += gf

        f["fora_jogos"] += 1
        f["fora_gf"] += gf
        f["fora_ga"] += gc

        if gc > gf:
            c["casa_pts"] += 3
        elif gc < gf:
            f["fora_pts"] += 3
        else:
            c["casa_pts"] += 1
            f["fora_pts"] += 1

    return stats


# médias da liga, usadas como fallback quando um time tem poucos jogos
_LIGA_GF_CASA = 1.45
_LIGA_GF_FORA = 1.10


def _media(soma, jogos, fallback):
    return soma / jogos if jogos > 0 else fallback


def recomendar(db, partida: Partida) -> dict:
    stats = calcular_estatisticas(db)
    odds = buscar_odds(partida.id)

    sc = stats.get(partida.time_casa_id, {})
    sf = stats.get(partida.time_fora_id, {})

    # gols esperados: combina ataque do mandante em casa com defesa do
    # visitante fora, e vice-versa
    casa_gf = _media(sc.get("casa_gf", 0), sc.get("casa_jogos", 0), _LIGA_GF_CASA)
    fora_ga = _media(sf.get("fora_ga", 0), sf.get("fora_jogos", 0), _LIGA_GF_CASA)
    fora_gf = _media(sf.get("fora_gf", 0), sf.get("fora_jogos", 0), _LIGA_GF_FORA)
    casa_ga = _media(sc.get("casa_ga", 0), sc.get("casa_jogos", 0), _LIGA_GF_FORA)

    exp_casa = (casa_gf + fora_ga) / 2
    exp_fora = (fora_gf + casa_ga) / 2
    exp_total = exp_casa + exp_fora

    # probabilidades h2h a partir da diferença de gols esperados
    diff = exp_casa - exp_fora
    p_casa = _clamp(0.40 + diff * 0.18, 0.08, 0.85)
    p_fora = _clamp(0.30 - diff * 0.18, 0.08, 0.85)
    p_empate = _clamp(1 - p_casa - p_fora, 0.05, 0.50)
    soma = p_casa + p_empate + p_fora
    p_casa, p_empate, p_fora = p_casa / soma, p_empate / soma, p_fora / soma

    # over/under 2.5 via logística centrada em 2.5
    p_over = _clamp(1 / (1 + math.exp(-(exp_total - 2.5) * 1.1)), 0.05, 0.95)
    p_under = 1 - p_over

    prob_por_tipo = {
        "h2h_casa": p_casa,
        "h2h_empate": p_empate,
        "h2h_fora": p_fora,
        "gols_over_2_5": p_over,
        "gols_under_2_5": p_under,
    }

    # edge = prob_modelo - prob_implícita (1/odd)
    avaliadas = []
    for o in odds:
        prob = prob_por_tipo.get(o["tipo_aposta"])
        if prob is None:
            continue
        implicita = 1 / o["odd"]
        edge = prob - implicita
        avaliadas.append({**o, "prob_modelo": round(prob, 4),
                          "prob_implicita": round(implicita, 4),
                          "edge": round(edge, 4)})

    avaliadas.sort(key=lambda x: x["edge"], reverse=True)
    melhor = avaliadas[0] if avaliadas else None

    if melhor is None:
        risco = "ALTO"
    elif melhor["edge"] >= 0.10:
        risco = "BAIXO"
    elif melhor["edge"] >= 0.03:
        risco = "MEDIO"
    else:
        risco = "ALTO"

    nome_casa = db.get(Time, partida.time_casa_id)
    nome_fora = db.get(Time, partida.time_fora_id)
    nc = nome_casa.nome if nome_casa else "Casa"
    nf = nome_fora.nome if nome_fora else "Fora"

    label = _rotulo(melhor, nc, nf) if melhor else "Sem recomendação"
    justificativa = _justificar(melhor, exp_casa, exp_fora, nc, nf) if melhor else (
        "Histórico insuficiente para recomendar."
    )

    return {
        "partida_id": partida.id,
        "time_casa": nc,
        "time_fora": nf,
        "gols_esperados": {
            "casa": round(exp_casa, 2),
            "fora": round(exp_fora, 2),
            "total": round(exp_total, 2),
        },
        "probabilidades": {k: round(v, 4) for k, v in prob_por_tipo.items()},
        "melhor_aposta": {**melhor, "rotulo": label} if melhor else None,
        "risco": risco,
        "justificativa": justificativa,
        "odds": odds,
    }


def _rotulo(m, nc, nf) -> str:
    t = m["tipo_aposta"]
    if t == "h2h_casa":
        return f"Vitória {nc}"
    if t == "h2h_fora":
        return f"Vitória {nf}"
    if t == "h2h_empate":
        return "Empate"
    if t == "gols_over_2_5":
        return "Mais de 2.5 gols"
    if t == "gols_under_2_5":
        return "Menos de 2.5 gols"
    return m.get("selecao", t)


def _justificar(m, exp_casa, exp_fora, nc, nf) -> str:
    edge_pct = round(m["edge"] * 100, 1)
    prob_pct = round(m["prob_modelo"] * 100, 1)
    return (
        f"Gols esperados {nc} {exp_casa:.2f} x {exp_fora:.2f} {nf}. "
        f"Modelo estima {prob_pct}% para esta seleção contra odd {m['odd']:.2f} "
        f"(Betano), gerando {edge_pct}% de valor."
    )
