from __future__ import annotations

from pathlib import Path

from gaia_lsp.analyzer import (
    analyze_path,
    analyze_text,
    completion_items,
    document_symbols,
    hover,
    hover_at,
)

VALID_GAIA = '''
from gaia.engine.lang import claim, contradict, derive, equal, note, register_prior

setup = note("A heavy body and a light body are tied together.")
daily_observation = claim("In air, heavy bodies often fall faster than light bodies.")
aristotle_model = claim("Weight itself causes greater natural falling speed.")
medium_model = claim("In-air speed differences are caused by medium resistance.")

aristotle_daily = derive(
    "Under the weight-speed model, heavy bodies should fall faster in air.",
    given=[aristotle_model],
    rationale="This follows from the model.",
    label="aristotle_daily",
)
equal(aristotle_daily, daily_observation, rationale="Prediction matches observation.")
contradict(aristotle_model, medium_model, rationale="The mechanisms are alternatives.")
register_prior(daily_observation, 0.9, justification="Everyday observations support it.")

__all__ = ["daily_observation", "aristotle_model", "medium_model", "aristotle_daily"]
'''


def codes(text: str, *, path: Path | None = None) -> list[str]:
    return [diagnostic.code for diagnostic in analyze_text(text, path=path)]


def test_valid_gaia_dsl_has_no_blocking_errors() -> None:
    diagnostics = analyze_text(VALID_GAIA, path=Path("example.py"))

    assert [item for item in diagnostics if item.severity == "error"] == []


def test_python_syntax_error_is_reported() -> None:
    found = codes("from gaia.engine.lang import claim\nclaim(", path=Path("broken.py"))

    assert "GAIA001" in found


def test_missing_string_content_and_deprecated_symbols_are_reported() -> None:
    source = """
from gaia.engine.lang import claim, setting, contradiction

bad = claim()
legacy = setting("legacy context")
also_legacy = contradiction(bad, legacy)
"""

    found = codes(source, path=Path("legacy.py"))

    assert "GAIA010" in found
    assert "GAIA020" in found
    assert "GAIA021" in found


def test_register_prior_requires_valid_probability_and_justification() -> None:
    source = """
from gaia.engine.lang import claim, register_prior

hypothesis = claim("The model is plausible.")
register_prior(hypothesis, 1.2)
register_prior("hypothesis", 0.5, justification="")
"""

    found = codes(source, path=Path("priors.py"))

    assert "GAIA030" in found
    assert "GAIA031" in found
    assert "GAIA032" in found


def test_legacy_priors_dict_is_blocking() -> None:
    found = codes('PRIORS = {"daily_observation": 0.9}\n', path=Path("priors.py"))

    assert "GAIA033" in found


def test_static_all_exports_unknown_and_duplicate_names() -> None:
    source = """
from gaia.engine.lang import claim

known = claim("Known claim")
__all__ = ["known", "missing", "known"]
"""

    found = codes(source, path=Path("__init__.py"))

    assert "GAIA040" in found
    assert "GAIA041" in found


def test_strict_references_resolve_against_local_labels_and_references_json(tmp_path: Path) -> None:
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "references.json").write_text(
        '{"Aspect1982": {"type": "article-journal", "title": "Experiment"}}',
        encoding="utf-8",
    )
    module = project / "src" / "pkg"
    module.mkdir(parents=True)
    source_path = module / "__init__.py"
    source_path.write_text(
        '''
from gaia.engine.lang import claim, note

setup = note("Local setup.")
result = claim("Result cites [@setup] and [@Aspect1982] but not [@MissingRef].")
''',
        encoding="utf-8",
    )

    diagnostics = analyze_path(source_path)

    assert [item.code for item in diagnostics].count("GAIA050") == 1
    assert "MissingRef" in diagnostics[0].message


def test_completion_and_hover_cover_gaia_authoring_surface() -> None:
    labels = {item["label"] for item in completion_items()}

    assert {"claim", "note", "derive", "register_prior", "Normal"} <= labels
    assert "probability" in hover("claim").lower()
    assert "prior" in hover("register_prior").lower()


def test_analyze_directory_skips_hidden_files(tmp_path: Path) -> None:
    visible = tmp_path / "visible.py"
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    visible.write_text("PRIORS = {'x': 0.5}\n", encoding="utf-8")
    (hidden_dir / "ignored.py").write_text("claim()\n", encoding="utf-8")

    diagnostics = analyze_path(tmp_path)

    assert [item.code for item in diagnostics] == ["GAIA033"]


def test_attribute_calls_claim_prior_dynamic_all_and_non_string_exports() -> None:
    source = """
import gaia.engine.lang as lang

known = lang.claim("Known claim.", prior=0.5)
__all__ = ["known", 123]
dynamic = ["known"]
__all__ = dynamic
"""

    found = codes(source, path=Path("dynamic.py"))

    assert "GAIA011" in found
    assert found.count("GAIA042") == 2


def test_hover_at_and_document_symbols_handle_positions_and_bad_syntax() -> None:
    source = "from gaia.engine.lang import claim\nknown = claim('Known')\n"

    assert "probability" in hover_at(source, 1, 9).lower()
    assert hover_at(source, -1, 0) == ""
    assert hover_at(source, 1, 999) == ""
    assert document_symbols("known = claim('Known')\n")[0]["name"] == "known"
    assert document_symbols("claim(") == []


def test_missing_or_malformed_references_json_keeps_refs_unresolved(tmp_path: Path) -> None:
    project = tmp_path / "pkg"
    project.mkdir()
    (project / "references.json").write_text("{bad json", encoding="utf-8")
    sample = project / "module.py"
    sample.write_text(
        "from gaia.engine.lang import claim\nresult = claim('See [@Broken].')\n",
        encoding="utf-8",
    )

    diagnostics = analyze_path(sample)

    assert [item.code for item in diagnostics] == ["GAIA050"]
