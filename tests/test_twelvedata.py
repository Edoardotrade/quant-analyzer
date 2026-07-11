"""Test del provider Twelve Data (con client HTTP finto, nessuna rete)."""

from __future__ import annotations

import pytest

from quantanalyzer.data.base import DataUnavailableError
from quantanalyzer.data.twelvedata_provider import TwelveDataProvider
from quantanalyzer.models import AssetClass, Interval

SAMPLE = {
    "status": "ok",
    "values": [
        {"datetime": "2024-01-01", "open": "1.10", "high": "1.12",
         "low": "1.09", "close": "1.11", "volume": "0"},
        {"datetime": "2024-01-02", "open": "1.11", "high": "1.13",
         "low": "1.10", "close": "1.12", "volume": "0"},
    ],
}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payload):
        self._payload = payload
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params):
        self.calls.append((url, params))
        return _Resp(self._payload)


def test_fetch_parses_values():
    provider = TwelveDataProvider(api_key="K", client=_Client(SAMPLE))
    s = provider.fetch("EURUSD", asset_class=AssetClass.FOREX, interval=Interval.D1, lookback=100)
    assert len(s) == 2
    assert s.source == "twelvedata"
    assert s.last_close == 1.12


def test_forex_and_gold_symbol_mapping():
    c = _Client(SAMPLE)
    TwelveDataProvider(api_key="K", client=c).fetch(
        "EURUSD", asset_class=AssetClass.FOREX, interval=Interval.D1, lookback=50
    )
    assert c.calls[0][1]["symbol"] == "EUR/USD"

    c2 = _Client(SAMPLE)
    TwelveDataProvider(api_key="K", client=c2).fetch(
        "XAUUSD", asset_class=AssetClass.FOREX, interval=Interval.D1, lookback=50
    )
    assert c2.calls[0][1]["symbol"] == "XAU/USD"


def test_index_symbol_mapping():
    c = _Client(SAMPLE)
    TwelveDataProvider(api_key="K", client=c).fetch(
        "^GSPC", asset_class=AssetClass.INDEX, interval=Interval.D1, lookback=50
    )
    assert c.calls[0][1]["symbol"] == "SPX"


def test_error_status_raises():
    provider = TwelveDataProvider(api_key="K", client=_Client({"status": "error", "message": "x"}))
    with pytest.raises(DataUnavailableError):
        provider.fetch("X", asset_class=AssetClass.EQUITY, interval=Interval.D1, lookback=50)


def test_supports_only_with_key():
    assert TwelveDataProvider(api_key="").supports(AssetClass.FOREX) is False
    assert TwelveDataProvider(api_key="K").supports(AssetClass.FOREX) is True
    assert TwelveDataProvider(api_key="K").supports(AssetClass.CRYPTO) is False
