#!/usr/bin/env python3
"""Read-only audit of profile <-> thread ownership drift in investigation.db.

Background
----------
`findings`, `leads`, and `connections` each carry a GLOBAL `thread_id`
(FK -> investigation_threads.id) *and* a `profile_id`. But investigation
profiles number their threads LOCALLY in `investigations/<name>/config.yaml`
(config thread id 1..N). When a profile's config-local ids overlap the global
ids another profile already owns (classically epstein's global threads 1-8),
records written with a config-local `thread_id` land on the WRONG profile's
thread. `findings.profile_id` and `leads.profile_id` both DEFAULT 'epstein',
so records created without an explicit profile silently inherit epstein too.

This tool REPORTS that drift. It is strictly read-only: it never writes to the
database. It emits both a human-readable summary and (with --json) a machine
report including a proposed remap table with per-record evidence.

Key finding baked into the evidence model
------------------------------------------
Empirically (see research/profile-thread-audit.md) the record's OWN
`profile_id` is the reliable owner in essentially every mismatch: the finding
was self-tagged with the correct profile but written on a colliding
config-local `thread_id`. So the correct remediation is a THREAD remap
(re-home config-local threads onto the profile's own global threads, exactly
like scripts/migrate_softbank_caper_threads.py did), NOT a profile_id rewrite.
The proposed "corrected profile_id" this tool emits is therefore the record's
existing profile_id whenever that is corroborated; the drift is quantified so a
human can decide the re-threading. Reverse/ambiguous cases (record.profile_id
disagreeing with strong thread+sibling signal) are flagged NEEDS-REVIEW.

Usage:
    uv run python scripts/audit_profile_threads.py                 # full summary
    uv run python scripts/audit_profile_threads.py --profile nginx # one profile
    uv run python scripts/audit_profile_threads.py --json          # JSON to stdout
    uv run python scripts/audit_profile_threads.py --json --output report.json

Consistent with:
    tools/lead_tracker.py (~line 906 startup backfill) — derives the tech-right
        thread list dynamically from investigation_threads rather than a
        hardcoded tuple; we do the same (never hardcode thread windows).
    scripts/migrate_softbank_caper_threads.py — config-local N -> global id
        remap, structural FK only, no content/corrections writes.
    tools/fix_null_profiles.py — NULL profile_id repair via active profile.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "investigation.db"
INVESTIGATIONS_DIR = PROJECT_ROOT / "investigations"

sys.path.insert(0, str(PROJECT_ROOT))

# Reuse the canonical config loader so we read thread declarations exactly the
# way the rest of the platform does (investigation_context.load_profile).
try:
    from tools.investigation_context import list_profiles, load_profile
    from tools.output_util import add_output_args, write_output
except Exception:  # pragma: no cover - fallback if import path differs
    list_profiles = None
    load_profile = None
    add_output_args = None
    write_output = None

# The column default for both findings.profile_id and leads.profile_id. A record
# sitting at this value on a thread owned by another profile is indistinguishable
# from "never set a profile" — that is the silent-default footgun.
DEFAULT_PROFILE = "epstein"


def _skey(v):
    """Type-safe sort key: some legacy leads.thread_id rows are stored TEXT, not
    INTEGER, so a raw sorted() over mixed int/str thread ids raises TypeError.
    Sort by (is-not-int, int-value-or-0, str) to keep a stable total order."""
    try:
        return (0, int(v), "")
    except (TypeError, ValueError):
        return (1, 0, str(v))


def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    # Read-only usage; WAL + busy_timeout keeps us safe alongside live writers.
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


# ── config-declared threads ──────────────────────────────────────────────

def load_declared_threads() -> dict:
    """Return {profile_name: {"declared_ids": [...], "names": {id: name}}}.

    Uses investigation_context.load_profile when available (canonical), else
    falls back to a minimal YAML scan. These are the CONFIG-LOCAL ids.
    """
    out: dict = {}
    if load_profile is not None and list_profiles is not None:
        for p in list_profiles():
            name = p.get("name")
            if not name or "error" in p:
                continue
            try:
                prof = load_profile(name)
            except Exception:
                continue
            ids, names = [], {}
            for t in prof.threads:
                tid = t.get("id")
                if tid is None:
                    continue
                ids.append(tid)
                names[tid] = t.get("name", "")
            out[name] = {"declared_ids": sorted(ids), "names": names}
        return out

    # Fallback: crude YAML scan (only used if imports fail entirely).
    import re

    for cfg in sorted(INVESTIGATIONS_DIR.glob("*/config.yaml")):
        name = cfg.parent.name
        if name == "_template":
            continue
        ids = [int(m) for m in re.findall(r"^\s+-\s+id:\s*(\d+)", cfg.read_text(), re.M)]
        out[name] = {"declared_ids": sorted(set(ids)), "names": {}}
    return out


def thread_profile_map(db: sqlite3.Connection) -> dict:
    """{thread_id: profile_id} as the DB currently records ownership."""
    rows = db.execute("SELECT id, profile_id FROM investigation_threads").fetchall()
    return {r["id"]: r["profile_id"] for r in rows}


# ── mismatch / null detection ────────────────────────────────────────────

_MISMATCH_SQL = """
    SELECT r.id            AS record_id,
           r.thread_id     AS thread_id,
           r.profile_id    AS record_profile,
           t.profile_id    AS thread_profile,
           t.title         AS thread_title,
           {label_expr}    AS label
    FROM {table} r
    JOIN investigation_threads t ON r.thread_id = t.id
    WHERE COALESCE(r.profile_id, '') <> COALESCE(t.profile_id, '')
      AND r.profile_id IS NOT NULL
    ORDER BY r.id
