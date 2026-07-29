"""Segnale operativo: la risposta semplice a 'cosa faccio, dove, con quale SL/TP?'.

Unisce analisi tecnica + piano di rischio + piano d'ingresso in un unico oggetto
in linguaggio comprensibile (COMPRA/VENDI/ASPETTA), pensato per l'utente finale.
"""

from __future__ import annotations

from ..models import (
    OperatingSignal,
    PositionSide,
    PriceSeries,
    RiskParams,
    SignalAction,
)
from ..risk.planner import build_risk_plan
from .entry import build_entry_playbook
from .market_hours import market_status
from .technical import analyze_technical


def _verb(side: PositionSide) -> str:
    return "COMPRA" if side == PositionSide.LONG else "VENDI"


def _asset_label(symbol: str) -> str:
    nice = {"XAUUSD": "oro", "XAGUSD": "argento", "WTIUSD": "petrolio"}
    return nice.get(symbol.upper(), symbol)


def build_operating_signal(series: PriceSeries, risk_params: RiskParams) -> OperatingSignal:
    """Costruisce il segnale operativo per un asset."""
    ta = analyze_technical(series)
    is_open, market_note = market_status(series.asset_class)
    base = {
        "symbol": series.symbol,
        "asset_class": series.asset_class,
        "interval": series.interval,
        "price": series.last_close,
        "as_of": series.end,
        "market_open": is_open,
        "market_note": market_note,
    }

    if not ta.computed:
        return OperatingSignal(
            **base,
            action=SignalAction.NONE,
            side=PositionSide.NONE,
            ready=False,
            headline=f"⚠️ {series.symbol}: dati insufficienti per un segnale.",
            reason="Storico troppo breve o dati non affidabili.",
        )

    plan = build_risk_plan(series, risk_params, technical=ta)
    playbook = build_entry_playbook(ta, plan, min_rr=risk_params.min_rr)

    if playbook is not None and playbook.ready:
        verb = _verb(plan.side)
        verso = "rialzo" if plan.side == PositionSide.LONG else "ribasso"
        label = _asset_label(series.symbol)
        headline = (
            f"🟢 {verb} {series.symbol} ({label}) a ~{plan.entry} · "
            f"SL {plan.stop} · TP {plan.target}"
        )
        return OperatingSignal(
            **base,
            action=SignalAction.ENTER,
            side=plan.side,
            ready=True,
            entry=plan.entry,
            stop_loss=plan.stop,
            take_profit=plan.target,
            rr=plan.rr,
            size_units=plan.position_size_units,
            headline=headline,
            reason=(
                f"Tutti i controlli superati: {verso} con rischio/rendimento {plan.rr}. "
                f"Rischi {plan.risk_amount} sul capitale."
            ),
        )

    # ASPETTA: spiega in una riga perché e cosa aspettare
    if playbook is not None:
        failed = next((g for g in playbook.gates if not g.passed), None)
        why = failed.detail if failed else "condizioni non ottimali"
        wait_for = playbook.triggers[0] if playbook.triggers else "un setup migliore"
    else:
        why = "nessun piano disponibile"
        wait_for = "un setup migliore"

    side_txt = ""
    if plan.side == PositionSide.LONG:
        side_txt = " (inclinazione: rialzo)"
    elif plan.side == PositionSide.SHORT:
        side_txt = " (inclinazione: ribasso)"

    return OperatingSignal(
        **base,
        action=SignalAction.WAIT,
        side=plan.side,
        ready=False,
        entry=plan.entry,
        stop_loss=plan.stop,
        take_profit=plan.target,
        rr=plan.rr,
        headline=f"⏳ ASPETTA {series.symbol}{side_txt}",
        reason=f"Perché: {why} → Aspetta: {wait_for}",
    )
