---
name: triage-leads
description: Process pending_triage leads — deduplicate, prioritize, link, and promote to open
user_invocable: true
---

# /triage-leads

**CONTROL PLANE** — This is a scheduling skill. Evaluate leads, assign depth tiers and recommended skills using rules from `tools/triage_policy.py`, and route work to the appropriate research agents. Do not investigate targets directly.

Process a batch of `pending_triage` leads created by `auto_leads.py`. Deduplicates, reprioritizes, links related leads, and promotes to `open`.

## Arguments

- No arguments: process the next batch (up to 20 leads)
- `--batch-size N`: process N leads instead of default 20
- `--dry-run`: preview triage decisions without modifying the DB

### Context Loading
Load the active investigation context before executing:
```bash
uv run python tools/investigation_context.py show
```
This provides: primary_subject, key_persons, threads, corpus_tools, key_dates, known_addresses.
Use these values instead of hardcoded names throughout this skill.

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
| Target is a key person from the investigation profile | Raise to `high` |
| Financial angle (trust, LLC, fund, transfer) | Raise by one level |
| Entity with 3+ roles in entity_roles | Raise to `medium` minimum |
| Target has 5+ existing findings | Lower by one level |
| Generic cross-ref with low-value target | Lower to `low` |
| Address-only lead at non-key address | Lower to `low` |

Elevate priority for key persons listed in the active investigation profile (loaded via `investigation_context.py`). Also elevate:
- Any person with 10+ email correspondences
- Thread-specific key persons — check the thread description for guidance

#### 3c-bis. Thread Assignment

If a lead clearly belongs to an investigation thread, assign it based on the investigation profile's thread definitions (loaded via `investigation_context.py`). Match targets to threads by their described scope and key persons. Leave thread_id NULL if the match is unclear.

Threads with fewer findings should get a slight priority boost to balance coverage across threads.

#### 3d. Category Enrichment

If category is missing, infer from title/description:
- "officer" / "person" keywords → `person`
- "registry" / "entity" / "LLC" / "trust" keywords → `entity`
- "address" / "property" keywords → `entity`
- "financial" / "payment" / "transfer" → `financial`
- "nonprofit" / "foundation" / "501(c)" / "grant" / "donor" / "grantee" / "dark money" / "donor-advised" → `nonprofit`
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

#### 3f. Depth Tier Assignment

Assign a `depth_tier` based on the target's structural position and information richness:

| Signal | Depth Tier |
|--------|-----------|
| Target is a key_person from the investigation profile | `deep_dive` |
| Target has 3+ entity_roles or 3+ connections already | `standard` (may escalate to `deep_dive`) |
| Entity at a known_address from the profile | `standard` |
| Nonprofit target appearing as filer/recipient in 990 grants to/from 3+ investigation entities | `standard` (may escalate to `deep_dive`) |
| Generic cross-ref with no special signals | `scan` |
| New person with 0 findings, not a key_person | `scan` |

Query to assess structural position:
```bash
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
target = '<TARGET>'
roles = db.execute('SELECT COUNT(*) FROM entity_roles WHERE person_name LIKE ?', (f'%{target}%',)).fetchone()[0]
conns = db.execute('SELECT COUNT(*) FROM connections WHERE person_a LIKE ? OR person_b LIKE ?', (f'%{target}%', f'%{target}%')).fetchone()[0]
findings = db.execute('SELECT COUNT(*) FROM findings WHERE target_name LIKE ?', (f'%{target}%',)).fetchone()[0]
print(f'roles={roles} connections={conns} findings={findings}')
"
```

#### 3g. Recommended Skill Assignment

Based on depth_tier and category, set `recommended_skill`:

| Depth Tier + Category | Recommended Skill |
|----------------------|-------------------|
| `deep_dive` + person | `/deep-investigate` |
| `deep_dive` + entity | `/deep-investigate` |
| `standard` + person | `/investigate-person` |
| `standard` + entity | `/trace-entity` |
| `standard` + financial | `/pursue-lead` |
| `*` + nonprofit | `/trace-grants` |
| `*` + grant | `/trace-grants` |
| `standard` + other | `/pursue-lead` |

**Cohort escalation:** When 3+ contract-category leads exist for different companies in the same investigation thread, suggest `/audit-contracts` for comparative procurement analysis instead of individual `/analyze-contract` runs.
| `scan` + any | `/pursue-lead` |

#### 3h. Thread Coverage Balancing

Check thread coverage balance before finalizing priorities:

```bash
uv run python -c "
import sqlite3
db = sqlite3.connect('investigation.db')
rows = db.execute('''
    SELECT t.id, t.title,
           (SELECT COUNT(*) FROM leads WHERE thread_id=t.id AND status IN ('open','in_progress')) as active_leads,
           (SELECT COUNT(*) FROM findings WHERE thread_id=t.id) as finding_count
    FROM investigation_threads t WHERE t.status='active'
    ORDER BY finding_count ASC
''').fetchall()
for r in rows:
    print(f'thread={r[0]} title={r[1]} active_leads={r[2]} findings={r[3]}')
"
```

Threads with fewer findings AND fewer active leads get a priority boost (raise by one level, capped at `high`). This prevents popular threads from starving under-investigated threads.

#### 3i. Stop Conditions

