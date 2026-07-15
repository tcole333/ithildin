#!/usr/bin/env bash
# Sync the repo Codex skill mirror (.codex/skills) into $CODEX_HOME/skills
# (default ~/.codex/skills), which is the tree the Codex CLI actually loads.
#
# Only skill directories that exist in the repo tree are touched; skills that
# live solely in $CODEX_HOME/skills (Codex-native ones such as playwright or
# cloudflare-deploy) are left alone. --delete inside each managed directory
# removes files that were dropped from the repo copy.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/.codex/skills"
DEST_DIR="${CODEX_HOME:-$HOME/.codex}/skills"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "ERROR: repo Codex skills not found at $SRC_DIR" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

count=0
for src in "$SRC_DIR"/*/; do
  name="$(basename "$src")"
  rsync -a --delete "$src" "$DEST_DIR/$name/"
  count=$((count + 1))
done

echo "Synced $count skill(s): $SRC_DIR -> $DEST_DIR"
