#!/usr/bin/env python3
"""Screens S1, S2, S3, S6 over census.db + census-awards.csv (all local).

Outputs (work dir):
  s1-competition-by-component.csv, s1-competition-by-month.csv,
  s1-offers-distribution.csv, s1-otfo-authorities.csv,
  s2-families.csv, s3-ceiling-flags.csv,
  s6-concentration.csv, s6-office-outliers.csv,
  screens-summary.json
"""
import csv
import json
import os
import sqlite3
from collections import Counter, defaultdict
from decimal import Decimal

WORK = "/tmp/osint-GWLtvuxV/work-census"
DB = os.path.join(WORK, "census.db")

csv.field_size_limit(50_000_000)

COMPETED = {"A", "D", "F", "CDO"}
NOT_COMPETED = {"B", "C", "G", "NDO", "E"}


def bucket_ec(code):
    if not code:
        return "blank"
    if code in COMPETED:
        return "competed"
    if code in NOT_COMPETED:
        return "not_competed"
    return f"other({code})"


def bucket_offers(v):
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return "missing"
    if n <= 0:
        return "missing"
    if n == 1:
        return "1"
    if n <= 3:
        return "2-3"
    if n <= 9:
        return "4-9"
    return "10+"


def load_awards():
    awards = {}
    with open(os.path.join(WORK, "census-awards.csv"), newline="") as f:
        for row in csv.DictReader(f):
            awards[row["award_id"]] = row
    return awards


def d(v, default="0"):
    try:
        return Decimal(v if v not in (None, "") else default)
    except Exception:
        return Decimal(default)


