import math

from app.models import Partida, Time
from app.services.odds_service import buscar_odds


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def calcular_estatisticas(db) -> dict:
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


_LIGA_GF_CASA = 1.55
_LIGA_GF_FORA = 1.20

_DESCONTO_SEM_HISTORICO = 0.6
_ACRESCIMO_SEM_HISTORICO = 1.4


def _media(soma, jogos, fallback):
    return soma / jogos if jogos > 0 else fallback


def _media_ataque(soma, jogos, fallback):
    return soma / jogos if jogos > 0 else fallback * _DESCONTO_SEM_HISTORICO


def _media_defesa(soma, jogos, fallback):
    return soma / jogos if jogos > 0 else fallback * _ACRESCIMO_SEM_HISTORICO


def _selecionar_por_perfil(avaliadas: list[dict], perfil_risco: str | None) -> dict | None:
    if not avaliadas:
        return None

    pool = [a for a in avaliadas if a["edge"] > 0] or avaliadas

    if perfil_risco == "CONSERVADOR":
        return max(pool, key=lambda a: a["prob_modelo"])
    if perfil_risco == "AGRESSIVO":
        return max(pool, key=lambda a: a["prob_modelo"] * a["odd"] - 1)
    return max(pool, key=lambda a: a["edge"])


def recomendar(db, partida: Partida, perfil_risco: str | None = None) -> dict:
    time_casa = db.get(Time, partida.time_casa_id)
    time_fora = db.get(Time, partida.time_fora_id)
    nc = time_casa.nome if time_casa else "Casa"
    nf = time_fora.nome if time_fora else "Fora"

    stats = calcular_estatisticas(db)

    sc = stats.get(partida.time_casa_id, {})
    sf = stats.get(partida.time_fora_id, {})

    casa_gf = _media_ataque(sc.get("casa_gf", 0), sc.get("casa_jogos", 0), _LIGA_GF_CASA)
    fora_ga = _media_defesa(sf.get("fora_ga", 0), sf.get("fora_jogos", 0), _LIGA_GF_CASA)
    fora_gf = _media_ataque(sf.get("fora_gf", 0), sf.get("fora_jogos", 0), _LIGA_GF_FORA)
    casa_ga = _media_defesa(sc.get("casa_ga", 0), sc.get("casa_jogos", 0), _LIGA_GF_FORA)

    exp_casa = (casa_gf + fora_ga) / 2
    exp_fora = (fora_gf + casa_ga) / 2
    exp_total = exp_casa + exp_fora

    odds = buscar_odds(partida.id, nc, nf, partida.data, exp_casa, exp_fora)

    diff = exp_casa - exp_fora
    p_casa = _clamp(0.40 + diff * 0.18, 0.08, 0.85)
    p_fora = _clamp(0.30 - diff * 0.18, 0.08, 0.85)
    p_empate = _clamp(1 - p_casa - p_fora, 0.05, 0.50)
    soma = p_casa + p_empate + p_fora
    p_casa, p_empate, p_fora = p_casa / soma, p_empate / soma, p_fora / soma

    prob_por_tipo = {
        "h2h_casa": p_casa,
        "h2h_empate": p_empate,
        "h2h_fora": p_fora,
    }

    def _prob_gols(ponto: float) -> tuple[float, float]:
        p_over = _clamp(1 / (1 + math.exp(-(exp_total - ponto) * 1.1)), 0.05, 0.95)
        return p_over, 1 - p_over

    avaliadas = []
    for o in odds:
        if o["mercado"] == "h2h":
            prob = prob_por_tipo.get(o["tipo_aposta"])
        elif o["mercado"] == "gols" and o.get("ponto") is not None:
            p_over, p_under = _prob_gols(o["ponto"])
            prob = p_over if o["tipo_aposta"].startswith("gols_over") else p_under
            prob_por_tipo[o["tipo_aposta"]] = prob
        else:
            prob = None

        if prob is None:
            continue
        implicita = 1 / o["odd"]
        edge = prob - implicita
        avaliadas.append({**o, "prob_modelo": round(prob, 4),
                          "prob_implicita": round(implicita, 4),
                          "edge": round(edge, 4)})

    avaliadas.sort(key=lambda x: x["edge"], reverse=True)
    melhor = _selecionar_por_perfil(avaliadas, perfil_risco)

    if melhor is None:
        risco = "ALTO"
    elif melhor["odd"] <= 2.0:
        risco = "BAIXO"
    elif melhor["odd"] <= 4.0:
        risco = "MEDIO"
    else:
        risco = "ALTO"

    label = _rotulo(melhor, nc, nf) if melhor else "Sem recomendação"
    justificativa = _justificar(melhor, exp_casa, exp_fora, nc, nf, perfil_risco) if melhor else (
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
    if t.startswith("gols_over_") and m.get("ponto") is not None:
        return f"Mais de {m['ponto']:g} gols"
    if t.startswith("gols_under_") and m.get("ponto") is not None:
        return f"Menos de {m['ponto']:g} gols"
    return m.get("selecao", t)


_PERFIL_SUFIXO = {
    "CONSERVADOR": "a mais segura do jogo",
    "AGRESSIVO": "o melhor retorno esperado do jogo",
    "MODERADO": "a maior vantagem sobre a casa",
}


def _justificar(m, exp_casa, exp_fora, nc, nf, perfil_risco: str | None = None) -> str:
    prob_pct = round(m["prob_modelo"] * 100)
    sufixo = _PERFIL_SUFIXO.get(perfil_risco or "", "a de maior vantagem no jogo")
    return (
        f"O modelo estima {prob_pct}% de chance. "
        f"Odd {m['odd']:.2f} na {m['casa_aposta']} — {sufixo}."
    )
