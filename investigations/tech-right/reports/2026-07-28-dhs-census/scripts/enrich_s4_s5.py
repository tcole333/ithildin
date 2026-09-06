#!/usr/bin/env python3
"""S4 (new entrants) + S5 (NAICS drift) enrichment for the top vendor slice.

Top slice: window_obligations >= 1M OR current_ceiling >= 10M, cap 300 UEIs.
Per UEI:
  1. USASpending spending_by_transaction, contracts, 2007-10-01..2024-11-04, asc:
     earliest PRE-window transaction whose "Recipient UEI" == target (client-side
     filter -- recipient_search_text expands to affiliates, verified 2026-07-28).
     Up to 4 pages x 100. Zero total results => no federal contract history pre-2024-11-05.
  2. If no pre-window contract history: assistance-type query (grants etc.) same window.
  3. Local sam.db: registration/activation/entity_start dates, state_of_inc, primary_naics.
S5: modal NAICS of matching pre-window rows vs modal NAICS of the vendor's census awards
    vs sam primary_naics.
Checkpointed in enrich_state.json; resumable. Sequential requests, backoff on 429/5xx.
"""
import csv
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from decimal import Decimal

WORK = "/tmp/osint-GWLtvuxV/work-census"
STATE = os.path.join(WORK, "enrich_state.json")
SAMDB = "/Users/travcole/projects/osint-research/datasets/sam.db"
CUTOFF = "2024-11-04"  # pre-window end (flag = first-ever after 2024-11-05)
CONTRACT_TYPES = ["A", "B", "C", "D", "IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"]
ASSIST_TYPES = ["02", "03", "04", "05", "06", "07", "08", "09", "10", "11"]

csv.field_size_limit(50_000_000)


def api(payload, max_retries=5):
    req = urllib.request.Request(
        "https://api.usaspending.gov/api/v2/search/spending_by_transaction/",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "osint-research-census/0.1"},
    )
    backoff = 5
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429,) or e.code >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)
    raise RuntimeError("api retries exhausted")


def query_history(uei, award_types, end_date, max_pages=4):
    """Return (earliest_matching_row, matching_rows, total_zero, pages_fetched, expansion_seen)."""
    matching = []
    expansion = False
    total_zero = False
    page = 1
    while page <= max_pages:
        d = api({
            "filters": {
                "recipient_search_text": [uei],
                "award_type_codes": award_types,
                "time_period": [{"start_date": "2007-10-01", "end_date": end_date}],
            },
            "fields": ["Action Date", "Transaction Amount", "Awarding Agency", "Awarding Sub Agency",
                       "naics_code", "product_or_service_code", "Recipient Name", "Recipient UEI", "Award ID"],
            "sort": "Action Date", "order": "asc", "limit": 100, "page": page,
        })
        results = d.get("results", [])
        if page == 1 and not results:
            total_zero = True
            break
        for row in results:
            if (row.get("Recipient UEI") or "").upper() == uei.upper():
                matching.append(row)
            else:
                expansion = True
        if matching and page >= 1 and len(matching) >= 100:
            break
        if not d.get("page_metadata", {}).get("hasNext"):
            break
        # keep paging only if we have no match yet (looking for earliest) or need modal sample
        if matching and page >= 2:
            break
        page += 1
        time.sleep(0.4)
    earliest = matching[0] if matching else None
    return earliest, matching, total_zero, page, expansion


