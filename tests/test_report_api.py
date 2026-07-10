"""Test degli endpoint /report, /report.md, /report.html, /report.pdf."""

from __future__ import annotations

from fastapi.testclient import TestClient
from helpers import FailingProvider, FakeProvider, build_linear_series

from quantanalyzer.api.app import create_app
from quantanalyzer.data.base import DataUnavailableError
from quantanalyzer.data.cache import FileCache
from quantanalyzer.data.service import MarketDataService


def _client(provider, tmp_path):
    svc = MarketDataService(providers=[provider], cache=FileCache(tmp_path, ttl_minutes=60))
    return TestClient(create_app(service=svc))


def test_report_json(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260, symbol="AAPL")), tmp_path)
    resp = client.get(
        "/report",
        params={"symbol": "AAPL", "asset_class": "equity", "capital": 10000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["report"]["scenarios"]) == 3
    assert body["report"]["risk_plan"] is not None
    assert body["report"]["disclaimer"]
    assert body["markdown"].startswith("# Report")


def test_report_without_capital_json(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260)), tmp_path)
    resp = client.get("/report", params={"symbol": "X", "asset_class": "equity"})
    assert resp.status_code == 200
    assert resp.json()["report"]["risk_plan"] is None


def test_report_markdown(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260)), tmp_path)
    resp = client.get("/report.md", params={"symbol": "X", "asset_class": "equity"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "# Report di analisi" in resp.text


def test_report_html(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260)), tmp_path)
    resp = client.get("/report.html", params={"symbol": "X", "asset_class": "equity"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<html" in resp.text.lower()


def test_report_pdf(tmp_path):
    client = _client(FakeProvider(build_linear_series(n=260)), tmp_path)
    resp = client.get("/report.pdf", params={"symbol": "X", "asset_class": "equity"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_report_unavailable_404(tmp_path):
    client = _client(FailingProvider(error=DataUnavailableError("no")), tmp_path)
    resp = client.get(
        "/report", params={"symbol": "NOPE", "asset_class": "equity", "capital": 5000}
    )
    assert resp.status_code == 404
