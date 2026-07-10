"""Dashboard Quant Analyzer — un'unica app chiara.

Ti dice, per ogni mercato che segui, COSA fare (COMPRA/VENDI/ASPETTA), DOVE entrare
e con quali Stop Loss e Take Profit — e manda l'avviso su Telegram quando è ora.

Avvio:  streamlit run src/quantanalyzer/dashboard/app.py
"""

from __future__ import annotations

import altair as alt
import streamlit as st

from quantanalyzer import DISCLAIMER, __version__
from quantanalyzer.alerts.telegram import TelegramNotConfigured, send_telegram_message
from quantanalyzer.analysis.signal import build_operating_signal
from quantanalyzer.config import get_settings
from quantanalyzer.dashboard.charts import indicators_frame
from quantanalyzer.data.base import DataError
from quantanalyzer.data.service import MarketDataService
from quantanalyzer.models import AssetClass, Interval, RiskParams, SignalAction
from quantanalyzer.report.builder import build_report
from quantanalyzer.report.render import to_html, to_markdown, to_pdf

st.set_page_config(page_title="Quant Analyzer", page_icon="📊", layout="wide")


@st.cache_resource
def _service() -> MarketDataService:
    return MarketDataService()


@st.cache_data(show_spinner="Scarico i dati…")
def _load(symbol: str, asset_class: str, interval: str, lookback: int, _nonce: int):
    return _service().get_prices(
        symbol, AssetClass(asset_class), Interval(interval), lookback=lookback, use_cache=False
    )


def _parse_watchlist(text: str) -> list[tuple[str, AssetClass]]:
    items: list[tuple[str, AssetClass]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        symbol = parts[0].upper()
        cls = parts[1].lower() if len(parts) > 1 else "equity"
        try:
            items.append((symbol, AssetClass(cls)))
        except ValueError:
            st.sidebar.warning(f"Classe non valida in «{line}» (equity/etf/index/forex/crypto).")
    return items


def _detail(series, params: RiskParams) -> None:
    """Grafico + download report, dentro un expander (dettagli, non in primo piano)."""
    frame = indicators_frame(series)
    cols = ["close"] + [c for c in frame.columns if c.startswith("SMA")]
    long = (
        frame[cols].reset_index().melt("timestamp", var_name="serie", value_name="v").dropna()
    )
    chart = (
        alt.Chart(long)
        .mark_line()
        .encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("v:Q", scale=alt.Scale(zero=False)),
            color=alt.Color("serie:N", title=None),
        )
        .properties(height=280)
    )
    st.altair_chart(chart, width="stretch")

    report = build_report(series, params)
    safe = series.symbol.replace("/", "_")
    d1, d2, d3 = st.columns(3)
    d1.download_button("📄 Report MD", to_markdown(report), file_name=f"{safe}.md", width="stretch")
    d2.download_button(
        "🌐 Report HTML", to_html(report), file_name=f"{safe}.html",
        mime="text/html", width="stretch",
    )
    d3.download_button(
        "📑 Report PDF", to_pdf(report), file_name=f"{safe}.pdf",
        mime="application/pdf", width="stretch",
    )


# --------------------------------------------------------------------------- #
# Barra laterale
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("📊 Quant Analyzer")
    st.caption(f"v{__version__} · ti dice QUANDO e DOVE entrare")

    st.subheader("I miei mercati")
    watch_text = st.text_area(
        "Uno per riga:  SIMBOLO  CLASSE",
        value=(
            "XAUUSD forex\n"
            "EURUSD forex\n"
            "GBPUSD forex\n"
            "USDJPY forex\n"
            "AUDUSD forex\n"
            "^GSPC index\n"
            "^IXIC index\n"
            "BTC/USDT crypto\n"
            "ETH/USDT crypto"
        ),
        height=220,
        help="Es:  AAPL equity · BTC/USDT crypto · EURUSD forex · ^GSPC index",
    )

    st.subheader("Rischio")
    capital = st.number_input("Capitale (€)", min_value=100.0, value=10_000.0, step=500.0)
    risk_pct = st.slider("Rischio per operazione (%)", 0.1, 5.0, 1.0, 0.1)
    min_rr = st.slider("Guadagno minimo vs rischio (R:R)", 1.0, 5.0, 2.0, 0.5)
    atr_mult = st.slider("Ampiezza stop (× ATR)", 0.5, 4.0, 1.5, 0.5)
    interval = st.selectbox(
        "Orizzonte", [i.value for i in Interval], index=[i.value for i in Interval].index("1d")
    )
    lookback = st.slider("Storico (barre)", 60, 2000, 300, 20)

    if st.button("🔄 Aggiorna adesso", width="stretch"):
        st.cache_data.clear()

