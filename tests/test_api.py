"""Test dell'API FastAPI (con servizio iniettato, nessuna rete)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from helpers import FailingProvider, FakeProvider, build_series

from quantanalyzer import DISCLAIMER
from quantanalyzer.api.app import create_app
from quantanalyzer.data.base import DataUnavailableError
from quantanalyzer.data.cache import FileCache
from quantanalyzer.data.service import MarketDataService


def _client(provider, tmp_path):
    svc = MarketDataService(providers=[provider], cache=FileCache(tmp_path, ttl_minutes=60))
    return TestClient(create_app(service=svc))


def test_health(tmp_path):
    client = _client(FakeProvider(build_series(n=10)), tmp_path)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_price_ok(tmp_path):
    client = _client(FakeProvider(build_series(n=40, symbol="AAPL")), tmp_path)
    resp = client.get(
        "/price",
        params={"symbol": "AAPL", "asset_class": "equity", "interval": "1d", "lookback": 40},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["series"]["symbol"] == "AAPL"
    assert len(body["series"]["bars"]) == 40
    assert body["data_quality"]["sufficient"] is True
    assert body["disclaimer"] == DISCLAIMER


def test_price_insufficient_data_still_returns_with_warning(tmp_path):
    client = _client(FakeProvider(build_series(n=5)), tmp_path)
    resp = client.get(
        "/price",
        params={"symbol": "X", "asset_class": "equity", "lookback": 10},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_quality"]["sufficient"] is False
    assert body["data_quality"]["warnings"]


def test_price_unavailable_returns_404(tmp_path):
    provider = FailingProvider(error=DataUnavailableError("simbolo inesistente"))
    client = _client(provider, tmp_path)
    resp = client.get(
        "/price",
        params={"symbol": "NOPE", "asset_class": "equity"},
    )
    assert resp.status_code == 404


def test_price_validation_error_on_bad_asset_class(tmp_path):
    client = _client(FakeProvider(build_series(n=10)), tmp_path)
    resp = client.get(
        "/price",
        params={"symbol": "X", "asset_class": "banana"},
    )
    assert resp.status_code == 422
