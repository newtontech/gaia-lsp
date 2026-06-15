# gaia-lsp

`gaia-lsp` provides static Language Server Protocol diagnostics and agent-facing
CLI checks for Gaia Lang Python DSL packages.

The first release is intentionally static: it parses Python source with `ast`
and never imports or executes the target Gaia package. That keeps editor and
agent preflight checks fast and safe for scientific reasoning packages whose
compile path may execute author code.

## Install

```bash
pip install gaia-lsp
```

The JSON CLI and static linter work from the base install. The stdio LSP server
needs the optional LSP runtime:

```bash
pip install "gaia-lsp[lsp]"
```

For local development:

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
ruff check src tests
```

## CLI

Run file diagnostics:

```bash
gaia-lint path/to/package/src/pkg/__init__.py
gaia-lint path/to/package/src/pkg/__init__.py --json
```

Run the agent-facing JSON tool:

```bash
gaia-lsp-tool capabilities
gaia-lsp-tool check path/to/package --fail-on-blocking
gaia-lsp-tool complete path/to/package/src/pkg/__init__.py
gaia-lsp-tool hover path/to/package/src/pkg/__init__.py --line 3 --character 10
gaia-lsp-tool rules
```

Start the LSP server on stdio:

```bash
gaia-lsp --stdio
```

## Current Diagnostics

- `GAIA001`: Python syntax error.
- `GAIA010`: `claim`, `note`, or `question` missing non-empty string content.
- `GAIA011`: `claim(prior=...)` shortcut used instead of auditable `register_prior`.
- `GAIA012`: Reviewable reasoning call missing a non-empty `rationale`.
- `GAIA013`: `note` or `question` incorrectly carries `prior=`.
- `GAIA014`: Invalid `claim(..., proposition/formula/tolerance=...)` shape.
- `GAIA020`: Deprecated `context` or `setting`; use `note`.
- `GAIA021`: Legacy `contradiction`; use `contradict`.
- `GAIA022`: Legacy strategy helper; spell the v0.5+ graph explicitly.
- `GAIA030`: Invalid `register_prior` probability or Cromwell-bound violation.
- `GAIA031`: Missing `register_prior(..., justification=...)`.
- `GAIA032`: `register_prior` targets a string instead of a Claim object.
- `GAIA033`: Legacy `PRIORS = {...}` dictionary.
- `GAIA034`: Empty or non-string `register_prior(..., source_id=...)`.
- `GAIA040`: `__all__` exports a name without a local Gaia Knowledge binding.
- `GAIA041`: Duplicate `__all__` export.
- `GAIA042`: Dynamic or non-string `__all__` entry.
- `GAIA050`: Strict `[@ref]` reference is unresolved in local labels or `references.json`.
- `GAIA063`: Invalid `pyproject.toml`.
- `GAIA064`: Missing or wrong `[tool.gaia].type = "knowledge-package"`.
- `GAIA065`: Missing required project metadata.
- `GAIA066`: Missing Gaia package source root or `__init__.py`.
- `GAIA067`: Invalid `references.json` schema, key, CSL type, or title.
- `GAIA068`: `references.json` key collides with a local Gaia label or binding.
- `GAIA070`: Invalid artifact kind.
- `GAIA071`: Artifact path is absolute or escapes the package root.
- `GAIA072`: `figure` or `table` artifact with `source=` is missing `locator=`.
- `GAIA073`: Artifact is missing both `source=` and `path=`.
- `GAIA074`: Artifact `path=` does not exist under the package root.
- `GAIA080`: Distribution factory missing non-empty content.
- `GAIA081`: Distribution factory missing required or keyword-only parameters.
- `GAIA082`: Distribution parameter that must be positive is invalid.
- `GAIA083`: Probability parameter is outside `[0, 1]`.
- `GAIA084`: Count parameter is not a non-negative integer.
- `GAIA090`: `observe(distribution_or_variable, ...)` missing `value=`.
- `GAIA091`: Measurement observation incorrectly uses `given=`.
- `GAIA092`: Claim observation incorrectly uses `value=` or `error=`.
- `GAIA093`: Deprecated `observe(source_refs=...)`.
- `GAIA100`: `associate` conditional probabilities are invalid.
- `GAIA101`: `associate` pattern is invalid or inconsistent with probabilities.
- `GAIA102`: `candidate_relation` has too few claims.
- `GAIA103`: `candidate_relation` pattern is invalid.
- `GAIA104`: Scaffold/decomposition/materialization call is structurally incomplete.
- `GAIA110`: `bayes.model` is missing `observable=` or `distribution=`.
- `GAIA111`: `bayes.compare` has invalid `models=` or `exclusivity=`.

## Source Alignment

The diagnostic rules target `SiliconEinstein/Gaia` commit
`6354a3425fdadcf6f7e5f557dd3bc30f36d3297e`, including package metadata,
curated exports, CSL references, current DSL helpers, distribution factories,
measurement observations, artifact metadata, scaffold actions, `register_prior`,
and strict `[@key]` references. See `docs/GAIA_RULE_COVERAGE.md` and
`gaia-lsp-tool rules` for the auditable rule catalog and static-analysis limits.
