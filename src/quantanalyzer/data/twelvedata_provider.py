"""Provider dati basato su Twelve Data (forex, indici, oro, azioni, ETF).

Twelve Data richiede una API key (gratuita) ma NON viene bloccata dagli IP dei
server cloud come yfinance: è la fonte affidabile per il deploy online.
Le crypto restano su ccxt. La chiave vive solo in env (TWELVEDATA_API_KEY).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..models import AssetClass, Interval, OHLCVBar, PriceSeries
from .base import DataFetchError, DataUnavailableError

_TD_INTERVAL = {
    Interval.M15: "15min",
    Interval.H1: "1h",
    Interval.D1: "1day",
    Interval.W1: "1week",
    Interval.MO1: "1month",
}

# Simboli indici principali nella nomenclatura Twelve Data.
_INDEX_MAP = {
    "^GSPC": "SPX",
    "^SPX": "SPX",
    "^IXIC": "IXIC",
    "^DJI": "DJI",
    "^NDX": "NDX",
    "^RUT": "RUT",
}


def _td_symbol(symbol: str, asset_class: AssetClass) -> str:
    """Converte il simbolo nella nomenclatura Twelve Data."""
    if asset_class == AssetClass.FOREX:
        s = symbol.upper().replace("=X", "")
        if "/" not in s and len(s) == 6:
            return f"{s[:3]}/{s[3:]}"  # EURUSD -> EUR/USD, XAUUSD -> XAU/USD
        return s
    if asset_class == AssetClass.INDEX:
        return _INDEX_MAP.get(symbol.upper(), symbol.lstrip("^"))
    return symbol  # equity / etf: ticker diretto


class TwelveDataProvider:
    """Provider per forex/indici/oro/azioni/ETF via Twelve Data."""

    name = "twelvedata"
    _SUPPORTED = {AssetClass.EQUITY, AssetClass.ETF, AssetClass.INDEX, AssetClass.FOREX}

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._api_key = api_key  # se None si legge da settings al fetch
        self._client = client
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _key(self) -> str | None:
        return self._api_key if self._api_key is not None else get_settings().twelvedata_api_key

    def supports(self, asset_class: AssetClass) -> bool:
        # attivo solo se c'è una chiave: senza chiave si passa a yfinance
        return asset_class in self._SUPPORTED and bool(self._key())

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        url = "https://api.twelvedata.com/time_series"
        if self._client is not None:
            return self._client.get(url, params=params).json()
        import httpx

        with httpx.Client(timeout=20.0) as http:
            return http.get(url, params=params).json()

    def fetch(
        self,
        symbol: str,
        *,
        asset_class: AssetClass,
        interval: Interval,
        lookback: int,
    ) -> PriceSeries:
        key = self._key()
        if not key:
            raise DataFetchError("Twelve Data: API key mancante (TWELVEDATA_API_KEY).")

        params = {
            "symbol": _td_symbol(symbol, asset_class),
            "interval": _TD_INTERVAL[interval],
            "outputsize": min(max(lookback, 30), 5000),
            "order": "ASC",
            "format": "JSON",
            "apikey": key,
        }
        try:
            data = self._request(params)
        except Exception as exc:
            raise DataFetchError(f"Twelve Data non raggiungibile per {symbol}: {exc}") from exc

        if not isinstance(data, dict) or data.get("status") == "error":
            msg = data.get("message", "risposta non valida") if isinstance(data, dict) else "n/d"
            raise DataUnavailableError(f"Twelve Data per '{symbol}': {msg}")

        values = data.get("values")
        if not values:
            raise DataUnavailableError(f"Nessun dato Twelve Data per '{symbol}'.")

        bars: list[OHLCVBar] = []
        for row in values:
            ts = datetime.fromisoformat(row["datetime"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            o = float(row["open"])
            h = float(row["high"])
            low_ = float(row["low"])
            c = float(row["close"])
            vol = float(row["volume"]) if row.get("volume") not in (None, "") else 0.0
            bars.append(
                OHLCVBar(
                    timestamp=ts,
                    open=o,
                    high=max(o, h, low_, c),
                    low=min(o, h, low_, c),
                    close=c,
                    volume=vol,
                )
            )
        bars.sort(key=lambda b: b.timestamp)
        return PriceSeries(
            symbol=symbol,
            asset_class=asset_class,
            interval=interval,
            source=self.name,
            fetched_at=self._now(),
            bars=bars,
        )
