"""Golden JSON envelope regression tests.

These fixtures prove the agent CLI emits a stable, deterministic output shape
for success, diagnostic, and failure cases (fleet contract +
agent-cli-json-envelope acceptance). If a diagnostic message, severity, range,
envelope field, or error contract drifts, the matching golden file must be
updated deliberately.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaia_lsp.tool import check_path, main

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"
FIXTURES = ROOT / "tests" / "fixtures"


def _normalize_path(payload: dict[str, Any], fixture: Path) -> str:
    """Serialize an envelope with machine-specific absolute paths normalized.

    Replacement order matters and must be deterministic (longest token first) so
    the URI is not partially mangled by the path replacement.
    """
    resolved = fixture.resolve()
    text = json.dumps(payload, indent=2, sort_keys=True)
    text = text.replace(resolved.as_uri(), "<URI>")
    text = text.replace(str(resolved), "<FIXTURE>")
    if str(fixture) != str(resolved):
        text = text.replace(str(fixture), "<FIXTURE>")
    return text


def test_golden_clean_check_envelope() -> None:
    fixture = FIXTURES / "valid" / "clean_claim.py"
    payload = check_path(fixture)
    expected = (GOLDEN / "check_clean.json").read_text(encoding="utf-8")

    assert _normalize_path(payload, fixture) + "\n" == expected


def test_golden_gaia010_check_envelope() -> None:
    fixture = FIXTURES / "invalid" / "claim_missing_content.py"
    payload = check_path(fixture)
    expected = (GOLDEN / "check_gaia010.json").read_text(encoding="utf-8")

    assert _normalize_path(payload, fixture) + "\n" == expected
    assert payload["ok"] is False
    assert payload["diagnostics"][0]["code"] == "GAIA010"


def test_golden_missing_file_error_envelope(capsys) -> None:  # type: ignore[no-untyped-def]
    fixture = FIXTURES / "invalid" / "does_not_exist.py"
    exit_code = main(["check", str(fixture)])
    payload = json.loads(capsys.readouterr().out)
    expected = (GOLDEN / "error_missing_file.json").read_text(encoding="utf-8")

    assert exit_code == 1
    assert _normalize_path(payload, fixture) + "\n" == expected
