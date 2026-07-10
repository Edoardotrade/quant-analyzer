"""Sorveglianza della watchlist e invio degli avvisi.

Flusso: per ogni mercato in watchlist calcola il segnale operativo; quando un
mercato passa a ENTRA (e prima non lo era) invia un avviso Telegram con prezzo,
SL e TP. Lo stato evita di ri-notificare lo stesso setup ad ogni giro.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from ..analysis.signal import build_operating_signal
from ..data.service import MarketDataService
from ..models import AssetClass, Interval, OperatingSignal, RiskParams, SignalAction
from .telegram import send_telegram_message

DISCLAIMER_SHORT = "Analisi tecnica, non consulenza. Decisione e rischio tuoi."


def check_watchlist(
    items: Sequence[tuple[str, AssetClass]],
    params: RiskParams,
    *,
    interval: Interval = Interval.D1,
    lookback: int = 300,
    service: MarketDataService | None = None,
) -> list[OperatingSignal]:
    """Calcola il segnale operativo per ogni mercato della watchlist."""
    svc = service or MarketDataService()
    signals: list[OperatingSignal] = []
    for symbol, asset_class in items:
        try:
            series = svc.get_prices(symbol, asset_class, interval, lookback=lookback)
            signals.append(build_operating_signal(series, params))
        except Exception as exc:  # noqa: BLE001 — un asset rotto non ferma gli altri
            signals.append(
                OperatingSignal(
                    symbol=symbol,
                    asset_class=asset_class,
                    action=SignalAction.NONE,
                    side="none",  # type: ignore[arg-type]
                    ready=False,
                    headline=f"⚠️ {symbol}: dati non disponibili",
                    reason=str(exc),
                )
            )
    return signals


def format_alert(sig: OperatingSignal) -> str:
    """Testo dell'avviso Telegram per un segnale di ingresso."""
    verbo = "COMPRA" if sig.side.value == "long" else "VENDI"
    return (
        f"🟢 <b>SEGNALE — {sig.symbol}</b>\n"
        f"Operazione: <b>{verbo}</b>\n"
        f"Ingresso: ~{sig.entry}\n"
        f"🛑 Stop Loss: {sig.stop_loss}\n"
        f"🎯 Take Profit: {sig.take_profit}\n"
        f"Quantità: {sig.size_units}\n"
        f"Rischio/Rendimento: {sig.rr}\n"
        f"—\n<i>{DISCLAIMER_SHORT}</i>"
    )


def evaluate_alerts(
    signals: Sequence[OperatingSignal],
    state: dict[str, bool],
    notifier: Callable[[str], bool] = send_telegram_message,
) -> list[str]:
    """Invia un avviso per ogni mercato appena passato a ENTRA. Aggiorna ``state``.

    Restituisce i simboli per cui è stato inviato un avviso in questo giro.
    """
    fired: list[str] = []
    for sig in signals:
        is_enter = sig.action == SignalAction.ENTER
        was_enter = state.get(sig.symbol, False)
        if is_enter and not was_enter:
            notifier(format_alert(sig))
            fired.append(sig.symbol)
        state[sig.symbol] = is_enter
    return fired


def _load_state(path: Path) -> dict[str, bool]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, state: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def run_once(
    items: Sequence[tuple[str, AssetClass]],
    params: RiskParams,
    *,
    state_path: str | Path = ".cache/monitor_state.json",
    notifier: Callable[[str], bool] = send_telegram_message,
    service: MarketDataService | None = None,
) -> tuple[list[OperatingSignal], list[str]]:
    """Un solo giro: controlla la watchlist, invia i nuovi ENTRA, salva lo stato.

    Pensato anche per scheduler esterni (GitHub Actions/cron): lo stato su file
    (persistito dallo scheduler) evita di ri-notificare lo stesso setup.
    """
    state_path = Path(state_path)
    state = _load_state(state_path)
    signals = check_watchlist(items, params, service=service)
    fired = evaluate_alerts(signals, state, notifier)
    _save_state(state_path, state)
    return signals, fired


def run_forever(
    items: Sequence[tuple[str, AssetClass]],
    params: RiskParams,
    *,
    interval_minutes: int = 15,
    state_path: str | Path = ".cache/monitor_state.json",
    notifier: Callable[[str], bool] = send_telegram_message,
) -> None:  # pragma: no cover — loop di lungo periodo
    """Controlla la watchlist a intervalli regolari e invia gli avvisi."""
    print(f"[monitor] avviato: {len(items)} mercati, ogni {interval_minutes} min.", flush=True)
    while True:
        signals, fired = run_once(items, params, state_path=state_path, notifier=notifier)
        for sig in signals:
            print(f"[monitor] {sig.symbol}: {sig.action.value}", flush=True)
        if fired:
            print(f"[monitor] AVVISI inviati: {fired}", flush=True)
        time.sleep(interval_minutes * 60)
