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
        "README.md",
        "docs/for-users/language-reference.md",
        "docs/for-users/quick-start.md",
        "docs/for-users/authoring-workflow.md",
        "docs/reference/cli/index.md",
        "docs/reference/cli/author.md",
        "docs/reference/engine/lang.md",
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


@dataclass(frozen=True)
class DiagnosticInfo:
    code: str
    severity: str
    group: str
    title: str
    explanation: str
    fix: str
    example: str


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

GAIA_IMPORT_SNIPPETS: tuple[dict[str, str], ...] = (
    {
        "label": "from gaia.engine.lang import claim, note, question",
        "detail": "Core Gaia knowledge import",
        "documentation": "Import the three primary Gaia knowledge constructors.",
        "insertText": "from gaia.engine.lang import claim, note, question",
        "kind": "snippet",
        "sortText": "000_gaia_import_knowledge",
    },
    {
        "label": "from gaia.engine.lang import reasoning verbs",
        "detail": "derive, observe, compute, infer",
        "documentation": "Import Gaia's current reviewable reasoning action helpers.",
        "insertText": "from gaia.engine.lang import derive, observe, compute, infer",
        "kind": "snippet",
        "sortText": "001_gaia_import_reasoning",
    },
    {
        "label": "from gaia.engine.lang import relations",
        "detail": "equal, contradict, exclusive, associate",
        "documentation": "Import relation helpers used to connect Gaia claims.",
        "insertText": "from gaia.engine.lang import equal, contradict, exclusive, associate",
        "kind": "snippet",
        "sortText": "002_gaia_import_relations",
    },
    {
        "label": "from gaia.engine.lang import typed terms",
        "detail": "Variable, Nat, Real, Probability, Bool",
        "documentation": "Import typed term and primitive formula helpers.",
        "insertText": "from gaia.engine.lang import Variable, Nat, Real, Probability, Bool",
        "kind": "snippet",
        "sortText": "003_gaia_import_terms",
    },
    {
        "label": "from gaia.engine.lang import runtime types",
        "detail": "Claim, Knowledge, Formula, Term, Distribution",
        "documentation": "Import public Gaia runtime and formula classes for annotations.",
        "insertText": "from gaia.engine.lang import Claim, Knowledge, Formula, Term, Distribution",
        "kind": "snippet",
        "sortText": "003b_gaia_import_runtime_types",
    },
    {
        "label": "from gaia.engine.lang import distributions",
        "detail": "Normal, Beta, Binomial, Poisson, ...",
        "documentation": "Import Gaia distribution factories for observations and Bayes models.",
        "insertText": (
            "from gaia.engine.lang import Normal, LogNormal, Beta, Exponential, Gamma, "
            "StudentT, Cauchy, ChiSquared, Binomial, BetaBinomial, Poisson"
        ),
        "kind": "snippet",
        "sortText": "004_gaia_import_distributions",
    },
    {
        "label": "import gaia.engine.bayes as bayes",
        "detail": "Bayes model/compare namespace",
        "documentation": "Import the canonical namespace for bayes.model and bayes.compare.",
        "insertText": "import gaia.engine.bayes as bayes",
        "kind": "module",
        "sortText": "005_gaia_import_bayes",
    },
    {
        "label": "from gaia.unit import q",
        "detail": "Unit-aware quantity helper",
        "documentation": "Import Gaia's unit quantity constructor used by unit-aware examples.",
        "insertText": "from gaia.unit import q",
        "kind": "module",
        "sortText": "006_gaia_import_units",
    },
)

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

def _runtime_symbol(name: str, documentation: str) -> SymbolInfo:
    return SymbolInfo(name, documentation, "runtime")


