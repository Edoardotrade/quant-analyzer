"""Test del risk planner (entry, stop, target, R:R, sizing)."""

from __future__ import annotations

from helpers import build_linear_series, build_ta

from quantanalyzer.models import Direction, PositionSide, RiskParams
from quantanalyzer.risk.planner import build_risk_plan

PARAMS = RiskParams(capital=10_000, risk_pct=1.0, min_rr=2.0, atr_stop_mult=1.5)


def test_long_projection_target_when_no_levels():
    # Serie monotòna crescente: nessuno swing => nessun S/R => target di proiezione.
    series = build_linear_series(n=260, start=100, step=1.0)
    plan = build_risk_plan(series, PARAMS)

    assert plan.side == PositionSide.LONG
    assert plan.viable is True
    assert plan.stop < plan.entry < plan.target
    assert "ATR" in plan.stop_basis
    assert "proiezione" in plan.target_basis.lower()
    assert abs(plan.rr - 2.0) < 1e-6
    assert plan.risk_amount == 100.0  # 1% di 10.000
    # size = rischio in valuta / rischio per unità
    assert abs(plan.position_size_units - 100.0 / plan.risk_per_unit) < 1e-3


def test_short_when_downtrend():
    series = build_linear_series(n=260, start=400, step=-1.0)
    plan = build_risk_plan(series, PARAMS)
    assert plan.side == PositionSide.SHORT
    assert plan.viable is True
    assert plan.stop > plan.entry > plan.target


def test_technical_stop_and_target_used():
    # entry ~360 (ultima chiusura), ATR ~2.02.
    series = build_linear_series(n=260, start=100, step=1.0)
    ta = build_ta(Direction.BULLISH, price=360.0, supports=[355.0], resistances=[375.0])
    plan = build_risk_plan(series, PARAMS, technical=ta)

    assert plan.side == PositionSide.LONG
    assert plan.viable is True
    assert plan.meets_min_rr is True
    assert "supporto" in plan.stop_basis
    assert "resistenza" in plan.target_basis
    assert plan.target == 375.0
    assert plan.rr > 2.0
    assert plan.risk_amount == 100.0


def test_low_rr_makes_plan_not_viable():
    series = build_linear_series(n=260, start=100, step=1.0)
    # resistenza troppo vicina: target realistico con R:R < minimo.
    ta = build_ta(Direction.BULLISH, price=360.0, supports=[], resistances=[362.0])
    plan = build_risk_plan(series, PARAMS, technical=ta)

    assert plan.viable is False
    assert plan.meets_min_rr is False
    assert "resistenza" in plan.target_basis
    assert any("R:R" in w for w in plan.warnings)


def test_neutral_trend_declines_trade():
    series = build_linear_series(n=60)
    ta = build_ta(Direction.NEUTRAL, price=160.0)
    plan = build_risk_plan(series, PARAMS, technical=ta)
    assert plan.side == PositionSide.NONE
    assert plan.viable is False
    assert any("laterale" in r.lower() or "direzionale" in r.lower() for r in plan.rationale)


def test_insufficient_data_no_plan():
    series = build_linear_series(n=10)
    plan = build_risk_plan(series, PARAMS)
    assert plan.side == PositionSide.NONE
    assert plan.viable is False
    assert plan.rationale
