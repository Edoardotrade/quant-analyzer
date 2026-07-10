"""Test dell'endpoint /backtest."""

from __future__ import annotations

from fastapi.testclient import TestClient
from helpers import FailingProvider, FakeProvider, build_wave_series

from quantanalyzer import DISCLAIMER
from quantanalyzer.api.app import create_app
from quantanalyzer.data.base import DataUnavailableError
from quantanalyzer.data.cache import FileCache
from quantanalyzer.data.service import MarketDataService


def _client(provider, tmp_path):
    svc = MarketDataService(providers=[provider], cache=FileCache(tmp_path, ttl_minutes=60))
    return TestClient(create_app(service=svc))


def test_backtest_ok(tmp_path):
    client = _client(FakeProvider(build_wave_series(n=500, symbol="AAPL")), tmp_path)
    resp = client.get(
        "/backtest",
        params={
            "symbol": "AAPL",
            "asset_class": "equity",
            "capital": 10000,
            "sma_fast": 10,
            "sma_slow": 30,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["computed"] is True
    assert body["result"]["n_trades"] >= 0
    assert body["disclaimer"] == DISCLAIMER


def test_backtest_requires_capital(tmp_path):
    client = _client(FakeProvider(build_wave_series(n=500)), tmp_path)
    resp = client.get("/backtest", params={"symbol": "X", "asset_class": "equity"})
    assert resp.status_code == 422


def test_backtest_bad_sma_returns_422(tmp_path):
    client = _client(FakeProvider(build_wave_series(n=500)), tmp_path)
    resp = client.get(
        "/backtest",
        params={"symbol": "X", "asset_class": "equity", "capital": 10000,
                "sma_fast": 50, "sma_slow": 20},
    )
    assert resp.status_code == 422


def test_backtest_unavailable_404(tmp_path):
    client = _client(FailingProvider(error=DataUnavailableError("no")), tmp_path)
    resp = client.get(
        "/backtest", params={"symbol": "NOPE", "asset_class": "equity", "capital": 5000}
    )
    assert resp.status_code == 404
