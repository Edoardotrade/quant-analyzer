"""Interpretazione degli indicatori tecnici in segnali spiegati.

Principi applicati:
  - se i dati sono insufficienti, NON si interpreta (computed=False);
  - ogni segnale porta con sé il suo ``rationale`` (cosa indica + cautele);
  - il linguaggio è probabilistico: nessuna certezza, nessun "verdetto unico".
    Gli scenari con probabilità e i livelli operativi arrivano nelle fasi 3-4.
"""

from __future__ import annotations

import math

import pandas as pd

from ..data.quality import assess
from ..indicators import (
    atr,
    bollinger,
    last_slope,
    macd,
    obv,
    relative_volume,
    rsi,
    sma,
    support_resistance,
)
from ..models import (
    Direction,
    IndicatorParams,
    PriceSeries,
    Signal,
    SupportResistance,
    TechnicalAnalysis,
)


def _last(series: pd.Series) -> float | None:
    """Ultimo valore non-NaN di una serie, oppure None."""
    s = series.dropna()
    if len(s) == 0:
        return None
    return float(s.iloc[-1])


def _round(value: float | None, ndigits: int = 4) -> float | None:
    return None if value is None else round(value, ndigits)


def _trend_signal(close: pd.Series, p: IndicatorParams) -> Signal:
    s_short, s_med, s_long = p.sma_periods
    price = float(close.iloc[-1])
    ma_med = _last(sma(close, s_med))
    ma_long = _last(sma(close, s_long))

    bull = bear = 0
    bits: list[str] = []
    if ma_med is not None:
        if price > ma_med:
            bull += 1
            bits.append(f"prezzo sopra SMA{s_med}")
        else:
            bear += 1
            bits.append(f"prezzo sotto SMA{s_med}")
    if ma_long is not None:
        if price > ma_long:
            bull += 1
            bits.append(f"prezzo sopra SMA{s_long}")
        else:
            bear += 1
            bits.append(f"prezzo sotto SMA{s_long}")
    if ma_med is not None and ma_long is not None:
        if ma_med > ma_long:
            bull += 1
            bits.append(f"SMA{s_med} sopra SMA{s_long} (struttura rialzista)")
        else:
            bear += 1
            bits.append(f"SMA{s_med} sotto SMA{s_long} (struttura ribassista)")

    slope = last_slope(sma(close, s_med), s_med)
    if not math.isnan(slope):
        if slope > 0:
            bits.append(f"SMA{s_med} inclinata al rialzo")
        elif slope < 0:
            bits.append(f"SMA{s_med} inclinata al ribasso")

    if bull > bear:
        direction, state = Direction.BULLISH, "trend rialzista"
    elif bear > bull:
        direction, state = Direction.BEARISH, "trend ribassista"
    else:
        direction, state = Direction.NEUTRAL, "trend incerto/laterale"

    if not bits:
        bits.append("storico insufficiente per alcune medie")

    rationale = (
        "Struttura delle medie mobili: "
        + "; ".join(bits)
        + ". Le medie descrivono la direzione dominante e il loro ordinamento la "
        "'salute' del trend; prezzo sopra le medie e medie ordinate indicano un "
        "contesto favorevole alla direzione, ma descrivono il passato e non predicono il futuro."
    )
    return Signal(
        name=f"Trend (SMA {s_short}/{s_med}/{s_long})",
        value=_round(ma_med),
        state=state,
        direction=direction,
        rationale=rationale,
    )


def _rsi_signal(close: pd.Series, p: IndicatorParams) -> Signal:
    value = _last(rsi(close, p.rsi_period))
    if value is None:
        return Signal(
            name=f"RSI ({p.rsi_period})",
            value=None,
            state="n/d",
            direction=Direction.NEUTRAL,
            rationale="Storico insufficiente per calcolare l'RSI.",
        )

    if value >= 70:
        state = "ipercomprato"
        extra = (
            "zona di ipercomprato: aumenta la probabilità di una pausa o di un "
            "ritracciamento, ma in trend forti l'RSI può restare alto a lungo — "
            "di per sé NON è un segnale di vendita."
        )
    elif value <= 30:
        state = "ipervenduto"
        extra = (
            "zona di ipervenduto: aumenta la probabilità di un rimbalzo, ma in trend "
            "ribassisti forti può restare basso a lungo — di per sé NON è un segnale di acquisto."
        )
    else:
        state = "neutrale"
        extra = "nessun estremo: momentum in area intermedia."

    # Direzione dal momentum (linea 50), con piccola banda morta attorno a 50.
    if value > 55:
        direction = Direction.BULLISH
    elif value < 45:
        direction = Direction.BEARISH
    else:
        direction = Direction.NEUTRAL

    rationale = (
        f"RSI({p.rsi_period}) = {value:.1f}. Misura la forza relativa dei movimenti "
        f"recenti su scala 0-100 (sopra 50 = momentum rialzista, sotto = ribassista); {extra}"
    )
    return Signal(
        name=f"RSI ({p.rsi_period})",
        value=_round(value, 2),
        state=state,
        direction=direction,
        rationale=rationale,
    )


