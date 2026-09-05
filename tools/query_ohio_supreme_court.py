#!/usr/bin/env python3
"""Query the Supreme Court of Ohio public docket.

The official eCMS application exposes anonymous case search, exact case
details, rolling recent filings, and public filing PDFs.  Search results are
returned as one source response and paginated only in the browser.  This
adapter preserves that response, reports the source's observed boundary
explicitly, and applies a caller-provided ``--limit`` only after retrieval.

Examples:
    uv run python tools/query_ohio_supreme_court.py source --json
    uv run python tools/query_ohio_supreme_court.py search \
        --caption LaPilusa --output /tmp/ohio-supreme-search.json
    uv run python tools/query_ohio_supreme_court.py case 2017-1682 \
        --output /tmp/ohio-supreme-case.json
    uv run python tools/query_ohio_supreme_court.py document \
        2017-1682 835936.pdf /tmp/835936.pdf --json
    uv run python tools/query_ohio_supreme_court.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

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
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-oh-supreme-court-public-docket"
SOURCE_NAME = "Supreme Court of Ohio Public Docket"
COURT_ID = "oh-supreme-court"
COURT_NAME = "Supreme Court of Ohio"
STATE_CODE = "OH"
JURISDICTION_ID = "39"
OBSERVED_AT = "2026-07-30"

BASE_URL = "https://www.supremecourt.ohio.gov/clerk/ecms/"
AJAX_URL = urljoin(BASE_URL, "Ajax.ashx")
PDF_VIEWER_URL = "https://www.supremecourt.ohio.gov/pdf_viewer/pdf_viewer.aspx"
EXPECTED_HOST = "www.supremecourt.ohio.gov"
EXPECTED_AJAX_PATH = "/clerk/ecms/ajax.ashx"
PLATFORM_FAMILY = "ohio_supreme_court_ecms"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_RETRIES = 2
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

PROBE_CASE_NUMBER = "2017-1682"
PROBE_CASE_CAPTION = "Newsome"
PROBE_DOCUMENT_NAME = "835936.pdf"
OBSERVED_SEARCH_BOUNDARY = 1000
SOURCE_REFINEMENT_RESPONSE = "Too many results"
CURSOR_PREFIX = "ohio-supreme-court:v1:"

_CASE_NUMBER_RE = re.compile(
    r"^\s*(?P<year>\d{4})\s*[-–— ]\s*(?P<number>\d+)\s*$"
)
_DOCUMENT_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.pdf$", re.IGNORECASE)
_TOKEN_RE = re.compile(r'X-CSRF-TOKEN["\']?\s*:\s*["\']([^"\']+)["\']')

_CASE_INFO_FIELDS = {
    "ID",
    "CaseNumber",
    "Caption",
    "DateFiled",
    "Status",
    "CaseType",
}
_SEARCH_FIELDS = {
    "CaseNumber",
    "Caption",
    "DateFiled",
    "Status",
    "CaseType",
    "PriorJurisdiction",
}
_DOCKET_FIELDS = {
    "ID",
    "Description",
    "Code",
    "Type",
    "DateFiled",
    "DocumentName",
    "FilingParties",
}
_RECENT_FIELDS = {
    "FullCaseNumber",
    "CaseDescription",
    "DocketDescription",
    "DateFiled",
    "DocumentName",
    "FilingParties",
}

SOURCE_WARNINGS = (
    "The public docket covers Supreme Court cases filed on or after January "
    "1, 1985, and practice-of-law cases filed on or after January 1, 1989.",
    "A docket entry records filing activity; its linked PDF is a separate "
    "document representation, and a published opinion is a separate Reporter "
    "of Decisions product.",
    "The exact-case route can return the source text 'Too many results' for "
    "an unresolved number. The adapter reports that response as a refinement "
    "state rather than treating it as an authoritative empty result.",
)


class OhioSupremeCourtError(RuntimeError):
    """Base error carrying public-record result semantics."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "ohio_supreme_court_error",
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


class OhioSupremeCourtSelectionError(OhioSupremeCourtError):
    """The caller supplied an invalid selector or continuation."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status=ResultStatus.UNAVAILABLE,
            category="query",
            details=details,
        )


class OhioSupremeCourtTransportError(OhioSupremeCourtError):
    """The official source could not be reached after bounded retries."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="transport_error",
            status=ResultStatus.UNAVAILABLE,
            category="transport",
            retryable=True,
        )


class OhioSupremeCourtHTTPError(OhioSupremeCourtError):
    """The official source returned a non-success HTTP response."""

    def __init__(self, status_code: int, url: str) -> None:
        status = (
            ResultStatus.RESTRICTED
            if status_code in {401, 403}
            else ResultStatus.RATE_LIMITED
            if status_code == 429
            else ResultStatus.UNAVAILABLE
        )
        super().__init__(
            f"Ohio Supreme Court docket returned HTTP {status_code} for {url}",
            code=f"http_{status_code}",
            status=status,
            category="http",
            retryable=status_code == 429 or status_code >= 500,
            details={
                "status_code": status_code,
                "url": url,
                "access_characterization": "observed_response_not_policy",
            },
        )


