"""Applicazione FastAPI.

FASE 1: espone solo il recupero dati (nessuna analisi ancora). Ogni risposta
"dati" include un giudizio di qualità e il disclaimer. Le fasi successive
aggiungeranno endpoint di analisi tecnica, risk management e report.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from .. import DISCLAIMER, __version__
from ..analysis.entry import build_entry_playbook
from ..analysis.signal import build_operating_signal
from ..analysis.technical import analyze_technical
from ..backtest.engine import run_backtest
from ..data.base import DataFetchError, DataUnavailableError
from ..data.quality import assess
from ..data.service import MarketDataService
from ..models import (
    AssetClass,
    BacktestParams,
    BacktestResult,
    DataQuality,
    EntryPlaybook,
    Interval,
    MarketReport,
    OperatingSignal,
    PriceSeries,
    RiskParams,
    RiskPlan,
    TechnicalAnalysis,
)
from ..report.builder import build_report
from ..report.render import to_html, to_markdown, to_pdf
from ..risk.planner import build_risk_plan


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = __version__


class PriceResponse(BaseModel):
    """Risposta dell'endpoint /price."""

    series: PriceSeries
    data_quality: DataQuality
    disclaimer: str = Field(default=DISCLAIMER)


class TechnicalResponse(BaseModel):
    """Risposta dell'endpoint /analysis/technical."""

    analysis: TechnicalAnalysis
    disclaimer: str = Field(default=DISCLAIMER)


class RiskResponse(BaseModel):
    """Risposta dell'endpoint /analysis/risk-plan."""

    plan: RiskPlan
    disclaimer: str = Field(default=DISCLAIMER)


class ReportResponse(BaseModel):
    """Risposta JSON dell'endpoint /report (struttura + Markdown già renderizzato)."""

    report: MarketReport
    markdown: str


class BacktestResponse(BaseModel):
    """Risposta dell'endpoint /backtest."""

    result: BacktestResult
    disclaimer: str = Field(default=DISCLAIMER)


class EntryResponse(BaseModel):
    """Risposta dell'endpoint /analysis/entry."""

    playbook: EntryPlaybook
    disclaimer: str = Field(default=DISCLAIMER)


class SignalResponse(BaseModel):
    """Risposta dell'endpoint /signal (segnale operativo semplice)."""

    signal: OperatingSignal
    disclaimer: str = Field(default=DISCLAIMER)


