#!/usr/bin/env python3
"""Query Delaware County, Ohio Common Pleas CourtView records.

The public portal uses rendered, session-bound Apache Wicket actions.  A
persistent headed-browser helper resolves those actions for party/company
search, exact cases, dockets, and linked PDF images.  Saved packets may be
normalized with ``--input`` for reproducible review and tests.

Examples:
    uv run python tools/query_ohio_delaware_common_pleas.py warmup --json
    uv run python tools/query_ohio_delaware_common_pleas.py search-party \
        --last-name Smith --first-name J --output smith.json
    uv run python tools/query_ohio_delaware_common_pleas.py case \
        "16 CV C 06 0330" --output case.json
    uv run python tools/query_ohio_delaware_common_pleas.py documents \
        "16 CV C 06 0330" --json
    uv run python tools/query_ohio_delaware_common_pleas.py document \
        "16 CV C 06 0330" dktdoc-... --document-output filing.pdf --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from tools.public_records_store import canonical_court_ref
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-oh-delaware-common-pleas-courtview"
COURT_ID = "oh-delaware-common-pleas"
COURT_NAME = "Delaware County Court of Common Pleas"
STATE_CODE = "OH"
COUNTY_FIPS = "39041"
HOME_URL = "https://court.co.delaware.oh.us/eservices/home.page"
SEARCH_GUIDE_URL = (
    "https://co.delaware.oh.us/wp-content/uploads/2019/06/"
    "eFiling-Searching-Public-Portal.pdf"
)
PUBLIC_RECORDS_POLICY_URL = (
    "https://clerkofcourts.co.delaware.oh.us/wp-content/uploads/sites/9/"
    "2022/07/Delaware-County-Common-Pleas-Court-Public-Records-Policy-"
    "June-2022.pdf"
)
CLERK_CONTACT_URL = "https://co.delaware.oh.us/contactus-copy/"
HELPER_PATH = Path(__file__).with_name(
    "_ohio_delaware_common_pleas_browser_helper.js"
)
DEFAULT_BROWSER_TIMEOUT = 180.0
ADAPTER_FAMILY = "equivant_courtview_wicket"
CURSOR_PREFIX = "delaware-courtview:offset:"
OBSERVED_AT = "2026-08-03"

SOURCE_WARNINGS = (
    "The portal combines General, Domestic Relations, Probate, Juvenile, and "
    "Fifth District case types; each record retains its displayed case type.",
    "Domestic Relations filing images are not viewable online to the general "
    "public, and Juvenile and Probate image access has additional limitations.",
    "CourtView Wicket links are session transport values; case and document "
    "records use displayed or derived identities instead of those URLs.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Delaware County Ohio CourtView public portal",
    source_role="county_common_pleas_party_case_docket_and_document_portal",
    base_url=HOME_URL,
    dataset_id=SOURCE_ID,
    metadata={
        "authority": COURT_NAME,
        "court_id": COURT_ID,
        "state_code": STATE_CODE,
        "county_fips": COUNTY_FIPS,
        "platform_family": ADAPTER_FAMILY,
        "access": "anonymous_session_with_interactive_challenge",
        "native_page_sizes": [25, 50, 75, 100],
        "search_guide_url": SEARCH_GUIDE_URL,
        "public_records_policy_url": PUBLIC_RECORDS_POLICY_URL,
        "clerk_contact_url": CLERK_CONTACT_URL,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-oh-delaware-county",
    name="Delaware County, Ohio",
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
    locality="Delaware County",
    metadata={"court_id": COURT_ID},
)

SOURCE_CATALOG_METADATA = {
    SOURCE_ID: {
        "source_id": SOURCE_ID,
        "record_identity_source_id": SOURCE_ID,
        "name": "Delaware County Ohio CourtView public portal",
        "authority": COURT_NAME,
        "domain": "court",
        "court_id": COURT_ID,
        "state_code": STATE_CODE,
        "county_fips": COUNTY_FIPS,
        "url": HOME_URL,
        "adapter": "tools/query_ohio_delaware_common_pleas.py",
        "platform_family": ADAPTER_FAMILY,
        "operations": [
            "source",
            "runtime_check",
            "warmup",
            "probe",
            "search_party",
            "search_company",
            "case",
            "docket",
            "documents",
            "document",
        ],
        "roles": [
            "party_name_search",
            "company_name_search",
            "exact_case_lookup",
            "case_docket",
            "public_filing_images",
        ],
        "access": {
            "authentication": "none",
            "interactive_challenge": "session_bootstrap",
            "browser_profile": "persistent_headed_by_default",
        },
        "paging": {
            "default": "exhaustive",
            "native_page_sizes": [25, 50, 75, 100],
            "cursor": "query_bound_offset_replay",
        },
        "monitor": {
            "mode": "rendered_browser_contract_probe",
            "fixed_request_budget": None,
            "challenge_state": "access_observation",
        },
        "complementary_sources": [
            {
                "kind": "official_search_instructions",
                "url": SEARCH_GUIDE_URL,
            },
            {
                "kind": "official_record_and_copy_request",
                "url": PUBLIC_RECORDS_POLICY_URL,
            },
            {
                "kind": "clerk_contact",
                "url": CLERK_CONTACT_URL,
            },
            {
                "source_id": "us-oh-delaware-county-recorder-pax",
                "kind": "recorded_instruments",
                "join_keys": ["party_name", "address", "instrument_number"],
            },
            {
                "source_id": "us-oh-delaware-sheriff-realauction",
                "kind": "sheriff_sales",
                "join_keys": ["case_number", "parcel_id", "address"],
            },
        ],
        "observed_at": OBSERVED_AT,
    }
}


class DelawareCourtViewError(RuntimeError):
    """Structured adapter error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "source",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.retryable = retryable
        self.details = dict(details or {})


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _required_text(value: Any, field: str) -> str:
    cleaned = _text(value)
    if cleaned is None:
        raise DelawareCourtViewError(
            "source_field_missing",
            f"CourtView record lacks {field}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return cleaned


def _source_date(value: Any) -> str | None:
    cleaned = _text(value)
    if cleaned is None or cleaned.lower().startswith("xx/"):
        return None
    for pattern in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(cleaned, pattern).date().isoformat()
        except ValueError:
            pass
    return None


def _amount(value: Any) -> float | None:
    cleaned = _text(value)
    if cleaned is None:
        return None
    numeric = cleaned.replace("$", "").replace(",", "")
    try:
        return float(numeric)
    except ValueError:
        return None


def _case_ref(case_number: str, record_kind: str = "case", native_id: str | None = None) -> str:
    return canonical_court_ref(
        SOURCE_ID,
        COURT_ID,
        case_number,
        record_kind,
        native_id,
    )


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "court_level": "common_pleas",
        "official_url": HOME_URL,
    }


