"""Dashboard Streamlit (interfaccia visuale sopra il core).

Il modulo ``charts`` è puro (solo pandas + indicatori) e testabile; ``app``
contiene la UI Streamlit e va lanciato con:  ``streamlit run <path>/app.py``.
"""

from .charts import indicators_frame

__all__ = ["indicators_frame"]
