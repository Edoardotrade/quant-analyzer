"""Watchlist e parametri di default, condivisi da sorvegliante e scheduler."""

from __future__ import annotations

from .models import AssetClass, Interval, RiskParams

# NB: EURUSD e GBPUSD rimossi dopo il backtest del sistema reale (2026-07-29):
# perdenti su entrambi i timeframe (PF < 0.5). Restano i mercati con edge/rischio
# migliore sul giornaliero (oro, USDJPY, azionari, crypto).
DEFAULT_WATCHLIST: list[tuple[str, AssetClass]] = [
    ("XAUUSD", AssetClass.FOREX),
    ("USDJPY", AssetClass.FOREX),
    ("AUDUSD", AssetClass.FOREX),
    ("SPY", AssetClass.ETF),  # ETF S&P 500 (≈ ^GSPC, affidabile via Twelve Data)
    ("QQQ", AssetClass.ETF),  # ETF Nasdaq-100 (≈ ^IXIC)
    ("BTC/USDT", AssetClass.CRYPTO),
    ("ETH/USDT", AssetClass.CRYPTO),
]

DEFAULT_PARAMS = RiskParams(capital=10_000, risk_pct=1.0, min_rr=2.0, atr_stop_mult=1.5)

# Timeframe operativo condiviso da monitor, digest e dashboard.
# GIORNALIERO: il backtest del sistema reale (2026-07-29) mostra che il daily
# batte nettamente l'1h (5/9 mercati positivi vs quasi tutti negativi su 1h) con
# drawdown bassi. Filtro di grado superiore = settimanale. Meno segnali ma migliori.
DEFAULT_INTERVAL = Interval.D1
DEFAULT_LOOKBACK = 300
