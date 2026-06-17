from __future__ import annotations

from gaia_lsp.analyzer import completion_items, hover
from gaia_lsp.rules import GAIA_UPSTREAM, rule_catalog


def test_rule_catalog_tracks_current_gaia_public_surface() -> None:
    catalog = rule_catalog()
    labels = {item["label"] for item in catalog["symbols"]}
    groups = {rule["group"] for rule in catalog["rules"]}
    diagnostic_codes = {item["code"]: item for item in catalog["diagnostics"]}

    assert GAIA_UPSTREAM["commit"] == "6354a3425fdadcf6f7e5f557dd3bc30f36d3297e"
    assert {
        "BetaBinomial",
        "Domain",
        "Variable",
        "export",
        "forall",
        "land",
        "model",
        "compare",
        "parameter",
        "roles_for_package",
        "Claim",
        "Knowledge",
        "Formula",
        "Term",
        "Distribution",
        "RoleOccurrence",
    } <= labels
    assert {
        "package",
        "references",
        "exports",
        "distribution",
        "observation",
        "artifact",
        "bayes",
        "scaffold",
        "association",
        "prior",
    } <= groups
    assert diagnostic_codes["GAIA010"]["severity"] == "error"
    assert diagnostic_codes["GAIA011"]["severity"] == "warning"
    assert diagnostic_codes["GAIA015"]["severity"] == "error"
    assert "non-empty string content" in diagnostic_codes["GAIA010"]["explanation"]
    assert "register_prior" in diagnostic_codes["GAIA011"]["fix"]
    assert "import" in diagnostic_codes["GAIA015"]["fix"].lower()
    assert {section["id"] for section in catalog["manual"]["sections"]} >= {
        "overview",
        "authoring-surface",
        "diagnostics",
        "cli",
    }


def test_completion_and_hover_include_full_gaia_surface() -> None:
    labels = {item["label"] for item in completion_items()}

    assert {
        "BetaBinomial",
        "Variable",
        "export",
        "forall",
        "Probability",
        "Claim",
        "Formula",
        "RoleOccurrence",
    } <= labels
    assert "public Gaia export helper" in hover("export")
    assert "Beta-Binomial" in hover("BetaBinomial")
    assert "Runtime Gaia Knowledge object" in hover("Claim")
