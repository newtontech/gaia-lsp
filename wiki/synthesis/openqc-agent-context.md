# Gaia Lang Agent Context

`gaia-lsp-tool` is the agent-facing JSON CLI for the Gaia DSL. Run
`gaia-lsp-tool check <path> --fail-on-blocking` before compiling a Gaia package;
it exits nonzero when blocking diagnostics are present. The analyzer inspects
Python AST without executing author code, so it is safe to run on untrusted
packages.

## Operations

`gaia-lsp-tool <operation> [args]`:

- `capabilities` — emits the `lsp-capabilities.json` manifest.
- `check <path>` — static diagnostics for a file or package directory.
- `context <path>` — completion items, symbols, and package metadata.
- `complete <path>` — Gaia symbol and import completion items.
- `hover <path> --line N --character N` — symbol documentation at a position.
- `definition <path> --line N --character N` — go-to-definition locations.
- `references <path> --line N --character N` — find-references locations.
- `symbols <path>` — document symbols (claims, notes, questions, …).
- `rules` — diagnostic rule catalog with severities, fixes, and examples.
- `manual [--format json|markdown]` — language manual.
- `explain <topic>` — explain a Gaia symbol or a `GAIA0xx` diagnostic code.

Every operation returns a stable JSON envelope with `software`, `operation`,
`ok`, and `toolVersion`. `check` adds `ok` (true only when no blocking
diagnostics remain), `blockingDiagnosticCount`, `diagnosticCount`, and
`diagnostics`. Positions in CLI arguments are 0-based; diagnostic `range`
fields are also 0-based for direct LSP transfer.

## Error contract

Failures are machine-readable, not tracebacks. On failure the envelope carries
`ok: false` and an `error` object with a stable `kind` and human-readable
`message`, and the process exits 1:

- `missing_file` — the target path does not exist.
- `not_a_file` — a file-only operation was given a directory.
- `encoding_error` — the file is not valid UTF-8.
- `permission_denied` / `io_error` — the file could not be read.
- `unknown_topic` — `explain` was given an unknown symbol or code.
- `invalid_input` / `internal_error` — argument or unexpected failures.

## Blocking policy

A diagnostic with `severity: "error"` is `blocking: true`; `warning`,
`information`, and `hint` are non-blocking. `check` is the blocking gate:
without `--fail-on-blocking` it exits 0 even when errors are reported, so agents
must inspect `ok` / `blockingDiagnosticCount`, or pass `--fail-on-blocking` to
make the exit code authoritative.
