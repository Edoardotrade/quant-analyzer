"""Test dell'endpoint /analysis/entry."""

from __future__ import annotations

from fastapi.testclient import TestClient
from helpers import FailingProvider, FakeProvider, build_linear_series

from quantanalyzer import DISCLAIMER
from quantanalyzer.api.app import create_app
from quantanalyzer.data.base import DataUnavailableError
from quantanalyzer.data.cache import FileCache
from quantanalyzer.data.service import MarketDataService


def _client(provider, tmp_path):
    svc = MarketDataService(providers=[provider], cache=FileCache(tmp_path, ttl_minutes=60))
    return TestClient(create_app(service=svc))


def test_entry_ok(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260, symbol="XAUUSD")), tmp_path)
    resp = client.get(
        "/analysis/entry",
        params={"symbol": "XAUUSD", "asset_class": "forex", "capital": 10000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["playbook"]["side"] in ("long", "short", "none")
    assert len(body["playbook"]["gates"]) == 6
    assert "ready" in body["playbook"]
    assert body["disclaimer"] == DISCLAIMER


def test_entry_requires_capital(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260)), tmp_path)
    resp = client.get("/analysis/entry", params={"symbol": "X", "asset_class": "forex"})
    assert resp.status_code == 422


def test_entry_insufficient_data_422(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=12)), tmp_path)
    resp = client.get(
        "/analysis/entry",
        params={"symbol": "X", "asset_class": "forex", "capital": 10000},
    )
    assert resp.status_code == 422


def test_entry_unavailable_404(tmp_path):
    client = _client(FailingProvider(error=DataUnavailableError("no")), tmp_path)
    resp = client.get(
        "/analysis/entry",
        params={"symbol": "NOPE", "asset_class": "forex", "capital": 5000},
    )
    assert resp.status_code == 404
