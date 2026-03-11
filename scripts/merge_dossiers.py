#!/usr/bin/env python3
"""Merge duplicate dossiers into canonical entries.

Combines findings, connections, entities, and metadata from source dossiers
into a canonical target. Adds redirects and updates the index.

Usage:
    python scripts/merge_dossiers.py plan          # Show what will be merged
    python scripts/merge_dossiers.py execute       # Perform merges
    python scripts/merge_dossiers.py execute --dry-run  # Show without writing
"""

import json
import sys
from pathlib import Path

CONTENT_DIR = Path(__file__).parent.parent / "content" / "dossiers"
INDEX_PATH = CONTENT_DIR / "_index.json"
REDIRECTS_PATH = CONTENT_DIR / "_redirects.json"

# (canonical_slug, [source_slugs_to_merge_in])
MERGE_PLAN = [
    ("anduril-industries", ["anduril-industries-llc"]),
    ("d-wave-quantum", ["d-wave"]),
    ("doge", ["doge-operations", "doge-personnel", "department-of-government-efficiency-doge"]),
    ("gd-culture-group", ["gd-culture-group-gdc"]),
    ("greenmet", ["greenmet-greentech-minerals-holdings-inc"]),
    ("mgx", ["mgx-fund-management-limited"]),
    ("palantir-technologies", ["palantir"]),
    ("red-planet-ventures", ["red-planet-ventures-i-llc"]),
    ("softbank-group", ["softbank", "softbank-group-masayoshi-son"]),
    ("world-liberty-financial", ["world-liberty-financial-inc"]),
    ("zachary-witkoff", ["zach-witkoff"]),
]


def load_dossier(slug: str) -> dict | None:
    path = CONTENT_DIR / f"{slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def merge_dossier(target: dict, source: dict) -> dict:
    """Merge source dossier data into target."""
    # Merge findings by ID
    existing_ids = {f["id"] for f in target.get("findings", [])}
    for f in source.get("findings", []):
        if f["id"] not in existing_ids:
            target["findings"].append(f)
            existing_ids.add(f["id"])

    # Merge connections (dedup by other_person + relationship_type)
    existing_conns = {
        (c.get("other_person"), c.get("relationship_type"))
        for c in target.get("connections", [])
    }
    for c in source.get("connections", []):
        key = (c.get("other_person"), c.get("relationship_type"))
        if key not in existing_conns:
            target["connections"].append(c)
            existing_conns.add(key)

    # Merge entities (dedup by name + jurisdiction)
    existing_entities = {
        (e.get("name"), e.get("jurisdiction"))
        for e in target.get("entities", [])
    }
    for e in source.get("entities", []):
        key = (e.get("name"), e.get("jurisdiction"))
        if key not in existing_entities:
            target["entities"].append(e)
            existing_entities.add(key)

    # Merge timeline events (dedup by date + summary)
    existing_events = {
        (t.get("date"), t.get("summary", t.get("description", "")))
        for t in target.get("timeline", [])
    }
    for t in source.get("timeline", []):
        key = (t.get("date"), t.get("summary", t.get("description", "")))
        if key not in existing_events:
            target["timeline"].append(t)
            existing_events.add(key)

    # Merge profile_ids
    target_profiles = set(target.get("profile_ids", []))
    for pid in source.get("profile_ids", []):
        target_profiles.add(pid)
    target["profile_ids"] = sorted(target_profiles)

    # Merge aliases
    target_aliases = set(target.get("aliases", []))
    # Add source name as alias if different from target name
    if source.get("name") and source["name"] != target["name"]:
        target_aliases.add(source["name"])
    for a in source.get("aliases", []):
        if a and a != target["name"]:
            target_aliases.add(a)
    target["aliases"] = sorted(target_aliases)

    # Recalculate stats
    target["stats"] = {
        "total_findings": len(target.get("findings", [])),
        "total_connections": len(target.get("connections", [])),
        "total_entities": len(target.get("entities", [])),
    }

    return target


def cmd_plan():
    print("MERGE PLAN")
    print("=" * 70)
    for canonical, sources in MERGE_PLAN:
        target = load_dossier(canonical)
        if not target:
            print(f"\n  SKIP {canonical}: file not found")
            continue
        tf = target.get("stats", {}).get("total_findings", 0)
        tc = target.get("stats", {}).get("total_connections", 0)
        print(f"\n  {canonical} ({tf}f {tc}c) <-- canonical")
        for src_slug in sources:
            src = load_dossier(src_slug)
            if not src:
                print(f"    + {src_slug}: FILE NOT FOUND (skip)")
                continue
            sf = src.get("stats", {}).get("total_findings", 0)
            sc = src.get("stats", {}).get("total_connections", 0)
            print(f"    + {src_slug} ({sf}f {sc}c)")

    total_sources = sum(len(s) for _, s in MERGE_PLAN)
    print(f"\n{len(MERGE_PLAN)} merges, {total_sources} source dossiers to absorb")


