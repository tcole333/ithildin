#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARGS=(--workspace "$ROOT_DIR" --skills-dir "$ROOT_DIR/.claude/skills" --skills-dir "$ROOT_DIR/.agents/skills")
for dir in "$ROOT_DIR/.claude/commands" "$ROOT_DIR/docs" "$ROOT_DIR/research"; do
  if [[ -d "$dir" ]]; then
    case "$dir" in
      */commands) ARGS+=(--commands-dir "$dir") ;;
      *) ARGS+=(--docs-dir "$dir") ;;
    esac
  fi
done
# Personal skills are outside repository ownership; opt in with --skills-dir.
exec uv run --project "$ROOT_DIR" --locked python "$ROOT_DIR/scripts/validate_skills.py" "${ARGS[@]}" "$@"
