"""Un solo giro di controllo (per scheduler esterni: GitHub Actions / cron).

Legge le chiavi Telegram dalle variabili d'ambiente (TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID). Invia un avviso solo per i mercati appena passati a ENTRA;
lo stato in .cache/monitor_state.json (persistito dallo scheduler) evita i doppioni.
"""

from quantanalyzer.alerts.monitor import run_once
from quantanalyzer.watchlist import DEFAULT_PARAMS, DEFAULT_WATCHLIST

if __name__ == "__main__":
    signals, fired = run_once(DEFAULT_WATCHLIST, DEFAULT_PARAMS)
    for s in signals:
        print(f"{s.symbol:10} -> {s.action.value.upper()}")
    print("Avvisi inviati:", ", ".join(fired) if fired else "nessuno")
