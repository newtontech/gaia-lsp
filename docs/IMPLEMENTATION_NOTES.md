# Gaia LSP Production Hardening — Implementation Notes

Running log of the serial skill pass defined in `PLAN.md`. Each entry records
what changed and the evidence collected.

## Skill 1 — agent-cli-json-envelope

- `src/gaia_lsp/tool.py`: introduced a shared envelope (`software`,
  `operation`, `ok`, `toolVersion`) across every operation, plus a
  `ToolError`/`_error_envelope` machine-readable failure path.
- Operations now emit stable JSON for missing files (`missing_file`),
  directories passed to file-only ops (`not_a_file`), non-UTF-8 input
  (`encoding_error`), permission errors (`permission_denied`), generic IO
  errors (`io_error`), unknown explain topics (`unknown_topic`), and unexpected
  failures (`internal_error`) — all with nonzero exit codes.
- Preserved existing contracts: `complete` still returns `items`,
  `capabilities` still returns the raw `OpenQCLspCapabilities` manifest, and
  `rules` keeps its top-level keys (now enriched with `operation`/`ok`/
  `toolVersion`).
- Tests: added 7 cases in `tests/test_tool_cli.py` (error envelopes, encoding,
  unknown topic, success envelopes carry `ok`/`toolVersion`).
- Evidence: `ruff` clean, `mypy` clean, 53 tests pass, 91% coverage; all 11
  operations probed and return stable envelopes.

## Skill 2 — editor-integration

- `gaia-vscode/src/extension.ts`: `runGaiaTool` now produces an actionable
  message when `gaia-lsp-tool` is missing (`ENOENT`) instead of a raw spawn
  error.
- `gaia-vscode/src/diagnostics.ts`: `parseGaiaCheckOutput` surfaces the real
  message from a machine-readable error envelope instead of a generic
  "missing diagnostics" error.
- Tests: added 7 cases covering `summarizeCheck` states, full `severityName`
  matrix, range clamping, `resolveDiagnosticFile` absolute/relative resolution,
  payload rejection paths, and error-envelope surfacing.
- `README.md` / `CHANGELOG.md` aligned with the new error behavior.
- Evidence: `npm run lint` clean, `npm test` 14 pass, `npm run package` builds
  `gaia-vscode-0.1.0.vsix`; documented CLI smoke against Galileo + Mendel
  fixtures (both `check` clean, `context` returns 106 completion items);
  VSIX installs and is listed as `newtontech.gaia-vscode`.

## Skill 3 — lsp-every-dsl fleet contract

- Manifest review: the 11 advertised `agentCli` operations all map to working
  CLI subcommands and tests; the 8 advertised editor providers all map to
  registered VS Code providers; `maturity` is honestly `alpha`.
- Evidence: `make release-check` green (lint, typecheck, test, package-check,
  vscode, upstream-examples). The upstream scan clones
  `SiliconEinstein/Gaia` at pinned commit `6354a34` and checks Galileo +
  Mendel clean.
- Deferred gaps (tracked below).

## Skill 4 — lsp-quality-audit

- Dispatched a focused correctness audit of `analyzer.py`/`diagnostics.py`.
  Found and fixed four false-positive/negative defects via TDD (failing test
  first, then fix):
  1. **BLOCKER** `_is_nonnegative_integer_literal` accepted negative integers
     (e.g. `Binomial(n=-3)`) — now rejects via `_literal_number`
     (`analyzer.py:1817`). Was a silent false negative (GAIA084).
  2. **BLOCKER** `_check_artifact_call` flagged `figure(path=<variable>)` as
     GAIA073 — now keys the "source or path required" check on keyword
     *presence* (`_keyword_present`) so non-literal sources/paths are not
     false positives (`analyzer.py:1156`).
  3. **BLOCKER** `_check_scaffold_call` flagged
     `candidate_relation(claims=<variable>)` as GAIA102 — now only fires when
     the literal length is known and too small, while still flagging a missing
     `claims=` argument (`analyzer.py:1262`).
  4. **MEDIUM** `_check_observe` flagged `observe(given=<variable>)` as
     GAIA091 — now only fires when `given=` is a provably non-empty literal
     collection (`analyzer.py:1088`), matching the `decompose`/`depends_on`
     policy.