def _normalized_case_number(value: Any) -> str:
    return (_text(value) or "").upper()


def document_identity_payload(case_number: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the docket occurrence fields used for a durable document ID."""

    return {
        "case_number": _text(case_number) or "",
        "date": _text(row.get("date")) or "",
        "description": _text(row.get("description")) or "",
        "docket_text": _text(row.get("docket_text")) or "",
        "amount_owed": _text(row.get("amount_owed")) or "",
        "amount_due": _text(row.get("amount_due")) or "",
        "duplicate_ordinal": int(row.get("duplicate_ordinal") or 0),
    }


def derive_document_id(case_number: str, row: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        canonical_json(document_identity_payload(case_number, row)).encode("utf-8")
    ).hexdigest()
    return f"dktdoc-{digest[:24]}"


def _selector_parameters(args: argparse.Namespace) -> dict[str, Any]:
    command = args.command
    if command == "search-party":
        return {
            "last_name": _text(args.last_name),
            "first_name": _text(args.first_name),
            "middle_name": _text(args.middle_name),
            "suffix": _text(args.suffix),
            "case_types": list(args.case_type),
            "case_statuses": list(args.case_status),
            "party_types": list(args.party_type),
            "dob_from": args.dob_from,
            "dob_to": args.dob_to,
            "dod_from": args.dod_from,
            "dod_to": args.dod_to,
            "filed_from": args.filed_from,
            "filed_to": args.filed_to,
        }
    if command == "search-company":
        return {
            "company_name": _text(args.company_name),
            "case_types": list(args.case_type),
            "case_statuses": list(args.case_status),
            "party_types": list(args.party_type),
            "filed_from": args.filed_from,
            "filed_to": args.filed_to,
        }
    if command in {"case", "docket", "documents"}:
        return {"case_number": _text(args.case_number)}
    if command == "document":
        return {
            "case_number": _text(args.case_number),
            "document_id": _text(args.document_id),
            "document_output": str(Path(args.document_output).resolve()),
        }
    if command == "warmup":
        return {"wait_seconds": args.wait_seconds}
    return {}


def _cursor_binding(command: str, parameters: Mapping[str, Any]) -> str:
    return sha256_fingerprint(
        {"source_id": SOURCE_ID, "operation": command, "parameters": parameters}
    )


def encode_cursor(binding: str, offset: int) -> str:
    payload = canonical_json(
        {"version": 1, "source_id": SOURCE_ID, "binding": binding, "offset": offset}
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def decode_cursor(cursor: str, binding: str) -> int:
    if not cursor.startswith(CURSOR_PREFIX):
        raise DelawareCourtViewError(
            "cursor_invalid",
            "cursor does not belong to the Delaware CourtView adapter",
            category="query_selection",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding))
    except (ValueError, json.JSONDecodeError) as error:
        raise DelawareCourtViewError(
            "cursor_invalid",
            "cursor is not valid encoded JSON",
            category="query_selection",
        ) from error
    if (
        payload.get("version") != 1
        or payload.get("source_id") != SOURCE_ID
        or payload.get("binding") != binding
        or not isinstance(payload.get("offset"), int)
        or payload["offset"] < 0
    ):
        raise DelawareCourtViewError(
            "cursor_query_mismatch",
            "cursor is not bound to this exact CourtView query",
            category="query_selection",
        )
    return int(payload["offset"])


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters = _selector_parameters(args)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command.replace("-", "_"),
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={"court_id": COURT_ID, "adapter_family": ADAPTER_FAMILY},
        ),
    )


def _load_packet(input_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DelawareCourtViewError(
            "input_packet_invalid",
            f"could not read browser packet: {error}",
            category="input",
        ) from error
    if not isinstance(payload, dict):
        raise DelawareCourtViewError(
            "input_packet_invalid",
            "browser packet must be a JSON object",
            category="input",
        )
    return payload


def _run_helper(
    operation: str,
    arguments: Sequence[str] = (),
    *,
    timeout: float = DEFAULT_BROWSER_TIMEOUT,
) -> dict[str, Any]:
    if shutil.which("node") is None:
        raise DelawareCourtViewError(
            "browser_runtime_unavailable",
            "Node.js was not found",
            category="runtime",
        )
    command = ["node", str(HELPER_PATH), operation, *arguments]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise DelawareCourtViewError(
            "browser_timeout",
            f"CourtView browser helper exceeded {timeout:g} seconds",
            category="transport",
            retryable=True,
        ) from error
    stdout = completed.stdout.strip().splitlines()
    payload: dict[str, Any] | None = None
    if stdout:
        try:
            candidate = json.loads(stdout[-1])
            if isinstance(candidate, dict):
                payload = candidate
        except json.JSONDecodeError:
            payload = None
    if payload is None:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise DelawareCourtViewError(
            "browser_helper_failed",
            message or "CourtView browser helper returned no JSON packet",
            category="runtime",
        )
    if completed.returncode != 0:
        helper_status = _text(payload.get("status"))
        status = (
            ResultStatus.SOURCE_CHANGED
            if helper_status == "source_changed"
            else ResultStatus.UNAVAILABLE
        )
        raise DelawareCourtViewError(
            helper_status or "browser_helper_failed",
            _text(payload.get("error")) or "CourtView browser helper failed",
            status=status,
            category=(
                "source_schema" if status == ResultStatus.SOURCE_CHANGED else "runtime"
            ),
            details={
                "error_type": payload.get("error_type"),
                "source_url": payload.get("source_url"),
            },
        )
    return payload


def _helper_arguments(args: argparse.Namespace) -> tuple[str, list[str]]:
    if args.command == "runtime-check":
        return "runtime-check", []
    if args.command == "warmup":
        return "warmup", ["--wait-seconds", str(args.wait_seconds)]
    if args.command == "probe":
        return "probe", []
    if args.command in {"search-party", "search-company"}:
        helper = [
            "--mode",
            "person" if args.command == "search-party" else "company",
        ]
        if args.command == "search-party":
            helper.extend(["--last", args.last_name])
            for option, value in (
                ("--first", args.first_name),
                ("--middle", args.middle_name),
                ("--suffix", args.suffix),
                ("--dob-from", args.dob_from),
                ("--dob-to", args.dob_to),
                ("--dod-from", args.dod_from),
                ("--dod-to", args.dod_to),
            ):
                if value:
                    helper.extend([option, value])
        else:
            helper.extend(["--company", args.company_name])
        for option, values in (
            ("--case-type", args.case_type),
            ("--case-status", args.case_status),
            ("--party-type", args.party_type),
        ):
            for value in values:
                helper.extend([option, value])
        for option, value in (
            ("--filed-from", args.filed_from),
            ("--filed-to", args.filed_to),
        ):
            if value:
                helper.extend([option, value])
        return "search", helper
    if args.command in {"case", "docket", "documents"}:
        return "case", [args.case_number]
    if args.command == "document":
        return "document", [
            args.case_number,
            args.document_id,
            str(Path(args.document_output).resolve()),
        ]
    raise DelawareCourtViewError(
        "unsupported_command",
        f"unsupported command: {args.command}",
        category="query_selection",
    )


def _challenge_error(packet: Mapping[str, Any]) -> DelawareCourtViewError | None:
    if packet.get("status") != "captcha_required":
        return None
    return DelawareCourtViewError(
        "captcha_required",
        "CourtView needs the visible session challenge completed in the headed browser",
        status=ResultStatus.HUMAN_REQUIRED,
        category="access",
        details={
            "source_url": packet.get("source_url") or HOME_URL,
            "access": packet.get("access") or {},
            "observed": packet.get("observed") or {},
        },
    )


def _source_record() -> dict[str, Any]:
    metadata = SOURCE_CATALOG_METADATA[SOURCE_ID]
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "record_kind": "source_manifest",
        "canonical_ref": f"SOURCE:{SOURCE_ID}",
        "name": metadata["name"],
        "authority": metadata["authority"],
        "source_url": HOME_URL,
        "court": _court_payload(),
        "platform_family": ADAPTER_FAMILY,
        "operations": list(metadata["operations"]),
        "roles": list(metadata["roles"]),
        "access": dict(metadata["access"]),
        "paging": dict(metadata["paging"]),
        "monitor": dict(metadata["monitor"]),
        "complementary_sources": list(metadata["complementary_sources"]),
        "identity_contract": {
            "case": "source-displayed case number within court namespace",
            "party_search_row": "raw occurrence; duplicate rows are retained",
            "docket_document": "derived from case and docket occurrence fields",
            "transport_values": "not record identity",
        },
        "image_scope_notice": SOURCE_WARNINGS[1],
        "observed_at": OBSERVED_AT,
    }


def normalize_probe(packet: Mapping[str, Any]) -> dict[str, Any]:
    challenge = _challenge_error(packet)
    if challenge:
        raise challenge
    contract = packet.get("contract")
    if packet.get("status") != "ok" or not isinstance(contract, Mapping):
        raise DelawareCourtViewError(
            "probe_packet_invalid",
            "CourtView probe packet lacks its rendered contract",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    page_options = packet.get("native_page_size_options") or []
    page_sizes = []
    for option in page_options:
        if isinstance(option, Mapping) and str(option.get("text", "")).isdigit():
            page_sizes.append(int(option["text"]))
    stable_contract = {
        "platform_family": packet.get("platform_family"),
        "form_method": contract.get("form_method"),
        "person_fields": list(contract.get("person_fields") or []),
        "company_field": bool(contract.get("company_field")),
        "date_fields": list(contract.get("date_fields") or []),
        "option_counts": {
            key: len(value)
            for key, value in (contract.get("option_sets") or {}).items()
            if isinstance(value, list)
        },
        "native_page_sizes": page_sizes,
    }
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "record_kind": "source_probe",
        "canonical_ref": f"SOURCEPROBE:{SOURCE_ID}",
        "source_url": HOME_URL,
        "access_state": "ready",
        "courtview_version": _text(contract.get("courtview_version")),
        "copyright_year": contract.get("copyright_year"),
        "native_page_size": packet.get("native_page_size"),
        "contract": stable_contract,
        "schema_fingerprint": sha256_fingerprint(stable_contract),
        "rolling_observations": {
            "courtview_version": _text(contract.get("courtview_version")),
            "copyright_year": contract.get("copyright_year"),
        },
    }


def normalize_search_rows(
    packet: Mapping[str, Any],
    *,
    query_binding: str | None = None,
) -> list[dict[str, Any]]:
    challenge = _challenge_error(packet)
    if challenge:
        raise challenge
    if packet.get("status") not in {"ok", "no_results"}:
        raise DelawareCourtViewError(
            "search_packet_invalid",
            "CourtView search packet has no authoritative result state",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    rows = packet.get("rows")
    if not isinstance(rows, list):
        raise DelawareCourtViewError(
            "search_packet_invalid",
            "CourtView search packet lacks rows[]",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    total = packet.get("total_reported")
    if not isinstance(total, int) or total != len(rows):
        raise DelawareCourtViewError(
            "search_incomplete",
            "CourtView packet does not contain every reported party occurrence",
            status=ResultStatus.PARTIAL,
            category="pagination",
            details={"total_reported": total, "rows": len(rows)},
        )
    records: list[dict[str, Any]] = []
    for occurrence_index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise DelawareCourtViewError(
                "search_row_invalid",
                "CourtView search row is not an object",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
            )
        case_number = _required_text(row.get("case_number"), "case_number")
        native_occurrence_id = None
        if query_binding is not None:
            native_occurrence_id = "searchocc-" + hashlib.sha256(
                canonical_json(
                    {
                        "query_fingerprint": query_binding,
                        "exhaustive_occurrence_ordinal": occurrence_index,
                    }
                ).encode("utf-8")
            ).hexdigest()[:24]
        records.append(
            {
                "source_id": SOURCE_ID,
                "court_id": COURT_ID,
                "native_court_id": COURT_ID,
                "court": _court_payload(),
                "state_code": STATE_CODE,
                "county_geoid": COUNTY_FIPS,
                "record_kind": "party_case_occurrence",
                "canonical_ref": _case_ref(case_number),
                "case_number": case_number,
                "display_case_number": case_number,
                "normalized_case_number": _normalized_case_number(case_number),
                "native_occurrence_id": native_occurrence_id,
                "search_query_fingerprint": query_binding,
                "exhaustive_occurrence_ordinal": occurrence_index,
                "party_name": _text(row.get("party_company")),
                "affiliation": _text(row.get("affiliation")),
                "party_type": _text(row.get("party_type")),
                "file_date": _source_date(row.get("file_date")),
                "file_date_raw": _text(row.get("file_date")),
                "case_status": _text(row.get("case_status")),
                "case_type": _text(row.get("case_type")),
                "date_of_birth_display": _text(row.get("date_of_birth")),
                "party_occurrence_index": occurrence_index,
                "source_page": row.get("source_page"),
                "source_row": row.get("source_row"),
                "source_url": HOME_URL,
                "raw": dict(row),
            }
        )
    return records


def _normalize_docket(case_number: str, row: Mapping[str, Any]) -> dict[str, Any]:
    duplicate_ordinal = int(row.get("duplicate_ordinal") or 0)
    identity = document_identity_payload(case_number, row)
    docket_occurrence_id = "dkt-" + hashlib.sha256(
        canonical_json(identity).encode("utf-8")
    ).hexdigest()[:24]
    record = {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "docket_entry",
        "canonical_case_ref": _case_ref(case_number),
        "case_number": case_number,
        "docket_occurrence_id": docket_occurrence_id,
        "date": _source_date(row.get("date")),
        "date_raw": _text(row.get("date")),
        "description": _text(row.get("description")),
        "docket_text": _text(row.get("docket_text")),
        "amount_owed": _amount(row.get("amount_owed")),
        "amount_due": _amount(row.get("amount_due")),
        "duplicate_ordinal": duplicate_ordinal,
        "source_index": row.get("source_index"),
        "document_link_present": bool(row.get("document_link_present")),
        "document_access_state": (
            "link_present" if row.get("document_link_present") else "not_listed"
        ),
        "source_url": HOME_URL,
        "raw": dict(row),
    }
    if record["document_link_present"]:
        expected = derive_document_id(case_number, row)
        supplied = _text(row.get("document_id"))
        if supplied is not None and supplied != expected:
            raise DelawareCourtViewError(
                "document_identity_mismatch",
                "browser packet document identity does not match docket fields",
                status=ResultStatus.SOURCE_CHANGED,
                category="normalization",
            )
        record["document_id"] = expected
    else:
        record["document_id"] = None
    return record


def normalize_case_packet(packet: Mapping[str, Any]) -> dict[str, Any] | None:
    challenge = _challenge_error(packet)
    if challenge:
        raise challenge
    if packet.get("status") == "no_results":
        return None
    case = packet.get("case")
    if packet.get("status") != "ok" or not isinstance(case, Mapping):
        raise DelawareCourtViewError(
            "case_packet_invalid",
            "CourtView exact-case packet lacks case data",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    case_number = _required_text(case.get("case_number"), "case_number")
    detail_paging_controls = case.get("detail_paging_controls") or []
    if detail_paging_controls:
        raise DelawareCourtViewError(
            "case_detail_paging_unresolved",
            "CourtView rendered case-detail paging controls not present in the verified contract",
            status=ResultStatus.PARTIAL,
            category="pagination",
            details={"controls": detail_paging_controls},
        )
    summary = dict(case.get("summary") or {})
    docket = [
        _normalize_docket(case_number, row)
        for row in case.get("docket") or []
        if isinstance(row, Mapping)
    ]
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "case",
        "canonical_ref": _case_ref(case_number),
        "case_number": case_number,
        "display_case_number": case_number,
        "normalized_case_number": _normalized_case_number(case_number),
        "caption": _text(case.get("caption")),
        "case_type": _text(summary.get("Case Type")),
        "case_status": _text(summary.get("Case Status")),
        "file_date": _source_date(summary.get("File Date")),
        "file_date_raw": _text(summary.get("File Date")),
        "action": _text(summary.get("Action")),
        "status_date": _source_date(summary.get("Status Date")),
        "judge": _text(summary.get("Case Judge")),
        "next_event": _text(summary.get("Next Event")),
        "parties": [dict(item) for item in case.get("parties") or []],
        "docket": docket,
        "events": [dict(item) for item in case.get("events") or []],
        "financial_tables": [
            dict(item) for item in case.get("financial_tables") or []
        ],
        "source_search_occurrences": [
            dict(item) for item in packet.get("occurrences") or []
        ],
        "source_url": HOME_URL,
        "raw_summary": summary,
    }


def _document_records(case_record: Mapping[str, Any]) -> list[dict[str, Any]]:
    case_number = _required_text(case_record.get("case_number"), "case_number")
    documents = []
    for docket in case_record.get("docket") or []:
        if not isinstance(docket, Mapping) or not docket.get("document_link_present"):
            continue
        document_id = _required_text(docket.get("document_id"), "document_id")
        documents.append(
            {
                "source_id": SOURCE_ID,
                "court_id": COURT_ID,
                "native_court_id": COURT_ID,
                "court": _court_payload(),
                "state_code": STATE_CODE,
                "county_geoid": COUNTY_FIPS,
                "record_kind": "case_document_listing",
                "canonical_ref": _case_ref(
                    case_number, "document", native_id=document_id
                ),
                "canonical_case_ref": _case_ref(case_number),
                "case_number": case_number,
                "document_id": document_id,
                "document_access_state": "link_present",
                "filed_date": docket.get("date"),
                "description": docket.get("description"),
                "docket_text": docket.get("docket_text"),
                "docket_occurrence_id": docket.get("docket_occurrence_id"),
                "source_index": docket.get("source_index"),
                "source_url": HOME_URL,
            }
        )
    return documents


def normalize_document_packet(packet: Mapping[str, Any]) -> dict[str, Any] | None:
    challenge = _challenge_error(packet)
    if challenge:
        raise challenge
    if packet.get("status") == "no_results":
        return None
    document = packet.get("document")
    artifact = packet.get("artifact")
    case = packet.get("case")
    if not all(isinstance(value, Mapping) for value in (document, artifact, case)):
        raise DelawareCourtViewError(
            "document_packet_invalid",
            "CourtView document packet lacks document, case, or artifact data",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    case_number = _required_text(case.get("case_number"), "case_number")
    docket = _normalize_docket(case_number, document)
    document_id = derive_document_id(case_number, document)
    supplied = _required_text(packet.get("requested_document_id"), "document_id")
    if supplied != document_id:
        raise DelawareCourtViewError(
            "document_identity_mismatch",
            "downloaded artifact does not match the requested docket occurrence",
            status=ResultStatus.SOURCE_CHANGED,
            category="normalization",
        )
    sha256 = _required_text(artifact.get("sha256"), "artifact.sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise DelawareCourtViewError(
            "document_hash_invalid",
            "CourtView artifact SHA-256 is invalid",
            status=ResultStatus.SOURCE_CHANGED,
            category="artifact",
        )
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "case_document_artifact",
        "canonical_ref": _case_ref(case_number, "document", native_id=document_id),
        "canonical_case_ref": _case_ref(case_number),
        "case_number": case_number,
        "caption": _text(case.get("caption")),
        "document_id": document_id,
        "filed_date": _source_date(document.get("date")),
        "description": _text(document.get("description")),
        "docket_text": _text(document.get("docket_text")),
        "docket_occurrence_id": docket["docket_occurrence_id"],
        "source_index": docket.get("source_index"),
        "document_link_present": True,
        "document_access_state": "retrieved",
        "artifact_path": _required_text(artifact.get("output_path"), "output_path"),
        "artifact_sha256": sha256,
        "artifact_byte_size": int(artifact.get("byte_size") or 0),
        "artifact_content_type": _text(artifact.get("content_type")),
        "source_url": HOME_URL,
    }


def _failure(query: PublicRecordsQuery, error: DelawareCourtViewError) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=error.category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    helper_runner: Callable[..., Mapping[str, Any]] | None = None,
) -> PublicRecordsResult:
    query = build_query(args)
    input_path = getattr(args, "input", None)
    raw_refs: tuple[str, ...] = ()
    try:
        if args.command == "source":
            records = [_source_record()]
            return PublicRecordsResult.success(query, records, warnings=SOURCE_WARNINGS)

        helper_operation, helper_args = _helper_arguments(args)
        if input_path:
            resolved = Path(input_path).resolve()
            packet = _load_packet(resolved)
            raw_refs = (str(resolved),)
        else:
            runner = helper_runner or _run_helper
            packet = dict(
                runner(helper_operation, helper_args, timeout=args.browser_timeout)
            )

        if args.command == "runtime-check":
            records = [
                {
                    "source_id": SOURCE_ID,
                    "court_id": COURT_ID,
                    "record_kind": "browser_runtime",
                    "canonical_ref": f"RUNTIME:{SOURCE_ID}",
                    **packet,
                }
            ]
            return PublicRecordsResult.success(query, records, warnings=SOURCE_WARNINGS)
        if args.command == "warmup":
            challenge = _challenge_error(packet)
            if challenge:
                raise challenge
            if packet.get("status") != "ok":
                raise DelawareCourtViewError(
                    "warmup_failed", "CourtView session did not become ready"
                )
            records = [
                {
                    "source_id": SOURCE_ID,
                    "court_id": COURT_ID,
                    "record_kind": "browser_session",
                    "canonical_ref": f"SESSION:{SOURCE_ID}",
                    "source_url": HOME_URL,
                    "access_state": "ready",
                    "session_ready": True,
                }
            ]
        elif args.command == "probe":
            records = [normalize_probe(packet)]
        elif args.command in {"search-party", "search-company"}:
            parameters = _selector_parameters(args)
            binding = _cursor_binding(args.command, parameters)
            all_records = normalize_search_rows(packet, query_binding=binding)
            offset = decode_cursor(args.cursor, binding) if args.cursor else 0
            if offset > len(all_records):
                raise DelawareCourtViewError(
                    "cursor_offset_invalid",
                    "cursor offset is beyond the current exhaustive result set",
                    category="query_selection",
                )
            end = len(all_records) if args.limit is None else offset + args.limit
            records = all_records[offset:end]
            next_cursor = None
            if end < len(all_records):
                next_cursor = encode_cursor(binding, end)
            return PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                raw_artifact_refs=raw_refs,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command in {"case", "docket", "documents"}:
            case_record = normalize_case_packet(packet)
            if case_record is None:
                records = []
            elif args.command == "case":
                records = [case_record]
            elif args.command == "docket":
                records = list(case_record["docket"])
            else:
                records = _document_records(case_record)
        elif args.command == "document":
            document = normalize_document_packet(packet)
            records = [] if document is None else [document]
        else:
            raise DelawareCourtViewError(
                "unsupported_command",
                f"unsupported command: {args.command}",
                category="query_selection",
            )
        return PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=raw_refs,
            warnings=SOURCE_WARNINGS,
        )
    except DelawareCourtViewError as error:
        return _failure(query, error)
    except (TypeError, ValueError, KeyError) as error:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="normalization",
                )
            ],
            raw_artifact_refs=raw_refs,
            warnings=SOURCE_WARNINGS,
        )


def _date_arg(value: str) -> str:
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.strftime("%m/%d/%Y")
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("date must be MM/DD/YYYY or YYYY-MM-DD")


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _nonnegative_float(value: str) -> float:
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return number


def _runtime_args(parser: argparse.ArgumentParser, *, input_packet: bool = True) -> None:
    if input_packet:
        parser.add_argument("--input", type=Path, help="Normalize a saved helper packet")
    parser.add_argument(
        "--browser-timeout",
        type=_nonnegative_float,
        default=DEFAULT_BROWSER_TIMEOUT,
    )
    add_output_args(parser)


def _filters(parser: argparse.ArgumentParser, *, person_dates: bool) -> None:
    parser.add_argument("--case-type", action="append", default=[])
    parser.add_argument("--case-status", action="append", default=[])
    parser.add_argument("--party-type", action="append", default=[])
    parser.add_argument("--filed-from", type=_date_arg)
    parser.add_argument("--filed-to", type=_date_arg)
    if person_dates:
        parser.add_argument("--dob-from", type=_date_arg)
        parser.add_argument("--dob-to", type=_date_arg)
        parser.add_argument("--dod-from", type=_date_arg)
        parser.add_argument("--dod-to", type=_date_arg)
    parser.add_argument("--limit", type=_positive_int)
    parser.add_argument("--cursor")
    _runtime_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser("source", help="Show verified source contract")
    add_output_args(source)

    runtime = subparsers.add_parser("runtime-check", help="Inspect browser runtime")
    _runtime_args(runtime, input_packet=True)

    warmup = subparsers.add_parser(
        "warmup", help="Open or restore the headed CourtView session"
    )
    warmup.add_argument("--wait-seconds", type=_nonnegative_float, default=0)
    _runtime_args(warmup)

    probe = subparsers.add_parser("probe", help="Verify rendered source contract")
    _runtime_args(probe)

    party = subparsers.add_parser(
        "search-party", help="Search raw party occurrences by person name"
    )
    party.add_argument("--last-name", required=True)
    party.add_argument("--first-name")
    party.add_argument("--middle-name")
    party.add_argument("--suffix")
    _filters(party, person_dates=True)

    company = subparsers.add_parser(
        "search-company", help="Search raw party occurrences by company name"
    )
    company.add_argument("company_name")
    _filters(company, person_dates=False)

    for command, help_text in (
        ("case", "Return one exact case with all rendered sections"),
        ("docket", "Return every rendered docket occurrence for an exact case"),
        ("documents", "List docket occurrences with image actions"),
    ):
        child = subparsers.add_parser(command, help=help_text)
        child.add_argument("case_number")
        _runtime_args(child)

    document = subparsers.add_parser(
        "document", help="Resolve and retrieve one current docket image action"
    )
    document.add_argument("case_number")
    document.add_argument("document_id")
    document.add_argument("--document-output", type=Path, required=True)
    _runtime_args(document)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Delaware County CourtView {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Delaware County CourtView {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
