#!/usr/bin/env python3
"""Build the DHS award census from downloaded USASpending transaction CSVs.

Reads every CSV under raw/*/, dedupes transactions, loads a work-dir SQLite
(census.db), aggregates to award level, and emits:
  - census-transactions.csv  (mod ledger)
  - census-awards.csv        (one row per award passing the >=250K keep rule)
  - full-universe aggregates for S1 denominators (kept in census.db)
  - recon.json               (pipeline stage counts + totals by component)

Column semantics verified empirically on probe file 2026-07-28:
  federal_action_obligation, base_and_all_options_value = per-action deltas
  total_dollars_obligated, potential_total_value_of_award = cumulative AS OF that action
"""
import csv
import glob
import json
import os
import sqlite3
from collections import defaultdict
from decimal import Decimal, InvalidOperation

WORK = "/tmp/osint-GWLtvuxV/work-census"
DB = os.path.join(WORK, "census.db")
WINDOW_START = "2025-01-20"
WINDOW_END = "2026-07-28"

csv.field_size_limit(50_000_000)

REQUIRED_COLS = [
    "contract_transaction_unique_key", "contract_award_unique_key", "award_id_piid",
    "modification_number", "transaction_number", "parent_award_id_piid",
    "federal_action_obligation", "total_dollars_obligated",
    "base_and_all_options_value", "potential_total_value_of_award",
    "current_total_value_of_award", "base_and_exercised_options_value",
    "action_date", "awarding_sub_agency_code", "awarding_sub_agency_name",
    "awarding_office_code", "awarding_office_name", "recipient_uei", "recipient_name",
    "recipient_parent_uei", "recipient_parent_name", "award_or_idv_flag",
    "award_type_code", "award_type", "idv_type_code", "idv_type",
    "transaction_description", "prime_award_base_transaction_description",
    "action_type_code", "action_type", "solicitation_identifier", "naics_code",
    "product_or_service_code", "extent_competed_code", "extent_competed",
    "solicitation_procedures_code", "solicitation_procedures",
    "type_of_set_aside_code", "type_of_set_aside",
    "other_than_full_and_open_competition_code", "other_than_full_and_open_competition",
    "fair_opportunity_limited_sources_code", "fair_opportunity_limited_sources",
    "number_of_offers_received", "usaspending_permalink", "last_modified_date",
    "solicitation_date",
]


def dec(s):
    if s is None or s == "":
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def normalize_pair(a, b, code_maxlen):
    """Return (code, label) regardless of which column upstream put them in."""
    a, b = a or "", b or ""
    if a and len(a) <= code_maxlen and (not b or len(b) > code_maxlen):
        return a, b
    if b and len(b) <= code_maxlen and (not a or len(a) > code_maxlen):
        return b, a
    return a, b  # ambiguous or both blank: keep original order


