"""Utility condivise dai test: builder di serie sintetiche e provider finti.

Nessun test tocca la rete: i provider reali (yfinance/ccxt) sono sostituiti
da questi doppi di test.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from quantanalyzer.data.base import DataFetchError, DataUnavailableError
from quantanalyzer.models import (
    AssetClass,
    DataQuality,
    Direction,
    Interval,
    OHLCVBar,
    PriceSeries,
    Signal,
    SupportResistance,
    TechnicalAnalysis,
)

UTC = timezone.utc
ALL_CLASSES = set(AssetClass)


def build_series(
    n: int = 60,
    *,
    symbol: str = "TEST",
    asset_class: AssetClass = AssetClass.EQUITY,
    interval: Interval = Interval.D1,
    source: str = "fake",
    start: datetime | None = None,
    fetched_at: datetime | None = None,
) -> PriceSeries:
    """Costruisce una PriceSeries sintetica e valida di ``n`` barre."""
    start = start or datetime(2024, 1, 1, tzinfo=UTC)
    fetched_at = fetched_at or datetime(2024, 3, 1, tzinfo=UTC)
    bars: list[OHLCVBar] = []
    price = 100.0
    for i in range(n):
        ts = start + timedelta(days=i)
        open_ = price
        close = price * (1 + 0.001 * ((i % 5) - 2))  # oscillazione deterministica
        high = max(open_, close) * 1.01
        low = min(open_, close) * 0.99
        bars.append(
            OHLCVBar(
                timestamp=ts,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=1000.0 + i,
            )
        )
        price = close
    return PriceSeries(
        symbol=symbol,
        asset_class=asset_class,
        interval=interval,
        source=source,
        fetched_at=fetched_at,
        bars=bars,
    )


def build_linear_series(
    n: int = 60,
    *,
    start: float = 100.0,
    step: float = 1.0,
    volume: float = 1000.0,
    symbol: str = "LIN",
    asset_class: AssetClass = AssetClass.EQUITY,
    interval: Interval = Interval.D1,
    source: str = "fake",
    start_dt: datetime | None = None,
    fetched_at: datetime | None = None,
) -> PriceSeries:
    """Serie a trend lineare (close strettamente monotòno).

    ``step`` > 0 => uptrend, < 0 => downtrend. Utile per proprietà note
    (es. RSI di serie crescente = 100).
    """
    start_dt = start_dt or datetime(2024, 1, 1, tzinfo=UTC)
    fetched_at = fetched_at or datetime(2024, 12, 1, tzinfo=UTC)
    bars: list[OHLCVBar] = []
    prev_close = start
    buffer = abs(step) * 0.5 + 0.01
    for i in range(n):
        ts = start_dt + timedelta(days=i)
        close = start + (i + 1) * step
        open_ = prev_close
        high = max(open_, close) + buffer
        low = min(open_, close) - buffer
        if low <= 0:
            low = min(open_, close) * 0.999
        bars.append(
            OHLCVBar(timestamp=ts, open=open_, high=high, low=low, close=close, volume=volume)
        )
        prev_close = close
    return PriceSeries(
        symbol=symbol,
        asset_class=asset_class,
        interval=interval,
        source=source,
        fetched_at=fetched_at,
        bars=bars,
    )


def build_wave_series(
    n: int = 400,
    *,
    base: float = 100.0,
    amp: float = 20.0,
    period: int = 40,
    drift: float = 0.0,
    volume: float = 1000.0,
    symbol: str = "WAVE",
    asset_class: AssetClass = AssetClass.EQUITY,
    interval: Interval = Interval.D1,
    source: str = "fake",
    start_dt: datetime | None = None,
    fetched_at: datetime | None = None,
) -> PriceSeries:
    """Serie oscillante (sinusoide + drift): genera incroci di medie -> trade nei backtest."""
    start_dt = start_dt or datetime(2023, 1, 1, tzinfo=UTC)
    fetched_at = fetched_at or datetime(2024, 12, 1, tzinfo=UTC)
    bars: list[OHLCVBar] = []
    prev_close = base
    for i in range(n):
        ts = start_dt + timedelta(days=i)
        close = base + drift * i + amp * math.sin(2 * math.pi * i / period)
        open_ = prev_close
        high = max(open_, close) + 0.5
        low = min(open_, close) - 0.5
        if low <= 0:
            low = min(open_, close) * 0.999
        bars.append(
            OHLCVBar(timestamp=ts, open=open_, high=high, low=low, close=close, volume=volume)
        )
        prev_close = close
    return PriceSeries(
        symbol=symbol,
        asset_class=asset_class,
        interval=interval,
        source=source,
        fetched_at=fetched_at,
        bars=bars,
    )


def build_ta(
    direction: Direction,
    *,
    price: float,
    supports: list[float] | None = None,
    resistances: list[float] | None = None,
    symbol: str = "X",
    n_bars: int = 60,
) -> TechnicalAnalysis:
    """TechnicalAnalysis controllata per testare il risk planner in isolamento."""
    return TechnicalAnalysis(
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        interval=Interval.D1,
        as_of=None,
        current_price=price,
        computed=True,
        trend_summary="(test)",
        signals=[
            Signal(
                name="Trend (SMA 20/50/200)",
                value=None,
                state="test",
                direction=direction,
                rationale="test",
            )
        ],
        support_resistance=SupportResistance(
            current_price=price,
            supports=supports or [],
            resistances=resistances or [],
        ),
        data_quality=DataQuality(
            n_bars=n_bars,
            min_bars=30,
            is_ordered=True,
            has_duplicates=False,
            sufficient=True,
        ),
    )


class FakeProvider:
    """Provider deterministico: restituisce sempre la serie fornita."""

    name = "fake"

    def __init__(
        self,
        series: PriceSeries,
        *,
        supported: set[AssetClass] | None = None,
    ) -> None:
        self._series = series
        self._supported = supported if supported is not None else ALL_CLASSES
        self.calls = 0

    def supports(self, asset_class: AssetClass) -> bool:
        return asset_class in self._supported

    def fetch(self, symbol, *, asset_class, interval, lookback) -> PriceSeries:
        self.calls += 1
        return self._series


class FailingProvider:
    """Provider che fallisce sempre (per testare il fail-soft)."""

    name = "fake"  # stessa 'name' del FakeProvider -> stessa chiave di cache

    def __init__(
        self,
        *,
        error: Exception | None = None,
        supported: set[AssetClass] | None = None,
    ) -> None:
        self._error = error or DataFetchError("errore simulato")
        self._supported = supported if supported is not None else ALL_CLASSES
        self.calls = 0

    def supports(self, asset_class: AssetClass) -> bool:
        return asset_class in self._supported

    def fetch(self, symbol, *, asset_class, interval, lookback) -> PriceSeries:
        self.calls += 1
        raise self._error


__all__ = [
    "UTC",
    "ALL_CLASSES",
    "build_series",
    "build_linear_series",
    "build_wave_series",
    "build_ta",
    "FakeProvider",
    "FailingProvider",
    "DataFetchError",
    "DataUnavailableError",
]
