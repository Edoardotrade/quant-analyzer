"""Test dei modelli di dominio (validazione + conversioni)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest
from pydantic import ValidationError

from quantanalyzer.models import AssetClass, Interval, OHLCVBar, PriceSeries

UTC = timezone.utc


def test_ohlcv_naive_timestamp_becomes_utc():
    bar = OHLCVBar(timestamp=datetime(2024, 1, 1, 12, 0), open=1, high=2, low=0.5, close=1.5)
    assert bar.timestamp.tzinfo is not None
    assert bar.timestamp == datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


def test_ohlcv_high_below_low_rejected():
    with pytest.raises(ValidationError):
        OHLCVBar(timestamp=datetime(2024, 1, 1), open=1, high=0.5, low=1.0, close=0.8)


def test_ohlcv_close_outside_range_rejected():
    with pytest.raises(ValidationError):
        OHLCVBar(timestamp=datetime(2024, 1, 1), open=1, high=2, low=0.5, close=5.0)


def test_ohlcv_negative_volume_rejected():
    with pytest.raises(ValidationError):
        OHLCVBar(timestamp=datetime(2024, 1, 1), open=1, high=2, low=0.5, close=1.5, volume=-1)


def test_priceseries_last_close_and_len():
    bars = [
        OHLCVBar(timestamp=datetime(2024, 1, d), open=1, high=10, low=0.5, close=1.0 + d)
        for d in (1, 2, 3)
    ]
    ps = PriceSeries(
        symbol="X",
        asset_class=AssetClass.EQUITY,
        interval=Interval.D1,
        source="fake",
        fetched_at=datetime(2024, 1, 4, tzinfo=UTC),
        bars=bars,
    )
    assert len(ps) == 3
    assert ps.last_close == 4.0
    assert ps.start == datetime(2024, 1, 1, tzinfo=UTC)
    assert ps.end == datetime(2024, 1, 3, tzinfo=UTC)


def test_from_frame_to_frame_roundtrip():
    idx = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"], utc=True)
    df = pd.DataFrame(
        {
            "Open": [10.0, 11.0, 12.0],
            "High": [10.5, 11.5, 12.5],
            "Low": [9.5, 10.5, 11.5],
            "Close": [10.2, 11.2, 12.2],
            "Volume": [100, 200, 300],
        },
        index=idx,
    )
    ps = PriceSeries.from_frame(
        df,
        symbol="X",
        asset_class=AssetClass.ETF,
        interval=Interval.D1,
        source="fake",
        fetched_at=datetime(2024, 1, 4, tzinfo=UTC),
    )
    assert len(ps) == 3
    assert ps.last_close == 12.2

    out = ps.to_frame()
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert out["close"].tolist() == [10.2, 11.2, 12.2]
    assert out.index.tolist() == list(idx)


def test_from_frame_clamps_open_close_outside_range():
    # open sotto il low e close sopra il high (capita col forex di Yahoo):
    # il range va ampliato, senza sollevare errori né scartare la barra.
    idx = pd.to_datetime(["2024-01-01"], utc=True)
    df = pd.DataFrame(
        {"open": [1.10], "high": [1.14], "low": [1.135], "close": [1.15]}, index=idx
    )
    ps = PriceSeries.from_frame(
        df,
        symbol="EURUSD",
        asset_class=AssetClass.FOREX,
        interval=Interval.D1,
        source="fake",
        fetched_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    bar = ps.bars[0]
    assert bar.low <= bar.open <= bar.high
    assert bar.low <= bar.close <= bar.high
    assert bar.low == 1.10
    assert bar.high == 1.15


def test_from_frame_missing_columns_raises():
    df = pd.DataFrame(
        {"open": [1], "high": [2], "close": [1.5]},
        index=pd.to_datetime(["2024-01-01"]),
    )
    with pytest.raises(ValueError):
        PriceSeries.from_frame(
            df,
            symbol="X",
            asset_class=AssetClass.EQUITY,
            interval=Interval.D1,
            source="fake",
            fetched_at=datetime(2024, 1, 2, tzinfo=UTC),
        )
