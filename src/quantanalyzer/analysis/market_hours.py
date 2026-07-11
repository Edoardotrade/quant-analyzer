"""Stato di apertura dei mercati (semplificato, a livello di giornata).

Le crypto sono sempre aperte; forex e mercati azionari chiudono nel weekend.
Serve solo a ETICHETTARE i segnali (aperto/chiuso), non a bloccarli: le notifiche
arrivano comunque, così un segnale di venerdì lo si valuta all'apertura di lunedì.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import AssetClass


def market_status(asset_class: AssetClass, now: datetime | None = None) -> tuple[bool, str]:
    """Restituisce (aperto, nota) per la classe di asset all'istante ``now`` (UTC)."""
    now = now or datetime.now(timezone.utc)
    weekend = now.weekday() >= 5  # 5=sabato, 6=domenica

    if asset_class == AssetClass.CRYPTO:
        return True, "crypto: aperto 24/7"

    if asset_class == AssetClass.FOREX:
        if weekend:
            return False, "forex chiuso nel weekend (riapre domenica sera)"
        return True, "forex aperto"

    # index / equity / etf (mercati azionari)
    if weekend:
        return False, "mercato azionario chiuso nel weekend (riapre lunedì)"
    return True, "mercato azionario: giorno feriale (sessione USA ~15:30–22:00 ora italiana)"
