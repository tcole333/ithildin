#!/bin/bash
# validate-dead-end.sh — PreToolUse hook for Bash
# Ensures lead_tracker.py dead-end commands include substantive rationale.
# Every dead-end decision must be auditable via `triage-log --missing-rationale`.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only validate lead_tracker dead-end commands
if ! echo "$COMMAND" | grep -qE "lead_tracker[^ ]*\s+dead-end\s+"; then
  exit 0
fi

# Extract the reason argument (positional, after the lead ID)
# Pattern: lead_tracker.py dead-end <ID> "<reason>"
REASON=$(echo "$COMMAND" | sed -n "s/.*dead-end [0-9]* *\"\([^\"]*\)\".*/\1/p")
if [ -z "$REASON" ]; then
  REASON=$(echo "$COMMAND" | sed -n "s/.*dead-end [0-9]* *'\([^']*\)'.*/\1/p")
fi

# Check reason is present
if [ -z "$REASON" ]; then
  echo "BLOCKED: lead_tracker dead-end requires a quoted reason explaining WHY this lead is a dead end. This enables audit review via \`triage-log --missing-rationale\`." >&2
  exit 2
fi

# Check reason is substantive (>= 20 chars)
REASON_LEN=${#REASON}
if [ "$REASON_LEN" -lt 20 ]; then
  echo "BLOCKED: Dead-end reason must be >= 20 characters (got $REASON_LEN). Explain WHY: duplicate of lead #X, exhaustively covered, no investigative angle, etc." >&2
  exit 2
fi

# Block generic/trivial reasons
REASON_LOWER=$(echo "$REASON" | tr '[:upper:]' '[:lower:]')
case "$REASON_LOWER" in
  "irrelevant"|"not needed"|"skip"|"n/a"|"not relevant"|"no reason")
    echo "BLOCKED: Dead-end reason '$REASON' is too generic. Explain the specific reason: what was checked, why this lead has no value, or which existing lead covers this target." >&2
    exit 2
    ;;
esac

exit 0
