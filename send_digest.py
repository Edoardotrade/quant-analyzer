"""Invia il riepilogo giornaliero della watchlist su Telegram (per scheduler).

Legge le chiavi Telegram dalle variabili d'ambiente. Da usare una volta al giorno.
"""

import sys
from pathlib import Path

from quantanalyzer.alerts.monitor import build_digest, check_watchlist
from quantanalyzer.alerts.paper import format_paper_report
from quantanalyzer.alerts.telegram import send_telegram_message
from quantanalyzer.config import get_settings
from quantanalyzer.watchlist import DEFAULT_PARAMS, DEFAULT_WATCHLIST

if __name__ == "__main__":
    if not get_settings().telegram_ready:
        print(
            "ERRORE: Telegram non configurato. Servono i Repository secrets "
            "TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.",
            flush=True,
        )
        sys.exit(1)

    signals = check_watchlist(DEFAULT_WATCHLIST, DEFAULT_PARAMS)
    message = build_digest(signals)

    # aggiunge il track record del paper-trading, se il registro esiste
    try:
        import json

        ledger = json.loads(Path(".cache/paper_ledger.json").read_text(encoding="utf-8"))
        message += "\n\n" + format_paper_report(ledger)
    except Exception:  # noqa: BLE001 — registro assente: si invia comunque il riepilogo
        pass

    send_telegram_message(message)
    print("Riepilogo inviato.", flush=True)
