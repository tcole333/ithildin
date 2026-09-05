#!/usr/bin/env python3
"""Query Wisconsin appellate case, docket, RSS, and public-document records.

WSCCA's published web application uses a public-use acknowledgment and an
invisible hCaptcha validation before its JSON case APIs return data. Browser
operations delegate that UI flow to ``_wisconsin_wscca_browser_helper.js``.
The per-case RSS feed remains a distinct, directly retrievable operation.

Examples:
    uv run python tools/query_wisconsin_wscca.py search \
        "Wisconsin Voter Alliance" --scope business --json
    uv run python tools/query_wisconsin_wscca.py case 2025AP000699 --json
    uv run python tools/query_wisconsin_wscca.py docket 2025AP000699 \
        --output /tmp/wscca-docket.json
    uv run python tools/query_wisconsin_wscca.py documents 2025AP000699 --json
    uv run python tools/query_wisconsin_wscca.py download \
        2025AP000699 994970 --document-output /tmp/brief.pdf --json
    uv run python tools/query_wisconsin_wscca.py rss 2025AP000699 --json
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from tools.lead_tracker import log_search
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
    )
    from tools.public_records_http import inferred_schema, schema_fingerprint
    from tools.public_records_store import canonical_court_ref
except ImportError:
    from lead_tracker import log_search
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
    )
    from public_records_http import inferred_schema, schema_fingerprint
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-wi-wscca-public"
STATE_CODE = "WI"
STATE_GEOID = "55"
BASE_URL = "https://wscca.wicourts.gov"
SEARCH_URL = f"{BASE_URL}/case-search"
HELPER_PATH = Path(__file__).with_name("_wisconsin_wscca_browser_helper.js")

SUPREME_COURT_ID = "wi-supreme-court"
COURT_OF_APPEALS_ID = "wi-court-of-appeals"
APPELLATE_COURTS_ID = "wi-appellate-courts"

SOURCE_WARNINGS = (
    "WSCCA states that case coverage generally includes appeals considered open "
    "from the end of 1993 forward.",
    "WSCCA lists eFiled briefs filed on or after July 1, 2009 and adds some "
    "scanned non-eFiled briefs; a docket event without a document link is not "
    "treated as proof that no document exists.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Wisconsin Supreme Court and Court of Appeals Case Access",
    source_role="appellate_case_index_docket_and_public_documents",
    base_url=BASE_URL,
    dataset_id="wscca-public",
    metadata={
        "authority": "Wisconsin Court System",
        "operator": "Clerk of the Supreme Court and Court of Appeals",
        "state_code": STATE_CODE,
        "state_geoid": STATE_GEOID,
        "platform_family": "wscca_public_interactive_portal",
        "authentication": "public_use_acknowledgment",
        "search_validation": "source_invisible_hcaptcha",
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-wi",
    name="Wisconsin",
    state_code=STATE_CODE,
    metadata={"state_geoid": STATE_GEOID},
)

HelperRunner = Callable[[Sequence[str], float], Mapping[str, Any]]


class WSCCASelectionError(ValueError):
    """A selector or cursor cannot be represented by the source adapter."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


