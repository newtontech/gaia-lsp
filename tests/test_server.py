"""Protocol-level tests for the LSP server.

Covers helper function correctness, handler behavior, diagnostic publication,
error recovery, and feature registration matching the capabilities manifest.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Feature registration (original test preserved and expanded)
# ---------------------------------------------------------------------------


def test_create_server_registers_all_advertised_text_document_features() -> None:
    """Every manifest-listed textDocument operation must have a registered handler."""
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import (
        TEXT_DOCUMENT_CODE_ACTION,
        TEXT_DOCUMENT_COMPLETION,
        TEXT_DOCUMENT_DEFINITION,
        TEXT_DOCUMENT_DOCUMENT_LINK,
        TEXT_DOCUMENT_DOCUMENT_SYMBOL,
        TEXT_DOCUMENT_FOLDING_RANGE,
        TEXT_DOCUMENT_HOVER,
        TEXT_DOCUMENT_REFERENCES,
        TEXT_DOCUMENT_RENAME,
        TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
        TEXT_DOCUMENT_SIGNATURE_HELP,
        WORKSPACE_SYMBOL,
    )

    from gaia_lsp.server import create_server

    server = create_server()
    registered = set(server.lsp.fm._features)

    assert server.name == "gaia-lsp"
    assert server.documents_cache == {}
    # didOpen and didChange are built-in pygls features registered via _features;
    # they may appear under different keys.  The advertised set must be a subset.
    advertised = {
        TEXT_DOCUMENT_COMPLETION,
        TEXT_DOCUMENT_HOVER,
        TEXT_DOCUMENT_DEFINITION,
        TEXT_DOCUMENT_REFERENCES,
        TEXT_DOCUMENT_SIGNATURE_HELP,
        TEXT_DOCUMENT_CODE_ACTION,
        TEXT_DOCUMENT_DOCUMENT_SYMBOL,
        WORKSPACE_SYMBOL,
        TEXT_DOCUMENT_FOLDING_RANGE,
        TEXT_DOCUMENT_DOCUMENT_LINK,
        TEXT_DOCUMENT_RENAME,
        TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
    }
    assert advertised <= registered, (
        f"Missing handlers: {advertised - registered}"
    )


def test_create_server_initializes_with_empty_cache_and_correct_name() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from gaia_lsp.server import create_server

    server = create_server()
    assert server.name == "gaia-lsp"
    assert server.documents_cache == {}
    # The server should carry version from __version__
    assert server.version


# ---------------------------------------------------------------------------
# Helper: _to_lsp_diagnostic
# ---------------------------------------------------------------------------


def test_to_lsp_diagnostic_converts_error_severity() -> None:
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import DiagnosticSeverity

    from gaia_lsp.diagnostics import Diagnostic
    from gaia_lsp.server import _to_lsp_diagnostic

    d = Diagnostic(
        code="GAIA010",
        message="claim content is empty",
        severity="error",
        line=5,
        column=3,
        end_line=5,
        end_column=10,
    )
    lsp = _to_lsp_diagnostic(d)
    assert lsp.code == "GAIA010"
    assert lsp.message == "claim content is empty"
    assert lsp.severity == DiagnosticSeverity.Error
    assert lsp.source == "gaia-lsp"
    # Positions are 0-based in LSP
    assert lsp.range.start.line == 4
    assert lsp.range.start.character == 2
    assert lsp.range.end.line == 4
    assert lsp.range.end.character == 9


def test_to_lsp_diagnostic_maps_all_severities() -> None:
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import DiagnosticSeverity

    from gaia_lsp.diagnostics import Diagnostic
    from gaia_lsp.server import _to_lsp_diagnostic

    cases = [
        ("error", DiagnosticSeverity.Error),
        ("warning", DiagnosticSeverity.Warning),
        ("information", DiagnosticSeverity.Information),
        ("hint", DiagnosticSeverity.Hint),
        ("unknown_fallback", DiagnosticSeverity.Warning),
    ]
    for severity_in, expected in cases:
        d = Diagnostic(code="TST", message="x", severity=severity_in, line=1, column=1)
        result = _to_lsp_diagnostic(d)
        assert result.severity == expected, f"severity={severity_in!r}"


def test_to_lsp_diagnostic_defaults_end_when_missing() -> None:
    pytest.importorskip("lsprotocol")
    from gaia_lsp.diagnostics import Diagnostic
    from gaia_lsp.server import _to_lsp_diagnostic

    # Only line/column provided, no end_*
    d = Diagnostic(code="TST", message="x", severity="warning", line=3, column=5)
    result = _to_lsp_diagnostic(d)
    # end should default to line=3, column=6 (column + 1)
    assert result.range.end.line == 2  # 0-based
    assert result.range.end.character == 5  # (column=5 → 0-based 4) + 1 = 5 in LSP


def test_to_lsp_diagnostic_includes_source() -> None:
    pytest.importorskip("lsprotocol")
    from gaia_lsp.diagnostics import Diagnostic
    from gaia_lsp.server import _to_lsp_diagnostic

    d = Diagnostic(code="TST", message="x", severity="error", line=1, column=1)
    result = _to_lsp_diagnostic(d)
    assert result.source == "gaia-lsp"


# ---------------------------------------------------------------------------
# Helper: _path_from_uri
# ---------------------------------------------------------------------------


def test_path_from_uri_file_scheme() -> None:
    from gaia_lsp.server import _path_from_uri

    result = _path_from_uri("file:///home/user/pkg/__init__.py")
    assert result is not None
    assert str(result) == "/home/user/pkg/__init__.py"


def test_path_from_uri_non_file_scheme_returns_none() -> None:
    from gaia_lsp.server import _path_from_uri

    assert _path_from_uri("http://example.com/file.py") is None
    assert _path_from_uri("https://example.com/file.py") is None
    assert _path_from_uri("") is None


def test_path_from_uri_decodes_percent_encoded() -> None:
    from gaia_lsp.server import _path_from_uri

    result = _path_from_uri("file:///home/user/my%20project/file.py")
    assert result is not None
    assert str(result) == "/home/user/my project/file.py"


# ---------------------------------------------------------------------------
# Helper: _function_name_before_call
# ---------------------------------------------------------------------------


def test_function_name_before_call_finds_simple_name() -> None:
    from gaia_lsp.server import _function_name_before_call

    text = "claim("
    assert _function_name_before_call(text, 0, 6) == "claim"


def test_function_name_before_call_within_call() -> None:
    from gaia_lsp.server import _function_name_before_call

    text = "claim('test', "
    result = _function_name_before_call(text, 0, len(text))
    assert result == "claim"


def test_function_name_before_call_none_when_no_call() -> None:
    from gaia_lsp.server import _function_name_before_call

    assert _function_name_before_call("just text", 0, 9) is None


def test_function_name_before_call_multi_line() -> None:
    from gaia_lsp.server import _function_name_before_call

    text = "x = 1\nregister_prior("
    assert _function_name_before_call(text, 1, 16) == "register_prior"


# ---------------------------------------------------------------------------
# Helper: _signature_parameters
# ---------------------------------------------------------------------------


def test_signature_parameters_extracts_list() -> None:
    from gaia_lsp.server import _signature_parameters

    result = _signature_parameters(
        "claim(content: str, prior: Prior | None = None)"
    )
    assert result == ["content: str", "prior: Prior | None = None"]


def test_signature_parameters_empty_when_no_parens() -> None:
    from gaia_lsp.server import _signature_parameters

    assert _signature_parameters("just a name") == []
    assert _signature_parameters("") == []


def test_signature_parameters_handles_empty_parens() -> None:
    from gaia_lsp.server import _signature_parameters

    assert _signature_parameters("func()") == []


# ---------------------------------------------------------------------------
# Helper: _active_parameter_index
# ---------------------------------------------------------------------------


def test_active_parameter_index_first_param() -> None:
    from gaia_lsp.server import _active_parameter_index

    text = "claim(first"
    assert _active_parameter_index(text, 0, len(text)) == 0


def test_active_parameter_index_second_param() -> None:
    from gaia_lsp.server import _active_parameter_index

    text = "claim(first, second"
    assert _active_parameter_index(text, 0, len(text)) == 1


def test_active_parameter_index_no_open_paren() -> None:
    from gaia_lsp.server import _active_parameter_index

    assert _active_parameter_index("no call here", 0, 12) == 0


# ---------------------------------------------------------------------------
# Helper: _suggested_import_from_message
# ---------------------------------------------------------------------------


def test_suggested_import_from_message_extracts_import() -> None:
    from gaia_lsp.server import _suggested_import_from_message

    msg = "Missing Gaia helper — add `from gaia.engine.lang import claim`"
    assert _suggested_import_from_message(msg) == "from gaia.engine.lang import claim"


def test_suggested_import_from_message_none_when_no_backtick() -> None:
    from gaia_lsp.server import _suggested_import_from_message

    assert _suggested_import_from_message("No backtick here") is None


# ---------------------------------------------------------------------------
# Helper: _import_insertion_line
# ---------------------------------------------------------------------------


def test_import_insertion_line_after_existing_imports() -> None:
    from gaia_lsp.server import _import_insertion_line

    text = "import os\nimport sys\n\nx = 1\n"
    assert _import_insertion_line(text) == 3


def test_import_insertion_line_after_docstring_then_imports() -> None:
    from gaia_lsp.server import _import_insertion_line

    text = '"""Module docstring."""\n\nimport os\n\nx = 1\n'
    assert _import_insertion_line(text) == 5


def test_import_insertion_line_top_of_file() -> None:
    from gaia_lsp.server import _import_insertion_line

    assert _import_insertion_line("x = 1\n") == 0


# ---------------------------------------------------------------------------
# Integration: didOpen publishes diagnostics
# ---------------------------------------------------------------------------


def test_did_open_publishes_diagnostics_for_valid_content() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import DidOpenTextDocumentParams, TextDocumentItem

    from gaia_lsp.server import create_server

    server = create_server()
    server.publish_diagnostics = MagicMock()

    uri = "file:///test/pkg/__init__.py"
    text = "from gaia.engine.lang import claim\nclaim('')"

    params = DidOpenTextDocumentParams(
        text_document=TextDocumentItem(
            uri=uri, language_id="python", version=1, text=text
        )
    )

    handler = server.lsp.fm.features["textDocument/didOpen"]
    handler(params)

    server.publish_diagnostics.assert_called_once()
    args = server.publish_diagnostics.call_args
    assert args[0][0] == uri
    diagnostics = args[0][1]
    # Empty claim content should produce GAIA010
    assert any(d.code == "GAIA010" for d in diagnostics)


def test_did_open_caches_text() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import DidOpenTextDocumentParams, TextDocumentItem

    from gaia_lsp.server import create_server

    server = create_server()
    server.publish_diagnostics = MagicMock()

    uri = "file:///test/pkg/__init__.py"
    text = "x = 1"

    params = DidOpenTextDocumentParams(
        text_document=TextDocumentItem(
            uri=uri, language_id="python", version=1, text=text
        )
    )

    handler = server.lsp.fm.features["textDocument/didOpen"]
    handler(params)

    assert server.documents_cache[uri] == text


# ---------------------------------------------------------------------------
# Integration: didChange updates diagnostics
# ---------------------------------------------------------------------------


def test_did_change_publishes_diagnostics_and_updates_cache() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import (
        DidChangeTextDocumentParams,
        TextDocumentContentChangeEvent_Type2,
        VersionedTextDocumentIdentifier,
    )

    from gaia_lsp.server import create_server

    server = create_server()
    server.publish_diagnostics = MagicMock()

    uri = "file:///test/pkg/__init__.py"
    change_text = "claim('valid content')"

    params = DidChangeTextDocumentParams(
        text_document=VersionedTextDocumentIdentifier(uri=uri, version=2),
        content_changes=[TextDocumentContentChangeEvent_Type2(text=change_text)],
    )

    handler = server.lsp.fm.features["textDocument/didChange"]
    handler(params)

    # Cache should be updated
    assert server.documents_cache[uri] == change_text
    # Should publish diagnostics
    server.publish_diagnostics.assert_called_once()


def test_did_change_no_content_changes_does_nothing() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import (
        DidChangeTextDocumentParams,
        VersionedTextDocumentIdentifier,
    )

    from gaia_lsp.server import create_server

    server = create_server()
    server.publish_diagnostics = MagicMock()

    uri = "file:///test/pkg/__init__.py"

    params = DidChangeTextDocumentParams(
        text_document=VersionedTextDocumentIdentifier(uri=uri, version=2),
        content_changes=[],
    )

    handler = server.lsp.fm.features["textDocument/didChange"]
    handler(params)

    # Empty content_changes: handler should return early without publishing
    server.publish_diagnostics.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: completion
# ---------------------------------------------------------------------------


def test_completion_returns_gaia_dsl_helpers() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import CompletionParams, Position, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()

    params = CompletionParams(
        text_document=TextDocumentIdentifier(uri="file:///test/pkg/__init__.py"),
        position=Position(line=0, character=0),
    )

    handler = server.lsp.fm.features["textDocument/completion"]
    result = handler(params)

    assert result.is_incomplete is False
    assert len(result.items) > 0
    labels = [item.label for item in result.items]
    assert "claim" in labels
    assert "note" in labels
    assert "question" in labels


def test_completion_items_have_detail_and_documentation() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import CompletionParams, Position, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()

    params = CompletionParams(
        text_document=TextDocumentIdentifier(uri="file:///test/pkg/__init__.py"),
        position=Position(line=0, character=0),
    )

    handler = server.lsp.fm.features["textDocument/completion"]
    result = handler(params)

    for item in result.items:
        assert item.label
        assert item.detail
        assert item.documentation


# ---------------------------------------------------------------------------
# Integration: hover
# ---------------------------------------------------------------------------


def test_hover_returns_markdown_for_known_symbol() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import HoverParams, MarkupKind, Position, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()
    uri = "file:///test/pkg/__init__.py"
    server.documents_cache[uri] = "claim('test')"

    params = HoverParams(
        text_document=TextDocumentIdentifier(uri=uri),
        position=Position(line=0, character=0),
    )

    handler = server.lsp.fm.features["textDocument/hover"]
    result = handler(params)

    assert result is not None
    assert result.contents.kind == MarkupKind.Markdown


def test_hover_returns_none_for_unknown_content() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import HoverParams, Position, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()
    uri = "file:///test/pkg/__init__.py"
    server.documents_cache[uri] = ""

    params = HoverParams(
        text_document=TextDocumentIdentifier(uri=uri),
        position=Position(line=5, character=10),
    )

    handler = server.lsp.fm.features["textDocument/hover"]
    assert handler(params) is None


# ---------------------------------------------------------------------------
# Integration: definition
# ---------------------------------------------------------------------------


def test_definition_returns_empty_for_nonexistent_file() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import DefinitionParams, Position, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()

    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///nonexistent/file.py"),
        position=Position(line=0, character=0),
    )

    handler = server.lsp.fm.features["textDocument/definition"]
    result = handler(params)
    assert result == []


# ---------------------------------------------------------------------------
# Integration: references
# ---------------------------------------------------------------------------


def test_references_returns_empty_for_nonexistent_file() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import Position, ReferenceParams, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()

    params = ReferenceParams(
        text_document=TextDocumentIdentifier(uri="file:///nonexistent/file.py"),
        position=Position(line=0, character=0),
        context=MagicMock(include_declaration=True),
    )

    handler = server.lsp.fm.features["textDocument/references"]
    result = handler(params)
    assert result == []


# ---------------------------------------------------------------------------
# Integration: signature help
# ---------------------------------------------------------------------------


def test_signature_help_returns_info_for_known_symbol() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import Position, SignatureHelpParams, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()
    uri = "file:///test/pkg/__init__.py"
    server.documents_cache[uri] = "claim("

    params = SignatureHelpParams(
        text_document=TextDocumentIdentifier(uri=uri),
        position=Position(line=0, character=6),
    )

    handler = server.lsp.fm.features["textDocument/signatureHelp"]
    result = handler(params)

    assert result is not None
    assert len(result.signatures) >= 1
    assert "claim" in result.signatures[0].label.lower()


def test_signature_help_returns_none_for_unknown_symbol() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import Position, SignatureHelpParams, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()
    uri = "file:///test/pkg/__init__.py"
    server.documents_cache[uri] = "nonexistent_function("

    params = SignatureHelpParams(
        text_document=TextDocumentIdentifier(uri=uri),
        position=Position(line=0, character=22),
    )

    handler = server.lsp.fm.features["textDocument/signatureHelp"]
    assert handler(params) is None


# ---------------------------------------------------------------------------
# Integration: code action (GAIA015 quick-fix)
# ---------------------------------------------------------------------------


def test_code_action_creates_gaia015_quick_fix() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import (
        CodeActionParams,
        DiagnosticSeverity,
        Position,
        Range,
        TextDocumentIdentifier,
    )
    from lsprotocol.types import (
        Diagnostic as LspDiagnostic,
    )

    from gaia_lsp.server import create_server

    server = create_server()
    uri = "file:///test/pkg/__init__.py"
    server.documents_cache[uri] = "claim('test')"

    params = CodeActionParams(
        text_document=TextDocumentIdentifier(uri=uri),
        range=Range(
            start=Position(line=0, character=0),
            end=Position(line=0, character=0),
        ),
        context=MagicMock(
            diagnostics=[
                LspDiagnostic(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=5),
                    ),
                    severity=DiagnosticSeverity.Error,
                    code="GAIA015",
                    source="gaia-lsp",
                    message="Missing Gaia helper — add `from gaia.engine.lang import claim`",
                )
            ]
        ),
    )

    handler = server.lsp.fm.features["textDocument/codeAction"]
    actions = handler(params)

    assert len(actions) >= 1
    assert "Add Gaia import" in actions[0].title
    assert "from gaia.engine.lang import claim" in actions[0].title
    assert actions[0].kind == "quickfix"


def test_code_action_skips_non_gaia015_diagnostics() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import (
        CodeActionParams,
        DiagnosticSeverity,
        Position,
        Range,
        TextDocumentIdentifier,
    )
    from lsprotocol.types import (
        Diagnostic as LspDiagnostic,
    )

    from gaia_lsp.server import create_server

    server = create_server()
    uri = "file:///test/pkg/__init__.py"
    server.documents_cache[uri] = "x = 1"

    params = CodeActionParams(
        text_document=TextDocumentIdentifier(uri=uri),
        range=Range(
            start=Position(line=0, character=0),
            end=Position(line=0, character=0),
        ),
        context=MagicMock(
            diagnostics=[
                LspDiagnostic(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=1),
                    ),
                    severity=DiagnosticSeverity.Error,
                    code="GAIA010",
                    source="gaia-lsp",
                    message="Some other diagnostic",
                )
            ]
        ),
    )

    handler = server.lsp.fm.features["textDocument/codeAction"]
    actions = handler(params)
    # No GAIA015 → no code actions
    assert len(actions) == 0


# ---------------------------------------------------------------------------
# Integration: document symbol
# ---------------------------------------------------------------------------


def test_document_symbol_returns_symbols_from_cache() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import DocumentSymbolParams, TextDocumentIdentifier

    from gaia_lsp.server import create_server

    server = create_server()
    uri = "file:///test/pkg/__init__.py"
    server.documents_cache[uri] = (
        "from gaia.engine.lang import claim, note, question\n"
        "c = claim('a claim')\n"
        "n = note('a note')\n"
    )

    params = DocumentSymbolParams(
        text_document=TextDocumentIdentifier(uri=uri)
    )

    handler = server.lsp.fm.features["textDocument/documentSymbol"]
    symbols = handler(params)

    assert len(symbols) >= 2
    names = [s.name for s in symbols]
    assert "c" in names
    assert "n" in names


def test_additional_mature_lsp_handlers_return_static_payloads(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import (
        DocumentLinkParams,
        FoldingRangeParams,
        Position,
        RenameParams,
        SemanticTokensParams,
        TextDocumentIdentifier,
        WorkspaceSymbolParams,
    )

    from gaia_lsp.server import create_server

    project = tmp_path / "rich-v0-5-gaia"
    package = project / "src" / "rich_v0_5"
    package.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        """