def build_db():
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE txn (
            txn_key TEXT PRIMARY KEY,
            award_key TEXT, piid TEXT, mod TEXT, txn_num TEXT, parent_piid TEXT,
            fao TEXT, total_obl TEXT, baov TEXT, potential TEXT,
            beov TEXT, current_total TEXT,
            action_date TEXT, sub_agency_code TEXT, sub_agency TEXT,
            office_code TEXT, office TEXT,
            uei TEXT, recipient TEXT, parent_uei TEXT, parent_recipient TEXT,
            flag TEXT, award_type_code TEXT, award_type TEXT, idv_type_code TEXT, idv_type TEXT,
            txn_desc TEXT, base_desc TEXT, action_type_code TEXT, action_type TEXT,
            solicitation TEXT, naics TEXT, psc TEXT,
            ec_code TEXT, ec TEXT, sp_code TEXT, sp TEXT, sa_code TEXT, sa TEXT,
            otfo_code TEXT, otfo TEXT, folso_code TEXT, folso TEXT,
            offers TEXT, permalink TEXT, last_modified TEXT, solicitation_date TEXT,
            src_file TEXT
        )
    """)

    stage = {"files": [], "physical_rows": 0, "dupes_across_windows": 0, "inserted": 0}
    files = sorted(glob.glob(os.path.join(WORK, "raw", "*", "*.csv")))
    assert files, "no CSVs found under raw/"
    for path in files:
        n_rows = n_dupe = 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            r = csv.DictReader(f)
            missing = [c for c in REQUIRED_COLS if c not in r.fieldnames]
            if missing:
                raise SystemExit(f"{os.path.basename(path)} MISSING COLUMNS: {missing}")
            batch = []
            for row in r:
                n_rows += 1
                batch.append((
                    row["contract_transaction_unique_key"],
                    row["contract_award_unique_key"], row["award_id_piid"],
                    row["modification_number"], row["transaction_number"],
                    row["parent_award_id_piid"],
                    row["federal_action_obligation"], row["total_dollars_obligated"],
                    row["base_and_all_options_value"], row["potential_total_value_of_award"],
                    row["base_and_exercised_options_value"], row["current_total_value_of_award"],
                    row["action_date"], row["awarding_sub_agency_code"], row["awarding_sub_agency_name"],
                    row["awarding_office_code"], row["awarding_office_name"],
                    row["recipient_uei"], row["recipient_name"],
                    row["recipient_parent_uei"], row["recipient_parent_name"],
                    row["award_or_idv_flag"], row["award_type_code"], row["award_type"],
                    row["idv_type_code"], row["idv_type"],
                    (row["transaction_description"] or "")[:400],
                    (row["prime_award_base_transaction_description"] or "")[:400],
                    row["action_type_code"], row["action_type"],
                    row["solicitation_identifier"], row["naics_code"], row["product_or_service_code"],
                    # bulk CSV swaps code/label for these two pairs (verified 2026-07-28):
                    # normalize so ec_code/sp_code always hold the short code
                    *normalize_pair(row["extent_competed_code"], row["extent_competed"], 1),
                    *normalize_pair(row["solicitation_procedures_code"], row["solicitation_procedures"], 4),
                    row["type_of_set_aside_code"], row["type_of_set_aside"],
                    row["other_than_full_and_open_competition_code"],
                    row["other_than_full_and_open_competition"],
                    row["fair_opportunity_limited_sources_code"], row["fair_opportunity_limited_sources"],
                    row["number_of_offers_received"], row["usaspending_permalink"],
                    row["last_modified_date"], row["solicitation_date"],
                    os.path.basename(path),
                ))
                if len(batch) >= 5000:
                    n_dupe += flush(con, batch)
                    batch = []
            n_dupe += flush(con, batch)
        stage["files"].append({"file": os.path.basename(path), "logical_rows": n_rows, "dupes": n_dupe})
        stage["physical_rows"] += n_rows
        stage["dupes_across_windows"] += n_dupe
        print(f"loaded {os.path.basename(path)}: {n_rows} logical rows, {n_dupe} dupes")
    con.commit()
    stage["inserted"] = con.execute("SELECT COUNT(*) FROM txn").fetchone()[0]
    con.execute("CREATE INDEX ix_award ON txn(award_key)")
    con.execute("CREATE INDEX ix_parent ON txn(parent_piid)")
    con.execute("CREATE INDEX ix_date ON txn(action_date)")
    con.commit()
    return con, stage


def flush(con, batch):
    if not batch:
        return 0
    before = con.total_changes
    con.executemany(
        f"INSERT OR IGNORE INTO txn VALUES ({','.join('?' * len(batch[0]))})", batch
    )
    return len(batch) - (con.total_changes - before)


def first_nonblank(seq):
    for v in seq:
        if v not in (None, ""):
            return v
    return None


def aggregate(con):
    """One pass per award: ordered ledger -> award record."""
    awards = {}
    cur = con.execute(
        "SELECT * FROM txn ORDER BY award_key, action_date, mod, txn_num"
    )
    cols = [d[0] for d in cur.description]
    rows_by_award = defaultdict(list)
    for row in cur:
        rows_by_award[row[cols.index("award_key")]].append(dict(zip(cols, row)))

    for key, rows in rows_by_award.items():
        first, last = rows[0], rows[-1]
        window_obl = sum((dec(r["fao"]) or Decimal(0)) for r in rows)
        window_ceiling_delta = sum((dec(r["baov"]) or Decimal(0)) for r in rows)
        cur_ceiling = dec(last["potential"])
        cur_total_value = dec(last["current_total"])
        total_obl_todate = dec(last["total_obl"])
        first_fao = dec(first["fao"]) or Decimal(0)
        first_baov = dec(first["baov"]) or Decimal(0)
        pre_window_obl = (dec(first["total_obl"]) or Decimal(0)) - first_fao
        start_ceiling = (dec(first["potential"]) or Decimal(0)) - first_baov
        born_in_window = first["mod"] in ("0", "00", "") and abs(pre_window_obl) < Decimal("0.01")
        # base competition fields: prefer the earliest row that has them
        ordered = rows
        awards[key] = {
            "award_id": key,
            "piid": first_nonblank([r["piid"] for r in ordered]),
            "parent_idv_piid": first_nonblank([r["parent_piid"] for r in ordered]),
            "recipient_name": last["recipient"] or first["recipient"],
            "recipient_uei": first_nonblank([last["uei"]] + [r["uei"] for r in ordered]),
            "recipient_parent_uei": first_nonblank([last["parent_uei"]] + [r["parent_uei"] for r in ordered]),
            "recipient_parent_name": last["parent_recipient"],
            "awarding_subagency_code": first_nonblank([r["sub_agency_code"] for r in ordered]),
            "awarding_subagency": first_nonblank([r["sub_agency"] for r in ordered]),
            "awarding_office_code": first_nonblank([r["office_code"] for r in ordered]),
            "awarding_office_name": first_nonblank([r["office"] for r in ordered]),
            "naics": first_nonblank([r["naics"] for r in ordered]),
            "psc": first_nonblank([r["psc"] for r in ordered]),
            "action_count": len(rows),
            "first_action_date": first["action_date"],
            "last_action_date": last["action_date"],
            "window_obligations": str(window_obl),
            "pre_window_obligations": str(pre_window_obl),
            "total_obligations_todate": str(total_obl_todate) if total_obl_todate is not None else "",
            "current_ceiling": str(cur_ceiling) if cur_ceiling is not None else "",
            "current_total_value": str(cur_total_value) if cur_total_value is not None else "",
            "start_of_window_ceiling": str(start_ceiling),
            "window_ceiling_delta": str(window_ceiling_delta),
            "born_in_window": int(born_in_window),
            "extent_competed_code": first_nonblank([r["ec_code"] for r in ordered]),
            "extent_competed": first_nonblank([r["ec"] for r in ordered]),
            "solicitation_procedures_code": first_nonblank([r["sp_code"] for r in ordered]),
            "solicitation_procedures": first_nonblank([r["sp"] for r in ordered]),
            "offers_received": first_nonblank([r["offers"] for r in ordered]),
            "other_than_full_open_competition_code": first_nonblank([r["otfo_code"] for r in ordered]),
            "other_than_full_open_competition": first_nonblank([r["otfo"] for r in ordered]),
            "fair_opportunity_limited_sources": first_nonblank([r["folso"] for r in ordered]),
            "set_aside_code": first_nonblank([r["sa_code"] for r in ordered]),
            "set_aside": first_nonblank([r["sa"] for r in ordered]),
            "solicitation_id": first_nonblank([r["solicitation"] for r in ordered]),
            "solicitation_date": first_nonblank([r["solicitation_date"] for r in ordered]),
            "is_idv": int(first["flag"] == "IDV"),
            "award_type_code": first_nonblank([r["award_type_code"] for r in ordered]),
            "award_type": first_nonblank([r["award_type"] for r in ordered]) or first_nonblank([r["idv_type"] for r in ordered]),
            "idv_type": first_nonblank([r["idv_type"] for r in ordered]),
            "description_snippet": (first_nonblank([r["base_desc"] for r in ordered]) or first_nonblank([r["txn_desc"] for r in ordered]) or "")[:200],
            "usaspending_permalink": first_nonblank([r["permalink"] for r in ordered]),
        }
    return awards


def main():
    con, stage = build_db()

    awards = aggregate(con)
    stage["awards_total"] = len(awards)

    # Keep rule: window obligations >= 250K OR current ceiling >= 250K
    TH = Decimal(250000)
    kept = {}
    for k, a in awards.items():
        wo = Decimal(a["window_obligations"])
        ceil = dec(a["current_ceiling"]) or Decimal(0)
        if wo >= TH or ceil >= TH:
            kept[k] = a
    stage["awards_kept_250k"] = len(kept)
    stage["awards_dropped_under_250k"] = len(awards) - len(kept)

    # census-awards.csv
    fields = list(next(iter(kept.values())).keys())
    with open(os.path.join(WORK, "census-awards.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for a in sorted(kept.values(), key=lambda x: Decimal(x["window_obligations"]), reverse=True):
            w.writerow(a)

    # full award universe -> census.db 'award' table (screen denominators)
    con.execute("DROP TABLE IF EXISTS award")
    cols_sql = ", ".join(f'"{c}" TEXT' for c in fields)
    con.execute(f"CREATE TABLE award ({cols_sql}, kept INTEGER)")
    con.executemany(
        f"INSERT INTO award VALUES ({','.join('?' * (len(fields) + 1))})",
        [tuple(str(a[c]) if a[c] is not None else "" for c in fields) + (int(k in kept),) for k, a in awards.items()],
    )
    con.execute("CREATE INDEX ix_award_sol ON award(solicitation_id)")
    con.execute("CREATE INDEX ix_award_uei ON award(recipient_uei)")
    con.commit()

    # census-transactions.csv (mod ledger for kept awards, with derived ceiling before/after)
    n_ledger = 0
    with open(os.path.join(WORK, "census-transactions.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "award_id", "piid", "mod_number", "transaction_number", "action_date",
            "obligation_delta", "obligations_after", "ceiling_delta", "ceiling_after",
            "ceiling_before", "action_type_code", "action_type", "description",
        ])
        cur = con.execute(
            "SELECT award_key, piid, mod, txn_num, action_date, fao, total_obl, baov, potential,"
            " action_type_code, action_type, txn_desc FROM txn"
            " ORDER BY award_key, action_date, mod, txn_num"
        )
        for (ak, piid, mod, tn, dt, fao, tot, baov, pot, atc, at, desc) in cur:
            if ak not in kept:
                continue
            pot_d, baov_d = dec(pot), dec(baov)
            before = str(pot_d - baov_d) if pot_d is not None and baov_d is not None else ""
            w.writerow([ak, piid, mod, tn, dt, fao, tot, baov, pot, before, atc, at, (desc or "")[:200]])
            n_ledger += 1
    stage["ledger_rows_kept_awards"] = n_ledger

    # Reconciliation: totals by component over FULL universe (all txns)
    comp = con.execute(
        "SELECT sub_agency, COUNT(*), SUM(CAST(fao AS REAL)) FROM txn GROUP BY sub_agency ORDER BY 3 DESC"
    ).fetchall()
    stage["by_component_full_universe"] = [
        {"component": c or "(blank)", "actions": n, "window_obligations": round(s or 0, 2)} for c, n, s in comp
    ]
    stage["window_obligations_total_full_universe"] = round(
        sum(s or 0 for _, _, s in comp), 2
    )
    kept_total = sum(Decimal(a["window_obligations"]) for a in kept.values())
    stage["window_obligations_total_kept"] = float(kept_total)

    with open(os.path.join(WORK, "recon.json"), "w") as f:
        json.dump(stage, f, indent=2, default=str)
    print(json.dumps({k: v for k, v in stage.items() if k != "by_component_full_universe"}, indent=2, default=str))
    print("top components:")
    for c in stage["by_component_full_universe"][:10]:
        print("  ", c)
    con.close()


if __name__ == "__main__":
    main()
