"""Costruzione del piano di rischio con logica esplicita.

Regole (prudenti) applicate:
  - si opera SOLO nella direzione del trend (long se rialzista, short se ribassista);
    trend incerto/laterale => nessun trade.
  - stop = il PIÙ prudente tra stop-ATR (volatilità) e stop su livello tecnico
    (con cuscinetto), così da non essere espulsi dal rumore; se il livello tecnico
    è troppo lontano (> max_stop_atr·ATR) si usa lo stop-ATR.
  - target = livello tecnico realistico in direzione del profitto; se il suo R:R
    non raggiunge il minimo, il trade è dichiarato NON conveniente. Senza un livello
    tecnico si usa una proiezione a R:R minimo, segnalandolo.
  - dimensione posizione = (capitale · rischio%) / rischio-per-unità: il rischio in
    valuta è FISSO, la size si adatta alla distanza dello stop.
"""

from __future__ import annotations

import pandas as pd

from ..analysis.technical import analyze_technical
from ..indicators import atr as atr_indicator
from ..models import (
    Direction,
    PositionSide,
    PriceSeries,
    RiskParams,
    RiskPlan,
    TechnicalAnalysis,
)


def _last(series: pd.Series) -> float | None:
    s = series.dropna()
    return float(s.iloc[-1]) if len(s) else None


def _trend_direction(ta: TechnicalAnalysis) -> Direction:
    for signal in ta.signals:
        if signal.name.startswith("Trend"):
            return signal.direction
    return Direction.NEUTRAL


