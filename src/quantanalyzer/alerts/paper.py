"""Registro di paper-trading automatico (track record forward, non backtest).

Ogni segnale ENTRA viene registrato come trade su carta; ad ogni giro il sistema
controlla sui prezzi reali se ha colpito prima lo stop o il target e lo chiude,
accumulando statistiche VERE nel tempo. È il ponte onesto tra "backtest promettente"
e "soldi veri": prima raccogli decine di trade su carta, poi decidi.

Il ledger è una lista di dict serializzabile in JSON (persistita come lo stato del
monitor). Nessuna dipendenza dal broker: si limita a TP/SL sui dati di mercato.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from ..models import OperatingSignal, PriceSeries, SignalAction

# series_for(symbol, interval_value, asset_class_value) -> PriceSeries | None
SeriesLookup = Callable[[str, str, str], PriceSeries | None]


def _key(symbol: str, interval: str) -> str:
    return f"{symbol}@{interval}"


def record_new_signals(
    signals: Sequence[OperatingSignal], ledger: list[dict], now: datetime
) -> list[dict]:
    """Registra come trade su carta i nuovi ENTRA (uno per simbolo@timeframe aperto)."""
    open_keys = {_key(t["symbol"], t["interval"]) for t in ledger if t["status"] == "open"}
    for s in signals:
        if s.action != SignalAction.ENTER:
            continue
        if s.entry is None or s.stop_loss is None or s.take_profit is None:
            continue
        interval = s.interval.value if s.interval else "?"
        k = _key(s.symbol, interval)
        if k in open_keys:
            continue  # trade già aperto su questo simbolo@timeframe
        ledger.append(
            {
                "symbol": s.symbol,
                "asset_class": s.asset_class.value,
                "interval": interval,
                "side": s.side.value,
                "entry": s.entry,
                "stop": s.stop_loss,
                "target": s.take_profit,
                "entry_date": now.isoformat(),
                "status": "open",
                "exit": None,
                "exit_date": None,
                "r_multiple": None,
            }
        )
        open_keys.add(k)
    return ledger


def update_open_trades(ledger: list[dict], series_for: SeriesLookup) -> list[dict]:
    """Chiude i trade su carta che hanno colpito stop o target (stop prudenziale)."""
    for t in ledger:
        if t["status"] != "open":
            continue
        series = series_for(t["symbol"], t["interval"], t.get("asset_class", "forex"))
        if series is None or not series.bars:
            continue
        entry_dt = datetime.fromisoformat(t["entry_date"])
        long = t["side"] == "long"
        entry, stop, target = t["entry"], t["stop"], t["target"]
        risk = abs(entry - stop)
        for bar in series.bars:
            if bar.timestamp <= entry_dt:
                continue
            outcome = price = None
            if long:
                if bar.low <= stop:  # stop prima (prudenziale)
                    outcome, price = "loss", stop
                elif bar.high >= target:
                    outcome, price = "win", target
            else:
                if bar.high >= stop:
                    outcome, price = "loss", stop
                elif bar.low <= target:
                    outcome, price = "win", target
            if outcome:
                move = (price - entry) if long else (entry - price)
                t["status"] = outcome
                t["exit"] = round(price, 6)
                t["exit_date"] = bar.timestamp.isoformat()
                t["r_multiple"] = round(move / risk, 3) if risk else 0.0
                break
    return ledger


def ledger_stats(ledger: Sequence[dict]) -> dict:
    """Statistiche del track record su carta."""
    closed = [t for t in ledger if t["status"] in ("win", "loss")]
    open_n = sum(1 for t in ledger if t["status"] == "open")
    if not closed:
        return {"n": 0, "open": open_n, "win_rate": None, "expectancy_r": None, "total_r": 0.0}
    wins = sum(1 for t in closed if t["status"] == "win")
    rs = [t["r_multiple"] or 0.0 for t in closed]
    return {
        "n": len(closed),
        "open": open_n,
        "win_rate": round(wins / len(closed) * 100),
        "expectancy_r": round(sum(rs) / len(rs), 3),
        "total_r": round(sum(rs), 2),
    }


def format_paper_report(ledger: Sequence[dict]) -> str:
    """Riga(righe) di riepilogo del paper-trading per Telegram."""
    st = ledger_stats(ledger)
    if st["n"] == 0:
        return (
            f"📝 <b>Paper trading</b>: 0 trade chiusi, {st['open']} aperti. "
            "Serve tempo (settimane e decine di trade) per un dato affidabile."
        )
    return (
        "📝 <b>Paper trading — track record REALE (forward)</b>\n"
        f"Trade chiusi: {st['n']} · aperti: {st['open']}\n"
        f"Win rate: {st['win_rate']}% · aspettativa: {st['expectancy_r']}R a trade\n"
        f"Risultato cumulato: {st['total_r']:+}R\n"
        "<i>Numeri veri, non backtest. Servono decine di trade prima di fidarsi.</i>"
    )
