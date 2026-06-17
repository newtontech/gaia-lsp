"""Static Gaia Lang Python DSL analysis.

The analyzer intentionally uses Python's AST instead of importing target
modules. Gaia packages are executable Python projects, so editor diagnostics
must not run author code just to find obvious DSL mistakes.
"""

from __future__ import annotations

import ast
import importlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

try:
    tomllib = importlib.import_module("tomllib")
except ImportError:  # pragma: no cover - exercised on Python < 3.11
    tomllib = importlib.import_module("tomli")

from .diagnostics import Diagnostic, diagnostic
from .rules import (
    ACTION_CALLS,
    ARTIFACT_CALLS,
    ARTIFACT_KINDS,
    ARTIFACT_LOCATOR_REQUIRED_WITH_SOURCE,
    ASSOCIATE_PATTERNS,
    ASSOCIATION_CALLS,
    BAYES_CALLS,
    CANDIDATE_RELATION_PATTERNS,
    CONTENT_CALLS,
    CROMWELL_EPS,
    CSL_TYPES,
    CURRENT_GAIA_SERIES,
    DEPRECATED_CALLS,
    DEPRECATED_RELATIONS,
    DEPRECATED_STRATEGIES,
    DISTRIBUTION_RULES,
    DISTRIBUTIONS,
    DOCUMENT_SYMBOL_CALLS,
    EXPORTABLE_KNOWLEDGE_CALLS,
    RELATION_CALLS,
    SCAFFOLD_CALLS,
    SUPPORTED_GAIA_SERIES,
    SYMBOLS,
    import_completion_items,
    preferred_import_for_symbol,
)

GAIA_MODULES = {
    "gaia.lang",
    "gaia.engine.bayes",
    "gaia.engine.bayes.dsl",
    "gaia.engine.lang",
    "gaia.engine.lang.dsl",
}
GAIA_MODULE_PREFIXES = (
    "gaia.lang",
    "gaia.engine.bayes",
    "gaia.engine.lang",
)
ALL_KNOWN_CALLS = (
    set(SYMBOLS)
    | set(DEPRECATED_CALLS)
    | set(DEPRECATED_RELATIONS)
    | set(DEPRECATED_STRATEGIES)
)

_KEY = (
    r"(?:[A-Za-z0-9_][A-Za-z0-9_:.#$%&+?<>~/\-]*[A-Za-z0-9_]"
    r"|[A-Za-z0-9_])"
)
CITATION_KEY_RE = re.compile(rf"^{_KEY}$")
BRACKET_GROUP_RE = re.compile(
    r"(?<!\\)\[([^\[\]]*(?<!\\)@[A-Za-z0-9_][^\[\]]*)\]"
)
INNER_KEY_RE = re.compile(rf"(?<!\\)@({_KEY})")


@dataclass(frozen=True)
class _ImportContext:
    aliases: dict[str, str] = field(default_factory=dict)
    module_aliases: set[str] = field(default_factory=set)

    @classmethod
    def from_tree(cls, tree: ast.Module) -> _ImportContext:
        aliases: dict[str, str] = {}
        module_aliases: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.module == "gaia.engine":
                    for alias in node.names:
                        if alias.name == "bayes":
                            module_aliases.add(alias.asname or alias.name)
                elif node.module and _is_gaia_import_module(node.module):
                    for alias in node.names:
                        if alias.name == "*":
                            for symbol in ALL_KNOWN_CALLS:
                                aliases[symbol] = symbol
                        else:
                            aliases[alias.asname or alias.name] = alias.name
                else:
                    for alias in node.names:
                        aliases.pop(alias.asname or alias.name, None)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_gaia_import_module(alias.name):
                        module_aliases.add(alias.asname or alias.name)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                aliases.pop(node.name, None)
        return cls(aliases=aliases, module_aliases=module_aliases)

    def canonical_call_name(self, func: ast.AST, *, allow_unimported: bool = False) -> str | None:
        if isinstance(func, ast.Name):
            name = self.aliases.get(func.id)
            if name in ALL_KNOWN_CALLS:
                return name
            if allow_unimported and func.id in ALL_KNOWN_CALLS:
                return func.id
            return None

        dotted = _dotted_name(func)
        if not dotted or "." not in dotted:
            return None
        prefix, attr = dotted.rsplit(".", 1)
        if attr not in ALL_KNOWN_CALLS:
            return None
        if prefix in self.module_aliases or _is_gaia_import_module(prefix):
            return attr
        return None


@dataclass
class _FileIndex:
    imports: _ImportContext
    bound_names: set[str] = field(default_factory=set)
    exportable_names: set[str] = field(default_factory=set)
    distribution_names: set[str] = field(default_factory=set)
    variable_names: set[str] = field(default_factory=set)
    domain_names: set[str] = field(default_factory=set)
    label_names: set[str] = field(default_factory=set)

    @property
    def local_reference_names(self) -> set[str]:
        return self.exportable_names | self.label_names


