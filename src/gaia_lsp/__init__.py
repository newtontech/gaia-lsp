"""Static diagnostics and LSP helpers for Gaia Lang Python DSL packages."""

from __future__ import annotations

from .analyzer import (
    analyze_path,
    analyze_text,
    completion_items,
    document_links,
    folding_ranges,
    hover,
    rename_edits_at,
    semantic_tokens,
    workspace_symbols,
)

__version__ = "0.5.0a3"

__all__ = [
    "__version__",
    "analyze_path",
    "analyze_text",
    "completion_items",
    "document_links",
    "folding_ranges",
    "hover",
    "rename_edits_at",
    "semantic_tokens",
    "workspace_symbols",
]
