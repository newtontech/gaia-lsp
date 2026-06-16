from __future__ import annotations

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.9/3.10 in CI
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_public_package_scripts_and_urls() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]

    assert project["name"] == "gaia-lsp"
    assert project["urls"]["Repository"] == "https://github.com/newtontech/gaia-lsp"
    assert project["urls"]["Source"] == "https://github.com/SiliconEinstein/Gaia"
    assert project["scripts"]["gaia-lsp"] == "gaia_lsp.cli:lsp_main"
    assert project["scripts"]["gaia-lsp-tool"] == "gaia_lsp.tool:main"


def test_capabilities_manifest_matches_openqc_lsp_contract() -> None:
    manifest = json.loads((ROOT / "lsp-capabilities.json").read_text(encoding="utf-8"))

    assert manifest["id"] == "gaia-lsp"
    assert manifest["software"] == "gaia"
    assert manifest["repository"] == "newtontech/gaia-lsp"
    assert manifest["agentCli"]["command"] == "gaia-lsp-tool"
    assert "rules" in manifest["agentCli"]["operations"]
    assert "diagnostic-engine-v1" in manifest["capabilities"]
    assert "rule-catalog" in manifest["capabilities"]


def test_vscode_extension_metadata_is_publishable() -> None:
    package = json.loads((ROOT / "gaia-vscode" / "package.json").read_text(encoding="utf-8"))

    assert package["name"] == "gaia-vscode"
    assert package["publisher"] == "newtontech"
    assert package["repository"]["directory"] == "gaia-vscode"
    assert package["main"] == "./out/src/extension.js"
    assert "gaia.lsp.checkFile" in {item["command"] for item in package["contributes"]["commands"]}

    manifest = json.loads((ROOT / "lsp-capabilities.json").read_text(encoding="utf-8"))
    extension = manifest["editorExtensions"][0]
    assert extension["directory"] == "gaia-vscode"
    assert extension["extensionId"] == "newtontech.gaia-vscode"