@dataclass
class _ReferenceInfo:
    keys: set[str] = field(default_factory=set)
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class _PackageIndex:
    root: Path
    source_root: Path | None
    file_indices: dict[Path, _FileIndex]
    exportable_names: set[str]
    label_names: set[str]
    reference_info: _ReferenceInfo
    diagnostics: list[Diagnostic]

    @property
    def local_reference_names(self) -> set[str]:
        return self.exportable_names | self.label_names

    @classmethod
    def build(cls, root: Path) -> _PackageIndex:
        config, source_root, package_diagnostics = _check_package_structure(root)
        del config
        python_files = [
            child
            for child in sorted(root.rglob("*.py"))
            if not any(part.startswith(".") for part in child.relative_to(root).parts)
        ]
        file_indices: dict[Path, _FileIndex] = {}
        exportable_names: set[str] = set()
        label_names: set[str] = set()
        for child in python_files:
            try:
                tree = ast.parse(child.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            index = _index_tree(tree)
            file_indices[child.resolve()] = index
            exportable_names.update(index.exportable_names)
            label_names.update(index.label_names)

        reference_info = _load_references_at(
            root / "references.json",
            exportable_names | label_names,
        )
        return cls(
            root=root,
            source_root=source_root,
            file_indices=file_indices,
            exportable_names=exportable_names,
            label_names=label_names,
            reference_info=reference_info,
            diagnostics=[*package_diagnostics, *reference_info.diagnostics],
        )


def analyze_path(path: Path) -> list[Diagnostic]:
    """Analyze one Python file or a directory of Gaia package files."""

    path = path.resolve()
    if path.is_dir():
        package_index = _PackageIndex.build(path)
        diagnostics: list[Diagnostic] = list(package_index.diagnostics)
        for child in sorted(package_index.file_indices):
            diagnostics.extend(
                analyze_text(
                    child.read_text(encoding="utf-8"),
                    path=child,
                    package_index=package_index,
                )
            )
        return _sort_diagnostics(diagnostics)
    return analyze_text(path.read_text(encoding="utf-8"), path=path)


def analyze_text(
    text: str,
    *,
    path: Path | None = None,
    package_index: _PackageIndex | None = None,
) -> list[Diagnostic]:
    """Analyze a Gaia DSL Python module without executing it."""

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [
            Diagnostic(
                code="GAIA001",
                message=exc.msg,
                severity="error",
                line=exc.lineno or 1,
                column=(exc.offset or 1),
                file=str(path) if path else None,
            )
        ]

    resolved_path = path.resolve() if path is not None else None
    file_index = (
        package_index.file_indices.get(resolved_path)
        if package_index is not None and resolved_path is not None
        else None
    )
    if file_index is None:
        file_index = _index_tree(tree)

    collector = _Analyzer(path, file_index=file_index, package_index=package_index)
    collector.visit(tree)
    collector.check_references()
    return _sort_diagnostics(collector.diagnostics)


def completion_items(path: Path | None = None) -> list[dict[str, str]]:
    """Return editor completion entries for Gaia symbols and package imports."""

    items = import_completion_items()
    items.extend(
        {
            "label": label,
            "detail": info.detail,
            "documentation": info.documentation,
            "kind": _completion_kind_for_group(info.group),
            "sortText": f"100_{label}",
        }
        for label, info in sorted(SYMBOLS.items())
    )
    if path is not None:
        items.extend(_local_import_completion_items(path))
    return items


def package_context(path: Path) -> dict[str, Any]:
    """Return static Gaia package/module context for a file or package directory."""

    package_root = _find_gaia_package_root(path.resolve())
    if package_root is None:
        return {}
    config, source_root, diagnostics = _check_package_structure(package_root)
    project_config = config.get("project", {}) if isinstance(config.get("project"), dict) else {}
    project_name = project_config.get("name")
    import_name = _project_import_name(project_name)
    gaia_version = _declared_gaia_version(config, project_name)
    package_index = _PackageIndex.build(package_root)
    modules = [
        _module_context_item(file_path, index, source_root, import_name)
        for file_path, index in sorted(package_index.file_indices.items())
    ]
    return {
        "root": str(package_root),
        "projectName": project_name if isinstance(project_name, str) else None,
        "importName": import_name,
        "gaiaVersion": gaia_version,
        "supportedGaiaSeries": list(SUPPORTED_GAIA_SERIES),
        "currentGaiaSeries": CURRENT_GAIA_SERIES,
        "sourceRoot": str(source_root) if source_root else None,
        "modules": modules,
        "referenceKeys": sorted(package_index.reference_info.keys),
        "diagnostics": [item.to_json() for item in diagnostics],
    }


def definition_at(path: Path, line: int, character: int) -> list[dict[str, Any]]:
    """Return Gaia symbol definitions for the word at a 0-based position."""

    path = path.resolve()
    text = path.read_text(encoding="utf-8")
    symbol = _word_at(text, line, character)
    if not symbol:
        return []
    return [
        item
        for item in _symbol_definitions_for_scope(path)
        if item["name"] == symbol or item.get("label") == symbol
    ]


def references_at(path: Path, line: int, character: int) -> list[dict[str, Any]]:
    """Return Gaia/Python references for the word at a 0-based position."""

    path = path.resolve()
    text = path.read_text(encoding="utf-8")
    symbol = _word_at(text, line, character)
    if not symbol:
        return []
    return _symbol_references_for_scope(path, symbol)


def workspace_symbols(path: Path, query: str = "") -> list[dict[str, Any]]:
    """Return Gaia symbols under a file, package, or workspace path."""

    path = path.resolve()
    root = _find_gaia_package_root(path) or (path if path.is_dir() else path.parent)
    query_folded = query.casefold()
    symbols: list[dict[str, Any]] = []
    for child in _python_files_for_scope(root, root if root.is_dir() else None):
        try:
            text = child.read_text(encoding="utf-8")
        except OSError:
            continue
        for symbol in document_symbols(text):
            if query_folded and query_folded not in symbol["name"].casefold():
                continue
            symbols.append(_location_from_symbol(symbol, child))
    return sorted(symbols, key=lambda item: (item["name"], item["file"], item["line"]))


def folding_ranges(text: str) -> list[dict[str, int | str]]:
    """Return foldable Gaia/Python source ranges in LSP-compatible coordinates."""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    ranges: list[dict[str, int | str]] = []
    for node in ast.walk(tree):
        start_line = int(getattr(node, "lineno", 0) or 0)
        end_line = int(getattr(node, "end_lineno", 0) or 0)
        if start_line <= 0 or end_line <= start_line:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "region"
        elif isinstance(node, (ast.Call, ast.List, ast.Tuple, ast.Dict, ast.Set)):
            kind = "region"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            kind = "comment"
        else:
            continue
        ranges.append({"startLine": start_line - 1, "endLine": end_line - 1, "kind": kind})
    return _dedupe_ranges(ranges)


def document_links(text: str, path: Path | None = None) -> list[dict[str, Any]]:
    """Return links for strict Gaia references and local artifact paths."""

    links: list[dict[str, Any]] = []
    for match in BRACKET_GROUP_RE.finditer(text):
        body = match.group(1)
        for key_match in INNER_KEY_RE.finditer(body):
            key = key_match.group(1)
            start = match.start(1) + key_match.start(1)
            end = match.start(1) + key_match.end(1)
            target = _reference_target(path, key)
            if target is None:
                continue
            links.append(
                {
                    "target": target,
                    "tooltip": f"Open Gaia reference {key}",
                    "range": _offset_range(text, start, end),
                }
            )
    if path is not None:
        links.extend(_artifact_path_links(text, path))
    return links


def rename_edits_at(path: Path, line: int, character: int, new_name: str) -> dict[str, Any]:
    """Return conservative package-local rename edits for Gaia bindings and labels."""

    path = path.resolve()
    text = path.read_text(encoding="utf-8")
    old_name = _word_at(text, line, character)
    if not old_name:
        raise ValueError("rename position does not resolve to a Gaia symbol or label")
    if not CITATION_KEY_RE.match(new_name):
        raise ValueError(f"new Gaia name {new_name!r} is not a valid identifier/reference key")
    references = references_at(path, line, character)
    if not references:
        raise ValueError(f"no package-local Gaia references found for {old_name!r}")
    changes: dict[str, list[dict[str, Any]]] = {}
    for item in references:
        start_column = int(item["column"]) - 1
        end_column = int(item["endColumn"]) - 1
        if item.get("kind") == "strict-reference":
            start_column += 1
        edit = {
            "range": {
                "start": {"line": int(item["line"]) - 1, "character": start_column},
                "end": {"line": int(item["endLine"]) - 1, "character": end_column},
            },
            "newText": new_name,
        }
        changes.setdefault(str(item["uri"]), []).append(edit)
    return {"oldName": old_name, "newName": new_name, "changes": changes}


SEMANTIC_TOKEN_TYPES = ["function", "variable", "class", "namespace", "property", "string"]
SEMANTIC_TOKEN_MODIFIERS = ["deprecated", "readonly"]


def semantic_tokens(text: str) -> list[dict[str, Any]]:
    """Return semantic token spans for Gaia DSL calls and authored bindings."""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    imports = _ImportContext.from_tree(tree)
    tokens: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        value = _assignment_value(node)
        if isinstance(value, ast.Call):
            name = imports.canonical_call_name(value.func, allow_unimported=True)
            if name in DOCUMENT_SYMBOL_CALLS:
                for target in _assignment_target_nodes(node):
                    if isinstance(target, ast.Name):
                        tokens.append(
                            _semantic_token(
                                target.lineno,
                                target.col_offset,
                                len(target.id),
                                "variable",
                            )
                        )
        if isinstance(node, ast.Call):
            name = imports.canonical_call_name(node.func, allow_unimported=True)
            if name in ALL_KNOWN_CALLS:
                location = _call_name_location(node.func)
                if location is not None:
                    line, column, length = location
                    modifiers = []
                    if (
                        name in DEPRECATED_CALLS
                        or name in DEPRECATED_RELATIONS
                        or name in DEPRECATED_STRATEGIES
                    ):
                        modifiers.append("deprecated")
                    token_type = (
                        "class"
                        if name in DISTRIBUTIONS or name in {"Variable", "Domain"}
                        else "function"
                    )
                    tokens.append(_semantic_token(line, column, length, token_type, modifiers))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            label = _gaia_label_value(node, tree)
            if label:
                tokens.append(
                    _semantic_token(
                        int(getattr(node, "lineno", 1) or 1),
                        int(getattr(node, "col_offset", 0) or 0)
                        + _string_content_start_offset(text, node),
                        len(label),
                        "string",
                        ["readonly"],
                    )
                )
    return sorted(tokens, key=lambda item: (item["line"], item["character"], item["length"]))


def hover(symbol: str) -> str:
    """Return hover documentation for a Gaia symbol."""

    info = SYMBOLS.get(symbol)
    if info is None:
        return ""
    return f"**{symbol}** `{info.detail}`\n\n{info.documentation}"


def hover_at(text: str, line: int, character: int) -> str:
    """Return hover documentation for the word at a 0-based position."""

    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return ""
    current = lines[line]
    if character < 0:
        character = 0
    if character > len(current):
        character = len(current)
    start = character
    while start > 0 and (current[start - 1].isalnum() or current[start - 1] == "_"):
        start -= 1
    end = character
    while end < len(current) and (current[end].isalnum() or current[end] == "_"):
        end += 1
    return hover(current[start:end])


def document_symbols(text: str) -> list[dict[str, Any]]:
    """Return Gaia knowledge bindings in a compact agent-facing shape."""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    file_index = _index_tree(tree)
    symbols: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        value = _assignment_value(node)
        if not isinstance(value, ast.Call):
            continue
        name = file_index.imports.canonical_call_name(value.func, allow_unimported=True)
        if name not in DOCUMENT_SYMBOL_CALLS:
            continue
        for target in _assignment_target_names(node):
            symbols.append(
                {
                    "name": target,
                    "kind": name,
                    "line": getattr(node, "lineno", 1),
                    "column": int(getattr(node, "col_offset", 0) or 0) + 1,
                }
            )
    return symbols


def _completion_kind_for_group(group: str) -> str:
    if group in {"formula", "distribution", "runtime"}:
        return "class"
    if group in {"introspection"}:
        return "function"
    return "function"


def _local_import_completion_items(path: Path) -> list[dict[str, str]]:
    context = package_context(path)
    source_root_value = context.get("sourceRoot")
    if not source_root_value:
        return []
    source_root = Path(str(source_root_value))
    target = path.resolve()
    current_package_parts = _current_package_parts(target, source_root)
    items: list[dict[str, str]] = []
    for module in context.get("modules", []):
        module_path = Path(str(module["path"]))
        if module_path == target:
            continue
        try:
            relative = module_path.relative_to(source_root)
        except ValueError:
            continue
        import_target = _relative_import_target(current_package_parts, relative)
        if not import_target:
            continue
        label = f"from {import_target} import *"
        items.append(
            {
                "label": label,
                "detail": f"Import local Gaia module {module['module']}",
                "documentation": "Package-local import hint derived from the Gaia source tree.",
                "insertText": label,
                "kind": "module",
                "sortText": f"010_local_import_{module['module']}",
            }
        )
    deduped: dict[str, dict[str, str]] = {item["label"]: item for item in items}
    return [deduped[label] for label in sorted(deduped)]


def _current_package_parts(target: Path, source_root: Path) -> tuple[str, ...]:
    if target.is_dir():
        current = target
    elif target.name == "__init__.py":
        current = target.parent
    else:
        current = target.parent
    try:
        return current.relative_to(source_root).parts
    except ValueError:
        return ()


def _relative_import_target(current_package_parts: tuple[str, ...], relative: Path) -> str:
    if relative.name == "__init__.py":
        destination_parts = relative.parent.parts
    else:
        destination_parts = relative.with_suffix("").parts
    if destination_parts == current_package_parts:
        return ""

    common = 0
    for left, right in zip(current_package_parts, destination_parts):
        if left != right:
            break
        common += 1

    upward_levels = len(current_package_parts) - common
    prefix = "." * (upward_levels + 1)
    suffix = ".".join(destination_parts[common:])
    return f"{prefix}{suffix}" if suffix else prefix


def _find_gaia_package_root(path: Path) -> Path | None:
    start = path if path.is_dir() else path.parent
    for directory in [start, *start.parents]:
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            try:
                config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            except Exception:
                return directory
            project_config = config.get("project", {})
            project_name = project_config.get("name") if isinstance(project_config, dict) else None
            gaia_section = (
                config.get("tool", {}).get("gaia", {})
                if isinstance(config.get("tool"), dict)
                else {}
            )
            if gaia_section or (isinstance(project_name, str) and project_name.endswith("-gaia")):
                return directory
        if (directory / ".git").exists():
            break
    return None


def _module_context_item(
    file_path: Path,
    index: _FileIndex,
    source_root: Path | None,
    import_name: str | None,
) -> dict[str, Any]:
    module = file_path.stem
    if source_root is not None and import_name:
        try:
            relative = file_path.relative_to(source_root)
        except ValueError:
            module_parts: tuple[str, ...] = ()
        else:
            if relative.name == "__init__.py":
                module_parts = relative.parts[:-1]
            else:
                module_parts = relative.with_suffix("").parts
        module = ".".join((import_name, *module_parts))
    return {
        "module": module,
        "path": str(file_path),
        "exports": sorted(index.exportable_names),
        "labels": sorted(index.label_names),
        "distributions": sorted(index.distribution_names),
        "variables": sorted(index.variable_names),
        "domains": sorted(index.domain_names),
    }


def _project_import_name(project_name: Any) -> str | None:
    if not isinstance(project_name, str) or not project_name:
        return None
    return project_name.removesuffix("-gaia").replace("-", "_")


def _top_level_bound_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            names.update(_assignment_target_names(node))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    names.add(alias.asname or alias.name)
    return names


def _word_at(text: str, line: int, character: int) -> str:
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return ""
    current = lines[line]
    character = min(max(character, 0), len(current))
    start = character
    while start > 0 and (current[start - 1].isalnum() or current[start - 1] == "_"):
        start -= 1
    end = character
    while end < len(current) and (current[end].isalnum() or current[end] == "_"):
        end += 1
    return current[start:end]


def _symbol_definitions_for_scope(path: Path) -> list[dict[str, Any]]:
    root = _find_gaia_package_root(path)
    files = _python_files_for_scope(path, root)
    definitions: list[dict[str, Any]] = []
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for symbol in document_symbols(text):
            definitions.append(_location_from_symbol(symbol, file_path))
        definitions.extend(_label_definitions_from_text(text, file_path))
    return definitions


def _symbol_references_for_scope(path: Path, symbol: str) -> list[dict[str, Any]]:
    root = _find_gaia_package_root(path)
    files = _python_files_for_scope(path, root)
    references: list[dict[str, Any]] = []
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == symbol:
                references.append(_location_from_ast(symbol, "name", node, file_path))
            elif _gaia_label_value(node, tree) == symbol:
                references.append(_location_from_label(symbol, "label-definition", node, file_path))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                references.extend(_reference_locations_in_string(symbol, node, file_path, text))
    return sorted(references, key=lambda item: (item["file"], item["line"], item["column"]))


def _python_files_for_scope(path: Path, root: Path | None) -> list[Path]:
    if root is None:
        return [path] if path.is_file() else sorted(path.rglob("*.py"))
    return [
        child
        for child in sorted(root.rglob("*.py"))
        if not any(part.startswith(".") for part in child.relative_to(root).parts)
    ]


def _location_from_symbol(symbol: dict[str, Any], file_path: Path) -> dict[str, Any]:
    name = str(symbol["name"])
    line = int(symbol.get("line", 1))
    column = int(symbol.get("column", 1))
    return {
        "name": name,
        "kind": str(symbol.get("kind", "symbol")),
        "file": str(file_path),
        "uri": file_path.as_uri(),
        "line": line,
        "column": column,
        "endLine": line,
        "endColumn": column + len(name),
    }


def _location_from_ast(symbol: str, kind: str, node: ast.AST, file_path: Path) -> dict[str, Any]:
    line = int(getattr(node, "lineno", 1) or 1)
    column = int(getattr(node, "col_offset", 0) or 0) + 1
    end_line = int(getattr(node, "end_lineno", line) or line)
    end_column = int(getattr(node, "end_col_offset", column) or column) + 1
    return {
        "name": symbol,
        "kind": kind,
        "file": str(file_path),
        "uri": file_path.as_uri(),
        "line": line,
        "column": column,
        "endLine": end_line,
        "endColumn": end_column,
    }


def _label_definitions_from_text(text: str, file_path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    definitions: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        label = _gaia_label_value(node, tree)
        if label:
            definitions.append(_location_from_label(label, "label", node, file_path))
    return definitions


def _gaia_label_value(node: ast.AST, tree: ast.Module) -> str | None:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return None
    parent = _parent_call_for_keyword_value(tree, node, "label")
    if parent is None:
        return None
    imports = _ImportContext.from_tree(tree)
    if imports.canonical_call_name(parent.func, allow_unimported=True) not in DOCUMENT_SYMBOL_CALLS:
        return None
    return str(node.value)


def _parent_call_for_keyword_value(
    tree: ast.Module,
    target: ast.Constant,
    keyword_name: str,
) -> ast.Call | None:
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        if any(
            keyword.arg == keyword_name and keyword.value is target
            for keyword in call.keywords
        ):
            return call
    return None


def _location_from_label(
    symbol: str,
    kind: str,
    node: ast.AST,
    file_path: Path,
) -> dict[str, Any]:
    line = int(getattr(node, "lineno", 1) or 1)
    column = int(getattr(node, "col_offset", 0) or 0) + 2
    return {
        "name": symbol,
        "kind": kind,
        "file": str(file_path),
        "uri": file_path.as_uri(),
        "line": line,
        "column": column,
        "endLine": line,
        "endColumn": column + len(symbol),
    }


def _reference_locations_in_string(
    symbol: str,
    node: ast.Constant,
    file_path: Path,
    source_text: str,
) -> list[dict[str, Any]]:
    text = str(node.value)
    locations: list[dict[str, Any]] = []
    for match in re.finditer(rf"(?<!\\)@{re.escape(symbol)}\b", text):
        line = int(getattr(node, "lineno", 1) or 1)
        prefix = text[: match.start()]
        relative_line = prefix.count("\n")
        if relative_line:
            line += relative_line
            column = len(prefix.rsplit("\n", 1)[-1]) + 1
        else:
            column = (
                int(getattr(node, "col_offset", 0) or 0)
                + _string_content_start_offset(source_text, node)
                + match.start()
                + 1
            )
        locations.append(
            {
                "name": symbol,
                "kind": "strict-reference",
                "file": str(file_path),
                "uri": file_path.as_uri(),
                "line": line,
                "column": column,
                "endLine": line,
                "endColumn": column + len(symbol) + 1,
            }
        )
    return locations


def _string_content_start_offset(source_text: str, node: ast.Constant) -> int:
    segment = ast.get_source_segment(source_text, node) or ""
    prefix = re.match(r"(?i)[rubf]*", segment)
    quote_index = prefix.end() if prefix else 0
    while quote_index < len(segment) and segment[quote_index] not in {"'", '"'}:
        quote_index += 1
    if quote_index >= len(segment):
        return 0
    quote = segment[quote_index]
    delimiter = quote * 3 if segment.startswith(quote * 3, quote_index) else quote
    return quote_index + len(delimiter)


class _Analyzer(ast.NodeVisitor):
    def __init__(
        self,
        path: Path | None,
        *,
        file_index: _FileIndex,
        package_index: _PackageIndex | None,
    ) -> None:
        self.path = path
        self.file_index = file_index
        self.package_index = package_index
        self.diagnostics: list[Diagnostic] = []
        self.strict_refs: dict[str, ast.AST] = {}
        self._added_reference_schema_diagnostics = False

    def visit_Assign(self, node: ast.Assign) -> Any:
        if any(isinstance(target, ast.Name) and target.id == "PRIORS" for target in node.targets):
            self.diagnostics.append(
                diagnostic(
                    "GAIA033",
                    "Legacy PRIORS dictionaries are rejected by Gaia v0.5+; use "
                    "register_prior(claim, value, justification=...) instead.",
                    "error",
                    node,
                    path=self.path,
                )
            )
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            self._check_all(node.value, node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        if isinstance(node.target, ast.Name) and node.target.id == "__all__" and node.value:
            self._check_all(node.value, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        name = self.file_index.imports.canonical_call_name(node.func)
        if name is None:
            self._check_unimported_gaia_call(node)
            self.generic_visit(node)
            return

        if name in DEPRECATED_CALLS:
            replacement = DEPRECATED_CALLS[name]
            self.diagnostics.append(
                diagnostic(
                    "GAIA020",
                    f"{name}() is deprecated for Gaia v0.5+ authoring; use {replacement}().",
                    "warning",
                    node,
                    path=self.path,
                )
            )
        if name in DEPRECATED_RELATIONS:
            replacement = DEPRECATED_RELATIONS[name]
            self.diagnostics.append(
                diagnostic(
                    "GAIA021",
                    f"{name}() is a legacy relation helper; use {replacement}().",
                    "warning",
                    node,
                    path=self.path,
                )
            )
        if name in DEPRECATED_STRATEGIES:
            replacement = DEPRECATED_STRATEGIES[name]
            self.diagnostics.append(
                diagnostic(
                    "GAIA022",
                    f"{name}() is a legacy strategy helper; spell the v0.5+ graph with "
                    f"{replacement}.",
                    "warning",
                    node,
                    path=self.path,
                )
            )
        if name in CONTENT_CALLS:
            self._check_content_call(name, node)
        reviewable_calls = (
            ACTION_CALLS | RELATION_CALLS | ASSOCIATION_CALLS | SCAFFOLD_CALLS | BAYES_CALLS
        )
        if name in reviewable_calls and name != "observe":
            self._check_reasoning_call(name, node)
        if name == "register_prior":
            self._check_register_prior(node)
        if name in DISTRIBUTIONS:
            self._check_distribution_call(name, node)
        if name == "observe":
            self._check_observe(node)
        if name in ARTIFACT_CALLS:
            self._check_artifact_call(name, node)
        if name == "associate":
            self._check_associate(node)
        if name in SCAFFOLD_CALLS or name == "decompose":
            self._check_scaffold_call(name, node)
        if name in BAYES_CALLS:
            self._check_bayes_call(name, node)

        for arg in list(node.args) + [kw.value for kw in node.keywords if kw.value is not None]:
            self._collect_refs(arg)
        self.generic_visit(node)

    def _check_unimported_gaia_call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            return
        symbol = node.func.id
        if symbol not in ALL_KNOWN_CALLS or symbol in self.file_index.bound_names:
            return
        import_stmt = preferred_import_for_symbol(symbol)
        self.diagnostics.append(
            diagnostic(
                "GAIA015",
                f"{symbol}() looks like Gaia DSL but is not imported; add `{import_stmt}`.",
                "error",
                node.func,
                path=self.path,
            )
        )

    def _check_content_call(self, name: str, node: ast.Call) -> None:
        if not node.args or not _is_nonempty_string(node.args[0]):
            self.diagnostics.append(
                diagnostic(
                    "GAIA010",
                    f"{name}() should start with non-empty string content.",
                    "error",
                    node,
                    path=self.path,
                )
            )
        if name == "claim" and _keyword_present(node, "prior"):
            self.diagnostics.append(
                diagnostic(
                    "GAIA011",
                    "claim(prior=...) is a low-priority shortcut; prefer register_prior() "
                    "with a justification for auditable Gaia packages.",
                    "warning",
                    node,
                    path=self.path,
                )
            )
        if name in {"note", "question"} and _keyword_present(node, "prior"):
            self.diagnostics.append(
                diagnostic(
                    "GAIA013",
                    f"{name}() does not participate in belief propagation and cannot carry prior=.",
                    "error",
                    node,
                    path=self.path,
                )
            )
        if name == "claim":
            self._check_claim_shape(node)

    def _check_claim_shape(self, node: ast.Call) -> None:
        if _keyword_present(node, "tolerance"):
            tolerance_node = _keyword_value(node, "tolerance")
            tolerance = _literal_number(tolerance_node)
            if len(node.args) < 2:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA014",
                        "claim(tolerance=...) requires an equation proposition argument.",
                        "error",
                        tolerance_node or node,
                        path=self.path,
                    )
                )
            elif tolerance is not None and tolerance <= 0.0:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA014",
                        "claim(tolerance=...) must be a positive number.",
                        "error",
                        tolerance_node or node,
                        path=self.path,
                    )
                )
        if len(node.args) >= 2 and _keyword_present(node, "formula"):
            self.diagnostics.append(
                diagnostic(
                    "GAIA014",
                    "claim() received both a proposition argument and formula=; pick one.",
                    "error",
                    node,
                    path=self.path,
                )
            )

    def _check_reasoning_call(self, name: str, node: ast.Call) -> None:
        if not _keyword_string(node, "rationale"):
            self.diagnostics.append(
                diagnostic(
                    "GAIA012",
                    f"{name}() should include a non-empty rationale for reviewable reasoning.",
                    "warning",
                    node,
                    path=self.path,
                )
            )

    def _check_register_prior(self, node: ast.Call) -> None:
        if (
            node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            self.diagnostics.append(
                diagnostic(
                    "GAIA032",
                    "register_prior() must target the Claim object, not its label string.",
                    "error",
                    node.args[0],
                    path=self.path,
                )
            )

        value_node = node.args[1] if len(node.args) >= 2 else _keyword_value(node, "value")
        value = _literal_number(value_node)
        if (
            value_node is None
            or _literal_bad_number(value_node)
            or (value is not None and not (CROMWELL_EPS <= value <= 1.0 - CROMWELL_EPS))
        ):
            self.diagnostics.append(
                diagnostic(
                    "GAIA030",
                    "register_prior() requires a finite numeric probability inside Gaia "
                    f"Cromwell bounds [{CROMWELL_EPS}, {1.0 - CROMWELL_EPS}].",
                    "error",
                    value_node or node,
                    path=self.path,
                )
            )

        justification = _keyword_string(node, "justification")
        if not justification:
            self.diagnostics.append(
                diagnostic(
                    "GAIA031",
                    "register_prior() requires a non-empty justification keyword.",
                    "error",
                    node,
                    path=self.path,
                )
            )

        source_id = _keyword_value(node, "source_id")
        if source_id is not None and not _is_nonempty_string(source_id):
            self.diagnostics.append(
                diagnostic(
                    "GAIA034",
                    "register_prior() source_id must be a non-empty string.",
                    "error",
                    source_id,
                    path=self.path,
                )
            )

    def _check_distribution_call(self, name: str, node: ast.Call) -> None:
        rule = DISTRIBUTION_RULES[name]
        if not node.args or not _is_nonempty_string(node.args[0]):
            self.diagnostics.append(
                diagnostic(
                    "GAIA080",
                    f"{name}() should start with non-empty string content.",
                    "error",
                    node,
                    path=self.path,
                )
            )
        if len(node.args) > 1:
            self.diagnostics.append(
                diagnostic(
                    "GAIA081",
                    f"{name}() distribution parameters are keyword-only after content.",
                    "error",
                    node.args[1],
                    path=self.path,
                )
            )
        present = {keyword.arg for keyword in node.keywords if keyword.arg is not None}
        missing = [param for param in rule.required if param not in present]
        if missing:
            self.diagnostics.append(
                diagnostic(
                    "GAIA081",
                    f"{name}() is missing required parameter(s): {', '.join(missing)}.",
                    "error",
                    node,
                    path=self.path,
                )
            )
        for keyword in node.keywords:
            if keyword.arg in rule.positive and not _is_positive_literal(keyword.value):
                self.diagnostics.append(
                    diagnostic(
                        "GAIA082",
                        f"{name}() parameter {keyword.arg} must be a positive numeric scalar.",
                        "error",
                        keyword.value,
                        path=self.path,
                    )
                )
            if keyword.arg in rule.probabilities and not _is_probability_literal(keyword.value):
                self.diagnostics.append(
                    diagnostic(
                        "GAIA083",
                        f"{name}() parameter {keyword.arg} must be a probability in [0, 1].",
                        "error",
                        keyword.value,
                        path=self.path,
                    )
                )
            if keyword.arg in rule.integer_nonnegative and not _is_nonnegative_integer_literal(
                keyword.value
            ):
                self.diagnostics.append(
                    diagnostic(
                        "GAIA084",
                        f"{name}() parameter {keyword.arg} must be a non-negative integer.",
                        "error",
                        keyword.value,
                        path=self.path,
                    )
                )

    def _check_observe(self, node: ast.Call) -> None:
        target = node.args[0] if node.args else None
        is_measurement_target = self._is_distribution_expr(target) or self._is_variable_expr(target)
        has_value = _keyword_present(node, "value")
        has_error = _keyword_present(node, "error")
        if is_measurement_target:
            if not has_value:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA090",
                        "observe(distribution_or_variable, ...) requires value=.",
                        "error",
                        target or node,
                        path=self.path,
                    )
                )
            given = _keyword_value(node, "given")
            given_count = _literal_collection_length(given)
            if given_count is not None and given_count > 0:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA091",
                        "observe(distribution_or_variable, value=..., given=...) is not supported; "
                        "measurement events are unconditional.",
                        "error",
                        given,
                        path=self.path,
                    )
                )
        elif has_value or has_error:
            self.diagnostics.append(
                diagnostic(
                    "GAIA092",
                    "observe(..., value=..., error=...) only applies to Distribution "
                    "or Variable targets.",
                    "error",
                    _keyword_value(node, "value") or _keyword_value(node, "error") or node,
                    path=self.path,
                )
            )
        if _keyword_present(node, "source_refs"):
            self.diagnostics.append(
                diagnostic(
                    "GAIA093",
                    "observe(source_refs=...) is deprecated; put citation markers like [@Key] "
                    "in rationale or content.",
                    "warning",
                    _keyword_value(node, "source_refs") or node,
                    path=self.path,
                )
            )

    def _is_distribution_expr(self, node: ast.AST | None) -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Name) and node.id in self.file_index.distribution_names:
            return True
        return isinstance(node, ast.Call) and (
            self.file_index.imports.canonical_call_name(node.func) in DISTRIBUTIONS
        )

    def _is_variable_expr(self, node: ast.AST | None) -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Name) and node.id in self.file_index.variable_names:
            return True
        return isinstance(node, ast.Call) and (
            self.file_index.imports.canonical_call_name(node.func) == "Variable"
        )

    def _check_artifact_call(self, name: str, node: ast.Call) -> None:
        kind = "figure" if name == "figure" else _keyword_string(node, "kind")
        source = _keyword_string(node, "source")
        path = _keyword_string(node, "path")
        locator = _keyword_string(node, "locator")
        if kind not in ARTIFACT_KINDS:
            self.diagnostics.append(
                diagnostic(
                    "GAIA070",
                    "artifact kind must be one of: " + ", ".join(sorted(ARTIFACT_KINDS)) + ".",
                    "error",
                    _keyword_value(node, "kind") or node,
                    path=self.path,
                )
            )
        if not _keyword_present(node, "source") and not _keyword_present(node, "path"):
            self.diagnostics.append(
                diagnostic(
                    "GAIA073",
                    "artifact metadata requires at least one of source= or path=.",
                    "error",
                    node,
                    path=self.path,
                )
            )
        if path:
            parsed = PurePosixPath(path)
            if parsed.is_absolute() or ".." in parsed.parts:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA071",
                        "artifact path must be package-relative and must not escape "
                        "the package root.",
                        "error",
                        _keyword_value(node, "path") or node,
                        path=self.path,
                    )
                )
            elif self.package_index is not None and not (self.package_index.root / path).exists():
                self.diagnostics.append(
                    diagnostic(
                        "GAIA074",
                        f"artifact path {path!r} does not exist under the Gaia package root.",
                        "warning",
                        _keyword_value(node, "path") or node,
                        path=self.path,
                    )
                )
        if source and kind in ARTIFACT_LOCATOR_REQUIRED_WITH_SOURCE and not locator:
            self.diagnostics.append(
                diagnostic(
                    "GAIA072",
                    f"artifact kind {kind!r} requires locator= when source= is set.",
                    "error",
                    _keyword_value(node, "source") or node,
                    path=self.path,
                )
            )

    def _check_associate(self, node: ast.Call) -> None:
        p_a = _keyword_number(node, "p_a_given_b")
        p_b = _keyword_number(node, "p_b_given_a")
        if p_a is None or p_b is None or not (0.0 <= p_a <= 1.0 and 0.0 <= p_b <= 1.0):
            self.diagnostics.append(
                diagnostic(
                    "GAIA100",
                    "associate() requires p_a_given_b and p_b_given_a probabilities in [0, 1].",
                    "error",
                    node,
                    path=self.path,
                )
            )
        pattern = _keyword_string(node, "pattern")
        if pattern is not None and pattern not in ASSOCIATE_PATTERNS:
            self.diagnostics.append(
                diagnostic(
                    "GAIA101",
                    "associate() pattern must be one of: "
                    + ", ".join(sorted(ASSOCIATE_PATTERNS))
                    + ".",
                    "error",
                    _keyword_value(node, "pattern") or node,
                    path=self.path,
                )
            )
        if (
            pattern == "equal"
            and p_a is not None
            and p_b is not None
            and not (p_a > 0.5 and p_b > 0.5)
        ):
            self.diagnostics.append(
                diagnostic(
                    "GAIA101",
                    "associate(pattern='equal') requires both conditional probabilities > 0.5.",
                    "error",
                    _keyword_value(node, "pattern") or node,
                    path=self.path,
                )
            )
        if (
            pattern in {"contradict", "exclusive"}
            and p_a is not None
            and p_b is not None
            and not (p_a < 0.5 and p_b < 0.5)
        ):
            self.diagnostics.append(
                diagnostic(
                    "GAIA101",
                    f"associate(pattern={pattern!r}) requires both conditional "
                    "probabilities < 0.5.",
                    "error",
                    _keyword_value(node, "pattern") or node,
                    path=self.path,
                )
            )

    def _check_scaffold_call(self, name: str, node: ast.Call) -> None:
        if name == "candidate_relation":
            claims = _keyword_value(node, "claims")
            claims_count = _literal_collection_length(claims)
            if claims is None or (claims_count is not None and claims_count < 2):
                self.diagnostics.append(
                    diagnostic(
                        "GAIA102",
                        "candidate_relation() requires claims= with at least two entries.",
                        "error",
                        claims or node,
                        path=self.path,
                    )
                )
            pattern = _keyword_string(node, "pattern")
            if pattern is not None and pattern not in CANDIDATE_RELATION_PATTERNS:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA103",
                        "candidate_relation() pattern must be one of: "
                        + ", ".join(sorted(CANDIDATE_RELATION_PATTERNS))
                        + ".",
                        "error",
                        _keyword_value(node, "pattern") or node,
                        path=self.path,
                    )
                )
            if pattern == "contradict" and claims_count is not None and claims_count != 2:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA102",
                        "candidate_relation(pattern='contradict') requires exactly two claims.",
                        "error",
                        claims or node,
                        path=self.path,
                    )
                )
        elif name == "depends_on":
            given = _keyword_value(node, "given")
            if given is None or _is_empty_collection_or_none(given):
                self.diagnostics.append(
                    diagnostic(
                        "GAIA104",
                        "depends_on() requires a non-empty given= argument.",
                        "error",
                        given or node,
                        path=self.path,
                    )
                )
        elif name == "decompose":
            parts = _keyword_value(node, "parts")
            if parts is None or _literal_collection_length(parts) == 0:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA104",
                        "decompose() requires non-empty parts=.",
                        "error",
                        parts or node,
                        path=self.path,
                    )
                )
            if not _keyword_present(node, "formula"):
                self.diagnostics.append(
                    diagnostic(
                        "GAIA104",
                        "decompose() requires formula=.",
                        "error",
                        node,
                        path=self.path,
                    )
                )
        elif name == "materialize" and not _keyword_present(node, "by"):
            self.diagnostics.append(
                diagnostic(
                    "GAIA104",
                    "materialize() requires by=.",
                    "error",
                    node,
                    path=self.path,
                )
            )

    def _check_bayes_call(self, name: str, node: ast.Call) -> None:
        if name == "model":
            missing = [
                keyword
                for keyword in ("observable", "distribution")
                if not _keyword_present(node, keyword)
            ]
            if missing:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA110",
                        "bayes.model() requires observable= and distribution=.",
                        "error",
                        node,
                        path=self.path,
                    )
                )
        elif name == "compare":
            models = _keyword_value(node, "models")
            model_count = _literal_collection_length(models)
            if models is None or model_count == 0:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA111",
                        "bayes.compare() requires a non-empty models= list.",
                        "error",
                        models or node,
                        path=self.path,
                    )
                )
            exclusivity = _keyword_string(node, "exclusivity")
            if exclusivity is not None and exclusivity not in {
                "pairwise_contradiction",
                "exhaustive_pairwise_complement",
            }:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA111",
                        "bayes.compare() exclusivity must be 'pairwise_contradiction' "
                        "or 'exhaustive_pairwise_complement'.",
                        "error",
                        _keyword_value(node, "exclusivity") or node,
                        path=self.path,
                    )
                )
            if (
                exclusivity in {None, "exhaustive_pairwise_complement"}
                and model_count is not None
                and model_count > 2
            ):
                self.diagnostics.append(
                    diagnostic(
                        "GAIA111",
                        "bayes.compare() default exhaustive_pairwise_complement "
                        "currently supports at most two models.",
                        "error",
                        models or node,
                        path=self.path,
                    )
                )

    def _check_all(self, value: ast.AST, node: ast.AST) -> None:
        entries = self._all_entries(value, node)
        if entries is None:
            return
        seen: set[str] = set()
        known_exportable = set(self.file_index.exportable_names)
        if self.package_index is not None:
            known_exportable |= self.package_index.exportable_names
        for name, entry_node in entries:
            if name in seen:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA041",
                        f"Duplicate Gaia export {name!r} in __all__.",
                        "warning",
                        entry_node,
                        path=self.path,
                    )
                )
            seen.add(name)
            if name not in known_exportable:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA040",
                        f"__all__ exports {name!r}, but no local exportable Gaia Knowledge "
                        "binding with that name was found in this package.",
                        "error",
                        entry_node,
                        path=self.path,
                    )
                )

    def _all_entries(self, value: ast.AST, node: ast.AST) -> list[tuple[str, ast.AST]] | None:
        if isinstance(value, (ast.List, ast.Tuple)):
            entries: list[tuple[str, ast.AST]] = []
            for element in value.elts:
                if isinstance(element, ast.Starred) and _is_all_extension(element.value):
                    continue
                if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                    self.diagnostics.append(
                        diagnostic(
                            "GAIA042",
                            "__all__ entries should be literal strings.",
                            "error",
                            element,
                            path=self.path,
                        )
                    )
                    continue
                entries.append((element.value, element))
            return entries
        if (
            isinstance(value, ast.Call)
            and self.file_index.imports.canonical_call_name(value.func) == "export"
        ):
            entries = []
            for arg in value.args:
                if isinstance(arg, ast.Name):
                    entries.append((arg.id, arg))
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    entries.append((arg.value, arg))
                else:
                    self.diagnostics.append(
                        diagnostic(
                            "GAIA042",
                            "export() entries in __all__ should be names or literal "
                            "strings for static validation.",
                            "error",
                            arg,
                            path=self.path,
                        )
                    )
            return entries
        self.diagnostics.append(
            diagnostic(
                "GAIA042",
                "__all__ should be a static literal list or export(...) call so Gaia "
                "can validate exports.",
                "error",
                node,
                path=self.path,
            )
        )
        return None

    def _collect_refs(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for key in _extract_strict_refs(node.value):
                self.strict_refs.setdefault(key, node)

    def check_references(self) -> None:
        if not self.strict_refs:
            if self.package_index is None and self.path is not None:
                self._add_direct_reference_diagnostics()
            return
        known_refs = set(self.file_index.local_reference_names)
        if self.package_index is not None:
            known_refs |= self.package_index.local_reference_names
            known_refs |= self.package_index.reference_info.keys
        else:
            reference_info = _load_reference_info_for_path(self.path, known_refs)
            known_refs |= reference_info.keys
            self.diagnostics.extend(reference_info.diagnostics)
            self._added_reference_schema_diagnostics = True
        for key, node in sorted(self.strict_refs.items()):
            if key not in known_refs:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA050",
                        f"Strict Gaia reference [@{key}] is unresolved in local labels or "
                        "references.json.",
                        "error",
                        node,
                        path=self.path,
                    )
                )

    def _add_direct_reference_diagnostics(self) -> None:
        if self._added_reference_schema_diagnostics:
            return
        reference_info = _load_reference_info_for_path(
            self.path,
            self.file_index.local_reference_names,
        )
        self.diagnostics.extend(reference_info.diagnostics)
        self._added_reference_schema_diagnostics = True


