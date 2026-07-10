"""Test del report: costruzione, scenari, confidenza e rendering multi-formato."""

from __future__ import annotations

from helpers import build_linear_series

from quantanalyzer.models import ConfidenceLevel, Probability, RiskParams, ScenarioType
from quantanalyzer.report.builder import build_report
from quantanalyzer.report.render import to_html, to_markdown, to_pdf

PARAMS = RiskParams(capital=10_000, risk_pct=1.0)


def test_report_has_three_scenarios_and_no_single_verdict():
    report = build_report(build_linear_series(n=260, start=100, step=1.0), PARAMS)
    types = {s.type for s in report.scenarios}
    assert types == {ScenarioType.BULLISH, ScenarioType.BEARISH, ScenarioType.SIDEWAYS}
    # trend fortemente rialzista -> scenario rialzista ad alta probabilità
    bull = next(s for s in report.scenarios if s.type == ScenarioType.BULLISH)
    assert bull.probability == Probability.ALTA
    # ogni scenario ha una condizione di invalidazione esplicita
    assert all(s.invalidation for s in report.scenarios)
    assert report.disclaimer
    assert report.risk_plan is not None
    assert report.confidence != ConfidenceLevel.BASSA  # storico ampio e sufficiente


def test_report_without_capital_has_no_risk_plan():
    report = build_report(build_linear_series(n=260), risk_params=None)
    assert report.risk_plan is None
    md = to_markdown(report)
    assert "Piano di rischio" not in md


def test_insufficient_data_report():
    report = build_report(build_linear_series(n=10), PARAMS)
    assert report.technical.computed is False
    assert report.scenarios == []
    assert report.confidence == ConfidenceLevel.BASSA
    md = to_markdown(report)
    assert "Analisi non calcolata" in md
    # anche con dati scarsi il PDF si genera (con i limiti in evidenza)
    assert to_pdf(report)[:4] == b"%PDF"


def test_render_markdown():
    report = build_report(build_linear_series(n=260, symbol="AAPL"), PARAMS)
    md = to_markdown(report)
    assert md.startswith("# Report di analisi — AAPL")
    assert "## Scenari" in md
    assert "Disclaimer" in md
    assert "## Piano di rischio" in md


def test_render_html():
    report = build_report(build_linear_series(n=260, symbol="AAPL"), PARAMS)
    html = to_html(report)
    assert "<html" in html.lower()
    assert "AAPL" in html
    assert "Disclaimer" in html


def test_render_pdf_is_valid():
    report = build_report(build_linear_series(n=260), PARAMS)
    pdf = to_pdf(report)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000
