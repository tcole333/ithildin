#!/usr/bin/env python3
"""Builder: temporal event index (Phase 1) in epstein_derived.db.

Mechanical load of ~54K events from the immutable source corpora into the
`event` / `event_participant` / `event_evidence` tables owned by
tools/epstein_derived.py. Read-only against source DBs; writes only
epstein_derived.db. Does NOT create tables — schema lives in epstein_derived.py.

Sources (kabass unless noted):
  - financial_transactions   -> event_type transaction|flight
  - communication_records    -> event_type call        (JSON rows)
  - investigative_records    -> event_type filing       (JSON rows)
  - curated_docs             -> event_type meeting|document
  - lms.ds09_travel_flights  -> event_type flight        (the real flight legs)

Idempotent: dedupe_key is a stable hash of type|canonical_ref|day|primary_actor,
enforced by a unique index in the schema, so re-running just no-ops via
INSERT OR IGNORE. Commits in batches of ~5000 rows to avoid one giant write lock.

Usage:
    uv run python tools/build_temporal_events.py [--limit N] [--note TEXT]
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from tools.epstein_derived import (  # noqa: E402
    get_db, attach, init_schema, new_run, source_system_id,
    KABASS_DB, LMSBAND_DB,
)
from tools.date_normalize import normalize_date, date_interval, to_epoch_day  # noqa: E402

BATCH_SIZE = 5000

# curated_docs headline/category -> 'meeting' vs 'document'
_MEETING_RE = re.compile(r"meet|visit|dinner|lunch|call|met |gather", re.IGNORECASE)


def _dedupe_key(event_type, canonical_ref, day, primary_actor):
    """Stable hash so re-runs are idempotent via the unique event.dedupe_key index."""
    key = f"{event_type}|{canonical_ref or ''}|{day if day is not None else ''}|{primary_actor or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


class Batcher:
    """Accumulates event + participant + evidence rows and flushes in batches.

    Each flushed event needs its event_id before participant/evidence rows can be
    inserted (AUTOINCREMENT), so events are inserted one at a time within a batch
    but the surrounding transaction is only committed every BATCH_SIZE events —
    this keeps the write lock short without losing per-row event_id linkage.
    """

    def __init__(self, db, run_id, batch_size=BATCH_SIZE):
        self.db = db
        self.run_id = run_id
        self.batch_size = batch_size
        self.n_events = 0
        self.n_participants = 0
        self.n_evidence = 0
        self.n_rejected = 0
        self._since_commit = 0
        self.by_type = {}

    def add(self, event_type, subtype, summary, iso_date, precision, confidence,
            source_system, canonical_ref, participants=None, location=None,
            amount_minor=None, time_local=None, source_locator=None):
        """participants: list of (raw_name, role) tuples; skips falsy raw_name."""
        if not iso_date:
            self.n_rejected += 1
            return None

        lo_iso, hi_iso = date_interval(iso_date, precision)
        start_min, start_max = to_epoch_day(lo_iso), to_epoch_day(hi_iso)
        primary_actor = next((n for n, _ in (participants or []) if n), None)
        dedupe_key = _dedupe_key(event_type, canonical_ref, start_min, primary_actor)

        cur = self.db.execute("""
            INSERT OR IGNORE INTO event
                (event_type, subtype, summary, start_day_min, start_day_max,
                 end_day_min, end_day_max, time_local, date_precision, date_raw,
                 date_parse_method, date_confidence, amount_minor, location,
                 assertion_kind, source_system_id, extraction_run_id, dedupe_key)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, 'date_normalize', ?, ?, ?,
                    'observed', ?, ?, ?)
        """, (event_type, subtype, summary, start_min, start_max, time_local,
              precision, iso_date, confidence, amount_minor, location,
              source_system, self.run_id, dedupe_key))

        if cur.rowcount == 0:
            # Already exists from a prior run (dedupe_key collision) — no-op.
            self._maybe_commit()
            return None

        event_id = cur.lastrowid
        self.n_events += 1
        self.by_type[event_type] = self.by_type.get(event_type, 0) + 1

        for raw_name, role in (participants or []):
            if not raw_name:
                continue
            self.db.execute("""
                INSERT OR IGNORE INTO event_participant (event_id, raw_name, role)
                VALUES (?, ?, ?)
            """, (event_id, raw_name.strip(), role))
            self.n_participants += 1

        if canonical_ref:
            ev_item = self.db.execute(
                "SELECT evidence_item_id FROM evidence_item WHERE canonical_ref = ?",
                (canonical_ref,)
            ).fetchone()
            self.db.execute("""
                INSERT OR IGNORE INTO event_evidence
                    (event_id, evidence_item_id, canonical_ref, source_locator)
                VALUES (?, ?, ?, ?)
            """, (event_id, ev_item[0] if ev_item else None, canonical_ref, source_locator))
            self.n_evidence += 1

        self._maybe_commit()
        return event_id

    def _maybe_commit(self):
        self._since_commit += 1
        if self._since_commit >= self.batch_size:
            self.db.commit()
            self._since_commit = 0

    def flush(self):
        self.db.commit()
        self._since_commit = 0


# ─────────────────────────── source loaders ───────────────────────────

def load_financial_transactions(db, batch, ss_kabass, limit=None):
    """financial_transactions -> transaction (or flight when flight_from set)."""
    limit_clause = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT id, file_key, source_page, transaction_date, amount, currency,
               merchant_name, merchant_raw, merchant_category, location, cardholder,
               description, flight_from, flight_to, flight_carrier, flight_departure,
               flight_ticket, flight_passenger
        FROM kab.financial_transactions
        {limit_clause}
    """).fetchall()

    for r in rows:
        iso, precision = normalize_date(r["transaction_date"])
        if not iso:
            batch.n_rejected += 1
            continue

        canonical_ref = r["file_key"] or r["source_page"]
        is_flight = bool(r["flight_from"])

        amount_minor = None
        if r["amount"] not in (None, ""):
            try:
                amount_minor = int(round(float(r["amount"]) * 100))
            except (TypeError, ValueError):
                amount_minor = None

        participants = []
        if r["cardholder"]:
            participants.append((r["cardholder"], "payer"))
        if is_flight and r["flight_passenger"]:
            participants.append((r["flight_passenger"], "passenger"))

        if is_flight:
            summary = f"{r['flight_carrier'] or 'Flight'} {r['flight_from']} -> {r['flight_to']}".strip()
            event_type = "flight"
        else:
            summary = r["description"] or r["merchant_name"] or r["merchant_raw"]
            event_type = "transaction"

        batch.add(
            event_type=event_type,
            subtype=r["merchant_category"],
            summary=summary,
            iso_date=iso, precision=precision,
            confidence=0.7,
            source_system=ss_kabass,
            canonical_ref=canonical_ref,
            participants=participants,
            location=r["location"] or None,
            amount_minor=amount_minor,
            source_locator=f"financial_transactions.id={r['id']}",
        )


