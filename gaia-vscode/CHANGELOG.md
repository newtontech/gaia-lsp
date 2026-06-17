# Changelog

## 0.5.0-alpha.3

- Aligns the VS Code extension version with upstream Gaia `v0.5.0a3`.
- Packages the current Gaia LSP diagnostic, completion, hover, navigation,
  semantic-token, folding, link, rename, and authoring-context surfaces.

## 0.1.0

- Initial VS Code extension for Gaia Lang static diagnostics.
- Adds current-file and workspace checks backed by `gaia-lsp-tool`.
- Adds a rule-catalog command for the Gaia diagnostic surface.
- Adds completion, hover, document symbols, authoring context, and language
  manual commands backed by the Gaia rule catalog.
- Adds canonical Gaia import snippets and package-local relative import
  suggestions in completion results.
- Adds signature help for Gaia DSL calls through `gaia-lsp-tool explain`.
- Adds Quick Fix code actions for `GAIA015` missing Gaia imports.
- Adds Go to Definition and Find References backed by package-scoped
  `gaia-lsp-tool definition` / `gaia-lsp-tool references`.
- Surfaces actionable errors when `gaia-lsp-tool` is missing and renders
  machine-readable `gaia-lsp-tool` error envelopes as VS Code diagnostics
  messages instead of raw parser failures.