def _index_tree(tree: ast.Module) -> _FileIndex:
    imports = _ImportContext.from_tree(tree)
    index = _FileIndex(imports=imports, bound_names=_top_level_bound_names(tree))
    for node in tree.body:
        value = _assignment_value(node)
        if not isinstance(value, ast.Call):
            continue
        name = imports.canonical_call_name(value.func)
        if name is None:
            continue
        label = _keyword_string(value, "label")
        if label:
            index.label_names.add(label)
        targets = set(_assignment_target_names(node))
        if name in EXPORTABLE_KNOWLEDGE_CALLS:
            index.exportable_names.update(targets)
            index.label_names.update(targets)
        elif name in DISTRIBUTIONS:
            index.distribution_names.update(targets)
        elif name == "Variable":
            index.variable_names.update(targets)
        elif name == "Domain":
            index.domain_names.update(targets)
    return index


def _check_package_structure(root: Path) -> tuple[dict[str, Any], Path | None, list[Diagnostic]]:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return {}, None, []
    try:
        config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, None, [
            _path_diagnostic(
                "GAIA063",
                f"pyproject.toml is not valid TOML: {exc}",
                "error",
                pyproject,
            )
        ]
    project_config = config.get("project", {})
    project_name = project_config.get("name") if isinstance(project_config, dict) else None
    gaia_section = (
        config.get("tool", {}).get("gaia", {})
        if isinstance(config.get("tool"), dict)
        else {}
    )
    should_validate = bool(gaia_section) or (
        isinstance(project_name, str) and project_name.endswith("-gaia")
    )
    if not should_validate:
        return config, None, []
    if not isinstance(gaia_section, dict) or gaia_section.get("type") != "knowledge-package":
        return config, None, [
            _path_diagnostic(
                "GAIA064",
                "Gaia packages require [tool.gaia].type = 'knowledge-package'.",
                "error",
                pyproject,
            )
        ]
    diagnostics: list[Diagnostic] = []
    if not isinstance(project_name, str) or not project_name:
        diagnostics.append(
            _path_diagnostic("GAIA065", "[project].name is required.", "error", pyproject)
        )
        return config, None, diagnostics
    version = project_config.get("version") if isinstance(project_config, dict) else None
    if not isinstance(version, str) or not version:
        diagnostics.append(
            _path_diagnostic("GAIA065", "[project].version is required.", "error", pyproject)
        )
    gaia_version = _declared_gaia_version(config, project_name)
    if gaia_version is not None:
        normalized_version = gaia_version.removeprefix("v")
        if not any(
            normalized_version == series or normalized_version.startswith(f"{series}.")
            for series in SUPPORTED_GAIA_SERIES
        ):
            diagnostics.append(
                _path_diagnostic(
                    "GAIA120",
                    f"Gaia language version {gaia_version!r} is not covered by this "
                    "static rule catalog.",
                    "error",
                    pyproject,
                )
            )
        elif not normalized_version.startswith(CURRENT_GAIA_SERIES):
            diagnostics.append(
                _path_diagnostic(
                    "GAIA121",
                    f"Gaia language version {gaia_version!r} uses a legacy authoring "
                    "series; compatibility aliases are linted but v0.5 is preferred.",
                    "warning",
                    pyproject,
                )
            )
    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    candidates = [root / import_name, root / "src" / import_name]
    source_root = next((candidate for candidate in candidates if candidate.exists()), None)
    if source_root is None:
        diagnostics.append(
            _path_diagnostic(
                "GAIA066",
                f"Gaia package source directory {import_name!r} was not found at "
                f"{import_name}/ or src/{import_name}/.",
                "error",
                pyproject,
            )
        )
        return config, None, diagnostics
    init_py = source_root / "__init__.py"
    if not init_py.exists():
        diagnostics.append(
            _path_diagnostic(
                "GAIA066",
                f"Gaia package source entrypoint is missing: {init_py}.",
                "error",
                init_py,
            )
        )
    return config, source_root, diagnostics


