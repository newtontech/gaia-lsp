"""Agent-facing JSON CLI for gaia-lsp."""

from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from .analyzer import analyze_path, completion_items, document_symbols, hover_at
from .rules import rule_catalog

SOFTWARE = "gaia"


def _load_capabilities() -> dict[str, Any]:
    root_manifest = Path(__file__).resolve().parents[2] / "lsp-capabilities.json"
    if root_manifest.exists():
        return cast(dict[str, Any], json.loads(root_manifest.read_text(encoding="utf-8")))
    resource = files("gaia_lsp").joinpath("lsp-capabilities.json")
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def check_path(path: Path) -> dict[str, Any]:
    path = path.resolve()
    diagnostics = [item.to_json() for item in analyze_path(path)]
    blocking_count = sum(1 for item in diagnostics if item["blocking"])
    return {
        "software": SOFTWARE,
        "operation": "check",
        "path": str(path),
        "uri": path.as_uri(),
        "ok": blocking_count == 0,
        "blockingDiagnosticCount": blocking_count,
        "diagnosticCount": len(diagnostics),
        "diagnostics": diagnostics,
    }


def context_path(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {
        "software": SOFTWARE,
        "operation": "context",
        "path": str(path.resolve()),
        "completionItems": completion_items(),
        "symbols": document_symbols(text),
    }


def hover_path(path: Path, line: int, character: int) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return {
        "software": SOFTWARE,
        "operation": "hover",
        "path": str(path.resolve()),
        "line": line,
        "character": character,
        "contents": hover_at(text, line, character),
    }


def symbols_path(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return {
        "software": SOFTWARE,
        "operation": "symbols",
        "path": str(path.resolve()),
        "symbols": document_symbols(text),
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gaia-lsp-tool")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    capabilities = subparsers.add_parser("capabilities")
    capabilities.add_argument("--format", choices=["json"], default="json")

    check = subparsers.add_parser("check")
    check.add_argument("path", type=Path)
    check.add_argument("--format", choices=["json"], default="json")
    check.add_argument("--fail-on-blocking", action="store_true")

    for operation in ("context", "complete", "symbols"):
        sub = subparsers.add_parser(operation)
        sub.add_argument("path", type=Path)
        sub.add_argument("--format", choices=["json"], default="json")

    rules = subparsers.add_parser("rules")
    rules.add_argument("--format", choices=["json"], default="json")

    hover = subparsers.add_parser("hover")
    hover.add_argument("path", type=Path)
    hover.add_argument("--line", type=int, default=0)
    hover.add_argument("--character", type=int, default=0)
    hover.add_argument("--format", choices=["json"], default="json")

    args = parser.parse_args(argv)
    if args.operation == "capabilities":
        _print_json(_load_capabilities())
        return 0
    if args.operation == "check":
        payload = check_path(args.path)
        _print_json(payload)
        return 1 if args.fail_on_blocking and not payload["ok"] else 0
    if args.operation == "complete":
        _print_json(
            {
                "software": SOFTWARE,
                "operation": "complete",
                "path": str(args.path.resolve()),
                "items": completion_items(),
            }
        )
        return 0
    if args.operation == "context":
        _print_json(context_path(args.path))
        return 0
    if args.operation == "hover":
        _print_json(hover_path(args.path, args.line, args.character))
        return 0
    if args.operation == "rules":
        _print_json(rule_catalog())
        return 0
    if args.operation == "symbols":
        _print_json(symbols_path(args.path))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
