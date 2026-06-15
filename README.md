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
- `GAIA020`: Deprecated `context` or `setting`; use `note`.
- `GAIA021`: Legacy `contradiction`; use `contradict`.
- `GAIA030`: Invalid `register_prior` probability.
- `GAIA031`: Missing `register_prior(..., justification=...)`.
- `GAIA032`: `register_prior` targets a string instead of a Claim object.
- `GAIA033`: Legacy `PRIORS = {...}` dictionary.
- `GAIA040`: `__all__` exports a name without a local Gaia Knowledge binding.
- `GAIA041`: Duplicate `__all__` export.
- `GAIA042`: Dynamic or non-string `__all__` entry.
- `GAIA050`: Strict `[@ref]` reference is unresolved in local labels or `references.json`.

## Source Alignment

The diagnostic rules target the Gaia v0.5 Python DSL surface documented in
`SiliconEinstein/Gaia`, including `claim`, `note`, `question`, `derive`,
`observe`, `compute`, `infer`, relation helpers, scaffold helpers, distribution
factories, `register_prior`, literal `__all__`, and strict `[@key]` references.
