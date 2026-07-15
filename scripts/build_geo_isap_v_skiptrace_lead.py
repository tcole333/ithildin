#!/usr/bin/env python3
"""Build the lead #62587 evidence matrix and hashed source manifest.

This builder intentionally separates federal award actions, current award-level
snapshots, preserved pre-award solicitation text, and GEO's SEC-filed corporate
statements. It does not infer that GEO's referenced pilot was a particular PIID.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "investigations/geo-group/sources/2026-07-14-lead-62587"
DEFAULT_REPORT_DIR = ROOT / "investigations/geo-group/reports"

USA_AWARD_URL = (
    "https://www.usaspending.gov/award/"
    "CONT_AWD_70CDCR25FR0000127_7012_70CDCR25D00000062_7012/"
)
USA_API_URL = "https://api.usaspending.gov/api/v2/transactions/"
SAM_OPPORTUNITY_URL = "https://sam.gov/opp/8bcce9c16821469395136f30f092ffbf/view"
SEC_2025_RESULTS_URL = (
    "https://www.sec.gov/Archives/edgar/data/923796/"
    "000119312526047556/d88889dex991.htm"
)
SEC_2026_Q1_URL = (
    "https://www.sec.gov/Archives/edgar/data/923796/"
    "000119312526207484/d122560dex991.htm"
)
SEC_10K_URL = (
    "https://www.sec.gov/Archives/edgar/data/923796/"
    "000119312526071747/geo-20251231.htm"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def require_text(path: Path, quote: str) -> str:
    text = path.read_text(errors="replace")
    if quote not in text:
        raise ValueError(f"Expected quote missing from {rel(path)}: {quote}")
    return quote


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_REPORT_DIR / "2026-07-14-lead-62587-isap-v-skiptrace-evidence-matrix.csv",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_REPORT_DIR / "2026-07-14-lead-62587-isap-v-skiptrace-source-manifest.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_DIR / "2026-07-14-lead-62587-isap-v-skiptrace-acquisition-record.md",
    )
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    transactions_path = source_dir / "usaspending/usaspending-isapv-transactions-current.json"
    award_path = source_dir / "usaspending/usaspending-isapv-award-current.json"
    idv_path = source_dir / "usaspending/usaspending-isapv-idv-current.json"
    attachment_path = (
        source_dir / "sam-preaward/attachment-4-pricing-template-preserved-text-extract.txt"
    )
    attachment_metadata_path = (
        source_dir / "sam-preaward/attachment-4-pricing-template-metadata.json"
    )
    sec_2025_path = source_dir / "sec/geo-2025-results-ex99-1.txt"
    sec_q1_path = source_dir / "sec/geo-2026-q1-results-ex99-1.txt"
    sec_10k_path = source_dir / "sec/geo-2025-10k.txt"
    govinfo_path = source_dir / "public-search/govinfo-piid.json"

    tx_payload = json.loads(transactions_path.read_text())
    transactions = tx_payload["results"]
    if len(transactions) != 5:
        raise ValueError(f"Expected 5 task actions, found {len(transactions)}")
    by_mod = {row["modification_number"]: row for row in transactions}
    expected_mods = {"0", "P00001", "P00002", "P00003", "P00004"}
    if set(by_mod) != expected_mods:
        raise ValueError(f"Unexpected modification set: {sorted(by_mod)}")

    expected_obligations = {
        "0": 21_966_324.91,
        "P00001": 16_103.09,
        "P00002": 690_000.00,
        "P00003": 9_660_000.00,
        "P00004": 76_011_425.00,
    }
    for mod, expected in expected_obligations.items():
        actual = by_mod[mod]["federal_action_obligation"]
        if actual != expected:
            raise ValueError(f"{mod} obligation changed: {actual} != {expected}")

    award = json.loads(award_path.read_text())
    if award["piid"] != "70CDCR25FR0000127":
        raise ValueError("Unexpected task-order PIID")
    if award["total_obligation"] != 108_343_853.00:
        raise ValueError("Unexpected current task-order obligations")
    if award["total_account_outlay"] != 94_747_700.79:
        raise ValueError("Unexpected current task-order outlay snapshot")
    if award["subaward_count"] != 0 or award["total_subaward_amount"] is not None:
        raise ValueError("Structured subaward snapshot changed")

    skip_total = sum(expected_obligations[mod] for mod in ("P00002", "P00003", "P00004"))
    skip_share = skip_total / award["total_obligation"]
    if skip_total != 86_361_425.00:
        raise ValueError("Skip-tracing action sum changed")

    item_39 = require_text(attachment_path, "39. J-site Case Coordination Meeting")
    estimate_quote = require_text(
        attachment_path,
        "*Quantities are estimated for evaluation purposes only. They shall not be modified by offerors and the Government is not obligated to order the stated quantity.",
    )
    if "42. " in attachment_path.read_text(errors="replace"):
        raise ValueError("Preserved pre-award pricing extract unexpectedly contains item 42")

    sec_pilot_quote = require_text(
        sec_2025_path,
        "This two-year contract award follows an initial Skip Tracing pilot contract that we successfully implemented during the fourth quarter of 2025.",
    )
    sec_transition_quote = require_text(
        sec_2025_path,
        "no revenue or earnings assumption for the Skip Tracing services contract as we transition from the pilot contract that was implemented in the fourth quarter to the new two-year contract.",
    )
    sec_go_live_quote = require_text(
        sec_q1_path,
        "We began providing skip tracing services under this new two-year contract in March 2026.",
    )
    sec_value_quote = require_text(
        sec_q1_path,
        "valued at up to $60 million in revenues per year.",
    )
    sec_10k_quote = require_text(
        sec_10k_path,
        "The new contract has a term of two years, with an initial term of one year, effective December 16, 2025, and an additional one-year period.",
    )

    govinfo = json.loads(govinfo_path.read_text())
    if govinfo != {
        "total": 0,
        "query": "70CDCR25FR0000127",
        "collection": None,
        "results": [],
    }:
        raise ValueError("GovInfo exact-PIID search boundary changed")

    rows: list[dict[str, str]] = []

    def add_row(
        evidence_id: str,
        source_class: str,
        issuer: str,
        document_date: str,
        locator: str,
        exact_quote: str,
        fact_boundary: str,
        hypothesis_relevance: str,
        path: Path,
        url: str,
    ) -> None:
        rows.append(
            {
                "evidence_id": evidence_id,
                "source_class": source_class,
                "issuer": issuer,
                "document_date": document_date,
                "locator": locator,
                "exact_quote": exact_quote,
                "fact_boundary": fact_boundary,
                "hypothesis_relevance": hypothesis_relevance,
                "source_path": rel(path),
                "source_sha256": sha256(path),
                "source_url": url,
            }
        )

    for mod in ("P00002", "P00003", "P00004"):
        row = by_mod[mod]
        add_row(
            f"USAS-{mod}",
            "official federal award transaction",
            "USAspending / ICE award data",
            row["action_date"],
            f"PIID 70CDCR25FR0000127; modification {mod}; action type {row['action_type_description']}",
            row["description"],
            f"Action obligation ${row['federal_action_obligation']:,.2f}; obligation is not an invoice, outlay, payment, or GEO revenue.",
            "Establishes the dated funding action and public label only; the truncated description does not reveal item 42's unit, quantity, cohort, or deliverable.",
            transactions_path,
            USA_AWARD_URL,
        )

    add_row(
        "USAS-AWARD-SNAPSHOT",
        "official federal award snapshot",
        "USAspending / ICE award data",
        "2026-07-14 retrieval",
        "PIID 70CDCR25FR0000127",
        (
            f"total_obligation={award['total_obligation']}; "
            f"total_account_outlay={award['total_account_outlay']}; "
            f"subaward_count={award['subaward_count']}; "
            f"total_subaward_amount={award['total_subaward_amount']}"
        ),
        "Current award-level snapshot; structured zero does not prove that no subcontractor or supplier exists.",
        "Quantifies the award state without resolving the missing acquisition file or downstream supplier chain.",
        award_path,
        USA_AWARD_URL,
    )

    add_row(
        "SAM-PREAWARD-ITEM39",
        "preserved extraction from public pre-award solicitation attachment",
        "ICE / SAM opportunity",
        "2025-08-15 posting",
        "Attachment 4, operational-support schedule ending at item 39",
        item_39,
        "The original XLSX was not recovered in this wave; the preserved text extraction is a secondary local representation of the public SAM attachment.",
        "Shows the public pre-award schedule reached item 39; does not establish the contents or absence of a post-award item 42.",
        attachment_path,
        SAM_OPPORTUNITY_URL,
    )
    add_row(
        "SAM-PREAWARD-ESTIMATE",
        "preserved extraction from public pre-award solicitation attachment",
        "ICE / SAM opportunity",
        "2025-08-15 posting",
        "Attachment 4, schedule note",
        estimate_quote,
        "Pre-award estimated quantities are not commitments, orders, invoices, or realized volume.",
        "Limits any attempt to infer realized item-42 volume from the pre-award workbook.",
        attachment_path,
        SAM_OPPORTUNITY_URL,
    )

    add_row(
        "SEC-PILOT",
        "SEC-filed company statement",
        "The GEO Group, Inc.",
        "2026-02-12",
        "Exhibit 99.1, 2025 results release",
        sec_pilot_quote,
        "Company statement about its own contracting history; it does not identify the pilot PIID.",
        "Distinguishes an initial Q4 2025 pilot from the two-year award but does not map the pilot to ISAP V item 42.",
        sec_2025_path,
        SEC_2025_RESULTS_URL,
    )
    add_row(
        "SEC-TRANSITION",
        "SEC-filed company statement",
        "The GEO Group, Inc.",
        "2026-02-12",
        "Exhibit 99.1, Q1 2026 guidance",
        sec_transition_quote,
        "Forward-looking company guidance; not an agency acquisition record or payment ledger.",
        "Establishes GEO described a pilot-to-new-contract transition; does not resolve case or data overlap.",
        sec_2025_path,
        SEC_2025_RESULTS_URL,
    )
    add_row(
        "SEC-GO-LIVE",
        "SEC-filed company statement",
        "The GEO Group, Inc.",
        "2026-05-06",
        "Exhibit 99.1, Q1 2026 results release",
        sec_go_live_quote,
        "Company-stated service-start month; not an ICE acceptance record and not proof of first case transfer.",
        "Supplies a March 2026 public operational anchor for the new two-year skip-tracing contract.",
        sec_q1_path,
        SEC_2026_Q1_URL,
    )
    add_row(
        "SEC-REVENUE-CAPACITY",
        "SEC-filed company statement",
        "The GEO Group, Inc.",
        "2026-05-06",
        "Exhibit 99.1, Q1 2026 results release",
        sec_value_quote,
        "Company-described potential revenue capacity; not obligation, outlay, invoice, or recognized revenue.",
        "Prevents conflation of company revenue guidance with USAspending action obligations.",
        sec_q1_path,
        SEC_2026_Q1_URL,
    )
    add_row(
        "SEC-10K-TERM",
        "SEC-filed company statement",
        "The GEO Group, Inc.",
        "2026-02-25",
        "2025 Form 10-K, contract developments",
        sec_10k_quote,
        "Company disclosure of the two-year contract term; does not identify item 42.",
        "Corroborates the corporate contract identity/date without supplying the missing modification package.",
        sec_10k_path,
        SEC_10K_URL,
    )
    add_row(
        "GOVINFO-EXACT-PIID",
        "official-search boundary",
        "GovInfo",
        "2026-07-14 search",
        "Exact query 70CDCR25FR0000127",
        '"total": 0',
        "Bounded zero in GovInfo only; not evidence that agency-held or non-indexed records do not exist.",
        "Does not discriminate the substantive hypotheses; records the exhausted official corpus.",
        govinfo_path,
        "https://www.govinfo.gov/",
    )

    args.matrix.parent.mkdir(parents=True, exist_ok=True)
    with args.matrix.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    source_records = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        source_records.append(
            {
                "path": rel(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )

    manifest = {
        "as_of": "2026-07-14",
        "profile": "geo-group",
        "lead_id": 62587,
        "scope": (
            "ISAP V task 70CDCR25FR0000127, its skip-tracing funding actions, "
            "the public pre-award Attachment 4 boundary, and GEO's pilot/new-contract statements"
        ),
        "public_record_result": {
            "post_award_attachment_4_item_42_recovered": False,
            "signed_modifications_p00002_p00004_recovered": False,
            "item_42_unit_quantity_unit_price_case_population_deliverables": "unresolved",
            "sam_live_status": (
                "Exact opportunity and contract calls failed silently before a direct call returned HTTP 429; "
                "papercut #979 records the credential-free reproduction."
            ),
            "highergov_api_called_in_wave": False,
            "existing_local_highergov_document_mirror_used": (
                "Only for the preserved pre-award SAM Attachment 4 text extraction and file metadata; "
                "no live HigherGov request or credential was used."
            ),
        },
        "calculations": {
            "skip_tracing_action_obligations": skip_total,
            "current_task_obligations": award["total_obligation"],
            "skip_actions_share_of_current_task_obligations": round(skip_share, 8),
            "current_task_outlay_snapshot": award["total_account_outlay"],
            "structured_subaward_count": award["subaward_count"],
            "structured_subaward_boundary": (
                "A structured zero is not proof that no subcontractor, supplier, reseller, or "
                "contractor-to-contractor arrangement exists."
            ),
        },
        "database_result": {
            "verified_finding_ids": [12467, 12941, 12942, 12943],
            "retracted_replaced_finding_ids": [12468],
            "human_action_id": 67,
            "hypothesis_evaluations_added_by_tier1_wave": 0,
        },
        "sources": source_records,
        "generated_outputs": [
            {
                "path": rel(args.matrix.resolve()),
                "sha256": sha256(args.matrix.resolve()),
                "rows": len(rows),
            },
            {
                "path": rel(args.report.resolve()),
                "sha256": sha256(args.report.resolve()),
            },
        ],
        "evidence_ids": [row["evidence_id"] for row in rows],
        "source_boundaries": [
            "USAspending obligations, outlays, award values, invoices, and GEO revenue are distinct metrics.",
            "The pre-award Attachment 4 extraction is not the unrecovered post-award schedule referenced by P00003/P00004.",
            "GEO's pilot and go-live statements do not identify the pilot PIID or prove cross-channel case/data overlap.",
            "No HigherGov API call was made during this wave.",
        ],
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "matrix": rel(args.matrix.resolve()),
                "matrix_sha256": sha256(args.matrix.resolve()),
                "matrix_rows": len(rows),
                "manifest": rel(args.manifest.resolve()),
                "manifest_sha256": sha256(args.manifest.resolve()),
                "source_files": len(source_records),
                "skip_total": skip_total,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
