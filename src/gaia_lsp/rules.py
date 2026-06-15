"""Gaia upstream rule catalog used by static diagnostics.

The catalog is deliberately static and source-provenanced.  Editor diagnostics
must not import a user's Gaia package, but they still need one auditable place
that explains which upstream Gaia surface the static checks target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GAIA_UPSTREAM = {
    "repository": "SiliconEinstein/Gaia",
    "url": "https://github.com/SiliconEinstein/Gaia",
    "commit": "6354a3425fdadcf6f7e5f557dd3bc30f36d3297e",
    "referenceDocs": [
        "docs/for-users/language-reference.md",
        "gaia/engine/lang/__init__.py",
        "gaia/engine/lang/dsl",
        "gaia/engine/lang/runtime/distribution.py",
        "gaia/engine/lang/refs",
        "gaia/engine/bayes",
    ],
}

CROMWELL_EPS = 1e-3


@dataclass(frozen=True)
class SymbolInfo:
    detail: str
    documentation: str
    group: str


@dataclass(frozen=True)
class DistributionRule:
    required: tuple[str, ...]
    positive: tuple[str, ...] = ()
    probabilities: tuple[str, ...] = ()
    integer_nonnegative: tuple[str, ...] = ()
    dimensionless: tuple[str, ...] = ()


CONTENT_CALLS = frozenset({"claim", "note", "question"})
ACTION_CALLS = frozenset({"derive", "observe", "compute", "infer", "decompose"})
RELATION_CALLS = frozenset({"equal", "contradict", "exclusive"})
ASSOCIATION_CALLS = frozenset({"associate"})
SCAFFOLD_CALLS = frozenset({"depends_on", "candidate_relation", "materialize"})
COMPOSITION_CALLS = frozenset({"compose", "composition"})
ARTIFACT_CALLS = frozenset({"artifact", "figure"})
FORMULA_CALLS = frozenset({"forall", "exists", "land", "lor", "lnot", "implies", "iff", "equals"})
SUGAR_CALLS = frozenset({"parameter", "export"})
BAYES_CALLS = frozenset({"model", "compare"})

DISTRIBUTION_RULES: dict[str, DistributionRule] = {
    "Normal": DistributionRule(required=("mu", "sigma"), positive=("sigma",)),
    "LogNormal": DistributionRule(
        required=("mu", "sigma"), positive=("sigma",), dimensionless=("mu", "sigma")
    ),
    "Beta": DistributionRule(
        required=("alpha", "beta"), positive=("alpha", "beta"), dimensionless=("alpha", "beta")
    ),
    "Exponential": DistributionRule(required=("rate",), positive=("rate",)),
    "Gamma": DistributionRule(
        required=("alpha", "rate"), positive=("alpha", "rate"), dimensionless=("alpha",)
    ),
    "StudentT": DistributionRule(
        required=("df", "mu", "sigma"),
        positive=("df", "sigma"),
        dimensionless=("df",),
    ),
    "Cauchy": DistributionRule(required=("mu", "gamma"), positive=("gamma",)),
    "ChiSquared": DistributionRule(required=("df",), positive=("df",), dimensionless=("df",)),
    "Binomial": DistributionRule(
        required=("n", "p"),
        probabilities=("p",),
        integer_nonnegative=("n",),
        dimensionless=("n", "p"),
    ),
    "BetaBinomial": DistributionRule(
        required=("n", "alpha", "beta"),
        positive=("alpha", "beta"),
        integer_nonnegative=("n",),
        dimensionless=("n", "alpha", "beta"),
    ),
    "Poisson": DistributionRule(required=("rate",), positive=("rate",), dimensionless=("rate",)),
}

DISTRIBUTIONS = frozenset(DISTRIBUTION_RULES)
LANG_ONLY_CALLS = frozenset({"Domain", "Variable"}) | DISTRIBUTIONS
EXPORTABLE_KNOWLEDGE_CALLS = (
    CONTENT_CALLS
    | ACTION_CALLS
    | RELATION_CALLS
    | ASSOCIATION_CALLS
    | ARTIFACT_CALLS
    | BAYES_CALLS
    | frozenset({"parameter"})
) - frozenset({"decompose"})
DOCUMENT_SYMBOL_CALLS = EXPORTABLE_KNOWLEDGE_CALLS | LANG_ONLY_CALLS | SCAFFOLD_CALLS | {
    "decompose",
    "compose",
    "composition",
}

ARTIFACT_KINDS = frozenset({"figure", "table", "dataset", "notebook", "attachment"})
ARTIFACT_LOCATOR_REQUIRED_WITH_SOURCE = frozenset({"figure", "table"})
ASSOCIATE_PATTERNS = frozenset({"equal", "contradict", "exclusive"})
CANDIDATE_RELATION_PATTERNS = frozenset({"equal", "contradict", "exclusive"})

DEPRECATED_CALLS = {
    "context": "note",
    "setting": "note",
}
DEPRECATED_RELATIONS = {
    "contradiction": "contradict",
    "equivalence": "equal",
    "complement": "exclusive",
}
DEPRECATED_STRATEGIES = {
    "support": "derive or infer",
    "deduction": "derive",
    "abduction": "derive / infer / bayes.compare",
    "induction": "derive / infer / bayes.compare",
    "analogy": "derive / infer / bayes.compare",
    "extrapolation": "derive / infer / bayes.compare",
    "elimination": "derive / infer / bayes.compare",
    "case_analysis": "derive / infer / bayes.compare",
    "mathematical_induction": "derive",
    "composite": "derive chains plus compose",
    "disjunction": "claim(..., formula=lor(...))",
    "and_": "claim(..., formula=land(...))",
    "or_": "claim(..., formula=lor(...))",
    "not_": "claim(..., formula=lnot(...))",
    "noisy_and": "derive / infer / bayes.compare",
    "fills": "derive",
}

CSL_TYPES = frozenset(
    {
        "article",
        "article-journal",
        "article-magazine",
        "article-newspaper",
        "bill",
        "book",
        "broadcast",
        "chapter",
        "classic",
        "collection",
        "dataset",
        "document",
        "entry",
        "entry-dictionary",
        "entry-encyclopedia",
        "event",
        "figure",
        "graphic",
        "hearing",
        "interview",
        "legal_case",
        "legislation",
        "manuscript",
        "map",
        "motion_picture",
        "musical_score",
        "pamphlet",
        "paper-conference",
        "patent",
        "performance",
        "periodical",
        "personal_communication",
        "post",
        "post-weblog",
        "regulation",
        "report",
        "review",
        "review-book",
        "software",
        "song",
        "speech",
        "standard",
        "thesis",
        "treaty",
        "webpage",
    }
)

SYMBOLS: dict[str, SymbolInfo] = {
    "claim": SymbolInfo(
        "claim(content, proposition=None, *, title=None, background=None, "
        "prior=None, formula=None, tolerance=None, **metadata)",
        "Declare a falsifiable Gaia claim. Claims participate directly in "
        "probability, formulas, and belief propagation.",
        "knowledge",
    ),
    "note": SymbolInfo(
        'note(content, *, title=None, format="markdown", **metadata)',
        "Declare non-probabilistic context such as definitions, setup, source "
        "notes, or package commentary.",
        "knowledge",
    ),
    "question": SymbolInfo(
        'question(content, *, title=None, format="markdown", **metadata)',
        "Declare an open inquiry. Questions do not carry probability.",
        "knowledge",
    ),
    "export": SymbolInfo(
        "export(*items)",
        "Build a static root __all__ list from strings or local Knowledge "
        "objects; this is the public Gaia export helper.",
        "exports",
    ),
    "derive": SymbolInfo(
        "derive(conclusion, *, given=(), background=None, rationale='', label=None)",
        "Record a logical derivation from premises to a conclusion claim.",
        "action",
    ),
    "observe": SymbolInfo(
        "observe(conclusion, *, value=..., error=None, given=(), "
        "background=None, source_refs=None, rationale='', label=None)",
        "Record a claim observation or a Distribution/Variable measurement. "
        "Distribution and Variable observations require value= and cannot use given=.",
        "action",
    ),
    "compute": SymbolInfo(
        "compute(conclusion, *, given=(), rationale='', label=None)",
        "Record a computational step that supports a conclusion.",
        "action",
    ),
    "infer": SymbolInfo(
        "infer(conclusion, *, given=(), rationale='', label=None)",
        "Record an inference action over Gaia claims or formulas.",
        "action",
    ),
    "decompose": SymbolInfo(
        "decompose(whole, *, parts, formula, rationale='', label=None)",
        "Declare that a whole claim is structurally equivalent to a formula "
        "over listed atomic parts.",
        "action",
    ),
    "equal": SymbolInfo(
        "equal(a, b, *, rationale='', label=None)",
        "Declare two claims or boolean-valued expressions equivalent.",
        "relation",
    ),
    "contradict": SymbolInfo(
        "contradict(a, b, *, rationale='', label=None)",
        "Declare two claims or boolean-valued expressions contradictory.",
        "relation",
    ),
    "exclusive": SymbolInfo(
        "exclusive(a, b, *, rationale='', label=None)",
        "Declare two claims as a closed binary partition.",
        "relation",
    ),
    "associate": SymbolInfo(
        "associate(a, b, *, p_a_given_b, p_b_given_a, pattern=None, rationale='', label=None)",
        "Declare a symmetric probabilistic association between two claims.",
        "relation",
    ),
    "depends_on": SymbolInfo(
        "depends_on(conclusion, *, given, rationale='', label=None)",
        "Record unformalized load-bearing dependencies for a claim.",
        "scaffold",
    ),
    "candidate_relation": SymbolInfo(
        "candidate_relation(*, claims, pattern=None, rationale='', label=None)",
        "Record a hypothesized relation without triggering formal relation semantics.",
        "scaffold",
    ),
    "materialize": SymbolInfo(
        "materialize(scaffold, *, by, rationale='', label=None)",
        "Record a checked link from scaffold records to formal graph records.",
        "scaffold",
    ),
    "compose": SymbolInfo("compose(*actions, label=None)", "Compose Gaia actions.", "composition"),
    "composition": SymbolInfo(
        "composition(*actions, label=None)", "Declare an action composition object.", "composition"
    ),
    "artifact": SymbolInfo(
        "artifact(*, kind, source=None, locator=None, path=None, caption=None, "
        "description=None, media_type=None, content=None, title=None)",
        "Create a note carrying structured artifact metadata. kind must be one "
        "of figure, table, dataset, notebook, attachment.",
        "artifact",
    ),
    "figure": SymbolInfo(
        "figure(*, source=None, locator=None, path=None, caption=None, "
        "description=None, media_type=None, content=None, title=None)",
        "Create a figure artifact note. A figure with source= requires locator=.",
        "artifact",
    ),
    "register_prior": SymbolInfo(
        "register_prior(claim, value, *, justification, source_id='user_priors', created_at=None)",
        "Attach an auditable external prior probability to an explicit Claim "
        "object inside Gaia Cromwell bounds.",
        "prior",
    ),
    "model": SymbolInfo(
        "model(hypothesis, *, observable, distribution, rationale='', label=None)",
        "Declare a Bayes predictive model for one hypothesis and observable.",
        "bayes",
    ),
    "compare": SymbolInfo(
        "compare(data, *, models, exclusivity='exhaustive_pairwise_complement', "
        "rationale='', label=None)",
        "Compare equal-positioned predictive models against observed data.",
        "bayes",
    ),
    "Domain": SymbolInfo(
        "Domain(content, *, members, **metadata)",
        "Declare a finite enumerable authoring domain. Domains are Lang-only "
        "and are not exported as package Knowledge.",
        "formula",
    ),
    "Variable": SymbolInfo(
        "Variable(*, symbol, domain, value=None, unit=None, content=None, **metadata)",
        "Declare a typed term referenceable by formulas, models, parameters, and observations.",
        "formula",
    ),
    "parameter": SymbolInfo(
        "parameter(variable, value, *, content=None, describe=None, prior=None, "
        "label=None, metadata=None)",
        "Declare that a primitive Variable takes a concrete value.",
        "formula",
    ),
    "forall": SymbolInfo("forall(variable, body)", "Create a universal quantifier.", "formula"),
    "exists": SymbolInfo("exists(variable, body)", "Create an existential quantifier.", "formula"),
    "land": SymbolInfo("land(*operands)", "Create a logical conjunction formula.", "formula"),
    "lor": SymbolInfo("lor(*operands)", "Create a logical disjunction formula.", "formula"),
    "lnot": SymbolInfo("lnot(operand)", "Create a logical negation formula.", "formula"),
    "implies": SymbolInfo(
        "implies(antecedent, consequent)", "Create an implication formula.", "formula"
    ),
    "iff": SymbolInfo("iff(left, right)", "Create an equivalence formula.", "formula"),
    "equals": SymbolInfo("equals(left, right)", "Create an equality formula.", "formula"),
    "Nat": SymbolInfo("Nat", "Built-in primitive type for natural numbers.", "formula"),
    "Real": SymbolInfo("Real", "Built-in primitive type for real-valued scalars.", "formula"),
    "Probability": SymbolInfo(
        "Probability", "Built-in primitive type for probabilities in [0, 1].", "formula"
    ),
    "Bool": SymbolInfo("Bool", "Built-in primitive type for booleans.", "formula"),
    "roles_for_claim": SymbolInfo(
        "roles_for_claim(claim)", "Return role occurrences for a Gaia claim.", "introspection"
    ),
    "roles_for_package": SymbolInfo(
        "roles_for_package(package)", "Return role occurrences for a Gaia package.", "introspection"
    ),
}

for _name, _rule in DISTRIBUTION_RULES.items():
    params = ", ".join(f"{param}=..." for param in _rule.required)
    doc = (
        "Declare a Gaia Distribution. "
        + (
            "Beta-Binomial predictive distribution with dimensionless n/alpha/beta parameters."
            if _name == "BetaBinomial"
            else f"{_name} distribution factory with statically checked required parameters."
        )
    )
    SYMBOLS[_name] = SymbolInfo(f"{_name}(content, *, {params}, **metadata)", doc, "distribution")


RULE_GROUPS: tuple[dict[str, Any], ...] = (
    {"group": "package", "codes": ["GAIA060", "GAIA063", "GAIA064", "GAIA065", "GAIA066"]},
    {"group": "references", "codes": ["GAIA050", "GAIA067", "GAIA068"]},
    {"group": "exports", "codes": ["GAIA040", "GAIA041", "GAIA042"]},
    {"group": "knowledge", "codes": ["GAIA010", "GAIA011", "GAIA012", "GAIA013", "GAIA014"]},
    {"group": "prior", "codes": ["GAIA030", "GAIA031", "GAIA032", "GAIA033", "GAIA034"]},
    {"group": "distribution", "codes": ["GAIA080", "GAIA081", "GAIA082", "GAIA083", "GAIA084"]},
    {"group": "observation", "codes": ["GAIA090", "GAIA091", "GAIA092", "GAIA093"]},
    {"group": "artifact", "codes": ["GAIA070", "GAIA071", "GAIA072", "GAIA073", "GAIA074"]},
    {"group": "association", "codes": ["GAIA100", "GAIA101"]},
    {"group": "scaffold", "codes": ["GAIA102", "GAIA103", "GAIA104"]},
    {"group": "bayes", "codes": ["GAIA110", "GAIA111"]},
    {"group": "deprecation", "codes": ["GAIA020", "GAIA021", "GAIA022"]},
)


def rule_catalog() -> dict[str, Any]:
    """Return an agent-facing snapshot of the static Gaia rule catalog."""

    return {
        "software": "gaia",
        "upstream": GAIA_UPSTREAM,
        "symbols": [
            {
                "label": label,
                "detail": info.detail,
                "documentation": info.documentation,
                "group": info.group,
            }
            for label, info in sorted(SYMBOLS.items())
        ],
        "rules": list(RULE_GROUPS),
        "limits": [
            "Static diagnostics do not import or execute target Gaia packages.",
            "Runtime-only graph invariants are reported only when the AST or "
            "package files expose them.",
            "Unit compatibility is checked only for literal obvious mistakes; "
            "full Pint conversion remains Gaia compiler work.",
        ],
    }