Before promoting, check if the lead should be stopped rather than investigated:

- **Target already exhaustively covered**: 10+ findings, no new angle in the lead description → dead-end with `stop_reason='exhaustively_covered'`
- **Duplicate target at same depth**: An existing open/in_progress lead for the same target_name at the same or higher depth_tier → dead-end with `stop_reason='covered_by_lead_#N'`
- **Budget throttle**: If more than 30 leads are open + in_progress for the same thread, only promote `high` and `critical` leads. Lower-priority leads stay in pending_triage until the queue drains.

#### 3j. Record Triage Rationale

For every lead processed, write a `triage_rationale` explaining the decision:

```sql
UPDATE leads SET triage_rationale=? WHERE id=?
```

Format: `"[ACTION]: [REASON]. depth_tier=[TIER], recommended_skill=[SKILL]"`

Examples:
- `"PROMOTED: Key person with 0 findings. depth_tier=deep_dive, recommended_skill=/deep-investigate"`
- `"DEPRIORITIZED: 8 existing findings, no new angle. depth_tier=scan, recommended_skill=/pursue-lead"`
- `"DEAD-ENDED: Duplicate of lead #1234 at standard tier"`
- `"HELD: 35 leads active in thread 3, holding medium-priority leads until queue drains"`

### 4. Promote to Open

For leads that pass triage (not deduped and not held), update all scheduler fields:

```bash
uv run python -c "
import sqlite3
from datetime import datetime
db = sqlite3.connect('investigation.db')
now = datetime.utcnow().isoformat()
db.execute('''
    UPDATE leads SET status='open', priority=?, depth_tier=?, recommended_skill=?,
        triage_rationale=?, triaged_by='agent:triage', triaged_at=?, updated_at=?
    WHERE id=?
''', ('<PRIORITY>', '<DEPTH_TIER>', '<RECOMMENDED_SKILL>', '<RATIONALE>', now, now, <LEAD_ID>))
db.commit()
"
```

For leads that are dead-ended by stop conditions:
```bash
uv run python -c "
import sqlite3
from datetime import datetime
db = sqlite3.connect('investigation.db')
now = datetime.utcnow().isoformat()
db.execute('''
    UPDATE leads SET status='dead_end', stop_reason=?, triage_rationale=?,
        triaged_by='agent:triage', triaged_at=?, updated_at=?
    WHERE id=?
''', ('<STOP_REASON>', '<RATIONALE>', now, now, <LEAD_ID>))
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
- Stopped (exhaustively covered / duplicate depth): W
- Held (queue throttle): V
- Reprioritized: U

### Remaining Queue
- N leads still pending triage

### Depth Tier Distribution
| Tier | Count |
|------|-------|
| scan | X |
| standard | Y |
| deep_dive | Z |

### Skill Recommendations
| Skill | Count | Example Targets |
|-------|-------|----------------|
| /deep-investigate | Z | [names] |
| /investigate-person | W | [names] |
| /trace-entity | V | [names] |
| /pursue-lead | U | [names] |

### Thread Balance
| Thread | Active Leads | Findings | Status |
|--------|-------------|----------|--------|
| [name] | X | Y | [balanced/starved/saturated] |

### Deduplication Details
| Lead # | Title | Duplicate Of | Action |
|--------|-------|-------------|--------|
| #1234  | Cross-ref officer: John Smith | #890 | dead_end |

### Priority Changes
| Lead # | Title | Old Priority | New Priority | Reason |
|--------|-------|-------------|-------------|--------|
| #1235  | Cross-ref registry: Example Trust | medium | high | Key person target |

### Links Created
- Lead #1236 ↔ Lead #1237 (shared target: "123 Main St")
```

## Triage Philosophy

### What to Dead-End
- Exact or near-exact duplicates of existing leads
- Cross-refs for well-known public entities (Goldman Sachs, Harvard) with no specific investigation angle
- Address cross-refs for generic addresses (c/o, PO Box, major commercial buildings not in known investigation addresses)

### What to Keep
- Any lead targeting a person with < 3 findings
- Any lead with a financial or corporate angle
- Any lead targeting an entity at a known investigation address (from the profile's known_addresses)
- Cross-refs for officers at 2+ investigation-linked entities

### What to Raise Priority
- Leads connected to financial flow investigation threads
- Leads targeting entities in the corporate architecture under investigation
- Cross-refs that could reveal new lateral connections

## Autonomy Level

The triage agent has **moderate autonomy**:
- CAN dead-end clear duplicates without human approval
- CAN adjust priorities up or down within the range (low ↔ high)
- CAN assign depth_tier (scan, standard, deep_dive)
- CAN assign recommended_skill based on depth_tier + category
- CAN hold leads when thread queues are saturated (30+ active)
- CAN enrich category and target_name fields
- CAN create lead_relations links
- CANNOT set priority to `critical` (reserved for human judgment)
- CANNOT delete leads (only dead_end)
- CANNOT escalate to `deep_dive` without structural evidence (3+ roles/connections or key_person status)

Human reviews dead-ends periodically to catch false positives.

## Context Management

- Use `--output $WORKDIR/...` on all searches
- Process leads in batches of 20 max to keep context manageable
- Record triage decisions as lead notes for audit trail
