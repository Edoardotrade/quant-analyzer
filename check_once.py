"""Un solo giro di controllo (per scheduler esterni: GitHub Actions / cron).

Legge le chiavi Telegram dalle variabili d'ambiente (TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID). Invia un avviso solo per i mercati appena passati a ENTRA;
lo stato in .cache/monitor_state.json (persistito dallo scheduler) evita i doppioni.
"""

import os

from quantanalyzer.alerts.monitor import run_once
from quantanalyzer.alerts.telegram import send_telegram_message
from quantanalyzer.watchlist import DEFAULT_PARAMS, DEFAULT_WATCHLIST

if __name__ == "__main__":
    # Heartbeat: solo all'avvio manuale (workflow_dispatch) manda una conferma su Telegram.
    if os.environ.get("MONITOR_HEARTBEAT"):
        try:
            send_telegram_message(
                "✅ Monitor attivo dal cloud (GitHub Actions). "
                "Ti avviserò qui quando un mercato diventa ENTRA (prezzo · SL · TP)."
            )
            print("heartbeat inviato")
        except Exception as exc:  # noqa: BLE001
            print("heartbeat fallito:", exc)

    signals, fired = run_once(DEFAULT_WATCHLIST, DEFAULT_PARAMS)
    for s in signals:
        print(f"{s.symbol:10} -> {s.action.value.upper()}")
    print("Avvisi inviati:", ", ".join(fired) if fired else "nessuno")