- MEDIUM (figure with neither `source=` nor `path=`) left as a policy
  decision pending upstream confirmation of the `figure` signature.
- Evidence: `ruff` clean, `mypy` clean, 57 tests pass, 91% coverage.

## Skill 7 — delivery-and-release-gates

- Audited `publish-pypi.yml` (OIDC trusted publishing, `pypi` environment,
  package-only by default) and `publish-vscode.yml` (explicit `VSCE_PAT` guard,
  `vscode-marketplace` environment, package-only by default). Both are gated
  and runnable.
- `make package-check` green: `python -m build`, `twine check dist/*` PASSED,
  `npm audit` 0 vulnerabilities.
- `gh run list --repo newtontech/gaia-lsp` shows both package-only publish
  workflows succeeded on 2026-06-17 and CI is green on `main`.
- Publishing docs (`docs/PYPI_PUBLISHING.md`, `docs/VSCODE_MARKETPLACE_PUBLISHING.md`)
  document exact remaining credential requirements: PyPI Trusted Publisher
  config (or a scoped `TWINE` token) and the `VSCE_PAT` secret + `newtontech`
  publisher.

## Skill 8 — fixtures-eval-harness

- Added `tests/fixtures/valid/` and `tests/fixtures/invalid/` with small
  representative Gaia files.
- Added `tests/golden/` (fleet standard layout) with three deterministic
  golden envelopes: clean `check`, a `GAIA010` diagnostic envelope, and a
  `missing_file` error envelope. Paths/URIs are normalized to placeholders so
  the goldens are CI-portable.
- Added `tests/test_golden_envelopes.py` as a drift guard; verified
  deterministic across two `PYTHONHASHSEED` values.
- Closes the deferred "no `tests/golden/`" gap and satisfies the
  agent-cli-json-envelope "golden JSON fixtures prove stable output shape"
  acceptance.
- Evidence: upstream fixtures test + `scripts/check_upstream_examples.sh`
  (sparse clone at pinned commit) remain robust; 66 tests pass, 91% coverage.

## Skill 9 — lsp-project-bootstrap

- Aligned `pyproject.toml` dev-status to `Development Status :: 3 - Alpha` to
  match the manifest `maturity: alpha` (closes the dev-status drift gap).
- Added `test_pyproject_dev_status_matches_manifest_maturity` to prevent
  future drift.
- Fresh-clone acceptance verified: documented install/dev/verify/capabilities
  commands; `python -m build` + `twine check` PASSED; versions consistent
  across `pyproject.toml`, `package.json`, `__version__`, and the manifest.

## Skill 10 — official-source-ingestion

- `git ls-remote https://github.com/SiliconEinstein/Gaia.git` confirms
  `refs/heads/main` HEAD == pinned commit `6354a34` — provenance is current,
  no re-ingestion needed.
- Compared upstream `gaia.engine.lang.__all__` (97 exports) against the local
  symbol catalog: added the two missing introspection predicates
  (`is_formula`, `is_term`). Coverage is now 97/97 of `lang.__all__` plus the
  bayes surface (`compare`, `model`) = 99 catalog symbols, 0 missing.

## Skill 11 — source-provenance-ledger

- Provenance model is commit-pinned: the immutable SHA is verified by
  `scripts/check_upstream_examples.sh` fetching exactly that commit.
- Verified every `rules` upstream `referenceDocs` path resolves at the pinned
  commit (files via raw, directories `lang/dsl`, `engine/bayes`, `lang/refs`
  via the contents API).
