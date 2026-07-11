"""Modelli di dominio validati (Pydantic v2).

Questi modelli sono la "frontiera" dei dati: qualunque cosa entri nel sistema
(da yfinance, ccxt, cache, ...) viene normalizzata e validata qui. In questo
modo il resto del codice (indicatori, risk, report) lavora su dati coerenti.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:  # evita di importare pandas se non serve
    import pandas as pd


class AssetClass(str, Enum):
    """Classe di attività finanziaria richiesta."""

    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    FOREX = "forex"
    CRYPTO = "crypto"


class Interval(str, Enum):
    """Granularità temporale delle barre (timeframe)."""

    M15 = "15m"
    H1 = "1h"
    D1 = "1d"
    W1 = "1w"
    MO1 = "1mo"


def _to_utc(value: datetime) -> datetime:
    """Normalizza un datetime a UTC tz-aware (assume UTC se naive)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class OHLCVBar(BaseModel):
    """Una singola barra di prezzo (Open/High/Low/Close/Volume)."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @field_validator("timestamp")
    @classmethod
    def _normalize_ts(cls, v: datetime) -> datetime:
        return _to_utc(v)

    @model_validator(mode="after")
    def _check_consistency(self) -> OHLCVBar:
        eps = 1e-9
        if self.high < self.low - eps:
            raise ValueError(f"high ({self.high}) < low ({self.low}) @ {self.timestamp}")
        for name, val in (("open", self.open), ("close", self.close)):
            if val < self.low - eps or val > self.high + eps:
                raise ValueError(
                    f"{name} ({val}) fuori dal range [low={self.low}, high={self.high}] "
                    f"@ {self.timestamp}"
                )
        if self.volume < 0:
            raise ValueError(f"volume negativo ({self.volume}) @ {self.timestamp}")
        return self


class PriceSeries(BaseModel):
    """Serie storica di prezzi per un asset, con metadati di provenienza."""

    symbol: str
    asset_class: AssetClass
    interval: Interval
    source: str = Field(description="Provider che ha fornito i dati, es. 'yfinance'")
    fetched_at: datetime = Field(description="Istante di recupero dati (UTC)")
    bars: list[OHLCVBar] = Field(default_factory=list)

    @field_validator("fetched_at")
    @classmethod
    def _normalize_fetched_at(cls, v: datetime) -> datetime:
        return _to_utc(v)

    @property
    def last_close(self) -> float | None:
        return self.bars[-1].close if self.bars else None

    @property
    def start(self) -> datetime | None:
        return self.bars[0].timestamp if self.bars else None

    @property
    def end(self) -> datetime | None:
        return self.bars[-1].timestamp if self.bars else None

    def __len__(self) -> int:
        return len(self.bars)

    def to_frame(self) -> pd.DataFrame:
        """Converte la serie in un DataFrame indicizzato per timestamp (UTC)."""
        import pandas as pd

        cols = ["open", "high", "low", "close", "volume"]
        if not self.bars:
            return pd.DataFrame(columns=cols)
        records = [
            {
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in self.bars
        ]
        idx = pd.DatetimeIndex([b.timestamp for b in self.bars], name="timestamp")
        return pd.DataFrame(records, index=idx, columns=cols).sort_index()

    @classmethod
    def from_frame(
        cls,
        df: pd.DataFrame,
        *,
        symbol: str,
        asset_class: AssetClass,
        interval: Interval,
        source: str,
        fetched_at: datetime,
    ) -> PriceSeries:
        """Costruisce una PriceSeries da un DataFrame con colonne o/h/l/c/[v].

        Il DataFrame deve avere un indice temporale e colonne (case-insensitive)
        ``open, high, low, close`` e opzionalmente ``volume``.
        """
        import pandas as pd

        frame = df.rename(columns=str.lower)
        required = {"open", "high", "low", "close"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Colonne mancanti nel DataFrame: {sorted(missing)}")

        index = pd.to_datetime(frame.index, utc=True)
        bars: list[OHLCVBar] = []
        for ts, (_, row) in zip(index, frame.iterrows(), strict=True):
            volume = row["volume"] if "volume" in frame.columns else 0.0
            if pd.isna(volume):
                volume = 0.0
            o, h, low_, c = (
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
            )
            # Normalizzazione alla frontiera: high/low devono contenere open/close.
            # Alcune fonti (tipicamente il forex di Yahoo) riportano un open/close
            # fuori dal range high-low; ampliamo il range invece di scartare la barra.
            bars.append(
                OHLCVBar(
                    timestamp=ts.to_pydatetime(),
                    open=o,
                    high=max(o, h, low_, c),
                    low=min(o, h, low_, c),
                    close=c,
                    volume=float(volume),
                )
            )
        return cls(
            symbol=symbol,
            asset_class=asset_class,
            interval=interval,
            source=source,
            fetched_at=fetched_at,
            bars=bars,
        )


class DataQuality(BaseModel):
    """Esito della valutazione di qualità di una serie di prezzi.

    Serve al principio non negoziabile: se i dati sono insufficienti,
    l'analisi lo dichiara invece di forzare una conclusione.
    """

    n_bars: int
    min_bars: int
    is_ordered: bool
    has_duplicates: bool
    sufficient: bool
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Fase 2: analisi tecnica
# --------------------------------------------------------------------------- #


class Direction(str, Enum):
    """Direzione qualitativa suggerita da un segnale."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class IndicatorParams(BaseModel):
    """Parametri (configurabili) degli indicatori. Default standard di settore."""

    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    sma_periods: tuple[int, int, int] = (20, 50, 200)
    atr_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    pivot_lookback: int = 5
    min_bars: int = 30


