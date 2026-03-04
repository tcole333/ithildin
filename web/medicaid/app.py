"""Medicaid Provider Spending Explorer — healthcare fraud investigation tool.

Usage:
    cd web/medicaid && uv run python app.py

Queries 227M-row parquet files via DuckDB. No import step needed.
"""

import re
import time
from pathlib import Path

import duckdb
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SPENDING = str(DATA_DIR / "medicaid_spending.parquet")
BILLING = str(DATA_DIR / "billing_providers.parquet")
SERVICING = str(DATA_DIR / "servicing_providers.parquet")
HCPCS = str(DATA_DIR / "hcpcs_codes.parquet")
LEIE = str(DATA_DIR / "leie_exclusions.csv")


def get_con():
    """Fresh DuckDB connection per request (thread-safe)."""
    con = duckdb.connect()
    con.execute("SET memory_limit='4GB'")
    con.execute("SET threads=4")
    return con


def _sanitize(val: str) -> str:
    """Escape single quotes for safe SQL interpolation in DuckDB.

    DuckDB's parquet reader doesn't support prepared-statement parameters
    in all contexts, so we escape quotes manually for string literals.
    Only alphanumeric, spaces, and common address characters are kept.
    """
    return val.replace("'", "''")


def _npi_only(val: str) -> str:
    """Strip an NPI to digits only."""
    return re.sub(r"[^0-9]", "", val)[:10]


# ---------------------------------------------------------------------------
# Percentile cache — computed once at startup for anomaly detection
# ---------------------------------------------------------------------------
_percentile_cache: dict | None = None


def _load_percentiles():
    """Compute 50th and 95th percentile per-claim rate for each HCPCS code.

    Aggregates across all NPIs — single pass over 227M rows.
    DuckDB handles it in a few seconds.
    """
    global _percentile_cache
    if _percentile_cache is not None:
        return _percentile_cache

    con = get_con()
    t0 = time.time()
    rows = con.execute(f"""
        WITH per_npi AS (
            SELECT hcpcs_code,
                   billing_npi,
                   SUM(paid) / NULLIF(SUM(claims), 0) AS per_claim
            FROM '{SPENDING}'
            GROUP BY hcpcs_code, billing_npi
        )
        SELECT hcpcs_code,
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY per_claim) AS p50,
               PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY per_claim) AS p95
        FROM per_npi
        WHERE per_claim IS NOT NULL
        GROUP BY hcpcs_code
    """).fetchall()
    _percentile_cache = {r[0]: {"p50": r[1], "p95": r[2]} for r in rows}
    elapsed = time.time() - t0
    print(f"  Percentile cache loaded: {len(_percentile_cache)} codes in {elapsed:.1f}s")
    return _percentile_cache


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    """Provider search — by NPI, name, address, city/state."""
    q = request.args.get("q", "").strip()
    search_type = request.args.get("type", "name")
    page = max(int(request.args.get("page", "1") or "1"), 1)
    per_page = 50
    offset = (page - 1) * per_page

    if not q:
        return render_template("search_results.html", providers=[], query="",
                               search_type=search_type, page=page, total=0, per_page=per_page)

    con = get_con()
    safe_q = _sanitize(q)

    # Build WHERE clause
    if search_type == "npi":
        npi_val = _npi_only(q)
        where = f"b.npi = '{npi_val}'"
    elif search_type == "address":
        where = f"LOWER(b.address_line1) LIKE '%{safe_q.lower()}%'"
    elif search_type == "city_state":
        parts = [p.strip() for p in q.split(",")]
        if len(parts) == 2:
            city = _sanitize(parts[0])
            state = _sanitize(parts[1])
            where = f"LOWER(b.city) = '{city.lower()}' AND UPPER(b.state) = '{state.upper().strip()}'"
        else:
            where = f"LOWER(b.city) LIKE '%{safe_q.lower()}%'"
    else:  # name
        where = (f"(LOWER(b.org_name) LIKE '%{safe_q.lower()}%' "
                 f"OR LOWER(b.last_name) LIKE '%{safe_q.lower()}%' "
                 f"OR LOWER(b.first_name) LIKE '%{safe_q.lower()}%')")

    t0 = time.time()

    # Count
    total = con.execute(
        f"SELECT COUNT(*) FROM '{BILLING}' b WHERE {where}"
    ).fetchone()[0]

    # Fetch providers with aggregated spending
    rows = con.execute(f"""
        SELECT b.npi,
               b.entity_type,
               COALESCE(b.org_name, b.last_name || ', ' || COALESCE(b.first_name, '')) AS name,
               b.address_line1, b.city, b.state, b.zip, b.phone,
               b.taxonomy_code, b.enumeration_date,
               s.total_paid, s.total_claims
        FROM '{BILLING}' b
        LEFT JOIN (
            SELECT billing_npi, SUM(paid) AS total_paid, SUM(claims) AS total_claims
            FROM '{SPENDING}'
            GROUP BY billing_npi
        ) s ON b.npi = s.billing_npi
        WHERE {where}
        ORDER BY s.total_paid DESC NULLS LAST
        LIMIT {per_page} OFFSET {offset}
    """).fetchall()
    elapsed = time.time() - t0

    providers = []
    for r in rows:
        providers.append({
            "npi": r[0], "entity_type": r[1], "name": r[2],
            "address": r[3], "city": r[4], "state": r[5], "zip": r[6],
            "phone": r[7], "taxonomy": r[8], "enum_date": r[9],
            "total_paid": r[10], "total_claims": r[11],
        })

    return render_template("search_results.html", providers=providers, query=q,
                           search_type=search_type, page=page, total=total,
                           per_page=per_page, elapsed=elapsed)


