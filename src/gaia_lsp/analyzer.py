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
    DEPRECATED_CALLS,
    DEPRECATED_RELATIONS,
    DEPRECATED_STRATEGIES,
    DISTRIBUTION_RULES,
    DISTRIBUTIONS,
    DOCUMENT_SYMBOL_CALLS,
    EXPORTABLE_KNOWLEDGE_CALLS,
    RELATION_CALLS,
    SCAFFOLD_CALLS,
    SYMBOLS,
)

GAIA_MODULES = {
    "gaia.engine.bayes",
    "gaia.engine.bayes.dsl",
    "gaia.engine.lang",
    "gaia.engine.lang.dsl",
}
GAIA_MODULE_PREFIXES = (
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


def completion_items() -> list[dict[str, str]]:
    """Return editor completion entries for the Gaia authoring surface."""

    return [
        {"label": label, "detail": info.detail, "documentation": info.documentation}
        for label, info in sorted(SYMBOLS.items())
    ]


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
            if given is not None and not _is_empty_collection_or_none(given):
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
        if not source and not path:
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
            if claims_count is None or claims_count < 2:
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
                        "warning",
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
                            "warning",
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
                            "warning",
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
                "warning",
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
    index = _FileIndex(imports=imports)
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
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
        node.value, bool
    ):
        return node.value >= 0
    if isinstance(node, ast.Constant) and isinstance(node.value, float):
        return node.value.is_integer() and node.value >= 0
    return True


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


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    return sorted(
        diagnostics,
        key=lambda item: (item.file or "", item.line, item.column, item.code),
    )
