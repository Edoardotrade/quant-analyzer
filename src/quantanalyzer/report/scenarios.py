"""Costruzione degli scenari alternativi e del livello di confidenza.

Sostituisce il "lean" a voto singolo della Fase 2 con 2-3 scenari espliciti
(rialzista / ribassista / laterale), ciascuno con probabilità qualitativa e
condizione di invalidazione. Le probabilità NON sono calibrate statisticamente.
"""

from __future__ import annotations

from ..models import (
    ConfidenceLevel,
    Direction,
    Probability,
    Scenario,
    ScenarioType,
    TechnicalAnalysis,
)

AMPLE_BARS = 200  # storico "ampio" (copre la SMA di lungo periodo)


def _counts(ta: TechnicalAnalysis) -> tuple[int, int]:
    bull = sum(1 for s in ta.signals if s.direction == Direction.BULLISH)
    bear = sum(1 for s in ta.signals if s.direction == Direction.BEARISH)
    return bull, bear


def build_scenarios(ta: TechnicalAnalysis) -> list[Scenario]:
    if not ta.computed:
        return []

    sr = ta.support_resistance
    supports = sr.supports if sr else []
    resistances = sr.resistances if sr else []
    nearest_sup = supports[0] if supports else None
    nearest_res = resistances[0] if resistances else None

    bull, bear = _counts(ta)
    diff = bull - bear
    if diff >= 2:
        p_bull, p_bear, p_side = Probability.ALTA, Probability.BASSA, Probability.MEDIA
    elif diff <= -2:
        p_bull, p_bear, p_side = Probability.BASSA, Probability.ALTA, Probability.MEDIA
    else:
        p_bull, p_bear, p_side = Probability.MEDIA, Probability.MEDIA, Probability.ALTA

    res_txt = f"la resistenza {nearest_res:.4f}" if nearest_res is not None else "i massimi recenti"
    sup_txt = f"il supporto {nearest_sup:.4f}" if nearest_sup is not None else "i minimi recenti"

    bullish = Scenario(
        type=ScenarioType.BULLISH,
        title="Scenario rialzista",
        probability=p_bull,
        narrative=(
            f"Prosecuzione al rialzo: tenuta dei supporti e superamento di {res_txt} "
            "aprirebbero spazio verso l'alto, con il momentum a confermare."
        ),
        key_levels=[nearest_res] if nearest_res is not None else [],
        invalidation=(
            f"Una chiusura sotto {sup_txt} indebolirebbe la tesi rialzista."
        ),
    )
    bearish = Scenario(
        type=ScenarioType.BEARISH,
        title="Scenario ribassista",
        probability=p_bear,
        narrative=(
            f"Discesa: cedimento di {sup_txt} esporrebbe a ulteriori ribassi "
            "verso i supporti successivi."
        ),
        key_levels=[nearest_sup] if nearest_sup is not None else [],
        invalidation=(
            f"Un ritorno deciso sopra {res_txt} indebolirebbe la tesi ribassista."
        ),
    )
    range_txt = (
        f" tra {nearest_sup:.4f} e {nearest_res:.4f}"
        if (nearest_sup is not None and nearest_res is not None)
        else ""
    )
    sideways = Scenario(
        type=ScenarioType.SIDEWAYS,
        title="Scenario laterale",
        probability=p_side,
        narrative=(
            f"Oscillazione in un range{range_txt}: assenza di direzione netta, "
            "tipica quando i segnali sono contrastanti o il momentum è debole."
        ),
        key_levels=[x for x in (nearest_sup, nearest_res) if x is not None],
        invalidation=(
            "Una chiusura decisa fuori dal range, accompagnata da volumi, "
            "segnalerebbe l'uscita dalla fase laterale."
        ),
    )
    return [bullish, bearish, sideways]


def assess_confidence(ta: TechnicalAnalysis) -> tuple[ConfidenceLevel, str]:
    if not ta.computed:
        return (
            ConfidenceLevel.BASSA,
            "Dati insufficienti: nessuna analisi prodotta, confidenza minima.",
        )

    bull, bear = _counts(ta)
    n = ta.data_quality.n_bars
    ample = n >= AMPLE_BARS
    conflict = bull > 0 and bear > 0
    strong = abs(bull - bear) >= 3

    if ample and strong and not conflict:
        level = ConfidenceLevel.ALTA
    elif (not ample) or (conflict and abs(bull - bear) <= 1):
        level = ConfidenceLevel.BASSA
    else:
        level = ConfidenceLevel.MEDIA

    rationale = (
        f"Storico di {n} barre ({'ampio' if ample else 'limitato'}); "
        f"segnali {bull} rialzisti / {bear} ribassisti "
        f"({'concordi' if not conflict else 'discordanti'}). "
        "La confidenza è qualitativa e riguarda la coerenza del quadro tecnico, "
        "NON la certezza dell'esito."
    )
    return level, rationale


def default_limits(ta: TechnicalAnalysis) -> list[str]:
    limits = [
        "Solo analisi tecnica: non considera fondamentali, bilanci, news, macro o eventi.",
        "Indicatori ritardati (medie, MACD, RSI): confermano il passato, non prevedono il futuro.",
        "Supporti/resistenze col metodo swing: visibili con qualche barra di ritardo.",
        "Fonti dati non ufficiali (yfinance) o di singolo exchange (ccxt): possibili errori/buchi.",
        "Le probabilità degli scenari sono QUALITATIVE, non calibrate statisticamente.",
        "I risultati passati non garantiscono quelli futuri.",
    ]
    if not ta.data_quality.sufficient:
        limits.insert(0, "ATTENZIONE: dati insufficienti — l'analisi è stata declinata.")
    return limits
