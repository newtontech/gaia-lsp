#!/usr/bin/env bash
set -euo pipefail

repo_url="${GAIA_UPSTREAM_REPO:-https://github.com/SiliconEinstein/Gaia.git}"
expected_commit="${GAIA_UPSTREAM_COMMIT:-6354a3425fdadcf6f7e5f557dd3bc30f36d3297e}"
workdir="${GAIA_UPSTREAM_WORKDIR:-$(mktemp -d)}"

cleanup() {
  if [[ -z "${GAIA_UPSTREAM_WORKDIR:-}" && -d "$workdir" ]]; then
    rm -rf "$workdir"
  fi
}
trap cleanup EXIT

clone_dir="$workdir/Gaia"
if [[ ! -d "$clone_dir/.git" ]]; then
  git clone --filter=blob:none --sparse "$repo_url" "$clone_dir"
fi

git -C "$clone_dir" sparse-checkout set examples
git -C "$clone_dir" fetch --depth=1 origin "$expected_commit"
git -C "$clone_dir" checkout --detach "$expected_commit"

mapfile -t examples < <(find "$clone_dir/examples" -mindepth 1 -maxdepth 1 -type d | sort)
if [[ "${#examples[@]}" -eq 0 ]]; then
  echo "No Gaia upstream examples found under $clone_dir/examples" >&2
  exit 1
fi

for example in "${examples[@]}"; do
  echo "checking $(basename "$example")"
  python3 -m gaia_lsp.tool check "$example" --fail-on-blocking
done
