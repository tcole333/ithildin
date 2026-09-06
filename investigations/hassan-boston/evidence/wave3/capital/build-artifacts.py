import csv
import hashlib
import json
import sqlite3
from pathlib import Path


BASE = Path(__file__).resolve().parent
REPO = BASE.parents[4]
DB = REPO / "investigation.db"
FINDING_IDS = [15629, 15630, 15631, 15632, 15633, 15634]
EXPECTED_COLUMNS = [
    "event_id", "property_key", "property_label", "municipality", "county",
    "parcel_id", "event_date", "date_precision", "date_basis", "event_type",
    "from_party", "from_capacity", "to_party", "to_capacity",
    "consideration_usd", "loan_amount_usd", "registry", "book_page",
    "instrument_id", "evidence_status", "source_url", "source_ref",
    "source_quote", "finding_ids", "notes",
]


def rows(conn, query, params=()):
    return [dict(row) for row in conn.execute(query, params).fetchall()]


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
placeholders = ",".join("?" for _ in FINDING_IDS)
finding_rows = rows(
    conn,
    f"SELECT * FROM findings WHERE id IN ({placeholders}) ORDER BY id",
    FINDING_IDS,
)
evidence_rows = rows(
    conn,
    f"SELECT * FROM finding_evidence WHERE finding_id IN ({placeholders}) ORDER BY finding_id, evidence_ref",
    FINDING_IDS,
)
entity_rows = rows(
    conn,
    f"SELECT * FROM finding_entities WHERE finding_id IN ({placeholders}) ORDER BY finding_id, entity_id",
    FINDING_IDS,
)
connection_rows = rows(
    conn,
    f"SELECT * FROM connections WHERE finding_id IN ({placeholders}) ORDER BY id",
    FINDING_IDS,
)
conn.close()

(BASE / "findings-manifest.json").write_text(
    json.dumps(
        {
            "finding_ids": FINDING_IDS,
            "findings": finding_rows,
            "evidence": evidence_rows,
            "entity_links": entity_rows,
            "connections": connection_rows,
        },
        indent=2,
        ensure_ascii=False,
    )
    + "\n"
)

with (BASE / "property-events.csv").open(newline="") as handle:
    event_rows = list(csv.reader(handle))

source_urls = json.loads((BASE / "source-urls.json").read_text())
evidence_refs = {row["evidence_ref"] for row in evidence_rows}
jpgs = sorted((BASE / "fr-pages").glob("page-*.jpg"))
texts = sorted((BASE / "fr-pages").glob("page-*.txt"))
pdf = BASE / "concepts-fr-statutes-2019.pdf"

checks = {
    "property_event_column_count": len(event_rows[0]) if event_rows else 0,
    "property_event_columns_exact": bool(event_rows and event_rows[0] == EXPECTED_COLUMNS),
    "property_event_data_rows": max(len(event_rows) - 1, 0),
    "capital_chronology_data_rows": max(
        sum(1 for _ in (BASE / "capital-chronology.csv").open()) - 1, 0
    ),
    "french_pdf_bytes": pdf.stat().st_size,
    "french_pdf_magic": pdf.read_bytes()[:5].decode("ascii", errors="replace"),
    "french_page_jpg_count": len(jpgs),
    "french_page_text_count": len(texts),
    "finding_ids_present": [row["id"] for row in finding_rows],
    "all_findings_have_evidence_quote": all(
        row.get("source_quote") for row in evidence_rows
    ) and len(evidence_rows) == len(FINDING_IDS),
    "all_findings_profile_scoped": all(
        row["profile_id"] == "hassan-boston" for row in finding_rows
    ),
    "confidence_caps_valid": all(
        not (row["claim_type"] in {"paraphrase", "inference", "synthesis"} and row["confidence"] == "confirmed")
        for row in finding_rows
    ),
    "source_url_refs_cover_finding_evidence": sorted(evidence_refs - set(source_urls)),
    "web_search_output_count": len(list(BASE.glob("c3_web*.json"))),
    "coverage_entries": len(json.loads((BASE / "coverage.json").read_text())),
    "ma_direct_http_response_is_not_pdf": "No documents found" in (BASE / "ma-merger-direct-http-response.html").read_text(),
    "report_exists": (REPO / "investigations/hassan-boston/reports/wave3/report-capital.md").exists(),
}
checks["passed"] = (
    checks["property_event_columns_exact"]
    and checks["property_event_data_rows"] == 0
    and checks["french_pdf_magic"] == "%PDF-"
    and checks["french_page_jpg_count"] == 16
    and checks["french_page_text_count"] == 16
    and checks["finding_ids_present"] == FINDING_IDS
    and checks["all_findings_have_evidence_quote"]
    and checks["all_findings_profile_scoped"]
    and checks["confidence_caps_valid"]
    and not checks["source_url_refs_cover_finding_evidence"]
    and checks["web_search_output_count"] == 12
    and checks["report_exists"]
)
(BASE / "validation.json").write_text(json.dumps(checks, indent=2) + "\n")

manifest = []
for file_path in sorted(BASE.rglob("*")):
    if not file_path.is_file() or file_path.name == "manifest.json":
        continue
    data = file_path.read_bytes()
    manifest.append(
        {
            "path": str(file_path.relative_to(REPO)),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )
(BASE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

print(json.dumps(checks, indent=2))
