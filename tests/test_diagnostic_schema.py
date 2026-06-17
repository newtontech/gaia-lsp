"""Schema and rule-catalog consistency tests for gaia-lsp diagnostics."""

from __future__ import annotations

import json
import re
from pathlib import Path

from gaia_lsp.analyzer import analyze_text
from gaia_lsp.diagnostics import Diagnostic
from gaia_lsp.rules import diagnostic_catalog
from gaia_lsp.tool import check_path

_REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = _REPO / "diagnostics" / "diagnostic-engine-v1.schema.json"
ANALYZER_PATH = _REPO / "src" / "gaia_lsp" / "analyzer.py"
VALID_SEVERITIES = {"error", "warning", "information", "hint"}


def test_schema_is_valid_json_and_declares_required_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["software"]["const"] == "gaia"
    assert set(schema["required"]) == {"software", "operation", "ok", "diagnostics"}
    diagnostic_item = schema["properties"]["diagnostics"]["items"]
    assert set(diagnostic_item["required"]) == {
        "code",
        "message",
        "severity",
        "range",
        "blocking",
    }
    assert set(diagnostic_item["properties"]["severity"]["enum"]) == VALID_SEVERITIES


def test_every_catalog_diagnostic_is_emitted_by_the_analyzer() -> None:
    """No advertised rule may be a dead catalog entry (fleet contract)."""
    emitted = set(re.findall(r'"(GAIA\d+)"', ANALYZER_PATH.read_text(encoding="utf-8")))
    catalog_codes = {item["code"] for item in diagnostic_catalog()}

    assert catalog_codes, "diagnostic catalog must not be empty"
    dead = catalog_codes - emitted
    assert not dead, f"catalog rules are never emitted by the analyzer: {sorted(dead)}"


def test_catalog_severities_are_within_schema_enum() -> None:
    catalog_severities = {item["severity"] for item in diagnostic_catalog()}
    assert catalog_severities <= VALID_SEVERITIES


def test_catalog_and_runtime_severities_match_for_export_and_reference_rules() -> None:
    catalog = {item["code"]: item["severity"] for item in diagnostic_catalog()}
    diagnostics = analyze_text(
        """
from gaia.engine.lang import claim

known = claim("Known [@Missing].")
__all__ = ["missing", 123]
""",
        path=Path("__init__.py"),
    )
    emitted = {item.code: item.severity for item in diagnostics}

    for code in ("GAIA040", "GAIA042", "GAIA050"):
        assert emitted[code] == catalog[code]
        assert emitted[code] == "error"


def test_emitted_diagnostics_match_the_schema_shape() -> None:
    diagnostics = analyze_text(
        "from gaia.engine.lang import claim\nclaim()\n",
    )

    assert diagnostics, "fixture must produce at least one diagnostic"
    for item in diagnostics:
        payload = item.to_json()
        assert payload["code"].startswith("GAIA")
        assert isinstance(payload["message"], str) and payload["message"]
        assert payload["severity"] in VALID_SEVERITIES
        assert "range" in payload and "start" in payload["range"] and "end" in payload["range"]
        assert payload["blocking"] == (payload["severity"] == "error")


def test_blocking_flag_is_deterministic_from_severity() -> None:
    assert Diagnostic(
        code="GAIA010", message="m", severity="error", line=1, column=1
    ).blocking is True
    assert Diagnostic(
        code="GAIA011", message="m", severity="warning", line=1, column=1
    ).blocking is False


def test_check_envelope_conforms_to_diagnostic_schema(tmp_path: Path) -> None:
    sample = tmp_path / "bad.py"
    sample.write_text("from gaia.engine.lang import claim\nclaim()\n", encoding="utf-8")

    payload = check_path(sample)

    assert payload["software"] == "gaia"
    assert payload["operation"] == "check"
    assert payload["ok"] is False
    assert payload["toolVersion"]
    assert isinstance(payload["diagnostics"], list)
    item = payload["diagnostics"][0]
    for key in ("code", "message", "severity", "range", "blocking", "source"):
        assert key in item
