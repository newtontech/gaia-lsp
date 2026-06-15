"""Diagnostic data model for gaia-lsp."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Diagnostic:
    """A source diagnostic with 1-based display positions."""

    code: str
    message: str
    severity: str
    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None
    source: str = "gaia-lsp"
    file: str | None = None

    @property
    def blocking(self) -> bool:
        return self.severity == "error"

    def to_json(self) -> dict[str, Any]:
        end_line = self.end_line if self.end_line is not None else self.line
        end_column = self.end_column if self.end_column is not None else self.column + 1
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "source": self.source,
            "blocking": self.blocking,
            "range": {
                "start": {"line": max(self.line - 1, 0), "character": max(self.column - 1, 0)},
                "end": {
                    "line": max(end_line - 1, 0),
                    "character": max(end_column - 1, 0),
                },
            },
            "line": self.line,
            "column": self.column,
        }
        if self.file:
            payload["file"] = self.file
        return payload


def diagnostic(
    code: str,
    message: str,
    severity: str,
    node: Any,
    *,
    path: Path | None = None,
) -> Diagnostic:
    """Create a diagnostic from an AST node-like object."""

    line = int(getattr(node, "lineno", 1) or 1)
    column = int(getattr(node, "col_offset", 0) or 0) + 1
    end_line = int(getattr(node, "end_lineno", line) or line)
    end_column = int(getattr(node, "end_col_offset", column) or column) + 1
    return Diagnostic(
        code=code,
        message=message,
        severity=severity,
        line=line,
        column=column,
        end_line=end_line,
        end_column=end_column,
        file=str(path) if path else None,
    )
