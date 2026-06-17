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
    assert set(manifest["agentCli"]["operations"]) >= {
        "check",
        "complete",
        "definition",
        "explain",
        "hover",
        "manual",
        "references",
        "rules",
        "symbols",
    }
    assert set(manifest["standardLsp"]["textDocument"]) >= {
        "completion",
        "hover",
        "definition",
        "references",
        "signatureHelp",
        "codeAction",
        "documentSymbol",
    }
    assert "diagnostic-engine-v1" in manifest["capabilities"]
    assert "rule-catalog" in manifest["capabilities"]


def test_pyproject_dev_status_matches_manifest_maturity() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "lsp-capabilities.json").read_text(encoding="utf-8"))
    maturity_to_status = {
        "alpha": "Development Status :: 3 - Alpha",
        "beta": "Development Status :: 4 - Beta",
        "production": "Development Status :: 5 - Production/Stable",
    }
    expected = maturity_to_status[manifest["maturity"]]
    assert expected in data["project"]["classifiers"]


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
    assert "gaia.lsp.showContext" in extension["commands"]
    assert set(extension["providers"]) >= {
        "diagnostics",
        "completion",
        "hover",
        "definition",
        "references",
        "signatureHelp",
        "codeAction",
        "documentSymbol",
    }


def test_manifest_advertises_only_backed_operations_and_maturity() -> None:
    from gaia_lsp.tool import _build_parser

    manifest = json.loads((ROOT / "lsp-capabilities.json").read_text(encoding="utf-8"))

    # Every advertised agentCli operation must be a real registered subcommand.
    parser = _build_parser()
    subparsers = parser._subparsers._group_actions[0].choices  # type: ignore[attr-defined]
    registered = set(subparsers)
    advertised = set(manifest["agentCli"]["operations"])
    assert advertised, "manifest must advertise at least one CLI operation"
    assert advertised <= registered, advertised - registered

    # Maturity must not overclaim: only "production" may be described as top-tier.
    assert manifest["maturity"] in {"alpha", "beta", "production"}
    assert manifest["maturity"] != "production", (
        "maturity is production only after provenance, golden fixtures, LSP smoke, "
        "install smoke, and a real release exist"
    )


def test_source_provenance_ledger_is_consistent() -> None:
    from gaia_lsp.rules import rule_catalog

    manifest = json.loads((ROOT / "lsp-capabilities.json").read_text(encoding="utf-8"))
    provenance = manifest["sourceProvenance"]

    assert provenance, "manifest must declare source provenance"
    by_id = {entry["id"]: entry for entry in provenance}
    for entry in provenance:
        assert {"id", "kind", "label", "url"} <= set(entry), entry

    upstream = by_id["gaia-upstream"]
    assert upstream["kind"] == "upstream_repo"
    assert upstream["url"] == "https://github.com/SiliconEinstein/Gaia"
    assert len(upstream["commit"]) == 40

    # The rules upstream block and the manifest provenance must agree.
    rules_upstream = rule_catalog()["upstream"]
    assert rules_upstream["commit"] == upstream["commit"]
    assert rules_upstream["repository"] == "SiliconEinstein/Gaia"
    assert rules_upstream["referenceDocs"], "rules must list source reference docs"
