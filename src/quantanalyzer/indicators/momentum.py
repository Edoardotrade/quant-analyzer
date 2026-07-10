"""Indicatori di momentum: RSI e MACD."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .trend import ema


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index con lo smoothing di Wilder (implementazione esplicita).

    RSI = 100 - 100 / (1 + RS), con RS = media guadagni / media perdite.
    - Serie strettamente crescente -> nessuna perdita -> RSI = 100.
    - Serie strettamente decrescente -> nessun guadagno -> RSI = 0.
    Il primo valore valido è all'indice ``period`` (servono ``period`` variazioni).
    """
    close = close.astype(float)
    delta = close.diff()
    gains = delta.clip(lower=0.0).to_numpy()
    losses = (-delta.clip(upper=0.0)).to_numpy()
    n = len(close)
    out = np.full(n, np.nan)
    if n <= period:
        return pd.Series(out, index=close.index)

    # Seed di Wilder: media delle prime `period` variazioni (indici 1..period).
    avg_gain = float(np.nanmean(gains[1 : period + 1]))
    avg_loss = float(np.nanmean(losses[1 : period + 1]))

    def _rsi(ag: float, al: float) -> float:
        if al == 0.0:
            return 100.0
        if ag == 0.0:
            return 0.0
        rs = ag / al
        return 100.0 - 100.0 / (1.0 + rs)

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = _rsi(avg_gain, avg_loss)

    return pd.Series(out, index=close.index)


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD = EMA(fast) - EMA(slow); Signal = EMA(MACD); Hist = MACD - Signal.

    Restituisce un DataFrame con colonne ``macd``, ``signal``, ``hist``.
    """
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist},
        index=close.index,
    )