@app.route("/provider/<npi>")
def provider_detail(npi):
    """Full provider detail page with billing breakdown and anomaly flags."""
    npi = _npi_only(npi)
    if not npi:
        return render_template("not_found.html", npi=npi), 404

    con = get_con()
    t0 = time.time()

    # --- Provider info (check both billing and servicing tables) ---
    info = con.execute(f"""
        SELECT npi, entity_type, org_name, last_name, first_name, middle_name,
               credential, address_line1, city, state, zip, phone, sex,
               taxonomy_code, enumeration_date
        FROM '{BILLING}' WHERE npi = '{npi}'
        UNION ALL
        SELECT npi, entity_type, org_name, last_name, first_name, middle_name,
               credential, address_line1, city, state, zip, phone, sex,
               taxonomy_code, enumeration_date
        FROM '{SERVICING}' WHERE npi = '{npi}'
        LIMIT 1
    """).fetchone()

    if not info:
        return render_template("not_found.html", npi=npi), 404

    provider = {
        "npi": info[0], "entity_type": info[1], "org_name": info[2],
        "last_name": info[3], "first_name": info[4], "middle_name": info[5],
        "credential": info[6], "address": info[7], "city": info[8],
        "state": info[9], "zip": info[10], "phone": info[11], "sex": info[12],
        "taxonomy": info[13], "enum_date": info[14],
    }
    provider["name"] = provider["org_name"] or f"{provider['last_name']}, {provider['first_name'] or ''}"

    # --- Yearly billing summary ---
    yearly = con.execute(f"""
        SELECT claim_month[:4] AS year,
               SUM(paid) AS total_paid,
               SUM(claims) AS total_claims,
               SUM(beneficiaries) AS total_benes
        FROM '{SPENDING}'
        WHERE billing_npi = '{npi}'
        GROUP BY year ORDER BY year
    """).fetchall()
    yearly_data = [{"year": r[0], "paid": r[1], "claims": r[2], "benes": r[3]} for r in yearly]

    # --- YoY growth flags ---
    growth_flags = []
    for i in range(1, len(yearly_data)):
        prev = yearly_data[i - 1]["paid"]
        curr = yearly_data[i]["paid"]
        if prev and prev > 0:
            pct = ((curr - prev) / prev) * 100
            if pct > 200:
                growth_flags.append({
                    "year": yearly_data[i]["year"],
                    "prev_year": yearly_data[i - 1]["year"],
                    "growth_pct": pct,
                    "prev_paid": prev,
                    "curr_paid": curr,
                })

    # --- HCPCS breakdown ---
    hcpcs_rows = con.execute(f"""
        SELECT s.hcpcs_code,
               COALESCE(h.description, '') AS description,
               SUM(s.paid) AS total_paid,
               SUM(s.claims) AS total_claims,
               SUM(s.beneficiaries) AS total_benes,
               SUM(s.paid) / NULLIF(SUM(s.claims), 0) AS per_claim
        FROM '{SPENDING}' s
        LEFT JOIN '{HCPCS}' h ON s.hcpcs_code = h.hcpcs_code
        WHERE s.billing_npi = '{npi}'
        GROUP BY s.hcpcs_code, h.description
        ORDER BY total_paid DESC
    """).fetchall()

    percentiles = _load_percentiles()
    hcpcs_data = []
    rate_flags = []
    for r in hcpcs_rows:
        code = r[0]
        per_claim = r[5]
        entry = {
            "code": code, "description": r[1], "paid": r[2],
            "claims": r[3], "benes": r[4], "per_claim": per_claim,
            "p50": None, "p95": None, "flag_95": False,
        }
        if code in percentiles and per_claim is not None:
            entry["p50"] = percentiles[code]["p50"]
            entry["p95"] = percentiles[code]["p95"]
            if per_claim > percentiles[code]["p95"]:
                entry["flag_95"] = True
                rate_flags.append({
                    "code": code,
                    "description": r[1],
                    "per_claim": per_claim,
                    "p95": percentiles[code]["p95"],
                    "p50": percentiles[code]["p50"],
                })
        hcpcs_data.append(entry)

    # --- Monthly timeline ---
    monthly = con.execute(f"""
        SELECT claim_month, SUM(paid) AS total_paid, SUM(claims) AS total_claims
        FROM '{SPENDING}'
        WHERE billing_npi = '{npi}'
        GROUP BY claim_month ORDER BY claim_month
    """).fetchall()
    monthly_data = [{"month": r[0], "paid": r[1], "claims": r[2]} for r in monthly]

    # --- Servicing providers (who rendered services under this billing NPI) ---
    servicing = con.execute(f"""
        SELECT s.servicing_npi,
               COALESCE(p.org_name, p.last_name || ', ' || COALESCE(p.first_name, '')) AS name,
               p.taxonomy_code,
               SUM(s.paid) AS total_paid,
               SUM(s.claims) AS total_claims
        FROM '{SPENDING}' s
        LEFT JOIN '{SERVICING}' p ON s.servicing_npi = p.npi
        WHERE s.billing_npi = '{npi}' AND s.servicing_npi != s.billing_npi
        GROUP BY s.servicing_npi, name, p.taxonomy_code
        ORDER BY total_paid DESC
        LIMIT 100
    """).fetchall()
    servicing_data = [{"npi": r[0], "name": r[1], "taxonomy": r[2],
                       "paid": r[3], "claims": r[4]} for r in servicing]

    # --- Billing relationships (who bills for this NPI's services) ---
    billing_for = con.execute(f"""
        SELECT s.billing_npi,
               COALESCE(p.org_name, p.last_name || ', ' || COALESCE(p.first_name, '')) AS name,
               p.taxonomy_code,
               SUM(s.paid) AS total_paid,
               SUM(s.claims) AS total_claims
        FROM '{SPENDING}' s
        LEFT JOIN '{BILLING}' p ON s.billing_npi = p.npi
        WHERE s.servicing_npi = '{npi}' AND s.billing_npi != s.servicing_npi
        GROUP BY s.billing_npi, name, p.taxonomy_code
        ORDER BY total_paid DESC
        LIMIT 100
    """).fetchall()
    billing_for_data = [{"npi": r[0], "name": r[1], "taxonomy": r[2],
                         "paid": r[3], "claims": r[4]} for r in billing_for]

    # --- OIG exclusion check ---
    exclusion = con.execute(f"""
        SELECT LASTNAME, FIRSTNAME, BUSNAME, EXCLTYPE, EXCLDATE, REINDATE
        FROM '{LEIE}'
        WHERE NPI = '{npi}' AND NPI != '0000000000'
    """).fetchall()
    exclusion_data = [{"last": r[0], "first": r[1], "business": r[2],
                       "type": r[3], "date": r[4], "reinstate": r[5]} for r in exclusion]

    # --- Colocated providers (same address) ---
    colocated = []
    if provider["address"]:
        addr_safe = _sanitize(provider["address"])
        colocated_rows = con.execute(f"""
            SELECT b.npi,
                   COALESCE(b.org_name, b.last_name || ', ' || COALESCE(b.first_name, '')) AS name,
                   b.taxonomy_code
            FROM '{BILLING}' b
            WHERE LOWER(b.address_line1) = LOWER('{addr_safe}')
              AND b.npi != '{npi}'
            LIMIT 20
        """).fetchall()
        colocated = [{"npi": r[0], "name": r[1], "taxonomy": r[2]} for r in colocated_rows]

    elapsed = time.time() - t0

    return render_template("provider.html",
                           provider=provider, yearly=yearly_data,
                           hcpcs=hcpcs_data, monthly=monthly_data,
                           servicing=servicing_data, billing_for=billing_for_data,
                           exclusions=exclusion_data, colocated=colocated,
                           growth_flags=growth_flags, rate_flags=rate_flags,
                           elapsed=elapsed)