"""

# Per-table human-readable label column (for evidence snippets).
_LABEL_EXPR = {
    "findings": "substr(COALESCE(r.target_name,'') || ' — ' || COALESCE(r.summary,''), 1, 140)",
    "leads": "substr(COALESCE(r.title,'') || ' — ' || COALESCE(r.description,''), 1, 140)",
}


def fetch_mismatches(db: sqlite3.Connection, table: str) -> list:
    sql = _MISMATCH_SQL.format(table=table, label_expr=_LABEL_EXPR[table])
    return [dict(r) for r in db.execute(sql).fetchall()]


def fetch_connection_mismatches(db: sqlite3.Connection) -> list:
    """Connections carry their own profile_id but derive from a finding.

    A connection whose profile_id disagrees with its source finding's
    profile_id is drifted. Standalone connections (finding_id NULL) can only be
    checked against their own thread-less profile, so we scope to those with a
    finding_id — the auditable subset.
    """
    sql = """
        SELECT c.id           AS record_id,
               c.finding_id   AS finding_id,
               c.profile_id   AS record_profile,
               f.profile_id   AS finding_profile,
               substr(COALESCE(c.person_a,'') || ' <-> ' || COALESCE(c.person_b,'')
                      || ' (' || COALESCE(c.relationship_type,'') || ')', 1, 140) AS label
        FROM connections c
        JOIN findings f ON c.finding_id = f.id
        WHERE COALESCE(c.profile_id, '') <> COALESCE(f.profile_id, '')
        ORDER BY c.id
    """
    return [dict(r) for r in db.execute(sql).fetchall()]


def fetch_nulls(db: sqlite3.Connection, table: str) -> dict:
    """NULL-profile records, split by whether a thread lets us infer an owner."""
    has_thread = db.execute(
        f"""SELECT r.id AS record_id, r.thread_id AS thread_id, t.profile_id AS thread_profile
            FROM {table} r LEFT JOIN investigation_threads t ON r.thread_id = t.id
            WHERE r.profile_id IS NULL AND r.thread_id IS NOT NULL"""
    ).fetchall()
    no_thread = db.execute(
        f"SELECT COUNT(*) AS n FROM {table} WHERE profile_id IS NULL AND thread_id IS NULL"
    ).fetchone()["n"]
    return {
        "with_thread": [dict(r) for r in has_thread],
        "without_thread_count": no_thread,
    }


# ── evidence & proposal ──────────────────────────────────────────────────

def _sibling_majority_profile(db: sqlite3.Connection, table: str, thread_id: int) -> tuple:
    """Dominant profile_id among OTHER records on the same thread.

    Returns (profile, share, total) where share is the fraction of records on
    that thread carrying the dominant non-null profile. This is a corroborating
    signal, not the primary one — a config-local thread that many profiles
    collided on will have a mixed population.
    """
    rows = db.execute(
        f"""SELECT profile_id, COUNT(*) AS n FROM {table}
            WHERE thread_id = ? AND profile_id IS NOT NULL
            GROUP BY profile_id ORDER BY n DESC""",
        (thread_id,),
    ).fetchall()
    total = sum(r["n"] for r in rows)
    if not rows or total == 0:
        return (None, 0.0, 0)
    top = rows[0]
    return (top["profile_id"], round(top["n"] / total, 3), total)


def build_proposal(db: sqlite3.Connection, table: str, mismatches: list) -> list:
    """For each mismatched record, propose a corrected profile_id + evidence.

    Evidence weighing (see module docstring):
      1. record.profile_id — the record self-tagged an owner (primary signal).
      2. thread.profile_id — who the DB says owns the thread.
      3. sibling majority   — dominant profile of other records on the thread.

    Because config-local thread collisions mean the THREAD is the stale field,
    we propose corrected_profile = record.profile_id when signal 1 is
    corroborated by either the record NOT being at the silent default, or by the
    sibling majority agreeing. When record.profile_id is the bare default
    'epstein' AND the thread is genuinely epstein-owned in config, there is no
    real drift; those never reach here (equal profiles are filtered out). The
    residual ambiguous case — record.profile_id present but contradicted by a
    strong sibling majority for a DIFFERENT profile — is flagged review.
    """
    proposals = []
    for m in mismatches:
        rp = m["record_profile"]
        tp = m["thread_profile"]
        sib_profile, sib_share, sib_total = _sibling_majority_profile(db, table, m["thread_id"])

        # Two drift classes, distinguished by whether the record's own profile_id
        # is corroborated or contested. The corrected owner is ALWAYS the
        # record's own profile_id — an automated audit must never assert a
        # profile_id FLIP, because deciding the true owner of a contested record
        # requires reading its content (which sibling-share cannot do). We only
        # raise or lower confidence.
        #
        #  (A) SAFE-AUTO config-local collision — record.profile_id is right, the
        #      thread_id is a config-local id colliding with another profile's
        #      global thread. Remediation = THREAD remap (not a profile change).
        #
        #  (B) NEEDS-REVIEW contested tag — the thread is a high-purity home for a
        #      DIFFERENT profile and this record is the outlier, so the record's
        #      profile_id MIGHT be wrong (genuinely mis-profiled) OR the thread
        #      might just be huge (epstein thread 1 has 2500+ records, so its 94%
        #      share swamps any collision victim). A human must read the record to
        #      decide. We flag it but do NOT flip; proposed stays record.profile_id.
        corrected = rp
        contested = (
            sib_profile is not None and sib_profile == tp and sib_share >= 0.9
        )
        if contested:
            confidence = "needs-review"
            reasons = [
                f"record.profile_id='{rp}' but the record is an OUTLIER on thread "
                f"{m['thread_id']}, which is {sib_share:.0%} '{tp}' "
                f"({sib_total} profiled records)",
                f"AMBIGUOUS: could be genuinely mis-profiled (true owner '{tp}') "
                f"OR a config-local collision victim on a large '{tp}' thread — "
                f"read content to decide; NOT auto-remapped",
            ]
        else:
            confidence = "safe-auto"
            reasons = [f"record.profile_id='{rp}' (record self-tags its owner)"]
            if sib_profile == rp:
                reasons.append(
                    f"sibling majority on thread {m['thread_id']} agrees "
                    f"({sib_share:.0%} of {sib_total} profiled records = '{rp}')"
                )
            else:
                reasons.append(
                    f"thread {m['thread_id']} owned by '{tp}' (config-local id "
                    f"collision — thread is the stale field, not profile_id)"
                )

        proposals.append(
            {
                "table": table,
                "record_id": m["record_id"],
                "thread_id": m["thread_id"],
                "current_profile_id": rp,
                "thread_profile_id": tp,
                "proposed_profile_id": corrected,
                "changes_profile_id": corrected != rp,  # ~always False by design
                "classification": confidence,
                "label": m.get("label", ""),
                "evidence": reasons,
            }
        )
    return proposals


# ── per-profile aggregation ──────────────────────────────────────────────

def aggregate(db: sqlite3.Connection) -> dict:
    declared = load_declared_threads()
    tmap = thread_profile_map(db)

    # threads each profile ACTUALLY uses (records live there) vs DECLARED (config)
    actual: dict = {}
    for table in ("findings", "leads"):
        for r in db.execute(
            f"""SELECT profile_id, thread_id, COUNT(*) AS n FROM {table}
                WHERE profile_id IS NOT NULL AND thread_id IS NOT NULL
                GROUP BY profile_id, thread_id"""
        ).fetchall():
            actual.setdefault(r["profile_id"], {}).setdefault(r["thread_id"], 0)
            actual[r["profile_id"]][r["thread_id"]] += r["n"]

    f_mis = fetch_mismatches(db, "findings")
    l_mis = fetch_mismatches(db, "leads")
    f_prop = build_proposal(db, "findings", f_mis)
    l_prop = build_proposal(db, "leads", l_mis)
    all_prop = f_prop + l_prop

    # Bucket proposals by the record's CURRENT profile_id — i.e. "the mismatch
    # set for profile X" is every drifted record currently tagged X, which is
    # what a reviewer scopes to. Within the bucket we track how many proposals
    # would KEEP the tag (config-local collision: re-thread only) vs FLIP it
    # (record was genuinely mis-profiled).
    by_profile: dict = {}
    for p in all_prop:
        owner = p["current_profile_id"]
        b = by_profile.setdefault(
            owner,
            {
                "profile_id": owner,
                "findings_mismatch": 0,
                "leads_mismatch": 0,
                "safe_auto": 0,
                "needs_review": 0,
                "declared_thread_ids": declared.get(owner, {}).get("declared_ids", []),
                "db_thread_ids": sorted(
                    [tid for tid, pr in tmap.items() if pr == owner], key=_skey
                ),
                "actual_thread_ids_used": sorted(
                    (actual.get(owner) or {}).keys(), key=_skey
                ),
                "colliding_thread_ids": sorted(
                    {p2["thread_id"] for p2 in all_prop if p2["current_profile_id"] == owner},
                    key=_skey,
                ),
                "sample_records": [],
            },
        )
        if p["table"] == "findings":
            b["findings_mismatch"] += 1
        else:
            b["leads_mismatch"] += 1
        if p["classification"] == "safe-auto":
            b["safe_auto"] += 1
        else:
            b["needs_review"] += 1
        if len(b["sample_records"]) < 3:
            b["sample_records"].append(
                {
                    "table": p["table"],
                    "record_id": p["record_id"],
                    "thread_id": p["thread_id"],
                    "proposed_profile_id": p["proposed_profile_id"],
                    "label": p["label"],
                    "classification": p["classification"],
                }
            )

    # Profile-level verdict. A profile's mismatch set is SAFE-AUTO only when
    # every record is a pure config-local collision (record.profile_id trusted,
    # re-thread only) — i.e. no record's profile tag is contested.
    for b in by_profile.values():
        b["profile_classification"] = (
            "SAFE-AUTO" if b["needs_review"] == 0 else "NEEDS-REVIEW"
        )
        # Does the profile's config declaration collide with epstein's global 1-8?
        # (the canonical drift generator). Informational.
        decl = set(b["declared_thread_ids"])
        dbids = set(b["db_thread_ids"])
        b["config_local_collision"] = bool(decl & set(range(1, 9))) and decl != dbids

    conn_mis = fetch_connection_mismatches(db)
    nulls = {
        "findings": fetch_nulls(db, "findings"),
        "leads": fetch_nulls(db, "leads"),
        "connections": {
            "null_count": db.execute(
                "SELECT COUNT(*) AS n FROM connections WHERE profile_id IS NULL"
            ).fetchone()["n"]
        },
    }

    return {
        "totals": {
            "findings_mismatch": len(f_mis),
            "leads_mismatch": len(l_mis),
            "connection_finding_mismatch": len(conn_mis),
            "findings_null": len(nulls["findings"]["with_thread"])
            + nulls["findings"]["without_thread_count"],
            "leads_null": len(nulls["leads"]["with_thread"])
            + nulls["leads"]["without_thread_count"],
            "leads_null_without_thread": nulls["leads"]["without_thread_count"],
            "connections_null": nulls["connections"]["null_count"],
        },
        "by_profile": by_profile,
        "null_records": nulls,
        "connection_mismatches": conn_mis,
        "proposals": all_prop,
    }


# ── rendering ─────────────────────────────────────────────────────────────

def render_summary(report: dict, profile_filter: str | None) -> str:
    t = report["totals"]
    lines = []
    lines.append("=" * 72)
    lines.append("PROFILE <-> THREAD OWNERSHIP AUDIT (read-only)")
    lines.append("=" * 72)
    lines.append("")
    lines.append("TOTALS")
    lines.append(f"  findings profile/thread mismatch : {t['findings_mismatch']}")
    lines.append(f"  leads    profile/thread mismatch : {t['leads_mismatch']}")
    lines.append(f"  connection/finding mismatch      : {t['connection_finding_mismatch']}")
    lines.append(f"  findings NULL profile_id         : {t['findings_null']}")
    lines.append(
        f"  leads    NULL profile_id         : {t['leads_null']} "
        f"({t['leads_null_without_thread']} have no thread -> cannot infer)"
    )
    lines.append(f"  connections NULL profile_id      : {t['connections_null']}")
    lines.append("")

    profiles = report["by_profile"]
    names = sorted(profiles, key=lambda k: -(profiles[k]["findings_mismatch"] + profiles[k]["leads_mismatch"]))
    if profile_filter:
        names = [n for n in names if n == profile_filter]

    lines.append("PER-PROFILE MISMATCH (owner inferred from record.profile_id)")
    lines.append("-" * 72)
    for n in names:
        b = profiles[n]
        verdict = b["profile_classification"]
        lines.append(
            f"  {n:<18} {verdict:<13} "
            f"findings={b['findings_mismatch']:<4} leads={b['leads_mismatch']:<4} "
            f"(safe-remap={b['safe_auto']}, contested={b['needs_review']})"
        )
        lines.append(
            f"    declared threads (config-local): {b['declared_thread_ids']}"
        )
        lines.append(f"    DB-owned threads (global)      : {b['db_thread_ids']}")
        lines.append(f"    records currently sit on threads: {b['colliding_thread_ids']}")
        if b["config_local_collision"]:
            lines.append(
                "    ! config-local ids overlap global epstein threads 1-8 "
                "(drift generator)"
            )
        for s in b["sample_records"]:
            lines.append(
                f"      e.g. {s['table'][:4]}#{s['record_id']} (thread {s['thread_id']}, "
                f"{s['classification']}): {s['label'][:80]}"
            )
        lines.append("")

    if not profile_filter:
        lines.append("CONNECTION/FINDING PROFILE MISMATCHES")
        lines.append("-" * 72)
        if report["connection_mismatches"]:
            for c in report["connection_mismatches"][:20]:
                lines.append(
                    f"  conn#{c['record_id']} (from finding {c['finding_id']}): "
                    f"conn='{c['record_profile']}' vs finding='{c['finding_profile']}' "
                    f"| {c['label'][:70]}"
                )
        else:
            lines.append("  (none)")
        lines.append("")

    lines.append("REMEDIATION NOTE")
    lines.append("-" * 72)
    lines.append(
        "  In every mismatch the record's OWN profile_id is the reliable owner;\n"
        "  the thread_id is the config-local collision. The correct fix is a\n"
        "  THREAD re-map (config-local id -> the profile's global thread id), as in\n"
        "  scripts/migrate_softbank_caper_threads.py — NOT a profile_id rewrite.\n"
        "  This tool is read-only; apply any remap through an audited path\n"
        "  (findings_tracker corrections / a reviewed migration script), never a\n"
        "  bare UPDATE (direct UPDATE on findings is hook-blocked)."
    )
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--profile", help="Restrict summary to a single profile")
    if add_output_args is not None:
        add_output_args(parser)
    else:  # pragma: no cover
        parser.add_argument("--json", action="store_true", dest="json_out")
        parser.add_argument("--output", metavar="FILE")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: database not found at {DB_PATH}", file=sys.stderr)
        return 1

    db = get_db()
    try:
        report = aggregate(db)
    finally:
        db.close()

    if getattr(args, "profile", None):
        report["filtered_profile"] = args.profile

    # --output FILE: write JSON, print 1-line summary (platform convention).
    if write_output is not None and write_output(
        report, args, summary="profile/thread audit"
    ):
        return 0

    if getattr(args, "json_out", False):
        print(json.dumps(report, indent=2, default=str))
        return 0

    print(render_summary(report, getattr(args, "profile", None)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
