"""Assembla il MarketReport unendo dati, analisi tecnica, rischio e scenari."""

from __future__ import annotations

from .. import DISCLAIMER
from ..analysis.entry import build_entry_playbook
from ..analysis.technical import analyze_technical
from ..models import MarketReport, PriceSeries, RiskParams
from ..risk.planner import build_risk_plan
from .scenarios import assess_confidence, build_scenarios, default_limits


def build_report(
    series: PriceSeries,
    risk_params: RiskParams | None = None,
) -> MarketReport:
    """Costruisce il report completo.

    Se ``risk_params`` è fornito (contiene il capitale), include il piano di rischio;
    altrimenti il report resta su dati + analisi + scenari.
    """
    ta = analyze_technical(series)
    risk_plan = (
        build_risk_plan(series, risk_params, technical=ta) if risk_params is not None else None
    )
    entry_playbook = build_entry_playbook(
        ta, risk_plan, min_rr=risk_params.min_rr if risk_params else 2.0
    )
    scenarios = build_scenarios(ta)
    confidence, confidence_rationale = assess_confidence(ta)
    limits = default_limits(ta)

    return MarketReport(
        symbol=series.symbol,
        asset_class=series.asset_class,
        interval=series.interval,
        as_of=series.end,
        current_price=series.last_close,
        data_quality=ta.data_quality,
        technical=ta,
        risk_plan=risk_plan,
        entry_playbook=entry_playbook,
        scenarios=scenarios,
        confidence=confidence,
        confidence_rationale=confidence_rationale,
        limits=limits,
        disclaimer=DISCLAIMER,
    )
