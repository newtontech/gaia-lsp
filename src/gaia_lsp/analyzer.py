"""Static Gaia Lang Python DSL analysis.

The analyzer intentionally uses Python's AST instead of importing target modules.
Gaia packages are executable Python projects, so editor diagnostics must not run
author code just to find obvious DSL mistakes.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .diagnostics import Diagnostic, diagnostic

GAIA_MODULES = {
    "gaia.engine.lang",
    "gaia.engine.lang.dsl",
}

CONTENT_CALLS = {"claim", "note", "question"}
ACTION_CALLS = {"derive", "observe", "compute", "infer", "decompose"}
RELATION_CALLS = {"equal", "contradict", "exclusive", "associate"}
SCAFFOLD_CALLS = {"depends_on", "candidate_relation", "materialize"}
COMPOSITION_CALLS = {"compose", "composition"}
DISTRIBUTIONS = {
    "Normal",
    "LogNormal",
    "Beta",
    "Exponential",
    "Gamma",
    "StudentT",
    "Cauchy",
    "ChiSquared",
    "Binomial",
    "Poisson",
}
KNOWLEDGE_CALLS = (
    CONTENT_CALLS
    | ACTION_CALLS
    | RELATION_CALLS
    | SCAFFOLD_CALLS
    | COMPOSITION_CALLS
    | {"artifact", "figure"}
)
DEPRECATED_CALLS = {"context": "note", "setting": "note"}
DEPRECATED_RELATIONS = {"contradiction": "contradict"}
STRICT_REF_RE = re.compile(r"\[@([A-Za-z_][A-Za-z0-9_.:-]*)\]")


@dataclass(frozen=True)
class SymbolInfo:
    detail: str
    documentation: str


SYMBOLS: dict[str, SymbolInfo] = {
    "claim": SymbolInfo(
        "claim(content, proposition=None, *, background=None, prior=None, **metadata)",
        "Declare a falsifiable Gaia claim. Claims are the only knowledge type that "
        "participates directly in probability and belief propagation.",
    ),
    "note": SymbolInfo(
        'note(content, *, title=None, format="markdown", **metadata)',
        "Declare non-probabilistic context such as definitions, setup, or source notes.",
    ),
    "question": SymbolInfo(
        "question(content, *, title=None, **metadata)",
        "Declare an open inquiry. Questions do not carry probability.",
    ),
    "derive": SymbolInfo(
        "derive(conclusion, *, given=(), background=None, rationale='', label=None)",
        "Record a logical derivation from premises to a conclusion claim.",
    ),
    "observe": SymbolInfo(
        "observe(conclusion, *, value=..., error=None, given=(), rationale='', label=None)",
        "Record an empirical observation. Zero-premise claim observations pin the claim.",
    ),
    "compute": SymbolInfo(
        "compute(conclusion, *, given=(), rationale='', label=None)",
        "Record a computational step that supports a conclusion.",
    ),
    "infer": SymbolInfo(
        "infer(conclusion, *, given=(), rationale='', label=None)",
        "Record an inference action over Gaia claims or formulas.",
    ),
    "equal": SymbolInfo(
        "equal(a, b, *, rationale='', label=None)",
        "Declare two claims equivalent and return a reviewable relation helper claim.",
    ),
    "contradict": SymbolInfo(
        "contradict(a, b, *, rationale='', label=None)",
        "Declare two claims contradictory and return a reviewable relation helper claim.",
    ),
    "exclusive": SymbolInfo(
        "exclusive(a, b, *, rationale='', label=None)",
        "Declare two claims as a closed binary partition.",
    ),
    "associate": SymbolInfo(
        "associate(a, b, *, rationale='', label=None)",
        "Declare a reviewable association relation between claims.",
    ),
    "register_prior": SymbolInfo(
        "register_prior(claim, value, *, justification, source_id='user_priors')",
        "Attach an auditable external prior probability to an explicit Claim object.",
    ),
    "depends_on": SymbolInfo(
        "depends_on(target, dependency, *, rationale='', label=None)",
        "Record a scaffold dependency for review and package structure.",
    ),
    "candidate_relation": SymbolInfo(
        "candidate_relation(a, b, *, relation_type, rationale='', label=None)",
        "Record a candidate relation that may be materialized after review.",
    ),
    "materialize": SymbolInfo(
        "materialize(candidate, *, rationale='', label=None)",
        "Promote a scaffold candidate into explicit Gaia knowledge.",
    ),
    "compose": SymbolInfo(
        "compose(*actions, label=None)",
        "Compose Gaia actions into a reusable reasoning structure.",
    ),
    "composition": SymbolInfo(
        "composition(*actions, label=None)",
        "Declare an action composition object.",
    ),
}

for _distribution in sorted(DISTRIBUTIONS):
    SYMBOLS[_distribution] = SymbolInfo(
        f"{_distribution}(label, **parameters)",
        f"Declare a Gaia continuous/discrete distribution with the {_distribution} factory.",
    )


def analyze_path(path: Path) -> list[Diagnostic]:
    """Analyze one Python file or a directory of Python files."""

    path = path.resolve()
    if path.is_dir():
        diagnostics: list[Diagnostic] = []
        for child in sorted(path.rglob("*.py")):
            if any(part.startswith(".") for part in child.relative_to(path).parts):
                continue
            diagnostics.extend(analyze_path(child))
        return diagnostics
    return analyze_text(path.read_text(encoding="utf-8"), path=path)


def analyze_text(text: str, *, path: Path | None = None) -> list[Diagnostic]:
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

    collector = _Analyzer(path)
    collector.visit(tree)
    collector.check_references()
    return sorted(collector.diagnostics, key=lambda item: (item.line, item.column, item.code))


def completion_items() -> list[dict[str, str]]:
    """Return editor completion entries for the Gaia authoring surface."""

    items = []
    for label, info in sorted(SYMBOLS.items()):
        items.append({"label": label, "detail": info.detail, "documentation": info.documentation})
    return items


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
    symbols: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        call = _assigned_call(node)
        if call is None or _call_name(call.func) not in KNOWLEDGE_CALLS:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                symbols.append(
                    {
                        "name": target.id,
                        "kind": _call_name(call.func),
                        "line": node.lineno,
                        "column": node.col_offset + 1,
                    }
                )
    return symbols


class _Analyzer(ast.NodeVisitor):
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.diagnostics: list[Diagnostic] = []
        self.gaia_aliases: set[str] = set()
        self.knowledge_names: set[str] = set()
        self.label_names: set[str] = set()
        self.strict_refs: dict[str, ast.AST] = {}

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module in GAIA_MODULES:
            for alias in node.names:
                self.gaia_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            if alias.name in GAIA_MODULES:
                self.gaia_aliases.add(alias.asname or alias.name.rsplit(".", 1)[-1])
        self.generic_visit(node)

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

        call = _assigned_call(node)
        if call is not None and _call_name(call.func) in KNOWLEDGE_CALLS:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.knowledge_names.add(target.id)
            label = _keyword_string(call, "label")
            if label:
                self.label_names.add(label)

        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                self._check_all(node.value, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        name = _call_name(node.func)
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
        if name in CONTENT_CALLS:
            self._check_content_call(name, node)
        if name in ACTION_CALLS | RELATION_CALLS and name not in {"observe"}:
            self._check_reasoning_call(name, node)
        if name == "register_prior":
            self._check_register_prior(node)

        for arg in list(node.args) + [kw.value for kw in node.keywords if kw.value is not None]:
            self._collect_refs(arg)
        self.generic_visit(node)

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
        if name == "claim" and _keyword_number(node, "prior") is not None:
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

        value_node = node.args[1] if len(node.args) >= 2 else None
        value = _literal_number(value_node)
        if value_node is None or value is None or not (0.0 < value < 1.0):
            self.diagnostics.append(
                diagnostic(
                    "GAIA030",
                    "register_prior() requires a numeric probability strictly between 0 and 1.",
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

    def _check_all(self, value: ast.AST, node: ast.AST) -> None:
        if not isinstance(value, (ast.List, ast.Tuple)):
            self.diagnostics.append(
                diagnostic(
                    "GAIA042",
                    "__all__ should be a static literal list so Gaia can validate exports.",
                    "warning",
                    node,
                    path=self.path,
                )
            )
            return
        seen: set[str] = set()
        for element in value.elts:
            if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                self.diagnostics.append(
                    diagnostic(
                        "GAIA042",
                        "__all__ entries should be literal strings.",
                        "warning",
                        element,
                        path=self.path,
                    )
                )
                continue
            name = element.value
            if name in seen:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA041",
                        f"Duplicate Gaia export {name!r} in __all__.",
                        "warning",
                        element,
                        path=self.path,
                    )
                )
            seen.add(name)
            if name not in self.knowledge_names:
                self.diagnostics.append(
                    diagnostic(
                        "GAIA040",
                        f"__all__ exports {name!r}, but no local Gaia Knowledge binding "
                        "with that name was found in this module.",
                        "warning",
                        element,
                        path=self.path,
                    )
                )

    def _collect_refs(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for match in STRICT_REF_RE.finditer(node.value):
                self.strict_refs.setdefault(match.group(1), node)

    def check_references(self) -> None:
        if not self.strict_refs:
            return
        known_refs = (
            set(self.knowledge_names) | set(self.label_names) | _load_reference_keys(self.path)
        )
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


def _assigned_call(node: ast.Assign) -> ast.Call | None:
    return node.value if isinstance(node.value, ast.Call) else None


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_nonempty_string(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and bool(node.value.strip())
    )


def _literal_number(node: ast.AST | None) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(
        node.value, bool
    ):
        return float(node.value)
    return None


def _keyword_string(node: ast.Call, name: str) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _keyword_number(node: ast.Call, name: str) -> float | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return _literal_number(keyword.value)
    return None


def _load_reference_keys(path: Path | None) -> set[str]:
    if path is None:
        return set()
    for directory in [path.parent, *path.parent.parents]:
        candidate = directory / "references.json"
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return set()
            if isinstance(data, dict):
                return {key for key in data if isinstance(key, str)}
            return set()
        if (directory / ".git").exists():
            break
    return set()
