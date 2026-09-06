#!/usr/bin/env bash
# Explicit unattended compatibility entry point. Interactive work uses chat-native agents.
set -uo pipefail

usage() {
  echo "Usage: $0 --unattended|--dry-run [parallel-jobs=5] SLUG_FILE"
  echo "Requires pinned ITHILDIN_PROFILE and absolute ITHILDIN_DB_PATH."
  echo "Workers review/fix disjoint dossiers; the coordinator persists actual reviews and receipts serially."
}
mode="${1:-}"
if [[ "$mode" == "--help" || "$mode" == "-h" ]]; then usage; exit 0; fi
if [[ "$mode" != "--unattended" && "$mode" != "--dry-run" ]]; then usage >&2; exit 2; fi
PARALLEL_JOBS="${2:-5}"
SLUG_FILE="${3:-}"
if [[ ! "$PARALLEL_JOBS" =~ ^[1-9][0-9]*$ || ! -f "$SLUG_FILE" ]]; then usage >&2; exit 2; fi
if [[ -z "${ITHILDIN_PROFILE:-}" || "${ITHILDIN_DB_PATH:-}" != /* ]]; then
  echo "Pin ITHILDIN_PROFILE and an absolute ITHILDIN_DB_PATH before starting." >&2
  exit 2
fi
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOSSIER_DIR="${ITHILDIN_CONTENT_DIR:-$ROOT_DIR/content}/dossiers"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/osint-dossier-review-XXXXXXXX")"
echo "Run artifacts: $WORKDIR"
slugs=()
while IFS= read -r slug || [[ -n "$slug" ]]; do
  [[ -z "$slug" ]] && continue
  if [[ ! "$slug" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ || ! -f "$DOSSIER_DIR/$slug.json" ]]; then
    echo "Invalid or missing dossier slug: $slug" >&2
    exit 2
  fi
  duplicate=false
  for prior in "${slugs[@]:-}"; do [[ "$prior" == "$slug" ]] && duplicate=true; done
  if [[ "$duplicate" == false ]]; then slugs+=("$slug"); fi
done < "$SLUG_FILE"
if [[ "${#slugs[@]}" -eq 0 ]]; then echo "No dossiers selected."; exit 0; fi

process_slug() {
  local slug="$1"
  local review_dir="$WORKDIR/$slug"
  local log_file="$review_dir/worker.log"
  mkdir -p "$review_dir"
  local prompt
  prompt="$(cat <<EOF
Use /review-dossiers --target "$slug" --fix for this explicitly requested unattended compatibility run.
The selected dossier is "$DOSSIER_DIR/$slug.json"; use "$review_dir" as WORKDIR.
Inherit the pinned ITHILDIN_PROFILE and ITHILDIN_DB_PATH and current model settings.
Read .claude/skills/review-dossiers/SKILL.md and the source evidence. Apply authorized curation corrections, then perform actual semantic review of final content. Preserve findings, connections, unrelated files and evidence records.
Write the actual completed review to "$review_dir/review-$slug.json" with the required final content_sha256, reviewer, real timestamp, explicit verdict and llm_issues. Keep structural check packets and report in WORKDIR.
Do not ingest reviews or write shared receipts: the coordinator will persist your supplied judgment serially after you finish. Do not create a PASS without performing the evidence review. Do not launch more unattended jobs.
EOF
)"
  printf '%s\n' "$prompt" > "$review_dir/prompt.txt"
  if [[ "$RUN_MODE" == "--dry-run" ]]; then
    echo "Prepared $slug → $review_dir/prompt.txt"
    return 0
  fi
  if printf '%s\n' "$prompt" | env -u CLAUDECODE claude -p --allowedTools "Read,Edit,Write,Bash,Glob,Grep" > "$log_file" 2>&1 \
      && [[ -f "$review_dir/review-$slug.json" ]]; then
    printf 'completed\n' > "$review_dir/worker-status.txt"
  else
    printf 'failed\n' > "$review_dir/worker-status.txt"
    echo "Review incomplete: $slug (see $log_file)" >&2
  fi
}
RUN_MODE="$mode"
export -f process_slug
export WORKDIR DOSSIER_DIR RUN_MODE
cd "$ROOT_DIR" || exit 2
printf '%s\n' "${slugs[@]}" | xargs -P "$PARALLEL_JOBS" -I '{}' bash -c 'process_slug "$1"' _ '{}'
worker_exit=$?
if [[ "$mode" == "--dry-run" ]]; then exit "$worker_exit"; fi
failures=0
for slug in "${slugs[@]}"; do
  review_dir="$WORKDIR/$slug"
  if [[ "$(cat "$review_dir/worker-status.txt" 2>/dev/null)" != "completed" ]]; then
    failures=$((failures + 1))
    continue
  fi
  if ! uv run python scripts/review_dossier_checks.py ingest-llm --dir "$review_dir" \
      > "$review_dir/persist.log" 2>&1; then
    failures=$((failures + 1))
    continue
  fi
  if ! uv run python scripts/review_dossier_checks.py receipt --review-file "$review_dir/review-$slug.json" \
      >> "$review_dir/persist.log" 2>&1; then
    failures=$((failures + 1))
    continue
  fi
  if ! uv run python scripts/review_dossier_checks.py validate-receipts --slug "$slug" \
      --output "$review_dir/receipt-validation.json" >> "$review_dir/persist.log" 2>&1; then
    failures=$((failures + 1))
  fi
done
echo "Selected ${#slugs[@]} dossiers; $failures need attention. Artifacts: $WORKDIR"
echo "Current receipts for this selection do not establish the platform-wide publication gate."
[[ "$failures" -eq 0 && "$worker_exit" -eq 0 ]]
