"""Test del layer di interpretazione tecnica."""

from __future__ import annotations

from helpers import build_linear_series

from quantanalyzer.analysis.technical import analyze_technical
from quantanalyzer.models import Direction


def _signal(analysis, name_prefix):
    for s in analysis.signals:
        if s.name.startswith(name_prefix):
            return s
    return None


def test_uptrend_is_computed_and_bullish():
    ta = analyze_technical(build_linear_series(n=260, start=100, step=1.0))
    assert ta.computed is True
    assert ta.current_price is not None
    assert len(ta.signals) == 6
    assert "rialzista" in ta.trend_summary.lower()
    # ogni segnale ha una spiegazione non vuota
    assert all(s.rationale for s in ta.signals)

    trend = _signal(ta, "Trend")
    assert trend.direction == Direction.BULLISH

    rsi_sig = _signal(ta, "RSI")
    assert rsi_sig.state == "ipercomprato"  # serie sempre crescente -> RSI 100
    assert rsi_sig.value == 100.0


def test_downtrend_is_bearish():
    ta = analyze_technical(build_linear_series(n=260, start=400, step=-1.0))
    assert ta.computed is True
    assert "ribassista" in ta.trend_summary.lower()
    assert _signal(ta, "Trend").direction == Direction.BEARISH
    assert _signal(ta, "RSI").state == "ipervenduto"


def test_insufficient_data_declines_to_interpret():
    ta = analyze_technical(build_linear_series(n=10))
    assert ta.computed is False
    assert ta.signals == []
    assert ta.support_resistance is None
    assert ta.notes  # spiega perché non ha interpretato
    assert ta.current_price is not None  # il prezzo grezzo resta disponibile
    assert ta.data_quality.sufficient is False


def test_support_resistance_present_in_uptrend():
    ta = analyze_technical(build_linear_series(n=120, start=50, step=0.5))
    assert ta.support_resistance is not None
    assert ta.support_resistance.current_price > 0