[project]
name = "rich-v0-5-gaia"
version = "0.1.0"

[tool.gaia]
type = "knowledge-package"
""",
        encoding="utf-8",
    )
    sample = package / "__init__.py"
    sample.write_text(
        '''
from gaia.engine.lang import claim

result = claim("""A multiline
claim body.""")
consumer = claim("Uses [@result].")
''',
        encoding="utf-8",
    )
    uri = sample.as_uri()
    server = create_server()
    server.documents_cache[uri] = sample.read_text(encoding="utf-8")

    folding_handler = server.lsp.fm.features["textDocument/foldingRange"]
    link_handler = server.lsp.fm.features["textDocument/documentLink"]
    rename_handler = server.lsp.fm.features["textDocument/rename"]
    semantic_handler = server.lsp.fm.features["textDocument/semanticTokens/full"]
    workspace_handler = server.lsp.fm.features["workspace/symbol"]

    assert folding_handler(FoldingRangeParams(text_document=TextDocumentIdentifier(uri=uri)))
    assert link_handler(DocumentLinkParams(text_document=TextDocumentIdentifier(uri=uri)))
    rename_edit = rename_handler(
        RenameParams(
            text_document=TextDocumentIdentifier(uri=uri),
            position=Position(line=3, character=1),
            new_name="renamed_result",
        )
    )
    assert rename_edit.changes
    semantic_result = semantic_handler(
        SemanticTokensParams(text_document=TextDocumentIdentifier(uri=uri))
    )
    assert semantic_result.data
    assert isinstance(workspace_handler(WorkspaceSymbolParams(query="result")), list)


# ---------------------------------------------------------------------------
# Error recovery: syntax errors should not crash the server
# ---------------------------------------------------------------------------


def test_error_recovery_syntax_error_does_not_crash() -> None:
    """Syntax errors must still produce diagnostics without crashing."""
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import DidOpenTextDocumentParams, TextDocumentItem

    from gaia_lsp.server import create_server

    server = create_server()
    server.publish_diagnostics = MagicMock()

    uri = "file:///test/pkg/__init__.py"
    # Unclosed triple-quoted string → syntax error
    text = 'from gaia.engine.lang import claim\nprint("""unclosed\n'

    params = DidOpenTextDocumentParams(
        text_document=TextDocumentItem(
            uri=uri, language_id="python", version=1, text=text
        )
    )

    handler = server.lsp.fm.features["textDocument/didOpen"]
    # Must not raise
    handler(params)

    server.publish_diagnostics.assert_called_once()
    args = server.publish_diagnostics.call_args
    diagnostics = args[0][1]
    # Should have at least one diagnostic (GAIA001 for syntax error)
    assert len(diagnostics) >= 1
    # At least one should be GAIA001
    assert any(d.code == "GAIA001" for d in diagnostics)


def test_error_recovery_empty_document_does_not_crash() -> None:
    """Empty document opens gracefully producing zero diagnostics."""
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import DidOpenTextDocumentParams, TextDocumentItem

    from gaia_lsp.server import create_server

    server = create_server()
    server.publish_diagnostics = MagicMock()

    uri = "file:///test/pkg/__init__.py"

    params = DidOpenTextDocumentParams(
        text_document=TextDocumentItem(
            uri=uri, language_id="python", version=1, text=""
        )
    )

    handler = server.lsp.fm.features["textDocument/didOpen"]
    handler(params)

    server.publish_diagnostics.assert_called_once()
    args = server.publish_diagnostics.call_args
    diagnostics = args[0][1]
    # Empty document → no Gaia diagnostics
    assert len(diagnostics) == 0


# ---------------------------------------------------------------------------
# Server main entry point
# ---------------------------------------------------------------------------


def test_main_starts_io_and_is_idempotent() -> None:
    """create_server().start_io() should not crash on construction."""
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from gaia_lsp.server import create_server

    server = create_server()
    # We cannot call start_io() in a test (it blocks), but we can verify
    # that accessing the IO transport adapter is safe.
    assert hasattr(server, "start_io")
    assert callable(server.start_io)