def _macd_signal(close: pd.Series, p: IndicatorParams) -> Signal:
    frame = macd(close, p.macd_fast, p.macd_slow, p.macd_signal)
    macd_v = _last(frame["macd"])
    signal_v = _last(frame["signal"])
    hist_series = frame["hist"].dropna()
    if macd_v is None or signal_v is None or len(hist_series) < 2:
        return Signal(
            name=f"MACD ({p.macd_fast}/{p.macd_slow}/{p.macd_signal})",
            value=None,
            state="n/d",
            direction=Direction.NEUTRAL,
            rationale="Storico insufficiente per calcolare il MACD.",
        )

    hist = float(hist_series.iloc[-1])
    hist_prev = float(hist_series.iloc[-2])
    above = macd_v > signal_v
    momentum = "in aumento" if hist > hist_prev else "in calo"

    if above:
        direction = Direction.BULLISH
        state = "MACD sopra la signal"
    else:
        direction = Direction.BEARISH
        state = "MACD sotto la signal"

    zero_note = "sopra lo zero" if macd_v > 0 else "sotto lo zero"
    rationale = (
        f"MACD = {macd_v:.4f}, Signal = {signal_v:.4f}, Istogramma = {hist:.4f} ({momentum}). "
        f"Il MACD ({zero_note}) confronta due medie esponenziali: la linea sopra la signal "
        "indica momentum a favore dei rialzi, sotto a favore dei ribassi; l'istogramma "
        "misura la forza del movimento. È un indicatore ritardato: conferma, non anticipa."
    )
    return Signal(
        name=f"MACD ({p.macd_fast}/{p.macd_slow}/{p.macd_signal})",
        value=_round(macd_v),
        state=state,
        direction=direction,
        rationale=rationale,
    )


def _atr_signal(df: pd.DataFrame, price: float, p: IndicatorParams) -> Signal:
    value = _last(atr(df, p.atr_period))
    if value is None or price == 0:
        return Signal(
            name=f"Volatilità (ATR {p.atr_period})",
            value=None,
            state="n/d",
            direction=Direction.NEUTRAL,
            rationale="Storico insufficiente per calcolare l'ATR.",
        )
    pct = value / price * 100
    rationale = (
        f"ATR({p.atr_period}) = {value:.4f} (~{pct:.2f}% del prezzo). Misura l'ampiezza "
        "media di oscillazione (volatilità), non la direzione. Servirà nella Fase 3 per "
        "dimensionare stop e target in modo oggettivo: più volatilità = stop più larghi e "
        "posizione più piccola a parità di rischio."
    )
    return Signal(
        name=f"Volatilità (ATR {p.atr_period})",
        value=_round(value),
        state=f"~{pct:.2f}% del prezzo",
        direction=Direction.NEUTRAL,
        rationale=rationale,
    )


def _bollinger_signal(close: pd.Series, price: float, p: IndicatorParams) -> Signal:
    frame = bollinger(close, p.bb_period, p.bb_std)
    upper = _last(frame["upper"])
    lower = _last(frame["lower"])
    mid = _last(frame["mid"])
    if upper is None or lower is None or mid is None or upper == lower:
        return Signal(
            name=f"Bollinger ({p.bb_period}, {p.bb_std}σ)",
            value=None,
            state="n/d",
            direction=Direction.NEUTRAL,
            rationale="Storico insufficiente per calcolare le Bande di Bollinger.",
        )

    percent_b = (price - lower) / (upper - lower)  # 0 = banda inf, 1 = banda sup
    width_pct = (upper - lower) / mid * 100 if mid else float("nan")

    if price >= upper:
        state = "oltre la banda superiore"
    elif price <= lower:
        state = "oltre la banda inferiore"
    else:
        state = f"%B = {percent_b:.2f}"

    rationale = (
        f"Prezzo rispetto alle bande (ampiezza ~{width_pct:.2f}% della media): {state}. "
        "Le bande racchiudono ~2σ di oscillazione attorno alla media: vicino alla banda "
        "superiore il prezzo è teso verso l'alto, vicino a quella inferiore verso il basso. "
        "Bande strette segnalano bassa volatilità (possibile espansione in arrivo). "
        "Non è un segnale direzionale di per sé."
    )
    return Signal(
        name=f"Bollinger ({p.bb_period}, {p.bb_std}σ)",
        value=_round(percent_b, 3),
        state=state,
        direction=Direction.NEUTRAL,
        rationale=rationale,
    )