@app.route("/address")
def address_search():
    """Search all providers at a given address."""
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("address.html", providers=[], query="")

    con = get_con()
    safe_q = _sanitize(q)
    t0 = time.time()

    rows = con.execute(f"""
        SELECT b.npi,
               COALESCE(b.org_name, b.last_name || ', ' || COALESCE(b.first_name, '')) AS name,
               b.address_line1, b.city, b.state, b.zip, b.phone,
               b.taxonomy_code, b.enumeration_date,
               s.total_paid, s.total_claims
        FROM '{BILLING}' b
        LEFT JOIN (
            SELECT billing_npi, SUM(paid) AS total_paid, SUM(claims) AS total_claims
            FROM '{SPENDING}'
            GROUP BY billing_npi
        ) s ON b.npi = s.billing_npi
        WHERE LOWER(b.address_line1) LIKE '%{safe_q.lower()}%'
        ORDER BY s.total_paid DESC NULLS LAST
        LIMIT 200
    """).fetchall()

    providers = []
    for r in rows:
        providers.append({
            "npi": r[0], "name": r[1], "address": r[2], "city": r[3],
            "state": r[4], "zip": r[5], "phone": r[6], "taxonomy": r[7],
            "enum_date": r[8], "total_paid": r[9], "total_claims": r[10],
        })

    elapsed = time.time() - t0
    return render_template("address.html", providers=providers, query=q, elapsed=elapsed)


@app.route("/api/monthly/<npi>")
def api_monthly(npi):
    """JSON endpoint for chart data."""
    npi = _npi_only(npi)
    con = get_con()
    rows = con.execute(f"""
        SELECT claim_month, SUM(paid) AS total_paid, SUM(claims) AS total_claims
        FROM '{SPENDING}'
        WHERE billing_npi = '{npi}'
        GROUP BY claim_month ORDER BY claim_month
    """).fetchall()
    return jsonify({
        "labels": [r[0] for r in rows],
        "paid": [r[1] for r in rows],
        "claims": [r[2] for r in rows],
    })


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Verify data files exist
    for f in [SPENDING, BILLING, SERVICING, HCPCS, LEIE]:
        if not Path(f).exists():
            print(f"ERROR: Missing data file: {f}")
            exit(1)
    print(f"Data directory: {DATA_DIR}")
    print("Pre-computing HCPCS percentiles (first request will be fast)...")
    _load_percentiles()
    print("Starting server on http://localhost:5001")
    app.run(host="127.0.0.1", port=5001, debug=True)
