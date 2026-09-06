#!/usr/bin/env bash
# Compatibility entrypoint. Project skills are discovered through .agents/skills;
# copying them into HOME creates stale duplicates. Default: read-only repo check.
# Optional inventory/backup requires explicit --personal-root; nothing is deleted.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec uv run --project "$ROOT_DIR" --locked python "$ROOT_DIR/scripts/skill_distribution.py" --workspace "$ROOT_DIR" "$@"