def _volume_signal(df: pd.DataFrame, p: IndicatorParams) -> Signal:
    volume = df["volume"].astype(float)
    if float(volume.abs().sum()) == 0.0:
        return Signal(
            name="Volume",
            value=None,
            state="non disponibile",
            direction=Direction.NEUTRAL,
            rationale=(
                "Volume non fornito dalla fonte per questo strumento (tipico di indici e "
                "di parte del forex): l'analisi del volume non è applicabile."
            ),
        )

    relvol = _last(relative_volume(volume, p.bb_period))
    obv_series = obv(df["close"], volume)
    obv_slope = last_slope(obv_series, min(len(obv_series), p.bb_period))

    if obv_slope > 0:
        direction, obv_txt = Direction.BULLISH, "OBV in salita (conferma pressione in acquisto)"
    elif obv_slope < 0:
        direction, obv_txt = Direction.BEARISH, "OBV in discesa (conferma pressione in vendita)"
    else:
        direction, obv_txt = Direction.NEUTRAL, "OBV piatto"

    if relvol is None or math.isnan(relvol):
        state = obv_txt
        rel_txt = "volume relativo non calcolabile (storico breve)"
    elif relvol >= 1.5:
        state = "volume elevato"
        rel_txt = f"volume {relvol:.2f}x la media (partecipazione elevata)"
    elif relvol <= 0.7:
        state = "volume debole"
        rel_txt = f"volume {relvol:.2f}x la media (partecipazione scarsa)"
    else:
        state = "volume nella norma"
        rel_txt = f"volume {relvol:.2f}x la media"

    rationale = (
        f"{rel_txt}; {obv_txt}. Il volume misura la partecipazione dietro un movimento: "
        "un movimento con volume in aumento è più 'credibile' di uno con volume calante. "
        "L'OBV cumula il volume col segno del prezzo per confermare (o smentire) il trend."
    )
    return Signal(
        name="Volume",
        value=_round(relvol, 2),
        state=state,
        direction=direction,
        rationale=rationale,
    )


def _support_resistance(df: pd.DataFrame, price: float, p: IndicatorParams) -> SupportResistance:
    supports, resistances = support_resistance(df, price, lookback=p.pivot_lookback)
    return SupportResistance(
        current_price=round(price, 4),
        supports=[round(x, 4) for x in supports],
        resistances=[round(x, 4) for x in resistances],
    )


def _synthesize(signals: list[Signal]) -> str:
    bull = sum(1 for s in signals if s.direction == Direction.BULLISH)
    bear = sum(1 for s in signals if s.direction == Direction.BEARISH)
    neutral = sum(1 for s in signals if s.direction == Direction.NEUTRAL)

    if bull > bear:
        lean = "prevalentemente rialzista"
    elif bear > bull:
        lean = "prevalentemente ribassista"
    else:
        lean = "misto/incerto"

    conflict = ""
    if bull > 0 and bear > 0:
        conflict = " Attenzione: segnali discordanti — il quadro non è univoco."

    return (
        f"Bilancio dei segnali: {bull} rialzisti, {bear} ribassisti, {neutral} neutri → "
        f"quadro tecnico {lean}.{conflict} È un BILANCIO DI INDICATORI sul passato, non una "
        "previsione: per gli scenari alternativi con probabilità e per i livelli operativi "
        "(entry/stop/target con R:R) vedi il piano di rischio e il report completo."
    )


def analyze_technical(
    series: PriceSeries,
    params: IndicatorParams | None = None,
) -> TechnicalAnalysis:
    """Analizza tecnicamente una serie di prezzi e restituisce segnali spiegati."""
    p = params or IndicatorParams()
    quality = assess(series, min_bars=p.min_bars)

    common = {
        "symbol": series.symbol,
        "asset_class": series.asset_class,
        "interval": series.interval,
        "as_of": series.end,
        "current_price": series.last_close,
        "data_quality": quality,
    }

    if not quality.sufficient:
        return TechnicalAnalysis(
            **common,
            computed=False,
            trend_summary="Analisi non calcolata: dati insufficienti o inaffidabili.",
            signals=[],
            support_resistance=None,
            notes=[
                "Dati insufficienti o non affidabili: nessuna interpretazione prodotta, "
                "per non forzare una raccomandazione su basi deboli.",
                *quality.warnings,
            ],
        )

    df = series.to_frame()
    close = df["close"]
    price = float(close.iloc[-1])
    notes: list[str] = []

    n = len(df)
    if n < max(p.sma_periods):
        notes.append(
            f"Solo {n} barre: la SMA{max(p.sma_periods)} (trend di lungo periodo) "
            "non è disponibile; il giudizio di trend usa gli orizzonti più corti."
        )

    signals = [
        _trend_signal(close, p),
        _rsi_signal(close, p),
        _macd_signal(close, p),
        _atr_signal(df, price, p),
        _bollinger_signal(close, price, p),
        _volume_signal(df, p),
    ]
    sr = _support_resistance(df, price, p)
    if not sr.supports:
        notes.append("Nessun supporto tecnico rilevato sotto il prezzo nello storico analizzato.")
    if not sr.resistances:
        notes.append(
            "Nessuna resistenza tecnica rilevata sopra il prezzo nello storico analizzato."
        )

    return TechnicalAnalysis(
        **common,
        computed=True,
        trend_summary=_synthesize(signals),
        signals=signals,
        support_resistance=sr,
        notes=notes,
    )
