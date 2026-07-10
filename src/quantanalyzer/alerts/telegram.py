"""Invio di messaggi via Telegram Bot API.

Le credenziali (token del bot e chat id) vivono solo in variabili d'ambiente
(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID), mai nel codice.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import get_settings


class TelegramNotConfigured(RuntimeError):
    """Token o chat id mancanti."""


def send_telegram_message(
    text: str,
    *,
    token: str | None = None,
    chat_id: str | None = None,
    client: Any | None = None,
    timeout: float = 10.0,
) -> bool:
    """Invia un messaggio Telegram. ``client`` iniettabile per i test.

    Restituisce True se l'invio è andato a buon fine (HTTP 200).
    """
    settings = get_settings()
    token = token or settings.telegram_bot_token
    chat_id = chat_id or settings.telegram_chat_id
    if not token or not chat_id:
        raise TelegramNotConfigured(
            "Telegram non configurato: imposta TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nel file .env"
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if client is not None:
        response = client.post(url, json=payload)
        return bool(getattr(response, "status_code", 0) == 200)

    with httpx.Client(timeout=timeout) as http:
        response = http.post(url, json=payload)
        return response.status_code == 200