def cmd_execute(dry_run: bool = False):
    index = json.loads(INDEX_PATH.read_text())
    redirects = {}
    if REDIRECTS_PATH.exists():
        redirects = json.loads(REDIRECTS_PATH.read_text())

    merged_count = 0
    removed_slugs = set()

    for canonical, sources in MERGE_PLAN:
        target = load_dossier(canonical)
        if not target:
            print(f"SKIP {canonical}: not found")
            continue

        before_f = target.get("stats", {}).get("total_findings", 0)
        any_merged = False

        for src_slug in sources:
            src = load_dossier(src_slug)
            if not src:
                print(f"  SKIP {src_slug}: not found")
                continue

            sf = src.get("stats", {}).get("total_findings", 0)
            target = merge_dossier(target, src)
            redirects[src_slug] = canonical
            removed_slugs.add(src_slug)
            any_merged = True
            print(f"  {src_slug} ({sf}f) -> {canonical}")

        if any_merged:
            after_f = target["stats"]["total_findings"]
            print(f"  {canonical}: {before_f}f -> {after_f}f")

            if not dry_run:
                # Write merged target
                target_path = CONTENT_DIR / f"{canonical}.json"
                target_path.write_text(json.dumps(target, indent=2, default=str))

                # Delete source files
                for src_slug in sources:
                    src_path = CONTENT_DIR / f"{src_slug}.json"
                    if src_path.exists():
                        src_path.unlink()

            merged_count += 1

    # Update index: remove merged-away entries
    if not dry_run:
        # Rebuild index entry for canonical slugs (stats may have changed)
        index_by_slug = {e["slug"]: e for e in index}
        for canonical, sources in MERGE_PLAN:
            target = load_dossier(canonical) if not dry_run else None
            if target and canonical in index_by_slug:
                index_by_slug[canonical]["total_findings"] = target["stats"]["total_findings"]

        new_index = [e for e in index if e["slug"] not in removed_slugs]
        INDEX_PATH.write_text(json.dumps(new_index, indent=2, default=str))

        # Write redirects
        REDIRECTS_PATH.write_text(json.dumps(redirects, indent=2))

    # Update cross-references in all remaining dossiers
    redirect_map = {src: canon for canon, srcs in MERGE_PLAN for src in srcs}
    xref_updates = 0
    if not dry_run:
        for p in sorted(CONTENT_DIR.glob("*.json")):
            if p.name.startswith("_"):
                continue
            d = json.loads(p.read_text())
            changed = False

            # Fix connection slugs
            for c in d.get("connections", []):
                old = c.get("other_person_slug", "")
                if old in redirect_map:
                    c["other_person_slug"] = redirect_map[old]
                    changed = True
                    xref_updates += 1

            # Fix href links in curation HTML
            curation = d.get("curation", {})
            for field in ("lead", "overview", "financial_summary"):
                val = curation.get(field, "")
                if not val:
                    continue
                for src, canon in redirect_map.items():
                    old_href = f"/dossiers/{src}"
                    new_href = f"/dossiers/{canon}"
                    if old_href in val:
                        val = val.replace(old_href, new_href)
                        changed = True
                        xref_updates += 1
                curation[field] = val

            for section in curation.get("sections", []):
                content = section.get("content", "")
                for src, canon in redirect_map.items():
                    old_href = f"/dossiers/{src}"
                    new_href = f"/dossiers/{canon}"
                    if old_href in content:
                        content = content.replace(old_href, new_href)
                        changed = True
                        xref_updates += 1
                section["content"] = content

            if changed:
                p.write_text(json.dumps(d, indent=2, default=str))

    action = "Would remove" if dry_run else "Removed"
    print(f"\n{merged_count} merges completed. {action} {len(removed_slugs)} duplicate dossiers.")
    print(f"Cross-reference updates: {xref_updates}")
    print(f"Redirects: {len(redirects)} total")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/merge_dossiers.py {plan|execute} [--dry-run]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "plan":
        cmd_plan()
    elif cmd == "execute":
        dry_run = "--dry-run" in sys.argv
        cmd_execute(dry_run=dry_run)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
