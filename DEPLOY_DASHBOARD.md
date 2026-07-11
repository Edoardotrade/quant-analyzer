# Dashboard online (link apribile dal telefono) — gratis con Streamlit Cloud

Obiettivo: avere la dashboard come **URL pubblico** (es. `https://...streamlit.app`),
così la apri dal telefono senza far girare niente sul PC.

## Passi (una volta sola, ~3 minuti)
1. Vai su **https://share.streamlit.io** e accedi con **GitHub** (lo stesso account del repo).
2. Clicca **“Create app”** → **“Deploy a public app from GitHub”**.
3. Compila:
   - **Repository:** `Edoardotrade/quant-analyzer`
   - **Branch:** `main`
   - **Main file path:** `src/quantanalyzer/dashboard/app.py`
4. Clicca **“Deploy”** e aspetta un paio di minuti (installa tutto da solo).
5. Ottieni un link tipo `https://quant-analyzer-xxxx.streamlit.app` → **salvalo tra i preferiti del telefono**.

## Note
- La dashboard mostra grafici e segnali; **gli avvisi Telegram continuano ad arrivare dal monitor**
  su GitHub Actions, indipendentemente dalla dashboard.
- La sezione “API / Swagger” dentro la dashboard non funziona online (richiede il server API locale):
  ignorala, tutto il resto va.
- Se vuoi rendere l'app privata o cambiare la watchlist di default, si fa dal repo (poi si
  ri-deploya da solo ad ogni push).
