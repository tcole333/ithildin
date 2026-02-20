#!/usr/bin/env python3
"""Recover curated prose from git history (commit 05ca6ba).

Commit 05ca6ba added curation prose (lead, sections, system_role, etc.)
to ~122 dossier files. Commit 7a6bcbe stripped those fields. This script
restores only the prose-related curation keys without touching findings,
connections, entities, or viz_data.
"""

import json
import subprocess
import sys
from pathlib import Path

HISTORY_COMMIT = "05ca6ba"
DOSSIER_DIR = Path("content/dossiers")

# Curation keys that carry prose — these are what we want to restore
PROSE_KEYS = {"lead", "sections", "system_role", "open_questions", "applicable_models"}

# Keys we never overwrite from history
PROTECTED_KEYS = {"findings", "connections", "entities", "viz_data", "key_finding_ids", "key_identifiers"}


def get_historical_json(filename: str) -> dict | None:
    """Load a dossier file from the historical commit."""
    git_path = f"content/dossiers/{filename}"
    try:
        result = subprocess.run(
            ["git", "show", f"{HISTORY_COMMIT}:{git_path}"],
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def needs_recovery(current_curation: dict) -> bool:
    """Check if current curation is missing prose fields."""
    for key in PROSE_KEYS:
        val = current_curation.get(key)
        if val and (isinstance(val, str) and val.strip()) or (isinstance(val, list) and len(val) > 0):
            return False
    return True


def main():
    dossier_files = sorted(
        f.name for f in DOSSIER_DIR.glob("*.json")
        if not f.name.startswith("_")
    )
    print(f"Found {len(dossier_files)} dossier files")

    recovered = 0
    skipped = 0
    failed = 0

    for filename in dossier_files:
        filepath = DOSSIER_DIR / filename
        current = json.loads(filepath.read_text())
        current_curation = current.get("curation", {})

        if not needs_recovery(current_curation):
            skipped += 1
            continue

        historical = get_historical_json(filename)
        if not historical:
            failed += 1
            continue

        hist_curation = historical.get("curation", {})
        if not hist_curation.get("lead") and not hist_curation.get("sections"):
            skipped += 1
            continue

        # Merge prose keys from history into current curation
        merged_curation = dict(current_curation)
        for key in PROSE_KEYS:
            hist_val = hist_curation.get(key)
            if hist_val:
                merged_curation[key] = hist_val

        # Also restore curated_at if it was in history
        if "curated_at" in hist_curation:
            merged_curation["curated_at"] = hist_curation["curated_at"]

        current["curation"] = merged_curation
        filepath.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n")
        recovered += 1
        print(f"  Recovered: {filename}")

    print(f"\nRecovered prose for {recovered} of {len(dossier_files)} dossiers")
    print(f"  Skipped (already had prose or no history): {skipped}")
    print(f"  Failed (not in history): {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
