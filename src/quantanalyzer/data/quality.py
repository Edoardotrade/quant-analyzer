"""Valutazione della qualità di una serie di prezzi.

Principio non negoziabile: se i dati sono insufficienti o sospetti, lo diciamo.
Questa funzione NON giudica il mercato, giudica solo i *dati*.
"""

from __future__ import annotations

from ..models import DataQuality, PriceSeries


def assess(series: PriceSeries, *, min_bars: int = 30) -> DataQuality:
    """Analizza una PriceSeries e restituisce un giudizio di qualità.

    ``min_bars`` è la soglia sotto la quale consideriamo i dati insufficienti
    per un'analisi tecnica sensata (di default 30 barre).
    """
    timestamps = [b.timestamp for b in series.bars]
    n = len(timestamps)

    is_ordered = timestamps == sorted(timestamps)
    has_duplicates = len(timestamps) != len(set(timestamps))

    warnings: list[str] = []
    if n == 0:
        warnings.append("Nessuna barra ricevuta dalla fonte dati.")
    if n < min_bars:
        warnings.append(
            f"Solo {n} barre disponibili (< {min_bars}): storico troppo breve "
            "per indicatori affidabili."
        )
    if has_duplicates:
        warnings.append("Presenti timestamp duplicati: possibile problema alla fonte.")
    if not is_ordered:
        warnings.append("Barre non ordinate cronologicamente.")

    sufficient = n >= min_bars and not has_duplicates and is_ordered

    return DataQuality(
        n_bars=n,
        min_bars=min_bars,
        is_ordered=is_ordered,
        has_duplicates=has_duplicates,
        sufficient=sufficient,
        warnings=warnings,
    )
