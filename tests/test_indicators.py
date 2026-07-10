"""Test degli indicatori: proprietà matematiche note su input deterministici."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantanalyzer.indicators import (
    atr,
    bollinger,
    ema,
    last_slope,
    macd,
    obv,
    relative_volume,
    rsi,
    sma,
    support_resistance,
    swing_highs,
    true_range,
    volume_sma,
)


def test_sma_of_constant_is_constant():
    s = pd.Series([5.0] * 30)
    out = sma(s, 10).dropna()
    assert (out == 5.0).all()
    assert len(out) == 21  # 30 - 10 + 1


def test_ema_of_constant_is_constant():
    s = pd.Series([7.0] * 30)
    out = ema(s, 10).dropna()
    assert np.allclose(out.to_numpy(), 7.0)


def test_rsi_monotonic_increasing_is_100():
    s = pd.Series(np.arange(1, 51, dtype=float))
    assert rsi(s, 14).dropna().iloc[-1] == 100.0


def test_rsi_monotonic_decreasing_is_0():
    s = pd.Series(np.arange(50, 0, -1, dtype=float))
    assert rsi(s, 14).dropna().iloc[-1] == 0.0


def test_rsi_bounded_0_100():
    rng = np.sin(np.linspace(0, 20, 100)) * 10 + 100
    out = rsi(pd.Series(rng), 14).dropna()
    assert out.min() >= 0.0
    assert out.max() <= 100.0


def test_macd_hist_equals_macd_minus_signal():
    s = pd.Series(np.cumsum(np.sin(np.linspace(0, 30, 200))) + 100)
    frame = macd(s).dropna()
    diff = (frame["macd"] - frame["signal"] - frame["hist"]).abs()
    assert diff.max() < 1e-9


def test_true_range_and_atr_constant():
    df = pd.DataFrame({"high": [11.0] * 20, "low": [9.0] * 20, "close": [10.0] * 20})
    tr = true_range(df)
    assert np.allclose(tr.to_numpy(), 2.0)
    assert abs(atr(df, 14).dropna().iloc[-1] - 2.0) < 1e-9


def test_bollinger_ordering():
    s = pd.Series(np.arange(1, 41, dtype=float))
    frame = bollinger(s, 20, 2.0).dropna()
    last = frame.iloc[-1]
    assert last["upper"] > last["mid"] > last["lower"]
    # la media centrale coincide con la SMA
    assert abs(last["mid"] - sma(s, 20).dropna().iloc[-1]) < 1e-9


def test_volume_sma_and_relative_volume():
    v = pd.Series([100.0] * 30)
    assert relative_volume(v, 20).dropna().iloc[-1] == 1.0
    assert volume_sma(v, 20).dropna().iloc[-1] == 100.0


def test_obv_rises_with_rising_price():
    close = pd.Series(np.arange(1, 21, dtype=float))
    vol = pd.Series([100.0] * 20)
    out = obv(close, vol)
    assert out.iloc[-1] > out.iloc[1]


def test_last_slope_sign():
    up = pd.Series(np.arange(0, 20, dtype=float))
    down = pd.Series(np.arange(20, 0, -1, dtype=float))
    assert last_slope(up, 10) > 0
    assert last_slope(down, 10) < 0


def test_swing_highs_detects_peak():
    idx = pd.date_range("2024-01-01", periods=11, freq="D")
    high = [1, 2, 3, 4, 5, 10, 5, 4, 3, 2, 1]
    low = [h - 1 for h in high]
    df = pd.DataFrame({"high": high, "low": low}, index=idx)
    peaks = swing_highs(df, left=2, right=2)
    assert any(price == 10.0 for _, price in peaks)


def test_support_resistance_splits_around_price():
    idx = pd.date_range("2024-01-01", periods=9, freq="D")
    high = [5, 6, 20, 6, 5, 6, 7, 6, 5]
    low = [5, 4, 3, 4, 5, 1, 5, 4, 5]
    df = pd.DataFrame({"high": high, "low": low}, index=idx)
    supports, resistances = support_resistance(df, current_price=10.0, lookback=2)
    assert all(s < 10.0 for s in supports)
    assert all(r > 10.0 for r in resistances)
    assert 20.0 in resistances
    # i supporti sono ordinati dal più vicino al prezzo
    assert supports == sorted(supports, reverse=True)