def s1(con, summary):
    # transaction-level: dollars (net fao) + action counts by extent_competed bucket
    rows = con.execute(
        "SELECT sub_agency, substr(action_date,1,7) AS ym, ec_code,"
        " COUNT(*), SUM(CAST(fao AS REAL)) FROM txn GROUP BY 1,2,3"
    ).fetchall()
    by_comp = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
    by_month = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
    for comp, ym, ec, n, s in rows:
        b = bucket_ec(ec)
        s = s or 0.0
        by_comp[comp or "(blank)"][b][0] += n
        by_comp[comp or "(blank)"][b][1] += s
        by_month[ym][b][0] += n
        by_month[ym][b][1] += s

    def emit(table, path, keyname):
        buckets = sorted({b for v in table.values() for b in v})
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            hdr = [keyname, "total_actions", "total_dollars"]
            for b in buckets:
                hdr += [f"{b}_actions", f"{b}_dollars", f"{b}_action_share", f"{b}_dollar_share"]
            w.writerow(hdr)
            for k in sorted(table, key=lambda k: -sum(v[1] for v in table[k].values())):
                tn = sum(v[0] for v in table[k].values())
                ts = sum(v[1] for v in table[k].values())
                row = [k, tn, round(ts, 2)]
                for b in buckets:
                    n, s = table[k].get(b, [0, 0.0])
                    row += [n, round(s, 2),
                            round(n / tn, 4) if tn else "",
                            round(s / ts, 4) if ts else ""]
                w.writerow(row)

    emit(by_comp, os.path.join(WORK, "s1-competition-by-component.csv"), "component")
    emit(by_month, os.path.join(WORK, "s1-competition-by-month.csv"), "month")

    # DHS-wide baseline (dollar-weighted)
    tot = defaultdict(lambda: [0, 0.0])
    for comp in by_comp.values():
        for b, (n, s) in comp.items():
            tot[b][0] += n
            tot[b][1] += s
    all_n = sum(v[0] for v in tot.values())
    all_s = sum(v[1] for v in tot.values())
    summary["s1_dhs_baseline"] = {
        b: {"actions": v[0], "dollars": round(v[1], 2),
            "action_share": round(v[0] / all_n, 4), "dollar_share": round(v[1] / all_s, 4)}
        for b, v in sorted(tot.items())
    }

    # offers distribution: award level (all kept awards + born-in-window)
    awards = load_awards()
    dist_all, dist_new = Counter(), Counter()
    dol_all, dol_new = defaultdict(Decimal), defaultdict(Decimal)
    for a in awards.values():
        b = bucket_offers(a["offers_received"])
        wo = d(a["window_obligations"])
        dist_all[b] += 1
        dol_all[b] += wo
        if a["born_in_window"] == "1":
            dist_new[b] += 1
            dol_new[b] += wo
    with open(os.path.join(WORK, "s1-offers-distribution.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["offers_bucket", "awards_all", "window_dollars_all", "awards_born_in_window", "window_dollars_born_in_window"])
        for b in ["1", "2-3", "4-9", "10+", "missing"]:
            w.writerow([b, dist_all[b], dol_all[b], dist_new[b], dol_new[b]])
    summary["s1_offers_born_in_window"] = {b: dist_new[b] for b in dist_new}

    # other-than-full-and-open authorities (award level + dollar weighted, born-in-window facet)
    auth = defaultdict(lambda: [0, Decimal(0), 0, Decimal(0)])
    for a in awards.values():
        code = a["other_than_full_open_competition"] or a["other_than_full_open_competition_code"]
        if not code:
            continue
        wo = d(a["window_obligations"])
        rec = auth[code]
        rec[0] += 1
        rec[1] += wo
        if a["born_in_window"] == "1":
            rec[2] += 1
            rec[3] += wo
    with open(os.path.join(WORK, "s1-otfo-authorities.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["authority", "awards", "window_dollars", "awards_born_in_window", "window_dollars_born_in_window"])
        for code, (n, s, nn, sn) in sorted(auth.items(), key=lambda kv: -kv[1][1]):
            w.writerow([code, n, s, nn, sn])
    summary["s1_otfo_top"] = [
        {"authority": c, "awards": v[0], "window_dollars": str(v[1])}
        for c, v in sorted(auth.items(), key=lambda kv: -kv[1][1])[:8]
    ]


def s2(con, summary):
    # FULL award universe (not just >=250K kept) so family membership is complete
    cur = con.execute("SELECT * FROM award")
    cols = [d[0] for d in cur.description]
    fams = defaultdict(list)
    for row in cur:
        a = dict(zip(cols, row))
        sol = (a["solicitation_id"] or "").strip().upper()
        if sol:
            fams[sol].append(a)
    out = []
    for sol, members in fams.items():
        ueis = {m["recipient_uei"] for m in members if m["recipient_uei"]}
        if len(ueis) < 2:
            continue
        offers = Counter(m["offers_received"] for m in members if m["offers_received"])
        modal_offers = offers.most_common(1)[0][0] if offers else ""
        try:
            modal_n = int(float(modal_offers))
        except (TypeError, ValueError):
            modal_n = None
        ceiling = sum(d(m["current_ceiling"]) for m in members)
        wobl = sum(d(m["window_obligations"]) for m in members)
        member_piids = {m["piid"] for m in members if m["piid"]}
        # child task order obligations for IDV members
        placeholders = ",".join("?" * len(member_piids))
        child = con.execute(
            f"SELECT COALESCE(SUM(CAST(fao AS REAL)),0) FROM txn WHERE parent_piid IN ({placeholders})"
            " AND award_key NOT IN (SELECT award_key FROM txn WHERE piid IN (" + placeholders + "))",
            list(member_piids) * 2,
        ).fetchone()[0]
        n_awardees = len(ueis)
        everyone_won = modal_n is not None and modal_n == n_awardees
        member_ceils = [d(m["current_ceiling"]) for m in members if d(m["current_ceiling"]) > 0]
        distinct_ceils = set(member_ceils)
        shared_ceiling = len(members) >= 3 and len(distinct_ceils) == 1 and len(member_ceils) >= 3
        out.append({
            "solicitation_id": sol,
            "n_awards": len(members),
            "n_distinct_awardees": n_awardees,
            "modal_offers_received": modal_offers,
            "offers_values_seen": ";".join(f"{k}x{v}" for k, v in offers.most_common()),
            "everyone_who_offered_won": int(everyone_won),
            "awardees_exceed_offers": int(modal_n is not None and n_awardees > modal_n),
            "shared_ceiling_suspected": int(shared_ceiling),
            "shared_or_max_ceiling": str(max(member_ceils) if member_ceils else Decimal(0)),
            "family_ceiling_sum": str(ceiling),
            "family_window_obligations_members": str(wobl),
            "child_task_order_window_obligations": round(child, 2),
            "any_idv": int(any(m["is_idv"] == "1" for m in members)),
            "components": ";".join(sorted({m["awarding_subagency"] or "" for m in members})),
            "sample_recipients": ";".join(sorted({m["recipient_name"] for m in members})[:6]),
        })
    out.sort(key=lambda r: (-r["everyone_who_offered_won"], -Decimal(r["family_ceiling_sum"])))
    with open(os.path.join(WORK, "s2-families.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    summary["s2_families_multi_awardee"] = len(out)
    summary["s2_everyone_won"] = sum(r["everyone_who_offered_won"] for r in out)
    summary["s2_top_everyone_won"] = [
        {k: r[k] for k in ("solicitation_id", "n_distinct_awardees", "modal_offers_received",
                           "shared_ceiling_suspected", "shared_or_max_ceiling", "family_ceiling_sum",
                           "child_task_order_window_obligations", "components")}
        for r in out if r["everyone_who_offered_won"]
    ][:12]


def s3(con, summary):
    awards = load_awards()
    flags = []
    # child obligations per parent piid (for IDV utilization)
    child_obl = dict(con.execute(
        "SELECT parent_piid, SUM(CAST(fao AS REAL)) FROM txn WHERE parent_piid != '' GROUP BY parent_piid"
    ).fetchall())
    # ceiling drop events from ledger
    drops = defaultdict(list)
    for ak, dt, mod, baov, pot in con.execute(
        "SELECT award_key, action_date, mod, CAST(baov AS REAL), CAST(potential AS REAL) FROM txn"
        " WHERE CAST(baov AS REAL) <= -10000000"
    ):
        drops[ak].append((dt, mod, baov, pot))

    for a in awards.values():
        cur = d(a["current_ceiling"])
        reasons = []
        details = {}
        base = d(a["start_of_window_ceiling"])
        start = base if base > 0 else None
        if start and cur > 2 * start:
            reasons.append("ceiling_growth_gt2x_in_window")
            details["start_ceiling"] = str(start)
        if a["award_id"] in drops:
            reasons.append("ceiling_cut_ge_10M")
            details["cuts"] = "; ".join(f"{dt} mod {m}: {b:,.0f} -> after {p:,.0f}" for dt, m, b, p in drops[a["award_id"]][:4])
        # capacity parking -- only for vehicles at least 180 days old (new vehicles
        # with only minimum guarantees obligated are just new, not parked)
        age_qualifies = a["first_action_date"] <= "2026-01-29" or a["born_in_window"] != "1"
        if cur >= Decimal(50_000_000) and age_qualifies:
            if a["is_idv"] == "1":
                obl = Decimal(str(child_obl.get(a["piid"], 0) or 0)) + d(a["total_obligations_todate"])
                complete = a["born_in_window"] == "1"
            else:
                obl = d(a["total_obligations_todate"])
                complete = True
            if cur > 0 and obl / cur <= Decimal("0.05"):
                reasons.append("capacity_parking_ceiling50M_le5pct")
                details["obligated_for_ratio"] = str(obl)
                details["child_sum_complete"] = int(complete)
                details["first_action_in_window"] = a["first_action_date"]
        # born-in-window growth: current vs first-action ceiling from ledger
        if reasons:
            flags.append({
                "award_id": a["award_id"], "piid": a["piid"], "is_idv": a["is_idv"],
                "recipient_name": a["recipient_name"],
                "component": a["awarding_subagency"],
                "current_ceiling": str(cur),
                "window_obligations": a["window_obligations"],
                "total_obligations_todate": a["total_obligations_todate"],
                "born_in_window": a["born_in_window"],
                "flags": ";".join(reasons),
                "detail": json.dumps(details),
                "description_snippet": a["description_snippet"][:120],
            })
    # growth for born-in-window awards needs first-action ceiling: fetch from ledger
    first_ceil = {}
    cur2 = con.execute(
        "SELECT award_key, action_date, mod, txn_num, potential FROM txn ORDER BY award_key, action_date, mod, txn_num"
    )
    seen = set()
    for ak, dt, mod, tn, pot in cur2:
        if ak in seen:
            continue
        seen.add(ak)
        try:
            first_ceil[ak] = Decimal(pot) if pot else None
        except Exception:
            first_ceil[ak] = None
    growth_flags = []
    for a in awards.values():
        if a["born_in_window"] != "1":
            continue
        fc = first_ceil.get(a["award_id"])
        cur = d(a["current_ceiling"])
        if fc and fc > 0 and cur > 2 * fc and cur >= Decimal(1_000_000):
            growth_flags.append({
                "award_id": a["award_id"], "piid": a["piid"], "is_idv": a["is_idv"],
                "recipient_name": a["recipient_name"], "component": a["awarding_subagency"],
                "current_ceiling": str(cur), "window_obligations": a["window_obligations"],
                "total_obligations_todate": a["total_obligations_todate"],
                "born_in_window": "1",
                "flags": "ceiling_growth_gt2x_from_initial",
                "detail": json.dumps({"initial_ceiling": str(fc), "growth_x": float(cur / fc)}),
                "description_snippet": a["description_snippet"][:120],
            })
    flags.extend(growth_flags)
    flags.sort(key=lambda r: -Decimal(r["current_ceiling"] or "0"))
    with open(os.path.join(WORK, "s3-ceiling-flags.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flags[0].keys()))
        w.writeheader()
        w.writerows(flags)
    summary["s3_flag_counts"] = dict(Counter(fl for r in flags for fl in r["flags"].split(";")))
    summary["s3_top"] = [
        {k: r[k] for k in ("piid", "recipient_name", "component", "current_ceiling", "total_obligations_todate", "flags")}
        for r in flags[:12]
    ]


def s6(con, summary):
    awards = load_awards()
    by_recip = defaultdict(lambda: {"wobl": Decimal(0), "ceiling": Decimal(0), "n": 0, "ncomp_wobl": Decimal(0), "names": Counter()})
    member_piids = {a["piid"] for a in awards.values() if a["is_idv"] == "1"}
    for a in awards.values():
        key = a["recipient_uei"] or a["recipient_name"]
        rec = by_recip[key]
        rec["wobl"] += d(a["window_obligations"])
        # avoid double counting ceilings: skip task orders under an in-census IDV
        if not (a["parent_idv_piid"] and a["parent_idv_piid"] in member_piids):
            rec["ceiling"] += d(a["current_ceiling"])
        rec["n"] += 1
        rec["names"][a["recipient_name"]] += 1
        if bucket_ec(a["extent_competed_code"]) == "not_competed":
            rec["ncomp_wobl"] += d(a["window_obligations"])
    rows = []
    for uei, rec in by_recip.items():
        rows.append({
            "recipient_uei": uei,
            "recipient_name": rec["names"].most_common(1)[0][0],
            "n_awards": rec["n"],
            "window_obligations": str(rec["wobl"]),
            "ceiling_sum_no_double_count": str(rec["ceiling"]),
            "not_competed_window_obligations": str(rec["ncomp_wobl"]),
            "not_competed_share": round(float(rec["ncomp_wobl"] / rec["wobl"]), 4) if rec["wobl"] > 0 else "",
        })
    rows.sort(key=lambda r: -Decimal(r["window_obligations"]))
    with open(os.path.join(WORK, "s6-concentration.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows[:200])
    summary["s6_top10_by_window_obligations"] = [
        {k: r[k] for k in ("recipient_name", "window_obligations", "not_competed_share")} for r in rows[:10]
    ]
    by_ceiling = sorted(rows, key=lambda r: -Decimal(r["ceiling_sum_no_double_count"]))
    summary["s6_top10_by_ceiling"] = [
        {k: r[k] for k in ("recipient_name", "ceiling_sum_no_double_count", "window_obligations")} for r in by_ceiling[:10]
    ]

    # office outliers: not-competed dollar share vs DHS baseline (transaction level)
    base = con.execute(
        "SELECT SUM(CASE WHEN ec_code IN ('B','C','G','NDO','E') THEN CAST(fao AS REAL) ELSE 0 END),"
        " SUM(CAST(fao AS REAL)) FROM txn"
    ).fetchone()
    dhs_share = (base[0] or 0) / base[1] if base[1] else 0
    offices = con.execute(
        "SELECT office_code, office, sub_agency,"
        " SUM(CASE WHEN ec_code IN ('B','C','G','NDO','E') THEN CAST(fao AS REAL) ELSE 0 END) nc,"
        " SUM(CAST(fao AS REAL)) tot, COUNT(*) n FROM txn GROUP BY 1,2,3 HAVING tot >= 10000000"
    ).fetchall()
    out = []
    for oc, on, comp, nc, tot, n in offices:
        share = nc / tot if tot else 0
        if share >= max(2 * dhs_share, 0.5):
            out.append({
                "office_code": oc, "office_name": on, "component": comp,
                "window_obligations": round(tot, 2), "not_competed_dollars": round(nc, 2),
                "not_competed_share": round(share, 4), "dhs_baseline_share": round(dhs_share, 4),
                "actions": n,
            })
    out.sort(key=lambda r: -r["not_competed_dollars"])
    with open(os.path.join(WORK, "s6-office-outliers.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()) if out else ["none"])
        if out:
            w.writeheader()
            w.writerows(out)
    summary["s6_dhs_notcompeted_dollar_share"] = round(dhs_share, 4)
    summary["s6_office_outliers"] = len(out)


def main():
    con = sqlite3.connect(DB)
    summary = {}
    s1(con, summary)
    print("S1 done")
    s2(con, summary)
    print("S2 done")
    s3(con, summary)
    print("S3 done")
    s6(con, summary)
    print("S6 done")
    with open(os.path.join(WORK, "screens-summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(json.dumps(summary, indent=2, default=str)[:4000])


if __name__ == "__main__":
    main()
