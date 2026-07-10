"""Layer di reportistica: scenari + report multi-formato (Markdown/HTML/PDF)."""

from .builder import build_report
from .render import to_html, to_markdown, to_pdf

__all__ = ["build_report", "to_markdown", "to_html", "to_pdf"]
