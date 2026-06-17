"""Agent-facing JSON CLI for gaia-lsp."""

from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from . import __version__
from .analyzer import (
    analyze_path,
    completion_items,
    definition_at,
    document_links,
    document_symbols,
    folding_ranges,
    hover_at,
    package_context,
    references_at,
    rename_edits_at,
    semantic_tokens,
    workspace_symbols,
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
TOOL_VERSION = __version__


class ToolError(Exception):
    """Machine-readable failure raised by an agent CLI operation.

    Carries a stable ``kind`` slug (e.g. ``missing_file``) so automation can
    branch on failure without parsing human prose.
    """

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


def _load_capabilities() -> dict[str, Any]:
    root_manifest = Path(__file__).resolve().parents[2] / "lsp-capabilities.json"
    if root_manifest.exists():
        return cast(dict[str, Any], json.loads(root_manifest.read_text(encoding="utf-8")))
    resource = files("gaia_lsp").joinpath("lsp-capabilities.json")
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def _base_envelope(operation: str, ok: bool = True, **fields: Any) -> dict[str, Any]:
    """Build the stable agent JSON envelope shared by every operation."""
    payload: dict[str, Any] = {
        "software": SOFTWARE,
        "operation": operation,
        "ok": ok,
        "toolVersion": TOOL_VERSION,
    }
    payload.update(fields)
    return payload


def _error_envelope(operation: str, kind: str, message: str, **fields: Any) -> dict[str, Any]:
    """Build a machine-readable failure envelope for an operation."""
    payload: dict[str, Any] = {
        "software": SOFTWARE,
        "operation": operation,
        "ok": False,
        "toolVersion": TOOL_VERSION,
        "error": {"kind": kind, "message": message},
    }
    payload.update(fields)
    return payload


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file, raising :class:`ToolError` on failure."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ToolError("missing_file", f"file not found: {path}") from exc
    except IsADirectoryError as exc:
        raise ToolError("not_a_file", f"expected a file but found a directory: {path}") from exc
    except PermissionError as exc:
        raise ToolError("permission_denied", f"permission denied reading: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ToolError(
            "encoding_error",
            f"file is not valid UTF-8 text: {path} ({exc.reason} at byte {exc.start})",
        ) from exc
    except OSError as exc:
        raise ToolError("io_error", f"could not read {path}: {exc.strerror or exc}") from exc


def check_path(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.exists():
        raise ToolError("missing_file", f"file or directory not found: {resolved}")
    diagnostics = [item.to_json() for item in analyze_path(resolved)]
    blocking_count = sum(1 for item in diagnostics if item["blocking"])
    return _base_envelope(
        "check",
        ok=blocking_count == 0,
        path=str(resolved),
        uri=resolved.as_uri(),
        blockingDiagnosticCount=blocking_count,
        diagnosticCount=len(diagnostics),
        diagnostics=diagnostics,
    )


def context_path(path: Path, query: str = "") -> dict[str, Any]:
    resolved = path.resolve()
    completions = completion_items(resolved)
    symbols = _symbols_for_path(resolved)
    explanations = _explanations_for_query(query)
    if query:
        completions = [
            item
            for item in completions
            if _matches_query(item, query, ("label", "detail", "documentation"))
        ]
        symbols = [
            item
            for item in symbols
            if _matches_query(item, query, ("name", "kind", "file"))
        ]
    return _base_envelope(
        "context",
        path=str(resolved),
        query=query,
        completionItems=completions,
        symbols=symbols,
        package=package_context(resolved),
        explanations=explanations,
    )


def complete_path(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return _base_envelope(
        "complete",
        path=str(resolved),
        items=completion_items(resolved),
    )


def hover_path(path: Path, line: int, character: int) -> dict[str, Any]:
    text = _read_text(path)
    return _base_envelope(
        "hover",
        path=str(path.resolve()),
        line=line,
        character=character,
        contents=hover_at(text, line, character),
    )


def definition_path(path: Path, line: int, character: int) -> dict[str, Any]:
    resolved = path.resolve()
    return _base_envelope(
        "definition",
        path=str(resolved),
        line=line,
        character=character,
        definitions=definition_at(resolved, line, character),
    )


def references_path(path: Path, line: int, character: int) -> dict[str, Any]:
    resolved = path.resolve()
    return _base_envelope(
        "references",
        path=str(resolved),
        line=line,
        character=character,
        references=references_at(resolved, line, character),
    )


def symbols_path(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    return _base_envelope(
        "symbols",
        path=str(path.resolve()),
        symbols=document_symbols(text),
    )


def workspace_symbols_path(path: Path, query: str) -> dict[str, Any]:
    resolved = path.resolve()
    return _base_envelope(
        "workspace-symbols",
        path=str(resolved),
        query=query,
        symbols=workspace_symbols(resolved, query),
    )


def folding_path(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    return _base_envelope(
        "folding",
        path=str(path.resolve()),
        ranges=folding_ranges(text),
    )


def links_path(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    resolved = path.resolve()
    return _base_envelope(
        "links",
        path=str(resolved),
        links=document_links(text, resolved),
    )


def rename_path(path: Path, line: int, character: int, new_name: str) -> dict[str, Any]:
    resolved = path.resolve()
    return _base_envelope(
        "rename",
        path=str(resolved),
        line=line,
        character=character,
        **rename_edits_at(resolved, line, character, new_name),
    )


def semantic_tokens_path(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    return _base_envelope(
        "semantic-tokens",
        path=str(path.resolve()),
        tokens=semantic_tokens(text),
    )


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _symbols_for_path(path: Path) -> list[dict[str, Any]]:
    if path.is_file():
        return document_symbols(_read_text(path))
    symbols: list[dict[str, Any]] = []
    for child in sorted(path.rglob("*.py")):
        if any(part.startswith(".") for part in child.relative_to(path).parts):
            continue
        try:
            text = _read_text(child)
        except ToolError:
            continue
        for symbol in document_symbols(text):
            symbols.append({**symbol, "file": str(child)})
    return symbols


def _matches_query(item: dict[str, Any], query: str, fields: tuple[str, ...]) -> bool:
    needle = query.casefold()
    return any(needle in str(item.get(field, "")).casefold() for field in fields)


def _explanations_for_query(query: str) -> list[dict[str, Any]]:
    if not query:
        return []
    catalog = rule_catalog()
    explanations: list[dict[str, Any]] = []
    for symbol in catalog["symbols"]:
        if _matches_query(symbol, query, ("label", "detail", "documentation", "group")):
            explanations.append({"kind": "symbol", "symbol": symbol})
    for diagnostic in catalog["diagnostics"]:
        if _matches_query(
            diagnostic,
            query,
            ("code", "severity", "group", "title", "explanation", "fix", "example"),
        ):
            explanations.append({"kind": "diagnostic", "diagnostic": diagnostic})
    return explanations


def manual_payload(section: str) -> dict[str, Any]:
    return _base_envelope("manual", **manual_catalog(section))


def explain_payload(topic: str) -> dict[str, Any]:
    try:
        payload = explain_topic(topic)
    except KeyError as exc:
        raise ToolError(
            "unknown_topic",
            f"unknown Gaia symbol or diagnostic code: {topic}",
        ) from exc
    return _base_envelope("explain", **payload)


def rules_payload() -> dict[str, Any]:
    return _base_envelope("rules", **rule_catalog())


def _build_parser() -> argparse.ArgumentParser:
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

    context = cast(Any, subparsers.choices["context"])
    context.add_argument("--query", default="")

    workspace = subparsers.add_parser("workspace-symbols")
    workspace.add_argument("path", type=Path)
    workspace.add_argument("--query", default="")
    workspace.add_argument("--format", choices=["json"], default="json")

    for operation in ("folding", "links", "semantic-tokens"):
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

    rename = subparsers.add_parser("rename")
    rename.add_argument("path", type=Path)
    rename.add_argument("new_name")
    rename.add_argument("--line", type=int, default=0)
    rename.add_argument("--character", type=int, default=0)
    rename.add_argument("--format", choices=["json"], default="json")

    return parser


def _dispatch(args: argparse.Namespace) -> tuple[Any, int, bool]:
    """Run one operation, returning (output, exit_code, is_json).

    ``output`` is a JSON-serializable dict when ``is_json`` is true, otherwise a
    pre-rendered human-readable string. Raises :class:`ToolError` for
    machine-readable failures.
    """
    operation = args.operation
    if operation == "capabilities":
        return _load_capabilities(), 0, True
    if operation == "check":
        payload = check_path(args.path)
        exit_code = 1 if args.fail_on_blocking and not payload["ok"] else 0
        return payload, exit_code, True
    if operation == "complete":
        return complete_path(args.path), 0, True
    if operation == "context":
        return context_path(args.path, args.query), 0, True
    if operation == "hover":
        return hover_path(args.path, args.line, args.character), 0, True
    if operation == "definition":
        return definition_path(args.path, args.line, args.character), 0, True
    if operation == "references":
        return references_path(args.path, args.line, args.character), 0, True
    if operation == "symbols":
        return symbols_path(args.path), 0, True
    if operation == "workspace-symbols":
        return workspace_symbols_path(args.path, args.query), 0, True
    if operation == "folding":
        return folding_path(args.path), 0, True
    if operation == "links":
        return links_path(args.path), 0, True
    if operation == "rename":
        return rename_path(args.path, args.line, args.character, args.new_name), 0, True
    if operation == "semantic-tokens":
        return semantic_tokens_path(args.path), 0, True
    if operation == "manual":
        if args.format == "json":
            return manual_payload(args.section), 0, True
        return render_manual_markdown(args.section), 0, False
    if operation == "explain":
        payload = explain_payload(args.topic)
        if args.format == "json":
            return payload, 0, True
        return render_explanation_markdown(payload), 0, False
    if operation == "rules":
        return rules_payload(), 0, True
    return None, 2, True


def _error_extras(args: argparse.Namespace) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    path = getattr(args, "path", None)
    if path is not None:
        extras["path"] = str(path)
    line = getattr(args, "line", None)
    if line is not None:
        extras["line"] = line
    character = getattr(args, "character", None)
    if character is not None:
        extras["character"] = character
    return extras


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    operation = args.operation
    try:
        output, exit_code, is_json = _dispatch(args)
    except ToolError as exc:
        _print_json(_error_envelope(operation, exc.kind, exc.message, **_error_extras(args)))
        return 1
    except (OSError, UnicodeDecodeError) as exc:
        kind = "io_error"
        message = exc.strerror or str(exc) if isinstance(exc, OSError) else str(exc)
        _print_json(_error_envelope(operation, kind, message, **_error_extras(args)))
        return 1
    except ValueError as exc:
        _print_json(
            _error_envelope(operation, "invalid_input", str(exc), **_error_extras(args))
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - last-resort machine-readable envelope
        _print_json(
            _error_envelope(operation, "internal_error", str(exc), **_error_extras(args))
        )
        return 1

    if is_json and isinstance(output, dict):
        _print_json(output)
    else:
        print(output, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
