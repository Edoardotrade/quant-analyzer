"""Supporti e resistenze da swing points (massimi/minimi locali).

Metodo trasparente: una barra è uno *swing high* se il suo massimo è il più alto
in una finestra simmetrica di ``left`` barre a sinistra e ``right`` a destra
(analogo per gli swing low). È un metodo classico e spiegabile; ha il limite di
"vedere" i pivot solo con ``right`` barre di ritardo (nessun indicatore è magico).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd


def swing_highs(df: pd.DataFrame, left: int = 5, right: int = 5) -> list[tuple[datetime, float]]:
    highs = df["high"].astype(float).to_numpy()
    idx = df.index
    out: list[tuple[datetime, float]] = []
    for i in range(left, len(highs) - right):
        window = highs[i - left : i + right + 1]
        # massimo al centro (e primo massimo della finestra) => pivot alto
        if highs[i] == window.max() and window.argmax() == left:
            out.append((idx[i].to_pydatetime(), float(highs[i])))
    return out


def swing_lows(df: pd.DataFrame, left: int = 5, right: int = 5) -> list[tuple[datetime, float]]:
    lows = df["low"].astype(float).to_numpy()
    idx = df.index
    out: list[tuple[datetime, float]] = []
    for i in range(left, len(lows) - right):
        window = lows[i - left : i + right + 1]
        if lows[i] == window.min() and window.argmin() == left:
            out.append((idx[i].to_pydatetime(), float(lows[i])))
    return out


def support_resistance(
    df: pd.DataFrame,
    current_price: float,
    *,
    lookback: int = 5,
    max_levels: int = 3,
) -> tuple[list[float], list[float]]:
    """Restituisce (supporti, resistenze) più vicini al prezzo corrente.

    - supporti: swing low STRETTAMENTE sotto il prezzo, dal più vicino;
    - resistenze: swing high STRETTAMENTE sopra il prezzo, dal più vicino.
    """
    lows = [p for _, p in swing_lows(df, lookback, lookback)]
    highs = [p for _, p in swing_highs(df, lookback, lookback)]

    supports = sorted({p for p in lows if p < current_price}, reverse=True)[:max_levels]
    resistances = sorted({p for p in highs if p > current_price})[:max_levels]
    return supports, resistances