def build_risk_plan(
    series: PriceSeries,
    params: RiskParams,
    technical: TechnicalAnalysis | None = None,
) -> RiskPlan:
    """Calcola un piano di rischio a partire dalla serie e dai parametri."""
    ta = technical or analyze_technical(series)
    base = {"symbol": series.symbol, "capital": params.capital, "risk_pct": params.risk_pct}

    if not ta.computed:
        return RiskPlan(
            **base,
            side=PositionSide.NONE,
            viable=False,
            rationale=[
                "Analisi tecnica non disponibile (dati insufficienti): nessun piano di rischio."
            ],
            warnings=list(ta.notes),
        )

    direction = _trend_direction(ta)
    if direction == Direction.BULLISH:
        side = PositionSide.LONG
    elif direction == Direction.BEARISH:
        side = PositionSide.SHORT
    else:
        return RiskPlan(
            **base,
            side=PositionSide.NONE,
            viable=False,
            rationale=[
                "Trend incerto/laterale: nessun bias direzionale chiaro. "
                "La scelta prudente è NON forzare un trade."
            ],
        )

    df = series.to_frame()
    atr_val = _last(atr_indicator(df, params.atr_period))
    entry = float(df["close"].iloc[-1])
    if atr_val is None or atr_val <= 0:
        return RiskPlan(
            **base,
            side=side,
            viable=False,
            atr=atr_val,
            entry=round(entry, 4),
            rationale=["ATR non calcolabile: impossibile dimensionare stop e rischio."],
        )

    sr = ta.support_resistance
    supports = sorted((sr.supports if sr else []), reverse=True)
    resistances = sorted(sr.resistances if sr else [])

    sign = 1.0 if side == PositionSide.LONG else -1.0
    long = side == PositionSide.LONG
    # livelli di protezione (dietro l'entry) e di profitto (davanti)
    protective = supports if long else resistances
    profit = resistances if long else supports

    rationale: list[str] = []
    warnings: list[str] = []

    # --- ENTRY ---
    half = 0.5 * atr_val
    entry_zone = (
        (round(entry - half, 4), round(entry, 4))
        if long
        else (round(entry, 4), round(entry + half, 4))
    )
    rationale.append(
        f"Entry di riferimento al prezzo corrente {entry:.4f}. Zona di ingresso suggerita "
        f"{entry_zone}: entrare in {'debolezza' if long else 'forza'} (± 0,5·ATR) migliora il "
        "rischio rispetto a inseguire il prezzo."
    )

    # --- STOP ---
    atr_stop = entry - sign * params.atr_stop_mult * atr_val
    stop = atr_stop
    stop_basis = f"ATR (volatilità): {params.atr_stop_mult}·ATR dall'entry"
    if protective:
        level = protective[0]  # livello più vicino
        tech_stop = level - sign * params.tech_stop_buffer_atr * atr_val
        tech_dist = abs(entry - tech_stop)
        if tech_dist <= params.max_stop_atr * atr_val:
            if tech_dist >= abs(entry - atr_stop):
                stop = tech_stop
                lvl_name = "supporto" if long else "resistenza"
                stop_basis = f"livello tecnico ({lvl_name} {level:.4f}) con cuscinetto ATR"
            else:
                stop_basis = "ATR (volatilità) — più prudente del livello tecnico vicino"
        else:
            warnings.append(
                f"Livello tecnico di stop lontano (> {params.max_stop_atr}·ATR): uso lo stop-ATR."
            )

    risk_per_unit = abs(entry - stop)
    rationale.append(
        f"Stop a {stop:.4f} [{stop_basis}]. Rischio per unità |entry−stop| = {risk_per_unit:.4f}."
    )

    # --- TARGET ---
    meets_min_rr = False
    if profit:
        target = profit[0]
        reward_per_unit = abs(target - entry)
        rr = reward_per_unit / risk_per_unit if risk_per_unit else 0.0
        target_basis = (
            f"resistenza tecnica più vicina ({target:.4f})"
            if long
            else f"supporto tecnico più vicino ({target:.4f})"
        )
        if rr >= params.min_rr:
            meets_min_rr = True
        else:
            warnings.append(
                f"Il target tecnico realistico offre R:R {rr:.2f} < minimo {params.min_rr}: "
                "il trade NON ripaga il rischio a questi livelli."
            )
    else:
        target = entry + sign * params.min_rr * risk_per_unit
        reward_per_unit = abs(target - entry)
        rr = params.min_rr
        meets_min_rr = True
        target_basis = f"proiezione a R:R {params.min_rr}:1 (nessun livello tecnico in profitto)"
        warnings.append(
            "Target da proiezione R:R, non da un livello osservato: usare con cautela."
        )
    rationale.append(
        f"Target a {target:.4f} [{target_basis}]. Rendimento per unità = {reward_per_unit:.4f}; "
        f"R:R = {rr:.2f} (minimo richiesto {params.min_rr})."
    )

    # --- DIMENSIONE POSIZIONE ---
    risk_amount = params.capital * params.risk_pct / 100.0
    size_units = risk_amount / risk_per_unit if risk_per_unit else 0.0
    notional = size_units * entry
    rationale.append(
        f"Rischio in valuta = {params.risk_pct}% di {params.capital:.2f} = {risk_amount:.2f}. "
        f"Size = rischio / rischio-per-unità = {size_units:.4f} unità "
        f"(controvalore ~{notional:.2f}). Arrotondare al lotto minimo dipende dallo strumento."
    )
    if notional > params.capital:
        warnings.append(
            "La size basata sul rischio richiede un controvalore superiore al capitale "
            "(servirebbe leva): valuta di ridurre il rischio% o di non entrare."
        )

    viable = meets_min_rr and risk_per_unit > 0
    if viable:
        rationale.append(
            f"R:R {rr:.2f} ≥ minimo {params.min_rr}: setup coerente col profilo di rischio scelto. "
            "Resta un'ipotesi probabilistica, non una certezza."
        )
    else:
        rationale.append(
            "Setup NON conveniente al momento: meglio attendere un entry migliore, un target "
            "più ampio o un altro strumento, piuttosto che accettare un R:R sfavorevole."
        )

    return RiskPlan(
        **base,
        side=side,
        viable=viable,
        entry=round(entry, 4),
        entry_zone=entry_zone,
        stop=round(stop, 4),
        stop_basis=stop_basis,
        target=round(target, 4),
        target_basis=target_basis,
        atr=round(atr_val, 4),
        risk_per_unit=round(risk_per_unit, 4),
        reward_per_unit=round(reward_per_unit, 4),
        rr=round(rr, 2),
        meets_min_rr=meets_min_rr,
        risk_amount=round(risk_amount, 2),
        position_size_units=round(size_units, 6),
        position_notional=round(notional, 2),
        rationale=rationale,
        warnings=warnings,
    )
