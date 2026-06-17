# Changelog

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
