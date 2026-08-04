"""Test del registro paper-trading (registra, chiude TP/SL, statistiche)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quantanalyzer.alerts.paper import (
    format_paper_report,
    ledger_stats,
    record_new_signals,
    update_open_trades,
)
from quantanalyzer.models import (
    AssetClass,
    Interval,
    OHLCVBar,
    OperatingSignal,
    PositionSide,
    PriceSeries,
    SignalAction,
)

T0 = datetime(2026, 7, 30, tzinfo=UTC)


def _enter(symbol="XAUUSD", interval=Interval.D1, entry=100.0, stop=95.0, target=110.0):
    return OperatingSignal(
        symbol=symbol,
        asset_class=AssetClass.FOREX,
        interval=interval,
        action=SignalAction.ENTER,
        side=PositionSide.LONG,
        ready=True,
        entry=entry,
        stop_loss=stop,
        take_profit=target,
        rr=2.0,
        headline="x",
        reason="y",
    )


def _series_with_bar(high, low):
    bar = OHLCVBar(
        timestamp=T0 + timedelta(days=1), open=100.0, high=high, low=low, close=100.0, volume=1.0
    )
    return PriceSeries(
        symbol="XAUUSD",
        asset_class=AssetClass.FOREX,
        interval=Interval.D1,
        source="fake",
        fetched_at=T0 + timedelta(days=2),
        bars=[bar],
    )


def test_record_new_signals_dedupes_and_ignores_wait():
    ledger: list[dict] = []
    record_new_signals([_enter()], ledger, T0)
    assert len(ledger) == 1 and ledger[0]["status"] == "open"
    # stesso simbolo@timeframe già aperto -> nessun doppione
    record_new_signals([_enter()], ledger, T0)
    assert len(ledger) == 1
    # un WAIT non registra nulla
    wait = _enter().model_copy(update={"action": SignalAction.WAIT})
    record_new_signals([wait], ledger, T0)
    assert len(ledger) == 1


def test_update_closes_win_and_loss():
    # WIN: una barra tocca il target (110)
    ledger = []
    record_new_signals([_enter()], ledger, T0)
    update_open_trades(ledger, lambda s, i, a: _series_with_bar(high=111.0, low=99.0))
    assert ledger[0]["status"] == "win"
    assert ledger[0]["r_multiple"] == 2.0  # (110-100)/5

    # LOSS: una barra tocca lo stop (95)
    ledger2 = []
    record_new_signals([_enter()], ledger2, T0)
    update_open_trades(ledger2, lambda s, i, a: _series_with_bar(high=101.0, low=94.0))
    assert ledger2[0]["status"] == "loss"
    assert ledger2[0]["r_multiple"] == -1.0


def test_ledger_stats_and_report():
    ledger = [
        {"status": "win", "r_multiple": 2.0},
        {"status": "loss", "r_multiple": -1.0},
        {"status": "open", "r_multiple": None},
    ]
    st = ledger_stats(ledger)
    assert st["n"] == 2 and st["open"] == 1
    assert st["win_rate"] == 50
    assert st["total_r"] == 1.0
    assert "track record" in format_paper_report(ledger).lower()
    assert "0 trade chiusi" in format_paper_report([])
