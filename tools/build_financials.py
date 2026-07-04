#!/usr/bin/env python3
"""Builder: normalized financial model in epstein_derived.db.

Reads the immutable corpora (kabasshouse re-OCR + LMSBAND typed extraction) and
populates the financial tables owned by tools/epstein_derived.py:
  merchant, financial_transaction, balance_snapshot, position_snapshot,
  security, financial_statement, fin_flight.

Design contract:
  * Read-only against source DBs. Writes ONLY epstein_derived.db.
  * Never CREATE TABLE (schema owned by epstein_derived.py). init_schema only.
  * Amounts are signed INTEGER minor units (cents). raw_amount always preserved.
  * Idempotent: UNIQUE(source_system_id, source_native_id) + INSERT OR IGNORE.
    Re-running rebuilds derived flags/dedupe in place (delete-and-reinsert per
    source-owned table) without touching source data.
  * Outliers are FLAGGED (is_outlier=1), never dropped: the -99999 OCR sentinel
    family, |amount| > $50M, absurd cost_basis > 1e12.
  * evidence_item_id is set by joining evidence_item on canonical_ref = EFTA.
    Rows whose EFTA is absent from evidence_item leave it NULL.

Usage:
    uv run python tools/build_financials.py [--limit N] [--stage STAGE ...]
      stages: merchants transactions balances positions statements flights all
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from tools.epstein_derived import (  # noqa: E402
    get_db, attach, init_schema, new_run, source_system_id,
    KABASS_DB, LMSBAND_DB,
)
from tools.parse_ds10_financials import (  # noqa: E402
    parse_dollar_amount, clean_entity_name,
)
from tools.date_normalize import normalize_date, to_epoch_day  # noqa: E402

# ── outlier thresholds (minor units unless noted) ─────────────────────────────
OUTLIER_ABS_MINOR = 50_000_000 * 100      # |amount| > $50M
COST_BASIS_ABSURD_MINOR = int(1e12 * 100)  # cost_basis > $1e12
# SQLite stores signed 64-bit ints; OCR garbage like 5.17e+33 overflows when
# scaled to cents. Such values are already outliers — keep the flag, null the int.
_INT64_MAX = 2**63 - 1
# The OCR sentinel family: 99999.xx / 999999.xx (all-nines placeholder).
_SENTINEL_RE = re.compile(r"^-?9{4,6}(\.\d+)?$")

# Statement-marker merchant names that are NOT real spend. Matched
# case-insensitively as a prefix so OCR tails ("Check Paid ...") still hit.
STRUCTURAL_MERCHANT_PREFIXES = [
    "beginning balance", "ending balance", "interest payment", "interest paid",
    "interest", "deposit", "check paid", "check payment", "check",
    "internal funds transfer", "internal transfer", "fedwire debit",
    "fedwire credit", "book transfer", "cash management transfer",
    "funds transfer", "funds transferred", "wire transfer", "outgoing money",
    "incoming money", "preauthorized debit", "balance", "payment received",
    "electronic payment", "automatic transfer", "transfer of funds", "sweep",
    "net sweep", "reinvestment", "misc disbursement",
]

# merchant_category (kabass) -> (direction, txn_type)
CATEGORY_MAP = {
    "debit": ("debit", "card"),
    "credit": ("credit", "card"),
    "check": ("debit", "check"),
    "wire_out": ("debit", "wire"),
    "wire_in": ("credit", "wire"),
    "deposit": ("credit", "deposit"),
    "transfer": ("unknown", "transfer"),
    "transfer_in": ("credit", "transfer"),
    "transfer_out": ("debit", "transfer"),
    "fee": ("debit", "fee"),
    "interest": ("credit", "interest"),
    "dividend": ("credit", "dividend"),
    "withdrawal": ("debit", "withdrawal"),
    "payment": ("debit", "payment"),
    "electronic_payment": ("debit", "payment"),
    "card_purchase": ("debit", "card"),
    "purchase": ("debit", "card"),
    "sale": ("credit", "sale"),
    "foreign_exchange": ("unknown", "fx"),
    "exchange": ("unknown", "fx"),
    "income": ("credit", "income"),
    "investment": ("debit", "investment"),
    "reinvestment": ("credit", "investment"),
    "sweep": ("unknown", "transfer"),
    "net_sweep": ("unknown", "transfer"),
    "balance": ("unknown", "balance"),
}


def _amount_to_minor(dollars):
    """Round a float dollar value to signed integer cents.

    Returns None if the scaled value would overflow SQLite's signed 64-bit
    INTEGER (OCR-garbage magnitudes) — callers flag those as outliers separately.
    """
    if dollars is None:
        return None
    try:
        minor = int(round(dollars * 100))
    except (ValueError, OverflowError):
        return None
    return minor if abs(minor) <= _INT64_MAX else None


def _is_sentinel(raw_amount):
    if not raw_amount:
        return False
    s = str(raw_amount).strip().replace("$", "").replace(",", "")
    return bool(_SENTINEL_RE.match(s))


def _norm_desc(s):
    """Collapse whitespace + lowercase for dedupe hashing (OCR-stable-ish)."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _dedupe_key(canonical_ref, day, amount_minor, description):
    h = hashlib.sha1(
        "|".join([
            str(canonical_ref or ""),
            str(day if day is not None else ""),
            str(amount_minor if amount_minor is not None else ""),
            _norm_desc(description),
        ]).encode("utf-8")
    ).hexdigest()
    return h[:16]


