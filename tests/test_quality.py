"""Test della valutazione di qualità dei dati."""

from __future__ import annotations

from datetime import datetime, timezone

from helpers import build_series

from quantanalyzer.data.quality import assess
from quantanalyzer.models import AssetClass, Interval, OHLCVBar, PriceSeries

UTC = timezone.utc


def test_sufficient_series():
    q = assess(build_series(n=60), min_bars=30)
    assert q.sufficient is True
    assert q.n_bars == 60
    assert q.warnings == []


def test_short_series_flagged():
    q = assess(build_series(n=5), min_bars=30)
    assert q.sufficient is False
    assert q.n_bars == 5
    assert any("barre" in w.lower() for w in q.warnings)


def test_empty_series_flagged():
    ps = PriceSeries(
        symbol="X",
        asset_class=AssetClass.EQUITY,
        interval=Interval.D1,
        source="fake",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
        bars=[],
    )
    q = assess(ps)
    assert q.sufficient is False
    assert q.n_bars == 0


def test_duplicate_timestamps_flagged():
    bar = OHLCVBar(timestamp=datetime(2024, 1, 1, tzinfo=UTC), open=1, high=2, low=0.5, close=1.5)
    ps = PriceSeries(
        symbol="X",
        asset_class=AssetClass.EQUITY,
        interval=Interval.D1,
        source="fake",
        fetched_at=datetime(2024, 1, 2, tzinfo=UTC),
        bars=[bar, bar],  # timestamp duplicato
    )
    q = assess(ps, min_bars=1)
    assert q.has_duplicates is True
    assert q.sufficient is False
