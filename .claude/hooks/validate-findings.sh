#!/bin/bash
# validate-findings.sh — PreToolUse hook for Bash
# Ensures findings_tracker.py add commands include proper provenance:
#   1. --evidence (at least one source reference)
#   2. --source-quote (traceable quote from source)
#   3. --claim-type (direct_quote|paraphrase|inference|synthesis|user_provided)
#   4. confidence rules (only direct_quote from primary source can be "confirmed")

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only validate findings_tracker add commands
if ! echo "$COMMAND" | grep -qE "findings_tracker[^ ]*\s+add\s+"; then
  exit 0
fi

# 1. Require --evidence
if ! echo "$COMMAND" | grep -q -- "--evidence"; then
  echo "BLOCKED: findings_tracker add requires --evidence flag. Every finding must cite at least one source (EFTA ID, file path, or URL). Add --evidence EFTA02XXXXXX or similar." >&2
  exit 2
fi

# 2. Require --source-quote for document-type evidence refs
# Structured data (FEC, 990, ACRIS, FARA, LDA, SEC, FAA, UCC, GLEIF, etc.) doesn't need quotes —
# the evidence_ref itself IS the verification.
EVIDENCE_VAL=$(echo "$COMMAND" | sed -n "s/.*--evidence[= ]*'\([^']*\)'.*/\1/p")
if [ -z "$EVIDENCE_VAL" ]; then
  EVIDENCE_VAL=$(echo "$COMMAND" | sed -n 's/.*--evidence[= ]*"\([^"]*\)".*/\1/p')
fi
if [ -z "$EVIDENCE_VAL" ]; then
  EVIDENCE_VAL=$(echo "$COMMAND" | awk '{for(i=1;i<=NF;i++) if($i=="--evidence") print $(i+1)}')
fi
# Check if evidence is a structured data type (source_quote optional)
IS_STRUCTURED=false
if echo "$EVIDENCE_VAL" | grep -qiE "^(FEC|IRS.?990|990:|ProPublica|PP990|PROPUBLICA|ACRIS|FARA|LDA|SEC|EDGAR|FAA|UCC|GLEIF|OpenSanctions|ICIJ|OCCRP|FL_SUNBIZ|FL.SunBiz|FL:|NY_DOS|NY.SoS|NY.DOS|NM.SoS|DC_|OC:|UK.Companies|USVI)"; then
  IS_STRUCTURED=true
fi

if [ "$IS_STRUCTURED" = "false" ] && ! echo "$COMMAND" | grep -q -- "--source-quote"; then
  echo "BLOCKED: findings_tracker add requires --source-quote flag for document-type evidence. Provide the exact text from the source that supports this claim. Format: --source-quote 'EFTAXXXX:exact quote text here'. (Structured data like FEC/990/ACRIS/FARA refs are exempt.)" >&2
  exit 2
fi

# 3. Require --claim-type
if ! echo "$COMMAND" | grep -q -- "--claim-type"; then
  echo "BLOCKED: findings_tracker add requires --claim-type flag. Must be one of: direct_quote, paraphrase, inference, synthesis, user_provided" >&2
  exit 2
fi

# 4. Confidence validation: agents cannot set "confirmed" for inferences/syntheses
if echo "$COMMAND" | grep -qE "\-\-confidence +confirmed"; then
  # Extract claim-type using awk (portable)
  CLAIM_TYPE=$(echo "$COMMAND" | awk '{for(i=1;i<=NF;i++) if($i=="--claim-type") print $(i+1)}')
  if [ "$CLAIM_TYPE" = "inference" ] || [ "$CLAIM_TYPE" = "synthesis" ]; then
    echo "BLOCKED: confidence 'confirmed' is not allowed for claim_type '$CLAIM_TYPE'. Only direct_quote from primary sources can be 'confirmed'. Use 'high' for well-supported inferences or 'medium' for syntheses." >&2
    exit 2
  fi
fi

# 5. Reject header-only source_quote for direct_quote claims
if echo "$COMMAND" | grep -q -- "--claim-type direct_quote"; then
  # Extract the source-quote value (text after --source-quote up to next --)
  SQ=$(echo "$COMMAND" | sed -n "s/.*--source-quote[= ]*'\([^']*\)'.*/\1/p")
  if [ -z "$SQ" ]; then
    SQ=$(echo "$COMMAND" | sed -n 's/.*--source-quote[= ]*"\([^"]*\)".*/\1/p')
  fi
  if [ -n "$SQ" ]; then
    # Check if quote starts with "From:" (email header, not actual quote)
    if echo "$SQ" | grep -qE "^[^:]*From:"; then
      echo "BLOCKED: source_quote for direct_quote claims must contain the actual quoted text, not email headers. The quote starts with 'From:' which is an email header. Extract the actual content from the email body." >&2
      exit 2
    fi
    # Check if quote is too short (< 20 chars after removing the ref prefix)
    QUOTE_TEXT=$(echo "$SQ" | sed 's/^EFTA[0-9]*://')
    QUOTE_LEN=${#QUOTE_TEXT}
    if [ "$QUOTE_LEN" -lt 20 ]; then
      echo "BLOCKED: source_quote for direct_quote claims must be at least 20 characters (got $QUOTE_LEN). Provide enough text to verify the claim against the source document." >&2
      exit 2
    fi
  fi
fi

exit 0
