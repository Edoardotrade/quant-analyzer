"""Test del servizio orchestratore: selezione provider, cache, fail-soft."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from helpers import DataUnavailableError, FailingProvider, FakeProvider, build_series

from quantanalyzer.data.base import DataFetchError
from quantanalyzer.data.cache import FileCache, make_key
from quantanalyzer.data.service import MarketDataService
from quantanalyzer.models import AssetClass, Interval

UTC = timezone.utc


def _service(tmp_path, provider, *, now=None, ttl=60):
    cache = FileCache(tmp_path, ttl_minutes=ttl, now=now)
    return MarketDataService(providers=[provider], cache=cache)


def test_fetch_when_cache_empty(tmp_path):
    provider = FakeProvider(build_series(n=40))
    svc = _service(tmp_path, provider)

    series = svc.get_prices("TEST", AssetClass.EQUITY, Interval.D1, lookback=40)

    assert provider.calls == 1
    assert len(series) == 40
    # è stata scritta in cache
    key = make_key("mkt", "TEST", AssetClass.EQUITY, Interval.D1)
    assert svc.cache.load(key) is not None


def test_fresh_cache_avoids_provider(tmp_path):
    now = datetime(2024, 3, 1, 12, 0, tzinfo=UTC)
    provider = FakeProvider(build_series(n=40, fetched_at=now))
    svc = _service(tmp_path, provider, now=lambda: now, ttl=60)

    # Pre-popola la cache con dati freschi.
    key = make_key("mkt", "TEST", AssetClass.EQUITY, Interval.D1)
    svc.cache.store(key, build_series(n=40, fetched_at=now - timedelta(minutes=5)))

    series = svc.get_prices("TEST", AssetClass.EQUITY, Interval.D1)

    assert provider.calls == 0  # servita dalla cache
    assert len(series) == 40


def test_force_refresh_bypasses_cache(tmp_path):
    now = datetime(2024, 3, 1, 12, 0, tzinfo=UTC)
    provider = FakeProvider(build_series(n=40, fetched_at=now))
    svc = _service(tmp_path, provider, now=lambda: now, ttl=60)

    key = make_key("mkt", "TEST", AssetClass.EQUITY, Interval.D1)
    svc.cache.store(key, build_series(n=40, fetched_at=now - timedelta(minutes=5)))

    svc.get_prices("TEST", AssetClass.EQUITY, Interval.D1, force_refresh=True)
    assert provider.calls == 1


def test_stale_cache_used_as_fallback_on_error(tmp_path):
    now = datetime(2024, 3, 1, 12, 0, tzinfo=UTC)
    provider = FailingProvider(error=DataFetchError("rete giù"))
    svc = _service(tmp_path, provider, now=lambda: now, ttl=60)

    # Cache stantia (oltre il TTL).
    key = make_key("mkt", "TEST", AssetClass.EQUITY, Interval.D1)
    svc.cache.store(key, build_series(n=40, fetched_at=now - timedelta(hours=5)))

    series = svc.get_prices("TEST", AssetClass.EQUITY, Interval.D1)

    assert provider.calls == 1  # ha provato il fetch
    assert len(series) == 40  # ma è ripiegato sulla cache


def test_error_without_cache_propagates(tmp_path):
    provider = FailingProvider(error=DataFetchError("rete giù"))
    svc = _service(tmp_path, provider)
    with pytest.raises(DataFetchError):
        svc.get_prices("TEST", AssetClass.EQUITY, Interval.D1)


def test_falls_back_to_next_provider(tmp_path):
    # la prima fonte fallisce -> si usa la seconda (chiave cache indipendente dalla fonte)
    first = FailingProvider(error=DataFetchError("prima giù"))
    second = FakeProvider(build_series(n=10))
    svc = _service(tmp_path, first)
    svc.providers = [first, second]

    series = svc.get_prices("TEST", AssetClass.EQUITY, Interval.D1)
    assert len(series) == 10
    assert first.calls == 1
    assert second.calls == 1


def test_no_provider_for_class_raises(tmp_path):
    # Provider che supporta solo crypto, ma chiediamo equity.
    provider = FakeProvider(build_series(n=10), supported={AssetClass.CRYPTO})
    svc = _service(tmp_path, provider)
    with pytest.raises(DataUnavailableError):
        svc.get_prices("TEST", AssetClass.EQUITY, Interval.D1)