def load_communication_records(db, batch, ss_kabass):
    """communication_records (JSON in `data`) -> call events."""
    rows = db.execute("SELECT rowid, data FROM kab.communication_records").fetchall()
    for r in rows:
        d = json.loads(r["data"])
        iso, precision = normalize_date(d.get("call_date"))
        if not iso:
            batch.n_rejected += 1
            continue

        participants = []
        if d.get("account_name"):
            participants.append((d["account_name"], "subscriber"))
        counterparty = d.get("destination") or d.get("number_called")
        if counterparty:
            participants.append((counterparty, "counterparty"))

        parts = [p for p in (
            d.get("direction"), d.get("provider"),
            f"{d.get('duration_minutes')}min" if d.get("duration_minutes") is not None else None,
        ) if p]
        summary = f"Call: {', '.join(parts)}" if parts else "Call"

        batch.add(
            event_type="call",
            subtype=d.get("record_type"),
            summary=summary,
            iso_date=iso, precision=precision,
            confidence=0.7,
            source_system=ss_kabass,
            canonical_ref=d.get("file_key"),
            participants=participants,
            time_local=d.get("call_time"),
            source_locator=f"communication_records.rowid={r['rowid']}",
        )


def load_investigative_records(db, batch, ss_kabass):
    """investigative_records (JSON in `data`) -> filing events."""
    rows = db.execute("SELECT rowid, data FROM kab.investigative_records").fetchall()
    for r in rows:
        d = json.loads(r["data"])
        iso, precision = normalize_date(d.get("date_start"))
        if not iso:
            batch.n_rejected += 1
            continue

        participants = []
        if d.get("person_name"):
            participants.append((d["person_name"], "participant"))
        if d.get("associated_person"):
            participants.append((d["associated_person"], "participant"))

        parts = [p for p in (d.get("record_type"), d.get("item_description"), d.get("agency")) if p]
        summary = " — ".join(parts) if parts else "Investigative record"

        batch.add(
            event_type="filing",
            subtype=d.get("record_type"),
            summary=summary,
            iso_date=iso, precision=precision,
            confidence=0.7,
            source_system=ss_kabass,
            canonical_ref=d.get("file_key"),
            participants=participants,
            location=d.get("agency"),
            source_locator=f"investigative_records.rowid={r['rowid']}",
        )


