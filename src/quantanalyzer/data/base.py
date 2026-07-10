"""Astrazione dei provider di dati di mercato.

Un provider è qualunque oggetto che sappia recuperare una PriceSeries per una
data classe di asset. L'astrazione permette di aggiungere/sostituire fonti
(yfinance, ccxt, Alpha Vantage, ...) senza toccare il resto del sistema.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import AssetClass, Interval, PriceSeries


class DataError(Exception):
    """Errore generico del layer dati."""


class DataUnavailableError(DataError):
    """La fonte ha risposto ma non ci sono dati per il simbolo richiesto."""


class DataFetchError(DataError):
    """Errore durante il recupero dati (rete, parsing, fonte non raggiungibile)."""


@runtime_checkable
class MarketDataProvider(Protocol):
    """Contratto minimo che ogni provider deve rispettare."""

    name: str

    def supports(self, asset_class: AssetClass) -> bool:
        """True se il provider può servire questa classe di asset."""
        ...

    def fetch(
        self,
        symbol: str,
        *,
        asset_class: AssetClass,
        interval: Interval,
        lookback: int,
    ) -> PriceSeries:
        """Recupera al più ``lookback`` barre più recenti per ``symbol``."""
        ...
