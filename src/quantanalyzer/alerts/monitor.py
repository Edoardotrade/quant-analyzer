"""Sorveglianza della watchlist e invio degli avvisi.

Flusso: per ogni mercato in watchlist calcola il segnale operativo; quando un
mercato passa a ENTRA (e prima non lo era) invia un avviso Telegram con prezzo,
SL e TP. Lo stato evita di ri-notificare lo stesso setup ad ogni giro.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..analysis.signal import build_operating_signal
from ..data.service import MarketDataService
from ..models import AssetClass, Interval, OperatingSignal, RiskParams, SignalAction
from ..watchlist import (
    DEFAULT_INTERVAL,
    DEFAULT_LOOKBACK,
    WatchItem,
    effective_params,
)
from .telegram import send_telegram_message

DISCLAIMER_SHORT = "Analisi tecnica, non consulenza. Decisione e rischio tuoi."

_TF_LABEL = {
    Interval.M15: "15 min",
    Interval.H1: "1 ora",
    Interval.H4: "4 ore",
    Interval.D1: "giornaliero",
    Interval.W1: "settimanale",
    Interval.MO1: "mensile",
}


def _tf(interval: Interval | None) -> str:
    return _TF_LABEL.get(interval, "n/d") if interval else "n/d"


def _state_key(sig: OperatingSignal) -> str:
    """Chiave di stato per-segnale: simbolo + timeframe (oro-daily ≠ oro-4h)."""
    return f"{sig.symbol}@{sig.interval.value if sig.interval else '?'}"


def _apply_staleness(
    sig: OperatingSignal, now: datetime, *, max_age_days: float = 5.0
) -> OperatingSignal:
    """Sicurezza: non far entrare su dati palesemente stantii (feed rotto).

    Se il segnale è ENTRA a mercato aperto ma l'ultima barra è più vecchia di
    ``max_age_days`` (soglia larga, cattura solo feed davvero fermi senza falsi
    positivi nei weekend), lo declassa ad ASPETTA. Meglio saltare un trade che
    entrare a un prezzo vecchio.
    """
    if (
        sig.action == SignalAction.ENTER
        and sig.market_open
        and sig.as_of is not None
        and (now - sig.as_of) > timedelta(days=max_age_days)
    ):
        return sig.model_copy(
            update={
                "action": SignalAction.WAIT,
                "ready": False,
                "headline": f"⏳ ASPETTA {sig.symbol}: dati non aggiornati",
                "reason": (
                    f"Ultima barra del {sig.as_of:%Y-%m-%d %H:%M} troppo vecchia "
                    "(feed fermo?): niente ingresso su prezzi stantii."
                ),
            }
        )
    return sig


def check_watchlist(
    items: Sequence[tuple[str, AssetClass]],
    params: RiskParams,
    *,
    interval: Interval = DEFAULT_INTERVAL,
    lookback: int = DEFAULT_LOOKBACK,
    service: MarketDataService | None = None,
    now: datetime | None = None,
) -> list[OperatingSignal]:
    """Calcola il segnale operativo per ogni mercato della watchlist."""
    svc = service or MarketDataService()
    now = now or datetime.now(timezone.utc)
    signals: list[OperatingSignal] = []
    for item in items:
        # accetta sia WatchItem (con timeframe/override) sia semplici (simbolo, classe)
        if isinstance(item, WatchItem):
            symbol, asset_class = item.symbol, item.asset_class
            it_interval, it_lookback = item.interval, item.lookback
            it_params = effective_params(item, params)
        else:
            symbol, asset_class = item
            it_interval, it_lookback, it_params = interval, lookback, params
        try:
            series = svc.get_prices(symbol, asset_class, it_interval, lookback=it_lookback)
            signals.append(_apply_staleness(build_operating_signal(series, it_params), now))
        except Exception as exc:  # noqa: BLE001 — un asset rotto non ferma gli altri
            signals.append(
                OperatingSignal(
                    symbol=symbol,
                    asset_class=asset_class,
                    interval=it_interval,
                    action=SignalAction.NONE,
                    side="none",  # type: ignore[arg-type]
                    ready=False,
                    headline=f"⚠️ {symbol} ({_tf(it_interval)}): dati non disponibili",
                    reason=str(exc),
                )
            )
    return signals


def format_alert(sig: OperatingSignal) -> str:
    """Testo dell'avviso Telegram per un segnale di ingresso."""
    verbo = "COMPRA" if sig.side.value == "long" else "VENDI"
    chiuso = ""
    if not sig.market_open:
        chiuso = f"🔒 {sig.market_note} — verifica all'apertura (possibile gap)\n"
    return (
        f"🟢 <b>SEGNALE — {sig.symbol}</b> <i>({_tf(sig.interval)})</i>\n"
        f"Operazione: <b>{verbo}</b>\n"
        f"Ingresso: ~{sig.entry}\n"
        f"🛑 Stop Loss: {sig.stop_loss}\n"
        f"🎯 Take Profit: {sig.take_profit}\n"
        f"Quantità: {sig.size_units}\n"
        f"Rischio/Rendimento: {sig.rr}\n"
        f"{chiuso}"
        f"—\n<i>{DISCLAIMER_SHORT}</i>"
    )


