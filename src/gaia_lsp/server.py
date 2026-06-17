"""pygls server wiring for gaia-lsp."""

from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from . import __version__
from .analyzer import (
    SEMANTIC_TOKEN_MODIFIERS,
    SEMANTIC_TOKEN_TYPES,
    analyze_text,
    completion_items,
    definition_at,
    document_links,
    document_symbols,
    folding_ranges,
    hover_at,
    references_at,
    rename_edits_at,
    semantic_tokens,
    workspace_symbols,
)
from .diagnostics import Diagnostic
from .rules import explain_topic

SERVER_NAME = "gaia-lsp"


def _load_language_server() -> type[Any]:
    try:
        return cast(type[Any], import_module("pygls.server").LanguageServer)
    except ImportError:
        return cast(type[Any], import_module("pygls.lsp.server").LanguageServer)


def _path_from_uri(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


def _to_lsp_diagnostic(item: Diagnostic) -> Any:
    from lsprotocol.types import Diagnostic as LspDiagnostic
    from lsprotocol.types import DiagnosticSeverity, Position, Range

    severity_map = {
        "error": DiagnosticSeverity.Error,
        "warning": DiagnosticSeverity.Warning,
        "information": DiagnosticSeverity.Information,
        "hint": DiagnosticSeverity.Hint,
    }
    payload = item.to_json()
    start = payload["range"]["start"]
    end = payload["range"]["end"]
    return LspDiagnostic(
        range=Range(
            start=Position(line=start["line"], character=start["character"]),
            end=Position(line=end["line"], character=end["character"]),
        ),
        severity=severity_map.get(item.severity, DiagnosticSeverity.Warning),
        code=item.code,
        source=item.source,
        message=item.message,
    )


def _register(server: Any, feature_name: str) -> Any:
    return server.feature(feature_name)


def _line_at(text: str, line: int) -> str:
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return ""
    return lines[line]


def _function_name_before_call(text: str, line: int, character: int) -> str | None:
    current = _line_at(text, line)[:character]
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\([^()]*$", current)
    return match.group(1) if match else None


def _signature_parameters(detail: str) -> list[str]:
    start = detail.find("(")
    end = detail.rfind(")")
    if start < 0 or end <= start:
        return []
    return [item.strip() for item in detail[start + 1 : end].split(",") if item.strip()]


def _active_parameter_index(text: str, line: int, character: int) -> int:
    current = _line_at(text, line)[:character]
    open_paren = current.rfind("(")
    if open_paren < 0:
        return 0
    return len(current[open_paren + 1 :].split(",")) - 1


def _suggested_import_from_message(message: str) -> str | None:
    match = re.search(r"add `([^`]+)`", message)
    return match.group(1) if match else None


def _import_insertion_line(text: str) -> int:
    lines = text.splitlines()
    index = 0
    if lines and lines[0].startswith(('"""', "'''")):
        index = 1
        while index < len(lines) and not lines[index].strip().endswith(('"""', "'''")):
            index += 1
        index = min(index + 1, len(lines))
    while index < len(lines) and (
        not lines[index].strip()
        or lines[index].startswith("import ")
        or lines[index].startswith("from ")
    ):
        index += 1
    return index


def _range_from_payload(payload: dict[str, Any]) -> Any:
    from lsprotocol.types import Position, Range

    start = payload["start"]
    end = payload["end"]
    return Range(
        start=Position(line=int(start["line"]), character=int(start["character"])),
        end=Position(line=int(end["line"]), character=int(end["character"])),
    )


def _semantic_tokens_data(tokens: list[dict[str, Any]]) -> list[int]:
    data: list[int] = []
    previous_line = 0
    previous_character = 0
    for token in sorted(tokens, key=lambda item: (item["line"], item["character"])):
        line = int(token["line"])
        character = int(token["character"])
        delta_line = line - previous_line
        delta_start = character - previous_character if delta_line == 0 else character
        token_type = SEMANTIC_TOKEN_TYPES.index(str(token["tokenType"]))
        modifier_bits = 0
        for modifier in token.get("tokenModifiers", []):
            if modifier in SEMANTIC_TOKEN_MODIFIERS:
                modifier_bits |= 1 << SEMANTIC_TOKEN_MODIFIERS.index(str(modifier))
        data.extend([delta_line, delta_start, int(token["length"]), token_type, modifier_bits])
        previous_line = line
        previous_character = character
    return data


def create_server(name: str = SERVER_NAME, version: str = __version__) -> Any:
    from lsprotocol.types import (
        COMPLETION_ITEM_RESOLVE,
        TEXT_DOCUMENT_CODE_ACTION,
        TEXT_DOCUMENT_COMPLETION,
        TEXT_DOCUMENT_DEFINITION,
        TEXT_DOCUMENT_DID_CHANGE,
        TEXT_DOCUMENT_DID_OPEN,
        TEXT_DOCUMENT_DOCUMENT_LINK,
        TEXT_DOCUMENT_DOCUMENT_SYMBOL,
        TEXT_DOCUMENT_FOLDING_RANGE,
        TEXT_DOCUMENT_HOVER,
        TEXT_DOCUMENT_REFERENCES,
        TEXT_DOCUMENT_RENAME,
        TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
        TEXT_DOCUMENT_SIGNATURE_HELP,
        WORKSPACE_SYMBOL,
        CodeAction,
        CodeActionKind,
        CodeActionParams,
        CompletionItem,
        CompletionList,
        CompletionParams,
        DefinitionParams,
        DidChangeTextDocumentParams,
        DidOpenTextDocumentParams,
        DocumentLink,
        DocumentLinkParams,
        DocumentSymbol,
        DocumentSymbolParams,
        FoldingRange,
        FoldingRangeParams,
        Hover,
        HoverParams,
        Location,
        MarkupContent,
        MarkupKind,
        ParameterInformation,
        Position,
        Range,
        ReferenceParams,
        RenameParams,
        SemanticTokens,
        SemanticTokensParams,
        SignatureHelp,
        SignatureHelpParams,
        SignatureInformation,
        SymbolKind,
        TextEdit,
        WorkspaceEdit,
        WorkspaceSymbol,
        WorkspaceSymbolParams,
    )

    language_server = _load_language_server()(name, version)
    language_server.documents_cache = {}  # type: ignore[attr-defined]

    def publish(uri: str, text: str) -> None:
        path = _path_from_uri(uri)
        diagnostics = [_to_lsp_diagnostic(item) for item in analyze_text(text, path=path)]
        language_server.publish_diagnostics(uri, diagnostics)

    def text_for_uri(uri: str) -> str:
        cached = language_server.documents_cache.get(uri)  # type: ignore[attr-defined]
        if isinstance(cached, str):
            return cached
        path = _path_from_uri(uri)
        if path is None or not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def to_location(item: dict[str, Any]) -> Location:
        line = max(int(item.get("line", 1)) - 1, 0)
        character = max(int(item.get("column", 1)) - 1, 0)
        end_line = max(int(item.get("endLine", item.get("line", 1))) - 1, line)
        end_character = max(
            int(item.get("endColumn", item.get("column", 1) + len(str(item.get("name", "")))))
            - 1,
            character + 1,
        )
        return Location(
            uri=str(item.get("uri") or Path(str(item["file"])).as_uri()),
            range=Range(
                start=Position(line=line, character=character),
                end=Position(line=end_line, character=end_character),
            ),
        )

    @_register(language_server, TEXT_DOCUMENT_DID_OPEN)
    def did_open(params: DidOpenTextDocumentParams) -> None:
        uri = params.text_document.uri
        text = params.text_document.text
        language_server.documents_cache[uri] = text  # type: ignore[attr-defined]
        publish(uri, text)

    @_register(language_server, TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: DidChangeTextDocumentParams) -> None:
        uri = params.text_document.uri
        if not params.content_changes:
            return
        text = params.content_changes[-1].text
        language_server.documents_cache[uri] = text  # type: ignore[attr-defined]
        publish(uri, text)

    @_register(language_server, TEXT_DOCUMENT_COMPLETION)
    def completion(params: CompletionParams) -> CompletionList:
        path = _path_from_uri(params.text_document.uri)
        return CompletionList(
            is_incomplete=False,
            items=[
                CompletionItem(
                    label=item["label"],
                    detail=item["detail"],
                    documentation=item["documentation"],
                )
                for item in completion_items(path)
            ],
        )

    @_register(language_server, COMPLETION_ITEM_RESOLVE)
    def completion_resolve(item: CompletionItem) -> CompletionItem:
        return item

    @_register(language_server, TEXT_DOCUMENT_HOVER)
    def hover(params: HoverParams) -> Hover | None:
        uri = params.text_document.uri
        text = language_server.documents_cache.get(uri, "")  # type: ignore[attr-defined]
        contents = hover_at(text, params.position.line, params.position.character)
        if not contents:
            return None
        return Hover(contents=MarkupContent(kind=MarkupKind.Markdown, value=contents))

    @_register(language_server, TEXT_DOCUMENT_DEFINITION)
    def definition(params: DefinitionParams) -> list[Location]:
        path = _path_from_uri(params.text_document.uri)
        if path is None or not path.exists():
            return []
        return [
            to_location(item)
            for item in definition_at(path, params.position.line, params.position.character)
        ]

    @_register(language_server, TEXT_DOCUMENT_REFERENCES)
    def references(params: ReferenceParams) -> list[Location]:
        path = _path_from_uri(params.text_document.uri)
        if path is None or not path.exists():
            return []
        return [
            to_location(item)
            for item in references_at(path, params.position.line, params.position.character)
        ]

    @_register(language_server, TEXT_DOCUMENT_SIGNATURE_HELP)
    def signature_help(params: SignatureHelpParams) -> SignatureHelp | None:
        text = text_for_uri(params.text_document.uri)
        symbol = _function_name_before_call(
            text,
            params.position.line,
            params.position.character,
        )
        if not symbol:
            return None
        try:
            payload = explain_topic(symbol)
        except KeyError:
            return None
        symbol_payload = payload.get("symbol")
        if payload.get("kind") != "symbol" or not isinstance(symbol_payload, dict):
            return None
        detail = str(symbol_payload.get("detail") or "")
        if not detail:
            return None
        documentation = symbol_payload.get("documentation")
        signature = SignatureInformation(
            label=detail,
            documentation=(
                MarkupContent(kind=MarkupKind.Markdown, value=str(documentation))
                if documentation
                else None
            ),
            parameters=[ParameterInformation(label=item) for item in _signature_parameters(detail)],
        )
        return SignatureHelp(
            signatures=[signature],
            active_signature=0,
            active_parameter=_active_parameter_index(
                text,
                params.position.line,
                params.position.character,
            ),
        )

    @_register(language_server, TEXT_DOCUMENT_CODE_ACTION)
    def code_action(params: CodeActionParams) -> list[CodeAction]:
        text = text_for_uri(params.text_document.uri)
        actions: list[CodeAction] = []
        for item in params.context.diagnostics:
            if str(item.code) != "GAIA015":
                continue
            import_statement = _suggested_import_from_message(item.message)
            if not import_statement or import_statement in text:
                continue
            line = _import_insertion_line(text)
            position = Position(line=line, character=0)
            edit = TextEdit(
                range=Range(start=position, end=position),
                new_text=f"{import_statement}\n",
            )
            actions.append(
                CodeAction(
                    title=f"Add Gaia import: {import_statement}",
                    kind=CodeActionKind.QuickFix,
                    diagnostics=[item],
                    is_preferred=True,
                    edit=WorkspaceEdit(changes={params.text_document.uri: [edit]}),
                )
            )
        return actions

    @_register(language_server, TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbol(params: DocumentSymbolParams) -> list[DocumentSymbol]:
        uri = params.text_document.uri
        text = language_server.documents_cache.get(uri, "")  # type: ignore[attr-defined]
        out: list[DocumentSymbol] = []
        for item in document_symbols(text):
            line = max(int(item["line"]) - 1, 0)
            character = max(int(item["column"]) - 1, 0)
            symbol_range = Range(
                start=Position(line=line, character=character),
                end=Position(line=line, character=character + max(len(item["name"]), 1)),
            )
            out.append(
                DocumentSymbol(
                    name=item["name"],
                    detail=item["kind"],
                    kind=SymbolKind.Variable,
                    range=symbol_range,
                    selection_range=symbol_range,
                )
            )
        return out

    @_register(language_server, WORKSPACE_SYMBOL)
    def workspace_symbol(params: WorkspaceSymbolParams) -> list[WorkspaceSymbol]:
        query = params.query or ""
        out: list[WorkspaceSymbol] = []
        for item in workspace_symbols(Path.cwd(), query):
            out.append(
                WorkspaceSymbol(
                    name=str(item["name"]),
                    kind=SymbolKind.Variable,
                    container_name=str(item.get("kind") or "gaia"),
                    location=to_location(item),
                )
            )
        return out

    @_register(language_server, TEXT_DOCUMENT_FOLDING_RANGE)
    def folding_range(params: FoldingRangeParams) -> list[FoldingRange]:
        text = text_for_uri(params.text_document.uri)
        return [
            FoldingRange(
                start_line=int(item["startLine"]),
                end_line=int(item["endLine"]),
                kind=str(item.get("kind", "region")),
            )
            for item in folding_ranges(text)
        ]

    @_register(language_server, TEXT_DOCUMENT_DOCUMENT_LINK)
    def document_link(params: DocumentLinkParams) -> list[DocumentLink]:
        uri = params.text_document.uri
        path = _path_from_uri(uri)
        text = text_for_uri(uri)
        return [
            DocumentLink(
                range=_range_from_payload(item["range"]),
                target=str(item["target"]),
                tooltip=str(item.get("tooltip") or ""),
            )
            for item in document_links(text, path)
        ]

    @_register(language_server, TEXT_DOCUMENT_RENAME)
    def rename(params: RenameParams) -> WorkspaceEdit:
        path = _path_from_uri(params.text_document.uri)
        if path is None or not path.exists():
            return WorkspaceEdit(changes={})
        try:
            payload = rename_edits_at(
                path,
                params.position.line,
                params.position.character,
                params.new_name,
            )
        except ValueError:
            return WorkspaceEdit(changes={})
        changes: dict[str, list[TextEdit]] = {}
        for uri, edits in payload["changes"].items():
            changes[uri] = [
                TextEdit(range=_range_from_payload(edit["range"]), new_text=str(edit["newText"]))
                for edit in edits
            ]
        return WorkspaceEdit(changes=changes)

    @_register(language_server, TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL)
    def semantic_tokens_full(params: SemanticTokensParams) -> SemanticTokens:
        text = text_for_uri(params.text_document.uri)
        return SemanticTokens(data=_semantic_tokens_data(semantic_tokens(text)))

    return language_server


def main() -> None:
    create_server().start_io()


if __name__ == "__main__":
    main()
