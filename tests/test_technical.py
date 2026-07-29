"""Test del layer di interpretazione tecnica."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from helpers import build_linear_series

from quantanalyzer.analysis.technical import analyze_technical, higher_tf_label
from quantanalyzer.models import (
    AssetClass,
    Direction,
    Interval,
    OHLCVBar,
    PriceSeries,
)


def _hourly_uptrend(n: int = 500) -> PriceSeries:
    """Serie ORARIA sintetica in salita (per testare il filtro di grado superiore)."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    bars: list[OHLCVBar] = []
    price = 100.0
    for i in range(n):
        ts = start + timedelta(hours=i)
        open_ = price
        close = price * (1 + 0.0005 * (((i % 5) - 2) + 1))  # deriva netta al rialzo
        high = max(open_, close) * 1.002
        low = min(open_, close) * 0.998
        bars.append(
            OHLCVBar(timestamp=ts, open=open_, high=high, low=low, close=close, volume=1000.0 + i)
        )
        price = close
    return PriceSeries(
        symbol="TEST",
        asset_class=AssetClass.CRYPTO,
        interval=Interval.H1,
        source="fake",
        fetched_at=start + timedelta(hours=n),
        bars=bars,
    )


def _signal(analysis, name_prefix):
    for s in analysis.signals:
        if s.name.startswith(name_prefix):
            return s
    return None


def test_uptrend_is_computed_and_bullish():
    ta = analyze_technical(build_linear_series(n=260, start=100, step=1.0))
    assert ta.computed is True
    assert ta.current_price is not None
    assert len(ta.signals) == 7
    assert "rialzista" in ta.trend_summary.lower()
    # ogni segnale ha una spiegazione non vuota
    assert all(s.rationale for s in ta.signals)

    trend = _signal(ta, "Trend")
    assert trend.direction == Direction.BULLISH

    rsi_sig = _signal(ta, "RSI")
    assert rsi_sig.state == "ipercomprato"  # serie sempre crescente -> RSI 100
    assert rsi_sig.value == 100.0


def test_downtrend_is_bearish():
    ta = analyze_technical(build_linear_series(n=260, start=400, step=-1.0))
    assert ta.computed is True
    assert "ribassista" in ta.trend_summary.lower()
    assert _signal(ta, "Trend").direction == Direction.BEARISH
    assert _signal(ta, "RSI").state == "ipervenduto"


def test_insufficient_data_declines_to_interpret():
    ta = analyze_technical(build_linear_series(n=10))
    assert ta.computed is False
    assert ta.signals == []
    assert ta.support_resistance is None
    assert ta.notes  # spiega perché non ha interpretato
    assert ta.current_price is not None  # il prezzo grezzo resta disponibile
    assert ta.data_quality.sufficient is False


def test_support_resistance_present_in_uptrend():
    ta = analyze_technical(build_linear_series(n=120, start=50, step=0.5))
    assert ta.support_resistance is not None
    assert ta.support_resistance.current_price > 0


def test_higher_tf_label_adatta_al_timeframe():
    # Il filtro di grado superiore dipende dal timeframe operativo.
    assert higher_tf_label(Interval.H1) == "giornaliero"
    assert higher_tf_label(Interval.D1) == "settimanale"
    assert higher_tf_label(Interval.M15) == "4 ore"


def test_intraday_1h_usa_filtro_giornaliero():
    # Su una serie oraria in salita: l'analisi si calcola e il filtro di grado
    # superiore (giornaliero) rileva una direzione (non resta None).
    ta = analyze_technical(_hourly_uptrend(n=500))
    assert ta.computed is True
    assert ta.interval == Interval.H1
    assert ta.weekly_trend is not None  # 500 barre orarie -> ~20 barre giornaliere
    assert ta.weekly_trend == Direction.BULLISH
