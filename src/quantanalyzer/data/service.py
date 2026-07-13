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
from .twelvedata_provider import TwelveDataProvider
from .yfinance_provider import YFinanceProvider


def _crypto_exchange_order(primary: str) -> list[str]:
    """Ordine di prova degli exchange crypto (il primo è quello configurato).

    Provando più exchange in cascata, le crypto funzionano su qualsiasi server:
    alcuni exchange sono bloccati da certi IP cloud (es. Binance dagli USA),
    ma almeno uno tra questi è quasi sempre raggiungibile.
    """
    order = [primary, "kraken", "coinbase", "binance", "bitstamp"]
    seen: set[str] = set()
    return [e for e in order if e and not (e in seen or seen.add(e))]


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
        if providers is not None:
            self.providers: list[MarketDataProvider] = list(providers)
        else:
            # Twelve Data prima (affidabile da cloud, richiede chiave: se assente
            # supports()=False e si passa a yfinance), poi yfinance, poi più exchange
            # crypto in cascata (così le crypto funzionano su qualsiasi server).
            crypto = [
                CCXTProvider(exchange_id=e)
                for e in _crypto_exchange_order(self.settings.ccxt_exchange)
            ]
            self.providers = [TwelveDataProvider(), YFinanceProvider(), *crypto]

    def providers_for(self, asset_class: AssetClass) -> list[MarketDataProvider]:
        """Provider che supportano la classe, in ordine di priorità."""
        return [p for p in self.providers if p.supports(asset_class)]

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
        """Restituisce una PriceSeries con cache, fallback tra fonti e fail-soft.

        Ordine: cache fresca → prova ogni fonte che supporta l'asset (in ordine) →
        cache stantia come ultimo ripiego.
        """
        providers = self.providers_for(asset_class)
        if not providers:
            raise DataUnavailableError(
                f"Nessun provider configurato per la classe di asset '{asset_class.value}'."
            )

        # chiave di cache indipendente dalla fonte: i dati sono gli stessi
        key = make_key("mkt", symbol, asset_class, interval)
        cached = self.cache.load(key) if use_cache else None
        if cached is not None and not force_refresh and self.cache.is_fresh(cached):
            return cached

        errors: list[str] = []
        had_unavailable = False
        had_fetch_error = False
        for provider in providers:
            try:
                series = provider.fetch(
                    symbol, asset_class=asset_class, interval=interval, lookback=lookback
                )
                if use_cache:
                    try:
                        self.cache.store(key, series)
                    except Exception:  # noqa: BLE001 — cache non scrivibile: non è fatale
                        pass
                return series
            except DataUnavailableError as exc:
                had_unavailable = True
                errors.append(f"{provider.name}: {exc}")
            except Exception as exc:  # noqa: BLE001 — errore di fetch: prova la fonte successiva
                had_fetch_error = True
                errors.append(f"{provider.name}: {exc}")

        # tutte le fonti hanno fallito
        if cached is not None:
            return cached
        message = f"Tutte le fonti hanno fallito per '{symbol}': {'; '.join(errors)}"
        # solo "dato non disponibile" (simbolo inesistente) -> 404; errore di fetch -> 502
        if had_unavailable and not had_fetch_error:
            raise DataUnavailableError(message)
        raise DataFetchError(message)
