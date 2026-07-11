"""Test del piano d'ingresso (i 4 cancelli + trigger + invalidazione)."""

from __future__ import annotations

from helpers import build_linear_series, build_ta

from quantanalyzer.analysis.entry import build_entry_playbook
from quantanalyzer.analysis.technical import analyze_technical
from quantanalyzer.models import Direction, PositionSide, RiskParams
from quantanalyzer.risk.planner import build_risk_plan

PARAMS = RiskParams(capital=10_000, risk_pct=1.0, min_rr=2.0)


def _gate(pb, prefix):
    return next(g for g in pb.gates if g.name.startswith(prefix))


def test_overbought_uptrend_is_not_ready():
    # serie monotòna crescente -> RSI 100 -> cancello momentum chiuso
    series = build_linear_series(n=260, step=1.0)
    ta = analyze_technical(series)
    plan = build_risk_plan(series, PARAMS, technical=ta)
    pb = build_entry_playbook(ta, plan, min_rr=2.0)

    assert pb is not None
    assert pb.side == PositionSide.LONG
    assert pb.ready is False
    assert _gate(pb, "Momentum").passed is False
    assert pb.triggers  # dice cosa aspettare
    assert "rialzista" in pb.invalidation.lower() or "SMA" in pb.invalidation


def test_all_gates_pass_is_ready():
    # trend rialzista, RSI assente (nessun eccesso), R:R buono via livelli tecnici
    series = build_linear_series(n=260, step=1.0)  # prezzo ~360, ATR ~2.02
    ta = build_ta(Direction.BULLISH, price=360.0, supports=[355.0], resistances=[375.0])
    plan = build_risk_plan(series, PARAMS, technical=ta)
    pb = build_entry_playbook(ta, plan, min_rr=2.0)

    assert pb.ready is True
    assert pb.side == PositionSide.LONG
    assert all(g.passed for g in pb.gates)
    assert "presente" in pb.verdict.lower()


def test_weak_adx_blocks_entry():
    series = build_linear_series(n=260, step=1.0)
    ta = build_ta(
        Direction.BULLISH, price=360.0, supports=[355.0], resistances=[375.0], adx=15.0
    )
    plan = build_risk_plan(series, PARAMS, technical=ta)
    pb = build_entry_playbook(ta, plan, min_rr=2.0)
    assert pb.ready is False
    assert _gate(pb, "Forza del trend").passed is False


def test_counter_weekly_trend_blocks_entry():
    series = build_linear_series(n=260, step=1.0)
    ta = build_ta(
        Direction.BULLISH,
        price=360.0,
        supports=[355.0],
        resistances=[375.0],
        adx=30.0,
        weekly=Direction.BEARISH,
    )
    plan = build_risk_plan(series, PARAMS, technical=ta)
    pb = build_entry_playbook(ta, plan, min_rr=2.0)
    assert pb.ready is False
    assert _gate(pb, "Allineato").passed is False


def test_low_rr_closes_rr_gate():
    series = build_linear_series(n=260, step=1.0)
    ta = build_ta(Direction.BULLISH, price=360.0, supports=[], resistances=[362.0])
    plan = build_risk_plan(series, PARAMS, technical=ta)
    pb = build_entry_playbook(ta, plan, min_rr=2.0)

    assert pb.ready is False
    assert _gate(pb, "Rapporto").passed is False


def test_neutral_trend_closes_direction_gate():
    series = build_linear_series(n=260, step=1.0)
    ta = build_ta(Direction.NEUTRAL, price=360.0)
    plan = build_risk_plan(series, PARAMS, technical=ta)
    pb = build_entry_playbook(ta, plan, min_rr=2.0)

    assert pb.side == PositionSide.NONE
    assert pb.ready is False
    assert _gate(pb, "Direzione").passed is False


def test_insufficient_data_returns_none():
    series = build_linear_series(n=10)
    ta = analyze_technical(series)
    plan = build_risk_plan(series, PARAMS, technical=ta)
    assert build_entry_playbook(ta, plan) is None
