#!/bin/bash
# warn-no-negative-results.sh — PostToolUse hook for Bash
# After lead completion, warn if no negative_result findings were recorded.
# Non-blocking (exit 0) — just a reminder to document what WASN'T found.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only check lead_tracker complete commands
if ! echo "$COMMAND" | grep -qE "lead_tracker[^ ]*\s+complete\s+"; then
  exit 0
fi

# Extract lead ID
LEAD_ID=$(echo "$COMMAND" | grep -oE "complete [0-9]+" | grep -oE "[0-9]+")
if [ -z "$LEAD_ID" ]; then
  exit 0
fi

# Check for negative_result findings on this lead
NEG_COUNT=$(sqlite3 "$(dirname "$0")/../../investigation.db" \
  "SELECT COUNT(*) FROM findings WHERE lead_id=$LEAD_ID AND finding_type='negative_result'" 2>/dev/null)

if [ "$NEG_COUNT" = "0" ] || [ -z "$NEG_COUNT" ]; then
  echo "WARNING: Lead #$LEAD_ID completed with no negative results recorded. If any sources returned zero results, record them with \`findings_tracker.py add --type negative_result\` to document what was NOT found. Negative results are evidence too." >&2
fi

exit 0
