"""Command-line entrypoints for gaia-lsp."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import analyze_path


def lint_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gaia-lint")
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true", help="emit JSON diagnostics")
    args = parser.parse_args(argv)

    diagnostics = analyze_path(args.path)
    if args.json:
        print(json.dumps([item.to_json() for item in diagnostics], indent=2, sort_keys=True))
    else:
        for item in diagnostics:
            file_label = f"{item.file}:" if item.file else ""
            print(
                f"{file_label}{item.line}:{item.column}: "
                f"{item.severity} {item.code} {item.message}"
            )
    return 1 if any(item.blocking for item in diagnostics) else 0


def lsp_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gaia-lsp")
    parser.add_argument("--stdio", action="store_true", help="start the LSP server on stdio")
    args = parser.parse_args(argv)
    if not args.stdio:
        parser.error("only --stdio is currently supported")
    from .server import create_server

    create_server().start_io()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python -m gaia_lsp.cli {lint,lsp} ...", file=sys.stderr)
        return 2
    command = args.pop(0)
    if command == "lint":
        return lint_main(args)
    if command == "lsp":
        return lsp_main(args)
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
