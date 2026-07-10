"""Test del segnale operativo (ENTRA/ASPETTA in linguaggio semplice)."""

from __future__ import annotations

from helpers import build_linear_series

from quantanalyzer.analysis.signal import build_operating_signal
from quantanalyzer.models import RiskParams, SignalAction

PARAMS = RiskParams(capital=10_000, risk_pct=1.0, min_rr=2.0)


def test_uptrend_overbought_says_wait():
    sig = build_operating_signal(build_linear_series(n=260, step=1.0), PARAMS)
    assert sig.action == SignalAction.WAIT
    assert "ASPETTA" in sig.headline
    assert sig.reason  # spiega perché e cosa aspettare
    # i livelli di riferimento restano comunque disponibili
    assert sig.entry is not None
    assert sig.stop_loss is not None


def test_insufficient_data_says_none():
    sig = build_operating_signal(build_linear_series(n=8), PARAMS)
    assert sig.action == SignalAction.NONE
    assert "insufficient" in sig.headline.lower() or "insufficient" in sig.reason.lower()


def test_signal_carries_price_and_symbol():
    sig = build_operating_signal(build_linear_series(n=260, symbol="EURUSD"), PARAMS)
    assert sig.symbol == "EURUSD"
    assert sig.price is not None