- Manifest `sourceProvenance` carries stable IDs (`gaia-upstream`,
  `gaia-language-reference`, `gaia-mendel-example`) and agrees with the
  `gaia-lsp-tool rules` upstream block.
- Added `test_source_provenance_ledger_is_consistent` regression guard.

## Skill 12 — dsl-grammar-and-parser

- Parser robust on import aliases, module aliases, starred imports, multiline
  strings, and empty/partial files (verified by focused tests, no false
  positives).
- Static-vs-runtime boundary already documented in `docs/GAIA_RULE_COVERAGE.md`
  (Static Limits section).
- Added `test_parser_recognizes_import_aliases_module_access_and_multiline_content`
  and `test_parser_is_stable_on_empty_and_partial_modules` to lock the parser
  behavior.
- Evidence: 70 tests pass; aliases/module-access/starred/multiline/empty all
  guarded by explicit test cases.

## Skill 13 — lsp-candidate-validator

- Added `test_manifest_advertises_only_backed_operations_and_maturity` as a
  no-overclaim guard: every advertised `agentCli` operation is a real registered
  CLI subcommand; maturity `alpha` is honestly not `production`.
- All manifest-to-implementation mappings verified: 11 CLI operations registered,
  8 VS Code providers registered, 8 textDocument LSP features registered.
- Evidence: 71 tests pass; no operation or capability is overclaimed.

## Skill 14 — lsp-protocol-server

- Expanded `tests/test_server.py` from 1 registration-only test to 42 tests
  covering:
  - Pure helper functions: `_to_lsp_diagnostic`, `_path_from_uri`,
    `_function_name_before_call`, `_signature_parameters`,
    `_active_parameter_index`, `_suggested_import_from_message`,
    `_import_insertion_line`.
  - Handler integration tests: `didOpen` publishes diagnostics and caches text;
    `didChange` updates diagnostics; empty `content_changes` skipped gracefully.
  - Feature-level tests: `completion` returns Gaia DSL helpers with
    detail/documentation; `hover` returns Markdown for known symbols and `None`
    for unknown; `definition`/`references` return empty for nonexistent files;
    `signatureHelp` works for `claim`; `codeAction` creates GAIA015 quick-fixes
    and skips non-GAIA015 diagnostics; `documentSymbol` returns symbols from
    cache.
  - Error recovery: syntax error (unclosed string) produces GAIA001 without
    crashing; empty document produces zero diagnostics gracefully.
- Evidence: `ruff` clean, `mypy` clean, 112 tests pass, 91% coverage.
  Protocol-level behavior now has comprehensive regression coverage.

## Skill 15 — runtime-output-diagnostics

- static-only boundary is clearly documented in three locations:
  - `docs/GAIA_RULE_COVERAGE.md` (lines 4–6): "The checker is static by design"
    with a full Static Limits section listing what is delegated to
    `gaia build compile`.
  - `AGENTS.md` (lines 6–7): "Keep diagnostics static unless a task explicitly
    asks for a runtime Gaia compiler integration."
  - `src/gaia_lsp/analyzer.py` docstring (lines 1–6): "intentionally uses
    Python's AST instead of importing target modules."
- No runtime-output ingestion added (static-only by design). The runtime
  boundary is clean and explicit.

## Skill 16 — tdd-lsp-workflow (final pass)

Complete release gate results:

| Gate | Status |
|---|---|
| `ruff check src tests` | ✅ Clean |
| `mypy src` | ✅ No issues |
| `python3 -m pytest` | ✅ 112 passed, 91% coverage |
| `make package-check` | ✅ Build + twine check PASSED |
| `make vscode` | ✅ `npm run lint` + 14 tests + package |
| `scripts/check_upstream_examples.sh` | ✅ Galileo + Mendel clean |

All 16 skills from the production-hardening plan are complete. The remaining
deferred item (`figure()` with neither `source=` nor `path=`) needs upstream
`figure` signature confirmation before adjusting the diagnostic policy.
