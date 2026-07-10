"""Test dell'helper puro dei grafici della dashboard (senza runtime Streamlit)."""

from __future__ import annotations

from helpers import build_linear_series

from quantanalyzer.dashboard.charts import indicators_frame
from quantanalyzer.models import IndicatorParams


def test_indicators_frame_columns_and_length():
    series = build_linear_series(n=260)
    frame = indicators_frame(series)
    assert len(frame) == 260
    for col in [
        "close", "SMA20", "SMA50", "SMA200", "EMA20",
        "RSI", "MACD", "MACD_signal", "MACD_hist", "BB_upper", "BB_lower",
    ]:
        assert col in frame.columns
    assert frame["close"].iloc[-1] == series.last_close


def test_indicators_frame_respects_custom_params():
    series = build_linear_series(n=120)
    frame = indicators_frame(series, IndicatorParams(sma_periods=(5, 10, 20)))
    assert "SMA5" in frame.columns
    assert "SMA20" in frame.columns
