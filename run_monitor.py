"""Sorvegliante continuo: controlla la watchlist e invia avvisi Telegram.

Avvio:  python run_monitor.py
Le chiavi Telegram vengono lette dal file .env (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).
Watchlist e parametri: vedi src/quantanalyzer/watchlist.py
"""

from quantanalyzer.alerts.monitor import run_forever
from quantanalyzer.watchlist import DEFAULT_PARAMS, DEFAULT_WATCHLIST

if __name__ == "__main__":
    run_forever(DEFAULT_WATCHLIST, DEFAULT_PARAMS, interval_minutes=15)
