#!/usr/bin/env python3
"""Build the GEO state/local political-payment ledger for investigation lead 59033.

The script intentionally keeps source rows rather than trying to manufacture a
single perfectly deduplicated transaction set from records that expose different
identifiers.  Florida provides recipient-side records but no report/check IDs;
FEC Schedule B provides payer-side GEO PAC records with transaction and filing
identifiers.  Florida rows carrying an explicit PAC/SSF label are therefore
preserved as corroborating recipient-side records and excluded from aggregate
PAC totals to avoid double counting.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


FL_SOURCE_URL = "https://dos.elections.myflorida.com/campaign-finance/contributions/"
FEC_SOURCE_URL = "https://www.fec.gov/data/disbursements/?committee_id=C00382150"
GEO_2024_URL = (
    "https://www.geogroup.com/media/tufn44mo/"
    "geo-political-activity-and-lobbying-report-_2024_.pdf"
)
GEO_2025_URL = "https://www.geogroup.com/geo-2025-political-activity-and-lobbying-report/"
ALBRITTON_OFFICE_URL = "https://www.flsenate.gov/Offices/President"
ALBRITTON_TRUMP_ACT_URL = (
    "https://www.flsenate.gov/PublishedContent/Offices/2024-2026/President/"
    "Documents/TRUMP_Act.pdf"
)
UTHEMEIER_OFFICE_URL = (
    "https://legacy.myfloridalegal.com/pages.nsf/Main/1515CE372E59D1E885256CC60071B1C4"
)
DONALDS_OFFICE_URL = "https://donalds.house.gov/about/"
FL_287G_URL = (
    "https://www.flgov.com/eog/news/press/2025/"
    "governor-ron-desantis-announces-additional-memoranda-agreement-between-florida-law"
)
FL_DETENTION_PLAN_URL = (
    "https://www.flgov.com/eog/news/press/2025/"
    "governor-ron-desantis-highlights-floridas-leadership-immigration-enforcement"
)
PL_119_21_URL = "https://www.congress.gov/bill/119th-congress/house-bill/1/text"

JURISDICTION_NAMES = {
    "AZ": "Arizona",
    "CA": "California",
    "CO": "Colorado",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "IL": "Illinois",
    "IN": "Indiana",
    "LA": "Louisiana",
    "MI": "Michigan",
    "NC": "North Carolina",
    "NJ": "New Jersey",
    "NY": "New York",
    "OK": "Oklahoma",
    "PA": "Pennsylvania",
    "TX": "Texas",
    "VA": "Virginia",
    "WI": "Wisconsin",
}


# Amounts transcribed from the State / Local tables in GEO's official reports.
# The table columns are Type | GEO PAC | Corporate.
COMPANY_STATE_LOCAL: dict[int, dict[str, Any]] = {
    2024: {
        "state_local_total": Decimal("969700"),
        "jurisdictions": {
            "AZ": {"geo_pac": Decimal("56000"), "corporate": Decimal("70000")},
            "CO": {"geo_pac": Decimal("0"), "corporate": Decimal("35000")},
            "FL": {"geo_pac": Decimal("0"), "corporate": Decimal("564500")},
            "GA": {"geo_pac": Decimal("0"), "corporate": Decimal("77500")},
            "IL": {"geo_pac": Decimal("0"), "corporate": Decimal("2200")},
            "IN": {"geo_pac": Decimal("0"), "corporate": Decimal("45000")},
            "NY": {"geo_pac": Decimal("0"), "corporate": Decimal("12000")},
            "OK": {"geo_pac": Decimal("12500"), "corporate": Decimal("75000")},
            "TX": {"geo_pac": Decimal("10000"), "corporate": Decimal("0")},
            "VA": {"geo_pac": Decimal("0"), "corporate": Decimal("10000")},
        },
    },
    2025: {
        "state_local_total": Decimal("2253400"),
        "jurisdictions": {
            "AZ": {"geo_pac": Decimal("43000"), "corporate": Decimal("111000")},
            "CA": {"geo_pac": Decimal("0"), "corporate": Decimal("1000")},
            "FL": {"geo_pac": Decimal("0"), "corporate": Decimal("1922600")},
            "GA": {"geo_pac": Decimal("0"), "corporate": Decimal("64800")},
            "IL": {"geo_pac": Decimal("0"), "corporate": Decimal("6500")},
            "IN": {"geo_pac": Decimal("0"), "corporate": Decimal("39000")},
            "NJ": {"geo_pac": Decimal("0"), "corporate": Decimal("2000")},
            "OK": {"geo_pac": Decimal("17500"), "corporate": Decimal("45000")},
            "PA": {"geo_pac": Decimal("1000"), "corporate": Decimal("0")},
        },
    },
}


LEDGER_FIELDS = [
    "record_id",
    "event_date",
    "calendar_year",
    "jurisdiction_code",
    "jurisdiction_name",
    "source_perspective",
    "source_stream",
    "payer_class",
    "funding_stream",
    "payer_legal_name_as_filed",
    "payer_canonical_name",
    "recipient_name_as_filed",
    "recipient_type",
    "party",
    "amount",
    "amount_direction",
    "transaction_type",
    "amendment_indicator",
    "amendment_description",
    "refund_void_status",
    "exact_row_duplicate_status",
    "exact_row_duplicate_group_id",
    "exact_row_duplicate_group_size",
    "cross_source_match_id",
    "cross_source_match_confidence",
    "aggregation_eligible",
    "aggregation_exclusion_reason",
    "source_record_id",
    "transaction_id",
    "sub_id",
    "file_number",
    "image_number",
    "source_file",
    "source_file_sha256",
    "source_url",
    "source_document_url",
    "source_quote",
    "description",
    "recipient_state_code_raw",
    "alias_query",
    "alias_decision",
    "coverage_scope",
    "deduplication_note",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_hash(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def decimal_text(value: Decimal) -> str:
    return f"{value:.2f}"


def json_decimal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_decimal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_decimal(item) for item in value]
    return value


def normalize_name(value: str | None) -> str:
    value = (value or "").upper()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return " ".join(value.split())


def florida_payer_class(name: str) -> tuple[str, str, bool, str]:
    """Return payer class, funding stream, aggregate flag, and alias decision."""
    normalized = normalize_name(name)
    contribution_account_markers = (
        "POLITICAL CONTRIBUTION ACCOUNT",
        "POLITICAL CONTRIBUTIONS ACCT",
        "POLITICAL CONTRIBUTION ACCT",
        "POLITICAL CONTRIBUTING ACCOUNT",
        " PCA",
    )
    pac_markers = (" POLITICAL ACTION COMMITTEE", " PAC")

    if any(marker in f" {normalized}" for marker in contribution_account_markers):
        return (
            "geo_corporate_legal_entity",
            "corporate_treasury_political_contribution_account",
            True,
            "Corporate class: exact filed name says political contribution account/PCA, "
            "not political action committee; consistent with GEO report's zero Florida "
            "GEO PAC column in 2024 and 2025.",
        )
    if any(marker in f" {normalized}" for marker in pac_markers):
        return (
            "geo_pac_ssf_label",
            "geo_pac_or_state_pac_label",
            False,
            "PAC/Political Action Committee label preserved as recipient-side "
            "corroboration; excluded from aggregate PAC totals to avoid double counting "
            "payer-side FEC Schedule B records.",
        )
    if normalized.startswith("THE GEO GROUP") or normalized.startswith("GEO CARE"):
        return (
            "geo_corporate_legal_entity",
            "corporate_treasury",
            True,
            "Corporate class based on exact GEO/GEO Care legal-entity name with no PAC/SSF label.",
        )
    if normalized.startswith("GEO ACQUISITION") or normalized.startswith("GEO REENTRY"):
        return (
            "geo_corporate_legal_entity",
            "corporate_treasury",
            True,
            "Corporate class based on exact GEO subsidiary legal-entity name with no PAC/SSF label.",
        )
    if re.search(r"\b(GEORGE|BRIAN|JAMES|JOHN|JOSE|MARY|DAVID)\b", normalized):
        return (
            "individual_officer",
            "individual",
            False,
            "Individual-name heuristic; no such row should be included without manual review.",
        )
    return (
        "ambiguous_or_unrelated",
        "unresolved",
        False,
        "Name did not satisfy the conservative GEO corporate or GEO PAC rules.",
    )


def florida_recipient_type(name: str) -> str:
    upper = name.upper()
    if re.search(r"\((REP|DEM|NOP)\)\([A-Z0-9]+\)\s*$", upper):
        return "candidate"
    if upper.rstrip().endswith("(PAC)"):
        return "political_action_committee"
    if upper.rstrip().endswith("(PAP)"):
        return "political_committee_or_party_affiliate"
    if upper.rstrip().endswith("(PTY)"):
        return "political_party"
    return "unreported_in_export"


def party_from_name(name: str) -> str:
    upper = name.upper()
    candidate_match = re.search(r"\((REP|DEM|NOP)\)\([A-Z0-9]+\)\s*$", upper)
    if candidate_match:
        return candidate_match.group(1)
    if "REPUBLICAN" in upper or re.search(r"\bGOP\b", upper):
        return "REP_name_based"
    if "DEMOCRAT" in upper:
        return "DEM_name_based"
    return "unreported"


def florida_transaction_type(code: str) -> tuple[str, str]:
    code = code.strip().upper()
    if code == "REF":
        return "refund", "refund"
    if code == "INK":
        return "in_kind", "none"
    if code == "CHE":
        return "check", "none"
    return f"state_code_{code or 'blank'}", "unresolved"


def parse_florida_rows(source_dir: Path) -> list[dict[str, str]]:
    staged: list[dict[str, Any]] = []
    for path in sorted(source_dir.glob("fl-all-2015-2026-*.txt")):
        if path.stat().st_size <= 100:
            continue
        alias_query = path.stem.removeprefix("fl-all-2015-2026-").replace("-", " ").upper()
        file_hash = sha256_file(path)
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for line_number, raw in enumerate(reader, start=2):
                amount = Decimal(raw["Amount"].strip())
                month, day, year = raw["Date"].strip().split("/")
                event_date = f"{year}-{month}-{day}"
                payer_class, funding_stream, eligible, alias_decision = florida_payer_class(
                    raw["Contributor Name"].strip()
                )
                transaction_type, adjustment_status = florida_transaction_type(raw["Typ"])
                duplicate_atom = {
                    key: raw.get(key, "").strip()
                    for key in (
                        "Candidate/Committee",
                        "Date",
                        "Amount",
                        "Typ",
                        "Contributor Name",
                        "Address",
                        "City State Zip",
                        "Occupation",
                        "Inkind Desc",
                    )
                }
                staged.append(
                    {
                        "raw": raw,
                        "source_file": path.name,
                        "source_hash": file_hash,
                        "source_line": line_number,
                        "alias_query": alias_query,
                        "amount_decimal": amount,
                        "event_date_value": event_date,
                        "payer_class_value": payer_class,
                        "funding_stream_value": funding_stream,
                        "aggregation_eligible_value": eligible,
                        "alias_decision_value": alias_decision,
                        "transaction_type_value": transaction_type,
                        "adjustment_status_value": adjustment_status,
                        "duplicate_atom": duplicate_atom,
                        "duplicate_hash": stable_hash(duplicate_atom)[:20],
                    }
                )

    duplicate_counts = Counter(row["duplicate_hash"] for row in staged)
    output: list[dict[str, str]] = []
    for row in staged:
        raw = row["raw"]
        amount: Decimal = row["amount_decimal"]
        duplicate_size = duplicate_counts[row["duplicate_hash"]]
        event_date = row["event_date_value"]
        source_key = {
            "source_file": row["source_file"],
            "source_line": row["source_line"],
            "row": row["duplicate_atom"],
        }
        source_record_id = f"FL:{stable_hash(source_key)[:24]}"
        is_eligible = row["aggregation_eligible_value"]
        exclusion_reason = ""
        if not is_eligible:
            exclusion_reason = (
                "Recipient-side PAC label retained as corroboration only"
                if row["payer_class_value"] == "geo_pac_ssf_label"
                else "Payer identity did not satisfy the conservative GEO corporate rule"
            )
        quote = "\t".join(raw.get(field, "") for field in raw.keys())
        output.append(
            {
                "record_id": source_record_id,
                "event_date": event_date,
                "calendar_year": event_date[:4],
                "jurisdiction_code": "FL",
                "jurisdiction_name": "Florida",
                "source_perspective": "recipient_side",
                "source_stream": "florida_campaign_finance_export",
                "payer_class": row["payer_class_value"],
                "funding_stream": row["funding_stream_value"],
                "payer_legal_name_as_filed": raw["Contributor Name"].strip(),
                "payer_canonical_name": (
                    "The GEO Group corporate family"
                    if row["payer_class_value"] == "geo_corporate_legal_entity"
                    else "The GEO Group PAC/SSF label"
                ),
                "recipient_name_as_filed": raw["Candidate/Committee"].strip(),
                "recipient_type": florida_recipient_type(raw["Candidate/Committee"]),
                "party": party_from_name(raw["Candidate/Committee"]),
                "amount": decimal_text(amount),
                "amount_direction": "negative" if amount < 0 else "positive",
                "transaction_type": row["transaction_type_value"],
                "amendment_indicator": "unavailable_in_export",
                "amendment_description": "unavailable_in_export",
                "refund_void_status": row["adjustment_status_value"],
                "exact_row_duplicate_status": (
                    "unresolved_exact_row_multiplicity"
                    if duplicate_size > 1
                    else "no_exact_duplicate_in_alias_exports"
                ),
                "exact_row_duplicate_group_id": (
                    f"FLDUP:{row['duplicate_hash']}" if duplicate_size > 1 else ""
                ),
                "exact_row_duplicate_group_size": str(duplicate_size),
                "aggregation_eligible": "true" if is_eligible else "false",
                "aggregation_exclusion_reason": exclusion_reason,
                "source_record_id": source_record_id,
                "transaction_id": "unavailable_in_export",
                "sub_id": "unavailable_in_export",
                "file_number": "unavailable_in_export",
                "image_number": "unavailable_in_export",
                "source_file": row["source_file"],
                "source_file_sha256": row["source_hash"],
                "source_url": FL_SOURCE_URL,
                "source_document_url": FL_SOURCE_URL,
                "source_quote": quote,
                "description": raw.get("Inkind Desc", "").strip(),
                "recipient_state_code_raw": "FL",
                "alias_query": row["alias_query"],
                "alias_decision": row["alias_decision_value"],
                "coverage_scope": (
                    "Florida Division of Elections statewide and multicounty records; "
                    "county/municipal filing-office records are outside this export"
                ),
                "deduplication_note": (
                    "Exact row multiplicity is flagged but not collapsed because the export "
                    "does not expose report, amendment, or check identifiers."
                ),
            }
        )
    return output


def fec_is_state_political_payment(row: dict[str, Any]) -> bool:
    if row.get("line_number_label") != "Other Disbursements":
        return False
    if row.get("entity_type") not in {"COM", "PTY", "CCM", "ORG"}:
        return False
    recipient = normalize_name(row.get("recipient_name"))
    if "CALIFORNIA SECRETARY" in recipient and "STATE" in recipient:
        return False
    return True


def fec_recipient_type(row: dict[str, Any]) -> str:
    return {
        "COM": "state_or_local_committee",
        "PTY": "political_party",
        "CCM": "candidate_committee",
        "ORG": "organization_or_committee_unresolved",
    }.get(row.get("entity_type"), "unreported")


def parse_fec_rows(path: Path) -> list[dict[str, str]]:
    file_hash = sha256_file(path)
    rows: list[dict[str, Any]] = json.loads(path.read_text())
    output: list[dict[str, str]] = []
    for raw in rows:
        if not fec_is_state_political_payment(raw):
            continue
        amount = Decimal(str(raw.get("disbursement_amount") or 0))
        event_date = raw["disbursement_date"]
        recipient_state_raw = raw.get("recipient_state") or ""
        jurisdiction = recipient_state_raw if recipient_state_raw in JURISDICTION_NAMES else "UNRESOLVED"
        amendment_indicator = raw.get("amendment_indicator") or ""
        adjustment_status = "none"
        description = (raw.get("disbursement_description") or "").strip()
        if amount < 0 and "VOID" in description.upper():
            adjustment_status = "void_or_stop_payment"
        elif amount < 0:
            adjustment_status = "negative_adjustment"
        source_record_id = f"FEC:{raw.get('sub_id') or stable_hash(raw)[:24]}"
        document_url = raw.get("pdf_url") or FEC_SOURCE_URL
        quote = (
            f"{event_date} | {raw.get('recipient_name') or ''} | "
            f"{decimal_text(amount)} | {description} | "
            f"transaction_id={raw.get('transaction_id') or ''} | "
            f"sub_id={raw.get('sub_id') or ''}"
        )
        output.append(
            {
                "record_id": source_record_id,
                "event_date": event_date,
                "calendar_year": event_date[:4],
                "jurisdiction_code": jurisdiction,
                "jurisdiction_name": JURISDICTION_NAMES.get(jurisdiction, "Unresolved"),
                "source_perspective": "payer_side",
                "source_stream": "fec_schedule_b_geo_pac_nonfederal",
                "payer_class": "geo_pac_ssf",
                "funding_stream": "geo_pac_employee_funded",
                "payer_legal_name_as_filed": "THE GEO GROUP, INC. POLITICAL ACTION COMMITTEE",
                "payer_canonical_name": "The GEO Group, Inc. Political Action Committee",
                "recipient_name_as_filed": (raw.get("recipient_name") or "").strip(),
                "recipient_type": fec_recipient_type(raw),
                "party": party_from_name(raw.get("recipient_name") or ""),
                "amount": decimal_text(amount),
                "amount_direction": "negative" if amount < 0 else "positive",
                "transaction_type": raw.get("line_number_label") or "Other Disbursements",
                "amendment_indicator": amendment_indicator,
                "amendment_description": raw.get("amendment_indicator_desc") or "",
                "refund_void_status": adjustment_status,
                "exact_row_duplicate_status": "unique_fec_sub_id",
                "exact_row_duplicate_group_id": "",
                "exact_row_duplicate_group_size": "1",
                "aggregation_eligible": "true",
                "aggregation_exclusion_reason": "",
                "source_record_id": source_record_id,
                "transaction_id": raw.get("transaction_id") or "",
                "sub_id": raw.get("sub_id") or "",
                "file_number": str(raw.get("file_number") or ""),
                "image_number": raw.get("image_number") or "",
                "source_file": path.name,
                "source_file_sha256": file_hash,
                "source_url": FEC_SOURCE_URL,
                "source_document_url": document_url,
                "source_quote": quote,
                "description": description,
                "recipient_state_code_raw": recipient_state_raw,
                "alias_query": "C00382150 Schedule B, line 29 Other Disbursements",
                "alias_decision": (
                    "Included COM/PTY/CCM/ORG Other Disbursements as state/local political "
                    "payments; excluded California Secretary of State registration-fee rows."
                ),
                "coverage_scope": (
                    "Payer-side FEC Schedule B disbursements reported by GEO PAC; state/local "
                    "recipient filing systems may report the same underlying payments."
                ),
                "deduplication_note": (
                    "FEC sub_id is unique in the input. Any matching recipient-side state record "
                    "is corroboration of the same payment, not an independent transaction."
                ),
            }
        )
    return output


def parse_nonfl_corporate_rows(
    ledger_path: Path | None, manifest_path: Path | None
) -> list[dict[str, str]]:
    """Map the bounded visible-agent non-Florida ledger into the canonical schema."""
    if ledger_path is None and manifest_path is None:
        return []
    if ledger_path is None or manifest_path is None:
        raise ValueError("--nonfl-ledger and --nonfl-manifest must be supplied together")

    manifest = json.loads(manifest_path.read_text())
    manifest_quotes = {
        item.get("source_record_id"): item.get("exact_quote")
        for item in manifest.get("source_records", [])
    }
    manifest_hash = sha256_file(manifest_path)
    with ledger_path.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    transaction_ids = [row["transaction_id"] for row in source_rows]
    guids = [row["guid"] for row in source_rows]
    if len(transaction_ids) != len(set(transaction_ids)):
        raise ValueError("non-Florida ledger contains duplicate transaction_id values")
    if len(guids) != len(set(guids)):
        raise ValueError("non-Florida ledger contains duplicate GUID values")

    output: list[dict[str, str]] = []
    for raw in source_rows:
        quote = raw["source_quote"]
        if not quote or manifest_quotes.get(raw.get("source_record_id")) != quote:
            raise ValueError(
                f"non-Florida source quote does not equal the parsed exact_quote in {manifest_path}: "
                f"{raw.get('source_record_id')}"
            )
        eligible = raw["aggregation_eligible"].strip().lower() == "true"
        payer_class = raw["payer_class"].strip()
        amount = Decimal(raw["amount"])
        record_id = raw["source_record_id"].strip()
        if not record_id:
            raise ValueError("non-Florida row missing source_record_id")
        output.append(
            {
                "record_id": record_id,
                "event_date": raw["event_date"],
                "calendar_year": raw["year"],
                "jurisdiction_code": raw["jurisdiction_code"],
                "jurisdiction_name": raw["jurisdiction_name"],
                "source_perspective": "recipient_side",
                "source_stream": "georgia_peachfile_campaign_finance_api",
                "payer_class": payer_class,
                "funding_stream": (
                    "corporate_treasury_or_political_contribution_account"
                    if eligible
                    else "ambiguous_pac_label_business_source_class"
                ),
                "payer_legal_name_as_filed": raw["exact_payer_legal_name_as_filed"],
                "payer_canonical_name": (
                    "The GEO Group corporate family"
                    if eligible
                    else "The GEO Group PAC-labelled payer ambiguity"
                ),
                "recipient_name_as_filed": raw["recipient_name_as_filed"],
                "recipient_type": raw["recipient_type"],
                "party": raw["party"] or "not_source_reported",
                "amount": decimal_text(amount),
                "amount_direction": "negative" if amount < 0 else "positive",
                "transaction_type": raw["transaction_type"],
                "amendment_indicator": (
                    f"filer_report_version_id={raw['filer_report_version_id']}"
                ),
                "amendment_description": raw["refund_void_amendment_status"],
                "refund_void_status": raw["refund_void_amendment_status"],
                "exact_row_duplicate_status": "unique_transaction_id_and_guid",
                "exact_row_duplicate_group_id": "",
                "exact_row_duplicate_group_size": "1",
                "cross_source_match_id": "",
                "cross_source_match_confidence": "",
                "aggregation_eligible": "true" if eligible else "false",
                "aggregation_exclusion_reason": (
                    ""
                    if eligible
                    else "Payer string contains PAC while Georgia source class says business/unregistered committee"
                ),
                "source_record_id": record_id,
                "transaction_id": raw["transaction_id"],
                "sub_id": raw["guid"],
                "file_number": raw["filer_report_id"],
                "image_number": "unavailable_in_source",
                "source_file": manifest_path.name,
                "source_file_sha256": manifest_hash,
                "source_url": raw["source_url"],
                "source_document_url": raw["source_url"],
                "source_quote": quote,
                "description": " | ".join(
                    value
                    for value in (raw["report_name"], raw["election_type_source_reported"])
                    if value
                ),
                "recipient_state_code_raw": raw["jurisdiction_code"],
                "alias_query": "Georgia PeachFile GEO business-source contribution search",
                "alias_decision": raw["payer_class_basis"],
                "coverage_scope": raw["coverage_boundary"],
                "deduplication_note": raw["duplicate_amendment_notes"],
            }
        )
    return output


GENERIC_RECIPIENT_TOKENS = {
    "ACCOUNT",
    "ACTION",
    "CAMPAIGN",
    "COMMITTEE",
    "DISTRICT",
    "FL",
    "FLORIDA",
    "FOR",
    "GOV",
    "GROUP",
    "HOUSE",
    "INC",
    "NOP",
    "OF",
    "PAC",
    "PAP",
    "PC",
    "POLITICAL",
    "REP",
    "REPRESENTATIVE",
    "SENATE",
    "STATE",
    "STR",
    "STS",
    "THE",
    "DEM",
}


def recipient_tokens(value: str) -> list[str]:
    return [
        token
        for token in re.sub(r"[^A-Z0-9]+", " ", value.upper()).split()
        if token not in GENERIC_RECIPIENT_TOKENS and len(token) > 1
    ]


def fuzzy_recipient_score(left: str, right: str) -> float:
    """Order-insensitive, token-level similarity for state/FEC recipient names."""
    left_tokens = recipient_tokens(left)
    right_tokens = recipient_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0

    def directional(source: list[str], target: list[str]) -> float:
        return sum(
            max(difflib.SequenceMatcher(None, token, other).ratio() for other in target)
            for token in source
        ) / len(source)

    return (directional(left_tokens, right_tokens) + directional(right_tokens, left_tokens)) / 2


def match_state_fec_pac_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Link high-confidence Florida PAC-label rows to payer-side FEC rows.

    Matching is deliberately narrow: exact positive amount, Florida jurisdiction,
    no more than 45 days between payer and recipient reporting dates, fuzzy name
    score of at least 0.90, and one-to-one greedy assignment by name score and
    then date proximity.  The crosswalk is corroborative; it never adds another
    aggregation-eligible transaction.
    """
    state_rows = [row for row in rows if row["payer_class"] == "geo_pac_ssf_label"]
    fec_rows = [
        row
        for row in rows
        if row["payer_class"] == "geo_pac_ssf"
        and row["jurisdiction_code"] == "FL"
        and Decimal(row["amount"]) > 0
    ]
    candidates: list[tuple[float, int, dict[str, str], dict[str, str]]] = []
    for state_row in state_rows:
        for fec_row in fec_rows:
            if state_row["amount"] != fec_row["amount"]:
                continue
            gap = abs(
                (
                    datetime.fromisoformat(state_row["event_date"])
                    - datetime.fromisoformat(fec_row["event_date"])
                ).days
            )
            if gap > 45:
                continue
            name_score = fuzzy_recipient_score(
                state_row["recipient_name_as_filed"], fec_row["recipient_name_as_filed"]
            )
            if name_score >= 0.90:
                candidates.append((name_score, gap, state_row, fec_row))

    used_state: set[str] = set()
    used_fec: set[str] = set()
    crosswalk: list[dict[str, str]] = []
    for name_score, gap, state_row, fec_row in sorted(
        candidates, key=lambda item: (item[0], -item[1]), reverse=True
    ):
        if state_row["record_id"] in used_state or fec_row["record_id"] in used_fec:
            continue
        used_state.add(state_row["record_id"])
        used_fec.add(fec_row["record_id"])
        match_id = "PACMATCH:" + stable_hash(
            [state_row["record_id"], fec_row["record_id"]]
        )[:20]
        state_row["cross_source_match_id"] = match_id
        state_row["cross_source_match_confidence"] = "high"
        fec_row["cross_source_match_id"] = match_id
        fec_row["cross_source_match_confidence"] = "high"
        state_row["deduplication_note"] += (
            f" High-confidence payer/recipient-source match to {fec_row['record_id']}; "
            "this state row remains aggregation-ineligible."
        )
        fec_row["deduplication_note"] += (
            f" High-confidence payer/recipient-source match to {state_row['record_id']}; "
            "the FEC row remains the canonical PAC aggregate row."
        )
        crosswalk.append(
            {
                "match_id": match_id,
                "confidence": "high",
                "match_rule": (
                    "exact positive amount; Florida jurisdiction; date gap <=45 days; "
                    "recipient token-fuzzy score >=0.90; one-to-one assignment"
                ),
                "name_score": f"{name_score:.6f}",
                "date_gap_days": str(gap),
                "amount": state_row["amount"],
                "state_record_id": state_row["record_id"],
                "state_date": state_row["event_date"],
                "state_payer_as_filed": state_row["payer_legal_name_as_filed"],
                "state_recipient_as_filed": state_row["recipient_name_as_filed"],
                "fec_record_id": fec_row["record_id"],
                "fec_date": fec_row["event_date"],
                "fec_recipient_as_filed": fec_row["recipient_name_as_filed"],
                "fec_transaction_id": fec_row["transaction_id"],
                "fec_sub_id": fec_row["sub_id"],
                "deduplication_disposition": (
                    "same underlying payment corroborated across payer/recipient sources; "
                    "count FEC canonical row once"
                ),
            }
        )
    return sorted(crosswalk, key=lambda row: (row["state_date"], row["match_id"]))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def aggregate_amounts(rows: list[dict[str, str]]) -> dict[tuple[int, str, str], dict[str, Decimal]]:
    aggregates: dict[tuple[int, str, str], dict[str, Decimal]] = defaultdict(
        lambda: {
            "gross_positive": Decimal("0"),
            "negative_adjustments": Decimal("0"),
            "signed_net": Decimal("0"),
            "row_count": Decimal("0"),
            "positive_row_count": Decimal("0"),
            "negative_row_count": Decimal("0"),
        }
    )
    for row in rows:
        if row["aggregation_eligible"] != "true":
            continue
        stream = "corporate" if row["payer_class"] == "geo_corporate_legal_entity" else "geo_pac"
        key = (int(row["calendar_year"]), row["jurisdiction_code"], stream)
        amount = Decimal(row["amount"])
        bucket = aggregates[key]
        bucket["row_count"] += 1
        bucket["signed_net"] += amount
        if amount >= 0:
            bucket["gross_positive"] += amount
            bucket["positive_row_count"] += 1
        else:
            bucket["negative_adjustments"] += amount
            bucket["negative_row_count"] += 1
    return aggregates


