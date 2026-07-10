# Quant Analyzer

Motore di **analisi quantitativa dei mercati** (azioni, ETF, forex, crypto, indici) che produce
report strutturati per **supportare — non sostituire —** le decisioni dell'utente.

> ⚠️ **Disclaimer**: strumento a solo scopo informativo/educativo. **Non è consulenza finanziaria.**
> I risultati passati non garantiscono quelli futuri. Ogni decisione e il relativo rischio restano
> a carico dell'utente.

## Filosofia di progetto

- **Ragionamento visibile**, mai solo la conclusione.
- **Probabilità e gestione del rischio**, mai certezze.
- Se i dati sono insufficienti o il segnale è debole, **lo si dichiara** invece di forzare una raccomandazione.
- **API key solo da variabili d'ambiente** (`.env`), mai hardcoded.

## Architettura (a livelli disaccoppiati)

```
src/quantanalyzer/
├─ __init__.py        # versione + disclaimer condiviso
├─ config.py          # impostazioni + API key da env (.env)
├─ models.py          # modelli validati: OHLCVBar, PriceSeries, DataQuality
├─ data/              # LAYER DATI
│  ├─ base.py         #   contratto MarketDataProvider + eccezioni
│  ├─ yfinance_provider.py   #  equity/ETF/indici/forex
│  ├─ ccxt_provider.py       #  crypto
│  ├─ cache.py        #   cache su file con TTL (+ fail-soft)
│  ├─ quality.py      #   giudizio di qualità dei dati
│  └─ service.py      #   orchestratore: provider giusto + cache + fallback
├─ indicators/        # INDICATORI (in casa, testati)
│  ├─ trend.py        #   SMA, EMA, pendenza
│  ├─ momentum.py     #   RSI (Wilder), MACD
│  ├─ volatility.py   #   True Range, ATR (Wilder), Bollinger
│  ├─ levels.py       #   supporti/resistenze da swing highs/lows
│  └─ volume.py       #   volume medio, volume relativo, OBV
├─ analysis/          # INTERPRETAZIONE
│  ├─ technical.py    #   indicatori -> Signal spiegati + sintesi + gate dati
│  └─ entry.py        #   piano d'ingresso: 4 cancelli + trigger + invalidazione
├─ risk/              # RISK MANAGEMENT
│  └─ planner.py      #   entry, stop (ATR/livello), target, R:R, position sizing
├─ report/            # REPORT
│  ├─ scenarios.py    #   scenari bull/bear/range + probabilità + confidenza
│  ├─ builder.py      #   assembla il MarketReport
│  └─ render.py       #   Markdown / HTML / PDF
├─ backtest/          # BACKTESTING
│  └─ engine.py       #   simulazione senza lookahead + metriche + buy&hold
├─ dashboard/         # UI STREAMLIT
│  ├─ charts.py       #   prezzo + indicatori per i grafici (puro, testabile)
│  └─ app.py          #   dashboard interattiva (streamlit run)
└─ api/
   └─ app.py          # FastAPI: health, price, analysis/*, report(.md/.html/.pdf), backtest
```

Tutte le fasi pianificate (dati → indicatori → rischio → report) sono complete, più
un'estensione di **backtesting** per validare le strategie sullo storico.

## Prerequisiti

Su questa macchina **Python non risulta installato**. Installalo prima di procedere:

```powershell
# Opzione consigliata (Windows):
winget install Python.Python.3.12
# poi chiudi e riapri il terminale
python --version
```

## Setup

```powershell
cd C:\Users\CPrando\.claude\quant-analyzer

# 1) Ambiente virtuale
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Installa il pacchetto in modalità editabile + strumenti di sviluppo
python -m pip install --upgrade pip
pip install -e ".[dev]"

# 3) Configura le variabili d'ambiente
copy .env.example .env
# (apri .env e, se vuoi il backup Alpha Vantage, incolla la tua chiave)
```

## Test

```powershell
pytest
```

I test **non toccano la rete**: usano provider finti e la cache in cartella temporanea.

## Dashboard interattiva (Streamlit) — l'app principale

Un'unica schermata **orientata all'azione**: per ogni mercato della tua watchlist ti dice
🟢 **ENTRA** (con *Ingresso · Stop Loss · Take Profit · Quantità*) oppure ⏳ **ASPETTA**
(con il motivo in una riga e il trigger da attendere). Il dettaglio tecnico (grafico, RSI,
scenari, report) è nascosto sotto un expander. Lo **Swagger dell'API** è incorporato in fondo.

```powershell
pip install -e ".[ui]"     # installa Streamlit (una volta sola)
streamlit run src/quantanalyzer/dashboard/app.py
# apre http://localhost:8501
```

### 🔔 Avvisi Telegram (quando entrare)
1. Su Telegram scrivi a **@BotFather** → `/newbot` → ottieni il **TOKEN**.
2. Scrivi un messaggio al tuo nuovo bot, poi apri
   `https://api.telegram.org/bot<TOKEN>/getUpdates` e copia il `chat.id`
   (oppure scrivi a **@userinfobot**).
3. Metti nel file `.env`:
   ```
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ```
4. Nella dashboard usa **“Invia un avviso di prova”** per verificare.
5. Avvia il **sorvegliante** che controlla la watchlist e ti avvisa quando un mercato diventa 🟢:
   ```powershell
   python run_monitor.py
   ```
   La watchlist e i parametri sono in `run_monitor.py` (modificabili). Controlla ogni 15 minuti
   e invia un avviso Telegram (prezzo · SL · TP) solo quando un mercato *passa* a ENTRA.

## Avvio dell'API