PUBLIC_RUNTIME_SYMBOLS: dict[str, SymbolInfo] = {
    "ArithOp": _runtime_symbol("ArithOp", "Runtime formula record for arithmetic expressions."),
    "Associate": _runtime_symbol("Associate", "Runtime action record emitted by associate()."),
    "BoolExpr": _runtime_symbol(
        "BoolExpr", "Boolean-valued Gaia expression used by relations and formulas."
    ),
    "CandidateRelation": _runtime_symbol(
        "CandidateRelation", "Runtime scaffold record emitted by candidate_relation()."
    ),
    "Claim": _runtime_symbol("Claim", "Runtime Gaia Knowledge object that carries belief."),
    "ClaimAtom": _runtime_symbol("ClaimAtom", "Formula atom that references a Gaia claim."),
    "ClaimKind": _runtime_symbol("ClaimKind", "Runtime enumeration for Gaia claim kinds."),
    "Compose": _runtime_symbol("Compose", "Runtime action record emitted by compose()."),
    "Composition": _runtime_symbol("Composition", "Runtime object grouping Gaia actions."),
    "Compute": _runtime_symbol("Compute", "Runtime action record emitted by compute()."),
    "Constant": _runtime_symbol("Constant", "Formula term for a literal constant value."),
    "Contradict": _runtime_symbol(
        "Contradict", "Runtime relation action emitted by contradict()."
    ),
    "Decompose": _runtime_symbol("Decompose", "Runtime action record emitted by decompose()."),
    "DependsOn": _runtime_symbol("DependsOn", "Runtime scaffold emitted by depends_on()."),
    "Derive": _runtime_symbol("Derive", "Runtime action record emitted by derive()."),
    "DerivedDistribution": _runtime_symbol(
        "DerivedDistribution", "Boolean-valued expression for derived distributions."
    ),
    "Distribution": _runtime_symbol("Distribution", "Runtime base class for distributions."),
    "Equal": _runtime_symbol("Equal", "Runtime relation action emitted by equal()."),
    "Equals": _runtime_symbol("Equals", "Formula node for equality predicates."),
    "Exclusive": _runtime_symbol("Exclusive", "Runtime relation action emitted by exclusive()."),
    "Exists": _runtime_symbol("Exists", "Formula node for existential quantification."),
    "Forall": _runtime_symbol("Forall", "Formula node for universal quantification."),
    "Formula": _runtime_symbol("Formula", "Base class for Gaia formula expressions."),
    "FunctionApp": _runtime_symbol("FunctionApp", "Formula term applying a function symbol."),
    "FunctionSymbol": _runtime_symbol("FunctionSymbol", "Named function symbol in formulas."),
    "Greater": _runtime_symbol("Greater", "Formula node for greater-than comparison."),
    "GreaterEqual": _runtime_symbol("GreaterEqual", "Formula node for >= comparison."),
    "Iff": _runtime_symbol("Iff", "Formula node for logical equivalence."),
    "Implies": _runtime_symbol("Implies", "Formula node for logical implication."),
    "Infer": _runtime_symbol("Infer", "Runtime action record emitted by infer()."),
    "Knowledge": _runtime_symbol("Knowledge", "Base runtime object for Gaia knowledge."),
    "Land": _runtime_symbol("Land", "Formula node for logical conjunction."),
    "Less": _runtime_symbol("Less", "Formula node for less-than comparison."),
    "LessEqual": _runtime_symbol("LessEqual", "Formula node for <= comparison."),
    "Lnot": _runtime_symbol("Lnot", "Formula node for logical negation."),
    "Lor": _runtime_symbol("Lor", "Formula node for logical disjunction."),
    "MaterializationLink": _runtime_symbol(
        "MaterializationLink", "Runtime record emitted by materialize()."
    ),
    "NotEquals": _runtime_symbol("NotEquals", "Formula node for inequality predicates."),
    "Note": _runtime_symbol("Note", "Runtime Gaia Knowledge object emitted by note()."),
    "Observe": _runtime_symbol("Observe", "Runtime action record emitted by observe()."),
    "PredicateSymbol": _runtime_symbol("PredicateSymbol", "Named predicate symbol in formulas."),
    "PrimitiveType": _runtime_symbol("PrimitiveType", "Descriptor for primitive formula types."),
    "Question": _runtime_symbol("Question", "Runtime Knowledge object emitted by question()."),
    "RoleOccurrence": _runtime_symbol("RoleOccurrence", "Runtime record for a claim role."),
    "Term": _runtime_symbol("Term", "Base class for Gaia formula terms."),
    "UserPredicate": _runtime_symbol("UserPredicate", "Runtime user-defined predicate."),
}

