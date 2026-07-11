"""Indicatori tecnici implementati in casa (matematica esplicita e testabile).

Scelta di design: NON usiamo una libreria black-box. Ogni indicatore è codice
leggibile e coperto da test, coerente col principio "logica esplicita, niente
numeri campati in aria". Tutte le funzioni lavorano su pandas Series/DataFrame.
"""

from .levels import support_resistance, swing_highs, swing_lows
from .momentum import macd, rsi
from .strength import adx
from .trend import ema, last_slope, sma
from .volatility import atr, bollinger, true_range
from .volume import obv, relative_volume, volume_sma

__all__ = [
    "sma",
    "ema",
    "last_slope",
    "rsi",
    "macd",
    "adx",
    "atr",
    "true_range",
    "bollinger",
    "swing_highs",
    "swing_lows",
    "support_resistance",
    "volume_sma",
    "relative_volume",
    "obv",
]
