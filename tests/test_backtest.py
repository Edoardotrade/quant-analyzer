"""Test del motore di backtesting."""

from __future__ import annotations

import pytest
from helpers import build_linear_series, build_wave_series

from quantanalyzer.backtest.engine import run_backtest
from quantanalyzer.models import BacktestParams, PositionSide

PARAMS = BacktestParams(capital=10_000, risk_pct=1.0, sma_fast=10, sma_slow=30)


def test_backtest_generates_trades_and_consistent_metrics():
    result = run_backtest(build_wave_series(n=500, amp=25, period=50), PARAMS)
    assert result.computed is True
    assert result.n_trades > 0
    # invarianti di base
    assert result.wins + result.losses == result.n_trades
    assert 0.0 <= result.win_rate <= 1.0
    assert result.final_equity > 0
    assert result.profit_factor is None or result.profit_factor >= 0
    # ogni trade è coerente e senza lookahead (uscita dopo l'ingresso)
    for t in result.trades:
        assert t.exit_index > t.entry_index
        assert t.bars_held >= 1
        assert t.entry_date is not None and t.exit_date is not None


def test_backtest_long_only_has_only_long_trades():
    params = BacktestParams(capital=10_000, sma_fast=10, sma_slow=30, direction="long")
    result = run_backtest(build_wave_series(n=500, amp=25, period=50), params)
    assert all(t.side == PositionSide.LONG for t in result.trades)


def test_backtest_reports_buy_hold_benchmark():
    result = run_backtest(build_wave_series(n=500, drift=0.05), PARAMS)
    assert isinstance(result.buy_hold_return_pct, float)
    # con drift positivo il buy&hold è positivo
    assert result.buy_hold_return_pct > 0


def test_backtest_insufficient_data():
    result = run_backtest(build_linear_series(n=30), PARAMS)
    assert result.computed is False
    assert result.n_trades == 0
    assert result.notes


def test_backtest_params_reject_fast_ge_slow():
    with pytest.raises(ValueError):
        BacktestParams(capital=10_000, sma_fast=50, sma_slow=50)


def test_backtest_costs_reduce_return():
    base = run_backtest(build_wave_series(n=500, amp=25, period=50), PARAMS)
    with_costs = run_backtest(
        build_wave_series(n=500, amp=25, period=50),
        BacktestParams(capital=10_000, sma_fast=10, sma_slow=30, cost_bps=20),
    )
    # a parità di trade, i costi non possono migliorare il rendimento
    if base.n_trades > 0:
        assert with_costs.total_return_pct <= base.total_return_pct
