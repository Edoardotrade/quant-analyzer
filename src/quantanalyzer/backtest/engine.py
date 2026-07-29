"""Backtest event-driven di una strategia baseline, SENZA lookahead.

Strategia testata (baseline trasparente, NON l'analisi multi-segnale completa):
  - regime/segnale: incrocio di due medie mobili (SMA fast/slow);
  - ingresso: alla CHIUSURA della barra in cui avviene l'incrocio;
  - stop: entry ∓ (atr_stop_mult · ATR);  target: R:R = rr_target;
  - uscita: stop/target intrabar (in caso di gap si esce all'apertura; se stop e
    target sono toccati nella stessa barra si assume PRIMA lo stop, in modo prudente),
    oppure inversione del trend all'incrocio opposto;
  - sizing: rischio in valuta = equity · risk_pct (compounding), size = rischio / |entry−stop|.

Assunzioni dichiarate: nessuno slippage oltre ``cost_bps``, nessun dividendo/funding,
niente fill parziali. È un backtest indicativo, non una garanzia di rendimenti futuri.
"""

from __future__ import annotations

import math

from ..indicators import atr as atr_indicator
from ..indicators import sma
from ..models import (
    BacktestParams,
    BacktestResult,
    PositionSide,
    PriceSeries,
    RiskParams,
    SignalAction,
    Trade,
)


def run_backtest(series: PriceSeries, params: BacktestParams) -> BacktestResult:
    df = series.to_frame()
    n = len(df)
    base = {
        "symbol": series.symbol,
        "asset_class": series.asset_class,
        "interval": series.interval,
        "n_bars": n,
        "capital": params.capital,
    }

    warmup = max(params.sma_slow, params.atr_period) + 1
    if n < warmup + 5:
        return BacktestResult(
            **base,
            computed=False,
            notes=[
                f"Storico insufficiente per il backtest (servono almeno ~{warmup + 5} barre, "
                f"disponibili {n})."
            ],
        )

    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    fast = sma(df["close"], params.sma_fast).to_numpy()
    slow = sma(df["close"], params.sma_slow).to_numpy()
    atrv = atr_indicator(df, params.atr_period).to_numpy()
    dates = [ts.to_pydatetime() for ts in df.index]

    cost = params.cost_bps / 10000.0
    state: dict = {"equity": params.capital, "pos": None}
    trades: list[Trade] = []
    equity_curve: list[float] = [params.capital]

    def valid(i: int) -> bool:
        return not (
            math.isnan(fast[i])
            or math.isnan(slow[i])
            or math.isnan(fast[i - 1])
            or math.isnan(slow[i - 1])
            or math.isnan(atrv[i])
        )

    def cross_up(i: int) -> bool:
        return fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]

    def cross_dn(i: int) -> bool:
        return fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]

    def open_pos(side: PositionSide, i: int) -> None:
        entry = c[i]
        risk_unit = params.atr_stop_mult * atrv[i]
        if risk_unit <= 0:
            return
        if side == PositionSide.LONG:
            stop = entry - risk_unit
            target = entry + params.rr_target * risk_unit
        else:
            stop = entry + risk_unit
            target = entry - params.rr_target * risk_unit
        risk_amount = state["equity"] * params.risk_pct / 100.0
        size = risk_amount / risk_unit
        state["pos"] = {
            "side": side,
            "entry": entry,
            "stop": stop,
            "target": target,
            "size": size,
            "risk_unit": risk_unit,
            "entry_index": i,
        }

    def close_pos(exit_price: float, i: int, reason: str) -> None:
        pos = state["pos"]
        long = pos["side"] == PositionSide.LONG
        move = (exit_price - pos["entry"]) if long else (pos["entry"] - exit_price)
        gross = pos["size"] * move
        costs = cost * pos["size"] * (pos["entry"] + exit_price)
        pnl = gross - costs
        state["equity"] += pnl
        equity_curve.append(state["equity"])
        trades.append(
            Trade(
                side=pos["side"],
                entry_index=pos["entry_index"],
                exit_index=i,
                entry_date=dates[pos["entry_index"]],
                exit_date=dates[i],
                entry=round(pos["entry"], 6),
                exit=round(exit_price, 6),
                stop=round(pos["stop"], 6),
                target=round(pos["target"], 6),
                size=round(pos["size"], 8),
                pnl=round(pnl, 4),
                r_multiple=round(move / pos["risk_unit"], 4),
                bars_held=i - pos["entry_index"],
                reason=reason,
            )
        )
        state["pos"] = None

    for i in range(warmup, n):
        if not valid(i):
            continue
        pos = state["pos"]
        if pos is None:
            if params.direction in ("long", "both") and cross_up(i):
                open_pos(PositionSide.LONG, i)
            elif params.direction in ("short", "both") and cross_dn(i):
                open_pos(PositionSide.SHORT, i)
            continue

        long = pos["side"] == PositionSide.LONG
        stop, target = pos["stop"], pos["target"]
        exit_price = reason = None
        if long:
            if o[i] <= stop:
                exit_price, reason = o[i], "stop (gap)"
            elif o[i] >= target:
                exit_price, reason = o[i], "target (gap)"
            elif low[i] <= stop:
                exit_price, reason = stop, "stop"
            elif h[i] >= target:
                exit_price, reason = target, "target"
        else:
            if o[i] >= stop:
                exit_price, reason = o[i], "stop (gap)"
            elif o[i] <= target:
                exit_price, reason = o[i], "target (gap)"
            elif h[i] >= stop:
                exit_price, reason = stop, "stop"
            elif low[i] <= target:
                exit_price, reason = target, "target"

        if exit_price is not None:
            close_pos(exit_price, i, reason)
            continue

        # nessuno stop/target: valuta l'inversione di trend
        if long and cross_dn(i):
            close_pos(c[i], i, "inversione trend")
            if params.direction == "both":
                open_pos(PositionSide.SHORT, i)
        elif (not long) and cross_up(i):
            close_pos(c[i], i, "inversione trend")
            if params.direction == "both":
                open_pos(PositionSide.LONG, i)

    if state["pos"] is not None:
        close_pos(c[n - 1], n - 1, "fine serie")

    return _metrics(base, trades, equity_curve, params, c, warmup, n)