def florida_duplicate_sensitivity(
    rows: list[dict[str, str]], year: int
) -> dict[str, Decimal | int]:
    selected = [
        row
        for row in rows
        if row["calendar_year"] == str(year)
        and row["jurisdiction_code"] == "FL"
        and row["payer_class"] == "geo_corporate_legal_entity"
        and row["aggregation_eligible"] == "true"
    ]
    raw_signed = sum((Decimal(row["amount"]) for row in selected), Decimal("0"))
    seen: set[str] = set()
    hypothetical_signed = Decimal("0")
    removed_rows = 0
    for row in selected:
        group_id = row["exact_row_duplicate_group_id"]
        if group_id and group_id in seen:
            removed_rows += 1
            continue
        if group_id:
            seen.add(group_id)
        hypothetical_signed += Decimal(row["amount"])
    return {
        "raw_row_count": len(selected),
        "raw_signed_net": raw_signed,
        "hypothetical_exact_row_collapse_removed_rows": removed_rows,
        "hypothetical_exact_row_collapse_signed_net": hypothetical_signed,
        "warning": (
            "Sensitivity only: exact rows are not asserted duplicates because Florida's "
            "export lacks report, amendment, and check identifiers."
        ),
    }


def build_reconciliation(rows: list[dict[str, str]]) -> dict[str, Any]:
    aggregates = aggregate_amounts(rows)
    reconciliation: dict[str, Any] = {
        "method": {
            "company_report_basis": (
                "Official GEO State / Local table, with columns Type | GEO PAC | Corporate"
            ),
            "florida_basis": (
                "Only Florida rows conservatively classified as GEO corporate legal entities "
                "are compared with GEO's Florida Corporate denominator."
            ),
            "fec_basis": (
                "GEO PAC Schedule B positive payments and signed net are both shown. State "
                "recipient rows representing the same PAC payments are corroboration, not "
                "independent transactions."
            ),
        },
        "years": {},
    }
    for year, company in COMPANY_STATE_LOCAL.items():
        year_obj: dict[str, Any] = {
            "company_state_local_total": company["state_local_total"],
            "company_state_local_corporate_total": sum(
                (item["corporate"] for item in company["jurisdictions"].values()), Decimal("0")
            ),
            "company_state_local_geo_pac_total": sum(
                (item["geo_pac"] for item in company["jurisdictions"].values()), Decimal("0")
            ),
            "jurisdictions": {},
        }
        for jurisdiction, expected in company["jurisdictions"].items():
            corp = aggregates.get(
                (year, jurisdiction, "corporate"),
                {"gross_positive": Decimal("0"), "negative_adjustments": Decimal("0"), "signed_net": Decimal("0"), "row_count": Decimal("0"), "positive_row_count": Decimal("0"), "negative_row_count": Decimal("0")},
            )
            pac = aggregates.get(
                (year, jurisdiction, "geo_pac"),
                {"gross_positive": Decimal("0"), "negative_adjustments": Decimal("0"), "signed_net": Decimal("0"), "row_count": Decimal("0"), "positive_row_count": Decimal("0"), "negative_row_count": Decimal("0")},
            )
            year_obj["jurisdictions"][jurisdiction] = {
                "company": expected,
                "primary_rows": {"corporate": corp, "geo_pac": pac},
                "residual_company_minus_primary_gross_positive": {
                    "corporate": expected["corporate"] - corp["gross_positive"],
                    "geo_pac": expected["geo_pac"] - pac["gross_positive"],
                },
                "residual_company_minus_primary_signed_net": {
                    "corporate": expected["corporate"] - corp["signed_net"],
                    "geo_pac": expected["geo_pac"] - pac["signed_net"],
                },
            }
        if year in {2024, 2025}:
            year_obj["florida_exact_row_collapse_sensitivity"] = florida_duplicate_sensitivity(
                rows, year
            )
        reconciliation["years"][str(year)] = year_obj
    return json_decimal(reconciliation)


