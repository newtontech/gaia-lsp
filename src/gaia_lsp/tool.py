"""Agent-facing JSON CLI for gaia-lsp."""

from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from .analyzer import (
    analyze_path,
    completion_items,
    definition_at,
    document_symbols,
    hover_at,
    package_context,
    references_at,
)
from .rules import (
    MANUAL_SECTION_IDS,
    explain_topic,
    manual_catalog,
    render_explanation_markdown,
    render_manual_markdown,
    rule_catalog,
)

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
    path = path.resolve()
    return {
        "software": SOFTWARE,
        "operation": "context",
        "path": str(path),
        "completionItems": completion_items(path),
        "symbols": _symbols_for_path(path),
        "package": package_context(path),
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


def definition_path(path: Path, line: int, character: int) -> dict[str, Any]:
    path = path.resolve()
    return {
        "software": SOFTWARE,
        "operation": "definition",
        "path": str(path),
        "line": line,
        "character": character,
        "definitions": definition_at(path, line, character),
    }


def references_path(path: Path, line: int, character: int) -> dict[str, Any]:
    path = path.resolve()
    return {
        "software": SOFTWARE,
        "operation": "references",
        "path": str(path),
        "line": line,
        "character": character,
        "references": references_at(path, line, character),
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


def _symbols_for_path(path: Path) -> list[dict[str, Any]]:
    if path.is_file():
        return document_symbols(path.read_text(encoding="utf-8"))
    symbols: list[dict[str, Any]] = []
    for child in sorted(path.rglob("*.py")):
        if any(part.startswith(".") for part in child.relative_to(path).parts):
            continue
        for symbol in document_symbols(child.read_text(encoding="utf-8")):
            symbols.append({**symbol, "file": str(child)})
    return symbols


def manual_payload(section: str) -> dict[str, Any]:
    payload = manual_catalog(section)
    return {
        "software": SOFTWARE,
        "operation": "manual",
        **payload,
    }


def explain_payload(topic: str) -> dict[str, Any]:
    payload = explain_topic(topic)
    return {
        "operation": "explain",
        **payload,
    }


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

    manual = subparsers.add_parser("manual")
    manual.add_argument("--format", choices=["markdown", "json"], default="markdown")
    manual.add_argument(
        "--section",
        choices=["all", *MANUAL_SECTION_IDS],
        default="all",
        help="manual section to render",
    )

    explain = subparsers.add_parser("explain")
    explain.add_argument("topic", help="Gaia symbol name or diagnostic code such as GAIA010")
    explain.add_argument("--format", choices=["json", "markdown"], default="json")

    hover = subparsers.add_parser("hover")
    hover.add_argument("path", type=Path)
    hover.add_argument("--line", type=int, default=0)
    hover.add_argument("--character", type=int, default=0)
    hover.add_argument("--format", choices=["json"], default="json")

    for operation in ("definition", "references"):
        location = subparsers.add_parser(operation)
        location.add_argument("path", type=Path)
        location.add_argument("--line", type=int, default=0)
        location.add_argument("--character", type=int, default=0)
        location.add_argument("--format", choices=["json"], default="json")

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
                "items": completion_items(args.path),
            }
        )
        return 0
    if args.operation == "context":
        _print_json(context_path(args.path))
        return 0
    if args.operation == "hover":
        _print_json(hover_path(args.path, args.line, args.character))
        return 0
    if args.operation == "definition":
        _print_json(definition_path(args.path, args.line, args.character))
        return 0
    if args.operation == "references":
        _print_json(references_path(args.path, args.line, args.character))
        return 0
    if args.operation == "manual":
        if args.format == "json":
            _print_json(manual_payload(args.section))
        else:
            print(render_manual_markdown(args.section), end="")
        return 0
    if args.operation == "explain":
        try:
            payload = explain_payload(args.topic)
        except KeyError:
            parser.error(f"unknown Gaia symbol or diagnostic code: {args.topic}")
        if args.format == "json":
            _print_json(payload)
        else:
            print(render_explanation_markdown(payload), end="")
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