def run_signal_backtest(
    series: PriceSeries,
    risk_params: RiskParams,
    *,
    signal_lookback: int = 720,
    cost_bps: float = 5.0,
    warmup: int = 60,
) -> BacktestResult:
    """Backtest del SEGNALE OPERATIVO REALE (i 6 cancelli), senza lookahead.

    A ogni barra ``i`` ricalcola ``build_operating_signal`` sulla sola finestra di
    dati fino a ``i`` (ultimo ``signal_lookback`` barre, come in produzione): se il
    verdetto è ENTRA apre la posizione al close di ``i`` usando stop/target/lato del
    sistema; poi gestisce l'uscita barra per barra (stop/target intrabar, gap
    all'apertura, stop prudenziale se entrambi toccati). Sizing a rischio % (compounding).

    A differenza di ``run_backtest`` (baseline SMA), qui si valuta il sistema vero.
    """
    from ..analysis.signal import build_operating_signal  # lazy: evita import pesanti a load

    df = series.to_frame()
    n = len(df)
    base = {
        "symbol": series.symbol,
        "asset_class": series.asset_class,
        "interval": series.interval,
        "n_bars": n,
        "capital": risk_params.capital,
    }
    if n < warmup + 20:
        return BacktestResult(
            **base,
            computed=False,
            notes=[f"Storico insufficiente per il backtest del segnale (barre: {n})."],
        )

    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    dates = [ts.to_pydatetime() for ts in df.index]
    bars = series.bars

    cost = cost_bps / 10000.0
    equity = risk_params.capital
    equity_curve: list[float] = [equity]
    trades: list[Trade] = []
    pos: dict | None = None

    i = warmup
    while i < n:
        if pos is None:
            a = max(0, i - signal_lookback + 1)
            sub = series.model_copy(update={"bars": bars[a : i + 1]})
            sig = build_operating_signal(sub, risk_params)
            ok_levels = (
                sig.action == SignalAction.ENTER
                and sig.stop_loss is not None
                and sig.take_profit is not None
                and sig.side in (PositionSide.LONG, PositionSide.SHORT)
            )
            if ok_levels:
                entry = c[i]
                stop = float(sig.stop_loss)
                target = float(sig.take_profit)
                long = sig.side == PositionSide.LONG
                # scarta setup malformati (livelli dal lato sbagliato)
                well_formed = (stop < entry < target) if long else (target < entry < stop)
                risk_unit = abs(entry - stop)
                if well_formed and risk_unit > 0:
                    risk_amount = equity * risk_params.risk_pct / 100.0
                    pos = {
                        "side": sig.side,
                        "entry": entry,
                        "stop": stop,
                        "target": target,
                        "size": risk_amount / risk_unit,
                        "risk_unit": risk_unit,
                        "entry_index": i,
                    }
            i += 1
            continue

        # in posizione: gestione uscita alla barra i (nessun lookahead: entrata era a i-…)
        long = pos["side"] == PositionSide.LONG
        stop, target = pos["stop"], pos["target"]
        exit_price = reason = None
        if long:
            if o[i] <= stop:
                exit_price, reason = o[i], "stop (gap)"
            elif o[i] >= target:
                exit_price, reason = o[i], "target (gap)"
            elif low[i] <= stop:
                exit_price, reason = stop, "stop"
            elif h[i] >= target:
                exit_price, reason = target, "target"
        else:
            if o[i] >= stop:
                exit_price, reason = o[i], "stop (gap)"
            elif o[i] <= target:
                exit_price, reason = o[i], "target (gap)"
            elif h[i] >= stop:
                exit_price, reason = stop, "stop"
            elif low[i] <= target:
                exit_price, reason = target, "target"

        if exit_price is not None:
            move = (exit_price - pos["entry"]) if long else (pos["entry"] - exit_price)
            gross = pos["size"] * move
            costs = cost * pos["size"] * (pos["entry"] + exit_price)
            pnl = gross - costs
            equity += pnl
            equity_curve.append(equity)
            trades.append(
                Trade(
                    side=pos["side"],
                    entry_index=pos["entry_index"],
                    exit_index=i,
                    entry_date=dates[pos["entry_index"]],
                    exit_date=dates[i],
                    entry=round(pos["entry"], 6),
                    exit=round(exit_price, 6),
                    stop=round(pos["stop"], 6),
                    target=round(pos["target"], 6),
                    size=round(pos["size"], 8),
                    pnl=round(pnl, 4),
                    r_multiple=round(move / pos["risk_unit"], 4),
                    bars_held=i - pos["entry_index"],
                    reason=reason,
                )
            )
            pos = None
        i += 1

    if pos is not None:
        move = (c[n - 1] - pos["entry"]) if pos["side"] == PositionSide.LONG else (
            pos["entry"] - c[n - 1]
        )
        pnl = pos["size"] * move - cost * pos["size"] * (pos["entry"] + c[n - 1])
        equity += pnl
        equity_curve.append(equity)
        trades.append(
            Trade(
                side=pos["side"],
                entry_index=pos["entry_index"],
                exit_index=n - 1,
                entry_date=dates[pos["entry_index"]],
                exit_date=dates[n - 1],
                entry=round(pos["entry"], 6),
                exit=round(c[n - 1], 6),
                stop=round(pos["stop"], 6),
                target=round(pos["target"], 6),
                size=round(pos["size"], 8),
                pnl=round(pnl, 4),
                r_multiple=round(move / pos["risk_unit"], 4),
                bars_held=n - 1 - pos["entry_index"],
                reason="fine serie",
            )
        )

    notes = [
        "Strategia: SEGNALE OPERATIVO COMPLETO (6 cancelli: direzione, momentum, "
        f"R:R≥{risk_params.min_rr}, sizing, ADX, allineamento grado superiore).",
        "Nessun lookahead: a ogni barra il segnale usa solo i dati passati "
        f"(finestra {signal_lookback} barre); ingresso al close, gestione dalla barra dopo.",
        (
            "Costi non modellati."
            if cost_bps == 0
            else f"Costo round-trip applicato: {cost_bps} bps."
        ),
        "Stop prudenziale se stop e target nella stessa barra. "
        "I risultati passati non garantiscono quelli futuri.",
    ]
    return _stats_result(base, trades, equity_curve, c, warmup, n, notes)