def _declared_gaia_version(config: dict[str, Any], project_name: Any) -> str | None:
    tool_config = config.get("tool", {}) if isinstance(config.get("tool"), dict) else {}
    gaia_section = tool_config.get("gaia", {}) if isinstance(tool_config, dict) else {}
    if isinstance(gaia_section, dict):
        for key in ("language_version", "gaia_version", "version"):
            value = gaia_section.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(project_name, str):
        match = re.search(r"(?:^|-|_)v?(0)[._-]([0-9]+)(?:-|_|$)", project_name)
        if match:
            return f"{match.group(1)}.{match.group(2)}"
    return None


def _load_reference_info_for_path(
    path: Path | None,
    local_reference_names: set[str],
) -> _ReferenceInfo:
    if path is None:
        return _ReferenceInfo()
    for directory in [path.parent, *path.parent.parents]:
        candidate = directory / "references.json"
        if candidate.exists():
            return _load_references_at(candidate, local_reference_names)
        if (directory / ".git").exists():
            break
    return _ReferenceInfo()


def _load_references_at(path: Path, local_reference_names: set[str]) -> _ReferenceInfo:
    info = _ReferenceInfo()
    if not path.exists():
        return info
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        info.diagnostics.append(
            _path_diagnostic(
                "GAIA067",
                f"references.json is not valid JSON: {exc.msg} "
                f"(line {exc.lineno}, col {exc.colno}).",
                "error",
                path,
            )
        )
        return info
    if not isinstance(data, dict):
        info.diagnostics.append(
            _path_diagnostic(
                "GAIA067",
                "references.json must be an object keyed by citation key, "
                f"got {type(data).__name__}.",
                "error",
                path,
            )
        )
        return info
    for key, entry in data.items():
        if not isinstance(key, str) or not CITATION_KEY_RE.match(key):
            info.diagnostics.append(
                _path_diagnostic(
                    "GAIA067",
                    f"reference key {key!r} cannot be cited via Gaia @-syntax.",
                    "error",
                    path,
                )
            )
            continue
        info.keys.add(key)
        if key in local_reference_names:
            info.diagnostics.append(
                _path_diagnostic(
                    "GAIA068",
                    f"reference key {key!r} collides with a local Gaia label or binding.",
                    "error",
                    path,
                )
            )
        if not isinstance(entry, dict):
            info.diagnostics.append(
                _path_diagnostic(
                    "GAIA067",
                    f"reference entry {key!r} must be an object, got {type(entry).__name__}.",
                    "error",
                    path,
                )
            )
            continue
        entry_type = entry.get("type")
        if not isinstance(entry_type, str) or entry_type not in CSL_TYPES:
            info.diagnostics.append(
                _path_diagnostic(
                    "GAIA067",
                    f"reference entry {key!r} has invalid CSL type {entry_type!r}.",
                    "error",
                    path,
                )
            )
        title = entry.get("title")
        if not isinstance(title, str) or not title:
            info.diagnostics.append(
                _path_diagnostic(
                    "GAIA067",
                    f"reference entry {key!r} requires a non-empty title string.",
                    "error",
                    path,
                )
            )
    return info


