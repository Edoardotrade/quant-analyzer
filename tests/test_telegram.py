"""Test dell'invio Telegram (con client HTTP finto, nessuna rete)."""

from __future__ import annotations

import pytest

from quantanalyzer.alerts import telegram as tg


class _Resp:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _Client:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.calls: list[tuple[str, dict]] = []

    def post(self, url, json):
        self.calls.append((url, json))
        return _Resp(self.status_code)


def test_send_ok():
    client = _Client(200)
    ok = tg.send_telegram_message("ciao", token="T", chat_id="C", client=client)
    assert ok is True
    url, payload = client.calls[0]
    assert "botT/sendMessage" in url
    assert payload["chat_id"] == "C"
    assert payload["text"] == "ciao"


def test_send_failure_returns_false():
    client = _Client(500)
    assert tg.send_telegram_message("x", token="T", chat_id="C", client=client) is False


def test_missing_config_raises(monkeypatch):
    class _S:
        telegram_bot_token = None
        telegram_chat_id = None

    monkeypatch.setattr(tg, "get_settings", lambda: _S())
    with pytest.raises(tg.TelegramNotConfigured):
        tg.send_telegram_message("x")
