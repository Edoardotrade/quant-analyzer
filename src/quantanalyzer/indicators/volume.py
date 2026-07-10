"""Indicatori di volume: media, volume relativo e OBV."""

from __future__ import annotations

import numpy as np
import pandas as pd


def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Media mobile semplice del volume."""
    return volume.rolling(window=period, min_periods=period).mean()


def relative_volume(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume relativo = volume / media mobile del volume.

    >1 = volume sopra la media (partecipazione elevata), <1 = sotto la media.
    """
    avg = volume_sma(volume, period)
    return volume / avg


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume: cumula il volume col segno della variazione di prezzo.

    OBV in salita conferma la pressione in acquisto; in discesa quella in vendita.
    """
    direction = np.sign(close.astype(float).diff().fillna(0.0))
    return (direction * volume.astype(float)).cumsum()
