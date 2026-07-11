"""Watchlist e parametri di default, condivisi da sorvegliante e scheduler."""

from __future__ import annotations

from .models import AssetClass, RiskParams

DEFAULT_WATCHLIST: list[tuple[str, AssetClass]] = [
    ("XAUUSD", AssetClass.FOREX),
    ("EURUSD", AssetClass.FOREX),
    ("GBPUSD", AssetClass.FOREX),
    ("USDJPY", AssetClass.FOREX),
    ("AUDUSD", AssetClass.FOREX),
    ("SPY", AssetClass.ETF),  # ETF S&P 500 (≈ ^GSPC, affidabile via Twelve Data)
    ("QQQ", AssetClass.ETF),  # ETF Nasdaq-100 (≈ ^IXIC)
    ("BTC/USDT", AssetClass.CRYPTO),
    ("ETH/USDT", AssetClass.CRYPTO),
]

DEFAULT_PARAMS = RiskParams(capital=10_000, risk_pct=1.0, min_rr=2.0, atr_stop_mult=1.5)
