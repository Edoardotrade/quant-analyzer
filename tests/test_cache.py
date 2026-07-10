"""Test della cache su file."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from helpers import build_series

from quantanalyzer.data.cache import FileCache, make_key
from quantanalyzer.models import AssetClass, Interval

UTC = timezone.utc


def test_store_and_load_roundtrip(tmp_path):
    cache = FileCache(tmp_path, ttl_minutes=60)
    series = build_series(n=10)
    key = make_key("fake", "TEST", AssetClass.EQUITY, Interval.D1)

    cache.store(key, series)
    loaded = cache.load(key)

    assert loaded is not None
    assert loaded.symbol == series.symbol
    assert len(loaded) == 10
    assert loaded.last_close == series.last_close


def test_load_missing_returns_none(tmp_path):
    cache = FileCache(tmp_path, ttl_minutes=60)
    assert cache.load("non-esiste") is None


def test_is_fresh_respects_ttl(tmp_path):
    now = datetime(2024, 3, 1, 12, 0, tzinfo=UTC)
    cache = FileCache(tmp_path, ttl_minutes=60, now=lambda: now)

    fresh = build_series(fetched_at=now - timedelta(minutes=10))
    stale = build_series(fetched_at=now - timedelta(minutes=120))

    assert cache.is_fresh(fresh) is True
    assert cache.is_fresh(stale) is False


def test_corrupted_file_returns_none(tmp_path):
    cache = FileCache(tmp_path, ttl_minutes=60)
    key = make_key("fake", "TEST", AssetClass.EQUITY, Interval.D1)
    cache.store(key, build_series(n=5))
    # Corrompiamo il file.
    path = cache._path(key)
    path.write_text("{ non-json", encoding="utf-8")
    assert cache.load(key) is None
