"""Static diagnostics and LSP helpers for Gaia Lang Python DSL packages."""

from __future__ import annotations

from .analyzer import analyze_path, analyze_text, completion_items, hover

__version__ = "0.1.0"

__all__ = ["__version__", "analyze_path", "analyze_text", "completion_items", "hover"]
