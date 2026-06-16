#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_DIR="${ROOT_DIR}/gaia-vscode"
REPO="${REPO:-newtontech/gaia-lsp}"
PUBLISHER="${PUBLISHER:-newtontech}"
SECRET_NAME="${SECRET_NAME:-VSCE_PAT}"
RUN_PUBLISH="${RUN_PUBLISH:-false}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required to configure ${SECRET_NAME}." >&2
  exit 1
fi

if [ ! -d "${EXT_DIR}/node_modules" ]; then
  (cd "${EXT_DIR}" && npm ci)
fi

if [ -z "${VSCE_PAT:-}" ] && [ ! -t 0 ]; then
  echo "${SECRET_NAME} is not set and stdin is not interactive." >&2
  echo "Export ${SECRET_NAME} or run this script from an interactive terminal." >&2
  exit 1
fi

if [ -z "${VSCE_PAT:-}" ]; then
  printf "Paste Visual Studio Marketplace PAT for publisher '%s' (input hidden): " "${PUBLISHER}" >&2
  restore_tty() { stty echo 2>/dev/null || true; }
  trap restore_tty EXIT
  stty -echo
  IFS= read -r VSCE_PAT
  stty echo
  trap - EXIT
  printf "\n" >&2
fi

if [ -z "${VSCE_PAT}" ]; then
  echo "${SECRET_NAME} cannot be empty." >&2
  exit 1
fi

(cd "${EXT_DIR}" && VSCE_PAT="${VSCE_PAT}" npx vsce verify-pat "${PUBLISHER}")

printf "%s" "${VSCE_PAT}" | gh secret set "${SECRET_NAME}" --repo "${REPO}" --app actions
echo "Configured ${SECRET_NAME} for ${REPO}."

if [ "${RUN_PUBLISH}" = "true" ]; then
  gh workflow run publish-vscode.yml --repo "${REPO}" -f publish=true
  echo "Triggered publish-vscode.yml with publish=true."
else
  echo "Publish workflow not triggered. Run with RUN_PUBLISH=true to publish after configuring the secret."
fi