def _stats_result(base, trades, equity_curve, c, warmup, n, notes) -> BacktestResult:
    """Metriche di sintesi condivise (usato dal backtest del segnale)."""
    buy_hold = (c[n - 1] / c[warmup] - 1.0) * 100.0
    capital = base["capital"]
    if not trades:
        return BacktestResult(
            **base,
            computed=True,
            final_equity=round(capital, 2),
            buy_hold_return_pct=round(buy_hold, 2),
            notes=[*notes, "Nessun trade generato dal segnale nel periodo."],
        )
    pnls = [t.pnl for t in trades]
    r_multiples = [t.r_multiple for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    profit_factor = round(gross_profit / gross_loss, 3) if gross_loss > 0 else None
    peak = equity_curve[0]
    max_dd = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        if peak > 0:
            max_dd = max(max_dd, (peak - e) / peak * 100.0)
    final_equity = equity_curve[-1]
    warnings = []
    if len(trades) < 20:
        warnings.append(
            f"Solo {len(trades)} trade nel campione: statistiche poco robuste, cautela."
        )
    if final_equity <= 0:
        warnings.append("Capitale azzerato su questo storico.")
    return BacktestResult(
        **base,
        computed=True,
        n_trades=len(trades),
        wins=wins,
        losses=len(pnls) - wins,
        win_rate=round(wins / len(trades), 4),
        avg_r=round(sum(r_multiples) / len(r_multiples), 4),
        expectancy_r=round(sum(r_multiples) / len(r_multiples), 4),
        profit_factor=profit_factor,
        total_return_pct=round((final_equity / capital - 1.0) * 100.0, 2),
        buy_hold_return_pct=round(buy_hold, 2),
        max_drawdown_pct=round(max_dd, 2),
        final_equity=round(final_equity, 2),
        avg_bars_held=round(sum(t.bars_held for t in trades) / len(trades), 1),
        trades=trades,
        notes=notes,
        warnings=warnings,
    )


def _metrics(base, trades, equity_curve, params, c, warmup, n) -> BacktestResult:
    notes = [
        f"Strategia BASELINE: incrocio SMA {params.sma_fast}/{params.sma_slow}, "
        f"stop {params.atr_stop_mult}·ATR, target R:R {params.rr_target}, "
        f"direzione '{params.direction}'. NON è l'analisi multi-segnale completa.",
        "Nessun lookahead: ingresso alla chiusura del segnale, gestito dalla barra successiva.",
        (
            "Costi non modellati (cost_bps=0)."
            if params.cost_bps == 0
            else f"Costo round-trip applicato: {params.cost_bps} bps."
        ),
        "In caso di stop e target nella stessa barra si assume lo stop (prudenziale). "
        "I risultati passati non garantiscono quelli futuri.",
    ]

    buy_hold = (c[n - 1] / c[warmup] - 1.0) * 100.0

    if not trades:
        return BacktestResult(
            **base,
            computed=True,
            final_equity=round(params.capital, 2),
            buy_hold_return_pct=round(buy_hold, 2),
            notes=[*notes, "Nessun trade generato nel periodo (nessun incrocio operabile)."],
        )

    pnls = [t.pnl for t in trades]
    r_multiples = [t.r_multiple for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    losses = len(pnls) - wins
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    profit_factor = round(gross_profit / gross_loss, 3) if gross_loss > 0 else None

    peak = equity_curve[0]
    max_dd = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        if peak > 0:
            max_dd = max(max_dd, (peak - e) / peak * 100.0)

    final_equity = equity_curve[-1]
    warnings = []
    if len(trades) < 20:
        warnings.append(
            f"Solo {len(trades)} trade nel campione: statistiche poco robuste, "
            "interpretare con molta cautela."
        )
    if final_equity <= 0:
        warnings.append("Capitale azzerato: strategia rovinosa su questo storico.")

    return BacktestResult(
        **base,
        computed=True,
        n_trades=len(trades),
        wins=wins,
        losses=losses,
        win_rate=round(wins / len(trades), 4),
        avg_r=round(sum(r_multiples) / len(r_multiples), 4),
        expectancy_r=round(sum(r_multiples) / len(r_multiples), 4),
        profit_factor=profit_factor,
        total_return_pct=round((final_equity / params.capital - 1.0) * 100.0, 2),
        buy_hold_return_pct=round(buy_hold, 2),
        max_drawdown_pct=round(max_dd, 2),
        final_equity=round(final_equity, 2),
        avg_bars_held=round(sum(t.bars_held for t in trades) / len(trades), 1),
        trades=trades,
        notes=notes,
        warnings=warnings,
    )