def _is_structural(name):
    if not name:
        return 0
    low = name.strip().lower()
    return 1 if any(low.startswith(p) for p in STRUCTURAL_MERCHANT_PREFIXES) else 0


def _efta_map(db):
    """canonical_ref (EFTA) -> evidence_item_id, for rows that have one."""
    return {r["canonical_ref"]: r["evidence_item_id"]
            for r in db.execute("SELECT canonical_ref, evidence_item_id FROM evidence_item")}


# ─────────────────────────────── merchants ───────────────────────────────────

def build_merchants(db, limit=None):
    """Canonicalize merchant from kab.financial_transactions.merchant_name."""
    print("building merchant canon from kabass merchant_name ...")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT merchant_name AS name, merchant_category AS cat, COUNT(*) AS n
        FROM kab.financial_transactions
        WHERE merchant_name IS NOT NULL AND TRIM(merchant_name) != ''
        GROUP BY merchant_name
        ORDER BY n DESC {lim}
    """).fetchall()

    payload = []
    for r in rows:
        name = r["name"].strip()
        payload.append((name, r["cat"], _is_structural(name)))
    db.executemany(
        "INSERT OR IGNORE INTO merchant(canonical_name, merchant_category, is_structural) "
        "VALUES (?, ?, ?)", payload)
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM merchant").fetchone()[0]
    n_struct = db.execute("SELECT COUNT(*) FROM merchant WHERE is_structural=1").fetchone()[0]
    print(f"  merchant: {n:,}  (structural markers: {n_struct:,})")
    return {r["canonical_name"]: r["merchant_id"]
            for r in db.execute("SELECT merchant_id, canonical_name FROM merchant")}


# ────────────────────────────── transactions ─────────────────────────────────

def _reset_transactions(db):
    """Idempotency: transactions are fully owned by this builder; rebuild clean.

    (is_duplicate_of is a self-FK, so clear it before deleting parents.)"""
    db.execute("UPDATE financial_transaction SET is_duplicate_of = NULL")
    db.execute("DELETE FROM financial_transaction")
    db.commit()


def build_kabass_transactions(db, ss, merchant_ids, efta, limit=None):
    print("loading kabass financial_transactions -> financial_transaction ...")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT id, file_key, transaction_date, amount, merchant_name,
               merchant_category, cardholder, description, source_page
        FROM kab.financial_transactions {lim}
    """).fetchall()

    batch, inserted = [], 0
    for r in rows:
        raw_amount = r["amount"]
        dollars, conf = parse_dollar_amount(raw_amount) if raw_amount not in (None, "") else (None, 0.0)
        amount_minor = _amount_to_minor(dollars)

        is_outlier = 0
        if _is_sentinel(raw_amount):
            is_outlier = 1
        elif amount_minor is not None and abs(amount_minor) > OUTLIER_ABS_MINOR:
            is_outlier = 1

        iso, _prec = normalize_date(r["transaction_date"])
        day = to_epoch_day(iso)

        cat = (r["merchant_category"] or "").strip().lower()
        direction, txn_type = CATEGORY_MAP.get(cat, ("unknown", cat or None))

        mname = (r["merchant_name"] or "").strip()
        merchant_id = merchant_ids.get(mname)

        file_key = r["file_key"]
        canonical_ref = file_key
        ev_id = efta.get(file_key)  # NULL if this file_key is not an evidence_item

        ddk = _dedupe_key(canonical_ref, day, amount_minor, r["description"])
        batch.append((
            ss["kabasshouse"], str(r["id"]), ev_id, canonical_ref,
            day, day, amount_minor, direction, txn_type, merchant_id,
            r["cardholder"], None, raw_amount, r["description"],
            conf if conf else None, is_outlier, ddk,
        ))
        if len(batch) >= 5000:
            inserted += _flush_txn(db, batch)
            batch = []
    if batch:
        inserted += _flush_txn(db, batch)
    db.commit()
    print(f"  kabass transactions inserted: {inserted:,}")
    return inserted


