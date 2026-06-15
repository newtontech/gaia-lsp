#!/usr/bin/env bash
set -euo pipefail

python3 -m pip index versions gaia-lsp || true
if [ -f "$HOME/.pypirc" ]; then
  echo "~/.pypirc present"
else
  echo "~/.pypirc absent"
fi
env | awk -F= '/^(TWINE_|PYPI_|UV_PUBLISH_|HATCH_INDEX_AUTH)/ {print $1"=<set>"}' | sort
