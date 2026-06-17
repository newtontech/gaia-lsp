from __future__ import annotations

import json
from pathlib import Path

from gaia_lsp.analyzer import analyze_path

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def test_manifest_declares_gaia_python_package_surface() -> None:
    manifest = json.loads((ROOT / "lsp-capabilities.json").read_text(encoding="utf-8"))

    assert manifest["languageId"] == "python"
    assert "src/**/*.py" in manifest["filePatterns"]
    assert "**/*-gaia/src/**/*.py" in manifest["filePatterns"]


def test_fixture_extensions_cover_python_package_metadata() -> None:
    extensions = {path.suffix for path in FIXTURES.rglob("*") if path.is_file()}

    assert ".py" in extensions
    assert ".json" in extensions
    assert ".toml" in extensions


def test_python_fixture_is_analyzed_as_gaia_source() -> None:
    diagnostics = analyze_path(FIXTURES / "valid" / "clean_claim.py")

    assert [item for item in diagnostics if item.severity == "error"] == []


def test_upstream_package_fixture_exercises_pyproject_and_references_json() -> None:
    package = FIXTURES / "upstream" / "mendel-v0-5-gaia"

    assert (package / "pyproject.toml").exists()
    assert (package / "references.json").exists()

    diagnostics = analyze_path(package)
    assert "GAIA067" not in {item.code for item in diagnostics}
