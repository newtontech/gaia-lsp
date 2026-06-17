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
mypy src
```

## VS Code Extension

The VS Code extension lives in `gaia-vscode/` and publishes as
`newtontech.gaia-vscode`. It calls the same static `gaia-lsp-tool` JSON CLI and
renders Gaia diagnostics in the Problems panel. The extension also wires Gaia
completion, hover, go-to-definition, find-references, signature-help, quick-fix
code actions, document-symbol, rule-catalog, and authoring-context features
through the same CLI surface.

Local package check:

```bash
cd gaia-vscode
npm ci
npm test
npm run package
```

Release-level verification:

```bash
ruff check src tests
mypy src
python3 -m pytest
python3 -m build
twine check dist/*
(cd gaia-vscode && npm run lint && npm test && npm run package)
scripts/check_upstream_examples.sh
```

Marketplace publishing is configured in `.github/workflows/publish-vscode.yml`.
Create the `newtontech` Marketplace publisher and configure the `VSCE_PAT`
secret before running the publish job. See
`docs/VSCODE_MARKETPLACE_PUBLISHING.md`.

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
gaia-lsp-tool context path/to/package --query register_prior
gaia-lsp-tool complete path/to/package/src/pkg/__init__.py
gaia-lsp-tool hover path/to/package/src/pkg/__init__.py --line 3 --character 10
gaia-lsp-tool definition path/to/package/src/pkg/__init__.py --line 3 --character 10
gaia-lsp-tool references path/to/package/src/pkg/__init__.py --line 3 --character 10
gaia-lsp-tool workspace-symbols path/to/package --query model
gaia-lsp-tool symbols path/to/package/src/pkg/__init__.py
gaia-lsp-tool folding path/to/package/src/pkg/__init__.py
gaia-lsp-tool links path/to/package/src/pkg/__init__.py
gaia-lsp-tool rename path/to/package/src/pkg/__init__.py new_label --line 3 --character 10
gaia-lsp-tool semantic-tokens path/to/package/src/pkg/__init__.py
gaia-lsp-tool rules
gaia-lsp-tool manual
gaia-lsp-tool manual --section diagnostics
gaia-lsp-tool explain GAIA010
gaia-lsp-tool explain claim
```

`manual` renders a CLI-readable Gaia language manual sourced from the upstream
Gaia README, language reference, CLI reference, and public `gaia.engine.lang`
surface. `explain` drills into one Gaia symbol or one diagnostic code. `rules`
keeps the same information machine-readable for agents and editor extensions.
`complete` includes Gaia import snippets and package-local relative import
suggestions when the path is inside a Gaia package. `context` returns the same
completion list plus package/module/export/version metadata for agent workflows;
`context --query <symbol-or-code>` narrows that payload and includes matching
Gaia symbol and diagnostic explanations for focused agent lookup.
`definition`, `references`, `workspace-symbols`, and `rename` resolve local Gaia
bindings and labels across the package source tree, including strict `[@label]`
prose references. `folding`, `links`, and `semantic-tokens` expose the same
static editor surfaces over JSON for agent and CI workflows.

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
- `GAIA015`: A Gaia DSL helper such as `claim()` is used without an import.
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
- `GAIA120`: Declared Gaia language version is outside the supported rule catalog.
- `GAIA121`: Package targets a legacy Gaia language series before v0.5.
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
strict `[@key]` references, CLI authoring groups, and the public
`gaia.engine.lang` authoring surface. See `docs/GAIA_RULE_COVERAGE.md`,
`gaia-lsp-tool rules`, and `gaia-lsp-tool manual` for the auditable rule
catalog, diagnostic explanations, language manual, version-aware package
metadata, and static-analysis limits. The fixed upstream fixture suite covers
the Galileo and Mendel v0.5 examples from that commit; the static compatibility
catalog also recognizes legacy Gaia import/module aliases such as `gaia.lang`,
`setting`, `contradiction`, `equivalence`, `complement`, and pre-v0.5 strategy
helpers while warning that new packages should use the v0.5 surface.
`scripts/check_upstream_examples.sh` rechecks the current upstream example tree
at the same commit before release.
