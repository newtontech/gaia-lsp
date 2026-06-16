# Gaia LSP for VS Code

`gaia-vscode` surfaces `gaia-lsp` static diagnostics inside VS Code for Gaia
Lang Python DSL packages.

The extension does not import or execute the target Gaia package. It shells out
to `gaia-lsp-tool check` and converts the JSON diagnostic envelope into VS Code
diagnostics.

## Requirements

Install the Python package in the environment visible to VS Code:

```bash
pip install "gaia-lsp[lsp]"
```

If the executable is not on `PATH`, set `gaiaLsp.toolPath` to the absolute path
or use `gaiaLsp.toolArgs` for a wrapper. For example:

```json
{
  "gaiaLsp.toolPath": "uv",
  "gaiaLsp.toolArgs": ["run", "gaia-lsp-tool"]
}
```

## Commands

- `Gaia LSP: Check Current File`
- `Gaia LSP: Check Workspace`
- `Gaia LSP: Show Rule Catalog`

## Settings

- `gaiaLsp.toolPath`: executable path, defaults to `gaia-lsp-tool`.
- `gaiaLsp.toolArgs`: extra arguments before the operation.
- `gaiaLsp.checkOnSave`: run diagnostics on save.
- `gaiaLsp.checkOnOpen`: run diagnostics when a candidate file opens.
- `gaiaLsp.failOnBlocking`: show an error notification for blocking diagnostics.
- `gaiaLsp.maxBufferMb`: command output buffer size.
- `gaiaLsp.trace`: write command details to the output channel.

## Packaging

```bash
npm ci
npm run package
```

The generated `.vsix` can be installed with:

```bash
code --install-extension gaia-vscode-0.1.0.vsix
```
