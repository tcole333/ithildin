#!/bin/bash
# check-existing-research.sh — PostToolUse hook for Bash
# After an agent runs a findings_tracker add, remind them to check
# if similar findings already exist (prevents duplicate work).
# Also flags high-confidence claims from agents for review.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Check if a finding was just added
if echo "$COMMAND" | grep -qE "findings_tracker[^ ]*\s+add\s+"; then
  # Extract target name portably (supports --target value and --target=value forms)
  TARGET=$(COMMAND_STR="$COMMAND" python3 - <<'PY'
import os
import shlex

command = os.environ.get("COMMAND_STR", "")
target = ""

try:
    parts = shlex.split(command)
except ValueError:
    parts = command.split()

for i, part in enumerate(parts):
    if part == "--target" and i + 1 < len(parts):
        target = parts[i + 1]
        break
    if part.startswith("--target="):
        target = part.split("=", 1)[1]
        break

print(target)
PY
)

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
