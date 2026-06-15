from __future__ import annotations

from pathlib import Path

from gaia_lsp.analyzer import analyze_path, analyze_text


def codes(text: str, *, path: Path | None = None) -> list[str]:
    return [diagnostic.code for diagnostic in analyze_text(text, path=path)]


def test_export_helper_accepts_static_names_and_rejects_non_exportable_bindings() -> None:
    source = """
from gaia.engine.lang import Normal, Variable, claim, export, Real

result = claim("A publishable result.")
temperature = Normal("temperature", mu=300, sigma=10)
x = Variable(symbol="x", domain=Real)
__all__ = export(result, "temperature", x)
"""

    found = codes(source, path=Path("__init__.py"))

    assert found.count("GAIA040") == 2
    assert "GAIA042" not in found


def test_distribution_factories_validate_required_params_and_literal_domains() -> None:
    source = """
from gaia.engine.lang import Beta, BetaBinomial, Binomial, Normal, Poisson

missing = Normal("missing mu", sigma=1)
bad_scale = Normal("bad scale", mu=0, sigma=0)
bad_probability = Binomial("bad p", n=10, p=1.2)
bad_count = BetaBinomial("bad count", n=2.5, alpha=1, beta=1)
bad_rate = Poisson("bad rate", rate=True)
bad_shape = Beta("bad shape", alpha=-1, beta=1)
"""

    found = codes(source, path=Path("distributions.py"))

    assert "GAIA081" in found
    assert found.count("GAIA082") == 3
    assert "GAIA083" in found
    assert "GAIA084" in found


def test_observe_branches_validate_distribution_and_claim_shapes() -> None:
    source = """
from gaia.engine.lang import Normal, claim, observe

temperature = Normal("temperature", mu=300, sigma=10)
result = claim("The sample is hot.")
observe(temperature)
observe(temperature, value=301, given=[result])
observe(result, value=1.0)
observe("The claim is directly observed.", error=0.1)
observe(result, source_refs=["Legacy2020"])
"""

    found = codes(source, path=Path("observe.py"))

    assert "GAIA090" in found
    assert "GAIA091" in found
    assert found.count("GAIA092") == 2
    assert "GAIA093" in found


def test_artifact_and_association_scaffold_rules_are_static() -> None:
    source = """
from gaia.engine.lang import artifact, associate, candidate_relation, claim, decompose, depends_on

a = claim("A")
b = claim("B")
bad_artifact = artifact(kind="video")
bad_path = artifact(kind="dataset", path="../raw.csv")
bad_figure = artifact(kind="figure", source="Paper2020")
associate(a, b, p_a_given_b=1.2, p_b_given_a=0.2, pattern="equal")
candidate_relation(claims=[a], pattern="causes")
depends_on(a)
decompose(a, parts=[])
"""

    found = codes(source, path=Path("actions.py"))

    assert "GAIA070" in found
    assert "GAIA071" in found
    assert "GAIA072" in found
    assert "GAIA073" in found
    assert "GAIA100" in found
    assert "GAIA101" in found
    assert "GAIA102" in found
    assert "GAIA103" in found
    assert "GAIA104" in found


def test_register_prior_uses_cromwell_bounds_and_source_id() -> None:
    source = """
from gaia.engine.lang import claim, register_prior

result = claim("A result.")
register_prior(result, 0.9999, justification="Too certain.")
register_prior(result, True, justification="Boolean is not a probability.")
register_prior(result, 0.5, justification="Missing source.", source_id="")
"""

    found = codes(source, path=Path("priors.py"))

    assert found.count("GAIA030") == 2
    assert "GAIA034" in found


def test_register_prior_allows_dynamic_probability_expressions() -> None:
    source = """
from gaia.engine.lang import claim, register_prior
from .probabilities import PRIOR_MODEL

result = claim("A result.")
register_prior(result, value=PRIOR_MODEL, justification="Configured prior.")
register_prior(result, value=1.0 - PRIOR_MODEL, justification="Complement prior.")
"""

    found = codes(source, path=Path("priors.py"))

    assert "GAIA030" not in found


