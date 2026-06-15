from __future__ import annotations

from gaia_lsp.analyzer import completion_items, hover
from gaia_lsp.rules import GAIA_UPSTREAM, rule_catalog


def test_rule_catalog_tracks_current_gaia_public_surface() -> None:
    catalog = rule_catalog()
    labels = {item["label"] for item in catalog["symbols"]}
    groups = {rule["group"] for rule in catalog["rules"]}

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


def test_completion_and_hover_include_full_gaia_surface() -> None:
    labels = {item["label"] for item in completion_items()}

    assert {"BetaBinomial", "Variable", "export", "forall", "Probability"} <= labels
    assert "public Gaia export helper" in hover("export")
    assert "Beta-Binomial" in hover("BetaBinomial")
