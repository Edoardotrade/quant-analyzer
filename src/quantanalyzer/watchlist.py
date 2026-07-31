"""Watchlist e parametri di default, condivisi da sorvegliante e scheduler.

Ogni voce è un ``WatchItem``: simbolo + classe + timeframe operativo + eventuali
override dei parametri di rischio (ottimizzati per quel mercato/timeframe).
Un simbolo può comparire su PIÙ timeframe (es. oro daily + oro 4h) per generare
più trade indipendenti sullo stesso strumento.
"""

from __future__ import annotations

from typing import NamedTuple

from .models import AssetClass, Interval, RiskParams

DEFAULT_PARAMS = RiskParams(capital=10_000, risk_pct=1.0, min_rr=2.0, atr_stop_mult=1.5)

# Timeframe/lookback operativi standard (vedi backtest: il daily batte l'1h).
DEFAULT_INTERVAL = Interval.D1
DEFAULT_LOOKBACK = 300
# Storico per il timeframe 4h (usato solo dai mercati che lo abilitano, es. oro).
H4_LOOKBACK = 720


class WatchItem(NamedTuple):
    """Voce di watchlist: mercato + timeframe + override di rischio opzionali."""

    symbol: str
    asset_class: AssetClass
    interval: Interval = DEFAULT_INTERVAL
    lookback: int = DEFAULT_LOOKBACK
    min_rr: float | None = None  # override del gate R:R minimo (se None usa il globale)
    atr_stop_mult: float | None = None  # override ampiezza stop (se None usa il globale)
    risk_pct: float | None = None  # override rischio% (es. metà rischio su timeframe meno validati)


# Watchlist operativa. ORO su DUE timeframe (più trade, ciascuno con edge validato
# out-of-sample): daily robusto (10 anni) + 4h più frequente (validazione più corta).
# EUR/GBP rimossi (perdenti su entrambi i timeframe). Parametri oro ottimizzati con
# split in-sample/out-of-sample il 2026-07-29.
DEFAULT_WATCHLIST: list[WatchItem] = [
    WatchItem(
        "XAUUSD", AssetClass.FOREX, Interval.D1, DEFAULT_LOOKBACK,
        min_rr=1.5, atr_stop_mult=1.5,
    ),
    WatchItem(
        "XAUUSD", AssetClass.FOREX, Interval.H4, H4_LOOKBACK,
        min_rr=2.0, atr_stop_mult=1.5, risk_pct=0.5,  # metà rischio: 4h meno validato
    ),
    WatchItem("USDJPY", AssetClass.FOREX),
    WatchItem("AUDUSD", AssetClass.FOREX),
    WatchItem("SPY", AssetClass.ETF),
    # SPY/QQQ anche su 4h: edge positivo out-of-sample (2026-07-30), rischio dimezzato
    # (edge sottile). USDJPY/AUDUSD/BTC/ETH su 4h NON abilitati (perdono OOS o dati insuff.).
    WatchItem(
        "SPY", AssetClass.ETF, Interval.H4, H4_LOOKBACK,
        min_rr=2.0, atr_stop_mult=1.5, risk_pct=0.5,
    ),
    WatchItem("QQQ", AssetClass.ETF),
    WatchItem(
        "QQQ", AssetClass.ETF, Interval.H4, H4_LOOKBACK,
        min_rr=2.0, atr_stop_mult=1.5, risk_pct=0.5,
    ),
    WatchItem("BTC/USDT", AssetClass.CRYPTO),
    WatchItem("ETH/USDT", AssetClass.CRYPTO),
]


def effective_params(item: WatchItem, base: RiskParams) -> RiskParams:
    """Applica gli override per-simbolo mantenendo capitale/rischio% dell'utente."""
    updates = {}
    if item.min_rr is not None:
        updates["min_rr"] = item.min_rr
    if item.atr_stop_mult is not None:
        updates["atr_stop_mult"] = item.atr_stop_mult
    if item.risk_pct is not None:
        updates["risk_pct"] = item.risk_pct
    return base.model_copy(update=updates) if updates else base


def unique_symbols() -> list[tuple[str, AssetClass]]:
    """Simboli distinti (per la dashboard, che usa un timeframe unico selezionabile)."""
    seen: dict[str, AssetClass] = {}
    for it in DEFAULT_WATCHLIST:
        seen.setdefault(it.symbol, it.asset_class)
    return list(seen.items())
