"""Provider dati crypto basato su ccxt.

ccxt espone in modo unificato le API pubbliche di molti exchange. Per i dati di
mercato OHLCV pubblici NON serve alcuna API key. L'oggetto exchange è iniettabile
per rendere i test indipendenti dalla rete.

Convenzione simboli ccxt: coppia "BASE/QUOTE", es. "BTC/USDT".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from ..models import AssetClass, Interval, OHLCVBar, PriceSeries
from .base import DataFetchError, DataUnavailableError

# Mappa: nostro Interval -> timeframe ccxt
_CCXT_TIMEFRAME = {
    Interval.M15: "15m",
    Interval.H1: "1h",
    Interval.D1: "1d",
    Interval.W1: "1w",
    Interval.MO1: "1M",
}


class CCXTProvider:
    """Provider per crypto via ccxt."""

    name = "ccxt"
    _SUPPORTED = {AssetClass.CRYPTO}

    def __init__(
        self,
        exchange: Any | None = None,
        *,
        exchange_id: str = "kraken",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        # ``exchange`` già istanziato (per i test) oppure creato lazy da exchange_id.
        self._exchange = exchange
        self._exchange_id = exchange_id
        self._now = now or (lambda: datetime.now(timezone.utc))

    def supports(self, asset_class: AssetClass) -> bool:
        return asset_class in self._SUPPORTED

    def _get_exchange(self) -> Any:
        if self._exchange is not None:
            return self._exchange
        import ccxt  # import lazy

        try:
            exchange_cls = getattr(ccxt, self._exchange_id)
        except AttributeError as exc:
            raise DataFetchError(f"Exchange ccxt sconosciuto: '{self._exchange_id}'") from exc
        # timeout breve: se un exchange è bloccato, fallisce in fretta e si passa al successivo
        self._exchange = exchange_cls({"enableRateLimit": True, "timeout": 10000})
        return self._exchange

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

        timeframe = _CCXT_TIMEFRAME[interval]
        exchange = self._get_exchange()
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=lookback)
        except Exception as exc:
            raise DataFetchError(f"fetch_ohlcv ccxt fallito per {symbol}: {exc}") from exc

        if not raw:
            raise DataUnavailableError(
                f"Nessun dato ccxt per '{symbol}' (timeframe={timeframe})."
            )

        bars: list[OHLCVBar] = []
        for row in raw:
            # ccxt: [timestamp_ms, open, high, low, close, volume]
            ts = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc)
            o, h, low_, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
            bars.append(
                OHLCVBar(
                    timestamp=ts,
                    open=o,
                    high=max(o, h, low_, c),  # il range deve contenere open/close
                    low=min(o, h, low_, c),
                    close=c,
                    volume=float(row[5]) if row[5] is not None else 0.0,
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
