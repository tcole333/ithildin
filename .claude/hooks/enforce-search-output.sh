#!/bin/bash
# enforce-search-output.sh — PreToolUse hook for Bash
# Blocks search/query commands that omit --output flag.
# Large result sets dumped inline cause 10-50MB context bloat per agent.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only check commands running our query/search tools
if ! echo "$COMMAND" | grep -qE "tools/(query_|duggan_search|parse_ds10_financials)"; then
  exit 0
fi

# Skip commands that already have --output
if echo "$COMMAND" | grep -q -- "--output"; then
  exit 0
fi

# Skip single-item retrieval commands (small results, --output not needed)
if echo "$COMMAND" | grep -qE "(efta|read|stats|download|ingest|detail|n-number|lookup|normalize|known)\b"; then
  exit 0
fi

# Skip commands piped to other tools (already processing output)
if echo "$COMMAND" | grep -q "|"; then
  exit 0
fi

# Match bulk-result subcommands that MUST use --output
BULK_CMDS="search|entities|cooccurrence|emails|docs|triples|party|donor|employer|address|client|registrant|lobbyist|articles|context|timeline|officers|filings|relationships|connections|cases|opinions|docket|batch|history|contributions|query|balances|flows|ein|match-entities|pep-check|expand|similar|ucc-search|ucc-party|ucc-collateral"

if echo "$COMMAND" | grep -qE "\b($BULK_CMDS)\b"; then
  echo "BLOCKED: Search commands must use --output /tmp/<name>.json to prevent context bloat. Example: --output /tmp/search-result.json" >&2
  exit 2
fi

# duggan_search.py has no subcommand — always returns bulk results
if echo "$COMMAND" | grep -qE "duggan_search\.py" && ! echo "$COMMAND" | grep -q -- "--output"; then
  echo "BLOCKED: duggan_search.py must use --output /tmp/<name>.json to prevent context bloat." >&2
  exit 2
fi

exit 0
