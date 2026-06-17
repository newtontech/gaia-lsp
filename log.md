# gaia-lsp Log

- 2026-06-15: Initial static Gaia DSL diagnostics, CLI, LSP server, tests, and CI.
- 2026-06-16: Added `gaia-vscode` VS Code extension project and Marketplace CI/CD workflow.
- 2026-06-16: Added upstream Gaia DSL fixtures, CLI error/warning evidence, and VS Code completion/hover/symbol providers.
- 2026-06-17: Production hardening pass. CLI returns stable JSON envelopes with
  `ok`/`toolVersion` and machine-readable error envelopes (missing file,
  encoding, unknown topic) instead of tracebacks. Fixed four analyzer
  false-positive/negative defects (negative integer counts, non-literal
  artifact path, non-literal `candidate_relation` claims, non-literal `observe`
  given). Removed the unimplemented `GAIA060` catalog rule. VS Code extension
  surfaces actionable errors when `gaia-lsp-tool` is missing. See
  `docs/IMPLEMENTATION_NOTES.md`.
