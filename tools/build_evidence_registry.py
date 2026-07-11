#!/usr/bin/env python3
"""Builder: evidence registry (provenance backbone) in epstein_derived.db.

Populates evidence_item + evidence_representation + source_crosswalk from the
immutable corpora. The whole point is `independence_group`: every representation
of the same released page (kabass re-OCR, LMSBAND parse, DOJ original) shares one
group = the EFTA canonical_ref, so downstream corroboration is counted by
distinct underlying page, not by row.

Read-only against source DBs; writes only epstein_derived.db.

Usage:
    uv run python tools/build_evidence_registry.py [--limit N]
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from tools.epstein_derived import (  # noqa: E402
    get_db, attach, init_schema, new_run, source_system_id,
    KABASS_DB, LMSBAND_DB, UNIFIED_DB,
)

# kabass dataset -> the primary releasing body (source_system name).
def release_for_dataset(ds):
    if not ds:
        return "kabasshouse"
    d = ds.lower()
    if d.startswith("dataset") or d.startswith("usavje"):
        return "doj_vol11"
    if d.startswith("images") or "houseoversight" in d or "housejudiciary" in d or d == "congressional":
        return "house_oversight"
    if "fbi" in d:
        return "fbi"
    return "kabasshouse"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="cap kabass docs (testing)")
    args = ap.parse_args()

    db = get_db()
    init_schema(db)
    attach(db, "kab", KABASS_DB)
    attach(db, "lms", LMSBAND_DB)
    attach(db, "uni", UNIFIED_DB)
    run_id = new_run(db, "build_evidence_registry", note="evidence_item + representation + crosswalk")

    ss = {name: source_system_id(db, name) for name in
          ("kabasshouse", "lmsband", "unified", "doj_vol11", "fbi", "house_oversight")}

    # Are kabass file_keys unique? (codex spot-check said yes) — verify, dedupe if not.
    limit_clause = f"LIMIT {args.limit}" if args.limit else ""

    print("registering evidence_items from kabass file_keys ...")
    # One evidence_item per distinct file_key. Pick a representative row (MIN id)
    # for dataset/date. primary_source is derived from the dataset.
    rows = db.execute(f"""
        SELECT file_key, dataset, MIN(id) AS rep_id, MIN(date) AS content_date
        FROM kab.documents
        WHERE file_key IS NOT NULL AND file_key != ''
        GROUP BY file_key {limit_clause}
    """).fetchall()

    ev_items = []
    for r in rows:
        rel = release_for_dataset(r["dataset"])
        ev_items.append((r["file_key"], "page", r["dataset"],
                         ss.get(rel), r["content_date"], run_id))
    db.executemany("""
        INSERT OR IGNORE INTO evidence_item
            (canonical_ref, item_kind, dataset, primary_source_system_id, content_date_raw, created_by_run)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ev_items)
    db.commit()
    n_items = db.execute("SELECT COUNT(*) FROM evidence_item").fetchone()[0]
    print(f"  evidence_item: {n_items:,}")

    # Map canonical_ref -> evidence_item_id for the representation/crosswalk joins.
    print("registering kabass OCR representations ...")
    # Insert one representation per kabass DOC (page-level), independence_group = file_key.
    db.execute(f"""
        INSERT OR IGNORE INTO evidence_representation
            (evidence_item_id, source_system_id, source_native_id, representation_type,
             extraction_model, independence_group)
        SELECT ei.evidence_item_id, {ss['kabasshouse']}, CAST(d.id AS TEXT), 'ocr',
               NULLIF(d.ocr_source,''), d.file_key
        FROM kab.documents d
        JOIN evidence_item ei ON ei.canonical_ref = d.file_key
        {('WHERE d.id IN (SELECT MIN(id) FROM kab.documents GROUP BY file_key)' if False else '')}
    """)
    db.commit()
    n_rep = db.execute("SELECT COUNT(*) FROM evidence_representation").fetchone()[0]
    print(f"  evidence_representation (kabass): {n_rep:,}")

    # Crosswalk LMSBAND: files.filename is 'EFTA00000001.pdf' -> strip extension.
    print("crosswalking LMSBAND -> evidence_item by EFTA filename ...")
    db.execute(f"""
        INSERT OR IGNORE INTO source_crosswalk
            (source_system_id, source_native_id, evidence_item_id, match_method, match_confidence, match_status)
        SELECT {ss['lmsband']}, f.filename, ei.evidence_item_id, 'filename', 1.0, 'accepted'
        FROM lms.files f
        JOIN evidence_item ei ON ei.canonical_ref = REPLACE(f.filename, '.pdf', '')
    """)
    db.commit()
    n_lms = db.execute(f"SELECT COUNT(*) FROM source_crosswalk WHERE source_system_id = {ss['lmsband']}").fetchone()[0]
    print(f"  crosswalk lmsband: {n_lms:,}")

    # Crosswalk UNIFIED documents by doc_id (mix of EFTA + HOUSE_OVERSIGHT ids;
    # only the EFTA-keyed subset will match kabass file_keys — expected).
    print("crosswalking UNIFIED -> evidence_item by doc_id ...")
    db.execute(f"""
        INSERT OR IGNORE INTO source_crosswalk
            (source_system_id, source_native_id, evidence_item_id, match_method, match_confidence, match_status)
        SELECT {ss['unified']}, u.doc_id, ei.evidence_item_id, 'doc_id', 1.0, 'accepted'
        FROM uni.documents u
        JOIN evidence_item ei ON ei.canonical_ref = u.doc_id
    """)
    db.commit()
    n_uni = db.execute(f"SELECT COUNT(*) FROM source_crosswalk WHERE source_system_id = {ss['unified']}").fetchone()[0]
    print(f"  crosswalk unified: {n_uni:,}")

    db.execute("UPDATE derivation_run SET completed_at = CURRENT_TIMESTAMP, record_count = ? WHERE run_id = ?",
               (n_items, run_id))
    db.commit()

    # Independence summary: distinct underlying pages vs total representations.
    groups = db.execute("SELECT COUNT(DISTINCT independence_group) FROM evidence_representation").fetchone()[0]
    print(f"\nindependence groups (distinct underlying pages): {groups:,}")
    print(f"total representations: {n_rep:,}  |  crosswalk edges: {n_lms + n_uni:,}")
    db.close()


if __name__ == "__main__":
    main()