class WSCCABrowserError(RuntimeError):
    """The source-specific browser helper reported a structured failure."""

    def __init__(
        self,
        message: str,
        *,
        error_type: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.details = dict(details or {})


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _case_number(value: Any) -> str:
    normalized = re.sub(r"\s+", "", str(value or "")).upper()
    if not normalized:
        raise WSCCASelectionError(
            "missing_case_number",
            "An appellate case number is required",
        )
    return normalized


def _date_parts(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return datetime(
            int(value["y"]),
            int(value["m"]),
            int(value["d"]),
        ).date().isoformat()
    except (KeyError, TypeError, ValueError):
        return None


def _rss_date(value: str | None) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    try:
        parsed = parsedate_to_datetime(normalized)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.isoformat()
    return parsed.isoformat()


def _source_schema(payload: Mapping[str, Any]) -> str:
    return schema_fingerprint(inferred_schema([payload]))


def _court_payload(
    court_type: Any,
    *,
    district: Any = None,
) -> dict[str, Any]:
    code = (_text(court_type) or "").upper()
    district_number = _text(district)
    if code == "SC":
        return {
            "court_id": SUPREME_COURT_ID,
            "native_court_id": "SC",
            "name": "Wisconsin Supreme Court",
            "state_code": STATE_CODE,
            "level": "supreme",
            "division": None,
        }
    if code == "CA":
        return {
            "court_id": COURT_OF_APPEALS_ID,
            "native_court_id": "CA",
            "name": "Wisconsin Court of Appeals",
            "state_code": STATE_CODE,
            "level": "appellate",
            "division": (
                f"District {district_number}" if district_number else None
            ),
        }
    return {
        "court_id": APPELLATE_COURTS_ID,
        "native_court_id": code or None,
        "name": "Wisconsin Supreme Court and Court of Appeals",
        "state_code": STATE_CODE,
        "level": "appellate",
        "division": (
            f"District {district_number}" if district_number else None
        ),
    }


def _name(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return _text(value)
    pieces = [
        _text(value.get("nameF")),
        _text(value.get("nameM")),
        _text(value.get("nameL")),
        _text(value.get("suffix")),
    ]
    return " ".join(piece for piece in pieces if piece) or None


def _addresses(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"native_visibility_state": None, "addresses": []}
    rows: list[dict[str, Any]] = []
    payload = value.get("p")
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            street = " ".join(
                part
                for part in (
                    _text(item.get("primAddr")),
                    _text(item.get("secAddr")),
                )
                if part
            ) or None
            rows.append(
                {
                    "street": street,
                    "city": _text(item.get("city")),
                    "state": _text(item.get("state")),
                    "postal_code": _text(item.get("zip")),
                    "country": _text(item.get("country")),
                    "source_fields": dict(item),
                }
            )
    return {
        "native_visibility_state": _text(value.get("c")),
        "addresses": rows,
    }


def _page_range(value: Any) -> dict[str, Any]:
    raw = _text(value)
    result: dict[str, Any] = {
        "page_range_raw": raw,
        "first_page": None,
        "last_page": None,
        "page_count": None,
    }
    if raw is None:
        return result
    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", raw)
    if match:
        first, last = (int(match.group(1)), int(match.group(2)))
        result.update(
            {
                "first_page": first,
                "last_page": last,
                "page_count": last - first + 1 if last >= first else None,
            }
        )
    return result


def _normalize_document(
    row: Mapping[str, Any],
    *,
    case_number: str,
    court: Mapping[str, Any],
) -> dict[str, Any]:
    document_id = _text(row.get("docId"))
    if document_id is None:
        raise ValueError("WSCCA document row lacks docId")
    source_url = (
        f"{BASE_URL}/api/case/{case_number}/document/{document_id}"
    )
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            str(court["court_id"]),
            case_number,
            "document",
            document_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "document",
        "court": dict(court),
        "raw_case_number": case_number,
        "native_document_id": document_id,
        "native_event_sequence": row.get("eventSeqNo"),
        "document_name": _text(row.get("docName")),
        "document_type": _text(row.get("eventDescr")),
        "native_event_code": _text(row.get("eventCode")),
        "filed_date": _date_parts(row.get("docStampDate")),
        **_page_range(row.get("pages")),
        "access_state": "public",
        "artifact_state": "available_pdf",
        "media_type": "application/pdf",
        "source_url": source_url,
        "source_fields": dict(row),
    }


def _normalize_event(
    row: Mapping[str, Any],
    *,
    case_number: str,
    court: Mapping[str, Any],
    phase: str,
    documents_by_event: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    sequence = row.get("eventSeqNo")
    native_id = _text(sequence)
    if native_id is None:
        raise ValueError("WSCCA event row lacks eventSeqNo")
    linked = [
        dict(document)
        for document in documents_by_event.get(int(sequence), ())
    ]
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            str(court["court_id"]),
            case_number,
            "docket_entry",
            native_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "docket_entry",
        "court": dict(court),
        "raw_case_number": case_number,
        "native_entry_id": native_id,
        "native_event_sequence": sequence,
        "phase": phase,
        "native_status_code": _text(row.get("eventStatusCode")),
        "native_court_type": _text(row.get("courtTypeCode")),
        "filed_date": _date_parts(row.get("filingDate")),
        "due_date": _date_parts(row.get("dueDate")),
        "description": _text(row.get("descr")),
        "comment": _text(row.get("additionalText")),
        "detail": _text(row.get("subEventText")),
        "linked_documents": linked,
        "source_url": f"{BASE_URL}/case/{case_number}#pastEvents",
        "source_fields": dict(row),
    }


def _normalize_search_row(row: Mapping[str, Any]) -> dict[str, Any]:
    case_number = _case_number(row.get("sccaCaseNo"))
    court = _court_payload(
        row.get("courtType"),
        district=row.get("districtNo"),
    )
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court["court_id"],
            case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_number,
        "caption": _text(row.get("shortCaption")),
        "filing_date": _date_parts(row.get("filingDate")),
        "case_type": _text(row.get("wcisClsCodeDescr")),
        "county": _text(row.get("ccCounty")),
        "district": _text(row.get("districtNo")),
        "public_domain_citations": list(row.get("pdcNos") or []),
        "source_url": f"{BASE_URL}/case/{case_number}",
        "source_fields": dict(row),
    }


def _normalize_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    case_data = payload.get("caseData")
    if not isinstance(case_data, Mapping):
        raise ValueError("WSCCA case response lacks caseData")
    case_number = _case_number(case_data.get("sccaCaseNo"))
    court = _court_payload(
        case_data.get("courtType"),
        district=case_data.get("districtNo"),
    )

    documents = [
        _normalize_document(item, case_number=case_number, court=court)
        for item in payload.get("documents") or []
        if isinstance(item, Mapping)
    ]
    documents_by_event: dict[int, list[dict[str, Any]]] = {}
    for document in documents:
        sequence = document.get("native_event_sequence")
        if isinstance(sequence, int):
            documents_by_event.setdefault(sequence, []).append(document)

    parties: list[dict[str, Any]] = []
    attorneys: list[dict[str, Any]] = []
    for party_row in payload.get("parties") or []:
        if not isinstance(party_row, Mapping):
            continue
        address_data = _addresses(party_row.get("addresses"))
        party = {
            "raw_name": _name(party_row.get("name")),
            "roles": [
                _text(value)
                for value in party_row.get("partyTypes") or []
                if _text(value)
            ],
            "native_party_sequence": party_row.get("partySeqNo"),
            **address_data,
            "source_fields": dict(party_row),
        }
        parties.append(party)
        for attorney_row in party_row.get("attorneys") or []:
            if not isinstance(attorney_row, Mapping):
                continue
            attorneys.append(
                {
                    "raw_name": _name(attorney_row.get("name")),
                    "native_attorney_sequence": attorney_row.get("attySeqNo"),
                    "native_party_sequence": attorney_row.get("partySeqNo"),
                    "entered_date": _date_parts(
                        attorney_row.get("enteredDate")
                    ),
                    "withdrawn_date": _date_parts(
                        attorney_row.get("withdrewDate")
                    ),
                    "source_fields": dict(attorney_row),
                }
            )

    interested_parties: list[dict[str, Any]] = []
    for item in payload.get("interestedParties") or []:
        if not isinstance(item, Mapping):
            continue
        interested_parties.append(
            {
                "raw_name": _name(item.get("name")),
                "role": _text(item.get("partyTypeDescr")),
                "comment": _text(item.get("comments")),
                "native_party_sequence": item.get("otherIntPartySeqNo"),
                **_addresses(item.get("address")),
                "source_fields": dict(item),
            }
        )

    linked_circuit_cases: list[dict[str, Any]] = []
    for item in payload.get("ccCaseData") or []:
        if not isinstance(item, Mapping):
            continue
        linked_circuit_cases.append(
            {
                "raw_case_number": _text(item.get("ccCaseNo")),
                "county": _text(item.get("ccCounty")),
                "native_county_number": item.get("ccCountyNo"),
                "circuit_court_judge": _text(item.get("ctofcName")),
                "responsible_circuit_court_judge": _text(
                    item.get("respCtofcName")
                ),
                "source_url": _text(item.get("legacyCaseLink")),
                "source_id": "us-wi-wcca-public",
                "source_fields": dict(item),
            }
        )

    past_events = [
        _normalize_event(
            item,
            case_number=case_number,
            court=court,
            phase="past",
            documents_by_event=documents_by_event,
        )
        for item in payload.get("pastEvents") or []
        if isinstance(item, Mapping)
    ]
    upcoming_events = [
        _normalize_event(
            item,
            case_number=case_number,
            court=court,
            phase="upcoming",
            documents_by_event=documents_by_event,
        )
        for item in payload.get("upcomingEvents") or []
        if isinstance(item, Mapping)
    ]

    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court["court_id"],
            case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": case_number,
        "caption": _text(case_data.get("shortCaption")),
        "long_caption": _text(case_data.get("longCaption")),
        "status": _text(case_data.get("statusDescr")),
        "native_status_code": _text(case_data.get("statusCode")),
        "case_type": _text(case_data.get("wcisClsCodeDescr")),
        "native_case_class_code": _text(case_data.get("wcisClsCode")),
        "filing_date": _date_parts(case_data.get("filingDate")),
        "county": _text(case_data.get("countyName")),
        "native_county_number": case_data.get("countyNo"),
        "filing_district": _text(case_data.get("filingDistrictNo")),
        "current_district": _text(case_data.get("districtNo")),
        "panel_size": _text(case_data.get("casePanelSize")),
        "disposition": _text(case_data.get("dispoCodeDescr")),
        "native_disposition_code": _text(case_data.get("dispoCode")),
        "disposition_date": _date_parts(case_data.get("dispoDate")),
        "source_confidential_flag": case_data.get("isConfidential"),
        "access_state": "public_metadata",
        "parties": parties,
        "attorneys": attorneys,
        "interested_parties": interested_parties,
        "linked_circuit_cases": linked_circuit_cases,
        "past_events": past_events,
        "upcoming_events": upcoming_events,
        "docket_entries": [*past_events, *upcoming_events],
        "documents": documents,
        "published_citations": [
            dict(item)
            for item in payload.get("pubCitnData") or []
            if isinstance(item, Mapping)
        ],
        "other_citations": [
            dict(item)
            for item in payload.get("citnData") or []
            if isinstance(item, Mapping)
        ],
        "opinion_documents": [
            {
                **dict(item),
                "source_url": (
                    "https://www.wicourts.gov/other/appeals/caopin.jsp"
                    f"?docket_number={case_number}"
                ),
                "source_id": "us-wi-court-opinions",
            }
            for item in payload.get("opinionDecisionDocuments") or []
            if isinstance(item, Mapping)
        ],
        "consolidated_cases": [
            dict(item)
            for item in payload.get("consolCaseData") or []
            if isinstance(item, Mapping)
        ],
        "rss_url": f"{BASE_URL}/rss/case/{case_number}",
        "source_url": f"{BASE_URL}/case/{case_number}",
        "source_schema": _source_schema(payload),
        "source_fields": dict(case_data),
    }