def main():
    state = {}
    if os.path.exists(STATE):
        with open(STATE) as f:
            state = json.load(f)

    # build top slice
    awards_by_uei = defaultdict(list)
    with open(os.path.join(WORK, "census-awards.csv"), newline="") as f:
        for row in csv.DictReader(f):
            if row["recipient_uei"]:
                awards_by_uei[row["recipient_uei"]].append(row)
    slice_rows = []
    for uei, rows in awards_by_uei.items():
        wobl = sum(Decimal(r["window_obligations"] or "0") for r in rows)
        ceil = sum(Decimal(r["current_ceiling"] or "0") for r in rows)
        if wobl >= Decimal(1_000_000) or ceil >= Decimal(10_000_000):
            naics = Counter(r["naics"] for r in rows if r["naics"])
            slice_rows.append({
                "uei": uei,
                "name": Counter(r["recipient_name"] for r in rows).most_common(1)[0][0],
                "window_obligations": wobl,
                "ceiling_sum": ceil,
                "dhs_modal_naics": naics.most_common(1)[0][0] if naics else "",
                "n_awards": len(rows),
            })
    slice_rows.sort(key=lambda r: -max(r["window_obligations"], r["ceiling_sum"] / 10))
    dropped = max(0, len(slice_rows) - 300)
    slice_rows = slice_rows[:300]
    print(f"top slice: {len(slice_rows)} UEIs (dropped {dropped} beyond cap)")

    sam = sqlite3.connect(SAMDB)

    for i, v in enumerate(slice_rows):
        uei = v["uei"]
        if uei in state:
            continue
        rec = {"name": v["name"], "window_obligations": str(v["window_obligations"]),
               "ceiling_sum": str(v["ceiling_sum"]), "dhs_modal_naics": v["dhs_modal_naics"],
               "n_awards": v["n_awards"]}
        try:
            earliest, matching, zero, pages, expansion = query_history(uei, CONTRACT_TYPES, CUTOFF)
            rec["pre_window_contract_zero_results"] = zero
            rec["pre_window_pages"] = pages
            rec["expansion_observed"] = expansion
            if earliest:
                rec["first_contract_action_pre_window"] = earliest["Action Date"]
                rec["first_contract_award_id"] = earliest["Award ID"]
                rec["first_contract_agency"] = earliest["Awarding Agency"]
                hist_naics = Counter(r["naics_code"] for r in matching if r.get("naics_code"))
                rec["historical_modal_naics"] = hist_naics.most_common(1)[0][0] if hist_naics else ""
                rec["historical_naics_sample_n"] = len(matching)
            else:
                rec["first_contract_action_pre_window"] = ""
                rec["historical_modal_naics"] = ""
                rec["historical_naics_sample_n"] = 0
                if zero:
                    time.sleep(0.4)
                    g_earliest, g_matching, g_zero, _, _ = query_history(uei, ASSIST_TYPES, CUTOFF, max_pages=2)
                    rec["pre_window_assistance_zero_results"] = g_zero
                    rec["first_assistance_action_pre_window"] = g_earliest["Action Date"] if g_earliest else ""
                else:
                    rec["unresolved_expansion"] = True
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
        # sam.db enrichment (local)
        srow = sam.execute(
            "SELECT registration_date, activation_date, entity_start_date, state_of_incorporation,"
            " primary_naics, legal_business_name FROM sam_entities WHERE uei = ?", (uei,)
        ).fetchone()
        if srow:
            rec["sam_registration_date"] = srow[0]
            rec["sam_activation_date"] = srow[1]
            rec["sam_entity_start_date"] = srow[2]
            rec["sam_state_of_incorporation"] = srow[3]
            rec["sam_primary_naics"] = srow[4]
            rec["sam_legal_name"] = srow[5]
        else:
            rec["sam_in_local_extract"] = False
        state[uei] = rec
        if i % 10 == 0 or i == len(slice_rows) - 1:
            with open(STATE, "w") as f:
                json.dump(state, f, indent=1)
            print(f"[{i+1}/{len(slice_rows)}] {uei} {v['name'][:40]}")
        time.sleep(0.4)

    with open(STATE, "w") as f:
        json.dump(state, f, indent=1)

    # emit s4 + s5 CSVs
    s4 = []
    s5 = []
    for uei, r in state.items():
        no_contract_hist = r.get("pre_window_contract_zero_results") or (
            not r.get("first_contract_action_pre_window") and not r.get("unresolved_expansion") and "error" not in r)
        new_flag = bool(no_contract_hist and r.get("pre_window_assistance_zero_results", True))
        reg = r.get("sam_registration_date") or ""
        s4.append({
            "recipient_uei": uei, "recipient_name": r["name"],
            "window_obligations": r["window_obligations"], "ceiling_sum": r["ceiling_sum"],
            "first_contract_action_pre_window": r.get("first_contract_action_pre_window", ""),
            "first_contract_award_id": r.get("first_contract_award_id", ""),
            "first_contract_agency": r.get("first_contract_agency", ""),
            "pre_window_contract_zero_results": r.get("pre_window_contract_zero_results", ""),
            "pre_window_assistance_zero_results": r.get("pre_window_assistance_zero_results", ""),
            "first_assistance_action_pre_window": r.get("first_assistance_action_pre_window", ""),
            "unresolved_expansion": r.get("unresolved_expansion", ""),
            "sam_registration_date": reg,
            "sam_activation_date": r.get("sam_activation_date", ""),
            "sam_entity_start_date": r.get("sam_entity_start_date", ""),
            "sam_state_of_incorporation": r.get("sam_state_of_incorporation", ""),
            "sam_registered_post_election": int(bool(reg and reg > "20241105")),
            "flag_new_entrant_post_2024_11_05": int(new_flag),
            "error": r.get("error", ""),
        })
        if r.get("historical_modal_naics") and r.get("dhs_modal_naics"):
            drift = r["historical_modal_naics"] != r["dhs_modal_naics"]
            drift_2digit = r["historical_modal_naics"][:2] != r["dhs_modal_naics"][:2]
            s5.append({
                "recipient_uei": uei, "recipient_name": r["name"],
                "window_obligations": r["window_obligations"],
                "dhs_modal_naics": r["dhs_modal_naics"],
                "historical_modal_naics": r["historical_modal_naics"],
                "historical_sample_n": r.get("historical_naics_sample_n", ""),
                "sam_primary_naics": r.get("sam_primary_naics", ""),
                "naics_differs": int(drift), "naics_differs_2digit": int(drift_2digit),
            })
    s4.sort(key=lambda r: (-r["flag_new_entrant_post_2024_11_05"], -Decimal(r["window_obligations"])))
    with open(os.path.join(WORK, "s4-new-entrants.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(s4[0].keys()))
        w.writeheader()
        w.writerows(s4)
    s5.sort(key=lambda r: (-r["naics_differs_2digit"], -r["naics_differs"], -Decimal(r["window_obligations"])))
    if s5:
        with open(os.path.join(WORK, "s5-naics-drift.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(s5[0].keys()))
            w.writeheader()
            w.writerows(s5)
    n_new = sum(r["flag_new_entrant_post_2024_11_05"] for r in s4)
    print(f"S4: {len(s4)} vendors enriched, {n_new} flagged new-entrant post-2024-11-05")
    print(f"S5: {len(s5)} vendors with historical NAICS sample; "
          f"{sum(r['naics_differs_2digit'] for r in s5)} differ at 2-digit level")


if __name__ == "__main__":
    main()
