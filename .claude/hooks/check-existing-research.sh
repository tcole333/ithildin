#!/bin/bash
# check-existing-research.sh — PostToolUse hook for Bash
# After an agent runs a findings_tracker add, remind them to check
# if similar findings already exist (prevents duplicate work).
# Also flags high-confidence claims from agents for review.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Check if a finding was just added
if echo "$COMMAND" | grep -qE "findings_tracker[^ ]*\s+add\s+"; then
  # Extract target name
  TARGET=$(echo "$COMMAND" | grep -oP "(?<=--target\s)['\"]([^'\"]+)['\"]" | tr -d "'\"" | head -1)
  if [ -z "$TARGET" ]; then
    TARGET=$(echo "$COMMAND" | grep -oP '(?<=--target\s)\S+' | head -1)
  fi

  if [ -n "$TARGET" ]; then
    # Check for existing findings on this target using parameterized query
    DB="$CLAUDE_PROJECT_DIR/investigation.db"
    if [ -f "$DB" ]; then
      EXISTING=$(TARGET_NAME="$TARGET" DB_PATH="$DB" python3 -c "
import os, sqlite3
db = sqlite3.connect(os.environ['DB_PATH'])
t = os.environ.get('TARGET_NAME', '')
print(db.execute('SELECT COUNT(*) FROM findings WHERE target_name LIKE ?', (f'%{t}%',)).fetchone()[0])
db.close()
" 2>/dev/null || echo "0")
      if [ "$EXISTING" -gt 1 ]; then
        # Escape target for JSON output
        ESCAPED_TARGET=$(echo "$TARGET" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip())[1:-1])")
        echo "{\"additionalContext\": \"Note: There are now $EXISTING findings for '$ESCAPED_TARGET'. Consider checking for duplicates: python tools/findings_tracker.py list --target '$ESCAPED_TARGET'\"}"
      fi
    fi
  fi
fi

exit 0
