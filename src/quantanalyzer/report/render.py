"""Rendering del MarketReport in Markdown, HTML e PDF.

Markdown e HTML mantengono l'Unicode completo. Il PDF (font core, senza font
esterni) usa una sanitizzazione dei pochi glifi non latin-1 per restare
dipendenza-leggero e portabile su Windows.
"""

from __future__ import annotations

import html

from ..models import MarketReport, RiskPlan

# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #


def _fmt(value: float | None, ndigits: int = 4) -> str:
    return "n/d" if value is None else f"{value:.{ndigits}f}"


def _levels(values: list[float]) -> str:
    return ", ".join(f"{v:.4f}" for v in values) if values else "nessuno"


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #


def to_markdown(report: MarketReport) -> str:
    r = report
    L: list[str] = []
    L.append(f"# Report di analisi — {r.symbol} ({r.asset_class.value}, {r.interval.value})")
    if r.as_of:
        L.append(f"*Dati aggiornati al {r.as_of:%Y-%m-%d %H:%M UTC}*")
    L.append("")
    L.append(f"- **Prezzo corrente:** {_fmt(r.current_price)}")
    L.append(f"- **Confidenza dell'analisi:** {r.confidence.value.upper()}")
    L.append(f"  - {r.confidence_rationale}")
    L.append(
        f"- **Qualità dati:** {r.data_quality.n_bars} barre, "
        f"sufficiente = {r.data_quality.sufficient}"
    )
    for w in r.data_quality.warnings:
        L.append(f"  - ⚠️ {w}")
    L.append("")

    if not r.technical.computed:
        L.append("## Analisi non calcolata")
        for note in r.technical.notes:
            L.append(f"- {note}")
    else:
        L.append("## Sintesi tecnica")
        L.append(r.technical.trend_summary)
        L.append("")
        L.append("## Segnali")
        L.append("| Indicatore | Stato | Direzione | Valore |")
        L.append("|---|---|---|---|")
        for s in r.technical.signals:
            L.append(f"| {s.name} | {s.state} | {s.direction.value} | {_fmt(s.value)} |")
        L.append("")
        L.append("**Dettaglio dei segnali:**")
        for s in r.technical.signals:
            L.append(f"- **{s.name}** — {s.rationale}")
        L.append("")
        if r.technical.support_resistance:
            sr = r.technical.support_resistance
            L.append("## Supporti e resistenze")
            L.append(f"- **Supporti:** {_levels(sr.supports)}")
            L.append(f"- **Resistenze:** {_levels(sr.resistances)}")
            L.append("")

    if r.risk_plan:
        L.extend(_risk_markdown(r.risk_plan))

    if r.entry_playbook:
        pb = r.entry_playbook
        L.append("## Piano d'ingresso")
        L.append(f"**Verdetto:** {pb.verdict}  ·  lato {pb.side.value}")
        L.append("")
        L.append("**Cancelli (tutti devono essere ✅ per un ingresso ora):**")
        for g in pb.gates:
            L.append(f"- {'✅' if g.passed else '❌'} **{g.name}** — {g.detail}")
        L.append("")
        L.append("**Trigger / cosa fare:**")
        for t in pb.triggers:
            L.append(f"- {t}")
        L.append(f"\n**Invalidazione:** {pb.invalidation}")
        L.append("")

    if r.scenarios:
        L.append("## Scenari")
        L.append("*Nessun verdetto unico: esiti alternativi con probabilità qualitativa.*")
        L.append("")
        for sc in r.scenarios:
            L.append(f"### {sc.title} — probabilità {sc.probability.value.upper()}")
            L.append(sc.narrative)
            if sc.key_levels:
                L.append(f"- Livelli chiave: {_levels(sc.key_levels)}")
            L.append(f"- Invalidazione: {sc.invalidation}")
            L.append("")

    L.append("## Limiti dell'analisi")
    for lim in r.limits:
        L.append(f"- {lim}")
    L.append("")
    L.append("---")
    L.append(f"**Disclaimer:** {r.disclaimer}")
    return "\n".join(L)


