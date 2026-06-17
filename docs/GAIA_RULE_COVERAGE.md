# Gaia Rule Coverage

`gaia-lsp` targets `SiliconEinstein/Gaia` commit
`6354a3425fdadcf6f7e5f557dd3bc30f36d3297e`. The checker is static by design:
it parses Python, `pyproject.toml`, and `references.json`, but it does not
import or execute the target Gaia package.

## Covered Rule Groups

- Package shape: Gaia package metadata, derived import name, source root, and
  package `__init__.py`.
- Public exports: literal `__all__`, `export(...)`, duplicate names,
  non-string entries, sibling-module re-exports, and non-exportable
  Distribution/Variable/Domain bindings.
- References: strict bracketed `[@key]` markers, CSL-style `references.json`
  object schema, key grammar, required `type` and `title`, and local
  label/reference-key collisions.
- Knowledge calls: `claim`, `note`, `question`, current relation/action verbs,
  rationale warnings, deprecated v0.5 migration helpers, and legacy `PRIORS`.
- Imports and package context: unimported Gaia DSL helper calls, canonical Gaia
  import snippets, and package-local relative import suggestions derived from
  `src/<import_name>` modules.
- Navigation: package-scoped go-to-definition and references for local Gaia
  labels, including strict `[@label]` references in claim/note prose.
- Priors: `register_prior` target shape, finite probability inside Gaia
  Cromwell bounds `[0.001, 0.999]`, non-empty justification, and source id.
- Distributions: `Normal`, `LogNormal`, `Beta`, `Exponential`, `Gamma`,
  `StudentT`, `Cauchy`, `ChiSquared`, `Binomial`, `BetaBinomial`, and
  `Poisson` required parameters plus literal positive/probability/count checks.
- Observations: claim observation versus Distribution/Variable measurement
  branches, required `value=`, forbidden measurement `given=`, and deprecated
  `source_refs=`.
- Artifacts: `artifact`/`figure` kind, source/path requirements, locator rules,
  package-relative path safety, and missing local artifact files.
- Scaffold and association: `associate` probability/pattern rules,
  `candidate_relation` arity/pattern rules, `depends_on`, `decompose`, and
  `materialize` required structure.
- Bayes authoring: `gaia.engine.bayes.model` predictive-model helpers,
  `compare` model-list/exclusivity contracts, and package export recognition
  for Bayes helper claims.
- CLI language manual: `gaia-lsp-tool manual` renders the same rule catalog as
  a command-line language manual, and `gaia-lsp-tool explain <symbol|GAIAxxx>`
  gives focused symbol or diagnostic explanations.
- CLI navigation: `gaia-lsp-tool definition` and `gaia-lsp-tool references`
  emit JSON locations for editor providers and agent workflows.
- Upstream examples: fixed tests cover both `galileo-v0-5-gaia` and
  `mendel-v0-5-gaia` from the pinned Gaia commit, and
  `scripts/check_upstream_examples.sh` can re-scan the upstream examples tree
  before a release.

## Static Limits

- Runtime-only graph invariants still belong to `gaia build compile`. Examples:
  materialization package membership, decompose formula atom bijections, graph
  cycles, exact `Knowledge` object identity, and full formula type checking.
- Unit compatibility is checked only for obvious literal mistakes. Pint
  conversion and dimension analysis remain Gaia compiler/runtime work.
- Cross-package dependency loading is not executed. The LSP resolves local
  package labels, sibling re-exports, and `references.json`, but it does not
  import editable Gaia dependencies.
- Aliased Gaia imports are recognized when the import source is under
  `gaia.engine.lang`, `gaia.engine.lang.dsl`, or `gaia.engine.bayes`.

Use `gaia-lsp-tool rules` to emit the machine-readable catalog used by
completion, hover, and diagnostics. Use `gaia-lsp-tool manual` for the
human-readable language manual and `gaia-lsp-tool explain GAIA010` for a single
diagnostic explanation.