class OhioSupremeCourtSourceChanged(OhioSupremeCourtError):
    """A verified route, host, media type, or response schema changed."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code="source_schema_or_provenance_changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


class OhioSupremeCourtRefinementRequired(OhioSupremeCourtError):
    """The source declined to resolve the supplied selection."""

    def __init__(
        self,
        *,
        operation: str,
        source_response: str,
    ) -> None:
        super().__init__(
            (
                "The Ohio Supreme Court docket did not resolve this "
                f"{operation} request and returned {source_response!r}"
            ),
            code="source_requires_refinement",
            status=ResultStatus.UNAVAILABLE,
            category="query",
            details={
                "operation": operation,
                "source_response": source_response,
                "source_response_semantics": (
                    "server_declined_or_could_not_resolve_selection"
                ),
                "suggested_action": (
                    "add or correct an exact case number, caption, party, "
                    "attorney, prior-case, or filing-date selector"
                ),
            },
        )


@dataclass(frozen=True)
class ParsedCaseNumber:
    raw: str
    year: str
    sequence: str
    normalized: str


@dataclass(frozen=True)
class DocumentArtifact:
    record: dict[str, Any]
    content: bytes


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:10]


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be zero or greater")
    return parsed


def _nonblank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise argparse.ArgumentTypeError("value must not be blank")
    return normalized


def parse_case_number(value: str) -> ParsedCaseNumber:
    match = _CASE_NUMBER_RE.fullmatch(value)
    if not match:
        raise OhioSupremeCourtSelectionError(
            "invalid_case_number",
            "case number must contain a four-digit year and numeric sequence",
        )
    year = match.group("year")
    sequence = match.group("number").zfill(4)
    return ParsedCaseNumber(
        raw=value,
        year=year,
        sequence=sequence,
        normalized=f"{year}-{sequence}",
    )


def validate_document_name(value: str) -> str:
    candidate = value.strip()
    if not _DOCUMENT_NAME_RE.fullmatch(candidate):
        raise OhioSupremeCourtSelectionError(
            "invalid_document_name",
            "document name must be a source PDF basename",
        )
    return candidate


def build_document_url(
    case_number: str,
    document_name: str,
    section: str,
) -> str:
    parsed = parse_case_number(case_number)
    document = validate_document_name(document_name)
    if section not in {"DocketItems", "DecisionItems"}:
        raise OhioSupremeCourtSelectionError(
            "invalid_document_section",
            "document section must be DocketItems or DecisionItems",
        )
    query = urlencode(
        {
            "pdf": document,
            "subdirectory": f"{parsed.normalized}\\{section}",
            "source": "DL_Clerk",
        }
    )
    return f"{PDF_VIEWER_URL}?{query}"


def _source_metadata() -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_ID,
        name=SOURCE_NAME,
        source_role=(
            "state_supreme_court_case_index_docket_parties_decisions_and_filings"
        ),
        base_url=BASE_URL,
        dataset_id="ohio-supreme-court-ecms",
        metadata={
            "publisher": "Supreme Court of Ohio, Office of the Clerk",
            "authentication": "none",
            "platform_family": PLATFORM_FAMILY,
            "native_case_identity": "CaseInfo.CaseNumber",
            "source_internal_case_locator": "CaseInfo.ID",
            "native_docket_identity": "DocketItems.ID",
            "native_document_identity": (
                "case_number + section + DocumentName"
            ),
            "source_response_pagination": "none_browser_paginates_locally",
            "observed_search_boundary": OBSERVED_SEARCH_BOUNDARY,
            "observed_at": OBSERVED_AT,
        },
    )


def _jurisdiction() -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=JURISDICTION_ID,
        name="Ohio",
        state_code=STATE_CODE,
        metadata={"court_id": COURT_ID, "court_name": COURT_NAME},
    )


def _query(
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=_source_metadata(),
        jurisdiction=_jurisdiction(),
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "source_response_pagination": (
                    "none_browser_paginates_locally"
                ),
                "default_result_cap": None,
                "caller_limit_applied_after_source_response": True,
            },
        ),
    )


def _source_record() -> dict[str, Any]:
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            "source-contract",
            "source_contract",
        ),
        "source_id": SOURCE_ID,
        "record_kind": "source_contract",
        "publisher": "Supreme Court of Ohio, Office of the Clerk",
        "observed_at": OBSERVED_AT,
        "access": {
            "authentication": "none",
            "bootstrap": "anonymous_session",
            "case_search": "anonymous_json",
            "exact_case": "anonymous_json",
            "recent_filings": "anonymous_json",
            "public_document": "anonymous_pdf",
            "resolved_host": EXPECTED_HOST,
        },
        "coverage": {
            "supreme_court_cases_from": "1985-01-01",
            "practice_of_law_cases_from": "1989-01-01",
            "court_scope": "Supreme Court of Ohio",
            "not_statewide_local_case_index": True,
        },
        "endpoints": {
            "application": BASE_URL,
            "structured_actions": {
                "search": "POST Ajax.ashx action=CaseSearch",
                "case": "POST Ajax.ashx action=GetCaseDetails",
                "recent": "POST Ajax.ashx action=GetRecentFilings",
                "case_types": "POST Ajax.ashx action=GetCaseTypes",
            },
            "document": (
                f"{PDF_VIEWER_URL}?pdf={{document_name}}&"
                "subdirectory={case_number}%5C{section}&source=DL_Clerk"
            ),
        },
        "identity": {
            "case": "CaseInfo.CaseNumber",
            "case_internal_locator": "CaseInfo.ID (not the case identity)",
            "docket_entry": "DocketItems.ID",
            "document": "case_number + section + DocumentName",
            "attorney_registration_number": "Parties.Attorneys.ARNumber",
            "search_result_ID": (
                "not an identity; observed as zero in search rows"
            ),
        },
        "source_response_behavior": {
            "native_pagination": "none",
            "browser_pagination": "local over returned array",
            "observed_search_boundary": OBSERVED_SEARCH_BOUNDARY,
            "boundary_handling": (
                "returned rows retained and result marked partial"
            ),
            "explicit_refinement_text": SOURCE_REFINEMENT_RESPONSE,
            "authoritative_empty_search": "empty JSON array",
            "exact_miss_note": (
                "observed unresolved exact numbers can return refinement text "
                "rather than an authoritative empty response"
            ),
        },
        "public_fields": [
            "case number and source-internal case locator",
            "caption, filed date, status, and case type",
            "prior jurisdiction, decision date, and lower-case numbers",
            "parties, roles, pro-se status, and counsel registration numbers",
            "docket entry ID, code, type, date, description, and filing parties",
            "decision description, release date, disposition, and document",
            "accepted case issues",
            "public filing and decision PDFs",
        ],
        "component_boundaries": [
            {
                "component": "Reporter of Decisions",
                "role": "published opinions and case announcements",
                "same_record_system": False,
            },
            {
                "component": "Clerk's Journal",
                "role": "orders and journal entries",
                "same_record_system": False,
            },
            {
                "component": "Attorney Directory",
                "role": "attorney registration and public business contact",
                "same_record_system": False,
            },
            {
                "component": "Oral Argument Calendar",
                "role": "argument schedule and video links",
                "same_record_system": False,
            },
        ],
    }


def _require_fields(
    value: Mapping[str, Any],
    required: set[str],
    *,
    label: str,
) -> None:
    missing = sorted(required.difference(value))
    if missing:
        raise OhioSupremeCourtSourceChanged(
            f"{label} is missing verified fields: {', '.join(missing)}",
            details={"missing_fields": missing},
        )


def _document_identity(
    case_number: str,
    section: str,
    document_name: str,
) -> str:
    return f"{case_number}:{section}:{document_name}"


def _document_record(
    *,
    case_number: str,
    section: str,
    document_name: str,
    source_url: str,
    linked_docket_entry_id: str | None = None,
) -> dict[str, Any]:
    native_id = _document_identity(case_number, section, document_name)
    record = {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
            "document",
            native_id=native_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "court_document",
        "court_id": COURT_ID,
        "case_number": case_number,
        "native_document_id": native_id,
        "document_name": document_name,
        "document_section": section,
        "source_url": source_url,
    }
    if linked_docket_entry_id is not None:
        record["linked_docket_entry_id"] = linked_docket_entry_id
    return record


def normalize_search_row(value: Mapping[str, Any]) -> dict[str, Any]:
    _require_fields(value, _SEARCH_FIELDS, label="case-search row")
    case_number = parse_case_number(str(value["CaseNumber"])).normalized
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "state_supreme_court_case_index",
        "court_id": COURT_ID,
        "court_name": COURT_NAME,
        "case_number": case_number,
        "caption": str(value["Caption"] or ""),
        "date_filed": _iso_date(value["DateFiled"]),
        "date_filed_raw": value["DateFiled"],
        "status": str(value["Status"] or ""),
        "case_type": str(value["CaseType"] or ""),
        "prior_jurisdiction": str(value["PriorJurisdiction"] or ""),
        "source_search_id": value.get("ID"),
        "source_url": f"{BASE_URL}#/caseinfo/{case_number.replace('-', '/')}",
    }


def _normalize_attorney(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": str(value.get("Name") or ""),
        "attorney_registration_number": str(value.get("ARNumber") or ""),
        "counsel_of_record": bool(value.get("CounselOfRecord")),
    }


def _normalize_party(value: Mapping[str, Any]) -> dict[str, Any]:
    attorneys = value.get("Attorneys") or []
    if not isinstance(attorneys, list) or not all(
        isinstance(item, Mapping) for item in attorneys
    ):
        raise OhioSupremeCourtSourceChanged(
            "case party Attorneys changed from a JSON object array"
        )
    return {
        "name": str(value.get("Name") or ""),
        "role": str(value.get("Type") or ""),
        "pro_se": bool(value.get("ProSe")),
        "attorneys": [_normalize_attorney(item) for item in attorneys],
    }


def _description_fields(value: Any) -> dict[str, Any]:
    html = str(value or "")
    soup = BeautifulSoup(html, "html.parser")
    links = [
        str(anchor.get("href"))
        for anchor in soup.find_all("a", href=True)
        if str(anchor.get("href")).strip()
    ]
    return {
        "description_text": _clean(soup.get_text(" ")),
        "description_html": html,
        "linked_urls": links,
    }


def normalize_case_payload(
    payload: Mapping[str, Any],
    *,
    requested_case_number: str,
) -> dict[str, Any]:
    required_top = {
        "CaseInfo",
        "CaseJurisdiction",
        "Parties",
        "DocketItems",
        "DecisionItems",
        "CaseIssues",
    }
    _require_fields(payload, required_top, label="exact-case response")
    case_info = payload["CaseInfo"]
    if not isinstance(case_info, Mapping):
        raise OhioSupremeCourtSourceChanged(
            "exact-case CaseInfo changed from a JSON object"
        )
    _require_fields(case_info, _CASE_INFO_FIELDS, label="CaseInfo")
    case_number = parse_case_number(str(case_info["CaseNumber"])).normalized
    requested = parse_case_number(requested_case_number).normalized
    if case_number != requested:
        raise OhioSupremeCourtSourceChanged(
            "exact-case response returned a different case number",
            details={"requested": requested, "returned": case_number},
        )

    parties = payload["Parties"]
    docket_items = payload["DocketItems"]
    decision_items = payload["DecisionItems"]
    issues = payload["CaseIssues"]
    if not isinstance(parties, list):
        raise OhioSupremeCourtSourceChanged(
            "exact-case Parties changed from a JSON array"
        )
    if not all(isinstance(value, Mapping) for value in parties):
        raise OhioSupremeCourtSourceChanged(
            "exact-case Parties contains a non-object row"
        )
    if not isinstance(docket_items, list):
        raise OhioSupremeCourtSourceChanged(
            "exact-case DocketItems changed from a JSON array"
        )
    if not isinstance(decision_items, list):
        raise OhioSupremeCourtSourceChanged(
            "exact-case DecisionItems changed from a JSON array"
        )
    if not isinstance(issues, list):
        raise OhioSupremeCourtSourceChanged(
            "exact-case CaseIssues changed from a JSON array"
        )
    if not all(isinstance(value, Mapping) for value in issues):
        raise OhioSupremeCourtSourceChanged(
            "exact-case CaseIssues contains a non-object row"
        )

    docket_records: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    seen_docket_ids: set[str] = set()
    seen_document_ids: set[str] = set()
    for value in docket_items:
        if not isinstance(value, Mapping):
            raise OhioSupremeCourtSourceChanged(
                "DocketItems contains a non-object row"
            )
        _require_fields(value, _DOCKET_FIELDS, label="docket item")
        docket_id = str(value["ID"])
        if not docket_id or docket_id in seen_docket_ids:
            raise OhioSupremeCourtSourceChanged(
                "DocketItems contains a missing or repeated native ID"
            )
        seen_docket_ids.add(docket_id)
        document_name = str(value.get("DocumentName") or "").strip()
        document_id = None
        document_url = None
        if document_name:
            document_name = validate_document_name(document_name)
            document_url = build_document_url(
                case_number,
                document_name,
                "DocketItems",
            )
            document_id = _document_identity(
                case_number,
                "DocketItems",
                document_name,
            )
            if document_id not in seen_document_ids:
                documents.append(
                    _document_record(
                        case_number=case_number,
                        section="DocketItems",
                        document_name=document_name,
                        source_url=document_url,
                        linked_docket_entry_id=docket_id,
                    )
                )
                seen_document_ids.add(document_id)
        docket_records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    case_number,
                    "docket_entry",
                    native_id=docket_id,
                ),
                "native_docket_entry_id": docket_id,
                "description": str(value["Description"] or ""),
                "docket_code": str(value["Code"] or ""),
                "docket_type": str(value["Type"] or ""),
                "date_filed": _iso_date(value["DateFiled"]),
                "date_filed_raw": value["DateFiled"],
                "filing_parties": value["FilingParties"],
                "document_name": document_name or None,
                "native_document_id": document_id,
                "document_url": document_url,
            }
        )

    decisions: list[dict[str, Any]] = []
    for index, value in enumerate(decision_items, start=1):
        if not isinstance(value, Mapping):
            raise OhioSupremeCourtSourceChanged(
                "DecisionItems contains a non-object row"
            )
        description = _description_fields(value.get("Description"))
        document_name = str(value.get("DocumentName") or "").strip()
        document_id = None
        document_url = None
        if document_name:
            document_name = validate_document_name(document_name)
            document_url = build_document_url(
                case_number,
                document_name,
                "DecisionItems",
            )
            document_id = _document_identity(
                case_number,
                "DecisionItems",
                document_name,
            )
            if document_id not in seen_document_ids:
                documents.append(
                    _document_record(
                        case_number=case_number,
                        section="DecisionItems",
                        document_name=document_name,
                        source_url=document_url,
                    )
                )
                seen_document_ids.add(document_id)
        decision_identity = document_id or hashlib.sha256(
            canonical_json(
                {
                    "case_number": case_number,
                    "description": description["description_text"],
                    "release_date": value.get("ReleaseDate"),
                    "occurrence": index,
                }
            ).encode("utf-8")
        ).hexdigest()
        decisions.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    case_number,
                    "decision",
                    native_id=decision_identity,
                ),
                **description,
                "release_date": _iso_date(value.get("ReleaseDate")),
                "release_date_raw": value.get("ReleaseDate"),
                "disposes_case": bool(value.get("DisposesCase")),
                "document_name": document_name or None,
                "native_document_id": document_id,
                "document_url": document_url,
            }
        )

    jurisdiction = payload["CaseJurisdiction"]
    if not isinstance(jurisdiction, Mapping):
        raise OhioSupremeCourtSourceChanged(
            "CaseJurisdiction changed from a JSON object"
        )
    prior_numbers = jurisdiction.get("PriorCaseNumbers") or []
    if not isinstance(prior_numbers, list):
        raise OhioSupremeCourtSourceChanged(
            "PriorCaseNumbers changed from a JSON array"
        )

    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "state_supreme_court_case",
        "court_id": COURT_ID,
        "court_name": COURT_NAME,
        "source_internal_case_locator": str(case_info["ID"]),
        "case_number": case_number,
        "caption": str(case_info["Caption"] or ""),
        "date_filed": _iso_date(case_info["DateFiled"]),
        "date_filed_raw": case_info["DateFiled"],
        "status": str(case_info["Status"] or ""),
        "case_type": str(case_info["CaseType"] or ""),
        "prior_jurisdiction": {
            "name": str(jurisdiction.get("Name") or ""),
            "county": str(jurisdiction.get("County") or ""),
            "prior_decision_date": _iso_date(
                jurisdiction.get("PriorDecisionDate")
            ),
            "prior_decision_date_raw": jurisdiction.get("PriorDecisionDate"),
            "prior_case_numbers": [
                dict(item) if isinstance(item, Mapping) else item
                for item in prior_numbers
            ],
        },
        "parties": [
            _normalize_party(value)
            for value in parties
        ],
        "docket_entries": docket_records,
        "decisions": decisions,
        "case_issues": [dict(item) for item in issues],
        "documents": documents,
        "retrieval": {
            "docket_entry_count": len(docket_records),
            "decision_count": len(decisions),
            "document_count": len(documents),
            "source_response_pagination": "none",
            "complete_exact_case_response": True,
        },
        "source_url": f"{BASE_URL}#/caseinfo/{case_number.replace('-', '/')}",
    }


def _recent_listing_identity(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "case_number": value.get("FullCaseNumber"),
                "date_filed": value.get("DateFiled"),
                "description": value.get("DocketDescription"),
                "document_name": value.get("DocumentName"),
                "filing_parties": value.get("FilingParties"),
            }
        ).encode("utf-8")
    ).hexdigest()


def normalize_recent_row(value: Mapping[str, Any]) -> dict[str, Any]:
    _require_fields(value, _RECENT_FIELDS, label="recent-filing row")
    case_number = parse_case_number(str(value["FullCaseNumber"])).normalized
    document_name = str(value.get("DocumentName") or "").strip()
    document_id = None
    document_url = None
    if document_name:
        document_name = validate_document_name(document_name)
        document_id = _document_identity(
            case_number,
            "DocketItems",
            document_name,
        )
        document_url = build_document_url(
            case_number,
            document_name,
            "DocketItems",
        )
    listing_id = _recent_listing_identity(value)
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
            "recent_filing_listing",
            native_id=listing_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "state_supreme_court_recent_filing",
        "court_id": COURT_ID,
        "case_number": case_number,
        "listing_identity": listing_id,
        "case_caption": str(value["CaseDescription"] or ""),
        "docket_description": str(value["DocketDescription"] or ""),
        "date_filed": _iso_date(value["DateFiled"]),
        "date_filed_raw": value["DateFiled"],
        "filing_parties": value["FilingParties"],
        "document_name": document_name or None,
        "native_document_id": document_id,
        "document_url": document_url,
        "docket_identity_note": (
            "Recent-filings rows do not publish DocketItems.ID; fetch the "
            "exact case to obtain the native docket-entry identity."
        ),
        "source_url": f"{BASE_URL}#/caseinfo/{case_number.replace('-', '/')}",
    }


class OhioSupremeCourtClient:
    """Requests-compatible client for the verified anonymous eCMS routes."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_budget: int | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if request_budget is not None and request_budget <= 0:
            raise ValueError("request_budget must be positive when supplied")
        self._owns_session = session is None
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_retries = max_retries
        self.request_budget = request_budget
        self._sleeper = sleeper
        self._clock = clock
        self._last_request_at = 0.0
        self._csrf_token: str | None = None
        self.request_count = 0

    def close(self) -> None:
        """Close a session created by this client."""

        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def __enter__(self) -> OhioSupremeCourtClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        for attempt in range(self.max_retries + 1):
            if (
                self.request_budget is not None
                and self.request_count >= self.request_budget
            ):
                raise OhioSupremeCourtSelectionError(
                    "request_budget_exhausted",
                    "Ohio Supreme Court request budget was exhausted",
                    details={
                        "request_budget": self.request_budget,
                        "requests_made": self.request_count,
                    },
                )
            elapsed = self._clock() - self._last_request_at
            if elapsed < self.minimum_interval:
                self._sleeper(self.minimum_interval - elapsed)
            try:
                self._last_request_at = self._clock()
                self.request_count += 1
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    **kwargs,
                )
            except requests.RequestException as error:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                raise OhioSupremeCourtTransportError(
                    f"Ohio Supreme Court docket request failed: {error}"
                ) from error

            final_url = str(getattr(response, "url", url))
            parsed = urlsplit(final_url)
            if (
                parsed.scheme.casefold() != "https"
                or (parsed.hostname or "").casefold() != EXPECTED_HOST
            ):
                raise OhioSupremeCourtSourceChanged(
                    "Ohio Supreme Court response resolved outside the "
                    "verified HTTPS host",
                    details={"final_url": final_url},
                )
            status_code = int(response.status_code)
            if (
                status_code == 429 or status_code >= 500
            ) and attempt < self.max_retries:
                self._sleeper(0.5 * (2**attempt))
                continue
            if status_code < 200 or status_code >= 300:
                raise OhioSupremeCourtHTTPError(status_code, final_url)
            return response
        raise OhioSupremeCourtTransportError(
            "Ohio Supreme Court docket request exhausted retries"
        )

    def bootstrap(self) -> None:
        if self._csrf_token:
            return
        landing = self._request(
            "GET",
            BASE_URL,
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        soup = BeautifulSoup(str(landing.text), "html.parser")
        script_src = None
        for script in soup.find_all("script", src=True):
            candidate = str(script.get("src"))
            if "site.min.js" in candidate:
                script_src = candidate
                break
        if not script_src:
            raise OhioSupremeCourtSourceChanged(
                "public docket landing page no longer identifies site.min.js"
            )
        script_url = urljoin(str(landing.url), script_src)
        script = self._request(
            "GET",
            script_url,
            headers={"Accept": "*/*", "Referer": BASE_URL},
        )
        match = _TOKEN_RE.search(str(script.text))
        if not match:
            raise OhioSupremeCourtSourceChanged(
                "public docket application bundle no longer exposes the "
                "verified request token contract"
            )
        self._csrf_token = match.group(1)

    def _post_json(
        self,
        action: str,
        parameters: Mapping[str, Any],
    ) -> Any:
        self.bootstrap()
        response = self._request(
            "POST",
            AJAX_URL,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": (
                    "application/x-www-form-urlencoded; charset=UTF-8"
                ),
                "X-CSRF-TOKEN": str(self._csrf_token),
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://www.supremecourt.ohio.gov",
                "Referer": BASE_URL,
            },
            data={"action": action, **dict(parameters)},
        )
        if urlsplit(str(response.url)).path.casefold() != EXPECTED_AJAX_PATH:
            raise OhioSupremeCourtSourceChanged(
                "structured docket response resolved outside Ajax.ashx",
                details={"final_url": str(response.url)},
            )
        content_type = str(response.headers.get("Content-Type") or "")
        if "json" not in content_type.casefold():
            raise OhioSupremeCourtSourceChanged(
                "structured docket route returned a non-JSON media type",
                details={"content_type": content_type},
            )
        try:
            return json.loads(str(response.text))
        except json.JSONDecodeError as error:
            raise OhioSupremeCourtSourceChanged(
                "structured docket route returned malformed JSON"
            ) from error

    @staticmethod
    def _refinement(operation: str, payload: Any) -> None:
        if payload == SOURCE_REFINEMENT_RESPONSE:
            raise OhioSupremeCourtRefinementRequired(
                operation=operation,
                source_response=payload,
            )

    def search(self, parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
        payload = self._post_json("CaseSearch", parameters)
        self._refinement("search", payload)
        if not isinstance(payload, list):
            raise OhioSupremeCourtSourceChanged(
                "case search no longer returns a JSON array or refinement text"
            )
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value in payload:
            if not isinstance(value, Mapping):
                raise OhioSupremeCourtSourceChanged(
                    "case search contains a non-object row"
                )
            record = normalize_search_row(value)
            case_number = str(record["case_number"])
            if case_number in seen:
                raise OhioSupremeCourtSourceChanged(
                    f"case search repeated case identity {case_number}"
                )
            seen.add(case_number)
            records.append(record)
        return records

    def case(self, case_number: str) -> dict[str, Any]:
        parsed = parse_case_number(case_number)
        payload = self._post_json(
            "GetCaseDetails",
            {
                "paramCaseYear": parsed.year,
                "paramCaseNumber": parsed.sequence,
            },
        )
        self._refinement("exact case", payload)
        if payload == "Sealed":
            raise OhioSupremeCourtError(
                "The source reports this case as sealed",
                code="sealed_case",
                status=ResultStatus.RESTRICTED,
                category="record_access",
                details={"case_number": parsed.normalized},
            )
        if not isinstance(payload, Mapping):
            raise OhioSupremeCourtSourceChanged(
                "exact case no longer returns an object, sealed state, or "
                "refinement response"
            )
        return normalize_case_payload(
            payload,
            requested_case_number=parsed.normalized,
        )

    def recent(self, days: int) -> list[dict[str, Any]]:
        payload = self._post_json(
            "GetRecentFilings",
            {"paramDaysPrior": days},
        )
        self._refinement("recent filings", payload)
        if not isinstance(payload, list):
            raise OhioSupremeCourtSourceChanged(
                "recent filings no longer returns a JSON array"
            )
        records: list[dict[str, Any]] = []
        for value in payload:
            if not isinstance(value, Mapping):
                raise OhioSupremeCourtSourceChanged(
                    "recent filings contains a non-object row"
                )
            records.append(normalize_recent_row(value))
        return records

    def document(
        self,
        case_number: str,
        document_name: str,
        section: str,
    ) -> DocumentArtifact:
        parsed = parse_case_number(case_number)
        document = validate_document_name(document_name)
        requested_url = build_document_url(
            parsed.normalized,
            document,
            section,
        )
        response = self._request(
            "GET",
            requested_url,
            headers={
                "Accept": "application/pdf,*/*;q=0.8",
                "Referer": (
                    f"{BASE_URL}#/caseinfo/"
                    f"{parsed.normalized.replace('-', '/')}"
                ),
            },
        )
        content_type = str(response.headers.get("Content-Type") or "")
        content = bytes(response.content)
        if "application/pdf" not in content_type.casefold():
            raise OhioSupremeCourtSourceChanged(
                "public filing route returned a non-PDF media type",
                details={
                    "content_type": content_type,
                    "final_url": str(response.url),
                },
            )
        if not content.startswith(b"%PDF-"):
            raise OhioSupremeCourtSourceChanged(
                "public filing route returned content without a PDF signature"
            )
        if not content:
            raise OhioSupremeCourtSourceChanged(
                "public filing route returned an empty artifact"
            )
        record = _document_record(
            case_number=parsed.normalized,
            section=section,
            document_name=document,
            source_url=str(response.url),
        )
        record.update(
            {
                "requested_url": requested_url,
                "final_url": str(response.url),
                "media_type": content_type.split(";", 1)[0].strip().casefold(),
                "byte_size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "signature": content[:8].decode("latin-1"),
            }
        )
        return DocumentArtifact(record=record, content=content)


def _search_parameters(args: argparse.Namespace) -> dict[str, Any]:
    parsed_case = (
        parse_case_number(args.case_number)
        if args.case_number
        else None
    )
    selectors = {
        "case_number": args.case_number,
        "caption": args.caption,
        "prior_case_number": args.prior_case_number,
        "party_first_name": args.party_first_name,
        "party_last_name": args.party_last_name,
        "party_entity": args.party_entity,
        "attorney_first_name": args.attorney_first_name,
        "attorney_last_name": args.attorney_last_name,
        "filed_from": args.filed_from,
        "filed_to": args.filed_to,
    }
    if not any(value not in {None, ""} for value in selectors.values()):
        raise OhioSupremeCourtSelectionError(
            "missing_search_selector",
            "search requires at least one case, caption, party, attorney, "
            "prior-case, or filed-date selector",
        )
    return {
        "action": "CaseSearch",
        "paramCaseYear": parsed_case.year if parsed_case else "",
        "paramCaseNumber": parsed_case.sequence if parsed_case else "",
        "paramCaseCaption": args.caption or "",
        "paramPriorCaseNumber": args.prior_case_number or "",
        "paramCaseType": "",
        "paramCaseFiledFrom": args.filed_from or "",
        "paramCaseFiledTo": args.filed_to or "",
        "paramPriorCaseJuris": "",
        "paramPartyFirstName": args.party_first_name or "",
        "paramPartyLastName": args.party_last_name or "",
        "paramPartyEntity": args.party_entity or "",
        "paramAttyFirstName": args.attorney_first_name or "",
        "paramAttyLastName": args.attorney_last_name or "",
    }


def _selection_fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _membership_fingerprint(
    records: Sequence[Mapping[str, Any]],
) -> str:
    identities = [
        str(
            record.get("case_number")
            if record.get("record_kind") == "state_supreme_court_case_index"
            else record.get("listing_identity")
        )
        for record in records
    ]
    return hashlib.sha256(
        canonical_json(identities).encode("utf-8")
    ).hexdigest()


def _cursor_encode(payload: Mapping[str, Any]) -> str:
    token = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _cursor_decode(value: str) -> Mapping[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise OhioSupremeCourtSelectionError(
            "invalid_cursor",
            "cursor is not an Ohio Supreme Court docket continuation",
        )
    token = value.removeprefix(CURSOR_PREFIX)
    try:
        decoded = base64.urlsafe_b64decode(
            token + "=" * (-len(token) % 4)
        )
        payload = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as error:
        raise OhioSupremeCourtSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(payload, Mapping):
        raise OhioSupremeCourtSelectionError(
            "invalid_cursor",
            "cursor payload changed type",
        )
    return payload


def _window_records(
    records: Sequence[Mapping[str, Any]],
    *,
    selection: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if cursor and limit is None:
        raise OhioSupremeCourtSelectionError(
            "cursor_requires_limit",
            "continuing a caller window requires --limit",
        )
    selection_hash = _selection_fingerprint(selection)
    membership_hash = _membership_fingerprint(records)
    offset = 0
    if cursor:
        payload = _cursor_decode(cursor)
        if payload.get("source_id") != SOURCE_ID:
            raise OhioSupremeCourtSelectionError(
                "cursor_source_mismatch",
                "cursor belongs to another source",
            )
        if payload.get("selection_fingerprint") != selection_hash:
            raise OhioSupremeCourtSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to another operation or selector set",
            )
        if (
            payload.get("membership_fingerprint") != membership_hash
            or payload.get("total") != len(records)
        ):
            raise OhioSupremeCourtSelectionError(
                "cursor_membership_changed",
                "ordered source-response membership changed",
            )
        try:
            offset = int(payload["offset"])
        except (KeyError, TypeError, ValueError) as error:
            raise OhioSupremeCourtSelectionError(
                "invalid_cursor",
                "cursor offset is invalid",
            ) from error
        if offset < 0 or offset > len(records):
            raise OhioSupremeCourtSelectionError(
                "invalid_cursor",
                "cursor offset is outside the source response",
            )

    end = len(records) if limit is None else min(offset + limit, len(records))
    selected = [dict(record) for record in records[offset:end]]
    next_cursor = None
    if end < len(records):
        next_cursor = _cursor_encode(
            {
                "source_id": SOURCE_ID,
                "selection_fingerprint": selection_hash,
                "membership_fingerprint": membership_hash,
                "offset": end,
                "total": len(records),
            }
        )
    return selected, next_cursor


def _boundary_error(
    *,
    operation: str,
    returned_count: int,
) -> PublicRecordsError:
    return PublicRecordsError(
        code="observed_source_result_boundary",
        message=(
            f"The {operation} response contains exactly "
            f"{OBSERVED_SEARCH_BOUNDARY} rows, the source's observed result "
            "boundary; additional matching rows may exist."
        ),
        category="source_response",
        retryable=False,
        details={
            "operation": operation,
            "returned_count": returned_count,
            "observed_boundary": OBSERVED_SEARCH_BOUNDARY,
            "source_response_preserved": True,
            "suggested_action": "add narrower source-native selectors",
        },
    )


def _failure(
    query: PublicRecordsQuery,
    error: OhioSupremeCourtError,
) -> PublicRecordsResult:
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


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: OhioSupremeCourtClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one standalone Supreme Court docket operation."""

    operation = args.command
    limit = getattr(args, "limit", None)
    cursor = getattr(args, "cursor", None)
    parameters: dict[str, Any] = {}
    search_parameters: dict[str, Any] | None = None
    try:
        if operation == "search":
            search_parameters = _search_parameters(args)
            parameters = {
                key: value
                for key, value in search_parameters.items()
                if key != "action"
            }
        elif operation == "case":
            parameters = {
                "case_number": parse_case_number(
                    args.case_number
                ).normalized
            }
        elif operation == "recent":
            parameters = {
                "days": args.days,
                "temporal_view": "rolling_recent_filings",
            }
        elif operation == "document":
            parameters = {
                "case_number": parse_case_number(
                    args.case_number
                ).normalized,
                "document_name": validate_document_name(
                    args.document_name
                ),
                "section": args.section,
                "destination": str(args.destination),
            }
        elif operation == "probe":
            parameters = {
                "sentinel_case_number": args.case_number,
                "sentinel_caption": PROBE_CASE_CAPTION,
                "routes": [
                    "bootstrap",
                    "case_search",
                    "exact_case",
                    "recent_filings",
                    "public_document",
                ],
            }
    except OhioSupremeCourtError as error:
        query = _query(
            operation,
            parameters={"invalid_selection": True},
            limit=limit,
            cursor=cursor,
        )
        return _failure(query, error)

    query = _query(
        operation,
        parameters=parameters,
        limit=limit,
        cursor=cursor,
    )
    source_client = client or OhioSupremeCourtClient(
        timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
        minimum_interval=float(
            getattr(args, "minimum_interval", DEFAULT_MINIMUM_INTERVAL)
        ),
        max_retries=int(
            getattr(args, "retry_attempts", DEFAULT_MAX_RETRIES)
        ),
    )

    try:
        if operation == "source":
            result = PublicRecordsResult.success(
                query,
                [_source_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif operation == "search":
            assert search_parameters is not None
            source_records = source_client.search(
                {
                    key: value
                    for key, value in search_parameters.items()
                    if key != "action"
                }
            )
            boundary = len(source_records) == OBSERVED_SEARCH_BOUNDARY
            window, next_cursor = _window_records(
                source_records,
                selection={
                    "operation": "search",
                    "parameters": parameters,
                },
                limit=limit,
                cursor=cursor,
            )
            for record in window:
                record["retrieval"] = {
                    "source_response_count": len(source_records),
                    "source_response_pagination": "none",
                    "browser_pagination": "local",
                    "observed_source_boundary": boundary,
                    "caller_window_applied": limit is not None,
                }
            if boundary:
                result = PublicRecordsResult.failure(
                    query,
                    ResultStatus.PARTIAL,
                    [
                        _boundary_error(
                            operation="case search",
                            returned_count=len(source_records),
                        )
                    ],
                    records=window,
                    next_cursor=next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
            else:
                result = PublicRecordsResult.success(
                    query,
                    window,
                    next_cursor=next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
        elif operation == "case":
            record = source_client.case(args.case_number)
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=SOURCE_WARNINGS,
            )
        elif operation == "recent":
            source_records = source_client.recent(args.days)
            boundary = len(source_records) == OBSERVED_SEARCH_BOUNDARY
            window, next_cursor = _window_records(
                source_records,
                selection={"operation": "recent", "days": args.days},
                limit=limit,
                cursor=cursor,
            )
            for record in window:
                record["retrieval"] = {
                    "source_response_count": len(source_records),
                    "source_response_pagination": "none",
                    "browser_pagination": "local",
                    "observed_source_boundary": boundary,
                    "caller_window_applied": limit is not None,
                }
            if boundary:
                result = PublicRecordsResult.failure(
                    query,
                    ResultStatus.PARTIAL,
                    [
                        _boundary_error(
                            operation="recent filings",
                            returned_count=len(source_records),
                        )
                    ],
                    records=window,
                    next_cursor=next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
            else:
                result = PublicRecordsResult.success(
                    query,
                    window,
                    next_cursor=next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
        elif operation == "document":
            destination = Path(args.destination)
            if destination.exists() and not args.overwrite:
                raise OhioSupremeCourtSelectionError(
                    "destination_exists",
                    "destination already exists; use --overwrite to replace it",
                    details={"destination": str(destination)},
                )
            artifact = source_client.document(
                args.case_number,
                args.document_name,
                args.section,
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(artifact.content)
            artifact.record["local_path"] = str(destination.resolve())
            result = PublicRecordsResult.success(
                query,
                [artifact.record],
                raw_artifact_refs=[str(destination.resolve())],
                warnings=SOURCE_WARNINGS,
            )
        else:
            parsed_probe = parse_case_number(args.case_number)
            search_records = source_client.search(
                {
                    "paramCaseYear": "",
                    "paramCaseNumber": "",
                    "paramCaseCaption": PROBE_CASE_CAPTION,
                    "paramPriorCaseNumber": "",
                    "paramCaseType": "",
                    "paramCaseFiledFrom": "",
                    "paramCaseFiledTo": "",
                    "paramPriorCaseJuris": "",
                    "paramPartyFirstName": "",
                    "paramPartyLastName": "",
                    "paramPartyEntity": "",
                    "paramAttyFirstName": "",
                    "paramAttyLastName": "",
                }
            )
            if not any(
                record["case_number"] == parsed_probe.normalized
                for record in search_records
            ):
                raise OhioSupremeCourtSourceChanged(
                    "probe case disappeared from the verified caption search"
                )
            case_record = source_client.case(parsed_probe.normalized)
            recent_records = source_client.recent(1)
            document_names = {
                document["document_name"]
                for document in case_record["documents"]
                if document["document_section"] == "DocketItems"
            }
            if PROBE_DOCUMENT_NAME not in document_names:
                raise OhioSupremeCourtSourceChanged(
                    "probe document disappeared from the historical case"
                )
            artifact = source_client.document(
                parsed_probe.normalized,
                PROBE_DOCUMENT_NAME,
                "DocketItems",
            )
            probe = _source_record()
            probe["record_kind"] = "source_probe"
            probe["probe"] = {
                "status": "available",
                "routes_exercised": [
                    "bootstrap",
                    "case_search",
                    "exact_case",
                    "recent_filings",
                    "public_document",
                ],
                "request_count": source_client.request_count,
                "sentinel_case_number": case_record["case_number"],
                "sentinel_source_internal_case_locator": case_record[
                    "source_internal_case_locator"
                ],
                "sentinel_docket_entry_count": len(
                    case_record["docket_entries"]
                ),
                "sentinel_document_name": PROBE_DOCUMENT_NAME,
                "sentinel_document_media_type": artifact.record["media_type"],
                "sentinel_document_signature": artifact.record["signature"],
                "sentinel_document_final_host": (
                    urlsplit(artifact.record["final_url"]).hostname
                ),
                "recent_one_day_record_count": len(recent_records),
                "caption_search_record_count": len(search_records),
            }
            result = PublicRecordsResult.success(
                query,
                [probe],
                warnings=SOURCE_WARNINGS,
            )
    except OhioSupremeCourtError as error:
        result = _failure(query, error)
    finally:
        if client is None:
            source_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        _log(query, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Ohio Supreme Court public docket {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Ohio Supreme Court public docket {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") in {
            "state_supreme_court_case",
            "state_supreme_court_case_index",
        }:
            print(
                f"- {record['case_number']} | "
                f"{_clean(record.get('caption'))} | {record.get('status')}"
            )
        elif record.get("record_kind") == (
            "state_supreme_court_recent_filing"
        ):
            print(
                f"- {record['case_number']} | {record['date_filed']} | "
                f"{record['docket_description']}"
            )
        elif record.get("record_kind") == "court_document":
            print(
                f"- {record['case_number']} | {record['document_name']} | "
                f"{record.get('byte_size')} bytes"
            )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_nonnegative_int,
        default=DEFAULT_MAX_RETRIES,
    )


def _add_window_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help=(
            "Return a caller-sized window after retrieving the source response"
        ),
    )
    parser.add_argument(
        "--cursor",
        help="Resume a prior caller-sized window over the same source response",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the Supreme Court of Ohio public docket"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show the verified routes, identities, fields, and boundaries",
    )
    add_output_args(source)

    search = subparsers.add_parser(
        "search",
        help="Search the Supreme Court case index using source-native fields",
    )
    search.add_argument("--case-number", type=_nonblank)
    search.add_argument("--caption", type=_nonblank)
    search.add_argument("--prior-case-number", type=_nonblank)
    search.add_argument("--party-first-name", type=_nonblank)
    search.add_argument("--party-last-name", type=_nonblank)
    search.add_argument("--party-entity", type=_nonblank)
    search.add_argument("--attorney-first-name", type=_nonblank)
    search.add_argument("--attorney-last-name", type=_nonblank)
    search.add_argument(
        "--filed-from",
        type=_nonblank,
        help="Source date selector, formatted MM-DD-YYYY",
    )
    search.add_argument(
        "--filed-to",
        type=_nonblank,
        help="Source date selector, formatted MM-DD-YYYY",
    )
    _add_window_args(search)
    add_output_args(search)

    case = subparsers.add_parser(
        "case",
        help="Fetch one exact Supreme Court case, docket, and document index",
    )
    case.add_argument("case_number", type=_nonblank)
    add_output_args(case)

    recent = subparsers.add_parser(
        "recent",
        help="Return the source's rolling recent-filings response",
    )
    recent.add_argument("--days", type=_positive_int, default=5)
    _add_window_args(recent)
    add_output_args(recent)

    document = subparsers.add_parser(
        "document",
        help="Download and verify one public docket or decision PDF",
    )
    document.add_argument("case_number", type=_nonblank)
    document.add_argument("document_name", type=_nonblank)
    document.add_argument("destination", type=Path)
    document.add_argument(
        "--section",
        choices=["DocketItems", "DecisionItems"],
        default="DocketItems",
    )
    document.add_argument("--overwrite", action="store_true")
    add_output_args(document)

    probe = subparsers.add_parser(
        "probe",
        help="Exercise search, exact case, recent filings, and a public PDF",
    )
    probe.add_argument(
        "--case-number",
        type=_nonblank,
        default=PROBE_CASE_NUMBER,
    )
    add_output_args(probe)

    for command in subparsers.choices.values():
        _add_transport_args(command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