SYMBOLS.update(PUBLIC_RUNTIME_SYMBOLS)

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
    {
        "group": "knowledge",
        "codes": ["GAIA010", "GAIA011", "GAIA012", "GAIA013", "GAIA014", "GAIA015"],
    },
    {"group": "prior", "codes": ["GAIA030", "GAIA031", "GAIA032", "GAIA033", "GAIA034"]},
    {"group": "distribution", "codes": ["GAIA080", "GAIA081", "GAIA082", "GAIA083", "GAIA084"]},
    {"group": "observation", "codes": ["GAIA090", "GAIA091", "GAIA092", "GAIA093"]},
    {"group": "artifact", "codes": ["GAIA070", "GAIA071", "GAIA072", "GAIA073", "GAIA074"]},
    {"group": "association", "codes": ["GAIA100", "GAIA101"]},
    {"group": "scaffold", "codes": ["GAIA102", "GAIA103", "GAIA104"]},
    {"group": "bayes", "codes": ["GAIA110", "GAIA111"]},
    {"group": "deprecation", "codes": ["GAIA020", "GAIA021", "GAIA022"]},
)

DIAGNOSTICS: tuple[DiagnosticInfo, ...] = (
    DiagnosticInfo(
        "GAIA001",
        "error",
        "syntax",
        "Python syntax error",
        "The source file cannot be parsed as Python, so Gaia DSL checks cannot continue.",
        "Fix the Python syntax at the reported location, then rerun gaia-lint or check.",
        "gaia-lsp-tool check src/pkg/__init__.py --fail-on-blocking",
    ),
    DiagnosticInfo(
        "GAIA010",
        "error",
        "knowledge",
        "Knowledge call missing content",
        "claim(), note(), and question() should start with non-empty string content.",
        "Add meaningful prose content as the first positional argument.",
        'claim("The intervention changes the measured observable.")',
    ),
    DiagnosticInfo(
        "GAIA011",
        "warning",
        "knowledge",
        "Inline prior shortcut",
        "claim(prior=...) is accepted as a shortcut, but reviewable packages need provenance.",
        "Prefer register_prior(claim_obj, value, justification=...) with source metadata.",
        'register_prior(result_claim, 0.7, justification="Independent calibration.")',
    ),
    DiagnosticInfo(
        "GAIA012",
        "warning",
        "knowledge",
        "Reviewable reasoning missing rationale",
        "Reasoning and relation helpers are audit points; empty rationale makes review weaker.",
        "Add a concise rationale explaining why the relation or action is justified.",
        'derive(conclusion, given=[premise], rationale="Mechanism follows from setup.")',
    ),
    DiagnosticInfo(
        "GAIA013",
        "error",
        "knowledge",
        "Non-probabilistic knowledge has prior",
        "note() and question() do not participate in belief propagation and cannot carry prior=.",
        "Move probability to a claim() plus register_prior(), or remove prior=.",
        'background = note("Experimental setup.")',
    ),
    DiagnosticInfo(
        "GAIA014",
        "error",
        "knowledge",
        "Invalid claim shape",
        "A claim cannot mix incompatible proposition/formula/tolerance forms.",
        "Use exactly one claim form and keep tolerance positive for equation propositions.",
        'claim("x equals y within tolerance.", equals(x, y), tolerance=0.01)',
    ),
    DiagnosticInfo(
        "GAIA015",
        "error",
        "knowledge",
        "Gaia DSL symbol is not imported",
        "A call looks like a Gaia DSL helper, but the file has not imported or defined it.",
        "Import the helper from gaia.engine.lang or gaia.engine.bayes before using it.",
        "from gaia.engine.lang import claim",
    ),
    DiagnosticInfo(
        "GAIA020",
        "warning",
        "deprecation",
        "Deprecated context or setting",
        "context() and setting() are compatibility aliases for old packages.",
        "Use note() for definitions, setup, or other non-probabilistic context.",
        'setup = note("The assay is run at room temperature.")',
    ),
    DiagnosticInfo(
        "GAIA021",
        "warning",
        "deprecation",
        "Deprecated relation helper",
        "Legacy relation aliases no longer describe the v0.5 authoring surface.",
        "Use contradict(), equal(), or exclusive() directly.",
        'contradict(model_a_prediction, model_b_prediction, rationale="Mutually impossible.")',
    ),
    DiagnosticInfo(
        "GAIA022",
        "warning",
        "deprecation",
        "Deprecated strategy helper",
        "Old strategy helpers hide the current explicit action/relation graph.",
        "Spell the graph with derive(), infer(), compute(), observe(), compose(), "
        "or Bayes helpers.",
        'derive(prediction, given=[model], rationale="Model entails the prediction.")',
    ),
    DiagnosticInfo(
        "GAIA030",
        "error",
        "prior",
        "Invalid prior probability",
        "register_prior() requires a finite probability inside Gaia Cromwell bounds.",
        f"Use a numeric value in [{CROMWELL_EPS}, {1.0 - CROMWELL_EPS}].",
        'register_prior(model, 0.6, justification="External benchmark.")',
    ),
    DiagnosticInfo(
        "GAIA031",
        "error",
        "prior",
        "Prior missing justification",
        "External priors must be auditable and explain where the probability came from.",
        "Add a non-empty justification= keyword.",
        'register_prior(model, 0.6, justification="Meta-analysis estimate.")',
    ),
    DiagnosticInfo(
        "GAIA032",
        "error",
        "prior",
        "Prior targets a string",
        "register_prior() must target the Claim object, not a label string.",
        "Pass the local claim binding as the first argument.",
        'register_prior(model_claim, 0.6, justification="External source.")',
    ),
    DiagnosticInfo(
        "GAIA033",
        "error",
        "prior",
        "Legacy PRIORS dictionary",
        "Gaia v0.5 rejects package-level PRIORS dictionaries.",
        "Replace PRIORS with one register_prior() call per sourced prior.",
        'register_prior(claim_obj, 0.55, justification="Reviewer calibration.")',
    ),
    DiagnosticInfo(
        "GAIA034",
        "error",
        "prior",
        "Invalid prior source id",
        "source_id must be a non-empty string so prior provenance remains stable.",
        "Use a short source id such as user_priors, reviewer, or a paper key.",
        'register_prior(claim_obj, 0.55, justification="...", source_id="reviewer")',
    ),
    DiagnosticInfo(
        "GAIA040",
        "error",
        "exports",
        "Unknown public export",
        "__all__ lists a name without a local Gaia Knowledge binding.",
        "Remove the name or define/export a local claim, note, question, relation, or action.",
        '__all__ = ["headline_claim"]',
    ),
    DiagnosticInfo(
        "GAIA041",
        "warning",
        "exports",
        "Duplicate public export",
        "Duplicate __all__ entries make the curated package surface ambiguous.",
        "Keep each exported binding name once.",
        '__all__ = ["headline_claim", "support_relation"]',
    ),
    DiagnosticInfo(
        "GAIA042",
        "error",
        "exports",
        "Dynamic public export",
        "Gaia package exports should be literal strings so static tools can verify them.",
        "Use a literal list or tuple of strings.",
        '__all__: list[str] = ["headline_claim"]',
    ),
    DiagnosticInfo(
        "GAIA050",
        "warning",
        "references",
        "Unresolved strict reference",
        "A [@key] marker does not resolve to references.json or a local Gaia label.",
        "Add the citation key, create a local binding, or fix the marker spelling.",
        'claim("The result follows prior work [@Aspect1982].")',
    ),
    DiagnosticInfo(
        "GAIA060",
        "error",
        "package",
        "Missing pyproject.toml",
        "A Gaia package directory must contain pyproject.toml.",
        "Run gaia build init or add the package manifest.",
        "gaia build init my-paper-gaia",
    ),
    DiagnosticInfo(
        "GAIA063",
        "error",
        "package",
        "Invalid pyproject.toml",
        "The package manifest cannot be parsed as TOML.",
        "Fix the TOML syntax and rerun the check.",
        "gaia-lsp-tool check my-paper-gaia --fail-on-blocking",
    ),
    DiagnosticInfo(
        "GAIA064",
        "error",
        "package",
        "Missing Gaia package metadata",
        '[tool.gaia].type must be "knowledge-package" for Gaia packages.',
        "Add or correct the [tool.gaia] table in pyproject.toml.",
        '[tool.gaia]\ntype = "knowledge-package"',
    ),
    DiagnosticInfo(
        "GAIA065",
        "error",
        "package",
        "Missing project metadata",
        "The package needs core Python project metadata for import-name discovery.",
        "Set [project].name and other required pyproject metadata.",
        '[project]\nname = "my-paper-gaia"',
    ),
    DiagnosticInfo(
        "GAIA066",
        "error",
        "package",
        "Missing package source root",
        "The package src layout or root __init__.py is missing.",
        "Create src/<import_name>/__init__.py or fix the project name/source layout.",
        "src/my_paper/__init__.py",
    ),
    DiagnosticInfo(
        "GAIA067",
        "error",
        "references",
        "Invalid references.json",
        "references.json must be an object keyed by CSL-style citation keys.",
        "Fix JSON syntax, key grammar, CSL type, and title fields.",
        '{"Aspect1982": {"type": "article-journal", "title": "Experimental Realization"}}',
    ),
    DiagnosticInfo(
        "GAIA068",
        "error",
        "references",
        "Reference key collides with local label",
        "Citation keys and local Gaia labels share one namespace.",
        "Rename either the references.json key or the local Gaia binding.",
        "Use Aspect1982 for the citation and aspect_experiment for the claim.",
    ),
    DiagnosticInfo(
        "GAIA070",
        "error",
        "artifact",
        "Invalid artifact kind",
        "artifact(kind=...) must use a supported Gaia artifact kind.",
        "Use figure, table, dataset, notebook, or attachment.",
        'artifact(kind="dataset", path="artifacts/data.csv")',
    ),
    DiagnosticInfo(
        "GAIA071",
        "error",
        "artifact",
        "Unsafe artifact path",
        "Artifact paths must be package-relative and must not escape the package root.",
        "Use a relative path under the package directory.",
        'figure(path="artifacts/figures/fig1.png")',
    ),
    DiagnosticInfo(
        "GAIA072",
        "error",
        "artifact",
        "Source-bound artifact missing locator",
        "Figures and tables tied to a source need a source-local locator.",
        'Add locator="Fig. 3", locator="Table 1", or equivalent.',
        'figure(source="Liu2015", locator="Fig. 3", path="artifacts/fig3.png")',
    ),
    DiagnosticInfo(
        "GAIA073",
        "error",
        "artifact",
        "Artifact missing source or path",
        "Artifact metadata needs at least one durable source or local path.",
        "Add source=, path=, or both.",
        'artifact(kind="attachment", path="artifacts/supplement.xlsx")',
    ),
    DiagnosticInfo(
        "GAIA074",
        "warning",
        "artifact",
        "Artifact path does not exist",
        "The declared local artifact file is missing from the package tree.",
        "Add the file or correct path=.",
        'figure(path="artifacts/figures/source_fig.png")',
    ),
    DiagnosticInfo(
        "GAIA080",
        "error",
        "distribution",
        "Distribution missing content",
        "Distribution factories should start with non-empty descriptive content.",
        "Add a natural-language description as the first positional argument.",
        'Normal("LDL reduction percentage", mu=35.0, sigma=4.0)',
    ),
    DiagnosticInfo(
        "GAIA081",
        "error",
        "distribution",
        "Invalid distribution parameters",
        "Distribution parameters are keyword-only and required parameters must be present.",
        "Use the documented keyword parameters for the selected distribution.",
        'Beta("Response probability", alpha=8, beta=2)',
    ),
    DiagnosticInfo(
        "GAIA082",
        "error",
        "distribution",
        "Distribution parameter must be positive",
        "Scale, rate, df, alpha, beta, and similar parameters must be positive.",
        "Use a positive numeric scalar.",
        'Gamma("Reaction rate", alpha=2.0, rate=0.5)',
    ),
    DiagnosticInfo(
        "GAIA083",
        "error",
        "distribution",
        "Distribution probability out of range",
        "Probability parameters must be inside [0, 1].",
        "Use a valid probability literal.",
        'Binomial("Success count", n=20, p=0.35)',
    ),
    DiagnosticInfo(
        "GAIA084",
        "error",
        "distribution",
        "Distribution count is invalid",
        "Count parameters such as n must be non-negative integers.",
        "Use an integer count greater than or equal to zero.",
        'Poisson("Event count", rate=3.0)',
    ),
    DiagnosticInfo(
        "GAIA090",
        "error",
        "observation",
        "Measurement missing value",
        "Observing a Distribution or Variable requires value=.",
        "Add value= to the observation.",
        'observe(ldl_pct, value=38.0, error=2.2, rationale="Trial measurement.")',
    ),
    DiagnosticInfo(
        "GAIA091",
        "error",
        "observation",
        "Measurement uses given",
        "Distribution and Variable measurement events are unconditional in Gaia.",
        "Remove given= from measurement observations.",
        'observe(ldl_pct, value=38.0, error=2.2)',
    ),
    DiagnosticInfo(
        "GAIA092",
        "error",
        "observation",
        "Claim observation uses measurement fields",
        "value= and error= apply to Distribution or Variable targets, not ordinary claims.",
        "Use observe(claim, given=...) or observe(variable_or_distribution, value=...).",
        'observe(observed_claim, given=[source_claim], rationale="Reported directly.")',
    ),
    DiagnosticInfo(
        "GAIA093",
        "warning",
        "observation",
        "Deprecated source_refs",
        "observe(source_refs=...) predates strict [@key] reference handling.",
        "Put citation markers in rationale or content instead.",
        'observe(result, rationale="Measured by the cited assay [@Trial2025].")',
    ),
    DiagnosticInfo(
        "GAIA100",
        "error",
        "association",
        "Invalid association probabilities",
        "associate() requires p_a_given_b and p_b_given_a probabilities in [0, 1].",
        "Provide both conditional probabilities as numeric literals.",
        "associate(a, b, p_a_given_b=0.8, p_b_given_a=0.75)",
    ),
    DiagnosticInfo(
        "GAIA101",
        "error",
        "association",
        "Invalid association pattern",
        "Association pattern must be supported and consistent with the probabilities.",
        "Use equal, contradict, or exclusive with matching conditional probabilities.",
        'associate(a, b, p_a_given_b=0.8, p_b_given_a=0.75, pattern="equal")',
    ),
    DiagnosticInfo(
        "GAIA102",
        "error",
        "scaffold",
        "Candidate relation has too few claims",
        "candidate_relation() needs enough claims to be reviewable.",
        "Provide at least two claims.",
        'candidate_relation(claims=[a, b], pattern="equal")',
    ),
    DiagnosticInfo(
        "GAIA103",
        "error",
        "scaffold",
        "Invalid candidate relation pattern",
        "candidate_relation() only supports the current relation pattern vocabulary.",
        "Use equal, contradict, or exclusive.",
        'candidate_relation(claims=[a, b], pattern="contradict")',
    ),
    DiagnosticInfo(
        "GAIA104",
        "error",
        "scaffold",
        "Incomplete scaffold call",
        "Scaffold, decomposition, or materialization calls are missing required structure.",
        "Add the required conclusion/given/parts/formula/by arguments.",
        'depends_on(conclusion, given=[premise], rationale="Load-bearing dependency.")',
    ),
    DiagnosticInfo(
        "GAIA110",
        "error",
        "bayes",
        "Bayes model is incomplete",
        "bayes.model() requires observable= and distribution=.",
        "Provide the observable variable/measurement and predictive distribution.",
        "bayes.model(hypothesis, observable=ldl_pct, distribution=normal_pred)",
    ),
    DiagnosticInfo(
        "GAIA111",
        "error",
        "bayes",
        "Bayes compare is invalid",
        "bayes.compare() requires a non-empty model list and supported exclusivity.",
        "Pass models=[...] and a supported exclusivity mode.",
        'bayes.compare(data, models=[model_a, model_b], '
        'exclusivity="exhaustive_pairwise_complement")',
    ),
)

