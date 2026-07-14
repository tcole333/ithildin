"""Corpus coverage-gap analysis: most-mentioned kabasshouse entities vs epstein-profile findings.

Filters out mass-mail noise (newsletters, market updates, press releases, news clippings)
before counting mentions, then ranks entities by clean page count where findings coverage
is low or absent.

Outputs:
  reports/coverage-gap-persons-latest.csv / coverage-gap-orgs-latest.csv - full ranked tables
  summary printed to stdout
"""
import pathlib
import sqlite3
import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
KAB = f"{ROOT}/datasets/kabasshouse_epstein.db"
DER = f"{ROOT}/datasets/epstein_derived.db"
INV = f"{ROOT}/investigation.db"
OUT = f"{ROOT}/reports"

# ---------------------------------------------------------------- noise pages
NOISE_TYPE_SQL = """
    (document_type LIKE '%article%' AND document_type NOT LIKE '%incorporation%'
        AND document_type NOT LIKE '%organization%' AND document_type NOT LIKE '%association%')
    OR document_type LIKE '%news%'
    OR document_type LIKE '%press release%'
    OR document_type LIKE '%press clipping%'
    OR document_type LIKE '%newsletter%'
    OR document_type IN (
        'Research Report','Equity Research Ratings','Research Profile','Magazine Cover',
        'magazine','Newspaper','newspaper','Bulletin','Weekly Bulletin','Email Digest',
        'Press Clippings','Newspaper Clipping','News Clips','News Broadcast',
        'Social Media Post','social media post','Media Article','Journal Article',
        'Academic Journal Article','List of Articles','Alert')
"""

# FTS phrase markers for mass-mail / newsletter / press-release boilerplate.
FTS_MARKERS = [
    "unsubscribe",
    '"you are receiving this"',
    '"view this email in your browser"',
    '"if you no longer wish to receive"',
    '"manage your subscription"',
    '"email preferences"',
    '"mailing list"',
    '"was sent to you"',
    '"for immediate release"',
    '"national press office"',
    '"fbi press office"',
    '"market update"',
    '"market commentary"',
    '"morning briefing"',
    '"daily briefing"',
    '"news briefing"',
    '"media coverage"',
    '"press coverage"',
]

# Masthead / source-name markers for recurring bulk sources found on inspection.
# (second-pass; extended after sampling residual top gaps)
MASTHEADS = []

TITLES = {"mr", "mrs", "ms", "dr", "mme", "sir", "jr", "sr", "ii", "iii", "prof",
          "mister", "madam", "esq", "hon", "rev", "capt", "lt", "col", "gen"}