def _flush_txn(db, batch):
    db.executemany("""
        INSERT OR IGNORE INTO financial_transaction
            (source_system_id, source_native_id, evidence_item_id, canonical_ref,
             txn_day_min, txn_day_max, amount_minor, direction, txn_type, merchant_id,
             cardholder_raw, counterparty_raw, raw_amount, raw_description,
             parse_confidence, is_outlier, dedupe_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    return len(batch)


def _load_lms_signed(row):
    """LMSBAND typed amounts are unsigned REAL + a direction column. Sign them:
    outgoing -> negative (outflow), incoming/credit -> positive."""
    amt = row["amount"]
    if amt is None:
        return None, None
    direction_raw = (row["direction"] or "").strip().lower()
    signed = -abs(amt) if direction_raw in ("outgoing", "debit", "out") else abs(amt)
    minor = _amount_to_minor(signed)
    dir_norm = "debit" if signed < 0 else ("credit" if signed > 0 else "unknown")
    return minor, dir_norm


def build_lmsband_transactions(db, ss, efta, limit=None):
    """ds10_transactions (wires), ds09_transactions (wires), ds09_cc_transactions (cards)."""
    lim = f"LIMIT {limit}" if limit else ""
    total = 0

    # -- ds10_transactions (Deutsche Bank wires / statement lines) --------------
    print("loading lms.ds10_transactions -> financial_transaction ...")
    rows = db.execute(f"""
        SELECT id, efta_id, tx_date, amount, direction, sender, receiver,
               bank, reference, running_balance, confidence, statement_id
        FROM lms.ds10_transactions {lim}
    """).fetchall()
    batch = []
    for r in rows:
        minor, dir_norm = _load_lms_signed(r)
        is_outlier = 1 if (minor is not None and abs(minor) > OUTLIER_ABS_MINOR) else 0
        iso, _p = normalize_date(r["tx_date"])
        day = to_epoch_day(iso)
        # For an outgoing wire sender=self, receiver=counterparty; incoming flips.
        self_side, counterparty = (
            (r["sender"], r["receiver"]) if dir_norm == "debit" else (r["receiver"], r["sender"]))
        desc = " ".join(x for x in [r["sender"], "->", r["receiver"], r["reference"]] if x)
        ev_id = efta.get(r["efta_id"])
        ddk = _dedupe_key(r["efta_id"], day, minor, desc)
        batch.append((
            ss["lmsband"], f"ds10:{r['id']}", ev_id, r["efta_id"],
            day, day, minor, dir_norm, "wire", None,
            self_side, counterparty, str(r["amount"]) if r["amount"] is not None else None,
            desc, r["confidence"], is_outlier, ddk,
        ))
    total += _flush_txn(db, batch) if batch else 0
    print(f"  ds10 wires inserted: {len(batch):,}")

    # -- ds09_transactions (wire threads) ---------------------------------------
    print("loading lms.ds09_transactions -> financial_transaction ...")
    rows = db.execute(f"""
        SELECT id, efta_id, tx_date, amount, direction, sender, receiver,
               bank, reference, tx_type, confidence
        FROM lms.ds09_transactions {lim}
    """).fetchall()
    batch = []
    for r in rows:
        minor, dir_norm = _load_lms_signed(r)
        is_outlier = 1 if (minor is not None and abs(minor) > OUTLIER_ABS_MINOR) else 0
        iso, _p = normalize_date(r["tx_date"])
        day = to_epoch_day(iso)
        self_side, counterparty = (
            (r["sender"], r["receiver"]) if dir_norm == "debit" else (r["receiver"], r["sender"]))
        desc = " ".join(x for x in [r["sender"], "->", r["receiver"], r["reference"]] if x)
        ev_id = efta.get(r["efta_id"])
        ddk = _dedupe_key(r["efta_id"], day, minor, desc)
        batch.append((
            ss["lmsband"], f"ds09:{r['id']}", ev_id, r["efta_id"],
            day, day, minor, dir_norm, r["tx_type"] or "wire", None,
            self_side, counterparty, str(r["amount"]) if r["amount"] is not None else None,
            desc, r["confidence"], is_outlier, ddk,
        ))
    total += _flush_txn(db, batch) if batch else 0
    print(f"  ds09 wires inserted: {len(batch):,}")

    # -- ds09_cc_transactions (credit-card lines) -------------------------------
    print("loading lms.ds09_cc_transactions -> financial_transaction ...")
    rows = db.execute(f"""
        SELECT id, efta_id, tx_date, description, merchant, location,
               amount, tx_category, confidence
        FROM lms.ds09_cc_transactions {lim}
    """).fetchall()
    batch = []
    for r in rows:
        # cc statement convention: purchases are positive, payments/credits are
        # negative in the source. Re-sign to the model's convention (outflow
        # negative, inflow positive): a purchase is a debit (-), a payment/credit
        # received against the card is a credit (+).
        amt = r["amount"]
        cat = (r["tx_category"] or "").strip().lower()
        if amt is None:
            minor, dir_norm = None, "unknown"
        elif cat in ("payment", "interest") or amt < 0:
            minor = _amount_to_minor(abs(amt))    # credit -> inflow (+)
            dir_norm = "credit"
        else:
            minor = _amount_to_minor(-abs(amt))   # purchase -> outflow (-)
            dir_norm = "debit"
        is_outlier = 1 if (minor is not None and abs(minor) > OUTLIER_ABS_MINOR) else 0
        iso, _p = normalize_date(r["tx_date"])
        day = to_epoch_day(iso)
        desc = r["description"] or r["merchant"]
        ev_id = efta.get(r["efta_id"])
        ddk = _dedupe_key(r["efta_id"], day, minor, desc)
        batch.append((
            ss["lmsband"], f"ds09cc:{r['id']}", ev_id, r["efta_id"],
            day, day, minor, dir_norm, "card", None,
            None, r["merchant"], str(amt) if amt is not None else None,
            desc, r["confidence"], is_outlier, ddk,
        ))
    total += _flush_txn(db, batch) if batch else 0
    print(f"  ds09 cc inserted: {len(batch):,}")

    db.commit()
    return total


def dedupe_transactions(db):
    """Two passes, mirroring the spec:

    1. within-kabass same-page dups: rows sharing (canonical_ref, day, amount,
       normalized description) — keep MIN(transaction_id), point the rest at it.
    2. cross-source: an LMSBAND row and a kabass row sharing (canonical_ref, day,
       amount) -> PREFER LMSBAND as canonical; mark the kabass row duplicate.
    """
    print("deduping transactions ...")
    kab = source_system_id(db, "kabasshouse")
    lms = source_system_id(db, "lmsband")

    # Pass 1: within-kabass identical dedupe_key groups.
    same_page = 0
    for grp in db.execute("""
        SELECT dedupe_key, MIN(transaction_id) AS keep_id, COUNT(*) AS c
        FROM financial_transaction
        WHERE source_system_id = ? AND dedupe_key IS NOT NULL
        GROUP BY dedupe_key HAVING c > 1
    """, (kab,)).fetchall():
        cur = db.execute("""
            UPDATE financial_transaction
            SET is_duplicate_of = ?
            WHERE dedupe_key = ? AND source_system_id = ? AND transaction_id != ?
              AND is_duplicate_of IS NULL
        """, (grp["keep_id"], grp["dedupe_key"], kab, grp["keep_id"]))
        same_page += cur.rowcount
    db.commit()
    print(f"  within-kabass same-page dups collapsed: {same_page:,}")

    # Pass 2: cross-source. Only where a shared canonical_ref (EFTA) exists.
    cross = db.execute("""
        UPDATE financial_transaction AS k
        SET is_duplicate_of = (
            SELECT MIN(l.transaction_id) FROM financial_transaction l
            WHERE l.source_system_id = ?
              AND l.canonical_ref = k.canonical_ref
              AND l.txn_day_min IS k.txn_day_min
              AND l.amount_minor = k.amount_minor
        )
        WHERE k.source_system_id = ?
          AND k.is_duplicate_of IS NULL
          AND k.canonical_ref IS NOT NULL
          AND k.amount_minor IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM financial_transaction l
            WHERE l.source_system_id = ?
              AND l.canonical_ref = k.canonical_ref
              AND l.txn_day_min IS k.txn_day_min
              AND l.amount_minor = k.amount_minor
          )
    """, (lms, kab, lms))
    db.commit()
    print(f"  cross-source (kabass->lmsband) dups collapsed: {cross.rowcount:,}")
    return same_page, cross.rowcount


# ─────────────────────────── balances / positions ────────────────────────────

def build_balances(db, efta, limit=None):
    print("loading lms.ds10_balances -> balance_snapshot ...")
    db.execute("DELETE FROM balance_snapshot")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT efta_id, account_holder, balance_date, balance FROM lms.ds10_balances {lim}
    """).fetchall()
    batch = []
    for r in rows:
        minor = _amount_to_minor(r["balance"])
        if minor is None:
            continue
        iso, _p = normalize_date(r["balance_date"])
        day = to_epoch_day(iso)
        if day is None:
            continue
        batch.append((r["account_holder"], day, minor, efta.get(r["efta_id"])))
    db.executemany("""
        INSERT INTO balance_snapshot(owner_raw, as_of_day, balance_minor, evidence_item_id)
        VALUES (?, ?, ?, ?)
    """, batch)
    db.commit()
    print(f"  balance_snapshot: {len(batch):,}")
    return len(batch)


