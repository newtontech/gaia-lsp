"""pygls server wiring for gaia-lsp."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from . import __version__
from .analyzer import analyze_text, completion_items, document_symbols, hover_at
from .diagnostics import Diagnostic

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


def create_server(name: str = SERVER_NAME, version: str = __version__) -> Any:
    from lsprotocol.types import (
        COMPLETION_ITEM_RESOLVE,
        TEXT_DOCUMENT_COMPLETION,
        TEXT_DOCUMENT_DID_CHANGE,
        TEXT_DOCUMENT_DID_OPEN,
        TEXT_DOCUMENT_DOCUMENT_SYMBOL,
        TEXT_DOCUMENT_HOVER,
        CompletionItem,
        CompletionList,
        CompletionParams,
        DidChangeTextDocumentParams,
        DidOpenTextDocumentParams,
        DocumentSymbol,
        DocumentSymbolParams,
        Hover,
        HoverParams,
        MarkupContent,
        MarkupKind,
        Position,
        Range,
        SymbolKind,
    )

    language_server = _load_language_server()(name, version)
    language_server.documents_cache = {}  # type: ignore[attr-defined]

    def publish(uri: str, text: str) -> None:
        path = _path_from_uri(uri)
        diagnostics = [_to_lsp_diagnostic(item) for item in analyze_text(text, path=path)]
        language_server.publish_diagnostics(uri, diagnostics)

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
        return CompletionList(
            is_incomplete=False,
            items=[
                CompletionItem(
                    label=item["label"],
                    detail=item["detail"],
                    documentation=item["documentation"],
                )
                for item in completion_items()
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

    return language_server


def main() -> None:
    create_server().start_io()


if __name__ == "__main__":
    main()
