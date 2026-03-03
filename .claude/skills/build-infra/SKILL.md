---
name: build-infra
description: Build new data source tools and infrastructure from the infra request queue
user_invocable: true
---

# /build-infra

Claim an infrastructure request and build the tool, or scan for infrastructure gaps and create requests.

## Arguments

- No arguments: claim the next open infra request and build it
- `scan`: scan for infrastructure gaps and create requests
- `<ID>`: claim a specific infra request by ID

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill.

## Modes

### Targeted Mode (default)

Claim an open infra request, evaluate it, build the tool, test it, and complete.

### Scan Mode (`/build-infra scan`)

Audit the investigation platform for gaps and create infra requests.

## Targeted Mode Process

### 1. Select Request

```bash
# No args — get next by priority
uv run python tools/infra_tracker.py next

# Specific ID
uv run python tools/infra_tracker.py show <ID>
```

### 2. Claim and Evaluate

```bash
uv run python tools/infra_tracker.py claim <ID>
```

**Probe the endpoint before writing code.** This is the critical step.

For REST APIs:
- Fetch the documentation page with WebFetch
- Try a test query with WebFetch or curl
- Check authentication requirements
- Verify response format

For bulk downloads:
- Check if the URL/SFTP is accessible
- Verify file format and size
- Check if data is current

For web scrape targets:
- Load the page with Playwright
- Check for anti-bot protection
- Verify the data structure

Record probe results:
```bash
uv run python tools/infra_tracker.py evaluate <ID> \
  --probe-results "API confirmed at https://... Returns JSON. No auth. Rate limit 10/sec." \
  --proceed
```

If the endpoint doesn't work or requires paid access:
```bash
uv run python tools/infra_tracker.py evaluate <ID> \
  --notes "API requires paid subscription ($500/year). Documented at URL." \
  --reject
```

### 3. Build the Tool

Follow existing tool patterns. Reference similar tools in `tools/` for structure.

**Naming convention:**
- Query tools (API): `tools/query_<source>.py`
- Ingest tools (bulk/scrape → registry.db or investigation.db): `tools/ingest_<source>.py`

**Required elements:**
1. CLI with argparse + subcommands
2. `--output` flag support via `output_util.py`
3. Rate limiting for external APIs
4. Error handling with retries
5. Search logging via `lead_tracker.log_search()`

**Template structure:**
```python
#!/usr/bin/env python3
"""
<Source Name> integration for OSINT investigation.

Usage:
    python tools/query_<source>.py search "query"
    python tools/query_<source>.py entity <id>
"""
import argparse
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

# ... implementation ...

def main():
    parser = argparse.ArgumentParser(description="<Source> query tool")
    sub = parser.add_subparsers(dest="command")
    # ... subcommands ...
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    # ... dispatch ...

if __name__ == "__main__":
    main()
```

### 4. Test the Tool

Run the tool against known targets to verify (use key_persons from the investigation profile):
```bash
# Test basic search
uv run python tools/query_<source>.py search "{TARGET}" --output /tmp/test-search.json

# Test with known entities
uv run python tools/query_<source>.py search "{TARGET}" --output /tmp/test-entity.json

# Verify output format
uv run python -c "import json; d=json.load(open('/tmp/test-search.json')); print(len(d), type(d))"
```

### 5. Document and Complete

Update documentation:
1. Add tool to `CLAUDE.md` data sources section
2. Add CLI examples to `docs/TOOL_REFERENCE.md`
3. Update `memory/MEMORY.md` key tools table

Complete the request:
```bash
uv run python tools/infra_tracker.py complete <ID> \
  --tool-file "tools/query_<source>.py" \
  --files-modified tools/query_<source>.py CLAUDE.md docs/TOOL_REFERENCE.md \
  --summary "Built <source> integration. Covers X records. No auth required."
```

This auto-unblocks any leads that were waiting on this infrastructure.

## Scan Mode Process

### 1. Audit Source Health

```bash
uv run python tools/source_report.py
```

Check for:
- Tools that are broken or returning errors
- Sources with zero coverage for key targets
- Missing jurisdictions in the registry

### 2. Check Priority Sources

Review the priority sources list in `CLAUDE.md` under "Priority Sources (Not Yet Integrated)".
Check `memory/MEMORY.md` for the "Priority Sources to Add" section.

### 3. Search Log Analysis

Find tools that consistently return zero results:
```bash
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('''
    SELECT source, COUNT(*) as searches, SUM(CASE WHEN result_count = 0 THEN 1 ELSE 0 END) as zeros
    FROM search_log GROUP BY source HAVING zeros > searches * 0.8 ORDER BY searches DESC
''').fetchall()
for r in rows: print(f'{r[0]}: {r[1]} searches, {r[2]} zeros ({r[2]*100//r[1]}%)')
"
```

### 4. Check Existing Requests

Don't duplicate:
```bash
uv run python tools/infra_tracker.py list --status open
uv run python tools/infra_tracker.py list --status evaluating
```

### 5. Create Requests

For each gap found:
```bash
uv run python tools/infra_tracker.py add \
  --title "Integrate <source name>" \
  --type new_source \
  --description "Description of source, what data it contains, why it matters for the investigation. At least 20 characters." \
  --source-name "<source>" \
  --source-url "https://..." \
  --data-type "corporate registrations" \
  --access-method rest_api \
  --auth none \
  --coverage "~50K entities" \
  --priority medium \
  --discovered-by "agent:build-infra-scan" \
  --discovered-during "infrastructure audit"
```

### 6. Report

Summarize what was found:
```
## /build-infra scan — Results

### Source Health
- X tools healthy, Y with issues

### Infrastructure Gaps Found
- [gap 1]: created infra request #N
- [gap 2]: created infra request #N

### Priority Sources Status
- [source]: [status — not started / request exists #N / completed]

### Recommendations
- [what to build next and why]
```

## Probe-Before-Code Rule

**Never write a tool targeting an unverified endpoint.** The workflow is:

1. **Discover**: Find the API/data source
2. **Probe**: Make a real request, verify it works
3. **Evaluate**: Record results in infra_tracker
4. **Build**: Write the tool only after confirming the endpoint
5. **Test**: Verify against known targets
6. **Document**: Update CLAUDE.md and TOOL_REFERENCE.md

If probing fails (403, paywall, requires registration), record the failure and reject or block the request. Do not write speculative code.

## Context Management

- Use `--output /tmp/...` on all search commands
- Keep tool code focused — one source per tool file
- Reuse `output_util.py` for consistent output handling
