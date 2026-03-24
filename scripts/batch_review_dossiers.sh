#!/usr/bin/env bash
# Batch review+fix dossiers using claude CLI in headless mode.
# Runs PARALLEL_JOBS at a time, logs per-slug output, tracks progress.

set -uo pipefail

PARALLEL_JOBS=${1:-5}
REMAINING_FILE="${2:-/tmp/remaining-slugs.txt}"
LOG_DIR="/tmp/dossier-review-logs"
PROGRESS_FILE="/tmp/dossier-review-progress.txt"

mkdir -p "$LOG_DIR"
> "$PROGRESS_FILE"

if [[ ! -f "$REMAINING_FILE" ]]; then
  echo "ERROR: $REMAINING_FILE not found. Generate it first."
  exit 1
fi

TOTAL=$(wc -l < "$REMAINING_FILE" | tr -d ' ')
echo "Processing $TOTAL dossiers with $PARALLEL_JOBS parallel jobs"
echo "Logs: $LOG_DIR"
echo "---"

PROMPT_TEMPLATE='Review and fix the curated dossier "SLUG_PLACEHOLDER" for editorial quality in a single pass. Only modify the `curation` object (lead, sections, system_role, open_questions). Do NOT touch findings, connections, or other data.

Steps:
1. Read `content/dossiers/SLUG_PLACEHOLDER.json`
2. Run: `uv run python scripts/review_dossier_checks.py check SLUG_PLACEHOLDER --no-record`
3. Review against this 8-point checklist and fix ALL issues:
   - Claim-evidence alignment (inference/synthesis must use attribution language like "analysis suggests" not stated as fact)
   - Tone (encyclopedic, neutral, no editorializing or loaded language)
   - Lead quality (standalone, covers who/what/significance/current status)
   - Section-lead overlap (sections add detail, not restate lead)
   - Narrative coherence (logical flow, clear writing, natural transitions)
   - AI tells (remove colon crutch patterns, "This reveals...", stacked declaratives, filler transitions like "Notably," "Importantly," "Significantly")
   - Open questions quality (specific, actionable, evidence-gap-based)
   - system_role quality (neutral analytical language, no loaded terms like "operative" or "dark money")
4. Write fixed JSON with json.dumps(data, indent=2) + trailing newline
5. Re-run check and report before/after verdict

Do NOT create any new files. Only modify the existing dossier JSON.'

process_slug() {
  local slug="$1"
  local log_file="$LOG_DIR/$slug.log"

  local prompt="${PROMPT_TEMPLATE//SLUG_PLACEHOLDER/$slug}"

  echo "[$(date +%H:%M:%S)] START $slug"

  if echo "$prompt" | env -u CLAUDECODE claude -p --allowedTools "Read,Edit,Write,Bash,Glob,Grep" > "$log_file" 2>&1; then
    # Check if the dossier was actually modified
    if git diff --name-only -- "content/dossiers/${slug}.json" | grep -q .; then
      echo "[$(date +%H:%M:%S)] DONE  $slug (modified)"
      echo "MODIFIED $slug" >> "$PROGRESS_FILE"
    else
      echo "[$(date +%H:%M:%S)] DONE  $slug (no changes)"
      echo "UNCHANGED $slug" >> "$PROGRESS_FILE"
    fi
  else
    echo "[$(date +%H:%M:%S)] FAIL  $slug (see $log_file)"
    echo "FAILED $slug" >> "$PROGRESS_FILE"
  fi
}

export -f process_slug
export PROMPT_TEMPLATE LOG_DIR PROGRESS_FILE

# Use xargs for parallel execution
cat "$REMAINING_FILE" | xargs -P "$PARALLEL_JOBS" -I {} bash -c 'process_slug "$@"' _ {}

echo ""
echo "=== SUMMARY ==="
echo "Modified:  $(grep -c '^MODIFIED' "$PROGRESS_FILE" 2>/dev/null || echo 0)"
echo "Unchanged: $(grep -c '^UNCHANGED' "$PROGRESS_FILE" 2>/dev/null || echo 0)"
echo "Failed:    $(grep -c '^FAILED' "$PROGRESS_FILE" 2>/dev/null || echo 0)"
echo "Total:     $TOTAL"
echo ""
echo "Check git diff --stat -- content/dossiers/ for full picture"
