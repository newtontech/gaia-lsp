from __future__ import annotations

import pytest


def test_create_server_initializes_pygls_server() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")
    from lsprotocol.types import (
        TEXT_DOCUMENT_CODE_ACTION,
        TEXT_DOCUMENT_COMPLETION,
        TEXT_DOCUMENT_DEFINITION,
        TEXT_DOCUMENT_DOCUMENT_SYMBOL,
        TEXT_DOCUMENT_HOVER,
        TEXT_DOCUMENT_REFERENCES,
        TEXT_DOCUMENT_SIGNATURE_HELP,
    )

    from gaia_lsp.server import create_server

    server = create_server()
    registered = set(server.lsp.fm._features)

    assert server.name == "gaia-lsp"
    assert server.documents_cache == {}
    assert {
        TEXT_DOCUMENT_COMPLETION,
        TEXT_DOCUMENT_HOVER,
        TEXT_DOCUMENT_DEFINITION,
        TEXT_DOCUMENT_REFERENCES,
        TEXT_DOCUMENT_SIGNATURE_HELP,
        TEXT_DOCUMENT_CODE_ACTION,
        TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    } <= registered
