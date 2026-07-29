"""Test della watchlist: override per-simbolo e simboli distinti."""

from __future__ import annotations

from quantanalyzer.models import AssetClass, Interval, RiskParams
from quantanalyzer.watchlist import WatchItem, effective_params, unique_symbols


def test_effective_params_applies_overrides_preserving_capital():
    base = RiskParams(capital=10_000, risk_pct=1.0, min_rr=2.0, atr_stop_mult=1.5)
    item = WatchItem(
        "XAUUSD", AssetClass.FOREX, Interval.H4, 720,
        min_rr=2.0, atr_stop_mult=1.5, risk_pct=0.5,
    )
    ep = effective_params(item, base)
    assert ep.risk_pct == 0.5  # override applicato (metà rischio sul 4h)
    assert ep.capital == 10_000  # capitale dell'utente preservato


def test_effective_params_no_override_returns_base():
    base = RiskParams(capital=10_000, risk_pct=1.0)
    plain = WatchItem("USDJPY", AssetClass.FOREX)
    assert effective_params(plain, base).risk_pct == 1.0


def test_unique_symbols_dedupes_gold_and_excludes_removed():
    syms = [s for s, _ in unique_symbols()]
    assert syms.count("XAUUSD") == 1  # oro su 2 timeframe ma 1 solo simbolo per la dashboard
    assert "EURUSD" not in syms and "GBPUSD" not in syms