def _risk_markdown(plan: RiskPlan) -> list[str]:
    L = ["## Piano di rischio"]
    L.append(f"- **Lato:** {plan.side.value}  |  **Operabile:** {plan.viable}")
    if plan.side.value != "none":
        L.append(f"- **Entry:** {_fmt(plan.entry)}  (zona {plan.entry_zone})")
        L.append(f"- **Stop:** {_fmt(plan.stop)}  [{plan.stop_basis}]")
        L.append(f"- **Target:** {_fmt(plan.target)}  [{plan.target_basis}]")
        L.append(
            f"- **R:R:** {_fmt(plan.rr, 2)} (minimo rispettato: {plan.meets_min_rr})"
        )
        L.append(
            f"- **Size:** {_fmt(plan.position_size_units, 6)} unità "
            f"(controvalore ~{_fmt(plan.position_notional, 2)}); "
            f"rischio {_fmt(plan.risk_amount, 2)} su capitale {_fmt(plan.capital, 2)}"
        )
    L.append("")
    L.append("**Ragionamento:**")
    for line in plan.rationale:
        L.append(f"- {line}")
    if plan.warnings:
        L.append("")
        L.append("**Avvisi:**")
        for w in plan.warnings:
            L.append(f"- ⚠️ {w}")
    L.append("")
    return L


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
       max-width: 820px; margin: 24px auto; padding: 0 16px; color: #1a1a1a; line-height: 1.5; }
