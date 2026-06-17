# Gaia LSP Production-Ready Plan

## Current State

- Repository: `newtontech/gaia-lsp`
- Local branch: `main`
- Latest pushed commit: `a146568 Expand Gaia LSP language coverage and VS Code providers`
- Remote CI status for `a146568`: passed
  - Python CI passed on Python 3.9 and 3.12.
  - VS Code extension CI passed and uploaded a VSIX artifact.
- Package-only publish workflows were triggered and passed with `publish=false`.
  - `publish-pypi.yml` built and checked distributions, but did not publish.
  - `publish-vscode.yml` built and uploaded VSIX, but did not publish.
- Local artifacts exist but are gitignored:
  - `dist/gaia_lsp-0.1.0-py3-none-any.whl`
  - `dist/gaia_lsp-0.1.0.tar.gz`
  - `gaia-vscode/gaia-vscode-0.1.0.vsix`
- Blocking external release state:
  - No local `VSCE_PAT` environment variable was present.
  - No PyPI/Twine token environment variable was present.
  - `~/.pypirc` was absent.
  - Real PyPI and VS Code Marketplace publishing still require credentials or Trusted Publisher configuration.

## Objective

Iterate `gaia-lsp` to production-ready quality for the Gaia DSL based on
`SiliconEinstein/Gaia`, preserving the full scope:

- Complete static diagnostics for Gaia DSL authoring mistakes.
- Complete CLI JSON envelope for agents.
- Complete standard LSP protocol server behavior.
- Complete VS Code extension behavior from packaged VSIX.
- Complete official-source provenance and reproducible fixture coverage.
- Complete release gates for GitHub, PyPI, and VS Code Marketplace.
- Publish only when credentials and explicit publish authorization are available.

## Required Serial Skill Pass

Use the following skills in this exact order, one by one. For every skill:

1. Read its `SKILL.md` completely before acting.
2. Follow any directly referenced local instruction files needed for this repo.
3. Make only changes aligned with Gaia LSP production readiness.
4. Run the smallest meaningful verification after each skill pass.
5. Record evidence in this plan or a follow-up implementation note before moving to the next skill.

Skill root discovered:

`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills`

### 1. agent-cli-json-envelope

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/agent-cli-json-envelope/SKILL.md`

Tasks:

- Audit every `gaia-lsp-tool` operation for a stable JSON envelope.
- Ensure all operations include enough machine-readable fields for agents.
- Confirm error and warning severities are explicit and blocking status is deterministic.
- Add or update tests for malformed input, missing paths, and nonzero exit behavior.

Evidence:

- `python3 -m pytest tests/test_tool_cli.py`
- CLI probes for `check`, `complete`, `context`, `hover`, `definition`, `references`, `rules`, `manual`, and `explain`.

### 2. editor-integration

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/editor-integration/SKILL.md`

Tasks:

- Audit VS Code providers: diagnostics, completion, hover, signature help, code action, document symbols, definition, and references.
- Verify packaged VSIX behavior against a real Gaia workspace.
- Add stronger extension tests where CLI payload parsing or provider conversion is weak.
- Keep `gaia-vscode/README.md` and `CHANGELOG.md` aligned with actual shipped behavior.

Evidence:

- `cd gaia-vscode && npm run lint && npm test && npm run package`
- `code --install-extension gaia-vscode/gaia-vscode-0.1.0.vsix --force`
- Screenshot or documented VS Code smoke against Galileo/Mendel examples.

### 3. lsp-every-dsl

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/lsp-every-dsl/SKILL.md`

Tasks:

- Check that Gaia LSP follows the generic production LSP contract used by the DSL fleet.
- Compare `lsp-capabilities.json` with repo behavior and tests.
- Confirm production-readiness gates are explicit, repeatable, and fail loudly.

Evidence:

- `make release-check`
- Manifest review against actual CLI, pygls server, VS Code, and fixtures.

### 4. lsp-quality-audit

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/lsp-quality-audit/SKILL.md`

Tasks:

- Perform a production quality review of diagnostics, protocol behavior, docs, test coverage, packaging, and CI.
- Identify false positives, false negatives, weak tests, and undocumented limitations.
- Fix any blocker before continuing.

Evidence:

- Written findings with file and line references.
- Full local gates after fixes.

### 5. schema-rule-engine

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/schema-rule-engine/SKILL.md`

Tasks:

- Audit Gaia rule definitions and diagnostic schema.
- Ensure diagnostic codes, severity, blocking policy, examples, fixes, and docs are consistent.
- Verify `diagnostics/diagnostic-engine-v1.schema.json` still matches emitted diagnostics.

Evidence:

- Schema validation tests or targeted tests for diagnostic JSON shape.
- `gaia-lsp-tool rules` probe.

### 6. wiki-knowledge-synthesis

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/wiki-knowledge-synthesis/SKILL.md`

Tasks:

- Audit `index.md`, `log.md`, `wiki/synthesis/openqc-agent-context.md`, and docs.
- Ensure wiki/context content reflects current Gaia rules, CLI operations, VS Code features, and release gates.
- Update stale knowledge after code changes.

Evidence:

- Docs diff.
- `gaia-lsp-tool manual` output still aligns with docs.

