#!/usr/bin/env python3
"""Generate curation prompts for dossiers that need narrative content.

Usage:
    uv run python site/pipeline/batch_curate.py --list          # Show dossiers needing curation
    uv run python site/pipeline/batch_curate.py --prompt SLUG   # Print curation prompt for a slug
    uv run python site/pipeline/batch_curate.py --batch N       # Print top N slugs needing curation
"""

import argparse
import json
import os
from pathlib import Path

DOSSIER_DIR = Path("site/content/dossiers")
AGENT_CONTEXT_DIR = Path("site/content/agent-context")
MODELS_DIR = Path("site/content/models")


def get_dossiers_needing_curation():
    """Return list of (slug, name, finding_count) sorted by finding_count desc."""
    results = []
    for f in sorted(DOSSIER_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.loads(f.read_text())
        c = d.get("curation", {})
        if c.get("lead") and c.get("sections"):
            continue
        slug = f.stem
        name = d.get("name", slug)
        findings = len(d.get("findings", []))
        results.append((slug, name, findings))
    results.sort(key=lambda x: -x[2])
    return results


def get_all_slugs():
    """Return set of all dossier slugs for cross-linking reference."""
    slugs = set()
    for f in DOSSIER_DIR.glob("*.json"):
        if not f.name.startswith("_"):
            slugs.add(f.stem)
    return slugs


def get_model_ids():
    """Return list of analytical model IDs."""
    ids = []
    for f in MODELS_DIR.glob("*.json"):
        ids.append(f.stem)
    return sorted(ids)


def generate_prompt(slug: str) -> str:
    """Generate a curation prompt for a given dossier slug."""
    dossier_path = DOSSIER_DIR / f"{slug}.json"
    if not dossier_path.exists():
        raise FileNotFoundError(f"No dossier at {dossier_path}")

    d = json.loads(dossier_path.read_text())
    name = d.get("name", slug)
    c = d.get("curation", {})

    # Get section suggestions
    suggestions = c.get("section_suggestions", [])
    suggestion_text = ""
    for s in suggestions:
        suggestion_text += f"  - {s['id']}: {s['title']} (viz: {s.get('viz', 'null')}, "
        suggestion_text += f"findings: {len(s.get('finding_ids', []))}, "
        suggestion_text += f"conns: {len(s.get('connection_ids', []))})\n"
        suggestion_text += f"    guidance: {s.get('guidance', '')}\n"

    # Get key finding IDs
    key_ids = c.get("key_finding_ids", [])

    # Get findings summary
    findings = d.get("findings", [])
    findings_text = ""
    for f_item in findings[:20]:  # Top 20 findings
        fid = f_item.get("id", "?")
        ftype = f_item.get("type", "?")
        conf = f_item.get("confidence", "?")
        summary = f_item.get("summary", "")[:200]
        evidence = f_item.get("evidence", "")
        is_key = " [KEY]" if fid in key_ids else ""
        findings_text += f"  - Finding #{fid} [{ftype}/{conf}]{is_key}: {summary}\n"
        if evidence:
            findings_text += f"    Evidence: {evidence}\n"

    # Get connections summary
    connections = d.get("connections", [])
    conn_text = ""
    for conn in connections[:20]:
        pa = conn.get("person_a", "?")
        pb = conn.get("person_b", "?")
        ct = conn.get("connection_type", "?")
        strength = conn.get("strength", "?")
        detail = conn.get("detail", "")[:150]
        conn_text += f"  - {pa} <-> {pb} ({ct}, {strength}): {detail}\n"

    # Get entity roles
    entities = d.get("entities", [])
    entity_text = ""
    for ent in entities:
        role = ent.get("role", "?")
        ename = ent.get("entity_name", "?")
        jurisdiction = ent.get("jurisdiction", "?")
        entity_text += f"  - {role} at {ename} ({jurisdiction})\n"

    # Get all slugs for cross-linking
    all_slugs = get_all_slugs()
    slugs_text = ", ".join(sorted(all_slugs))

    # Get model IDs
    model_ids = get_model_ids()
    models_text = ", ".join(model_ids)

    # Read agent context if available
    agent_ctx_path = AGENT_CONTEXT_DIR / f"{slug}.md"
    agent_ctx = ""
    if agent_ctx_path.exists():
        agent_ctx = agent_ctx_path.read_text()

    prompt = f"""You are curating the "{name}" dossier for the Ithildin OSINT investigation site. Generate wiki-style narrative content.

## Agent Context
{agent_ctx}

## Section Suggestions (from automated pipeline)
{suggestion_text}

## Key Finding IDs: {key_ids}

## Findings (top 20)
{findings_text}

## Connections (top 20)
{conn_text}

## Entity Roles
{entity_text}

## Available Dossier Slugs (for cross-linking)
{slugs_text}

## Available Analytical Models
{models_text}

## YOUR TASK

Generate narrative content for this dossier. Write the following fields:

### 1. `lead` (HTML, 2-3 paragraphs using <p> tags)
Wikipedia-style lead section:
- **Standalone** — a reader who only reads the lead understands the subject
- **Encyclopedic tone** — neutral, authoritative, information-dense
- **Specific** — names, amounts, dates, jurisdictions
- **Every claim references evidence** — inline citation tokens only
- Structure: (1) Who/what and why it matters, (2) Most significant facts, (3) Current status/unresolved questions
- Adapt structure to whether this is a person, entity, or event

Citation syntax is REQUIRED:
- Good: `[Finding #2108][EFTA01296686]`
- Good: `[SEC:0000909518-01-000297]` / `[EDGAR:0000909518-01-000297]`
- Bad: `(Finding #2108, EFTA01296686)` (parenthetical citations do not reliably render)
- Bad: plain `Finding #2108` without brackets

### 2. `system_role` (plain text, 1-2 sentences)
What this entity reveals about how the network operates.

### 3. `sections` (array of objects)
Each section: {{"id": "...", "title": "...", "content": "<p>HTML prose...</p>", "viz": "ego_network"|"timeline"|null}}

Rules:
- Use section_suggestions as starting point but rename/merge/skip as needed
- Sections are topical, not categorical ("Key Relationships" not "Relationship Findings")
- Content is PROSE PARAGRAPHS, not bullet lists
- Link to other dossiers: <a href="/dossiers/SLUG">Name</a> (only if slug exists in list above)
- Evidence woven into narrative, not appended
- viz: only set where it contextually supports the section
- Don't repeat the lead — sections go deeper

### 4. `open_questions` (array of 3-5 strings)
Specific, actionable investigative questions based on evidence gaps.

### 5. `applicable_models` (array of strings)
Which analytical models apply, from: {models_text}

## WRITE THE JSON

After composing the content, write it to the dossier using this exact command:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

path = Path('site/content/dossiers/{slug}.json')
dossier = json.loads(path.read_text())

dossier.setdefault('curation', {{}})
dossier['curation']['lead'] = YOUR_LEAD_HTML
dossier['curation']['system_role'] = YOUR_SYSTEM_ROLE
dossier['curation']['sections'] = YOUR_SECTIONS_LIST
dossier['curation']['open_questions'] = YOUR_QUESTIONS_LIST
dossier['curation']['applicable_models'] = YOUR_MODELS_LIST

# Remove old flat fields
for old_field in ['overview', 'financial_summary']:
    dossier['curation'].pop(old_field, None)

path.write_text(json.dumps(dossier, indent=2, default=str))
print('Written successfully')
PY
```

IMPORTANT: Use triple-quoted strings for the HTML content. Escape any quotes properly for JSON.
IMPORTANT: Do NOT use `python -c "..."` to write narrative HTML containing dollar amounts (`$250,000` etc). Shell expansion will corrupt numbers.
IMPORTANT: The content is HTML rendered via set:html — use <p>, <a>, <strong>, <em> tags.
IMPORTANT: Keep sections substantive (2-4 paragraphs each) but focused. Quality over quantity.
IMPORTANT: Do NOT read the full dossier JSON yourself — all the data you need is provided above.
"""
    return prompt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List dossiers needing curation")
    parser.add_argument("--prompt", type=str, help="Generate prompt for a specific slug")
    parser.add_argument("--batch", type=int, help="Print top N slugs needing curation")
    args = parser.parse_args()

    if args.list:
        dossiers = get_dossiers_needing_curation()
        print(f"{len(dossiers)} dossiers need curation:\n")
        for slug, name, count in dossiers:
            print(f"  {slug}: {name} ({count} findings)")
    elif args.prompt:
        print(generate_prompt(args.prompt))
    elif args.batch:
        dossiers = get_dossiers_needing_curation()
        for slug, name, count in dossiers[:args.batch]:
            print(slug)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
