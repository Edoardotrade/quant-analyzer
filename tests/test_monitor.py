"""Test della logica di sorveglianza/avvisi (dedup, formattazione)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quantanalyzer.alerts import monitor as mon
from quantanalyzer.alerts.monitor import (
    _apply_staleness,
    build_digest,
    evaluate_alerts,
    format_alert,
    run_once,
)
from quantanalyzer.models import (
    AssetClass,
    Interval,
    OperatingSignal,
    PositionSide,
    RiskParams,
    SignalAction,
)


def _enter(symbol="XAUUSD", interval=Interval.D1):
    return OperatingSignal(
        symbol=symbol,
        asset_class=AssetClass.FOREX,
        interval=interval,
        action=SignalAction.ENTER,
        side=PositionSide.LONG,
        ready=True,
        entry=4100.0,
        stop_loss=4050.0,
        take_profit=4200.0,
        rr=2.0,
        size_units=0.02,
        headline="🟢 COMPRA",
        reason="ok",
    )


def _wait(symbol="XAUUSD", interval=Interval.D1):
    return OperatingSignal(
        symbol=symbol,
        asset_class=AssetClass.FOREX,
        interval=interval,
        action=SignalAction.WAIT,
        side=PositionSide.LONG,
        ready=False,
        headline="⏳ ASPETTA",
        reason="rr basso",
    )


def test_build_digest_lists_markets():
    msg = build_digest([_enter("XAUUSD"), _wait("EURUSD")])
    assert "Riepilogo" in msg
    assert "XAUUSD" in msg
    assert "EURUSD" in msg
    assert "COMPRA" in msg  # per il mercato in ENTRA


def test_format_alert_contains_levels():
    msg = format_alert(_enter())
    assert "COMPRA" in msg
    assert "Stop Loss" in msg and "4050.0" in msg
    assert "Take Profit" in msg and "4200.0" in msg


def test_alert_fires_once_then_dedupes():
    state: dict[str, bool] = {}
    sent: list[str] = []
    notifier = lambda text: sent.append(text) or True  # noqa: E731

    # primo giro: ENTRA -> invia
    fired1 = evaluate_alerts([_enter()], state, notifier)
    assert fired1 == ["XAUUSD@1d"]
    assert len(sent) == 1

    # secondo giro: ancora ENTRA -> NON reinvia
    fired2 = evaluate_alerts([_enter()], state, notifier)
    assert fired2 == []
    assert len(sent) == 1


def test_alert_refires_after_returning_to_wait():
    state: dict[str, bool] = {}
    sent: list[str] = []
    notifier = lambda text: sent.append(text) or True  # noqa: E731

    evaluate_alerts([_enter()], state, notifier)  # invia (1)
    evaluate_alerts([_wait()], state, notifier)  # torna in attesa
    fired = evaluate_alerts([_enter()], state, notifier)  # nuovo ENTRA -> invia (2)
    assert fired == ["XAUUSD@1d"]
    assert len(sent) == 2


def test_failed_send_is_not_marked_and_retries():
    state: dict[str, bool] = {}

    def failing(_text):
        raise RuntimeError("boom")

    # invio fallito -> nessun fired, stato NON marcato come inviato
    fired = evaluate_alerts([_enter()], state, failing)
    assert fired == []
    assert state.get("XAUUSD@1d", False) is False

    # giro successivo con invio ok -> parte davvero
    sent: list[str] = []
    fired2 = evaluate_alerts([_enter()], state, lambda t: sent.append(t) or True)
    assert fired2 == ["XAUUSD@1d"]
    assert len(sent) == 1


def test_same_symbol_two_timeframes_fire_independently():
    # L'oro su daily e su 4h deve generare DUE avvisi distinti (chiavi separate).
    state: dict[str, bool] = {}
    sent: list[str] = []
    notifier = lambda text: sent.append(text) or True  # noqa: E731
    signals = [_enter("XAUUSD", Interval.D1), _enter("XAUUSD", Interval.H4)]
    fired = evaluate_alerts(signals, state, notifier)
    assert set(fired) == {"XAUUSD@1d", "XAUUSD@4h"}
    assert len(sent) == 2
    # secondo giro: nessun doppione
    assert evaluate_alerts(signals, state, notifier) == []
    assert len(sent) == 2


def test_staleness_downgrades_enter_on_old_data():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    # dato fresco: ENTRA resta ENTRA
    fresh = _enter().model_copy(update={"as_of": now - timedelta(hours=2)})
    assert _apply_staleness(fresh, now).action == SignalAction.ENTER
    # dato vecchio (feed fermo): ENTRA declassato ad ASPETTA, non pronto
    stale = _enter().model_copy(update={"as_of": now - timedelta(days=10)})
    out = _apply_staleness(stale, now)
    assert out.action == SignalAction.WAIT
    assert out.ready is False


def test_run_once_persists_state_on_file(tmp_path, monkeypatch):
    sent: list[str] = []
    notifier = lambda text: sent.append(text) or True  # noqa: E731
    monkeypatch.setattr(mon, "check_watchlist", lambda items, params, **kw: [_enter()])
    state_file = tmp_path / "state.json"
    params = RiskParams(capital=10_000)

    _, fired1 = run_once([], params, state_path=state_file, notifier=notifier)
    assert fired1 == ["XAUUSD@1d"]
    assert state_file.exists()

    # secondo giro (stato riletto dal file): niente doppione
    _, fired2 = run_once([], params, state_path=state_file, notifier=notifier)
    assert fired2 == []
    assert len(sent) == 1