def create_app(service: MarketDataService | None = None) -> FastAPI:
    """Crea l'app FastAPI. ``service`` iniettabile per i test."""
    app = FastAPI(
        title="Quant Analyzer API",
        version=__version__,
        summary="Motore di analisi quantitativa dei mercati — Fase 1: dati.",
    )
    # Servizio condiviso; sovrascrivibile via dependency_overrides nei test.
    default_service = service or MarketDataService()

    def get_service() -> MarketDataService:
        return default_service

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/price", response_model=PriceResponse, tags=["dati"])
    def price(
        symbol: str = Query(..., description="Ticker/simbolo, es. AAPL, BTC/USDT, EURUSD"),
        asset_class: AssetClass = Query(..., description="Classe di asset"),
        interval: Interval = Query(Interval.D1, description="Timeframe"),
        lookback: int = Query(250, ge=10, le=5000, description="Numero di barre richieste"),
        force_refresh: bool = Query(False, description="Ignora la cache e forza il fetch"),
        service: MarketDataService = Depends(get_service),
    ) -> PriceResponse:
        try:
            series = service.get_prices(
                symbol,
                asset_class,
                interval,
                lookback=lookback,
                force_refresh=force_refresh,
            )
        except DataUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DataFetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return PriceResponse(series=series, data_quality=assess(series))

    @app.get("/analysis/technical", response_model=TechnicalResponse, tags=["analisi"])
    def technical(
        symbol: str = Query(..., description="Ticker/simbolo, es. AAPL, BTC/USDT, EURUSD"),
        asset_class: AssetClass = Query(..., description="Classe di asset"),
        interval: Interval = Query(Interval.D1, description="Timeframe"),
        lookback: int = Query(
            300, ge=30, le=5000, description="Barre da analizzare (>=250 per la SMA200)"
        ),
        force_refresh: bool = Query(False, description="Ignora la cache e forza il fetch"),
        service: MarketDataService = Depends(get_service),
    ) -> TechnicalResponse:
        try:
            series = service.get_prices(
                symbol,
                asset_class,
                interval,
                lookback=lookback,
                force_refresh=force_refresh,
            )
        except DataUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DataFetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return TechnicalResponse(analysis=analyze_technical(series))

    @app.get("/analysis/risk-plan", response_model=RiskResponse, tags=["analisi"])
    def risk_plan(
        symbol: str = Query(..., description="Ticker/simbolo, es. AAPL, BTC/USDT, EURUSD"),
        asset_class: AssetClass = Query(..., description="Classe di asset"),
        capital: float = Query(..., gt=0, description="Capitale disponibile (valuta del conto)"),
        interval: Interval = Query(Interval.D1, description="Timeframe"),
        lookback: int = Query(300, ge=30, le=5000, description="Barre da analizzare"),
        risk_pct: float = Query(1.0, gt=0, le=100, description="% capitale a rischio/trade"),
        min_rr: float = Query(2.0, gt=0, description="Rapporto rischio/rendimento minimo"),
        atr_stop_mult: float = Query(1.5, gt=0, description="Moltiplicatore ATR per lo stop"),
        force_refresh: bool = Query(False, description="Ignora la cache e forza il fetch"),
        service: MarketDataService = Depends(get_service),
    ) -> RiskResponse:
        try:
            series = service.get_prices(
                symbol,
                asset_class,
                interval,
                lookback=lookback,
                force_refresh=force_refresh,
            )
        except DataUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DataFetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        params = RiskParams(
            capital=capital,
            risk_pct=risk_pct,
            min_rr=min_rr,
            atr_stop_mult=atr_stop_mult,
        )
        return RiskResponse(plan=build_risk_plan(series, params))

    @app.get("/analysis/entry", response_model=EntryResponse, tags=["analisi"])
    def entry(
        symbol: str = Query(..., description="Ticker/simbolo, es. XAUUSD, EURUSD, AAPL"),
        asset_class: AssetClass = Query(..., description="Classe di asset"),
        capital: float = Query(..., gt=0, description="Capitale disponibile"),
        interval: Interval = Query(Interval.D1, description="Timeframe"),
        lookback: int = Query(300, ge=30, le=5000, description="Barre da analizzare"),
        risk_pct: float = Query(1.0, gt=0, le=100, description="% capitale a rischio/trade"),
        min_rr: float = Query(2.0, gt=0, description="Rapporto rischio/rendimento minimo"),
        atr_stop_mult: float = Query(1.5, gt=0, description="Moltiplicatore ATR per lo stop"),
        force_refresh: bool = Query(False, description="Ignora la cache e forza il fetch"),
        service: MarketDataService = Depends(get_service),
    ) -> EntryResponse:
        try:
            series = service.get_prices(
                symbol, asset_class, interval, lookback=lookback, force_refresh=force_refresh
            )
        except DataUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DataFetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        params = RiskParams(
            capital=capital, risk_pct=risk_pct, min_rr=min_rr, atr_stop_mult=atr_stop_mult
        )
        ta = analyze_technical(series)
        plan = build_risk_plan(series, params, technical=ta)
        playbook = build_entry_playbook(ta, plan, min_rr=min_rr)
        if playbook is None:
            raise HTTPException(
                status_code=422,
                detail="Piano d'ingresso non calcolabile: dati insufficienti per l'analisi.",
            )
        return EntryResponse(playbook=playbook)

    @app.get("/signal", response_model=SignalResponse, tags=["analisi"])
    def signal(
        symbol: str = Query(..., description="Ticker/simbolo, es. XAUUSD, EURUSD, AAPL"),
        asset_class: AssetClass = Query(..., description="Classe di asset"),
        capital: float = Query(..., gt=0, description="Capitale disponibile"),
        interval: Interval = Query(Interval.D1, description="Timeframe"),
        lookback: int = Query(300, ge=30, le=5000, description="Barre da analizzare"),
        risk_pct: float = Query(1.0, gt=0, le=100, description="% capitale a rischio/trade"),
        min_rr: float = Query(2.0, gt=0, description="Rapporto rischio/rendimento minimo"),
        atr_stop_mult: float = Query(1.5, gt=0, description="Moltiplicatore ATR per lo stop"),
        force_refresh: bool = Query(False, description="Ignora la cache e forza il fetch"),
        service: MarketDataService = Depends(get_service),
    ) -> SignalResponse:
        try:
            series = service.get_prices(
                symbol, asset_class, interval, lookback=lookback, force_refresh=force_refresh
            )
        except DataUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DataFetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        params = RiskParams(
            capital=capital, risk_pct=risk_pct, min_rr=min_rr, atr_stop_mult=atr_stop_mult
        )
        return SignalResponse(signal=build_operating_signal(series, params))

    def _make_report(
        symbol: str,
        asset_class: AssetClass,
        interval: Interval,
        lookback: int,
        capital: float | None,
        risk_pct: float,
        min_rr: float,
        atr_stop_mult: float,
        force_refresh: bool,
        service: MarketDataService,
    ) -> MarketReport:
        try:
            series = service.get_prices(
                symbol,
                asset_class,
                interval,
                lookback=lookback,
                force_refresh=force_refresh,
            )
        except DataUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DataFetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        risk_params = (
            RiskParams(
                capital=capital,
                risk_pct=risk_pct,
                min_rr=min_rr,
                atr_stop_mult=atr_stop_mult,
            )
            if capital is not None
            else None
        )
        return build_report(series, risk_params)

    def _report_params(
        symbol: str = Query(..., description="Ticker/simbolo, es. AAPL, BTC/USDT, EURUSD"),
        asset_class: AssetClass = Query(..., description="Classe di asset"),
        interval: Interval = Query(Interval.D1, description="Timeframe"),
        lookback: int = Query(300, ge=30, le=5000, description="Barre da analizzare"),
        capital: float | None = Query(
            None, gt=0, description="Capitale: se presente, include il piano di rischio"
        ),
        risk_pct: float = Query(1.0, gt=0, le=100, description="% capitale a rischio/trade"),
        min_rr: float = Query(2.0, gt=0, description="Rapporto rischio/rendimento minimo"),
        atr_stop_mult: float = Query(1.5, gt=0, description="Moltiplicatore ATR per lo stop"),
        force_refresh: bool = Query(False, description="Ignora la cache e forza il fetch"),
        service: MarketDataService = Depends(get_service),
    ) -> MarketReport:
        return _make_report(
            symbol,
            asset_class,
            interval,
            lookback,
            capital,
            risk_pct,
            min_rr,
            atr_stop_mult,
            force_refresh,
            service,
        )

    @app.get("/report", response_model=ReportResponse, tags=["report"])
    def report(report_model: MarketReport = Depends(_report_params)) -> ReportResponse:
        return ReportResponse(report=report_model, markdown=to_markdown(report_model))

    @app.get("/report.md", response_class=PlainTextResponse, tags=["report"])
    def report_md(report_model: MarketReport = Depends(_report_params)) -> PlainTextResponse:
        return PlainTextResponse(
            to_markdown(report_model), media_type="text/markdown; charset=utf-8"
        )

    @app.get("/report.html", response_class=HTMLResponse, tags=["report"])
    def report_html(report_model: MarketReport = Depends(_report_params)) -> HTMLResponse:
        return HTMLResponse(to_html(report_model))

    @app.get("/report.pdf", tags=["report"])
    def report_pdf(report_model: MarketReport = Depends(_report_params)) -> Response:
        pdf_bytes = to_pdf(report_model)
        filename = f"report_{report_model.symbol.replace('/', '_')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    @app.get("/backtest", response_model=BacktestResponse, tags=["analisi"])
    def backtest(
        symbol: str = Query(..., description="Ticker/simbolo, es. AAPL, BTC/USDT, EURUSD"),
        asset_class: AssetClass = Query(..., description="Classe di asset"),
        capital: float = Query(..., gt=0, description="Capitale iniziale della simulazione"),
        interval: Interval = Query(Interval.D1, description="Timeframe"),
        lookback: int = Query(500, ge=60, le=5000, description="Barre storiche da simulare"),
        risk_pct: float = Query(1.0, gt=0, le=100, description="% capitale a rischio/trade"),
        atr_stop_mult: float = Query(1.5, gt=0, description="Moltiplicatore ATR per lo stop"),
        rr_target: float = Query(2.0, gt=0, description="R:R del target"),
        sma_fast: int = Query(20, gt=0, description="Periodo SMA veloce"),
        sma_slow: int = Query(50, gt=0, description="Periodo SMA lenta"),
        direction: str = Query("both", description="long | short | both"),
        cost_bps: float = Query(0.0, ge=0, description="Costo round-trip in bps"),
        force_refresh: bool = Query(False, description="Ignora la cache e forza il fetch"),
        service: MarketDataService = Depends(get_service),
    ) -> BacktestResponse:
        try:
            series = service.get_prices(
                symbol,
                asset_class,
                interval,
                lookback=lookback,
                force_refresh=force_refresh,
            )
        except DataUnavailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DataFetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        try:
            params = BacktestParams(
                capital=capital,
                risk_pct=risk_pct,
                atr_stop_mult=atr_stop_mult,
                rr_target=rr_target,
                sma_fast=sma_fast,
                sma_slow=sma_slow,
                direction=direction,  # type: ignore[arg-type]
                cost_bps=cost_bps,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return BacktestResponse(result=run_backtest(series, params))

    return app


# Istanza usata da uvicorn: `uvicorn quantanalyzer.api.app:app`
app = create_app()


def run() -> None:
    """Entrypoint per `quantanalyzer-api` (avvio dev con uvicorn)."""
    import uvicorn

    uvicorn.run("quantanalyzer.api.app:app", host="127.0.0.1", port=8000, reload=True)
