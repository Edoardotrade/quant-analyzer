"""Test dell'endpoint /analysis/risk-plan."""

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


def test_risk_plan_ok(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260, symbol="AAPL")), tmp_path)
    resp = client.get(
        "/analysis/risk-plan",
        params={"symbol": "AAPL", "asset_class": "equity", "capital": 10000, "risk_pct": 1.0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["side"] == "long"
    assert body["plan"]["viable"] is True
    assert body["plan"]["risk_amount"] == 100.0
    assert body["disclaimer"] == DISCLAIMER
    assert body["plan"]["rationale"]


def test_risk_plan_requires_capital(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260)), tmp_path)
    resp = client.get(
        "/analysis/risk-plan",
        params={"symbol": "X", "asset_class": "equity"},  # manca capital
    )
    assert resp.status_code == 422


def test_risk_plan_unavailable_returns_404(tmp_path):
    provider = FailingProvider(error=DataUnavailableError("simbolo inesistente"))
    client = _client(provider, tmp_path)
    resp = client.get(
        "/analysis/risk-plan",
        params={"symbol": "NOPE", "asset_class": "equity", "capital": 5000},
    )
    assert resp.status_code == 404
