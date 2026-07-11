"""Test dell'endpoint /analysis/technical (servizio iniettato, nessuna rete)."""

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


def test_technical_ok(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260, symbol="AAPL")), tmp_path)
    resp = client.get(
        "/analysis/technical",
        params={"symbol": "AAPL", "asset_class": "equity", "interval": "1d", "lookback": 300},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["analysis"]["computed"] is True
    assert body["analysis"]["symbol"] == "AAPL"
    assert len(body["analysis"]["signals"]) == 7
    assert body["disclaimer"] == DISCLAIMER
    # ogni segnale espone la sua spiegazione
    assert all(s["rationale"] for s in body["analysis"]["signals"])


def test_technical_insufficient_returns_200_not_computed(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=12)), tmp_path)
    resp = client.get(
        "/analysis/technical",
        params={"symbol": "X", "asset_class": "equity", "lookback": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["analysis"]["computed"] is False
    assert body["analysis"]["signals"] == []
    assert body["analysis"]["notes"]


def test_technical_unavailable_returns_404(tmp_path):
    provider = FailingProvider(error=DataUnavailableError("simbolo inesistente"))
    client = _client(provider, tmp_path)
    resp = client.get(
        "/analysis/technical",
        params={"symbol": "NOPE", "asset_class": "equity"},
    )
    assert resp.status_code == 404
