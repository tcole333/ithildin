#!/bin/bash
# protect-investigation-db.sh — PreToolUse hook for Bash
# Prevents destructive operations on investigation.db and enforces
# that data modifications go through the CLI tools (maintaining audit trail).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Skip if command doesn't mention investigation.db or the tracker tools
if ! echo "$COMMAND" | grep -qiE "investigation\.db|findings_tracker|lead_tracker"; then
  exit 0
fi

# Block destructive SQL operations on investigation.db
if echo "$COMMAND" | grep -qi "investigation\.db"; then
  # Block DROP TABLE
  if echo "$COMMAND" | grep -qiE "DROP\s+TABLE"; then
    echo "BLOCKED: DROP TABLE on investigation.db is not allowed. This would destroy investigation data." >&2
    exit 2
  fi

  # Block unqualified DELETE FROM (allow only through tools)
  if echo "$COMMAND" | grep -qiE "DELETE\s+FROM" && ! echo "$COMMAND" | grep -q "tools/"; then
    echo "BLOCKED: DELETE FROM investigation.db via raw SQL is not allowed. Use the CLI tools to maintain audit trail." >&2
    exit 2
  fi

  # Block rm on the database file
  if echo "$COMMAND" | grep -qE "rm\s+.*investigation\.db"; then
    echo "BLOCKED: Cannot delete investigation.db. Back it up instead: cp investigation.db investigation.db.bak" >&2
    exit 2
  fi

  # Block direct UPDATE on findings/connections tables (must go through findings_tracker correct)
  if echo "$COMMAND" | grep -qiE "UPDATE\s+(findings|connections)\s+SET" && \
     ! echo "$COMMAND" | grep -q "tools/"; then
    echo "BLOCKED: Direct UPDATE on findings/connections bypasses the audit trail. Use 'python tools/findings_tracker.py correct <id> --field <field> --value <value> --reason <reason>' instead." >&2
    exit 2
  fi
fi

exit 0
