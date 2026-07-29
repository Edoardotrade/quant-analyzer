"""Provider dati basato su yfinance (azioni, ETF, indici, forex).

NOTA DI RISCHIO: yfinance interroga in modo non ufficiale le API di Yahoo
Finance. Può cambiare formato, rate-limitare o restituire dati mancanti senza
preavviso. Per questo il fetch è isolato, normalizzato e validato, e il download
è iniettabile (``downloader``) così i test non toccano la rete.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from ..models import AssetClass, Interval, PriceSeries
from .base import DataFetchError, DataUnavailableError

# Mappa: nostro Interval -> intervallo yfinance
_YF_INTERVAL = {
    Interval.M15: "15m",
    Interval.H1: "60m",
    Interval.H4: "4h",  # yfinance non ha il 4h nativo: fallback che fallisce -> altra fonte
    Interval.D1: "1d",
    Interval.W1: "1wk",
    Interval.MO1: "1mo",
}


def _yf_period(interval: Interval, lookback: int) -> str:
    """Sceglie un ``period`` yfinance abbastanza ampio da coprire ``lookback`` barre.

    yfinance impone limiti sugli intraday (es. 15m max ~60 giorni, 60m max ~730).
    Scarichiamo una finestra generosa e poi tagliamo alle ultime ``lookback`` barre.
    """
    if interval == Interval.M15:
        return "60d"
    if interval in (Interval.H1, Interval.H4):
        return "730d"
    if interval == Interval.D1:
        years_needed = math.ceil(lookback / 252) + 1  # ~252 giorni di borsa/anno
        for years, label in ((1, "1y"), (2, "2y"), (5, "5y"), (10, "10y")):
            if years_needed <= years:
                return label
        return "max"
    # settimanale / mensile: lo storico è compatto, prendiamo tutto
    return "max"


# Metalli/commodity: lo spot (es. XAUUSD) non è sul feed gratuito di Yahoo,
# quindi si usa il future come proxy (traccia lo spot da vicino).
_FOREX_ALIASES = {
    "XAUUSD": "GC=F",  # oro (COMEX gold futures)
    "XAGUSD": "SI=F",  # argento
    "WTIUSD": "CL=F",  # petrolio WTI
}


def _to_yf_symbol(symbol: str, asset_class: AssetClass) -> str:
    """Adatta il simbolo alla convenzione di Yahoo per il forex/commodity."""
    if asset_class == AssetClass.FOREX:
        upper = symbol.upper()
        if upper in _FOREX_ALIASES:
            return _FOREX_ALIASES[upper]
        if "=" not in symbol:
            # es. "EURUSD" -> "EURUSD=X"
            return f"{upper}=X"
    return symbol


class YFinanceProvider:
    """Provider per equity/ETF/indici/forex via yfinance."""

    name = "yfinance"
    _SUPPORTED = {
        AssetClass.EQUITY,
        AssetClass.ETF,
        AssetClass.INDEX,
        AssetClass.FOREX,
    }

    def __init__(
        self,
        downloader: Callable[..., Any] | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        # ``downloader`` iniettabile (default: yfinance.download, importato lazy).
        self._downloader = downloader
        self._now = now or (lambda: datetime.now(timezone.utc))

    def supports(self, asset_class: AssetClass) -> bool:
        return asset_class in self._SUPPORTED

    def _download(self, **kwargs: Any) -> Any:
        if self._downloader is not None:
            return self._downloader(**kwargs)
        import yfinance as yf  # import lazy: non necessario per i test

        return yf.download(**kwargs)

    @staticmethod
    def _normalize(df: Any) -> Any:
        """Appiattisce colonne MultiIndex e uniforma i nomi (lowercase)."""
        import pandas as pd

        if isinstance(df.columns, pd.MultiIndex):
            df = df.copy()
            # yfinance recente restituisce (Campo, Ticker): teniamo il campo.
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)
        keep = ["open", "high", "low", "close", "volume"]
        available = [c for c in keep if c in df.columns]
        missing = {"open", "high", "low", "close"} - set(available)
        if missing:
            raise DataFetchError(
                f"Colonne attese mancanti dai dati yfinance: {sorted(missing)}"
            )
        return df[available].dropna(how="any")

    def fetch(
        self,
        symbol: str,
        *,
        asset_class: AssetClass,
        interval: Interval,
        lookback: int,
    ) -> PriceSeries:
        if not self.supports(asset_class):
            raise DataFetchError(f"{self.name} non supporta la classe {asset_class}")

        yf_symbol = _to_yf_symbol(symbol, asset_class)
        period = _yf_period(interval, lookback)
        try:
            raw = self._download(
                tickers=yf_symbol,
                period=period,
                interval=_YF_INTERVAL[interval],
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception as exc:  # rete, parsing yfinance, ecc.
            raise DataFetchError(f"Download yfinance fallito per {yf_symbol}: {exc}") from exc

        if raw is None or getattr(raw, "empty", True):
            raise DataUnavailableError(
                f"Nessun dato da yfinance per '{yf_symbol}' "
                f"(period={period}, interval={_YF_INTERVAL[interval]})."
            )

        df = self._normalize(raw).tail(lookback)
        if df.empty:
            raise DataUnavailableError(f"Serie vuota dopo normalizzazione per '{yf_symbol}'.")

        return PriceSeries.from_frame(
            df,
            symbol=symbol,
            asset_class=asset_class,
            interval=interval,
            source=self.name,
            fetched_at=self._now(),
        )
