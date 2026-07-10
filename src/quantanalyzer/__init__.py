"""Quant Analyzer — motore di analisi quantitativa dei mercati.

Il package è organizzato per livelli disaccoppiati:
  - models      : modelli di dominio (dati validati)
  - config      : configurazione + API key da variabili d'ambiente
  - data        : provider di dati di mercato + cache + qualità dei dati
  - api         : interfaccia FastAPI (thin layer sopra il core)

Le fasi successive aggiungeranno: indicators, analysis, risk, report.
"""

__version__ = "0.1.0"

# Disclaimer usato in ogni output rivolto all'utente.
DISCLAIMER = (
    "Questo strumento fornisce analisi quantitative a solo scopo informativo ed educativo. "
    "NON è consulenza finanziaria. I risultati passati non garantiscono quelli futuri. "
    "Ogni decisione di investimento e il relativo rischio restano a carico esclusivo dell'utente."
)