ORG_STOP = {"llc", "ltd", "inc", "lp", "llp", "corp", "co", "company", "limited",
            "the", "of", "and", "group", "corporation", "incorporated", "plc", "sa", "ag"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def person_tokens(s):
    toks = [t for t in norm(s).split() if len(t) >= 2 and t not in TITLES]
    return frozenset(toks)


def org_tokens(s):
    toks = [t for t in norm(s).split() if t not in ORG_STOP and len(t) >= 2]
    return frozenset(toks)


def main():
    kab = sqlite3.connect(KAB)
    kab.execute(f"ATTACH DATABASE '{DER}' AS der")

    # ---- 1. build noise page-id set --------------------------------------
    print("== building noise page set ==", flush=True)
    noise_ids = set()
    for (i,) in kab.execute(f"SELECT id FROM documents WHERE {NOISE_TYPE_SQL}"):
        noise_ids.add(i)
    typed = len(noise_ids)
    print(f"  typed noise pages: {typed}", flush=True)

    for m in FTS_MARKERS + MASTHEADS:
        q = f'"full_text" : {m}' if not m.startswith('"') else f'"full_text" : {m}'
        try:
            rows = kab.execute(
                "SELECT d.id FROM documents_fts f JOIN documents d ON d.rowid = f.rowid "
                "WHERE documents_fts MATCH ?", (q,)).fetchall()
        except sqlite3.OperationalError as e:
            print(f"  marker {m!r} FAILED: {e}", flush=True)
            continue
        before = len(noise_ids)
        noise_ids.update(r[0] for r in rows)
        print(f"  marker {m}: {len(rows)} pages (+{len(noise_ids)-before} new)", flush=True)
    print(f"  TOTAL noise pages: {len(noise_ids)}", flush=True)

    kab.execute("CREATE TEMP TABLE noise (id TEXT PRIMARY KEY)")
    kab.executemany("INSERT OR IGNORE INTO noise VALUES (?)", ((i,) for i in noise_ids))

    # ---- 2. person mention counts (canonical, clean vs total) ------------
    print("== counting person mentions ==", flush=True)
    rows = kab.execute("""
        SELECT COALESCE(pm.canonical_id, -1) AS cid, e.value,
               COUNT(DISTINCT e.document_id) AS pages,
               COUNT(DISTINCT CASE WHEN n.id IS NULL THEN e.document_id END) AS clean_pages
        FROM entities e
        JOIN documents d ON d.id = e.document_id
        LEFT JOIN der.person_mention pm ON pm.raw_value = e.value
        LEFT JOIN noise n ON n.id = e.document_id
        WHERE e.entity_type = 'person'
        GROUP BY cid, e.value
    """).fetchall()
    print(f"  raw person value rows: {len(rows)}", flush=True)

    canon = {}   # person_id -> (name, category)
    for pid, name, cat in kab.execute(
            "SELECT person_id, canonical_name, category FROM der.canonical_person"):
        canon[pid] = (name, cat or "")

    # aggregate by token-set key so duplicate clusters (Larry Visoski / Larry Visoski Larry) merge.
    # CRITICAL: only count raw variants that are themselves multi-token names — the resolver
    # folds bare first names ("Richard", "Larry") into clusters, wildly inflating page counts.
    persons = {}   # key -> dict
    for cid, raw, pages, clean in rows:
        if len(person_tokens(raw)) < 2:
            continue    # bare-name mention: ambiguous, excluded from counts
        if cid == -1:
            name, cat = raw, ""
        else:
            name, cat = canon.get(cid, (raw, ""))
        toks = person_tokens(name)
        if len(toks) < 2:
            toks = person_tokens(raw)
        key = toks
        p = persons.setdefault(key, {
            "name": name, "category": cat, "pages": 0, "clean": 0,
            "variants": Counter(), "cids": set()})
        p["pages"] += pages
        p["clean"] += clean
        p["variants"][raw] += pages
        if cid != -1:
            p["cids"].add(cid)
        # prefer the longest canonical name as display
        if len(name) > len(p["name"]):
            p["name"] = name
        if cat and not p["category"]:
            p["category"] = cat

    print(f"  merged person clusters: {len(persons)}", flush=True)

    JE_FIRST = {"jeff", "jeffrey", "jeffery", "je", "jeffreye", "jefferey"}
    def is_self(toks):
        return "epstein" in toks and any(t in JE_FIRST for t in toks) \
            and not ({"mark", "edward", "paula", "seymour"} & set(toks))

    # ---- 3. org mention counts -------------------------------------------
    print("== counting org mentions ==", flush=True)
    org_rows = kab.execute("""
        SELECT COALESCE(NULLIF(e.normalized_value,''), e.value) AS nv,
               MAX(e.value) AS display,
               COUNT(DISTINCT e.document_id) AS pages,
               COUNT(DISTINCT CASE WHEN n.id IS NULL THEN e.document_id END) AS clean_pages
        FROM entities e
        JOIN documents d ON d.id = e.document_id
        LEFT JOIN noise n ON n.id = e.document_id
        WHERE e.entity_type = 'organization'
        GROUP BY nv
    """).fetchall()
    # brand collapse: OCR fragments many spellings of the big institutions
    BRANDS = [
        ({"jpmorgan"}, "JPMorgan Chase"), ({"jp", "morgan"}, "JPMorgan Chase"),
        ({"jpmorganchase"}, "JPMorgan Chase"), ({"jpmc"}, "JPMorgan Chase"),
        ({"chase", "manhattan"}, "JPMorgan Chase"),
        ({"deutsche"}, "Deutsche Bank"),
        ({"amex"}, "American Express"), ({"american", "express"}, "American Express"),
        ({"bear", "stearns"}, "Bear Stearns"),
        ({"citibank"}, "Citigroup"), ({"citigroup"}, "Citigroup"),
        ({"goldman"}, "Goldman Sachs"),
        ({"morgan", "stanley"}, "Morgan Stanley"),
        ({"merrill"}, "Merrill Lynch"),
        ({"ubs"}, "UBS"), ({"hsbc"}, "HSBC"), ({"barclays"}, "Barclays"),
        ({"bank", "america"}, "Bank of America"),
        ({"wells", "fargo"}, "Wells Fargo"),
        ({"fedex"}, "FedEx"), ({"tmobile"}, "T-Mobile"), ({"mobile"}, "T-Mobile"),
        ({"att"}, "AT&T"), ({"verizon"}, "Verizon"),
        ({"fbi"}, "FBI"), ({"bloomberg"}, "Bloomberg"),
        ({"lehman"}, "Lehman Brothers"),
        ({"first", "union"}, "First Union"),
        ({"southern", "trust"}, "Southern Trust Company"),
        ({"financial", "trust"}, "Financial Trust Company"),
        ({"hyperion"}, "Hyperion Air"),
        ({"gratitude", "america"}, "Gratitude America"),
        ({"coq", "hardi"}, "Le Coq Hardi"),
        ({"hbrk"}, "HBRK Associates"),
        ({"nes", "llc"}, "NES LLC"), ({"cypress"}, "Cypress Inc"),
        ({"maple"}, "Maple Inc"), ({"laurel"}, "Laurel Inc"),
    ]

    def brand_key(toks):
        for pat, label in BRANDS:
            if pat <= toks:
                return frozenset(norm(label).split()), label
        return toks, None

    orgs = {}
    for nv, display, pages, clean in org_rows:
        toks = org_tokens(nv)
        if not toks:
            continue
        key, label = brand_key(toks)
        o = orgs.setdefault(key, {"name": label or display, "pages": 0, "clean": 0,
                                  "branded": bool(label)})
        o["pages"] += pages
        o["clean"] += clean
        if not o["branded"] and len(display) > len(o["name"]):
            o["name"] = display
    print(f"  merged org clusters: {len(orgs)}", flush=True)
    kab.close()

    # ---- 4. findings coverage (epstein profile) ---------------------------
    print("== loading findings (epstein profile) ==", flush=True)
    inv = sqlite3.connect(INV)
    findings = inv.execute("""
        SELECT id, target_name, COALESCE(summary,''), COALESCE(detail,'')
        FROM findings WHERE profile_id = 'epstein'
    """).fetchall()
    print(f"  epstein findings: {len(findings)}", flush=True)

    target_fids = defaultdict(set)      # tokenset of target_name -> finding ids (both tokenizations)
    target_keys = []                     # (tokenset, fid) list for subset matching
    texts = []                           # (fid, lowered text) for substring scan
    for fid, tname, summ, det in findings:
        for ts in {person_tokens(tname), org_tokens(tname)}:
            if ts:
                target_fids[ts].add(fid)
                target_keys.append((ts, fid))
        texts.append((fid, norm(tname + " " + summ + " " + det)))

    # entity-linked findings
    ent_fids = defaultdict(set)
    for fid, eid in inv.execute("""
        SELECT f.id, fe.entity_id FROM finding_entities fe
        JOIN findings f ON f.id = fe.finding_id WHERE f.profile_id = 'epstein'
    """):
        ent_fids[eid].add(fid)

    ent_name_ids = defaultdict(set)     # tokenset -> entity ids
    for eid, name in inv.execute("SELECT id, name FROM entities"):
        ent_name_ids[person_tokens(name)].add(eid)
        ent_name_ids[org_tokens(name)].add(eid)
    for alias, eid, canonical in inv.execute(
            "SELECT alias, entity_id, canonical_name FROM name_aliases"):
        if eid:
            ent_name_ids[person_tokens(alias)].add(eid)
        # alias -> canonical target_name bridging
        if canonical:
            target_fids[person_tokens(alias)] |= target_fids.get(person_tokens(canonical), set())
    inv.close()

    def coverage(tokensets, variants_for_text):
        """union of finding ids reachable by name match (exact or subset); plus substring hits"""
        fids = set()
        tokensets = [ts for ts in tokensets if ts]
        for ts in tokensets:
            fids |= target_fids.get(ts, set())
            for eid in ent_name_ids.get(ts, set()):
                fids |= ent_fids.get(eid, set())
        # subset match: "Prince Andrew" vs target "Prince Andrew (Duke of York)",
        # or target "Larry Visoski" vs cluster "Larry Visoski Larry"
        for tts, fid in target_keys:
            if fid in fids:
                continue
            for ts in tokensets:
                if (len(ts) >= 2 and ts <= tts) or (len(tts) >= 2 and tts <= ts):
                    fids.add(fid)
                    break
        # substring scan (any full variant string >= 8 chars appearing in finding text)
        subs = [norm(v) for v in variants_for_text
                if len(norm(v)) >= 8 and len(person_tokens(v)) >= 2]
        text_hits = set()
        if subs:
            for fid, txt in texts:
                if any(s in txt for s in subs):
                    text_hits.add(fid)
        return fids, text_hits

    # ---- 5. score top persons ---------------------------------------------
    print("== scoring top persons ==", flush=True)
    top_p = sorted(persons.items(), key=lambda kv: -kv[1]["clean"])[:600]
    p_out = []
    for key, p in top_p:
        variants = [v for v, _ in p["variants"].most_common(6)]
        exact, textual = coverage([key] + [person_tokens(v) for v in variants], variants + [p["name"]])
        flags = "SELF" if is_self(key) else ""
        p_out.append({
            "name": p["name"], "category": p["category"], "flags": flags,
            "clean_pages": p["clean"], "total_pages": p["pages"],
            "noise_pct": round(100 * (1 - p["clean"] / p["pages"]), 1) if p["pages"] else 0,
            "findings_exact": len(exact), "findings_text": len(textual),
            "variants": "; ".join(variants[:4]),
        })

    print("== scoring top orgs ==", flush=True)
    top_o = sorted(orgs.items(), key=lambda kv: -kv[1]["clean"])[:400]
    o_out = []
    for key, o in top_o:
        exact, textual = coverage([key], [o["name"]])
        o_out.append({
            "name": o["name"],
            "clean_pages": o["clean"], "total_pages": o["pages"],
            "noise_pct": round(100 * (1 - o["clean"] / o["pages"]), 1) if o["pages"] else 0,
            "findings_exact": len(exact), "findings_text": len(textual),
        })

    # ---- 6. write ----------------------------------------------------------
    with open(f"{OUT}/coverage-gap-persons-latest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(p_out[0].keys()))
        w.writeheader()
        w.writerows(p_out)
    with open(f"{OUT}/coverage-gap-orgs-latest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(o_out[0].keys()))
        w.writeheader()
        w.writerows(o_out)

    print("\n==== TOP 50 PERSON GAPS (clean pages, <=2 findings, non-self) ====")
    gaps = [p for p in p_out if p["findings_exact"] <= 2 and not p["flags"]]
    for p in gaps[:50]:
        print(f"  {p['clean_pages']:>7}  (tot {p['total_pages']:>7}, noise {p['noise_pct']:>5}%)  "
              f"exact={p['findings_exact']} text={p['findings_text']}  "
              f"{p['name']}  [{p['category']}]  vars: {p['variants'][:70]}")

    print("\n==== TOP 40 ORG GAPS (clean pages, <=2 findings) ====")
    ogaps = [o for o in o_out if o["findings_exact"] <= 2]
    for o in ogaps[:40]:
        print(f"  {o['clean_pages']:>7}  (tot {o['total_pages']:>7}, noise {o['noise_pct']:>5}%)  "
              f"exact={o['findings_exact']} text={o['findings_text']}  {o['name']}")

    print("\n==== CONTEXT: TOP 25 PERSONS OVERALL ====")
    for p in p_out[:25]:
        print(f"  {p['clean_pages']:>7}  exact={p['findings_exact']:>4} text={p['findings_text']:>4}  "
              f"{p['name']}  [{p['category']}] {p['flags']}")

    print("\ndone. CSVs in", OUT)


if __name__ == "__main__":
    main()
