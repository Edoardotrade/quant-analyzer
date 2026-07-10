"""Test della mappatura simboli del provider yfinance."""

from __future__ import annotations

from quantanalyzer.data.yfinance_provider import _to_yf_symbol
from quantanalyzer.models import AssetClass


def test_forex_gets_x_suffix():
    assert _to_yf_symbol("EURUSD", AssetClass.FOREX) == "EURUSD=X"


def test_forex_alias_gold_and_silver():
    assert _to_yf_symbol("XAUUSD", AssetClass.FOREX) == "GC=F"
    assert _to_yf_symbol("xauusd", AssetClass.FOREX) == "GC=F"
    assert _to_yf_symbol("XAGUSD", AssetClass.FOREX) == "SI=F"


def test_non_forex_symbols_unchanged():
    assert _to_yf_symbol("AAPL", AssetClass.EQUITY) == "AAPL"
    assert _to_yf_symbol("^GSPC", AssetClass.INDEX) == "^GSPC"