def load_curated_docs(db, batch, ss_kabass):
    """curated_docs -> meeting (if headline/category reads as a meeting) else document."""
    rows = db.execute("""
        SELECT id, file_key, doc_date, doc_from, doc_to, headline, category, tier
        FROM kab.curated_docs
    """).fetchall()

    tier_confidence = {"NUCLEAR": 0.9, "CRITICAL": 0.9, "HIGH": 0.75, "MEDIUM": 0.6, "SUPPORTING": 0.5}

    for r in rows:
        iso, precision = normalize_date(r["doc_date"])
        if not iso:
            batch.n_rejected += 1
            continue

        text = f"{r['headline'] or ''} {r['category'] or ''}"
        is_meeting = bool(_MEETING_RE.search(text))

        participants = []
        if r["doc_from"]:
            participants.append((r["doc_from"], "sender"))
        if r["doc_to"]:
            participants.append((r["doc_to"], "recipient"))

        confidence = tier_confidence.get(r["tier"], 0.6)

        batch.add(
            event_type="meeting" if is_meeting else "document",
            subtype=r["category"],
            summary=r["headline"],
            iso_date=iso, precision=precision,
            confidence=confidence,
            source_system=ss_kabass,
            canonical_ref=r["file_key"],
            participants=participants,
            source_locator=f"curated_docs.id={r['id']}",
        )


def load_lms_flights(db, batch, ss_lmsband):
    """lms.ds09_travel_flights -> the real flight legs (kabass financials lack these)."""
    rows = db.execute("""
        SELECT id, efta_id, passenger_name, flight_date, airline, flight_number,
               origin, destination
        FROM lms.ds09_travel_flights
    """).fetchall()

    for r in rows:
        iso, precision = normalize_date(r["flight_date"])
        if not iso:
            batch.n_rejected += 1
            continue

        participants = []
        if r["passenger_name"]:
            participants.append((r["passenger_name"], "passenger"))

        parts = [p for p in (r["airline"], r["flight_number"]) if p]
        route = f"{r['origin'] or '?'} -> {r['destination'] or '?'}"
        summary = f"{' '.join(parts)} {route}".strip()

        batch.add(
            event_type="flight",
            subtype="lms_travel_leg",
            summary=summary,
            iso_date=iso, precision=precision,
            confidence=0.75,
            source_system=ss_lmsband,
            canonical_ref=r["efta_id"],
            participants=participants,
            location=route,
            source_locator=f"ds09_travel_flights.id={r['id']}",
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="cap financial_transactions rows (testing)")
    ap.add_argument("--note")
    args = ap.parse_args()

    db = get_db()
    init_schema(db)
    attach(db, "kab", KABASS_DB)
    attach(db, "lms", LMSBAND_DB)
    run_id = new_run(db, "build_temporal_events", note=args.note or "Phase-1 mechanical event load")

    ss_kabass = source_system_id(db, "kabasshouse")
    ss_lmsband = source_system_id(db, "lmsband")

    batch = Batcher(db, run_id)

    print("loading financial_transactions (transaction|flight) ...")
    load_financial_transactions(db, batch, ss_kabass, limit=args.limit)
    batch.flush()
    print(f"  events so far: {batch.n_events:,}  rejected so far: {batch.n_rejected:,}")

    print("loading communication_records (call) ...")
    load_communication_records(db, batch, ss_kabass)
    batch.flush()
    print(f"  events so far: {batch.n_events:,}  rejected so far: {batch.n_rejected:,}")

    print("loading investigative_records (filing) ...")
    load_investigative_records(db, batch, ss_kabass)
    batch.flush()
    print(f"  events so far: {batch.n_events:,}  rejected so far: {batch.n_rejected:,}")

    print("loading curated_docs (meeting|document) ...")
    load_curated_docs(db, batch, ss_kabass)
    batch.flush()
    print(f"  events so far: {batch.n_events:,}  rejected so far: {batch.n_rejected:,}")

    print("loading lms.ds09_travel_flights (flight) ...")
    load_lms_flights(db, batch, ss_lmsband)
    batch.flush()
    print(f"  events so far: {batch.n_events:,}  rejected so far: {batch.n_rejected:,}")

    db.execute(
        "UPDATE derivation_run SET completed_at = CURRENT_TIMESTAMP, record_count = ? WHERE run_id = ?",
        (batch.n_events, run_id),
    )
    db.commit()

    print(f"\n=== build_temporal_events run #{run_id} complete ===")
    print(f"events inserted:      {batch.n_events:,}")
    print(f"participants inserted:{batch.n_participants:,}")
    print(f"evidence links:       {batch.n_evidence:,}")
    print(f"rejected (bad date):  {batch.n_rejected:,}")
    print("by type:")
    for t, n in sorted(batch.by_type.items(), key=lambda kv: -kv[1]):
        print(f"  {t:<14} {n:>8,}")

    db.close()


if __name__ == "__main__":
    main()