def build_quote_audit(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    audit: list[dict[str, str]] = []
    for row in rows:
        quote = row["source_quote"]
        audit.append(
            {
                "record_id": row["record_id"],
                "source_file": row["source_file"],
                "source_file_sha256": row["source_file_sha256"],
                "source_document_url": row["source_document_url"],
                "quote_sha256": sha256_bytes(quote.encode("utf-8")),
                "source_quote": quote,
                "quote_present": "true" if quote else "false",
            }
        )
    return audit


def build_finding_support(
    reconciliation: dict[str, Any], rows: list[dict[str, str]]
) -> dict[str, Any]:
    """Emit compact, quoteable blocks for the lead's aggregate synthesis findings.

    The full reconciliation is optimized for jurisdiction-by-jurisdiction audit and
    therefore separates the values used in one prose claim by hundreds of lines.
    These blocks contain the same values in one contiguous, deterministic object so
    a database evidence quote can semantically support every asserted number.
    """
    pac_jurisdictions = {}
    pac_aggregate = {
        "gross_positive": 0.0,
        "negative_adjustments": 0.0,
        "signed_net": 0.0,
    }
    year_2025 = reconciliation["years"]["2025"]
    for jurisdiction in ("AZ", "OK", "PA"):
        item = year_2025["jurisdictions"][jurisdiction]
        primary = item["primary_rows"]["geo_pac"]
        pac_jurisdictions[jurisdiction] = {
            "company_geo_pac": item["company"]["geo_pac"],
            "fec_gross_positive": primary["gross_positive"],
            "fec_negative_adjustments": primary["negative_adjustments"],
            "fec_signed_net": primary["signed_net"],
        }
        pac_aggregate["gross_positive"] += primary["gross_positive"]
        pac_aggregate["negative_adjustments"] += primary["negative_adjustments"]
        pac_aggregate["signed_net"] += primary["signed_net"]

    florida = {}
    for year in ("2024", "2025"):
        item = reconciliation["years"][year]["jurisdictions"]["FL"]
        primary = item["primary_rows"]["corporate"]
        florida[year] = {
            "corporate_row_count": int(primary["row_count"]),
            "primary_gross_positive": primary["gross_positive"],
            "primary_negative_adjustments": primary["negative_adjustments"],
            "primary_signed_net": primary["signed_net"],
            "company_reported_florida_corporate": item["company"]["corporate"],
            "company_minus_primary_gross_positive": item[
                "residual_company_minus_primary_gross_positive"
            ]["corporate"],
            "company_minus_primary_signed_net": item[
                "residual_company_minus_primary_signed_net"
            ]["corporate"],
        }

    georgia = {}
    georgia_aggregate = {
        "strict_corporate_row_count": 0,
        "strict_corporate_signed_net": 0.0,
        "pac_label_business_class_ambiguity_row_count": 0,
        "pac_label_business_class_ambiguity_signed_net": 0.0,
    }
    for year in ("2024", "2025"):
        item = reconciliation["years"][year]["jurisdictions"]["GA"]
        primary = item["primary_rows"]["corporate"]
        ambiguous = [
            row
            for row in rows
            if row["calendar_year"] == year
            and row["jurisdiction_code"] == "GA"
            and row["payer_class"] == "ambiguous_pac_name_filed_as_business"
        ]
        ambiguous_sum = sum(
            (Decimal(row["amount"]) for row in ambiguous), Decimal("0")
        )
        georgia[year] = {
            "strict_corporate_row_count": int(primary["row_count"]),
            "strict_corporate_signed_net": primary["signed_net"],
            "company_reported_georgia_corporate": item["company"]["corporate"],
            "company_minus_strict_primary": item[
                "residual_company_minus_primary_signed_net"
            ]["corporate"],
            "pac_label_business_class_ambiguity_row_count": len(ambiguous),
            "pac_label_business_class_ambiguity_signed_net": float(ambiguous_sum),
        }
        georgia_aggregate["strict_corporate_row_count"] += int(primary["row_count"])
        georgia_aggregate["strict_corporate_signed_net"] += primary["signed_net"]
        georgia_aggregate["pac_label_business_class_ambiguity_row_count"] += len(
            ambiguous
        )
        georgia_aggregate[
            "pac_label_business_class_ambiguity_signed_net"
        ] += float(ambiguous_sum)

    return {
        "as_of": date.today().isoformat(),
        "lead_id": 59033,
        "geo_pac_2025_reconciliation": {
            "company_state_local_geo_pac_total": year_2025[
                "company_state_local_geo_pac_total"
            ],
            "jurisdictions": pac_jurisdictions,
            "fec_aggregate": pac_aggregate,
        },
        "florida_corporate_reconciliation": florida,
        "georgia_bounded_corporate_reconciliation": {
            "coverage_status": (
                "verified partial primary recovery; company-minus-primary values are "
                "coverage differences, not reporting-error findings"
            ),
            "years": georgia,
            "aggregate": georgia_aggregate,
        },
    }


def build_timing_crosswalk(
    rows: list[dict[str, str]], ice_action_matrix: Path
) -> list[dict[str, str]]:
    with ice_action_matrix.open(encoding="utf-8", newline="") as handle:
        ice_actions = [
            row
            for row in csv.DictReader(handle)
            if row.get("component") == "ICE" and row.get("action_date", "").startswith("2025-")
        ]
    contributions = [
        row
        for row in rows
        if row["calendar_year"] == "2025"
        and row["jurisdiction_code"] == "FL"
        and row["payer_class"] == "geo_corporate_legal_entity"
        and row["aggregation_eligible"] == "true"
    ]
    policy_events = {
        "2025-01": [
            (
                "2025-01-27 Florida Legislature TRUMP Act proposal/special session",
                ALBRITTON_TRUMP_ACT_URL,
            )
        ],
        "2025-02": [
            ("2025-02-19 Florida announces additional ICE 287(g) agreements", FL_287G_URL)
        ],
        "2025-05": [
            (
                "2025-05-12 Florida announces plan for new detention facilities and expanded apprehension",
                FL_DETENTION_PLAN_URL,
            )
        ],
        "2025-07": [("2025-07-04 Public Law 119-21 enacted", PL_119_21_URL)],
    }
    output: list[dict[str, str]] = []
    for month_number in range(1, 13):
        month = f"2025-{month_number:02d}"
        month_contributions = [row for row in contributions if row["event_date"].startswith(month)]
        month_ice = [row for row in ice_actions if row["action_date"].startswith(month)]
        month_broward = [
            row
            for row in month_ice
            if row.get("facility_or_service") == "Broward Transitional Center"
        ]
        events = policy_events.get(month, [])
        output.append(
            {
                "month": month,
                "fl_geo_corporate_row_count": str(len(month_contributions)),
                "fl_geo_corporate_gross_positive": decimal_text(
                    sum(
                        (
                            Decimal(row["amount"])
                            for row in month_contributions
                            if Decimal(row["amount"]) > 0
                        ),
                        Decimal("0"),
                    )
                ),
                "fl_geo_corporate_negative_adjustments": decimal_text(
                    sum(
                        (
                            Decimal(row["amount"])
                            for row in month_contributions
                            if Decimal(row["amount"]) < 0
                        ),
                        Decimal("0"),
                    )
                ),
                "fl_geo_corporate_signed_net": decimal_text(
                    sum((Decimal(row["amount"]) for row in month_contributions), Decimal("0"))
                ),
                "broward_ice_action_count": str(len(month_broward)),
                "broward_ice_net_action_obligation": decimal_text(
                    sum(
                        (Decimal(row["action_obligation"]) for row in month_broward),
                        Decimal("0"),
                    )
                ),
                "all_geo_ice_action_count": str(len(month_ice)),
                "all_geo_ice_net_action_obligation": decimal_text(
                    sum(
                        (Decimal(row["action_obligation"]) for row in month_ice),
                        Decimal("0"),
                    )
                ),
                "policy_events": " | ".join(event[0] for event in events),
                "policy_source_urls": " | ".join(event[1] for event in events),
                "relationship_basis": (
                    "calendar-month co-location only; Florida political rows, federal ICE "
                    "procurement actions, and policy events have different decision makers and sources"
                ),
                "causation_status": "no causal inference",
            }
        )
    return output


def build_recipient_office_crosswalk(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    specs = {
        "FL:a2ee44bb67e033c971ed457c": {
            "official_name": "Ben Albritton",
            "official_role": "President, Florida Senate",
            "office_source_url": ALBRITTON_OFFICE_URL,
            "policy_record": "January 27, 2025 Florida Legislature TRUMP Act proposal",
            "policy_source_url": ALBRITTON_TRUMP_ACT_URL,
            "timing_note": "Contribution was 22 days after the dated policy document.",
        },
        "FL:29747aa1dd36ed801df4fb34": {
            "official_name": "James Uthmeier",
            "official_role": "Attorney General of Florida",
            "office_source_url": UTHEMEIER_OFFICE_URL,
            "policy_record": "Official bio says he was appointed in February 2025.",
            "policy_source_url": UTHEMEIER_OFFICE_URL,
            "timing_note": "Contribution and appointment occurred in the same month; exact appointment day is not stated in the cited bio.",
        },
        "FL:8655cf105d109373a3038798": {
            "official_name": "James Uthmeier",
            "official_role": "Attorney General of Florida",
            "office_source_url": UTHEMEIER_OFFICE_URL,
            "policy_record": "Official bio says he was appointed in February 2025.",
            "policy_source_url": UTHEMEIER_OFFICE_URL,
            "timing_note": "Later contribution while Uthmeier held the cited office.",
        },
        "FL:6a55e5ffdfa960b551e3fa40": {
            "official_name": "James Uthmeier",
            "official_role": "Attorney General of Florida",
            "office_source_url": UTHEMEIER_OFFICE_URL,
            "policy_record": "Official bio says he was appointed in February 2025.",
            "policy_source_url": UTHEMEIER_OFFICE_URL,
            "timing_note": "Direct candidate-name row while Uthmeier held the cited office.",
        },
        "FL:603ef9e439d01d336158bfbb": {
            "official_name": "Byron Donalds",
            "official_role": "U.S. Representative, Florida 19th District",
            "office_source_url": DONALDS_OFFICE_URL,
            "policy_record": "No Florida detention-procurement role established in the cited official bio.",
            "policy_source_url": DONALDS_OFFICE_URL,
            "timing_note": "Official-role identity crosswalk only.",
        },
    }
    by_id = {row["record_id"]: row for row in rows}
    output: list[dict[str, str]] = []
    for record_id, spec in specs.items():
        row = by_id[record_id]
        output.append(
            {
                "record_id": record_id,
                "contribution_date": row["event_date"],
                "amount": row["amount"],
                "payer_as_filed": row["payer_legal_name_as_filed"],
                "recipient_as_filed": row["recipient_name_as_filed"],
                **spec,
                "relationship_basis": (
                    "recipient-name identity plus official office record; campaign-finance "
                    "record does not itself establish committee control or procurement authority"
                ),
                "causation_status": "no causal inference",
            }
        )
    return output


def build_manifest(
    source_dir: Path,
    outputs: list[Path],
    rows: list[dict[str, str]],
    crosswalk: list[dict[str, str]],
    ice_action_matrix: Path,
    finding_provenance_paths: list[Path] | None = None,
    accepted_finding_ids: list[int] | None = None,
    retracted_finding_ids: list[int] | None = None,
    reused_input_paths: list[Path] | None = None,
) -> dict[str, Any]:
    sources = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or path.name == "source-sha256.txt":
            continue
        sources.append(
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payer_counts = Counter(row["payer_class"] for row in rows)
    stream_counts = Counter(row["source_stream"] for row in rows)
    unique_outputs: list[Path] = []
    seen_output_paths: set[str] = set()
    for path in outputs:
        key = str(path)
        if key not in seen_output_paths:
            seen_output_paths.add(key)
            unique_outputs.append(path)

    database_evidence = []
    for path in finding_provenance_paths or []:
        snapshot = json.loads(path.read_text())
        database_evidence.append(
            {
                "finding_id": int(snapshot["id"]),
                "verification_status": snapshot.get("verification_status"),
                "source_datasets": json.loads(snapshot.get("source_datasets") or "[]"),
                "evidence_row_count": len(snapshot.get("evidence") or []),
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "as_of": date.today().isoformat(),
        "lead_id": 59033,
        "source_files": sources,
        "reused_audited_inputs": [
            {
                "path": str(ice_action_matrix),
                "bytes": ice_action_matrix.stat().st_size,
                "sha256": sha256_file(ice_action_matrix),
                "provenance": "lead 57842 exact-matched USAspending ICE action matrix",
            }
        ]
        + [
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "provenance": "visible-agent bounded non-Florida corporate contribution wave",
            }
            for path in reused_input_paths or []
        ],
        "outputs": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in unique_outputs
            if path.exists()
        ],
        "database_evidence": sorted(
            database_evidence, key=lambda item: item["finding_id"]
        ),
        "accepted_finding_ids": sorted(set(accepted_finding_ids or [])),
        "retracted_finding_ids": sorted(set(retracted_finding_ids or [])),
        "ledger_row_count": len(rows),
        "source_stream_row_counts": dict(stream_counts),
        "payer_class_row_counts": dict(payer_counts),
        "high_confidence_state_fec_pac_matches": len(crosswalk),
        "excluded_fec_rows": {
            "count": 3,
            "rationale": (
                "California Secretary of State registration-fee rows, including two "
                "records filed with the typo 'SECRETARY OR STATE', are administrative "
                "fees/voids rather than political payments."
            ),
        },
        "methodological_warnings": [
            "Same-value/date Florida rows were not collapsed because report, amendment, and check IDs are absent.",
            "Florida's state export covers statewide and multicounty filers, not county/municipal filing offices.",
            "FEC payer-side Schedule B and state recipient-side PAC records may describe the same underlying payment.",
            "GEO's political-activity reports state that they are unaudited company disclosures.",
        ],
        "primary_urls": [
            FL_SOURCE_URL,
            FEC_SOURCE_URL,
            GEO_2024_URL,
            GEO_2025_URL,
            ALBRITTON_OFFICE_URL,
            ALBRITTON_TRUMP_ACT_URL,
            UTHEMEIER_OFFICE_URL,
            DONALDS_OFFICE_URL,
            FL_287G_URL,
            FL_DETENTION_PLAN_URL,
            PL_119_21_URL,
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--quote-audit", type=Path, required=True)
    parser.add_argument("--finding-support", type=Path, required=True)
    parser.add_argument("--nonfl-ledger", type=Path)
    parser.add_argument("--nonfl-manifest", type=Path)
    parser.add_argument("--nonfl-report", type=Path)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--ice-action-matrix", type=Path, required=True)
    parser.add_argument("--timing-crosswalk", type=Path, required=True)
    parser.add_argument("--recipient-crosswalk", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--extra-output",
        type=Path,
        action="append",
        default=[],
        help="Additional durable output to hash in the manifest (repeatable).",
    )
    parser.add_argument(
        "--finding-provenance",
        type=Path,
        action="append",
        default=[],
        help="findings_tracker provenance JSON to hash and crosswalk to a DB finding (repeatable).",
    )
    parser.add_argument(
        "--accepted-finding-id", type=int, action="append", default=[]
    )
    parser.add_argument(
        "--retracted-finding-id", type=int, action="append", default=[]
    )
    args = parser.parse_args()

    fl_rows = parse_florida_rows(args.source_dir)
    fec_rows = parse_fec_rows(args.source_dir / "fec-c00382150-all-disbursements-2015-2026.json")
    nonfl_rows = parse_nonfl_corporate_rows(args.nonfl_ledger, args.nonfl_manifest)
    rows = sorted(
        fl_rows + fec_rows + nonfl_rows,
        key=lambda row: (row["event_date"], row["record_id"]),
    )
    crosswalk = match_state_fec_pac_rows(rows)
    timing_crosswalk = build_timing_crosswalk(rows, args.ice_action_matrix)
    recipient_crosswalk = build_recipient_office_crosswalk(rows)

    write_csv(args.ledger, rows, LEDGER_FIELDS)
    write_csv(
        args.crosswalk,
        crosswalk,
        [
            "match_id",
            "confidence",
            "match_rule",
            "name_score",
            "date_gap_days",
            "amount",
            "state_record_id",
            "state_date",
            "state_payer_as_filed",
            "state_recipient_as_filed",
            "fec_record_id",
            "fec_date",
            "fec_recipient_as_filed",
            "fec_transaction_id",
            "fec_sub_id",
            "deduplication_disposition",
        ],
    )
    write_csv(
        args.timing_crosswalk,
        timing_crosswalk,
        [
            "month",
            "fl_geo_corporate_row_count",
            "fl_geo_corporate_gross_positive",
            "fl_geo_corporate_negative_adjustments",
            "fl_geo_corporate_signed_net",
            "broward_ice_action_count",
            "broward_ice_net_action_obligation",
            "all_geo_ice_action_count",
            "all_geo_ice_net_action_obligation",
            "policy_events",
            "policy_source_urls",
            "relationship_basis",
            "causation_status",
        ],
    )
    write_csv(
        args.recipient_crosswalk,
        recipient_crosswalk,
        [
            "record_id",
            "contribution_date",
            "amount",
            "payer_as_filed",
            "recipient_as_filed",
            "official_name",
            "official_role",
            "office_source_url",
            "policy_record",
            "policy_source_url",
            "timing_note",
            "relationship_basis",
            "causation_status",
        ],
    )
    reconciliation = build_reconciliation(rows)
    args.reconciliation.parent.mkdir(parents=True, exist_ok=True)
    args.reconciliation.write_text(json.dumps(reconciliation, indent=2, sort_keys=True) + "\n")
    finding_support = build_finding_support(reconciliation, rows)
    args.finding_support.parent.mkdir(parents=True, exist_ok=True)
    args.finding_support.write_text(
        json.dumps(finding_support, indent=2, sort_keys=True) + "\n"
    )
    quote_audit = build_quote_audit(rows)
    write_csv(
        args.quote_audit,
        quote_audit,
        [
            "record_id",
            "source_file",
            "source_file_sha256",
            "source_document_url",
            "quote_sha256",
            "source_quote",
            "quote_present",
        ],
    )
    manifest = build_manifest(
        args.source_dir,
        [
            args.ledger,
            args.reconciliation,
            args.quote_audit,
            args.finding_support,
            args.crosswalk,
            args.timing_crosswalk,
            args.recipient_crosswalk,
            *args.extra_output,
            *args.finding_provenance,
        ],
        rows,
        crosswalk,
        args.ice_action_matrix,
        args.finding_provenance,
        args.accepted_finding_id,
        args.retracted_finding_id,
        [
            path
            for path in (args.nonfl_ledger, args.nonfl_manifest, args.nonfl_report)
            if path is not None
        ],
    )
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(
        json.dumps(
            {
                "ledger_rows": len(rows),
                "florida_rows": len(fl_rows),
                "fec_state_local_rows": len(fec_rows),
                "nonfl_corporate_rows": len(nonfl_rows),
                "high_confidence_state_fec_pac_matches": len(crosswalk),
                "payer_classes": dict(Counter(row["payer_class"] for row in rows)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
