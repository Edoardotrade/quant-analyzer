# Deploy degli avvisi 24/7 (gratis, con GitHub Actions)

Obiettivo: far girare il controllo dei mercati **sui server di GitHub ogni ~15 minuti**,
gratis e **indipendente dal tuo PC**. Gli avvisi arrivano su Telegram.

> ⚠️ Le chiavi (token bot e chat id) **non stanno mai nel codice**: si mettono nei
> *Secrets* del repository GitHub. Il file `.env` è escluso da git e non viene caricato.

## Passi (una volta sola, ~5 minuti)

### 1. Crea un repository su GitHub
- Vai su https://github.com/new
- Nome: es. `quant-analyzer` · visibilità: **Private** · **non** aggiungere README/gitignore
- Crea il repo e copia l'URL (es. `https://github.com/TUONOME/quant-analyzer.git`)

### 2. Carica il codice (dal PC, nella cartella del progetto)
```powershell
cd C:\Users\CPrando\.claude\quant-analyzer
git remote add origin https://github.com/TUONOME/quant-analyzer.git
git push -u origin main
```
(Se Git chiede l'accesso, accedi con l'account GitHub / token.)

### 3. Aggiungi i due Secrets
Sul repo GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
Crea questi due (i valori sono quelli del tuo file `.env` locale):

| Nome del secret | Valore |
|---|---|
| `TELEGRAM_BOT_TOKEN` | il token del tuo bot |
| `TELEGRAM_CHAT_ID`   | il tuo chat id |

### 4. Attiva / prova
- Scheda **Actions** → se chiede di abilitare i workflow, conferma.
- Apri **“Quant Monitor (avvisi Telegram)”** → **Run workflow** per un test immediato.
- Da lì gira **da solo ogni ~15 minuti**. Ti arriva un messaggio Telegram **solo** quando un
  mercato passa a 🟢 ENTRA (con prezzo, Stop Loss, Take Profit).

## Note
- GitHub può ritardare l'orario del cron di qualche minuto sotto carico: normale.
- I workflow *schedulati* vengono messi in pausa dopo **60 giorni senza attività** sul repo:
  se non tocchi il repo per due mesi, fai un piccolo commit o un “Run workflow” per riattivarlo.
- La watchlist e i parametri si cambiano in `src/quantanalyzer/watchlist.py` (poi `git push`).
- Puoi anche continuare a usare la **dashboard** in locale (`streamlit run …`) quando vuoi
  guardare i grafici; gli avvisi però arrivano dal cloud, quindi il PC può stare spento.
