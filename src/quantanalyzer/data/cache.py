"""Cache locale su file delle serie di prezzo.

Obiettivi:
  - ridurre le chiamate alle fonti (rate limit di yfinance / Alpha Vantage);
  - poter ripiegare su dati "stale" se la fonte è momentaneamente irraggiungibile;
  - rendere trasparente *quanto sono vecchi* i dati usati (campo fetched_at).

Formato: un file JSON per chiave (serializzazione del modello PriceSeries).
Niente dipendenze extra (evitiamo parquet/pyarrow in questa fase).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..models import AssetClass, Interval, PriceSeries

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def make_key(
    source: str, symbol: str, asset_class: AssetClass, interval: Interval
) -> str:
    """Chiave di cache stabile e leggibile."""
    return f"{source}__{symbol}__{asset_class.value}__{interval.value}"


class FileCache:
    """Cache su filesystem con TTL configurabile."""

    def __init__(
        self,
        cache_dir: Path | str,
        ttl_minutes: int = 60,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.dir = Path(cache_dir)
        self.ttl = timedelta(minutes=max(0, ttl_minutes))
        # ``now`` iniettabile per rendere i test deterministici.
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _path(self, key: str) -> Path:
        safe = _SAFE.sub("_", key)
        return self.dir / f"{safe}.json"

    def load(self, key: str) -> PriceSeries | None:
        """Carica una serie dalla cache, o None se assente/corrotta."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return PriceSeries.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            # Un file corrotto non deve far cadere l'applicazione.
            return None

    def is_fresh(self, series: PriceSeries) -> bool:
        """True se la serie è entro il TTL rispetto a ``now``."""
        age = self._now() - series.fetched_at
        return age <= self.ttl

    def store(self, key: str, series: PriceSeries) -> Path:
        """Salva una serie in cache e restituisce il percorso del file."""
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        path.write_text(series.model_dump_json(indent=2), encoding="utf-8")
        return path