def _is_gaia_import_module(module: str) -> bool:
    return module in GAIA_MODULES or any(
        module == prefix or module.startswith(f"{prefix}.") for prefix in GAIA_MODULE_PREFIXES
    )


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _assignment_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.Assign):
        return node.value
    if isinstance(node, ast.AnnAssign):
        return node.value
    return None


def _assignment_target_names(node: ast.AST) -> list[str]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)
    names: list[str] = []
    for target in targets:
        names.extend(_target_names(target))
    return names


def _assignment_target_nodes(node: ast.AST) -> list[ast.AST]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets.append(node.target)
    return targets


def _target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    return []


def _is_all_extension(node: ast.AST) -> bool:
    dotted = _dotted_name(node)
    return dotted == "__all__" or dotted.endswith(".__all__")


def _is_nonempty_string(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and bool(node.value.strip())
    )


def _literal_number(node: ast.AST | None) -> float | None:
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
        and not isinstance(node.operand.value, bool)
    ):
        value = float(node.operand.value)
        if isinstance(node.op, ast.USub):
            value = -value
        if math.isfinite(value):
            return value
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(
        node.value, bool
    ):
        value = float(node.value)
        if math.isfinite(value):
            return value
    return None


def _is_positive_literal(node: ast.AST) -> bool:
    value = _literal_number(node)
    return value is None or value > 0.0 if not _literal_bad_number(node) else False