DIAGNOSTIC_BY_CODE: dict[str, DiagnosticInfo] = {item.code: item for item in DIAGNOSTICS}

MANUAL_SECTION_IDS = (
    "overview",
    "authoring-surface",
    "diagnostics",
    "cli",
    "static-limits",
)


def symbol_catalog() -> list[dict[str, str]]:
    """Return the documented Gaia symbols used for completion and hover."""

    return [
        {
            "label": label,
            "detail": info.detail,
            "documentation": info.documentation,
            "group": info.group,
        }
        for label, info in sorted(SYMBOLS.items())
    ]


def import_completion_items() -> list[dict[str, str]]:
    """Return import-oriented completion snippets for Gaia packages."""

    return [dict(item) for item in GAIA_IMPORT_SNIPPETS]


def preferred_import_for_symbol(symbol: str) -> str:
    """Return the most direct import statement for a Gaia DSL symbol."""

    if symbol in BAYES_CALLS:
        return f"from gaia.engine.bayes import {symbol}"
    return f"from gaia.engine.lang import {symbol}"


def diagnostic_catalog() -> list[dict[str, str]]:
    """Return static diagnostic documentation."""

    return [
        {
            "code": item.code,
            "severity": item.severity,
            "group": item.group,
            "title": item.title,
            "explanation": item.explanation,
            "fix": item.fix,
            "example": item.example,
        }
        for item in DIAGNOSTICS
    ]