class Signal(BaseModel):
    """Un singolo segnale tecnico, con la spiegazione di cosa indica.

    Il campo ``rationale`` è obbligatorio: non esponiamo mai un valore senza
    dire cosa significa e con quali cautele (principio: mostrare il ragionamento).
    """

    name: str
    value: float | None = None
    state: str
    direction: Direction
    rationale: str


class SupportResistance(BaseModel):
    """Livelli tecnici vicini, calcolati da swing highs/lows."""

    current_price: float
    supports: list[float] = Field(default_factory=list)
    resistances: list[float] = Field(default_factory=list)


class TechnicalAnalysis(BaseModel):
    """Esito dell'analisi tecnica di un asset.

    Se ``computed`` è False, l'analisi si è rifiutata di interpretare dati
    insufficienti/inaffidabili (vedi ``notes``): nessun segnale forzato.
    """

    symbol: str
    asset_class: AssetClass
    interval: Interval
    as_of: datetime | None = None
    current_price: float | None = None
    computed: bool
    trend_summary: str
    weekly_trend: Direction | None = None
    signals: list[Signal] = Field(default_factory=list)
    support_resistance: SupportResistance | None = None
    data_quality: DataQuality
    notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Fase 3: risk management
# --------------------------------------------------------------------------- #


class PositionSide(str, Enum):
    """Lato dell'operazione suggerita."""

    LONG = "long"
    SHORT = "short"
    NONE = "none"  # nessun bias direzionale chiaro -> nessun trade


class RiskParams(BaseModel):
    """Parametri di gestione del rischio (input dell'utente + default prudenti)."""

    capital: float = Field(gt=0, description="Capitale disponibile, valuta del conto")
    risk_pct: float = Field(default=1.0, gt=0, le=100, description="% del capitale a rischio/trade")
    min_rr: float = Field(default=2.0, gt=0, description="Rapporto rischio/rendimento minimo")
    atr_stop_mult: float = Field(default=1.5, gt=0, description="Moltiplicatore ATR per lo stop")
    atr_period: int = Field(default=14, gt=0)
    tech_stop_buffer_atr: float = Field(default=0.25, ge=0, description="Cuscinetto (ATR)")
    max_stop_atr: float = Field(default=3.5, gt=0, description="Distanza max stop tecnico in ATR")


class RiskPlan(BaseModel):
    """Piano operativo di rischio calcolato con logica esplicita.

    ``viable`` è True solo se esiste un bias direzionale, i dati sono sufficienti,
    lo stop è definibile e il rapporto R:R rispetta il minimo richiesto.
    Ogni livello è accompagnato dal suo ``rationale``.
    """

    symbol: str
    side: PositionSide
    viable: bool
    capital: float
    risk_pct: float

    entry: float | None = None
    entry_zone: tuple[float, float] | None = None
    stop: float | None = None
    stop_basis: str | None = None
    target: float | None = None
    target_basis: str | None = None

    atr: float | None = None
    risk_per_unit: float | None = None
    reward_per_unit: float | None = None
    rr: float | None = None
    meets_min_rr: bool = False

    risk_amount: float | None = None
    position_size_units: float | None = None
    position_notional: float | None = None

    rationale: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EntryGate(BaseModel):
    """Uno dei 'cancelli' che devono essere superati per un ingresso disciplinato."""

    name: str
    passed: bool
    detail: str


