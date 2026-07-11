"""Forza del trend: ADX (Average Directional Index).

L'ADX misura QUANTO è forte un trend (0-100), non la sua direzione: valori bassi
(<20) indicano mercato laterale/debole, dove gli ingressi di tendenza rendono meno.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .volatility import true_range


def _rma(series: pd.Series, period: int) -> pd.Series:
    """Media di Wilder (RMA) via ewm."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (forza del trend)."""
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)

    atr = _rma(true_range(df), period)
    plus_di = 100.0 * _rma(plus_dm, period) / atr
    minus_di = 100.0 * _rma(minus_dm, period) / atr

    denom = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denom
    return _rma(dx, period)
