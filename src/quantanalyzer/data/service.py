"""Servizio orchestratore per il recupero dei dati di mercato.

Responsabilità:
  - scegliere il provider giusto in base alla classe di asset;
  - usare la cache (ridurre chiamate, rispettare i rate limit);
  - se la fonte è irraggiungibile ma esistono dati in cache, ripiegare su di essi
    (fail-soft) segnalandolo, invece di lasciare l'utente senza nulla.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..config import Settings, get_settings
from ..models import AssetClass, Interval, PriceSeries
from .base import DataFetchError, DataUnavailableError, MarketDataProvider
from .cache import FileCache, make_key
from .ccxt_provider import CCXTProvider
from .yfinance_provider import YFinanceProvider


class MarketDataService:
    """Punto d'ingresso unico per ottenere serie di prezzo."""

    def __init__(
        self,
        providers: Sequence[MarketDataProvider] | None = None,
        cache: FileCache | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cache = cache or FileCache(
            self.settings.cache_dir, self.settings.cache_ttl_minutes
        )
        self.providers: list[MarketDataProvider] = list(
            providers
            if providers is not None
            else [
                YFinanceProvider(),
                CCXTProvider(exchange_id=self.settings.ccxt_exchange),
            ]
        )

    def provider_for(self, asset_class: AssetClass) -> MarketDataProvider:
        for provider in self.providers:
            if provider.supports(asset_class):
                return provider
        raise DataUnavailableError(
            f"Nessun provider configurato per la classe di asset '{asset_class.value}'."
        )

    def get_prices(
        self,
        symbol: str,
        asset_class: AssetClass,
        interval: Interval = Interval.D1,
        *,
        lookback: int = 250,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> PriceSeries:
        """Restituisce una PriceSeries applicando cache e fail-soft.

        Ordine di preferenza:
          1. cache fresca (se ``use_cache`` e non ``force_refresh``);
          2. fetch dal provider;
          3. cache stantia come ripiego se il fetch fallisce.
        """
        provider = self.provider_for(asset_class)
        key = make_key(provider.name, symbol, asset_class, interval)

        cached = self.cache.load(key) if use_cache else None
        if cached is not None and not force_refresh and self.cache.is_fresh(cached):
            return cached

        try:
            series = provider.fetch(
                symbol, asset_class=asset_class, interval=interval, lookback=lookback
            )
        except (DataFetchError, DataUnavailableError):
            # Fail-soft: se abbiamo dati in cache (anche stantii), meglio quelli
            # che niente — ma NON silenziamo il problema a monte.
            if cached is not None:
                return cached
            raise
        except Exception as exc:  # errore imprevisto (parsing, validazione, ...)
            if cached is not None:
                return cached
            raise DataFetchError(
                f"Errore imprevisto dal provider '{provider.name}' per {symbol}: {exc}"
            ) from exc

        if use_cache:
            self.cache.store(key, series)
        return series
