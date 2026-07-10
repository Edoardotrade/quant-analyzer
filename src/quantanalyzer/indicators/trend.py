"""Indicatori di trend: medie mobili e pendenza."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """Media mobile semplice (Simple Moving Average).

    Restituisce NaN finché non ci sono almeno ``period`` osservazioni.
    """
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Media mobile esponenziale (adjust=False = ricorsione classica)."""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def last_slope(series: pd.Series, period: int) -> float:
    """Pendenza (variazione per barra) della retta di regressione sugli ultimi
    ``period`` valori validi. Positiva = media in salita, negativa = in discesa.
    """
    s = series.dropna()
    if len(s) < 2:
        return float("nan")
    y = s.iloc[-period:].to_numpy(dtype=float)
    x = np.arange(len(y), dtype=float)
    slope = np.polyfit(x, y, 1)[0]
    return float(slope)
