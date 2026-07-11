"""Test dello stato di apertura dei mercati."""

from __future__ import annotations

from datetime import datetime, timezone

from quantanalyzer.analysis.market_hours import market_status
from quantanalyzer.models import AssetClass

UTC = timezone.utc
SABATO = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)  # sabato
MERCOLEDI = datetime(2026, 7, 8, 15, 0, tzinfo=UTC)  # mercoledì


def test_crypto_sempre_aperto():
    assert market_status(AssetClass.CRYPTO, SABATO)[0] is True
    assert market_status(AssetClass.CRYPTO, MERCOLEDI)[0] is True


def test_forex_chiuso_weekend_aperto_feriale():
    assert market_status(AssetClass.FOREX, SABATO)[0] is False
    assert market_status(AssetClass.FOREX, MERCOLEDI)[0] is True


def test_indici_chiusi_weekend():
    aperto_sab, nota = market_status(AssetClass.INDEX, SABATO)
    assert aperto_sab is False
    assert "weekend" in nota.lower()
    assert market_status(AssetClass.INDEX, MERCOLEDI)[0] is True


def test_nota_sempre_presente():
    for ac in AssetClass:
        _, nota = market_status(ac, SABATO)
        assert nota