```powershell
# opzione A: entrypoint installato
quantanalyzer-api

# opzione B: uvicorn diretto
uvicorn quantanalyzer.api.app:app --reload
```

Poi apri http://127.0.0.1:8000/docs per la documentazione interattiva.

### Esempi di chiamata

```
GET /health
GET /price?symbol=AAPL&asset_class=equity&interval=1d&lookback=250
GET /price?symbol=BTC/USDT&asset_class=crypto&interval=1d&lookback=200
GET /price?symbol=EURUSD&asset_class=forex&interval=1d&lookback=250

# Analisi tecnica (Fase 2)
GET /analysis/technical?symbol=AAPL&asset_class=equity&interval=1d&lookback=300
GET /analysis/technical?symbol=BTC/USDT&asset_class=crypto&lookback=300

# Piano di rischio (Fase 3) — capital è obbligatorio
GET /analysis/risk-plan?symbol=AAPL&asset_class=equity&capital=10000&risk_pct=1&min_rr=2

# Report completo (Fase 4) — capital è opzionale (se presente include il piano di rischio)
GET /report?symbol=AAPL&asset_class=equity&capital=10000        # JSON (+ markdown)
GET /report.md?symbol=AAPL&asset_class=equity&capital=10000     # text/markdown
GET /report.html?symbol=AAPL&asset_class=equity&capital=10000   # HTML
GET /report.pdf?symbol=AAPL&asset_class=equity&capital=10000    # PDF scaricabile
```

`/report` unisce dati + analisi tecnica + piano di rischio in un report che **impone** i
principi non negoziabili: **2-3 scenari** (rialzista/ribassista/laterale) con probabilità
qualitative e condizione di invalidazione, **livello di confidenza** con motivazione, **limiti**
espliciti e **disclaimer**. Disponibile in JSON, Markdown, HTML e PDF.

```
# Backtest di una strategia baseline (incrocio SMA + stop ATR + target R:R)
GET /backtest?symbol=AAPL&asset_class=equity&capital=10000&sma_fast=20&sma_slow=50

# Piano d'ingresso — "quando entrare" in modo disciplinato (capital obbligatorio)
GET /analysis/entry?symbol=EURUSD&asset_class=forex&capital=10000&min_rr=2
```

`/analysis/entry` risponde alla domanda «quando entrare?» **senza mai dire "compra adesso"**:
valuta 4 **cancelli** (direzione · momentum non in eccesso · R:R ≥ minimo · rischio
dimensionabile). Se anche uno solo è chiuso → verdetto **attendere**, con i **trigger** espliciti
(rottura / pullback) e la condizione di **invalidazione**. È incluso anche nel `/report`.

> 🥇 **Metalli/commodity:** lo spot (es. `XAUUSD`) non è sul feed gratuito di Yahoo. Con
> `asset_class=forex` i simboli `XAUUSD`/`XAGUSD`/`WTIUSD` sono mappati automaticamente sui
> future `GC=F`/`SI=F`/`CL=F` (proxy che tracciano lo spot da vicino).

`/backtest` valida una **strategia baseline** (incrocio di medie, stop su ATR, target a R:R)
sullo storico, **senza lookahead**, e riporta win rate, R medio, profit factor, rendimento,
**max drawdown** e confronto con **buy&hold**. Serve a smontare la falsa fiducia: se una
strategia non regge sul passato, è meglio saperlo. Non è (ancora) l'analisi multi-segnale
completa, ed è indicativo — non una garanzia di rendimenti futuri.

`/analysis/risk-plan` calcola, con logica esplicita: lato (long/short dal trend), zona di
**entry**, **stop** (il più prudente tra ATR e livello tecnico), **target** (livello tecnico o
proiezione), **R:R** e **dimensione posizione** = (capitale × rischio%) / rischio-per-unità.
Se il R:R non raggiunge il minimo o il trend è incerto, `viable=false`: lo strumento **rifiuta
di forzare un trade** invece di inventare numeri.

Ogni risposta di `/price` include: la serie di prezzi, un **giudizio di qualità dei dati**
(`data_quality.sufficient`, con eventuali warning) e il **disclaimer**.

`/analysis/technical` restituisce, per ogni asset: i **segnali** (trend/RSI/MACD/ATR/Bollinger/
volume) ognuno con `state`, `direction` e un `rationale` che spiega cosa indica; i **supporti/
resistenze**; una **sintesi** del bilancio dei segnali; il `data_quality`; il disclaimer. Se i
dati sono insufficienti, `computed=false` e l'analisi **non** produce segnali (vedi `notes`).

> ⚠️ **Limite noto:** la sintesi di `/analysis/technical` pesa i segnali in modo uniforme. Un
> asset in downtrend strutturale ma con momentum in recupero può risultare "prevalentemente
> rialzista" perché i segnali di momentum superano di numero quello di trend. Per questo il
> **report** (`/report`) affianca alla sintesi degli **scenari espliciti** (rialzista/ribassista/
> laterale) con probabilità qualitative: è quella la vista d'insieme da preferire.

## Note di rischio sulle fonti dati

- **yfinance** interroga in modo *non ufficiale* Yahoo Finance: può cambiare formato, rate-limitare
  o restituire buchi senza preavviso. La cache con fail-soft mitiga le interruzioni temporanee.
- **Alpha Vantage** (backup) ha un free tier molto limitato (~25 richieste/giorno).
- **ccxt** usa dati di mercato pubblici degli exchange (nessuna API key per l'OHLCV).

Il campo `fetched_at` di ogni serie dice **quanto sono vecchi** i dati che stai guardando.
