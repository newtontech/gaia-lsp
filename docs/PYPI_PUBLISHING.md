# PyPI Publishing

The package name `gaia-lsp` is not present on PyPI as of 2026-06-16. This repo
is ready for PyPI Trusted Publishing, but PyPI must be configured by an account
that owns or can create the project.

## Trusted Publisher Configuration

Create a pending publisher on PyPI with these exact values:

- PyPI project name: `gaia-lsp`
- Owner: `newtontech`
- Repository name: `gaia-lsp`
- Workflow name: `publish-pypi.yml`
- Environment name: `pypi`

After that configuration exists, publishing is:

```bash
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 dist/* --repo newtontech/gaia-lsp \
  --title "gaia-lsp v0.1.0" \
  --notes "Initial static Gaia Lang DSL diagnostics, CLI, and LSP server."
```

Publishing the GitHub release triggers `.github/workflows/publish-pypi.yml`.
The workflow builds the sdist and wheel, validates metadata with Twine, uploads
the GitHub artifact, and publishes to PyPI using OIDC.

## Manual Token Fallback

If Trusted Publishing is not available, set a scoped PyPI API token locally and
upload the already validated artifacts:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-...
.venv/bin/twine upload dist/*
```

Do not commit PyPI tokens or write them into repo files.
