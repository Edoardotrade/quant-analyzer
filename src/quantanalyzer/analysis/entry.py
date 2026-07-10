"""Piano d'ingresso: i 4 'cancelli' + trigger + invalidazione.

Traduce analisi tecnica + piano di rischio in una risposta disciplinata alla
domanda 'quando entrare?', SENZA mai dire 'compra adesso': se anche un solo
cancello è chiuso, il verdetto è 'attendere', con i trigger espliciti da aspettare.
"""

from __future__ import annotations

from ..models import (
    EntryGate,
    EntryPlaybook,
    PositionSide,
    RiskPlan,
    TechnicalAnalysis,
)


def _rsi_value(ta: TechnicalAnalysis) -> float | None:
    for s in ta.signals:
        if s.name.startswith("RSI"):
            return s.value
    return None


def build_entry_playbook(
    ta: TechnicalAnalysis,
    plan: RiskPlan | None,
    *,
    min_rr: float = 2.0,
    rsi_overbought: float = 70.0,
    rsi_oversold: float = 30.0,
) -> EntryPlaybook | None:
    """Costruisce il piano d'ingresso. Richiede analisi calcolata e piano di rischio."""
    if not ta.computed or plan is None:
        return None

    side = plan.side
    long = side == PositionSide.LONG
    sr = ta.support_resistance
    supports = sr.supports if sr else []
    resistances = sr.resistances if sr else []
    nearest_sup = supports[0] if supports else None
    nearest_res = resistances[0] if resistances else None
    rsi = _rsi_value(ta)

    gates: list[EntryGate] = []

    # Cancello 1 — direzione
    g1 = side != PositionSide.NONE
    gates.append(
        EntryGate(
            name="Direzione (trend chiaro)",
            passed=g1,
            detail=(
                ("Trend rialzista → bias long." if long else "Trend ribassista → bias short.")
                if g1
                else "Trend incerto/laterale: nessun bias direzionale."
            ),
        )
    )

    # Cancello 2 — momentum non in eccesso
    if not g1:
        g2, d2 = False, "Non valutabile senza una direzione."
    elif rsi is None:
        g2, d2 = True, "RSI non disponibile: nessun eccesso rilevato."
    elif long and rsi >= rsi_overbought:
        g2, d2 = False, f"RSI {rsi:.0f} ipercomprato: comprare qui è inseguire il prezzo."
    elif (not long) and rsi <= rsi_oversold:
        g2, d2 = False, f"RSI {rsi:.0f} ipervenduto: vendere qui è inseguire il prezzo."
    else:
        g2, d2 = True, f"RSI {rsi:.0f}: nessun eccesso, momentum utilizzabile."
    gates.append(EntryGate(name="Momentum non in eccesso", passed=g2, detail=d2))

    # Cancello 3 — rapporto rischio/rendimento
    g3 = bool(plan.meets_min_rr)
    gates.append(
        EntryGate(
            name=f"Rapporto rischio/rendimento ≥ {min_rr}",
            passed=g3,
            detail=(
                f"R:R {plan.rr} sul target realistico."
                if plan.rr is not None
                else "R:R non calcolabile."
            ),
        )
    )

    # Cancello 4 — rischio dimensionabile
    g4 = plan.risk_per_unit is not None and plan.risk_per_unit > 0
    if g4:
        d4 = "Stop e dimensione posizione definiti."
    else:
        d4 = "Stop non definibile: rischio non misurabile."
    if g4 and plan.position_notional is not None and plan.position_notional > plan.capital:
        d4 += " Nota: la size richiederebbe leva (controvalore > capitale)."
    gates.append(EntryGate(name="Rischio dimensionabile", passed=g4, detail=d4))

    ready = all(g.passed for g in gates)

    triggers: list[str] = []
    if ready:
        triggers.append(
            f"Ingresso nella zona {plan.entry_zone}, con una candela di conferma nella "
            "direzione del trade (non entrare in anticipo)."
        )
        triggers.append(
            f"Stop {plan.stop}, target {plan.target} (R:R {plan.rr}), "
            f"size {plan.position_size_units} unità (rischio {plan.risk_amount})."
        )
    elif not g1:
        triggers.append(
            "Attendi un trend definito (medie allineate / incrocio) prima di valutare un ingresso."
        )
    elif long:
        if nearest_res is not None:
            triggers.append(
                f"ROTTURA: chiusura decisa sopra la resistenza {nearest_res:.4f} con volumi, "
                "poi rivaluta stop e target sul nuovo assetto."
            )
        pull = "la zona di ingresso"
        if nearest_sup is not None:
            pull = f"il supporto {nearest_sup:.4f}"
        triggers.append(
            f"PULLBACK: ritracciamento verso {pull} mantenendo il prezzo sopra la SMA di medio "
            "periodo → stop più stretto e R:R migliore."
        )
        if not g2:
            triggers.append(f"Attendi il rientro dell'RSI sotto {rsi_overbought:.0f}.")
    else:
        if nearest_sup is not None:
            triggers.append(
                f"ROTTURA: chiusura decisa sotto il supporto {nearest_sup:.4f} con volumi, "
                "poi rivaluta stop e target."
            )
        bounce = "la zona di ingresso"
        if nearest_res is not None:
            bounce = f"la resistenza {nearest_res:.4f}"
        triggers.append(
            f"PULLBACK: rimbalzo verso {bounce} restando sotto la SMA di medio periodo → "
            "stop più stretto."
        )
        if not g2:
            triggers.append(f"Attendi il rientro dell'RSI sopra {rsi_oversold:.0f}.")

    if long:
        ref = f"{nearest_sup:.4f}" if nearest_sup is not None else str(plan.stop)
        invalidation = (
            f"Chiusura sotto {ref} o sotto la SMA di medio periodo → il bias rialzista decade."
        )
    else:
        ref = f"{nearest_res:.4f}" if nearest_res is not None else str(plan.stop)
        invalidation = (
            f"Chiusura sopra {ref} o sopra la SMA di medio periodo → il bias ribassista decade."
        )

    verdict = "Setup presente: cancelli superati" if ready else "Attendere: setup non ancora pronto"
    return EntryPlaybook(
        symbol=ta.symbol,
        side=side,
        ready=ready,
        verdict=verdict,
        gates=gates,
        triggers=triggers,
        invalidation=invalidation,
    )