def test_bayes_model_and_compare_exports_are_part_of_gaia_authoring_surface() -> None:
    source = """
from gaia.engine import bayes
from gaia.engine.lang import Binomial, claim

hypothesis = claim("The model is plausible.")
count_model = bayes.model(
    hypothesis,
    observable=f2_count,
    distribution=Binomial("F2 count", n=395, p=0.75),
    rationale="Predictive model.",
    label="count_model",
)
model_choice = bayes.compare(
    observed_count,
    models=[count_model, other_model],
    rationale="Compare likelihoods.",
    label="model_choice",
)
__all__ = ["count_model", "model_choice"]
"""

    found = codes(source, path=Path("__init__.py"))

    assert "GAIA040" not in found


def test_bayes_model_and_compare_validate_required_keywords() -> None:
    source = """
from gaia.engine import bayes

bad_model = bayes.model(hypothesis, rationale="Missing distribution and observable.")
bad_compare = bayes.compare(data, models=[], exclusivity="none", rationale="Bad compare.")
too_many = bayes.compare(data, models=[m1, m2, m3], rationale="Unsupported default.")
"""

    found = codes(source, path=Path("bayes.py"))

    assert "GAIA110" in found
    assert found.count("GAIA111") == 3


def test_package_structure_and_references_json_schema(tmp_path: Path) -> None:
    package = tmp_path / "broken-gaia"
    source_root = package / "src" / "broken"
    source_root.mkdir(parents=True)
    (package / "pyproject.toml").write_text(
        """
[project]
name = "broken-gaia"
version = "0.1.0"

[tool.gaia]
type = "knowledge-package"
""",
        encoding="utf-8",
    )
    (package / "references.json").write_text(
        '{"Bad Key": {"type": "made-up", "title": ""}, '
        '"result": {"type": "webpage", "title": "Collision"}}',
        encoding="utf-8",
    )
    (source_root / "__init__.py").write_text(
        """
from gaia.engine.lang import claim

result = claim("Result cites [@Bad Key] and [@Missing].")
__all__ = ["result"]
""",
        encoding="utf-8",
    )

    diagnostics = analyze_path(package)
    found = [diagnostic.code for diagnostic in diagnostics]

    assert "GAIA067" in found
    assert "GAIA068" in found
    assert found.count("GAIA050") == 2


def test_package_layout_reports_missing_source_entrypoint(tmp_path: Path) -> None:
    package = tmp_path / "layout-gaia"
    package.mkdir()
    (package / "pyproject.toml").write_text(
        """
[project]
name = "layout-gaia"
version = "0.1.0"

[tool.gaia]
type = "knowledge-package"
""",
        encoding="utf-8",
    )

    found = [diagnostic.code for diagnostic in analyze_path(package)]

    assert "GAIA066" in found


def test_package_root_all_accepts_reexported_sibling_knowledge(tmp_path: Path) -> None:
    package = tmp_path / "valid-gaia"
    source_root = package / "src" / "valid"
    source_root.mkdir(parents=True)
    (package / "pyproject.toml").write_text(
        """
[project]
name = "valid-gaia"
version = "0.1.0"

[tool.gaia]
type = "knowledge-package"
""",
        encoding="utf-8",
    )
    (source_root / "claims.py").write_text(
        """
from gaia.engine.lang import claim

result = claim("A sibling-defined public result.")
""",
        encoding="utf-8",
    )
    (source_root / "__init__.py").write_text(
        """
from .claims import result

__all__ = ["result"]
""",
        encoding="utf-8",
    )

    found = [diagnostic.code for diagnostic in analyze_path(package)]

    assert "GAIA040" not in found


def test_all_extension_starred_existing_exports_is_allowed() -> None:
    source = """
from gaia.engine.lang import claim

known = claim("Known.")
__all__ = ["known"]
__all__ = [*__all__, *_authored.__all__]
"""

    found = codes(source, path=Path("__init__.py"))

    assert "GAIA042" not in found


def test_gaia_import_aliases_are_checked_without_linting_unrelated_local_names() -> None:
    source = """
from gaia.engine.lang import claim as hypothesis

def claim():
    return None

local = claim()
bad = hypothesis()
"""

    found = codes(source, path=Path("aliases.py"))

    assert found == ["GAIA010"]