class EntryPlaybook(BaseModel):
    """Piano d'ingresso: dice se il setup è pronto ORA e, se no, cosa attendere.

    Non è un 'compra adesso': elenca i cancelli superati/falliti, i trigger che
    renderebbero valido l'ingresso e la condizione che invaliderebbe la tesi.
    """

    symbol: str
    side: PositionSide
    ready: bool
    verdict: str
    gates: list[EntryGate] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    invalidation: str


class SignalAction(str, Enum):
    ENTER = "entra"
    WAIT = "aspetta"
    NONE = "nessuno"


class OperatingSignal(BaseModel):
    """Segnale operativo in linguaggio semplice: ENTRA/ASPETTA + prezzo, SL, TP.

    È la vista 'per l'utente' che unisce analisi + rischio + piano d'ingresso in
    una risposta diretta: cosa fare, a che prezzo, con quale stop e target.
    """

    symbol: str
    asset_class: AssetClass
    action: SignalAction
    side: PositionSide
    ready: bool
    price: float | None = None
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    rr: float | None = None
    size_units: float | None = None
    headline: str
    reason: str
    as_of: datetime | None = None
    market_open: bool = True
    market_note: str = ""


# --------------------------------------------------------------------------- #
# Fase 4: scenari + report
# --------------------------------------------------------------------------- #


class ScenarioType(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"


class Probability(str, Enum):
    """Probabilità QUALITATIVA (non calibrata statisticamente)."""

    ALTA = "alta"
    MEDIA = "media"
    BASSA = "bassa"


class ConfidenceLevel(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BASSA = "bassa"


class Scenario(BaseModel):
    """Uno scenario alternativo con probabilità qualitativa e condizione di invalidazione."""

    type: ScenarioType
    title: str
    probability: Probability
    narrative: str
    key_levels: list[float] = Field(default_factory=list)
    invalidation: str


class MarketReport(BaseModel):
    """Report finale: unisce dati, analisi tecnica, piano di rischio e scenari.

    Struttura che *impone* i principi non negoziabili: scenari multipli (mai un
    verdetto unico), livello di confidenza, limiti espliciti e disclaimer.
    """

    symbol: str
    asset_class: AssetClass
    interval: Interval
    as_of: datetime | None = None
    current_price: float | None = None
    data_quality: DataQuality
    technical: TechnicalAnalysis
    risk_plan: RiskPlan | None = None
    entry_playbook: EntryPlaybook | None = None
    scenarios: list[Scenario] = Field(default_factory=list)
    confidence: ConfidenceLevel
    confidence_rationale: str
    limits: list[str] = Field(default_factory=list)
    disclaimer: str


# --------------------------------------------------------------------------- #
# Estensione: backtesting
# --------------------------------------------------------------------------- #


class Trade(BaseModel):
    """Una singola operazione simulata dal backtest."""

    side: PositionSide
    entry_index: int
    exit_index: int
    entry_date: datetime | None = None
    exit_date: datetime | None = None
    entry: float
    exit: float
    stop: float
    target: float
    size: float
    pnl: float
    r_multiple: float
    bars_held: int
    reason: str


class BacktestParams(BaseModel):
    """Parametri della strategia baseline testata (incrocio di medie + rischio)."""

    capital: float = Field(gt=0)
    risk_pct: float = Field(default=1.0, gt=0, le=100)
    atr_stop_mult: float = Field(default=1.5, gt=0)
    rr_target: float = Field(default=2.0, gt=0)
    atr_period: int = Field(default=14, gt=0)
    sma_fast: int = Field(default=20, gt=0)
    sma_slow: int = Field(default=50, gt=0)
    direction: Literal["long", "short", "both"] = "both"
    cost_bps: float = Field(default=0.0, ge=0, description="Costo round-trip in basis point")

    @model_validator(mode="after")
    def _check_periods(self) -> BacktestParams:
        if self.sma_fast >= self.sma_slow:
            raise ValueError("sma_fast deve essere < sma_slow")
        return self


class BacktestResult(BaseModel):
    """Esito del backtest con metriche di performance e confronto buy&hold."""

    symbol: str
    asset_class: AssetClass
    interval: Interval
    computed: bool
    n_bars: int
    capital: float
    n_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float | None = None
    total_return_pct: float = 0.0
    buy_hold_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    final_equity: float = 0.0
    avg_bars_held: float = 0.0
    trades: list[Trade] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