def manual_catalog(section: str = "all") -> dict[str, Any]:
    """Return the Gaia authoring manual as structured JSON-ready data."""

    sections = _manual_sections()
    if section != "all":
        sections = [item for item in sections if item["id"] == section]
        if not sections:
            raise KeyError(section)
    return {
        "software": "gaia",
        "upstream": GAIA_UPSTREAM,
        "sections": sections,
    }


def render_manual_markdown(section: str = "all") -> str:
    """Render the Gaia authoring manual as Markdown for command-line use."""

    catalog = manual_catalog(section)
    lines = [
        "# Gaia LSP Language Manual",
        "",
        f"Source: {GAIA_UPSTREAM['repository']} @ {GAIA_UPSTREAM['commit']}",
        f"URL: {GAIA_UPSTREAM['url']}",
        "",
    ]
    for item in catalog["sections"]:
        lines.extend([f"## {item['title']}", "", item["summary"], ""])
        for entry in item.get("items", []):
            lines.append(f"- {entry}")
        if item.get("items"):
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def explain_topic(topic: str) -> dict[str, Any]:
    """Explain one Gaia symbol or diagnostic code."""

    diagnostic_info = DIAGNOSTIC_BY_CODE.get(topic.upper())
    if diagnostic_info is not None:
        return {
            "software": "gaia",
            "kind": "diagnostic",
            "diagnostic": diagnostic_catalog_item(diagnostic_info),
        }
    symbol_info = SYMBOLS.get(topic)
    if symbol_info is not None:
        return {
            "software": "gaia",
            "kind": "symbol",
            "symbol": {
                "label": topic,
                "detail": symbol_info.detail,
                "documentation": symbol_info.documentation,
                "group": symbol_info.group,
            },
        }
    raise KeyError(topic)