def _strip_html(value: str) -> str:
    decoded = html.unescape(value)
    with_breaks = re.sub(r"</(?:div|li|p|ul)>", "\n", decoded, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", with_breaks)).strip()


def parse_rss(xml_bytes: bytes, *, case_number: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("WSCCA RSS response lacks channel")
    records: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        guid = _text(item.findtext("guid"))
        if guid is None:
            raise ValueError("WSCCA RSS item lacks guid")
        guid_match = re.fullmatch(
            rf"{re.escape(case_number)}-(\d+)",
            guid,
            flags=re.I,
        )
        native_event_id = guid_match.group(1) if guid_match else guid
        native_event_sequence = (
            int(guid_match.group(1)) if guid_match else None
        )
        description_raw = item.findtext("description") or ""
        description_text = _strip_html(description_raw)
        if re.search(r"\bCourt:\s*Supreme Court\b", description_text, re.I):
            court = _court_payload("SC")
        elif re.search(
            r"\bCourt:\s*Court of Appeals\b",
            description_text,
            re.I,
        ):
            court = _court_payload("CA")
        else:
            court = _court_payload(None)
        links = re.findall(
            r'href=["\']([^"\']+)["\']',
            html.unescape(description_raw),
            flags=re.I,
        )
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    court["court_id"],
                    case_number,
                    "docket_entry",
                    native_event_id,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "docket_entry",
                "court": court,
                "raw_case_number": case_number,
                "native_entry_id": native_event_id,
                "native_event_sequence": native_event_sequence,
                "native_rss_guid": guid,
                "title": _text(item.findtext("title")),
                "published_at": _rss_date(item.findtext("pubDate")),
                "description": description_text,
                "description_html": description_raw,
                "linked_source_urls": links,
                "source_url": f"{BASE_URL}/rss/case/{case_number}",
            }
        )
    return records


