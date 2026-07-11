---
name: init-investigation
description: Initialize a new investigation profile — create config, seed threads, set active profile
---

# $init-investigation

Bootstrap a new investigation from a subject name or topic. Creates the YAML config, seeds the database, and sets the new profile as active.

## Arguments

- Required: target name or topic (e.g., `$init-investigation "Sam Bankman-Fried"`)
- Optional `--dry-run`: show what would be created without writing files
- No arguments: show current active profile and available profiles

## Process

### 1. Check Existing State

```bash
uv run python tools/investigation_context.py list
```

If an investigation for this subject already exists, confirm whether to switch to it or create a fresh one.

### 2. Generate Profile Name (slug)

Derive a short lowercase slug from the subject name:
- Person: last name or recognizable short form (e.g., `sbf`, `madoff`, `holmes`)
- Organization: abbreviation or short name (e.g., `wirecard`, `theranos`, `enron`)
- Topic: descriptive slug (e.g., `gulf-state-ops`, `crypto-fraud`)

### 3. Create Investigation Directory

```bash
mkdir -p investigations/<slug>
cp investigations/_template/config.yaml investigations/<slug>/config.yaml
```

### 4. Fill In Profile Config

Edit `investigations/<slug>/config.yaml` with:

#### Required Fields
- `name`: the slug
- `primary_subject`: full name of the primary subject
- `description`: 1-2 sentence scope description

#### Key Persons (use your knowledge)
Research and populate `key_persons` with known associates, co-conspirators, key executives, lawyers, enablers. These are names that should trigger priority escalation in auto-lead generation. Use lowercase.

For well-known subjects, you should be able to populate 10-30 key persons from training knowledge. For obscure subjects, start with what's known and note that agents will expand the list during investigation.

#### Known Addresses
Populate `known_addresses` with addresses associated with the subject — offices, residences, properties that appear in public records. Use partial lowercase address patterns as keys.

#### Investigation Threads
Create 3-7 thematic threads that organize the investigation:
- Each thread groups related leads/findings under a theme
- Include `targets` (lowercase names that auto-classify into the thread)
- Include `keywords` (regex patterns for auto-classification)

Thread design principles:
- One thread for the core subject and their direct operations
- One thread per major institutional relationship (e.g., "Banking Pipeline", "Legal Defense", "Political Connections")
- One thread per geographic or thematic cluster (e.g., "Offshore Structures", "Regulatory Actions")
- Threads should be broad enough to absorb many leads, narrow enough to be useful

#### Corpus Tools
Only populate if you know of specific document corpora available for this investigation. Leave empty for most new investigations — the generic tools (EDGAR, FEC, CourtListener, registries) are always available.

#### Key Dates
Populate `key_dates` with significant dates from public knowledge:
- Founding/incorporation dates
- Key financial events
- Legal actions, arrests, indictments
- Media exposés
- Regulatory actions

Categories: `legal`, `financial`, `media`, `operational`, `political`, `milestone`

#### Seed Pillars
Populate `seed_pillars` with the institutional backbone of the network:
- Banks the subject used
- Law firms involved
- Accounting firms
- Government agencies with jurisdiction
- Key companies/organizations

Each pillar needs: `name`, `pillar_type`, `sub_type`, `status`, `significance`

Pillar types: `banking`, `legal`, `accounting`, `government`, `intelligence`, `media`, `philanthropy`, `academia`, `operations`

#### Remaining Fields
- `evidence_id_prefix`: set if there's a known document corpus with canonical IDs
- `exclude_from_graph`: typically the primary subject name
- `source_overrides`: any known media reliability issues

### 5. Set Active Profile

```bash
uv run python tools/investigation_context.py set <slug>
```

### 6. Seed Database

```bash
uv run python tools/lead_tracker.py seed
uv run python tools/event_timeline.py seed
uv run python tools/pillar_tracker.py seed
```

These commands read from the active profile and populate:
- Investigation threads from `threads`
- Key dates from `key_dates`
- Institutional pillars from `seed_pillars`

### 7. Create Initial Leads

Generate 5-10 seed leads to kickstart the investigation:

```bash
uv run python tools/lead_tracker.py add --title "LEAD_TITLE" \
  --description "DESCRIPTION" --priority high --thread-id N
```

Good seed leads:
- Search all corporate registries for the primary subject
- Check EDGAR for SEC filings involving the subject
- Search court records (CourtListener, PACER) for litigation
- Check FEC for political contributions
- Search property records in known jurisdictions
- Trace key corporate entities through registry tools
- Check OFAC/sanctions lists
- Search news/GDELT for media coverage patterns

### 8. Create nested AGENTS.md (optional)

If there's case-specific context that agents need (source reliability notes, corpus-specific search tips, known data quality issues), create:

```
investigations/<slug>/AGENTS.md
```

Codex automatically loads `AGENTS.md` files when working in or below the investigation directory, so the case-specific instructions apply without an explicit read.

### 9. Verify

```bash
uv run python tools/investigation_context.py show
uv run python tools/lead_tracker.py stats
uv run python tools/lead_tracker.py list --status open --limit 10
```

## Output

Print a summary:
- Profile created at `investigations/<slug>/config.yaml`
- N key persons, N known addresses, N threads, N key dates, N seed pillars
- N initial leads created
- Active profile set to `<slug>`
- Next steps: `$pursue-lead` or `$deep-investigate <name>` to begin