h1 { border-bottom: 2px solid #444; padding-bottom: 6px; }
h2 { margin-top: 28px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 14px; }
th { background: #f2f2f2; }
.meta { color: #555; font-size: 14px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 13px; font-weight: 600; }
.alta { background: #e6f4ea; color: #137333; }
.media { background: #fef7e0; color: #b06000; }
.bassa { background: #fce8e6; color: #a50e0e; }
.disclaimer { background: #fff8e1; border-left: 4px solid #f0ad4e; padding: 10px 14px;
              font-size: 13px; margin-top: 24px; }
.scenario { border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px 14px; margin: 10px 0; }
ul { margin: 6px 0; }
"""


def _e(text: object) -> str:
    return html.escape(str(text))


def _badge(level: str) -> str:
    return f'<span class="badge {level}">{level.upper()}</span>'


def to_html(report: MarketReport) -> str:
    r = report
    P: list[str] = []
    P.append("<!DOCTYPE html><html lang='it'><head><meta charset='utf-8'>")
    P.append(f"<title>Report {_e(r.symbol)}</title><style>{_CSS}</style></head><body>")
    P.append(
        f"<h1>Report di analisi — {_e(r.symbol)} "
        f"<span class='meta'>({_e(r.asset_class.value)}, {_e(r.interval.value)})</span></h1>"
    )
    if r.as_of:
        P.append(f"<p class='meta'>Dati aggiornati al {r.as_of:%Y-%m-%d %H:%M} UTC</p>")
    P.append("<ul>")
    P.append(f"<li><b>Prezzo corrente:</b> {_fmt(r.current_price)}</li>")
    P.append(
        f"<li><b>Confidenza:</b> {_badge(r.confidence.value)} — "
        f"{_e(r.confidence_rationale)}</li>"
    )
    P.append(
        f"<li><b>Qualità dati:</b> {r.data_quality.n_bars} barre, "
        f"sufficiente = {r.data_quality.sufficient}</li>"
    )
    P.append("</ul>")

    if not r.technical.computed:
        P.append("<h2>Analisi non calcolata</h2><ul>")
        for note in r.technical.notes:
            P.append(f"<li>{_e(note)}</li>")
        P.append("</ul>")
    else:
        P.append("<h2>Sintesi tecnica</h2>")
        P.append(f"<p>{_e(r.technical.trend_summary)}</p>")
        P.append("<h2>Segnali</h2>")
        P.append("<table><tr><th>Indicatore</th><th>Stato</th><th>Direzione</th>"
                 "<th>Valore</th></tr>")
        for s in r.technical.signals:
            P.append(
                f"<tr><td>{_e(s.name)}</td><td>{_e(s.state)}</td>"
                f"<td>{_e(s.direction.value)}</td><td>{_fmt(s.value)}</td></tr>"
            )
        P.append("</table><ul>")
        for s in r.technical.signals:
            P.append(f"<li><b>{_e(s.name)}</b> — {_e(s.rationale)}</li>")
        P.append("</ul>")
        if r.technical.support_resistance:
            sr = r.technical.support_resistance
            P.append("<h2>Supporti e resistenze</h2><ul>")
            P.append(f"<li><b>Supporti:</b> {_e(_levels(sr.supports))}</li>")
            P.append(f"<li><b>Resistenze:</b> {_e(_levels(sr.resistances))}</li></ul>")

    if r.risk_plan:
        P.append(_risk_html(r.risk_plan))

    if r.entry_playbook:
        pb = r.entry_playbook
        P.append("<h2>Piano d'ingresso</h2>")
        P.append(f"<p><b>Verdetto:</b> {_e(pb.verdict)} · lato {_e(pb.side.value)}</p><ul>")
        for g in pb.gates:
            mark = "✅" if g.passed else "❌"
            P.append(f"<li>{mark} <b>{_e(g.name)}</b> — {_e(g.detail)}</li>")
        P.append("</ul><b>Trigger / cosa fare:</b><ul>")
        for t in pb.triggers:
            P.append(f"<li>{_e(t)}</li>")
        P.append("</ul>")
        P.append(f"<p><b>Invalidazione:</b> {_e(pb.invalidation)}</p>")

    if r.scenarios:
        P.append("<h2>Scenari</h2>")
        P.append("<p class='meta'>Nessun verdetto unico: esiti alternativi con probabilità "
                 "qualitativa.</p>")
        for sc in r.scenarios:
            P.append("<div class='scenario'>")
            P.append(f"<h3>{_e(sc.title)} {_badge(sc.probability.value)}</h3>")
            P.append(f"<p>{_e(sc.narrative)}</p><ul>")
            if sc.key_levels:
                P.append(f"<li>Livelli chiave: {_e(_levels(sc.key_levels))}</li>")
            P.append(f"<li>Invalidazione: {_e(sc.invalidation)}</li></ul></div>")

    P.append("<h2>Limiti dell'analisi</h2><ul>")
    for lim in r.limits:
        P.append(f"<li>{_e(lim)}</li>")
    P.append("</ul>")
    P.append(f"<div class='disclaimer'><b>Disclaimer:</b> {_e(r.disclaimer)}</div>")
    P.append("</body></html>")
    return "".join(P)


def _risk_html(plan: RiskPlan) -> str:
    P = ["<h2>Piano di rischio</h2><ul>"]
    P.append(f"<li><b>Lato:</b> {_e(plan.side.value)} — <b>Operabile:</b> {plan.viable}</li>")
    if plan.side.value != "none":
        P.append(f"<li><b>Entry:</b> {_fmt(plan.entry)} (zona {_e(plan.entry_zone)})</li>")
        P.append(f"<li><b>Stop:</b> {_fmt(plan.stop)} [{_e(plan.stop_basis)}]</li>")
        P.append(f"<li><b>Target:</b> {_fmt(plan.target)} [{_e(plan.target_basis)}]</li>")
        P.append(
            f"<li><b>R:R:</b> {_fmt(plan.rr, 2)} "
            f"(minimo rispettato: {plan.meets_min_rr})</li>"
        )
        P.append(
            f"<li><b>Size:</b> {_fmt(plan.position_size_units, 6)} unità "
            f"(controvalore ~{_fmt(plan.position_notional, 2)}); "
            f"rischio {_fmt(plan.risk_amount, 2)}</li>"
        )
    P.append("</ul><b>Ragionamento:</b><ul>")
    for line in plan.rationale:
        P.append(f"<li>{_e(line)}</li>")
    P.append("</ul>")
    if plan.warnings:
        P.append("<b>Avvisi:</b><ul>")
        for w in plan.warnings:
            P.append(f"<li>{_e(w)}</li>")
        P.append("</ul>")
    return "".join(P)


# --------------------------------------------------------------------------- #
# PDF (fpdf2, font core -> sanitizzazione latin-1)
# --------------------------------------------------------------------------- #

_PDF_SUBST = {
    "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≠": "!=",
    "−": "-", "–": "-", "—": "-", "•": "-", "·": ".",
    "σ": "sigma", "±": "+/-", "×": "x", "…": "...",
    "’": "'", "‘": "'", "“": '"', "”": '"', "⚠️": "[!]", "⚠": "[!]",
}


def _s(text: object) -> str:
    out = str(text)
    for bad, good in _PDF_SUBST.items():
        out = out.replace(bad, good)
    return out.encode("latin-1", "replace").decode("latin-1")


def to_pdf(report: MarketReport) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    r = report
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def _cell(txt: str, height: float) -> None:
        # new_x=LMARGIN + new_y=NEXT: torna a sinistra e va a capo, così il
        # multi_cell successivo ha sempre l'intera larghezza disponibile.
        pdf.multi_cell(0, height, _s(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def title(txt: str) -> None:
        pdf.set_font("Helvetica", "B", 15)
        _cell(txt, 8)
        pdf.ln(1)

    def heading(txt: str) -> None:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        _cell(txt, 7)

    def para(txt: str, bullet: bool = False) -> None:
        pdf.set_font("Helvetica", "", 10)
        _cell(("- " if bullet else "") + txt, 5)

    title(f"Report di analisi — {r.symbol} ({r.asset_class.value}, {r.interval.value})")
    if r.as_of:
        pdf.set_font("Helvetica", "I", 9)
        _cell(f"Dati aggiornati al {r.as_of:%Y-%m-%d %H:%M} UTC", 5)
    para(f"Prezzo corrente: {_fmt(r.current_price)}", bullet=True)
    para(f"Confidenza: {r.confidence.value.upper()} — {r.confidence_rationale}", bullet=True)
    para(
        f"Qualità dati: {r.data_quality.n_bars} barre, sufficiente = {r.data_quality.sufficient}",
        bullet=True,
    )

    if not r.technical.computed:
        heading("Analisi non calcolata")
        for note in r.technical.notes:
            para(note, bullet=True)
    else:
        heading("Sintesi tecnica")
        para(r.technical.trend_summary)
        heading("Segnali")
        for s in r.technical.signals:
            para(f"{s.name} [{s.state}, {s.direction.value}] val={_fmt(s.value)}", bullet=True)
            para(f"   {s.rationale}")
        if r.technical.support_resistance:
            sr = r.technical.support_resistance
            heading("Supporti e resistenze")
            para(f"Supporti: {_levels(sr.supports)}", bullet=True)
            para(f"Resistenze: {_levels(sr.resistances)}", bullet=True)

    if r.risk_plan:
        heading("Piano di rischio")
        p = r.risk_plan
        para(f"Lato: {p.side.value} | Operabile: {p.viable}", bullet=True)
        if p.side.value != "none":
            para(f"Entry {_fmt(p.entry)} | Stop {_fmt(p.stop)} | Target {_fmt(p.target)} "
                 f"| R:R {_fmt(p.rr, 2)}", bullet=True)
            para(f"Size {_fmt(p.position_size_units, 6)} unità (~{_fmt(p.position_notional, 2)}), "
                 f"rischio {_fmt(p.risk_amount, 2)}", bullet=True)
        for line in p.rationale:
            para(line, bullet=True)
        for w in p.warnings:
            para(f"[!] {w}", bullet=True)

    if r.entry_playbook:
        pb = r.entry_playbook
        heading("Piano d'ingresso")
        para(f"Verdetto: {pb.verdict} | lato {pb.side.value}", bullet=True)
        for g in pb.gates:
            para(f"{'[OK]' if g.passed else '[NO]'} {g.name}: {g.detail}", bullet=True)
        para("Trigger / cosa fare:")
        for t in pb.triggers:
            para(t, bullet=True)
        para(f"Invalidazione: {pb.invalidation}")

    if r.scenarios:
        heading("Scenari (nessun verdetto unico)")
        for sc in r.scenarios:
            para(f"{sc.title} — probabilità {sc.probability.value.upper()}", bullet=True)
            para(f"   {sc.narrative}")
            if sc.key_levels:
                para(f"   Livelli chiave: {_levels(sc.key_levels)}")
            para(f"   Invalidazione: {sc.invalidation}")

    heading("Limiti dell'analisi")
    for lim in r.limits:
        para(lim, bullet=True)

    heading("Disclaimer")
    para(r.disclaimer)

    return bytes(pdf.output())
