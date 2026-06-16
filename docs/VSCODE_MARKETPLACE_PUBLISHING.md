# VS Code Marketplace Publishing

The VS Code extension lives in `gaia-vscode/` and publishes as:

- Extension id: `newtontech.gaia-vscode`
- Package name: `gaia-vscode`
- Publisher: `newtontech`
- Repository: `https://github.com/newtontech/gaia-lsp`

## Local Package Check

```bash
cd gaia-vscode
npm ci
npm run lint
npm test
npm run package
```

The package step creates `gaia-vscode-0.1.0.vsix`.

## Marketplace Publisher Setup

Create or verify the `newtontech` publisher in the Visual Studio Marketplace
publisher management page. The publisher id must match the `publisher` field in
`gaia-vscode/package.json`.

## GitHub Secret

For the PAT-based workflow, add a repository environment or repository secret:

- Name: `VSCE_PAT`
- Scope: Visual Studio Marketplace `Manage`
- Organization: all accessible organizations

The official VS Code publishing documentation now recommends Microsoft Entra
ID workload identity for long-term automated publishing. The PAT workflow here
is still supported for current GitHub Actions publishing, but should be migrated
before Azure DevOps global PAT retirement on 2026-12-01.

Configure and verify the PAT without writing it to disk:

```bash
scripts/configure_vsce.sh
```

To configure the secret and immediately dispatch the Marketplace publish
workflow:

```bash
RUN_PUBLISH=true scripts/configure_vsce.sh
```

The script runs `npx vsce verify-pat newtontech` with `VSCE_PAT` in the command
environment before writing the token to the repository's GitHub Actions
secrets.

You can also use npm scripts directly from `gaia-vscode/`:

```bash
npm run vsce:verify
npm run vsce:publish:pat
```

## GitHub Actions

Manual package-only validation:

```bash
gh workflow run publish-vscode.yml --repo newtontech/gaia-lsp
```

Manual Marketplace publish after `VSCE_PAT` is configured:

```bash
gh workflow run publish-vscode.yml --repo newtontech/gaia-lsp -f publish=true
```

Release publish:

```bash
gh release create gaia-vscode-v0.1.0 --repo newtontech/gaia-lsp \
  --title "gaia-vscode v0.1.0" \
  --notes "Initial VS Code extension for Gaia LSP diagnostics."
```