items = _parse_watchlist(watch_text)
params = RiskParams(capital=capital, risk_pct=risk_pct, min_rr=min_rr, atr_stop_mult=atr_mult)
settings = get_settings()

# --------------------------------------------------------------------------- #
# Segnali operativi (in primo piano)
# --------------------------------------------------------------------------- #
st.title("🔔 I miei segnali operativi")
st.caption("🟢 Verde = si può entrare (prezzo · stop · target).  ⏳ Grigio = aspetta.")

if not items:
    st.info("Aggiungi almeno un mercato nella barra a sinistra.")
    st.stop()

for symbol, asset_class in items:
    with st.container(border=True):
        try:
            series = _load(symbol, asset_class.value, interval, lookback, 0)
        except DataError as exc:
            st.error(f"❌ {symbol}: dati non disponibili — {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            st.error(f"❌ {symbol}: errore — {exc}")
            continue

        sig = build_operating_signal(series, params)

        if sig.action == SignalAction.ENTER:
            st.success(f"**{sig.headline}**")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Operazione", "COMPRA" if sig.side.value == "long" else "VENDI")
            m2.metric("Ingresso", sig.entry)
            m3.metric("🛑 Stop Loss", sig.stop_loss)
            m4.metric("🎯 Take Profit", sig.take_profit)
            m5.metric("Quantità", sig.size_units)
            st.caption(sig.reason)
        elif sig.action == SignalAction.WAIT:
            st.warning(f"**{sig.headline}**")
            st.write(sig.reason)
        else:
            st.error(f"**{sig.headline}**")
            st.write(sig.reason)

        if series.end:
            st.caption(
                f"Prezzo ora: {sig.price} · aggiornato al {series.end:%Y-%m-%d} · "
                f"fonte {series.source}"
            )
        with st.expander("Vedi grafico e scarica il report (dettagli)"):
            _detail(series, params)

# --------------------------------------------------------------------------- #
# Avvisi Telegram
# --------------------------------------------------------------------------- #
st.divider()
st.subheader("🔔 Avvisi su Telegram")
if settings.telegram_ready:
    st.success("Telegram configurato ✅ — riceverai un avviso quando un mercato diventa 🟢.")
    if st.button("Invia un avviso di prova"):
        try:
            ok = send_telegram_message("✅ Quant Analyzer: avviso di prova. Funziona!")
            if ok:
                st.success("Inviato! Controlla Telegram. 📲")
            else:
                st.error("Invio fallito: verifica token e chat id.")
        except TelegramNotConfigured as exc:
            st.error(str(exc))
else:
    st.info(
        "Telegram non ancora configurato. Metti TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nel file "
        ".env (istruzioni nel README / .env.example), poi riavvia l'app."
    )

# --------------------------------------------------------------------------- #
# Avanzato: Swagger dentro l'app
# --------------------------------------------------------------------------- #
with st.expander("⚙️ Strumenti avanzati — API / Swagger"):
    st.caption("Documentazione interattiva dell'API (server API attivo sulla porta 8000).")
    st.iframe("http://localhost:8000/docs", height=600, scrolling=True)

st.caption(f"⚠️ {DISCLAIMER}")