def _run_helper(
    arguments: Sequence[str],
    timeout: float,
) -> Mapping[str, Any]:
    command = ["node", str(HELPER_PATH), *arguments]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = completed.stdout.strip()
    payload: Mapping[str, Any] | None = None
    if output:
        try:
            candidate = json.loads(output)
        except json.JSONDecodeError:
            candidate = None
        if isinstance(candidate, Mapping):
            payload = candidate
    if payload is not None and payload.get("ok") is False:
        raise WSCCABrowserError(
            _text(payload.get("error")) or "WSCCA browser helper failed",
            error_type=_text(payload.get("error_type")) or "Error",
            details=(
                payload.get("details")
                if isinstance(payload.get("details"), Mapping)
                else {}
            ),
        )
    if completed.returncode != 0:
        raise WSCCABrowserError(
            _text(completed.stderr) or "WSCCA browser helper exited unsuccessfully",
            error_type="HelperProcessError",
            details={"returncode": completed.returncode},
        )
    if payload is None:
        raise WSCCABrowserError(
            "WSCCA browser helper returned unparseable output",
            error_type="HelperProtocolError",
            details={"stdout_prefix": output[:240]},
        )
    return payload


def _call_helper(
    runner: HelperRunner,
    arguments: Sequence[str],
    *,
    timeout: float,
    attempts: int,
) -> Mapping[str, Any]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return runner(arguments, timeout)
        except (subprocess.TimeoutExpired, WSCCABrowserError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(min(1.0 + attempt, 2.0))
    assert last_error is not None
    raise last_error


def _fetch_rss(
    case_number: str,
    *,
    timeout: float,
    attempts: int,
    minimum_interval: float,
) -> bytes:
    source_url = f"{BASE_URL}/rss/case/{case_number}"
    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "Ithildin-OSINT/1.0 (+public-record research)"},
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        if minimum_interval:
            time.sleep(minimum_interval)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                media_type = (
                    response.headers.get_content_type()
                    if response.headers
                    else None
                )
                if media_type not in {"application/rss+xml", "text/xml", "application/xml"}:
                    raise ValueError(
                        f"WSCCA RSS returned unexpected media type {media_type!r}"
                    )
                return body
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(min(1.0 + attempt, 2.0))
    assert last_error is not None
    raise last_error