def build_positions(db, efta, limit=None):
    print("loading lms.ds10_positions -> position_snapshot (+ security) ...")
    db.execute("DELETE FROM position_snapshot")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT efta_id, entity, investment, position_date, value, cost_basis
        FROM lms.ds10_positions {lim}
    """).fetchall()

    # securities first
    secs = {r["investment"].strip() for r in rows if r["investment"] and r["investment"].strip()}
    db.executemany("INSERT OR IGNORE INTO security(canonical_name) VALUES (?)", [(s,) for s in secs])
    db.commit()
    sec_ids = {r["canonical_name"]: r["security_id"]
               for r in db.execute("SELECT security_id, canonical_name FROM security")}

    batch = []
    for r in rows:
        # Detect absurdity from the raw float (before scaling, which may overflow
        # to None). cost_basis > $1e12 is the flagged case from the spec.
        raw_cb, raw_mv = r["cost_basis"], r["value"]
        is_outlier = 0
        if raw_cb is not None and abs(raw_cb) > 1e12:
            is_outlier = 1
        if raw_mv is not None and abs(raw_mv) > 1e12:
            is_outlier = 1
        mv = _amount_to_minor(raw_mv)
        cb = _amount_to_minor(raw_cb)
        iso, _p = normalize_date(r["position_date"])
        day = to_epoch_day(iso)
        if day is None:
            continue
        sid = sec_ids.get((r["investment"] or "").strip())
        batch.append((r["entity"], sid, day, mv, cb, is_outlier, efta.get(r["efta_id"])))
    db.executemany("""
        INSERT INTO position_snapshot
            (owner_raw, security_id, as_of_day, market_value_minor, cost_basis_minor,
             is_outlier, evidence_item_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    n_out = db.execute("SELECT COUNT(*) FROM position_snapshot WHERE is_outlier=1").fetchone()[0]
    print(f"  position_snapshot: {len(batch):,}  (securities: {len(sec_ids):,}, outliers: {n_out})")
    return len(batch)


def build_statements(db, efta, limit=None):
    print("loading lms.ds10_statement_recon -> financial_statement ...")
    db.execute("DELETE FROM financial_statement")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT efta_id, statement_start_date, statement_end_date,
               beginning_balance, ending_balance, recon_delta, recon_status
        FROM lms.ds10_statement_recon {lim}
    """).fetchall()
    batch = []
    for r in rows:
        s_iso, _ = normalize_date(r["statement_start_date"])
        e_iso, _ = normalize_date(r["statement_end_date"])
        batch.append((
            to_epoch_day(s_iso), to_epoch_day(e_iso), to_epoch_day(e_iso),
            _amount_to_minor(r["beginning_balance"]), _amount_to_minor(r["ending_balance"]),
            r["recon_status"], _amount_to_minor(r["recon_delta"]), efta.get(r["efta_id"]),
        ))
    db.executemany("""
        INSERT INTO financial_statement
            (period_start_day, period_end_day, statement_date_day,
             beginning_balance_minor, ending_balance_minor, recon_status,
             recon_delta_minor, evidence_item_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    print(f"  financial_statement: {len(batch):,}")
    return len(batch)


def build_flights(db, ss, efta, limit=None):
    """ds09_travel_flights joined to invoices (ticket cost) + passengers (names)."""
    print("loading lms.ds09_travel_flights -> fin_flight ...")
    db.execute("DELETE FROM fin_flight")
    lim = f"LIMIT {limit}" if limit else ""
    # Scalar subquery for the invoice total keeps this 1 row per source flight —
    # a plain LEFT JOIN fans out when a record_locator maps to several invoices.
    rows = db.execute(f"""
        SELECT f.id, f.efta_id, f.passenger_name, f.flight_date, f.airline,
               f.flight_number, f.origin, f.destination, f.ticket_number,
               f.ticket_cost, f.record_locator,
               (SELECT MAX(inv.total_charged) FROM lms.ds09_travel_invoices inv
                 WHERE inv.record_locator = f.record_locator
                   AND f.record_locator IS NOT NULL AND f.record_locator != ''
               ) AS inv_total
        FROM lms.ds09_travel_flights f
        {lim}
    """).fetchall()
    batch = []
    for r in rows:
        iso, _p = normalize_date(r["flight_date"])
        day = to_epoch_day(iso)
        cost = r["ticket_cost"] if r["ticket_cost"] is not None else r["inv_total"]
        cost_minor = _amount_to_minor(cost)
        batch.append((
            ss["lmsband"], f"ds09flt:{r['id']}", efta.get(r["efta_id"]),
            r["passenger_name"], day, r["airline"], r["flight_number"],
            r["origin"], r["destination"], cost_minor, r["ticket_number"],
            r["record_locator"],
        ))
    db.executemany("""
        INSERT INTO fin_flight
            (source_system_id, source_native_id, evidence_item_id, passenger_raw,
             flight_day, airline, flight_number, origin, destination,
             ticket_cost_minor, ticket_number, record_locator)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    print(f"  fin_flight: {len(batch):,}")
    return len(batch)


# ─────────────────────────────────── main ────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="cap rows per source table (testing)")
    ap.add_argument("--stage", action="append",
                    choices=["merchants", "transactions", "balances", "positions",
                             "statements", "flights", "all"],
                    help="run only these stages (default: all)")
    args = ap.parse_args()
    stages = set(args.stage or ["all"])
    run_all = "all" in stages

    db = get_db()
    init_schema(db)
    attach(db, "kab", KABASS_DB)
    attach(db, "lms", LMSBAND_DB)
    run_id = new_run(db, "build_financials", note="normalized financial model")
    ss = {n: source_system_id(db, n) for n in ("kabasshouse", "lmsband")}
    efta = _efta_map(db)

    total = 0
    merchant_ids = None
    if run_all or "merchants" in stages:
        merchant_ids = build_merchants(db, limit=args.limit)
    if run_all or "transactions" in stages:
        if merchant_ids is None:
            merchant_ids = {r["canonical_name"]: r["merchant_id"]
                            for r in db.execute("SELECT merchant_id, canonical_name FROM merchant")}
        _reset_transactions(db)
        total += build_kabass_transactions(db, ss, merchant_ids, efta, limit=args.limit)
        total += build_lmsband_transactions(db, ss, efta, limit=args.limit)
        dedupe_transactions(db)
    if run_all or "balances" in stages:
        build_balances(db, efta, limit=args.limit)
    if run_all or "positions" in stages:
        build_positions(db, efta, limit=args.limit)
    if run_all or "statements" in stages:
        build_statements(db, efta, limit=args.limit)
    if run_all or "flights" in stages:
        build_flights(db, ss, efta, limit=args.limit)

    n_txn = db.execute("SELECT COUNT(*) FROM financial_transaction").fetchone()[0]
    n_out = db.execute("SELECT COUNT(*) FROM financial_transaction WHERE is_outlier=1").fetchone()[0]
    n_dup = db.execute("SELECT COUNT(*) FROM financial_transaction WHERE is_duplicate_of IS NOT NULL").fetchone()[0]
    db.execute("UPDATE derivation_run SET completed_at=CURRENT_TIMESTAMP, record_count=? WHERE run_id=?",
               (n_txn, run_id))
    db.commit()
    print(f"\nfinancial_transaction: {n_txn:,}  (outliers {n_out:,}, duplicates {n_dup:,})")
    db.close()


if __name__ == "__main__":
    main()
