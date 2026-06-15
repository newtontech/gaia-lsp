from __future__ import annotations

import pytest


def test_create_server_initializes_pygls_server() -> None:
    pytest.importorskip("pygls")
    pytest.importorskip("lsprotocol")

    from gaia_lsp.server import create_server

    server = create_server()

    assert server.name == "gaia-lsp"
    assert server.documents_cache == {}