def _query(
    operation: str,
    *,
    parameters: Mapping[str, Any],
    requested_limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _cursor_offset(cursor: str | None, *, prefix: str) -> int:
    if cursor is None:
        return 0
    match = re.fullmatch(rf"{re.escape(prefix)}(\d+)", cursor)
    if not match:
        raise WSCCASelectionError(
            "invalid_cursor",
            f"Cursor must match {prefix}<offset>",
            details={"cursor": cursor},
        )
    return int(match.group(1))


def _slice_records(
    records: Sequence[Mapping[str, Any]],
    *,
    limit: int | None,
    cursor: str | None,
    prefix: str,
) -> tuple[list[Mapping[str, Any]], str | None]:
    offset = _cursor_offset(cursor, prefix=prefix)
    if offset > len(records):
        raise WSCCASelectionError(
            "cursor_out_of_range",
            "Cursor offset exceeds the retrieved source window",
            details={"cursor": cursor, "retrieved_count": len(records)},
        )
    if limit is None:
        return list(records[offset:]), None
    end = min(offset + limit, len(records))
    next_cursor = f"{prefix}{end}" if end < len(records) else None
    return list(records[offset:end]), next_cursor


def source_routes() -> list[dict[str, Any]]:
    return [
        {
            "record_kind": "source_route",
            "source_id": SOURCE_ID,
            "name": "WSCCA public appellate case access",
            "operations": [
                "search_cases",
                "fetch_case",
                "list_docket_entries",
                "list_documents",
                "fetch_document",
                "case_rss",
            ],
            "coverage": (
                "Wisconsin Supreme Court and Court of Appeals; generally appeals "
                "considered open from the end of 1993 forward"
            ),
            "document_coverage": (
                "eFiled briefs from July 1, 2009 forward plus source-added "
                "scanned non-eFiled briefs"
            ),
            "source_url": BASE_URL,
        },
        {
            "record_kind": "source_route",
            "source_id": "us-wi-wcca-public",
            "name": "Wisconsin Circuit Court Access",
            "operations": ["fetch_linked_circuit_case", "search_circuit_cases"],
            "adds": "Circuit case metadata, docket entries, judgments, and calendars",
            "gaps": "Public circuit search is separate from appellate case documents",
            "source_url": "https://wcca.wicourts.gov/",
        },
        {
            "record_kind": "source_route",
            "source_id": "us-wi-court-opinions",
            "name": "Wisconsin Court System opinions",
            "operations": ["search_opinions", "fetch_opinion"],
            "adds": "Official Supreme Court and Court of Appeals opinion PDFs",
            "gaps": "Published decision text does not replace the appellate docket or briefs",
            "source_url": "https://www.wicourts.gov/opinions/",
        },
        {
            "record_kind": "source_route",
            "source_id": "us-wi-state-law-library-briefs",
            "name": "Wisconsin State Law Library briefs and document order",
            "operations": ["locate_brief", "order_document"],
            "adds": "Brief and appendix coverage, including items not linked in WSCCA",
            "gaps": "Some holdings require a targeted copy order",
            "source_url": "https://wilawlibrary.gov/search/briefs.html",
            "order_url": "https://wilawlibrary.gov/services/order.html",
        },
        {
            "record_kind": "source_route",
            "source_id": "us-wi-uw-law-historical-briefs",
            "name": "UW Law historical Wisconsin briefs",
            "operations": ["search_historical_briefs", "fetch_historical_brief"],
            "adds": (
                "Briefs and appendices for decisions in 173 Wis. 2d through "
                "317 Wis. 2d"
            ),
            "gaps": "Historical collection ends around the July 2009 WSCCA transition",
            "source_url": (
                "https://repository.law.wisc.edu/s/uwlaw/page/wisconsin-briefs"
            ),
        },
        {
            "record_kind": "source_route",
            "source_id": "us-wi-wcca-rest",
            "name": "Wisconsin WCCA REST subscription",
            "operations": ["obtain_feed", "sync_circuit_case_metadata"],
            "adds": "Agreement-based circuit case data and correction/deletion handling",
            "gaps": "Circuit metadata feed; filed documents are outside that product",
            "source_url": (
                "https://www.wicourts.gov/courts/resources/docs/"
                "RESTagreementpaid.pdf"
            ),
        },
        {
            "record_kind": "source_route",
            "source_id": "us-wi-appellate-clerk",
            "name": "Clerk of the Supreme Court and Court of Appeals",
            "operations": ["verify_case", "request_document"],
            "adds": "Official verification and targeted records unavailable online",
            "source_url": (
                "https://www.wicourts.gov/courts/offices/clerkcontact.htm"
            ),
        },
    ]


def _failure_result(
    query: PublicRecordsQuery,
    error: Exception,
    *,
    records: Sequence[Mapping[str, Any]] = (),
) -> PublicRecordsResult:
    if isinstance(error, WSCCASelectionError):
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code=error.code,
                    message=str(error),
                    category="query",
                    retryable=False,
                    details=error.details,
                )
            ],
            records=records,
            warnings=SOURCE_WARNINGS,
        )
    if isinstance(error, WSCCABrowserError):
        if error.error_type == "SourceChallengeError":
            status = ResultStatus.HUMAN_REQUIRED
            code = "source_validation_required"
            category = "source_challenge"
            retryable = True
        elif error.error_type == "DocumentStateError":
            status = ResultStatus.HUMAN_REQUIRED
            code = "document_not_listed"
            category = "record_access"
            retryable = False
        elif error.error_type == "RuntimeDependencyError":
            status = ResultStatus.UNAVAILABLE
            code = "browser_runtime_unavailable"
            category = "runtime"
            retryable = False
        else:
            status = ResultStatus.UNAVAILABLE
            code = "browser_operation_failed"
            category = "transport"
            retryable = True
        return PublicRecordsResult.failure(
            query,
            status,
            [
                PublicRecordsError(
                    code=code,
                    message=str(error),
                    category=category,
                    retryable=retryable,
                    details={
                        **error.details,
                        "alternatives": source_routes()[1:],
                    },
                )
            ],
            records=records,
            warnings=SOURCE_WARNINGS,
        )
    if isinstance(error, subprocess.TimeoutExpired):
        return PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="browser_timeout",
                    message="WSCCA browser operation timed out",
                    category="transport",
                    retryable=True,
                    details={"timeout_seconds": error.timeout},
                )
            ],
            records=records,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="source_request_failed",
                message=str(error),
                category="transport",
                retryable=True,
            )
        ],
        records=records,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    helper_runner: HelperRunner = _run_helper,
    log_results: bool = True,
) -> PublicRecordsResult:
    parameters: dict[str, Any]
    if args.command == "search":
        parameters = {
            "query": args.query,
            "scope": args.scope,
            "first_name": args.first_name,
            "middle_name": args.middle_name,
            "county": args.county,
            "similar_names": args.similar_names,
            "include_missing_middle": not args.exclude_missing_middle,
        }
    elif args.command in {"case", "docket", "documents", "rss"}:
        parameters = {"case_number": _case_number(args.case_number)}
    elif args.command == "download":
        parameters = {
            "case_number": _case_number(args.case_number),
            "document_id": str(args.document_id),
            "document_output": str(Path(args.document_output).resolve()),
        }
    elif args.command == "probe":
        parameters = {"case_number": _case_number(args.case_number)}
    else:
        parameters = {}

    query = _query(
        args.command,
        parameters=parameters,
        requested_limit=getattr(args, "limit", None),
        cursor=getattr(args, "cursor", None),
    )

    try:
        if args.command == "routes":
            result = PublicRecordsResult.success(
                query,
                source_routes(),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "runtime-check":
            payload = _call_helper(
                helper_runner,
                ["runtime-check"],
                timeout=args.timeout,
                attempts=args.attempts,
            )
            result = PublicRecordsResult.success(
                query,
                [{"record_kind": "runtime_probe", **dict(payload)}],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            payload = _call_helper(
                helper_runner,
                [
                    "probe",
                    "--case",
                    args.case_number,
                    "--minimum-interval",
                    str(args.minimum_interval),
                ],
                timeout=args.timeout,
                attempts=args.attempts,
            )
            result = PublicRecordsResult.success(
                query,
                [{"record_kind": "source_probe", **dict(payload)}],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "search":
            helper_args = [
                "search",
                "--scope",
                args.scope,
                "--query",
                args.query,
                "--minimum-interval",
                str(args.minimum_interval),
            ]
            if args.first_name:
                helper_args.extend(["--first-name", args.first_name])
            if args.middle_name:
                helper_args.extend(["--middle-name", args.middle_name])
            if args.county:
                helper_args.extend(["--county", args.county])
            if args.similar_names:
                helper_args.append("--similar-names")
            if args.exclude_missing_middle:
                helper_args.append("--exclude-missing-middle")
            payload = _call_helper(
                helper_runner,
                helper_args,
                timeout=args.timeout,
                attempts=args.attempts,
            )
            records = [
                _normalize_search_row(row)
                for row in payload.get("records") or []
                if isinstance(row, Mapping)
            ]
            sliced, next_cursor = _slice_records(
                records,
                limit=args.limit,
                cursor=args.cursor,
                prefix="wscca:search:offset:",
            )
            total_reported = payload.get("total_reported")
            if (
                isinstance(total_reported, int)
                and total_reported > len(records)
            ):
                result = PublicRecordsResult.failure(
                    query,
                    ResultStatus.PARTIAL,
                    [
                        PublicRecordsError(
                            code="source_window_incomplete",
                            message=(
                                "WSCCA reported more cases than the browser "
                                "application returned in its result payload"
                            ),
                            category="source_pagination",
                            retryable=True,
                            details={
                                "total_reported": total_reported,
                                "retrieved_count": len(records),
                                "selectors": payload.get("selectors"),
                            },
                        )
                    ],
                    records=sliced,
                    next_cursor=next_cursor,
                    raw_artifact_refs=[
                        value
                        for value in (
                            _text(payload.get("count_api_url")),
                            _text(payload.get("search_api_url")),
                        )
                        if value
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                result = PublicRecordsResult.success(
                    query,
                    sliced,
                    next_cursor=next_cursor,
                    raw_artifact_refs=[
                        value
                        for value in (
                            _text(payload.get("count_api_url")),
                            _text(payload.get("search_api_url")),
                        )
                        if value
                    ],
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command in {"case", "docket", "documents"}:
            payload = _call_helper(
                helper_runner,
                [
                    "case",
                    parameters["case_number"],
                    "--minimum-interval",
                    str(args.minimum_interval),
                ],
                timeout=args.timeout,
                attempts=args.attempts,
            )
            if payload.get("found") is False or not isinstance(
                payload.get("result"), Mapping
            ):
                result = PublicRecordsResult.success(
                    query,
                    [],
                    raw_artifact_refs=[
                        value
                        for value in (
                            _text(payload.get("source_url")),
                            _text(payload.get("api_url")),
                        )
                        if value
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                case_record = _normalize_case(payload["result"])
                if args.command == "case":
                    records: list[Mapping[str, Any]] = [case_record]
                    next_cursor = None
                elif args.command == "docket":
                    records, next_cursor = _slice_records(
                        case_record["docket_entries"],
                        limit=args.limit,
                        cursor=args.cursor,
                        prefix="wscca:docket:offset:",
                    )
                else:
                    records, next_cursor = _slice_records(
                        case_record["documents"],
                        limit=args.limit,
                        cursor=args.cursor,
                        prefix="wscca:documents:offset:",
                    )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    raw_artifact_refs=[
                        value
                        for value in (
                            _text(payload.get("source_url")),
                            _text(payload.get("api_url")),
                        )
                        if value
                    ],
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command == "download":
            payload = _call_helper(
                helper_runner,
                [
                    "download",
                    parameters["case_number"],
                    parameters["document_id"],
                    parameters["document_output"],
                    "--minimum-interval",
                    str(args.minimum_interval),
                ],
                timeout=args.timeout,
                attempts=args.attempts,
            )
            if payload.get("found") is False:
                result = PublicRecordsResult.success(
                    query,
                    [],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                receipt = payload.get("receipt")
                document = payload.get("document")
                if not isinstance(receipt, Mapping) or not isinstance(
                    document, Mapping
                ):
                    raise ValueError("WSCCA download response lacks artifact receipt")
                case_number = _case_number(payload.get("case_number"))
                court = _court_payload(payload.get("court_type"))
                document_id = _text(document.get("docId"))
                if document_id is None:
                    raise ValueError("WSCCA download response lacks docId")
                parent_ref = canonical_court_ref(
                    SOURCE_ID,
                    court["court_id"],
                    case_number,
                    "document",
                    document_id,
                )
                artifact = {
                    "canonical_ref": canonical_court_ref(
                        SOURCE_ID,
                        court["court_id"],
                        case_number,
                        "document_artifact",
                        document_id,
                    ),
                    "source_id": SOURCE_ID,
                    "record_kind": "document_artifact",
                    "court": court,
                    "raw_case_number": case_number,
                    "native_document_id": document_id,
                    "parent_document_ref": parent_ref,
                    "document_name": _text(document.get("docName")),
                    "document_type": _text(document.get("eventDescr")),
                    "filed_date": _date_parts(document.get("docStampDate")),
                    **_page_range(document.get("pages")),
                    "artifact_state": "acquired",
                    "certification_status": "source_public_copy",
                    "media_type": _text(receipt.get("media_type")),
                    "byte_count": receipt.get("byte_count"),
                    "sha256": _text(receipt.get("sha256")),
                    "local_path": _text(receipt.get("local_path")),
                    "source_url": _text(payload.get("source_url")),
                    "source_status": receipt.get("source_status"),
                    "source_fields": dict(document),
                }
                result = PublicRecordsResult.success(
                    query,
                    [artifact],
                    raw_artifact_refs=[
                        value
                        for value in (
                            artifact["source_url"],
                            artifact["local_path"],
                        )
                        if value
                    ],
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command == "rss":
            xml_bytes = _fetch_rss(
                parameters["case_number"],
                timeout=args.timeout,
                attempts=args.attempts,
                minimum_interval=args.minimum_interval,
            )
            records = parse_rss(
                xml_bytes,
                case_number=parameters["case_number"],
            )
            sliced, next_cursor = _slice_records(
                records,
                limit=args.limit,
                cursor=args.cursor,
                prefix="wscca:rss:offset:",
            )
            result = PublicRecordsResult.success(
                query,
                sliced,
                next_cursor=next_cursor,
                raw_artifact_refs=[
                    f"{BASE_URL}/rss/case/{parameters['case_number']}"
                ],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise AssertionError(f"unhandled command: {args.command}")
    except (TypeError, ValueError, ET.ParseError) as error:
        if isinstance(error, WSCCASelectionError):
            result = _failure_result(query, error)
        else:
            result = PublicRecordsResult.failure(
                query,
                ResultStatus.SOURCE_CHANGED,
                [
                    PublicRecordsError(
                        code="normalization_failed",
                        message=str(error),
                        category="source_schema",
                        retryable=False,
                    )
                ],
                warnings=SOURCE_WARNINGS,
            )
    except (
        WSCCABrowserError,
        subprocess.TimeoutExpired,
        urllib.error.URLError,
        TimeoutError,
    ) as error:
        result = _failure_result(query, error)

    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    if log_results:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=240.0,
        help="Total browser or HTTP attempt timeout in seconds",
    )
    parser.add_argument(
        "--attempts",
        type=_positive_int,
        default=2,
        help="Bounded attempts for transient browser or transport failures",
    )
    parser.add_argument(
        "--minimum-interval",
        type=_non_negative_float,
        default=0.5,
        help="Minimum delay before a source operation, in seconds",
    )


def _add_page_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=_positive_int)
    parser.add_argument("--cursor")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Wisconsin WSCCA appellate cases, dockets, RSS, and public PDFs"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search WSCCA by party, business, or appellate case number",
    )
    search.add_argument("query")
    search.add_argument(
        "--scope",
        choices=("party", "business", "case-number"),
        default="party",
    )
    search.add_argument("--first-name")
    search.add_argument("--middle-name")
    search.add_argument("--county")
    search.add_argument("--similar-names", action="store_true")
    search.add_argument("--exclude-missing-middle", action="store_true")
    _add_page_args(search)
    _add_transport_args(search)
    add_output_args(search)

    for command, help_text in (
        ("case", "Fetch one exact appellate case with all returned components"),
        ("docket", "List past and upcoming events for one exact appellate case"),
        ("documents", "List source-linked public documents for one exact case"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument("case_number")
        if command != "case":
            _add_page_args(subparser)
        _add_transport_args(subparser)
        add_output_args(subparser)

    download = subparsers.add_parser(
        "download",
        help="Acquire one source-listed public PDF and emit an artifact receipt",
    )
    download.add_argument("case_number")
    download.add_argument("document_id")
    download.add_argument("--document-output", required=True)
    _add_transport_args(download)
    add_output_args(download)

    rss = subparsers.add_parser(
        "rss",
        help="Fetch the official per-case RSS docket feed",
    )
    rss.add_argument("case_number")
    _add_page_args(rss)
    _add_transport_args(rss)
    add_output_args(rss)

    routes = subparsers.add_parser(
        "routes",
        help="List distinct official acquisition and complementary routes",
    )
    add_output_args(routes)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded exact-case live source probe",
    )
    probe.add_argument("--case-number", default="2025AP000699")
    _add_transport_args(probe)
    add_output_args(probe)

    runtime = subparsers.add_parser(
        "runtime-check",
        help="Check the browser runtime without querying a case",
    )
    runtime.add_argument("--timeout", type=float, default=30.0)
    runtime.add_argument("--attempts", type=_positive_int, default=1)
    add_output_args(runtime)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Wisconsin WSCCA {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Wisconsin WSCCA {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
        ResultStatus.HUMAN_REQUIRED,
    } else 1


if __name__ == "__main__":
    sys.exit(main())
