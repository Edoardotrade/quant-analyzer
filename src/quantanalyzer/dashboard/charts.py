"""Preparazione dei dati per i grafici della dashboard.

Modulo PURO (nessun import di Streamlit): produce un DataFrame con prezzo e
indicatori, così la logica di charting è testabile senza il runtime Streamlit.
"""

from __future__ import annotations

import pandas as pd

from ..indicators import bollinger, ema, macd, rsi, sma
from ..models import IndicatorParams, PriceSeries


def indicators_frame(series: PriceSeries, params: IndicatorParams | None = None) -> pd.DataFrame:
    """DataFrame indicizzato per data con prezzo + indicatori per i grafici.

    Colonne: close, SMA{f}, SMA{m}, SMA{l}, EMA{f}, RSI, MACD, MACD_signal,
    MACD_hist, BB_upper, BB_lower.
    """
    p = params or IndicatorParams()
    df = series.to_frame()
    close = df["close"]
    s_fast, s_mid, s_slow = p.sma_periods

    out = pd.DataFrame(index=df.index)
    out["close"] = close
    out[f"SMA{s_fast}"] = sma(close, s_fast)
    out[f"SMA{s_mid}"] = sma(close, s_mid)
    out[f"SMA{s_slow}"] = sma(close, s_slow)
    out[f"EMA{s_fast}"] = ema(close, s_fast)

    out["RSI"] = rsi(close, p.rsi_period)

    macd_frame = macd(close, p.macd_fast, p.macd_slow, p.macd_signal)
    out["MACD"] = macd_frame["macd"]
    out["MACD_signal"] = macd_frame["signal"]
    out["MACD_hist"] = macd_frame["hist"]

    bb = bollinger(close, p.bb_period, p.bb_std)
    out["BB_upper"] = bb["upper"]
    out["BB_lower"] = bb["lower"]
    return out
