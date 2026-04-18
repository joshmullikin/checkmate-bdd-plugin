#!/usr/bin/env bash
# clone-deps.sh
# Clones (or updates) checkmate, playwright-http, and checkmate-mcp
# into ~/.checkmate-bdd/. Safe to re-run.

set -e

DEPS_DIR="${HOME}/.checkmate-bdd"
mkdir -p "$DEPS_DIR"

clone_or_pull() {
  local repo="$1"
  local name="$2"
  local dest="${DEPS_DIR}/${name}"

  if [ -d "${dest}/.git" ]; then
    echo "Updating ${name}..."
    git -C "$dest" pull --ff-only
  else
    echo "Cloning ${name}..."
    git clone "https://github.com/${repo}.git" "$dest"
  fi
}

clone_or_pull "ksankaran/checkmate"       "checkmate"
clone_or_pull "ksankaran/playwright-http" "playwright-http"
clone_or_pull "ksankaran/checkmate-mcp"   "checkmate-mcp"

echo ""
echo "All dependencies ready at ${DEPS_DIR}"
echo "PLUGIN_DEPS_DIR=${DEPS_DIR}"
