# gaia-lsp Agent Notes

This repository follows the scientific LSP family pattern used under
`/Users/yhm/Desktop/code`.

- Keep diagnostics static unless a task explicitly asks for a runtime Gaia
  compiler integration.
- Do not import or execute target Gaia packages during editor diagnostics.
- Use `python3`, `ruff`, `pytest`, and `python3 -m build` for local gates.
- Keep PRs tied to issues and include test evidence in the PR body.