def render_explanation_markdown(payload: dict[str, Any]) -> str:
    """Render an explain_topic payload as Markdown."""

    if payload["kind"] == "diagnostic":
        item = payload["diagnostic"]
        return (
            f"# {item['code']}: {item['title']}\n\n"
            f"Severity: {item['severity']}\n\n"
            f"{item['explanation']}\n\n"
            f"Fix: {item['fix']}\n\n"
            f"Example: `{item['example']}`\n"
        )
    item = payload["symbol"]
    return (
        f"# {item['label']}\n\n"
        f"`{item['detail']}`\n\n"
        f"{item['documentation']}\n"
    )


def diagnostic_catalog_item(item: DiagnosticInfo) -> dict[str, str]:
    """Convert one diagnostic metadata record to JSON-ready data."""

    return {
        "code": item.code,
        "severity": item.severity,
        "group": item.group,
        "title": item.title,
        "explanation": item.explanation,
        "fix": item.fix,
        "example": item.example,
    }


def _manual_sections() -> list[dict[str, Any]]:
    symbol_groups: dict[str, list[str]] = {}
    for symbol in symbol_catalog():
        symbol_groups.setdefault(symbol["group"], []).append(
            f"{symbol['label']}: `{symbol['detail']}` - {symbol['documentation']}"
        )
    diagnostic_items = [
        f"{item['code']} ({item['severity']}): {item['title']} - {item['fix']}"
        for item in diagnostic_catalog()
    ]
    return [
        {
            "id": "overview",
            "title": "Overview",
            "summary": (
                "Gaia v0.5 packages are Python DSL projects for explicit scientific "
                "claims, reviewable reasoning, references, priors, and probabilistic "
                "belief updates. The LSP is static: it parses source and metadata "
                "without importing or executing author code."
            ),
            "items": [
                "Primary authoring path: run `gaia sdk`, then write Python DSL directly.",
                "Static source: README, language reference, CLI reference, and public "
                "gaia.engine.lang exports from the upstream Gaia commit.",
                "Main workflow: gaia build compile -> Gaia IR/factor graph -> gaia run infer.",
            ],
        },
        {
            "id": "authoring-surface",
            "title": "Authoring Surface",
            "summary": (
                "The manual groups the current Gaia public authoring symbols by layer. "
                "Completion and hover use the same catalog."
            ),
            "items": [
                "Knowledge: " + ", ".join(sorted(CONTENT_CALLS | ARTIFACT_CALLS)),
                "Reasoning actions: " + ", ".join(sorted(ACTION_CALLS)),
                "Relations: "
                + ", ".join(sorted(RELATION_CALLS | ASSOCIATION_CALLS | {"decompose"})),
                "Scaffolds: " + ", ".join(sorted(SCAFFOLD_CALLS)),
                "Composition: " + ", ".join(sorted(COMPOSITION_CALLS)),
                "Priors: register_prior",
                "Formula and typed terms: "
                + ", ".join(
                    [
                        "Variable",
                        "Nat",
                        "Real",
                        "Probability",
                        "Bool",
                        "forall",
                        "exists",
                        "land",
                        "lor",
                        "lnot",
                        "implies",
                        "iff",
                        "equals",
                    ]
                ),
                "Distributions: " + ", ".join(sorted(DISTRIBUTIONS)),
                "Bayes helpers: model, compare",
                "Runtime/API types: Claim, Knowledge, Formula, Term, Distribution, "
                "RoleOccurrence, and action/relation records.",
                "Canonical imports: "
                + "; ".join(item["label"] for item in GAIA_IMPORT_SNIPPETS),
                "Detailed symbols: " + "; ".join(symbol_groups.get("knowledge", [])[:4]),
            ],
        },
        {
            "id": "diagnostics",
            "title": "Diagnostics",
            "summary": (
                "Diagnostics use stable GAIAxxx codes. Error diagnostics are blocking; "
                "warning diagnostics are advisory but still returned in JSON."
            ),
            "items": diagnostic_items,
        },
        {
            "id": "cli",
            "title": "CLI",
            "summary": (
                "The command-line surface supports linting, agent JSON, completion, "
                "hover text, definition/references navigation, symbol lookup, "
                "diagnostics, and this manual."
            ),
            "items": [
                "gaia-lint path/to/package --json",
                "gaia-lsp-tool check path/to/package --fail-on-blocking",
                "gaia-lsp-tool complete path/to/module.py",
                "gaia-lsp-tool hover path/to/module.py --line 3 --character 10",
                "gaia-lsp-tool definition path/to/module.py --line 3 --character 10",
                "gaia-lsp-tool references path/to/module.py --line 3 --character 10",
                "gaia-lsp-tool symbols path/to/module.py",
                "gaia-lsp-tool rules",
                "gaia-lsp-tool manual --section diagnostics",
                "gaia-lsp-tool explain GAIA010",
                "gaia-lsp-tool explain claim",
            ],
        },
        {
            "id": "static-limits",
            "title": "Static Limits",
            "summary": "Static analysis catches authoring mistakes before Gaia runtime checks.",
            "items": [
                "Runtime-only graph invariants still belong to `gaia build compile`.",
                "Full unit conversion and dimension analysis remain Gaia compiler work.",
                "The LSP does not import editable dependencies or execute package code.",
            ],
        },
    ]


def rule_catalog() -> dict[str, Any]:
    """Return an agent-facing snapshot of the static Gaia rule catalog."""

    return {
        "software": "gaia",
        "upstream": GAIA_UPSTREAM,
        "symbols": symbol_catalog(),
        "diagnostics": diagnostic_catalog(),
        "manual": manual_catalog(),
        "rules": list(RULE_GROUPS),
        "limits": [
            "Static diagnostics do not import or execute target Gaia packages.",
            "Runtime-only graph invariants are reported only when the AST or "
            "package files expose them.",
            "Unit compatibility is checked only for literal obvious mistakes; "
            "full Pint conversion remains Gaia compiler work.",
        ],
    }
