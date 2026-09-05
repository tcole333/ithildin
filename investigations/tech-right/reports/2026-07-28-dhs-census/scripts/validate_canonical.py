#!/usr/bin/env python3
"""Validate the census against wave-3 canonical numbers (method law: obligations
from child task orders, never off the parent IDV).

Targets (2026-07-27-wave3-brief.md):
  skip tracing sol 26-SOL-DCR-01: 14 IDIQs, ceiling 1,442,909,640, obligated 19,032,607
  UAC sol 70CDCR26R00000015: 18 IDIQs (70CDCR26D00000030-47), ceiling ~20,583,928,204,
      obligated 86,822,317 via 19 task orders (18 = FR0000081-0098 + MVM FR0000052 on FY24 vehicle)
"""
import json
import os
import sqlite3
from decimal import Decimal

WORK = "/tmp/osint-GWLtvuxV/work-census"
con = sqlite3.connect(os.path.join(WORK, "census.db"))
out = {}


def q(sql, params=()):
    return con.execute(sql, params).fetchall()


def latest_potential_per_award(where, params):
    """current ceiling per award = potential of last (date,mod,txn) row."""
    rows = q(f"""
        SELECT award_key, piid, potential FROM txn t
        WHERE {where} AND NOT EXISTS (
            SELECT 1 FROM txn t2 WHERE t2.award_key = t.award_key
            AND (t2.action_date > t.action_date OR (t2.action_date = t.action_date AND (t2.mod > t.mod OR (t2.mod = t.mod AND t2.txn_num > t.txn_num))))
        )""", params)
    return rows


# --- skip tracing ---
skip = {}
idvs = latest_potential_per_award(
    "t.flag='IDV' AND UPPER(t.solicitation) LIKE '26-SOL-DCR%'", ())
skip["n_idvs"] = len(idvs)
skip["idv_piids"] = sorted(r[1] for r in idvs)
skip["ceiling_sum"] = str(sum(Decimal(r[2] or "0") for r in idvs))
piids = [r[1] for r in idvs]
ph = ",".join("?" * len(piids))
child = q(f"SELECT COALESCE(SUM(CAST(fao AS REAL)),0), COUNT(DISTINCT award_key) FROM txn WHERE parent_piid IN ({ph})", piids)
skip["child_order_obligations"] = round(child[0][0], 2)
skip["n_child_awards"] = child[0][1]
out["skip_tracing_26SOLDCR01"] = skip
out["skip_expected"] = {"n_idvs": 14, "ceiling": "1442909640", "obligated": "19032607"}

# --- UAC ---
uac = {}
idvs = latest_potential_per_award(
    "t.flag='IDV' AND UPPER(t.solicitation) LIKE '%70CDCR26R00000015%'", ())
uac["n_idvs"] = len(idvs)
uac["idv_piids"] = sorted(r[1] for r in idvs)
uac["ceiling_sum"] = str(sum(Decimal(r[2] or "0") for r in idvs))
piids = [r[1] for r in idvs]
if piids:
    ph = ",".join("?" * len(piids))
    child = q(f"SELECT COALESCE(SUM(CAST(fao AS REAL)),0), COUNT(DISTINCT award_key) FROM txn WHERE parent_piid IN ({ph})", piids)
    uac["child_order_obligations_new_family"] = round(child[0][0], 2)
    uac["n_child_awards_new_family"] = child[0][1]
# MVM order on FY24 vehicle
mvm = q("SELECT award_key, SUM(CAST(fao AS REAL)) FROM txn WHERE piid LIKE '%FR0000052%' GROUP BY award_key")
uac["mvm_FR0000052"] = [{"award": r[0], "obligations": round(r[1], 2)} for r in mvm]
if piids and mvm:
    uac["initiative_total_with_mvm"] = round(child[0][0] + sum(r[1] for r in mvm), 2)
out["uac_70CDCR26R00000015"] = uac
out["uac_expected"] = {"n_idvs": 18, "ceiling": "~20583928204", "obligated_19_orders": "86822317"}

print(json.dumps(out, indent=2))
with open(os.path.join(WORK, "canonical-validation.json"), "w") as f:
    json.dump(out, f, indent=2)
