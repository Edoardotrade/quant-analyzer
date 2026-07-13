"""Configurazione applicativa.

Le impostazioni sono lette da variabili d'ambiente e/o da un file ``.env``.
Le chiavi API NON sono mai hardcoded: se mancano, i provider che le richiedono
lo segnalano esplicitamente invece di fallire in modo opaco.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env della radice del progetto, risolto in modo assoluto: così le chiavi si
# trovano a prescindere dalla cartella da cui si avvia il processo.
_PROJECT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Impostazioni dell'applicazione.

    Gli ``alias`` corrispondono ai nomi delle variabili d'ambiente:
      - chiavi di terze parti col loro nome standard (es. ``ALPHA_VANTAGE_API_KEY``)
      - configurazione nostra col prefisso ``QA_`` per evitare collisioni.
    """

    model_config = SettingsConfigDict(
        env_file=(str(_PROJECT_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- Chiavi di terze parti ---
    alpha_vantage_api_key: str | None = Field(default=None, alias="ALPHA_VANTAGE_API_KEY")
    twelvedata_api_key: str | None = Field(default=None, alias="TWELVEDATA_API_KEY")

    # --- Notifiche Telegram ---
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")

    @property
    def telegram_ready(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    # --- Configurazione applicativa ---
    # Kraken: raggiungibile anche dai server cloud/USA (Binance li blocca).
    ccxt_exchange: str = Field(default="kraken", alias="QA_CCXT_EXCHANGE")
    cache_dir: Path = Field(default=Path(".cache"), alias="QA_CACHE_DIR")
    cache_ttl_minutes: int = Field(default=60, alias="QA_CACHE_TTL_MINUTES", ge=0)
    request_timeout_seconds: float = Field(default=15.0, alias="QA_REQUEST_TIMEOUT", gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Restituisce le impostazioni (con cache di processo)."""
    return Settings()
