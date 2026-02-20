---
name: triage-leads
description: Process pending_triage leads — deduplicate, prioritize, link, and promote to open
---

# /triage-leads

Process a batch of `pending_triage` leads created by `auto_leads.py`. Deduplicates, reprioritizes, links related leads, and promotes to `open`.

## Arguments

- No arguments: process the next batch (up to 20 leads)
- `--batch-size N`: process N leads instead of default 20
- `--dry-run`: preview triage decisions without modifying the DB

## Process

### 0. Session Setup — Prevent File Collisions

Create a unique working directory for this session:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)
echo "Session workdir: $WORKDIR"
```

Use `$WORKDIR/` instead of `/tmp/` for ALL `--output` paths throughout this session.

### 1. Check Queue Depth

```bash
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
total = db.execute(\"SELECT COUNT(*) FROM leads WHERE status='pending_triage'\").fetchone()[0]
by_cat = db.execute(\"SELECT category, COUNT(*) FROM leads WHERE status='pending_triage' GROUP BY category ORDER BY COUNT(*) DESC\").fetchall()
print(f'Pending triage: {total}')
for cat, cnt in by_cat: print(f'  {cat}: {cnt}')
"
```

If zero leads pending, report that and exit.

### 2. Claim Batch

```bash
uv run python -c "
import sqlite3, json
db = sqlite3.connect('investigation.db')
rows = db.execute('''
    SELECT id, title, description, category, priority, source, target_name, created_at
    FROM leads WHERE status='pending_triage'
    ORDER BY
        CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
        created_at ASC
    LIMIT 20
''').fetchall()
leads = [dict(zip([d[0] for d in rows[0].description] if hasattr(rows[0], 'description') else ['id','title','description','category','priority','source','target_name','created_at'], r)) for r in rows] if rows else []
json.dump([dict(r) for r in rows], open('$WORKDIR/triage-batch.json','w'), indent=2, default=str)
print(f'Claimed {len(rows)} leads for triage')
" --output $WORKDIR/triage-batch.json
```

Or more simply, use the Python API directly within your analysis.

### 3. For Each Lead, Apply Triage Rules

Process each lead through these checks in order:

#### 3a. Deduplication Check

Search for leads with similar titles or the same target:

```bash
uv run python tools/lead_tracker.py search "<LEAD_TITLE_KEYWORDS>" --output $WORKDIR/triage-dupes.json
```

Also check by target_name:
```bash
uv run python -c "
import sqlite3, json
db = sqlite3.connect('investigation.db')
db.row_factory = sqlite3.Row
rows = db.execute('''
    SELECT id, title, status, priority, target_name
    FROM leads
    WHERE target_name LIKE ? AND status != 'pending_triage' AND id != ?
''', ('%<TARGET>%', <LEAD_ID>)).fetchall()
json.dump([dict(r) for r in rows], open('$WORKDIR/triage-target-dupes.json','w'), indent=2)
print(f'{len(rows)} existing leads for this target')
"
```

**If near-duplicate found** (same target + similar title/description):
- Dead-end the triage lead with reason "Duplicate of lead #X"
- Add a note to the original lead referencing this one
- Link them: `INSERT INTO lead_relations (lead_id, related_lead_id, relation_type) VALUES (original_id, triage_id, 'duplicate')`

#### 3b. Coverage Check

How well-investigated is this target already?

```bash
uv run python tools/findings_tracker.py search "<TARGET>" --output $WORKDIR/triage-findings.json
```

- **5+ findings**: Target is well-covered. Lower priority unless the lead opens a genuinely new angle.
- **1-4 findings**: Partially covered. Keep current priority.
- **0 findings**: Under-investigated. If the target is interesting (connected to key persons, financial angle), raise priority.

#### 3c. Priority Adjustment

Adjust priority based on:

| Signal | Priority Change |
|--------|----------------|
| Target is key person (Wexner, Black, Indyke, etc.) | Raise to `high` |
| Financial angle (trust, LLC, fund, transfer) | Raise by one level |
| Entity with 3+ roles in entity_roles | Raise to `medium` minimum |
| Target has 5+ existing findings | Lower by one level |
| Generic cross-ref with low-value target | Lower to `low` |
| Address-only lead at non-key address | Lower to `low` |

Key persons to check (raise priority if target matches):
- Wexner, Black, Indyke, Kahn, Groff, Maxwell, Dubin, Summers
- Ruemmler, Barak, Rod-Larsen, Bannon, Wolff, Thomas
- Any person with 10+ email correspondences
- Thread-specific key persons may vary — check the thread description for guidance

#### 3c-bis. Thread Assignment

If a lead clearly belongs to an investigation thread, assign it:
- Mega Group targets (Lauder, Steinhardt, Bronfman, Lender, Fisher, Crown) → thread_id=2
- Deutsche Bank / banking targets → thread_id=3
- Israeli intelligence targets (Barak, Carbyne, Maxwell family) → thread_id=4
- Apollo / Leon Black financial targets → thread_id=5
- Gulf state targets (Al Thani, Alsabbagh, Broidy, Nader) → thread_id=6
- General Epstein network → thread_id=1 (or leave NULL if unclear)

Threads with fewer findings should get a slight priority boost to balance coverage across threads.

#### 3d. Category Enrichment

If category is missing, infer from title/description:
- "officer" / "person" keywords → `person`
- "registry" / "entity" / "LLC" / "trust" keywords → `entity`
- "address" / "property" keywords → `entity`
- "financial" / "payment" / "transfer" → `financial`
- "connection" keywords → `connection`

If target_name is obvious from the title but missing, fill it in.

#### 3e. Link Related Leads

Find leads sharing the same target or closely related targets:

```bash
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
# Find leads with same target
rows = db.execute('''
    SELECT id, title FROM leads
    WHERE target_name = ? AND id != ? AND status IN ('open','in_progress','pending_triage')
''', ('<TARGET>', <LEAD_ID>)).fetchall()
for r in rows: print(f'Related: #{r[0]} {r[1]}')
"
```

Create `lead_relations` entries for related leads:
```sql
INSERT OR IGNORE INTO lead_relations (lead_id, related_lead_id, relation_type) VALUES (?, ?, 'related')
```

### 4. Promote to Open

For leads that pass triage (not deduped):

```bash
uv run python -c "
import sqlite3
from datetime import datetime
db = sqlite3.connect('investigation.db')
now = datetime.utcnow().isoformat()
db.execute('''
    UPDATE leads SET status='open', triaged_by='agent:triage', triaged_at=?, updated_at=?
    WHERE id=?
''', (now, now, <LEAD_ID>))
db.commit()
"
```

If priority was adjusted:
```bash
uv run python -c "
import sqlite3
from datetime import datetime
db = sqlite3.connect('investigation.db')
now = datetime.utcnow().isoformat()
db.execute('''
    UPDATE leads SET status='open', priority=?, triaged_by='agent:triage', triaged_at=?, updated_at=?
    WHERE id=?
''', ('<NEW_PRIORITY>', now, now, <LEAD_ID>))
db.commit()
"
```

### 5. Report

After processing the batch, summarize:

```
## /triage-leads — Batch Results

### Summary
- Processed: X leads
- Promoted to open: Y
- Deduplicated (dead-ended): Z
- Reprioritized: W

### Remaining Queue
- N leads still pending triage

### Deduplication Details
| Lead # | Title | Duplicate Of | Action |
|--------|-------|-------------|--------|
| #1234  | Cross-ref officer: John Smith | #890 | dead_end |

### Priority Changes
| Lead # | Title | Old Priority | New Priority | Reason |
|--------|-------|-------------|-------------|--------|
| #1235  | Cross-ref registry: Wexner Trust | medium | high | Key person target |

### Links Created
- Lead #1236 ↔ Lead #1237 (shared target: "457 Madison")
```

## Triage Philosophy

### What to Dead-End
- Exact or near-exact duplicates of existing leads
- Cross-refs for well-known public entities (Goldman Sachs, Harvard) with no specific Epstein angle
- Address cross-refs for generic addresses (c/o, PO Box, major commercial buildings not in key addresses list)

### What to Keep
- Any lead targeting a person with < 3 findings
- Any lead with a financial or corporate angle
- Any lead targeting an entity at a known Epstein address
- Cross-refs for officers at 2+ Epstein-linked entities

### What to Raise Priority
- Leads connected to the financial flow investigation (Black, STC, Deutsche Bank)
- Leads targeting the 5-tier corporate architecture entities
- Cross-refs that could reveal new lateral connections

## Autonomy Level

The triage agent has **moderate autonomy**:
- CAN dead-end clear duplicates without human approval
- CAN adjust priorities up or down within the range (low ↔ high)
- CAN enrich category and target_name fields
- CAN create lead_relations links
- CANNOT set priority to `critical` (reserved for human judgment)
- CANNOT delete leads (only dead_end)

Human reviews dead-ends periodically to catch false positives.

## Context Management

- Use `--output $WORKDIR/...` on all searches
- Process leads in batches of 20 max to keep context manageable
- Record triage decisions as lead notes for audit trail
