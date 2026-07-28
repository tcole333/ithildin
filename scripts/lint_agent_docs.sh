#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# $CODEX_HOME/skills is a synced copy of the repo's .codex/skills — if this
# lint flags stale HOME skills, refresh them with scripts/sync_codex_skills.sh.
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"

ARGS=(
  --workspace "$ROOT_DIR"
  --skills-dir "$ROOT_DIR/.claude/skills"
  --skills-dir "$ROOT_DIR/.codex/skills"
  --skills-dir "$CODEX_HOME_DIR/skills"
)

for dir in \
  "$ROOT_DIR/.claude/commands" \
  "$HOME/.claude/commands" \
  "$ROOT_DIR/docs" \
  "$ROOT_DIR/research"
do
  if [[ -d "$dir" ]]; then
    case "$dir" in
      */commands) ARGS+=(--commands-dir "$dir") ;;
      *) ARGS+=(--docs-dir "$dir") ;;
    esac
  fi
done

uv run --no-sync python "$ROOT_DIR/scripts/validate_skills.py" "${ARGS[@]}" "$@"
