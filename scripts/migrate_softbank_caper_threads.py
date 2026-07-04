#!/usr/bin/env python
"""One-off migration: remap softbank-caper findings/leads from the shared
thread IDs 1-11 (owned by the epstein/tech-right profiles) onto the profile's
own threads, seeded as DB IDs 76-86 via `lead_tracker.py thread seed`.

Mapping is config-thread-number N -> DB id 75+N, verified semantically:
  old 3 = WeWork self-dealing  -> 78 "WeWork Extraction"
  old 8 = WeWork acquisitions  -> 83 "Acquisition Looting"
  old 11 = FTX/Wirecard        -> 86 "Portfolio Fraud Nexus"

Structural FK remap only — no finding CONTENT changes — so it deliberately does
not write to the corrections audit table. Idempotent and reversible (reverse map
is DB id 75+N -> N, but only re-run in reverse if you know no other profile has
claimed 1-11 in the interim). Scoped strictly to profile_id='softbank-caper'.
"""
import sqlite3
import sys

DB = "investigation.db"
PROFILE = "softbank-caper"
# config thread N -> newly seeded DB thread id
OLD_TO_NEW = {n: 75 + n for n in range(1, 12)}


def main():
    apply = "--apply" in sys.argv
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    # Sanity: confirm the 11 destination threads exist and belong to this profile.
    rows = cur.execute(
        "SELECT id FROM investigation_threads WHERE profile_id=? AND id BETWEEN 76 AND 86",
        (PROFILE,),
    ).fetchall()
    dest_ids = {r[0] for r in rows}
    missing = set(OLD_TO_NEW.values()) - dest_ids
    if missing:
        print(f"ABORT: destination threads not found for {PROFILE}: {sorted(missing)}")
        print("Run: uv run python tools/lead_tracker.py thread seed")
        return 1

    for table in ("findings", "leads"):
        print(f"\n== {table} ==")
        total = 0
        for old, new in OLD_TO_NEW.items():
            n = cur.execute(
                f"SELECT count(*) FROM {table} WHERE profile_id=? AND thread_id=?",
                (PROFILE, old),
            ).fetchone()[0]
            if n:
                print(f"  thread {old:>2} -> {new}: {n} rows")
                total += n
            if apply and n:
                cur.execute(
                    f"UPDATE {table} SET thread_id=? WHERE profile_id=? AND thread_id=?",
                    (new, PROFILE, old),
                )
        print(f"  TOTAL {table} remapped: {total}")

    if apply:
        con.commit()
        print("\nCOMMITTED.")
    else:
        print("\nDRY RUN (pass --apply to commit).")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
