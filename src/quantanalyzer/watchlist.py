"""Watchlist e parametri di default, condivisi da sorvegliante e scheduler."""

from __future__ import annotations

from .models import AssetClass, Interval, RiskParams

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

# Timeframe operativo condiviso da monitor, digest e dashboard.
# Intraday 1h: molti più segnali e più veloci (reazione in ore, non giorni),
# mantenendo gli stessi standard di qualità. Il filtro di grado superiore
# diventa automaticamente il giornaliero. Lookback ampio per SMA lunghe + filtro.
DEFAULT_INTERVAL = Interval.H1
DEFAULT_LOOKBACK = 720