def _is_probability_literal(node: ast.AST) -> bool:
    value = _literal_number(node)
    return value is None or 0.0 <= value <= 1.0 if not _literal_bad_number(node) else False


def _is_nonnegative_integer_literal(node: ast.AST) -> bool:
    if _literal_bad_number(node):
        return False
    value = _literal_number(node)
    if value is None:
        return True
    return value.is_integer() and value >= 0


def _literal_bad_number(node: ast.AST) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _literal_bad_number(node.operand)
    if not isinstance(node, ast.Constant):
        return False
    return isinstance(node.value, bool) or (
        not isinstance(node.value, (int, float)) or not math.isfinite(float(node.value))
    )


def _keyword_value(node: ast.Call, name: str) -> ast.AST | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _keyword_present(node: ast.Call, name: str) -> bool:
    return _keyword_value(node, name) is not None


def _keyword_string(node: ast.Call, name: str) -> str | None:
    value_node = _keyword_value(node, name)
    if isinstance(value_node, ast.Constant):
        value = value_node.value
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _keyword_number(node: ast.Call, name: str) -> float | None:
    return _literal_number(_keyword_value(node, name))


def _literal_collection_length(node: ast.AST | None) -> int | None:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return len(node.elts)
    return None


def _is_empty_collection_or_none(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    length = _literal_collection_length(node)
    return length == 0


def _extract_strict_refs(text: str) -> list[str]:
    keys: list[str] = []
    for group in BRACKET_GROUP_RE.finditer(text):
        body = group.group(1)
        keys.extend(match.group(1) for match in INNER_KEY_RE.finditer(body))
    return keys


def _path_diagnostic(code: str, message: str, severity: str, path: Path) -> Diagnostic:
    return Diagnostic(
        code=code,
        message=message,
        severity=severity,
        line=1,
        column=1,
        file=str(path),
    )


def _dedupe_ranges(ranges: list[dict[str, int | str]]) -> list[dict[str, int | str]]:
    seen: set[tuple[int, int, str]] = set()
    out: list[dict[str, int | str]] = []
    for item in sorted(ranges, key=lambda value: (int(value["startLine"]), int(value["endLine"]))):
        key = (int(item["startLine"]), int(item["endLine"]), str(item.get("kind", "")))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _offset_range(text: str, start: int, end: int) -> dict[str, dict[str, int]]:
    line_starts = [0]
    for match in re.finditer("\n", text):
        line_starts.append(match.end())

    def position(offset: int) -> dict[str, int]:
        line = 0
        for index, line_start in enumerate(line_starts):
            if line_start > offset:
                break
            line = index
        return {"line": line, "character": offset - line_starts[line]}

    return {"start": position(start), "end": position(end)}


def _reference_target(path: Path | None, key: str) -> str | None:
    if path is None:
        return None
    reference_info = _load_reference_info_for_path(path, set())
    if key in reference_info.keys:
        for directory in [path.parent, *path.parent.parents]:
            candidate = directory / "references.json"
            if candidate.exists():
                return candidate.as_uri()
            if (directory / ".git").exists():
                break
    root = _find_gaia_package_root(path)
    if root is not None:
        for item in _symbol_definitions_for_scope(path):
            if item["name"] == key or item.get("label") == key:
                return str(item["uri"])
    return None


def _artifact_path_links(text: str, path: Path) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    root = _find_gaia_package_root(path) or path.parent
    links: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "path" or not isinstance(keyword.value, ast.Constant):
                continue
            value = keyword.value.value
            if not isinstance(value, str) or not value:
                continue
            target = root / value
            if not target.exists():
                continue
            start_line = int(getattr(keyword.value, "lineno", 1) or 1)
            start_column = int(getattr(keyword.value, "col_offset", 0) or 0)
            content_start = _string_content_start_offset(text, keyword.value)
            links.append(
                {
                    "target": target.as_uri(),
                    "tooltip": f"Open Gaia artifact {value}",
                    "range": {
                        "start": {
                            "line": start_line - 1,
                            "character": start_column + content_start,
                        },
                        "end": {
                            "line": start_line - 1,
                            "character": start_column + content_start + len(value),
                        },
                    },
                }
            )
    return links


def _semantic_token(
    line: int,
    character: int,
    length: int,
    token_type: str,
    modifiers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "line": line - 1,
        "character": character,
        "length": length,
        "tokenType": token_type,
        "tokenModifiers": modifiers or [],
    }


def _call_name_location(func: ast.AST) -> tuple[int, int, int] | None:
    if isinstance(func, ast.Name):
        return int(func.lineno), int(func.col_offset), len(func.id)
    if isinstance(func, ast.Attribute):
        return (
            int(func.lineno),
            int(func.end_col_offset or func.col_offset) - len(func.attr),
            len(func.attr),
        )
    return None


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    return sorted(
        diagnostics,
        key=lambda item: (item.file or "", item.line, item.column, item.code),
    )
