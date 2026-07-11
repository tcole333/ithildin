#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

uv run python "$ROOT_DIR/scripts/validate_skills.py" "${ARGS[@]}" "$@"
