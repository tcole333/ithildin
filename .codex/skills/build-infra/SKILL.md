---
name: build-infra
description: Build new data source tools and infrastructure from the infra request queue
---

# $build-infra

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

### Scan Mode (`$build-infra scan`)

Audit the investigation platform for gaps and create infra requests.

## Targeted Mode Process

### 0. Session Setup

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Use this directory for every probe/test artifact so parallel builders cannot
overwrite one another.

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

Paid, registered, request, purchase, or physical access is an access fact, not
a reason to reject the source. Record the observed route and proceed when the
request can be satisfied by an account-aware adapter, catalog entry, licensed
product, or reproducible human action:
```bash
uv run python tools/infra_tracker.py evaluate <ID> \
  --probe-results "Official API requires a paid account; public request route confirmed at https://..." \
  --notes "Retain both the licensed API and public request capabilities." \
  --proceed
```

Use `--block` when a missing credential, account, purchase decision, or other
dependency prevents the requested implementation from continuing. Reject only
when evaluation shows that the request itself is invalid, duplicated or
superseded, or has no viable and useful source route.

Before settling the evaluation, map complementary routes for the same
information need. When the preferred source is partial, interactive, paid,
offline, or otherwise difficult to acquire, check adjacent official and useful
public sources such as calendars, appellate indexes and opinions, recorder or
assessor records, agency notices, bulk programs, archives, and defined
request/copy channels. Record each viable route as a distinct source or action,
including the fields and periods it adds and the gaps it leaves. Treat overlap
as complementary coverage unless the evidence establishes field-level
equivalence.

When the source publishes both row/feature identifiers and business fields,
audit the occurrence grain separately from candidate joins. Sample
source-observed blank, whitespace, and sentinel encodings as well as database
nulls. Preserve the raw values and attributable occurrences; project a
business join only where the observed fields support one.

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
    uv run python tools/query_<source>.py search "query"
    uv run python tools/query_<source>.py entity <id>
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
uv run python tools/query_<source>.py search "{TARGET}" --output "$WORKDIR/test-search.json"

# Test with known entities
uv run python tools/query_<source>.py search "{TARGET}" --output "$WORKDIR/test-entity.json"

# Verify output format
uv run python - "$WORKDIR/test-search.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(len(d), type(d))
PY
```

### 5. Document and Complete

Update documentation:
1. Add the tool to the relevant `docs/modules/*.md` source module and `docs/TOOL_REFERENCE.md`
2. Update `CLAUDE.md` and `AGENTS.md` source inventories when the new source changes their overview
3. Add its citation type to `web/src/lib/citations.ts`, or add one-off URL mappings to `web/src/data/source-urls.json`
4. Update `tools/source_report.py` when the source has a health/readiness check
5. Update every workflow skill that should call the tool in both `.claude` and `.codex` trees
6. Keep durable source summaries in the canonical module and tool reference; do not create a separate memory copy

Complete the request:
```bash
uv run python tools/infra_tracker.py complete <ID> \
  --tool-file "tools/query_<source>.py" \
  --files-modified tools/query_<source>.py docs/modules/<module>.md docs/TOOL_REFERENCE.md web/src/lib/citations.ts \
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

### 2. Review Canonical Source Inventories

Review the source-category table in `AGENTS.md`, the corresponding
`docs/modules/*.md` inventories, `docs/TOOL_REFERENCE.md`, and
`research/OSINT_RESOURCES.md`. Compare those documented sources with the live
health report and the open/evaluating infra queue before proposing a gap. Do
not rely on a separate memory or priority-source list. For incomplete or
difficult primary routes, include complementary sources that satisfy part of
the same information need and state their field and coverage differences.

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
## $build-infra scan — Results

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
6. **Document**: Update the canonical module, tool reference, citations, source health, and affected skills

If probing encounters a 403, paywall, registration, purchase, request, or
physical-access workflow, record exactly what was observed and retain that
route when it is useful. Proceed with a supported adapter, catalog entry, or
human action; block when the current implementation has an unmet dependency;
reject only when the request itself is not viable. Do not write speculative
code or reject a source solely because machine access is not anonymous.

## Context Management

- Use `--output "$WORKDIR/..."` on all search commands
- Keep tool code focused — one source per tool file
- Reuse `output_util.py` for consistent output handling
