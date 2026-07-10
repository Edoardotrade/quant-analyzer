"""Indicatori di volatilità: True Range / ATR e Bollinger Bands."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .trend import sma


def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range = max(high-low, |high-close_prev|, |low-close_prev|).

    Alla prima barra (close precedente assente) si riduce a high-low.
    """
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    prev_close = df["close"].astype(float).shift(1)
    ranges = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1)


def _wilder(values: np.ndarray, period: int) -> np.ndarray:
    """Smoothing di Wilder (RMA): seed = SMA delle prime ``period`` osservazioni."""
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return out
    seed = float(np.mean(values[:period]))
    out[period - 1] = seed
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period
    return out


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder). Misura la volatilità media in valore assoluto.

    Base oggettiva per dimensionare stop e target nella Fase 3.
    """
    tr = true_range(df)
    smoothed = _wilder(tr.to_numpy(dtype=float), period)
    return pd.Series(smoothed, index=df.index)


def bollinger(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Bande di Bollinger: media mobile ± num_std deviazioni standard (ddof=0).

    Restituisce colonne ``mid``, ``upper``, ``lower``.
    """
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return pd.DataFrame(
        {"mid": mid, "upper": upper, "lower": lower},
        index=close.index,
    )