### 7. delivery-and-release-gates

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/delivery-and-release-gates/SKILL.md`

Tasks:

- Audit GitHub workflows, release workflows, and local release commands.
- Ensure PyPI and VS Code Marketplace paths are documented and runnable.
- Verify package-only workflows and identify exact remaining credential requirements.

Evidence:

- `gh run list --repo newtontech/gaia-lsp --limit 10`
- `make package-check`
- Package-only workflow run URLs.

### 8. fixtures-eval-harness

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/fixtures-eval-harness/SKILL.md`

Tasks:

- Expand and harden fixture evaluation.
- Keep fixed upstream fixtures for Galileo and Mendel.
- Check whether more upstream Gaia examples or generated invalid fixtures should be added.
- Ensure `scripts/check_upstream_examples.sh` is robust and documented.

Evidence:

- `python3 -m pytest tests/test_upstream_fixtures.py`
- `make upstream-examples`

### 9. lsp-project-bootstrap

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/lsp-project-bootstrap/SKILL.md`

Tasks:

- Audit project scaffold: package metadata, scripts, Makefile, docs, CI, extension package, and capabilities manifest.
- Ensure the repo is usable from a fresh clone.

Evidence:

- Fresh-clone command list.
- `make release-check` or equivalent segmented proof.

### 10. official-source-ingestion

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/official-source-ingestion/SKILL.md`

Tasks:

- Re-check `SiliconEinstein/Gaia` official README and language reference.
- Compare public `gaia.engine.lang` exports and examples against the local catalog.
- Update source provenance if upstream changes.

Evidence:

- `git ls-remote https://github.com/SiliconEinstein/Gaia.git HEAD refs/heads/main`
- Symbol coverage count and missing-symbol report.

### 11. source-provenance-ledger

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/source-provenance-ledger/SKILL.md`

Tasks:

- Audit `sourceProvenance` in `lsp-capabilities.json`.
- Ensure docs identify upstream commit, official docs, and fixture origin.
- Keep provenance evidence machine-readable.

Evidence:

- Manifest and docs diff.
- `gaia-lsp-tool rules` upstream block.

### 12. dsl-grammar-and-parser

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/dsl-grammar-and-parser/SKILL.md`

Tasks:

- Audit AST parsing and Gaia DSL recognition.
- Identify where static AST analysis is enough and where runtime compiler checks remain out of scope.
- Add tests for import aliases, package-local imports, labels, references, and multiline strings if gaps remain.

Evidence:

- Focused parser/analyzer tests.
- Updated static limits documentation.

### 13. lsp-candidate-validator

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/lsp-candidate-validator/SKILL.md`

Tasks:

- Validate Gaia LSP as a production candidate against the fleet contract.
- Ensure maturity, capabilities, CLI operations, server features, and editor providers are not overclaimed.

Evidence:

- Manifest-to-implementation test coverage.
- Any validator script output if provided by the skill.

### 14. lsp-protocol-server

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/lsp-protocol-server/SKILL.md`

Tasks:

- Audit pygls server registrations and behavior.
- Ensure standard LSP methods match `lsp-capabilities.json`.
- Add protocol-level tests if current tests only inspect registration.

Evidence:

- `python3 -m pytest tests/test_server.py`
- Manual or automated pygls request/response smoke if feasible.

### 15. runtime-output-diagnostics

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/runtime-output-diagnostics/SKILL.md`

Tasks:

- Check whether Gaia compiler/runtime outputs can be mapped into diagnostics without executing unsafe author code by default.
- If runtime output ingestion is added, keep it opt-in and clearly separate from static checks.
- Document runtime-only limits that remain delegated to `gaia build compile`.

Evidence:

- Tests for runtime-output parsing if implemented.
- Static limits documentation.

### 16. tdd-lsp-workflow

Path:
`/Users/yhm/Desktop/code/lsp-every-dsl/.agents/skills/tdd-lsp-workflow/SKILL.md`

Tasks:

- Final TDD pass over all changes from the previous 15 skills.
- Add failing tests first for any discovered gap.
- Run the complete release gate.
- Do not mark complete unless remote, package, editor, and release evidence proves the full objective.

Evidence:

- `ruff check src tests`
- `mypy src`
- `python3 -m pytest`
- `make package-check`
- `make vscode`
- `make upstream-examples`
- GitHub CI green on `origin/main`
- Package-only publish workflows green
- Real publish evidence only after credentials and explicit publish authorization exist.

## Final Production Completion Criteria

Do not mark the goal complete until all of the following are proven:

- `origin/main` contains the final production commit.
- GitHub CI passes on the final commit.
- PyPI release is published or explicitly documented as blocked by missing PyPI Trusted Publisher/token.
- VS Code Marketplace release is published or explicitly documented as blocked by missing `VSCE_PAT`/publisher credentials.
- Gaia upstream commit and official docs are current or intentionally pinned.
- `gaia-lsp-tool rules` reports complete symbol and diagnostic coverage for the pinned Gaia source.
- Fixed upstream fixtures and live upstream example scan pass.
- VSIX installs and works against a real Gaia workspace.
- All release gates pass locally and remotely.

## Stop Point

Per user instruction, stop after writing this plan. Do not continue implementation
or run further skill passes until the user resumes the task.