def build_digest(signals: Sequence[OperatingSignal]) -> str:
    """Riepilogo giornaliero di tutti i mercati della watchlist."""
    enters = [s for s in signals if s.action == SignalAction.ENTER]
    lines = ["📊 <b>Riepilogo giornaliero — Quant Analyzer</b>", ""]
    if enters:
        lines.append("🟢 <b>Pronti all'ingresso:</b>")
        for s in enters:
            verbo = "COMPRA" if s.side.value == "long" else "VENDI"
            chiuso = " 🔒" if not s.market_open else ""
            lines.append(
                f"• {s.symbol} [{_tf(s.interval)}]: {verbo} ~{s.entry} "
                f"(SL {s.stop_loss} / TP {s.take_profit}){chiuso}"
            )
    else:
        lines.append("Nessun mercato pronto all'ingresso adesso.")
    lines.append("")
    lines.append("<b>Stato mercati:</b>")
    icons = {"entra": "🟢", "aspetta": "⏳", "nessuno": "⚠️"}
    for s in signals:
        icon = icons.get(s.action.value, "•")
        chiuso = " 🔒" if not s.market_open else ""
        lines.append(f"{icon} {s.symbol} [{_tf(s.interval)}]: {s.action.value}{chiuso}")
    lines.append("")
    lines.append(f"<i>{DISCLAIMER_SHORT}</i>")
    return "\n".join(lines)


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
        key = _state_key(sig)
        is_enter = sig.action == SignalAction.ENTER
        was_enter = state.get(key, False)
        if is_enter and not was_enter:
            try:
                sent_ok = bool(notifier(format_alert(sig)))
            except Exception as exc:  # noqa: BLE001 — un invio fallito non ferma gli altri
                print(f"[monitor] invio avviso fallito per {sig.symbol}: {exc}", flush=True)
                sent_ok = False
            if sent_ok:
                fired.append(key)
                state[key] = True
            # se l'invio non riesce, NON marchiamo lo stato: si ritenta al giro dopo
        else:
            state[key] = is_enter
    return fired


def _load_state(path: Path) -> dict[str, bool]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, state: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def _load_ledger(path: Path) -> list[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_ledger(path: Path, ledger: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger), encoding="utf-8")


def _update_paper_ledger(
    signals: Sequence[OperatingSignal], svc: MarketDataService, ledger_path: Path
) -> None:
    """Aggiorna il registro paper-trading (registra nuovi ENTRA, chiude TP/SL colpiti).

    Difensivo: qualunque errore qui NON deve fermare gli avvisi.
    """
    from .paper import record_new_signals, update_open_trades

    ledger = _load_ledger(ledger_path)
    record_new_signals(signals, ledger, datetime.now(timezone.utc))

    def series_for(sym: str, interval: str, ac: str):
        try:
            return svc.get_prices(sym, AssetClass(ac), Interval(interval), lookback=400)
        except Exception:  # noqa: BLE001 — dato mancante: il trade resta aperto
            return None

    update_open_trades(ledger, series_for)
    _save_ledger(ledger_path, ledger)


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
    Aggiorna anche il registro paper-trading (track record forward).
    """
    state_path = Path(state_path)
    svc = service or MarketDataService()
    state = _load_state(state_path)
    signals = check_watchlist(items, params, service=svc)
    fired = evaluate_alerts(signals, state, notifier)
    _save_state(state_path, state)
    try:
        _update_paper_ledger(signals, svc, state_path.parent / "paper_ledger.json")
    except Exception as exc:  # noqa: BLE001 — paper-trading non deve mai rompere gli avvisi
        print(f"[paper] aggiornamento saltato (non fatale): {exc}", flush=True)
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
