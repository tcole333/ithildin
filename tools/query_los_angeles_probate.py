#!/usr/bin/env python3
"""Query Los Angeles Superior Court's public probate services.

The court exposes three useful, distinct anonymous routes:

* Case Summary: exact case-number lookup with case metadata, parties, filed
  document index rows, proceedings, future hearings, and register actions.
* Probate Notes: time-windowed examiner/attorney notes keyed by case number.
* Case Calendar: a direct case-number route for upcoming hearings.

Document images and name-to-case discovery are separate court services. Their
official URLs and access characteristics are preserved in source metadata and
case records, but this adapter does not place document orders.

Examples:
    uv run python tools/query_los_angeles_probate.py case 17STPB02676 --json
    uv run python tools/query_los_angeles_probate.py notes 26STPB00601 \
        --view all --output notes.json
    uv run python tools/query_los_angeles_probate.py calendar 26STPB00601
    uv run python tools/query_los_angeles_probate.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
        acquisition_result_status,
    )
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
    from tools.public_records_http import (
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_court_ref
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
        acquisition_result_status,
    )
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
    from public_records_http import (
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-ca-los-angeles-superior-probate"
STATE_CODE = "CA"
COUNTY_GEOID = "06037"
COURT_ID = "ca-los-angeles-superior-court-probate"
COURT_NAME = (
    "Superior Court of California, County of Los Angeles, Probate Division"
)
BASE_URL = "https://www.lacourt.ca.gov"
PROBATE_LANDING_URL = f"{BASE_URL}/pages/lp/probate"
CASE_SEARCH_URL = f"{BASE_URL}/casesummary/v2web3/?casetype=probate"
CASE_RESULT_URL = f"{BASE_URL}/casesummary/v2web3/CaseSummary"
NOTES_SEARCH_URL = f"{BASE_URL}/ProbateNotes/v2pubweb3/"
NOTES_RESULTS_URL = f"{BASE_URL}/ProbateNotes/v2pubweb3/Results"
CALENDAR_URL_TEMPLATE = (
    f"{BASE_URL}/CivilCalendar/ui/CalendarCase.aspx?caseNumber={{case_number}}"
)
DOCUMENT_IMAGE_URL_TEMPLATE = (
    f"{BASE_URL}/paos/v2web3/DocumentImages/SearchCaseNumber"
    "?casenumber={case_number}"
)
NAME_INDEX_URL = f"{BASE_URL}/paos/v2web3/CivilIndex"
PROBE_CASE_NUMBER = "17STPB02676"
DEFAULT_TIMEOUT = 30.0

SOURCE_WARNINGS = (
    "The Case Summary page states that it is not the official court record.",
    "Filed-document metadata is public in Case Summary; image selection and "
    "delivery use the court's separate guest/account document service.",
    "Probate Notes are published for a source-defined window around a hearing "
    "and are not a complete historical docket.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Los Angeles Superior Court Probate Online Services",
    source_role=(
        "county_superior_probate_case_docket_document_index_notes_calendar"
    ),
    base_url=PROBATE_LANDING_URL,
    dataset_id="lasc-probate-online-services",
    metadata={
        "authority": "Superior Court of California, County of Los Angeles",
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_id": COURT_ID,
        "authentication": "none",
        "platform_family": "lasc_aspnet_public_online_services",
        "case_summary_url": CASE_SEARCH_URL,
        "probate_notes_url": NOTES_SEARCH_URL,
        "case_calendar_url_template": CALENDAR_URL_TEMPLATE,
        "document_image_url_template": DOCUMENT_IMAGE_URL_TEMPLATE,
        "name_index_url": NAME_INDEX_URL,
    },
)


class LAProbateQueryError(ValueError):
    """The source rejected a query or a source selector was not available."""

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


@dataclass(frozen=True)
class CaseSearchPage:
    request_verification_token: str
    courthouse_options: Mapping[str, str]
    schema_fingerprint: str


@dataclass(frozen=True)
class PartyRow:
    name: str
    role: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "role": self.role}


@dataclass(frozen=True)
class HearingRow:
    hearing_date: str
    hearing_time: str
    department: str
    location: str
    hearing_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "hearing_date": self.hearing_date,
            "hearing_time": self.hearing_time,
            "department": self.department,
            "location": self.location,
            "hearing_type": self.hearing_type,
        }


@dataclass(frozen=True)
class DocumentRow:
    filed_date: str
    description: str
    filer: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "filed_date": self.filed_date,
            "description": self.description,
            "filer": self.filer,
        }


@dataclass(frozen=True)
class ProceedingRow:
    proceeding_datetime: str
    department: str
    proceeding_type: str
    disposition: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "proceeding_datetime": self.proceeding_datetime,
            "department": self.department,
            "proceeding_type": self.proceeding_type,
            "disposition": self.disposition,
        }


@dataclass(frozen=True)
class RegisterActionRow:
    action_date: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "action_date": self.action_date,
            "description": self.description,
        }


@dataclass(frozen=True)
class CaseSummaryPage:
    case_number: str
    case_title: str
    filing_courthouse: str
    filing_date: str
    case_type: str
    status: str
    document_image_url: str
    future_hearings: tuple[HearingRow, ...]
    parties: tuple[PartyRow, ...]
    documents: tuple[DocumentRow, ...]
    past_proceedings: tuple[ProceedingRow, ...]
    register_actions: tuple[RegisterActionRow, ...]
    schema_fingerprint: str


@dataclass(frozen=True)
class CaseLookup:
    page: CaseSummaryPage | None
    no_match_message: str | None = None
    native_courthouse_value: str | None = None


@dataclass(frozen=True)
class NotesSearchPage:
    request_verification_token: str
    schema_fingerprint: str


@dataclass(frozen=True)
class ProbateNote:
    case_number: str
    view: str
    hearing_datetime: str
    department: str
    calendar_item: str | None
    caption: str | None
    hearing_type: str | None
    petitioners: str | None
    attorneys: str | None
    continuance_number: str | None
    continuance_from: str | None
    last_date_changed: str | None
    last_note_changed_by: str | None
    recommended_disposition: str | None
    related_items: str | None
    is_contested: str | None
    summary_text: str | None
    facts_text: str | None
    matters_to_clear: str | None
    relief_text: str | None
    findings_and_order_text: str | None
    probate_examiner_comments: str | None
    raw_text: str
    tables: tuple[tuple[tuple[str, ...], ...], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_number": self.case_number,
            "view": self.view,
            "hearing_datetime": self.hearing_datetime,
            "department": self.department,
            "calendar_item": self.calendar_item,
            "caption": self.caption,
            "hearing_type": self.hearing_type,
            "petitioners": self.petitioners,
            "attorneys": self.attorneys,
            "continuance_number": self.continuance_number,
            "continuance_from": self.continuance_from,
            "last_date_changed": self.last_date_changed,
            "last_note_changed_by": self.last_note_changed_by,
            "recommended_disposition": self.recommended_disposition,
            "related_items": self.related_items,
            "is_contested": self.is_contested,
            "summary_text": self.summary_text,
            "facts_text": self.facts_text,
            "matters_to_clear": self.matters_to_clear,
            "relief_text": self.relief_text,
            "findings_and_order_text": self.findings_and_order_text,
            "probate_examiner_comments": self.probate_examiner_comments,
            "raw_text": self.raw_text,
            "tables": [
                [list(row) for row in table]
                for table in self.tables
            ],
        }


@dataclass(frozen=True)
class ProbateNotesPage:
    case_number: str
    view: str
    request_verification_token: str
    notes: tuple[ProbateNote, ...]
    message: str | None
    schema_fingerprint: str


@dataclass(frozen=True)
class CalendarHearing:
    hearing_date: str
    hearing_time: str
    department: str
    location: str
    hearing_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "hearing_date": self.hearing_date,
            "hearing_time": self.hearing_time,
            "department": self.department,
            "location": self.location,
            "hearing_type": self.hearing_type,
        }


@dataclass(frozen=True)
class CalendarPage:
    case_number: str
    caption: str | None
    filing_date: str | None
    hearings: tuple[CalendarHearing, ...]
    message: str | None
    calendar_window_days: int | None
    business_window_days: int | None
    schema_fingerprint: str


@dataclass(frozen=True)
class ProbeSnapshot:
    case_search: CaseSearchPage
    case_summary: CaseSummaryPage
    notes_search: NotesSearchPage
    calendar: CalendarPage


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _clean_text(value)
    if normalized is None:
        raise ValueError(f"Los Angeles probate response lacks {field_name}")
    return normalized


def _clean_lines(value: Any) -> str | None:
    if value is None:
        return None
    lines = [
        normalized
        for line in str(value).replace("\x00", "").splitlines()
        if (normalized := _clean_text(line)) is not None
    ]
    return "\n".join(lines) or None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(str(html).replace("\x00", ""), "html.parser")


def _source_schema_error(
    message: str,
    *,
    url: str,
    details: Mapping[str, Any] | None = None,
) -> SourceSchemaError:
    return SourceSchemaError(message, url=url, details=details)


def _checked_response(response: Any, *, url: str) -> str:
    status_code = int(getattr(response, "status_code", 0))
    text = getattr(response, "text", "")
    text = text if isinstance(text, str) else str(text)
    if status_code == 429:
        raise RateLimitedHTTPError(status_code, url=url, response_text=text)
    if status_code in {401, 403}:
        raise RestrictedHTTPError(status_code, url=url, response_text=text)
    if status_code == 451:
        raise TermsBlockedHTTPError(status_code, url=url, response_text=text)
    if status_code in {404, 410}:
        raise SourceChangedHTTPError(status_code, url=url, response_text=text)
    if status_code < 200 or status_code >= 300:
        raise HTTPStatusError(status_code, url=url, response_text=text)

    content_type = ""
    headers = getattr(response, "headers", {})
    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if str(key).lower() == "content-type":
                content_type = str(value).lower()
                break
    if content_type and "html" not in content_type:
        raise _source_schema_error(
            "Los Angeles probate service returned a non-HTML response",
            url=url,
            details={"content_type": content_type},
        )
    return text


def _table_rows(table: Tag) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        rows.append(
            [
                _clean_text(cell.get_text(" ", strip=True)) or ""
                for cell in cells
            ]
        )
    return rows


def _fingerprint_rows(rows: Sequence[Mapping[str, Any]], empty: Mapping[str, Any]) -> str:
    return schema_fingerprint(inferred_schema(list(rows) or [dict(empty)]))


def parse_case_search_html(html: str) -> CaseSearchPage:
    """Parse the exact-case search form and its native courthouse options."""

    soup = _soup(html)
    form = soup.find("form", id="caseSummaryForm")
    if not isinstance(form, Tag):
        raise _source_schema_error(
            "Los Angeles probate case-search form is missing",
            url=CASE_SEARCH_URL,
        )
    if str(form.get("method") or "").casefold() != "post":
        raise _source_schema_error(
            "Los Angeles probate case-search method changed",
            url=CASE_SEARCH_URL,
        )
    required_fields = {"txtCaseNumber", "ddlCourthouse", "action"}
    observed_fields = {
        str(field.get("name"))
        for field in form.find_all(["input", "select"])
        if field.get("name")
    }
    missing_fields = sorted(required_fields - observed_fields)
    if missing_fields:
        raise _source_schema_error(
            "Los Angeles probate case-search fields changed",
            url=CASE_SEARCH_URL,
            details={"missing_fields": missing_fields},
        )
    token = form.find("input", attrs={"name": "__RequestVerificationToken"})
    token_value = _clean_text(token.get("value") if isinstance(token, Tag) else None)
    if token_value is None:
        raise _source_schema_error(
            "Los Angeles probate case-search token is missing",
            url=CASE_SEARCH_URL,
        )
    courthouse_options: dict[str, str] = {}
    select = form.find("select", attrs={"name": "ddlCourthouse"})
    if isinstance(select, Tag):
        for option in select.find_all("option"):
            value = _clean_text(option.get("value")) or ""
            label = _clean_text(option.get_text(" ", strip=True)) or ""
            courthouse_options[value] = label
    schema = {
        "form_id": "caseSummaryForm",
        "method": "post",
        "fields": sorted(observed_fields),
        "courthouse_option_codes": sorted(courthouse_options),
    }
    return CaseSearchPage(
        request_verification_token=token_value,
        courthouse_options=courthouse_options,
        schema_fingerprint=schema_fingerprint(schema),
    )


def _section_table(soup: BeautifulSoup, anchor_name: str) -> Tag:
    anchor = soup.find("a", attrs={"name": anchor_name})
    if not isinstance(anchor, Tag):
        raise _source_schema_error(
            f"Los Angeles probate case section {anchor_name!r} is missing",
            url=CASE_RESULT_URL,
        )
    table = anchor.find_next("table", class_="dataTable")
    if not isinstance(table, Tag):
        raise _source_schema_error(
            f"Los Angeles probate case section {anchor_name!r} lacks its table",
            url=CASE_RESULT_URL,
        )
    return table


def parse_case_lookup_html(
    html: str,
    *,
    expected_case_number: str | None = None,
) -> CaseLookup:
    """Parse a Case Summary result or its authoritative no-match message."""

    soup = _soup(html)
    messages = [
        text
        for node in soup.select(
            ".message, .validation-summary-errors, .field-validation-error"
        )
        if (text := _clean_text(node.get_text(" ", strip=True))) is not None
    ]
    no_match = next(
        (
            message
            for message in messages
            if re.search(r"\bno match found for case number\b", message, re.I)
        ),
        None,
    )
    if no_match is not None:
        return CaseLookup(page=None, no_match_message=no_match)

    try:
        case_rows = _table_rows(_section_table(soup, "CaseInformation"))
    except SourceSchemaError:
        if messages:
            raise LAProbateQueryError(
                "source_validation_error",
                "; ".join(messages),
                details={"messages": messages},
            )
        raise
    case_fields: dict[str, str] = {}
    for row in case_rows:
        if len(row) != 2:
            raise _source_schema_error(
                "Los Angeles probate Case Information row width changed",
                url=CASE_RESULT_URL,
                details={"row": row},
            )
        key = row[0].strip().rstrip(":").casefold()
        case_fields[key] = row[1]
    field_names = {
        "case information": "case number",
        "case title": "case title",
        "filing courthouse": "filing courthouse",
        "filing date": "filing date",
        "case type": "case type",
        "status": "status",
    }
    missing = sorted(key for key in field_names if not case_fields.get(key))
    if missing:
        raise _source_schema_error(
            "Los Angeles probate Case Information fields changed",
            url=CASE_RESULT_URL,
            details={"missing_fields": missing},
        )
    case_number = case_fields["case information"]
    if (
        expected_case_number is not None
        and case_number.casefold() != expected_case_number.strip().casefold()
    ):
        raise _source_schema_error(
            "Los Angeles probate result case number differs from the query",
            url=CASE_RESULT_URL,
            details={
                "expected": expected_case_number,
                "observed": case_number,
            },
        )

    image_link = soup.find(
        "a",
        href=lambda value: isinstance(value, str)
        and "/DocumentImages/SearchCaseNumber" in value,
    )
    if not isinstance(image_link, Tag):
        raise _source_schema_error(
            "Los Angeles probate document-image link is missing",
            url=CASE_RESULT_URL,
        )
    document_image_url = urljoin(CASE_RESULT_URL, str(image_link.get("href")))

    future_rows = _table_rows(_section_table(soup, "FutureHearings"))
    future_hearings: list[HearingRow] = []
    for index, row in enumerate(future_rows):
        if len(row) != 5:
            raise _source_schema_error(
                "Los Angeles probate Future Hearings row width changed",
                url=CASE_RESULT_URL,
                details={"row_index": index, "row": row},
            )
        future_hearings.append(HearingRow(*map(_required_text, row, (
            "future hearing date",
            "future hearing time",
            "future hearing department",
            "future hearing location",
            "future hearing type",
        ))))

    party_rows = _table_rows(_section_table(soup, "Parties"))
    parties: list[PartyRow] = []
    for index, row in enumerate(party_rows):
        if len(row) != 2:
            raise _source_schema_error(
                "Los Angeles probate Party Information row width changed",
                url=CASE_RESULT_URL,
                details={"row_index": index, "row": row},
            )
        parties.append(
            PartyRow(
                name=_required_text(row[0], "party name"),
                role=_required_text(row[1], "party role"),
            )
        )

    document_rows = _table_rows(_section_table(soup, "DocumentsFiled"))
    documents: list[DocumentRow] = []
    for index, row in enumerate(document_rows):
        if len(row) != 3:
            raise _source_schema_error(
                "Los Angeles probate Documents Filed row width changed",
                url=CASE_RESULT_URL,
                details={"row_index": index, "row": row},
            )
        documents.append(
            DocumentRow(
                filed_date=_required_text(row[0], "document filed date"),
                description=_required_text(row[1], "document description"),
                filer=_clean_text(row[2]),
            )
        )

    proceeding_rows = _table_rows(_section_table(soup, "PastProceedings"))
    proceedings: list[ProceedingRow] = []
    for index, row in enumerate(proceeding_rows):
        if len(row) != 4:
            raise _source_schema_error(
                "Los Angeles probate Proceedings Held row width changed",
                url=CASE_RESULT_URL,
                details={"row_index": index, "row": row},
            )
        proceedings.append(
            ProceedingRow(
                proceeding_datetime=_required_text(
                    row[0], "proceeding date and time"
                ),
                department=_required_text(row[1], "proceeding department"),
                proceeding_type=_required_text(row[2], "proceeding type"),
                disposition=_clean_text(row[3]),
            )
        )

    action_rows = _table_rows(_section_table(soup, "RegisterOfAction"))
    actions: list[RegisterActionRow] = []
    for index, row in enumerate(action_rows):
        if len(row) != 2:
            raise _source_schema_error(
                "Los Angeles probate Register Of Actions row width changed",
                url=CASE_RESULT_URL,
                details={"row_index": index, "row": row},
            )
        actions.append(
            RegisterActionRow(
                action_date=_required_text(row[0], "register action date"),
                description=_required_text(row[1], "register action description"),
            )
        )

    shape_rows = [
        {
            "case": {
                "case_number": case_number,
                "case_title": case_fields["case title"],
                "filing_courthouse": case_fields["filing courthouse"],
                "filing_date": case_fields["filing date"],
                "case_type": case_fields["case type"],
                "status": case_fields["status"],
            },
            "future_hearing": (
                future_hearings[0].to_dict() if future_hearings else None
            ),
            "party": parties[0].to_dict() if parties else None,
            "document": documents[0].to_dict() if documents else None,
            "past_proceeding": (
                proceedings[0].to_dict() if proceedings else None
            ),
            "register_action": actions[0].to_dict() if actions else None,
        }
    ]
    page = CaseSummaryPage(
        case_number=case_number,
        case_title=case_fields["case title"],
        filing_courthouse=case_fields["filing courthouse"],
        filing_date=case_fields["filing date"],
        case_type=case_fields["case type"],
        status=case_fields["status"],
        document_image_url=document_image_url,
        future_hearings=tuple(future_hearings),
        parties=tuple(parties),
        documents=tuple(documents),
        past_proceedings=tuple(proceedings),
        register_actions=tuple(actions),
        schema_fingerprint=schema_fingerprint(inferred_schema(shape_rows)),
    )
    return CaseLookup(page=page)


def parse_notes_search_html(html: str) -> NotesSearchPage:
    """Parse the public Probate Notes case-number form."""

    soup = _soup(html)
    form = soup.find("form", id="frmProbateNotes")
    if not isinstance(form, Tag):
        raise _source_schema_error(
            "Los Angeles Probate Notes search form is missing",
            url=NOTES_SEARCH_URL,
        )
    if str(form.get("method") or "").casefold() != "post":
        raise _source_schema_error(
            "Los Angeles Probate Notes search method changed",
            url=NOTES_SEARCH_URL,
        )
    case_input = form.find("input", attrs={"name": "CaseNumber"})
    token = form.find("input", attrs={"name": "__RequestVerificationToken"})
    token_value = _clean_text(token.get("value") if isinstance(token, Tag) else None)
    if not isinstance(case_input, Tag) or token_value is None:
        raise _source_schema_error(
            "Los Angeles Probate Notes search fields changed",
            url=NOTES_SEARCH_URL,
        )
    schema = {
        "form_id": "frmProbateNotes",
        "method": "post",
        "fields": ["CaseNumber", "__RequestVerificationToken"],
    }
    return NotesSearchPage(
        request_verification_token=token_value,
        schema_fingerprint=schema_fingerprint(schema),
    )


def _notes_table_value(rows: Sequence[Sequence[str]], label: str) -> str | None:
    label_key = label.casefold().rstrip(":")
    for row in rows:
        for cell in row:
            normalized = _clean_text(cell)
            if normalized is None:
                continue
            key, separator, value = normalized.partition(":")
            if separator and key.casefold().strip() == label_key:
                return _clean_text(value)
    return None


def _notes_section(text: str, heading: str) -> str | None:
    headings = (
        "SUMMARY",
        "FACTS",
        "MATTERS TO CLEAR",
        "RELIEF",
        "FINDINGS AND ORDER",
        "PE COMMENTS",
        "RECOMMENDED DISPOSITION",
        "RELATED ITEMS",
    )
    alternates = "|".join(
        re.escape(value) for value in headings if value != heading
    )
    match = re.search(
        rf"(?:^|\n){re.escape(heading)}\s*:\s*(.*?)"
        rf"(?=(?:\n(?:{alternates})\s*:)|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return _clean_lines(match.group(1)) if match else None


def _is_note_start(table: Tag) -> bool:
    text = _clean_text(table.get_text(" ", strip=True)) or ""
    return (
        text.casefold().startswith("department ")
        and "court convened at:" in text.casefold()
    )


def _parse_note_block(
    table_elements: Sequence[Tag],
    *,
    case_number: str,
    view: str,
    raw_text: str,
) -> ProbateNote:
    tables = [
        tuple(tuple(row) for row in _table_rows(element))
        for element in table_elements
    ]
    if not tables or not tables[0] or len(tables[0][0]) < 2:
        raise _source_schema_error(
            "Los Angeles Probate Notes hearing header changed",
            url=NOTES_RESULTS_URL,
        )
    header_text = " ".join(tables[0][0])
    department_match = re.search(
        r"\bDepartment\s+(?:Dept\.\s*)?(.+?)\s+Court Convened at:",
        header_text,
        flags=re.IGNORECASE,
    )
    hearing_match = re.search(
        r"\bCourt Convened at:\s*(.+)$",
        header_text,
        flags=re.IGNORECASE,
    )
    if department_match is None or hearing_match is None:
        raise _source_schema_error(
            "Los Angeles Probate Notes hearing fields changed",
            url=NOTES_RESULTS_URL,
            details={"header": header_text},
        )
    department = _required_text(department_match.group(1), "note department")
    hearing_datetime = _required_text(
        hearing_match.group(1), "note hearing date and time"
    )

    case_table: tuple[tuple[str, ...], ...] | None = None
    for table in tables:
        if table and table[0] and table[0][0].casefold() == case_number.casefold():
            case_table = table
            break
    if case_table is None:
        raise _source_schema_error(
            "Los Angeles Probate Notes case header changed",
            url=NOTES_RESULTS_URL,
            details={"case_number": case_number},
        )

    first_row = case_table[0]
    calendar_item = _clean_text(first_row[1]) if len(first_row) > 1 else None
    caption = _clean_text(first_row[2]) if len(first_row) > 2 else None
    hearing_type = None
    petitioners = None
    attorneys = None
    for row in case_table[1:]:
        text = _clean_text(" ".join(row))
        if text is None:
            continue
        lowered = text.casefold()
        if lowered.startswith("petitioner(s):"):
            petitioners = _clean_text(text.partition(":")[2])
        elif lowered.startswith("attorney(s):"):
            attorneys = _clean_text(text.partition(":")[2])
        elif hearing_type is None:
            hearing_type = text

    flattened_tables = [row for table in tables for row in table]
    normalized_raw_text = _clean_lines(raw_text)
    if normalized_raw_text is None:
        raise _source_schema_error(
            "Los Angeles Probate Notes block has no text",
            url=NOTES_RESULTS_URL,
        )
    return ProbateNote(
        case_number=case_number,
        view=view,
        hearing_datetime=hearing_datetime,
        department=department,
        calendar_item=calendar_item,
        caption=caption,
        hearing_type=hearing_type,
        petitioners=petitioners,
        attorneys=attorneys,
        continuance_number=_notes_table_value(
            flattened_tables, "Continuance Number"
        ),
        continuance_from=_notes_table_value(
            flattened_tables, "Continuance From"
        ),
        last_date_changed=_notes_table_value(
            flattened_tables, "Last Date Changed"
        ),
        last_note_changed_by=_notes_table_value(
            flattened_tables, "Last Note Changed By"
        ),
        recommended_disposition=_notes_table_value(
            flattened_tables, "Recommended Disposition"
        ),
        related_items=_notes_table_value(flattened_tables, "Related Items"),
        is_contested=_notes_table_value(flattened_tables, "Is Contested"),
        summary_text=_notes_section(normalized_raw_text, "SUMMARY"),
        facts_text=_notes_section(normalized_raw_text, "FACTS"),
        matters_to_clear=_notes_section(
            normalized_raw_text,
            "MATTERS TO CLEAR",
        ),
        relief_text=_notes_section(normalized_raw_text, "RELIEF"),
        findings_and_order_text=_notes_section(
            normalized_raw_text,
            "FINDINGS AND ORDER",
        ),
        probate_examiner_comments=_notes_section(
            normalized_raw_text,
            "PE COMMENTS",
        ),
        raw_text=normalized_raw_text,
        tables=tuple(tables),
    )


def parse_notes_results_html(
    html: str,
    *,
    expected_case_number: str | None = None,
) -> ProbateNotesPage:
    """Parse one future- or past-hearing Probate Notes result page."""

    soup = _soup(html)
    subheading = soup.find("div", class_="subheading")
    heading_text = _clean_text(
        subheading.get_text(" ", strip=True)
        if isinstance(subheading, Tag)
        else None
    )
    heading_match = re.fullmatch(
        r"(FUTURE|PAST)\s+HEARINGS\s+for\s+(.+)",
        heading_text or "",
        flags=re.IGNORECASE,
    )
    if heading_match is None:
        messages = [
            text
            for node in soup.select(
                ".message, .validation-summary-errors, .field-validation-error"
            )
            if (text := _clean_text(node.get_text(" ", strip=True))) is not None
        ]
        if messages:
            raise LAProbateQueryError(
                "source_validation_error",
                "; ".join(messages),
                details={"messages": messages},
            )
        raise _source_schema_error(
            "Los Angeles Probate Notes result heading changed",
            url=NOTES_RESULTS_URL,
        )
    view = heading_match.group(1).casefold()
    case_number = _required_text(heading_match.group(2), "note case number")
    if (
        expected_case_number is not None
        and case_number.casefold() != expected_case_number.strip().casefold()
    ):
        raise _source_schema_error(
            "Los Angeles Probate Notes result case differs from the query",
            url=NOTES_RESULTS_URL,
            details={
                "expected": expected_case_number,
                "observed": case_number,
            },
        )

    form = soup.find("form", id="frmProbateNotes")
    token = (
        form.find("input", attrs={"name": "__RequestVerificationToken"})
        if isinstance(form, Tag)
        else None
    )
    token_value = _clean_text(token.get("value") if isinstance(token, Tag) else None)
    if token_value is None:
        raise _source_schema_error(
            "Los Angeles Probate Notes result token is missing",
            url=NOTES_RESULTS_URL,
        )
    scrollable = soup.find("div", class_="scrollable")
    if not isinstance(scrollable, Tag):
        raise _source_schema_error(
            "Los Angeles Probate Notes result body changed",
            url=NOTES_RESULTS_URL,
        )

    note_tables = list(
        scrollable.find_all("table", class_="probateNotesTable")
    )
    start_indexes = [
        index
        for index, table in enumerate(note_tables)
        if _is_note_start(table)
    ]
    notes_list: list[ProbateNote] = []
    for group_index, start_index in enumerate(start_indexes):
        end_index = (
            start_indexes[group_index + 1]
            if group_index + 1 < len(start_indexes)
            else len(note_tables)
        )
        stop_element: Tag | None = (
            note_tables[end_index] if end_index < len(note_tables) else token
        )
        text_parts: list[str] = []
        for element in note_tables[start_index].next_elements:
            if element is stop_element:
                break
            if isinstance(element, NavigableString):
                text_parts.append(str(element))
        notes_list.append(
            _parse_note_block(
                note_tables[start_index:end_index],
                case_number=case_number,
                view=view,
                raw_text="\n".join(text_parts),
            )
        )
    notes = tuple(notes_list)
    message = None
    if not notes:
        message = _clean_text(scrollable.get_text(" ", strip=True))
    note_shape = [
        {
            "case_number": note.case_number,
            "view": note.view,
            "hearing_datetime": note.hearing_datetime,
            "department": note.department,
            "calendar_item": note.calendar_item,
            "caption": note.caption,
            "hearing_type": note.hearing_type,
            "petitioners": note.petitioners,
            "attorneys": note.attorneys,
            "last_date_changed": note.last_date_changed,
            "recommended_disposition": note.recommended_disposition,
            "is_contested": note.is_contested,
            "summary_text": note.summary_text,
            "facts_text": note.facts_text,
            "matters_to_clear": note.matters_to_clear,
            "relief_text": note.relief_text,
            "findings_and_order_text": note.findings_and_order_text,
            "probate_examiner_comments": note.probate_examiner_comments,
            "raw_text": note.raw_text,
        }
        for note in notes
    ]
    empty_shape = {
        "case_number": "",
        "view": view,
        "hearing_datetime": "",
        "department": "",
        "calendar_item": None,
        "caption": None,
        "hearing_type": None,
        "petitioners": None,
        "attorneys": None,
        "last_date_changed": None,
        "recommended_disposition": None,
        "is_contested": None,
        "summary_text": None,
        "facts_text": None,
        "matters_to_clear": None,
        "relief_text": None,
        "findings_and_order_text": None,
        "probate_examiner_comments": None,
        "raw_text": "",
    }
    return ProbateNotesPage(
        case_number=case_number,
        view=view,
        request_verification_token=token_value,
        notes=notes,
        message=message,
        schema_fingerprint=_fingerprint_rows(note_shape, empty_shape),
    )


def parse_calendar_html(
    html: str,
    *,
    expected_case_number: str | None = None,
) -> CalendarPage:
    """Parse the direct case-calendar route, including its empty window."""

    soup = _soup(html)
    table = soup.find(
        "table",
        id=lambda value: isinstance(value, str)
        and value.endswith("_tblResults"),
    )
    if not isinstance(table, Tag):
        raise _source_schema_error(
            "Los Angeles case-calendar result table is missing",
            url=CALENDAR_URL_TEMPLATE,
        )
    rows = table.find_all("tr", recursive=False)
    if not rows:
        raise _source_schema_error(
            "Los Angeles case-calendar result table is empty",
            url=CALENDAR_URL_TEMPLATE,
        )
    full_text = _clean_text(table.get_text(" ", strip=True)) or ""
    empty_match = re.fullmatch(
        r"There are no future hearings scheduled for Case Number (.+?) "
        r"in the next (\d+) days \((\d+) business days\)\.",
        full_text,
        flags=re.IGNORECASE,
    )
    if empty_match is not None:
        case_number = _required_text(
            empty_match.group(1), "calendar case number"
        )
        if (
            expected_case_number is not None
            and case_number.casefold() != expected_case_number.strip().casefold()
        ):
            raise _source_schema_error(
                "Los Angeles case-calendar empty result differs from the query",
                url=CALENDAR_URL_TEMPLATE,
            )
        empty_shape = {
            "case_number": case_number,
            "caption": None,
            "filing_date": None,
            "hearing": None,
            "calendar_window_days": int(empty_match.group(2)),
            "business_window_days": int(empty_match.group(3)),
        }
        return CalendarPage(
            case_number=case_number,
            caption=None,
            filing_date=None,
            hearings=(),
            message=full_text,
            calendar_window_days=int(empty_match.group(2)),
            business_window_days=int(empty_match.group(3)),
            schema_fingerprint=schema_fingerprint(empty_shape),
        )

    if len(rows) < 4:
        raise _source_schema_error(
            "Los Angeles case-calendar result rows changed",
            url=CALENDAR_URL_TEMPLATE,
            details={"row_count": len(rows)},
        )
    row_texts = [
        [
            text
            for value in row.stripped_strings
            if (text := _clean_text(value)) is not None
        ]
        for row in rows
    ]
    case_match = re.fullmatch(
        r"Case Number:\s*(.+)",
        " ".join(row_texts[0]),
        flags=re.IGNORECASE,
    )
    filing_match = re.fullmatch(
        r"Case filed on\s+(.+)",
        " ".join(row_texts[2]),
        flags=re.IGNORECASE,
    )
    if case_match is None or filing_match is None or not row_texts[1]:
        raise _source_schema_error(
            "Los Angeles case-calendar case header changed",
            url=CALENDAR_URL_TEMPLATE,
            details={"rows": row_texts[:3]},
        )
    case_number = _required_text(case_match.group(1), "calendar case number")
    if (
        expected_case_number is not None
        and case_number.casefold() != expected_case_number.strip().casefold()
    ):
        raise _source_schema_error(
            "Los Angeles case-calendar result case differs from the query",
            url=CALENDAR_URL_TEMPLATE,
        )
    caption = _required_text(" ".join(row_texts[1]), "calendar caption")
    filing_date = _required_text(
        filing_match.group(1), "calendar filing date"
    )

    hearings: list[CalendarHearing] = []
    for index, values in enumerate(row_texts[3:]):
        if len(values) < 3:
            raise _source_schema_error(
                "Los Angeles case-calendar hearing row changed",
                url=CALENDAR_URL_TEMPLATE,
                details={"row_index": index, "values": values},
            )
        hearing_date = values[0]
        details = values[1]
        hearing_type = _required_text(
            " ".join(values[2:]), "calendar hearing type"
        )
        details_match = re.fullmatch(
            r"at\s+(.+?)\s+in\s+(.+?)\s+at\s+(.+)",
            details,
            flags=re.IGNORECASE,
        )
        if details_match is None:
            raise _source_schema_error(
                "Los Angeles case-calendar hearing details changed",
                url=CALENDAR_URL_TEMPLATE,
                details={"row_index": index, "details": details},
            )
        hearings.append(
            CalendarHearing(
                hearing_date=_required_text(
                    hearing_date, "calendar hearing date"
                ),
                hearing_time=_required_text(
                    details_match.group(1), "calendar hearing time"
                ),
                department=_required_text(
                    details_match.group(2), "calendar department"
                ),
                location=_required_text(
                    details_match.group(3), "calendar location"
                ),
                hearing_type=hearing_type,
            )
        )
    shape = {
        "case_number": case_number,
        "caption": caption,
        "filing_date": filing_date,
        "hearing": hearings[0].to_dict(),
        "calendar_window_days": None,
        "business_window_days": None,
    }
    return CalendarPage(
        case_number=case_number,
        caption=caption,
        filing_date=filing_date,
        hearings=tuple(hearings),
        message=None,
        calendar_window_days=None,
        business_window_days=None,
        schema_fingerprint=schema_fingerprint(shape),
    )


def _resolve_courthouse_value(
    requested: str | None,
    offered: Mapping[str, str],
) -> str:
    """Resolve a short courthouse code to the exact source option value."""

    selector = _clean_text(requested) or ""
    if not selector:
        return ""
    if selector in offered:
        return selector

    casefolded_matches = [
        native_value
        for native_value in offered
        if native_value.casefold() == selector.casefold()
    ]
    if len(casefolded_matches) == 1:
        return casefolded_matches[0]

    code_matches = [
        native_value
        for native_value in offered
        if native_value.partition(";")[0].casefold() == selector.casefold()
    ]
    if len(code_matches) == 1:
        return code_matches[0]

    raise LAProbateQueryError(
        "unknown_courthouse",
        f"courthouse selector {selector!r} is not uniquely offered by the source",
        details={"available_courthouses": dict(offered)},
    )


class LosAngelesProbateClient:
    """Same-session client for the court's anonymous probate services."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self._owns_session = session is None
        self.headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Ithildin public-record source adapter",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _get(self, url: str) -> str:
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise TransportError(
                "Los Angeles probate GET failed",
                url=url,
                details={"error": str(error)},
            ) from error
        return _checked_response(response, url=url)

    def _post(self, url: str, data: Mapping[str, str], *, referer: str) -> str:
        try:
            response = self.session.post(
                url,
                data=dict(data),
                headers={**self.headers, "Referer": referer},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise TransportError(
                "Los Angeles probate POST failed",
                url=url,
                details={"error": str(error)},
            ) from error
        return _checked_response(response, url=url)

    def bootstrap_case(self) -> CaseSearchPage:
        return parse_case_search_html(self._get(CASE_SEARCH_URL))

    def case(
        self,
        case_number: str,
        *,
        courthouse: str | None = None,
    ) -> CaseLookup:
        normalized_case = _required_text(case_number, "case number")
        bootstrap = self.bootstrap_case()
        courthouse_value = _resolve_courthouse_value(
            courthouse,
            bootstrap.courthouse_options,
        )
        html = self._post(
            CASE_SEARCH_URL,
            {
                "txtCaseNumber": normalized_case,
                "ddlCourthouse": courthouse_value,
                "action": "Search",
                "__RequestVerificationToken": (
                    bootstrap.request_verification_token
                ),
            },
            referer=CASE_SEARCH_URL,
        )
        lookup = parse_case_lookup_html(
            html,
            expected_case_number=normalized_case,
        )
        return CaseLookup(
            page=lookup.page,
            no_match_message=lookup.no_match_message,
            native_courthouse_value=courthouse_value,
        )

    def bootstrap_notes(self) -> NotesSearchPage:
        return parse_notes_search_html(self._get(NOTES_SEARCH_URL))

    def notes(
        self,
        case_number: str,
        *,
        view: str = "future",
    ) -> tuple[ProbateNotesPage, ...]:
        normalized_case = _required_text(case_number, "case number")
        if view not in {"future", "past", "all"}:
            raise LAProbateQueryError(
                "invalid_notes_view",
                "notes view must be future, past, or all",
            )
        bootstrap = self.bootstrap_notes()
        future_html = self._post(
            NOTES_SEARCH_URL,
            {
                "CaseNumber": normalized_case,
                "__RequestVerificationToken": (
                    bootstrap.request_verification_token
                ),
            },
            referer=NOTES_SEARCH_URL,
        )
        future = parse_notes_results_html(
            future_html,
            expected_case_number=normalized_case,
        )
        if view == "future":
            return (future,)
        past_html = self._post(
            NOTES_RESULTS_URL,
            {
                "FormAction": f"{normalized_case};past",
                "__RequestVerificationToken": (
                    future.request_verification_token
                ),
            },
            referer=NOTES_RESULTS_URL,
        )
        past = parse_notes_results_html(
            past_html,
            expected_case_number=normalized_case,
        )
        return (past,) if view == "past" else (future, past)

    def calendar(self, case_number: str) -> CalendarPage:
        normalized_case = _required_text(case_number, "case number")
        url = CALENDAR_URL_TEMPLATE.format(
            case_number=quote(normalized_case, safe="")
        )
        return parse_calendar_html(
            self._get(url),
            expected_case_number=normalized_case,
        )

    def probe(self) -> ProbeSnapshot:
        case_search = self.bootstrap_case()
        case_lookup = self.case(PROBE_CASE_NUMBER)
        if case_lookup.page is None:
            raise _source_schema_error(
                "Los Angeles probate probe case stopped resolving",
                url=CASE_SEARCH_URL,
            )
        return ProbeSnapshot(
            case_search=case_search,
            case_summary=case_lookup.page,
            notes_search=self.bootstrap_notes(),
            calendar=self.calendar(PROBE_CASE_NUMBER),
        )


def _source_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise ValueError(
            f"Los Angeles probate source date is unparseable: {value!r}"
        ) from error


def _source_datetime(value: str) -> tuple[str, str]:
    for pattern in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.date().isoformat(), parsed.time().isoformat()
        except ValueError:
            continue
    raise ValueError(
        f"Los Angeles probate source date/time is unparseable: {value!r}"
    )


def _identity_text(value: str | None) -> str:
    return (_clean_text(value) or "").casefold()


def _native_id(prefix: str, basis: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        canonical_json(dict(basis)).encode("utf-8")
    ).hexdigest()
    return f"{prefix}:{digest}"


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": "los-angeles-superior-probate",
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": "superior",
        "official_url": PROBATE_LANDING_URL,
    }


def _base_case_record(
    case_number: str,
    *,
    caption: str | None,
    filing_date: str | None,
    case_type: str | None,
    status: str | None,
    source_url: str,
) -> dict[str, Any]:
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": _court_payload(),
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": None,
        "caption": caption,
        "case_type": case_type,
        "filing_date": filing_date,
        "status": status,
        "native_status": status,
        "access_state": "public",
        "certified_record": False,
        "source_url": source_url,
        "parties": [],
        "docket_entries": [],
        "documents": [],
    }


def _occurrence_numbers(
    values: Iterable[Any],
    key,
) -> Iterable[tuple[Any, int]]:
    counts: defaultdict[str, int] = defaultdict(int)
    for value in values:
        identity_key = canonical_json(key(value))
        ordinal = counts[identity_key]
        counts[identity_key] += 1
        yield value, ordinal


def _future_hearing_entry(
    case_number: str,
    row: HearingRow,
    ordinal: int,
) -> dict[str, Any]:
    event_date = _source_date(row.hearing_date)
    basis = {
        "case_number": case_number.upper(),
        "section": "future_hearings",
        "event_date": event_date,
        "source_time": _identity_text(row.hearing_time),
        "department": _identity_text(row.department),
        "location": _identity_text(row.location),
        "hearing_type": _identity_text(row.hearing_type),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_entry_id": _native_id("future-hearing", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "event_type": "future_hearing",
        "event_code": None,
        "raw_text": row.hearing_type,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": None,
        "source_event_time_raw": row.hearing_time,
        "department": row.department,
        "location": row.location,
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def _past_proceeding_entry(
    case_number: str,
    row: ProceedingRow,
    ordinal: int,
) -> dict[str, Any]:
    event_date, event_time = _source_datetime(row.proceeding_datetime)
    basis = {
        "case_number": case_number.upper(),
        "section": "past_proceedings",
        "event_date": event_date,
        "event_time": event_time,
        "department": _identity_text(row.department),
        "proceeding_type": _identity_text(row.proceeding_type),
        "disposition": _identity_text(row.disposition),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_entry_id": _native_id("past-proceeding", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "event_type": "past_proceeding",
        "event_code": None,
        "raw_text": row.proceeding_type,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": event_time,
        "department": row.department,
        "disposition": row.disposition,
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def _register_action_entry(
    case_number: str,
    row: RegisterActionRow,
    ordinal: int,
) -> dict[str, Any]:
    event_date = _source_date(row.action_date)
    basis = {
        "case_number": case_number.upper(),
        "section": "register_of_actions",
        "event_date": event_date,
        "description": _identity_text(row.description),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_entry_id": _native_id("register-action", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "event_type": "register_of_actions",
        "event_code": None,
        "raw_text": row.description,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "document_available": None,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def _document_payload(
    case_number: str,
    image_url: str,
    row: DocumentRow,
    ordinal: int,
) -> dict[str, Any]:
    filed_date = _source_date(row.filed_date)
    basis = {
        "case_number": case_number.upper(),
        "section": "documents_filed",
        "filed_date": filed_date,
        "description": _identity_text(row.description),
        "filer": _identity_text(row.filer),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_document_id": _native_id("document-index-row", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "document_type": row.description,
        "filed_date": filed_date,
        "source_url": image_url,
        "sha256": None,
        "mime_type": None,
        "page_count": None,
        "storage_path": None,
        "ocr_status": "not_acquired",
        "certification_status": "uncertified",
        "access_state": "public",
        "native_access_state": "public_index_separate_paid_email_delivery",
        "acquired_at": None,
        "filer_raw": row.filer,
        "raw": row.to_dict(),
    }


def _slice_values(
    values: Sequence[Any],
    *,
    limit: int | None,
    offset: int,
) -> tuple[list[Any], str | None]:
    selected = list(values[offset:] if limit is None else values[offset : offset + limit])
    next_cursor = None
    if limit is not None and offset + limit < len(values):
        next_cursor = f"la-probate:offset:{offset + limit}"
    return selected, next_cursor


def normalize_case(
    page: CaseSummaryPage,
    *,
    entry_limit: int | None = None,
    entry_offset: int = 0,
) -> tuple[dict[str, Any], str | None]:
    """Normalize a Case Summary page into one ingestible court case."""

    entries: list[dict[str, Any]] = []

    def future_key(row: HearingRow) -> dict[str, str]:
        return {
            "date": row.hearing_date,
            "time": row.hearing_time,
            "department": row.department,
            "location": row.location,
            "type": row.hearing_type,
        }

    for row, ordinal in _occurrence_numbers(page.future_hearings, future_key):
        entries.append(_future_hearing_entry(page.case_number, row, ordinal))

    def proceeding_key(row: ProceedingRow) -> dict[str, str | None]:
        return row.to_dict()

    for row, ordinal in _occurrence_numbers(
        page.past_proceedings,
        proceeding_key,
    ):
        entries.append(_past_proceeding_entry(page.case_number, row, ordinal))

    def action_key(row: RegisterActionRow) -> dict[str, str]:
        return row.to_dict()

    for row, ordinal in _occurrence_numbers(page.register_actions, action_key):
        entries.append(_register_action_entry(page.case_number, row, ordinal))
    selected_entries, next_cursor = _slice_values(
        entries,
        limit=entry_limit,
        offset=entry_offset,
    )

    parties = [
        {
            "sequence_no": index,
            "raw_name": party.name,
            "role": party.role,
            "access_state": "public",
            "raw": party.to_dict(),
        }
        for index, party in enumerate(page.parties, start=1)
    ]
    documents = [
        _document_payload(page.case_number, page.document_image_url, row, ordinal)
        for row, ordinal in _occurrence_numbers(
            page.documents,
            lambda value: value.to_dict(),
        )
    ]
    record = _base_case_record(
        page.case_number,
        caption=page.case_title,
        filing_date=_source_date(page.filing_date),
        case_type=page.case_type,
        status=page.status,
        source_url=CASE_SEARCH_URL,
    )
    record.update(
        {
            "filing_courthouse": page.filing_courthouse,
            "parties": parties,
            "docket_entries": selected_entries,
            "documents": documents,
            "document_image_url": page.document_image_url,
            "document_access": {
                "service_url": page.document_image_url,
                "search_without_account": True,
                "delivery": "email_after_purchase",
                "probate_preview_available": False,
            },
            "source_scope": {
                "record_type": "probate_case_summary",
                "query_key": "exact_case_number",
                "fields": [
                    "case_metadata",
                    "parties_and_roles",
                    "future_hearings",
                    "filed_document_index",
                    "past_proceedings",
                    "register_of_actions",
                ],
                "name_discovery_service_url": NAME_INDEX_URL,
                "document_image_service_url": page.document_image_url,
            },
            "search_metadata": {
                "source_counts": {
                    "future_hearings": len(page.future_hearings),
                    "parties": len(page.parties),
                    "documents": len(page.documents),
                    "past_proceedings": len(page.past_proceedings),
                    "register_actions": len(page.register_actions),
                    "docket_entries_combined": len(entries),
                },
                "returned_docket_entries": len(selected_entries),
                "docket_entry_offset": entry_offset,
                "docket_entry_limit": entry_limit,
            },
            "schema_fingerprint": page.schema_fingerprint,
            "raw": {
                "case_information": {
                    "case_number": page.case_number,
                    "case_title": page.case_title,
                    "filing_courthouse": page.filing_courthouse,
                    "filing_date": page.filing_date,
                    "case_type": page.case_type,
                    "status": page.status,
                },
                "returned_docket_entries": [
                    entry["raw"] for entry in selected_entries
                ],
                "parties": [party.to_dict() for party in page.parties],
                "documents": [row.to_dict() for row in page.documents],
            },
        }
    )
    return record, next_cursor


def _note_entry(
    note: ProbateNote,
    ordinal: int,
) -> dict[str, Any]:
    event_date, event_time = _source_datetime(note.hearing_datetime)
    basis = {
        "case_number": note.case_number.upper(),
        "view": note.view,
        "event_date": event_date,
        "event_time": event_time,
        "department": _identity_text(note.department),
        "calendar_item": _identity_text(note.calendar_item),
        "hearing_type": _identity_text(note.hearing_type),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_entry_id": _native_id("probate-note", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "event_type": "probate_note",
        "event_code": "probate_note",
        "raw_text": note.raw_text,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": event_time,
        "department": note.department,
        "disposition": note.recommended_disposition,
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "raw": note.to_dict(),
    }


def normalize_notes(
    pages: Sequence[ProbateNotesPage],
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[dict[str, Any] | None, str | None]:
    """Normalize future/past notes into one case-shaped supplement."""

    notes = [note for page in pages for note in page.notes]
    if not notes:
        return None, None
    case_numbers = {note.case_number.casefold(): note.case_number for note in notes}
    if len(case_numbers) != 1:
        raise ValueError("Los Angeles Probate Notes pages contain multiple cases")
    case_number = next(iter(case_numbers.values()))
    keyed_notes = list(
        _occurrence_numbers(
            notes,
            lambda note: {
                "case_number": note.case_number,
                "view": note.view,
                "hearing_datetime": note.hearing_datetime,
                "department": note.department,
                "calendar_item": note.calendar_item,
                "hearing_type": note.hearing_type,
            },
        )
    )
    entries = [_note_entry(note, ordinal) for note, ordinal in keyed_notes]
    selected_entries, next_cursor = _slice_values(
        entries,
        limit=limit,
        offset=offset,
    )
    if not selected_entries:
        return None, None
    selected_ids = {entry["native_entry_id"] for entry in selected_entries}
    selected_notes = [
        note.to_dict()
        for (note, ordinal), entry in zip(keyed_notes, entries, strict=True)
        if entry["native_entry_id"] in selected_ids
    ]
    captions = [
        note.caption
        for note in notes
        if _clean_text(note.caption) is not None
    ]
    record = _base_case_record(
        case_number,
        caption=captions[0] if captions else None,
        filing_date=None,
        case_type=None,
        status=None,
        source_url=NOTES_SEARCH_URL,
    )
    record.update(
        {
            "docket_entries": selected_entries,
            "probate_notes": selected_notes,
            "source_scope": {
                "record_type": "probate_examiner_attorney_notes",
                "query_key": "exact_case_number",
                "views": [page.view for page in pages],
                "source_window": (
                    "typically posted about two weeks before a hearing "
                    "through 60 days after it"
                ),
            },
            "search_metadata": {
                "source_note_count": len(notes),
                "returned_note_count": len(selected_entries),
                "note_offset": offset,
                "note_limit": limit,
                "empty_view_messages": {
                    page.view: page.message
                    for page in pages
                    if page.message
                },
            },
            "schema_fingerprint": schema_fingerprint(
                [page.schema_fingerprint for page in pages]
            ),
            "raw": {
                "views": [page.view for page in pages],
                "notes": selected_notes,
            },
        }
    )
    return record, next_cursor


def _calendar_entry(
    case_number: str,
    row: CalendarHearing,
    ordinal: int,
) -> dict[str, Any]:
    event_date = _source_date(row.hearing_date)
    try:
        event_time = datetime.strptime(
            row.hearing_time.upper(), "%I:%M %p"
        ).time().isoformat()
    except ValueError as error:
        raise ValueError(
            "Los Angeles case-calendar hearing time is unparseable: "
            f"{row.hearing_time!r}"
        ) from error
    basis = {
        "case_number": case_number.upper(),
        "section": "case_calendar",
        "event_date": event_date,
        "event_time": event_time,
        "department": _identity_text(row.department),
        "location": _identity_text(row.location),
        "hearing_type": _identity_text(row.hearing_type),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_entry_id": _native_id("case-calendar-hearing", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "event_type": "future_hearing",
        "event_code": None,
        "raw_text": row.hearing_type,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": event_time,
        "department": row.department,
        "location": row.location,
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def normalize_calendar(
    page: CalendarPage,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[dict[str, Any] | None, str | None]:
    """Normalize an upcoming-hearing calendar page."""

    entries = [
        _calendar_entry(page.case_number, row, ordinal)
        for row, ordinal in _occurrence_numbers(
            page.hearings,
            lambda hearing: hearing.to_dict(),
        )
    ]
    selected, next_cursor = _slice_values(
        entries,
        limit=limit,
        offset=offset,
    )
    if not selected:
        return None, None
    record = _base_case_record(
        page.case_number,
        caption=page.caption,
        filing_date=(
            _source_date(page.filing_date) if page.filing_date else None
        ),
        case_type=None,
        status=None,
        source_url=CALENDAR_URL_TEMPLATE.format(
            case_number=quote(page.case_number, safe="")
        ),
    )
    record.update(
        {
            "docket_entries": selected,
            "source_scope": {
                "record_type": "upcoming_case_calendar",
                "query_key": "exact_case_number",
                "calendar_window_days": page.calendar_window_days,
                "business_window_days": page.business_window_days,
            },
            "search_metadata": {
                "source_hearing_count": len(page.hearings),
                "returned_hearing_count": len(selected),
                "hearing_offset": offset,
                "hearing_limit": limit,
            },
            "schema_fingerprint": page.schema_fingerprint,
            "raw": {
                "message": page.message,
                "hearings": [entry["raw"] for entry in selected],
            },
        }
    )
    return record, next_cursor


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any]
    requested_limit: int | None = getattr(args, "limit", None)
    cursor = None
    if args.command == "case":
        parameters = {
            "case_number": args.case_number,
            "courthouse": args.courthouse,
            "docket_entry_offset": args.offset,
            "docket_entry_limit": args.limit,
        }
        cursor = f"la-probate:offset:{args.offset}"
    elif args.command == "notes":
        parameters = {
            "case_number": args.case_number,
            "view": args.view,
            "note_offset": args.offset,
            "note_limit": args.limit,
        }
        cursor = f"la-probate:offset:{args.offset}"
    elif args.command == "calendar":
        parameters = {
            "case_number": args.case_number,
            "hearing_offset": args.offset,
            "hearing_limit": args.limit,
        }
        cursor = f"la-probate:offset:{args.offset}"
    else:
        parameters = {"case_number": PROBE_CASE_NUMBER}
        requested_limit = 1
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Los Angeles County, California",
            state_code=STATE_CODE,
            county_fips=COUNTY_GEOID,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(
            getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
        ).expanduser(),
        config_path=Path(
            getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
        ).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _access_failure(
    query: PublicRecordsQuery,
    error: AcquisitionUnavailableError | CatalogError | OSError | ValueError,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        return PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code")
                        or "acquisition_route_unavailable"
                    ),
                    message=str(decision.get("reason") or error),
                    category="access",
                    retryable=False,
                    details=decision,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="acquisition_route_unavailable",
                message=str(error),
                category="access_control",
                retryable=False,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=decision,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _query_failure(
    query: PublicRecordsQuery,
    error: LAProbateQueryError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="query_selection",
                retryable=False,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _probe_record(snapshot: ProbeSnapshot) -> dict[str, Any]:
    return {
        "canonical_ref": (
            f"STATECOURT:{SOURCE_ID}/{COURT_ID}/probe/public-services"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "probe",
        "source_url": PROBATE_LANDING_URL,
        "court": _court_payload(),
        "probe_case_number": snapshot.case_summary.case_number,
        "case_search_schema_fingerprint": (
            snapshot.case_search.schema_fingerprint
        ),
        "case_summary_schema_fingerprint": (
            snapshot.case_summary.schema_fingerprint
        ),
        "notes_search_schema_fingerprint": (
            snapshot.notes_search.schema_fingerprint
        ),
        "calendar_schema_fingerprint": snapshot.calendar.schema_fingerprint,
        "case_summary_counts": {
            "future_hearings": len(snapshot.case_summary.future_hearings),
            "parties": len(snapshot.case_summary.parties),
            "documents": len(snapshot.case_summary.documents),
            "past_proceedings": len(
                snapshot.case_summary.past_proceedings
            ),
            "register_actions": len(snapshot.case_summary.register_actions),
        },
        "available_courthouses": dict(
            snapshot.case_search.courthouse_options
        ),
        "calendar_probe_message": snapshot.calendar.message,
    }


def _execute_command(
    args: argparse.Namespace,
    client: LosAngelesProbateClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "case":
        lookup = client.case(
            args.case_number,
            courthouse=args.courthouse,
        )
        if lookup.page is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        record, next_cursor = normalize_case(
            lookup.page,
            entry_limit=args.limit,
            entry_offset=args.offset,
        )
        if lookup.native_courthouse_value is not None:
            record["search_metadata"]["native_courthouse_value"] = (
                lookup.native_courthouse_value
            )
        return PublicRecordsResult.success(
            query,
            [record],
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "notes":
        pages = client.notes(args.case_number, view=args.view)
        record, next_cursor = normalize_notes(
            pages,
            limit=args.limit,
            offset=args.offset,
        )
        return PublicRecordsResult.success(
            query,
            [record] if record else [],
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "calendar":
        page = client.calendar(args.case_number)
        record, next_cursor = normalize_calendar(
            page,
            limit=args.limit,
            offset=args.offset,
        )
        return PublicRecordsResult.success(
            query,
            [record] if record else [],
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        return PublicRecordsResult.success(
            query,
            [_probe_record(client.probe())],
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(
        f"unsupported Los Angeles probate command: {args.command}"
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: LosAngelesProbateClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one Los Angeles probate operation."""

    query = build_query(args)
    try:
        decision = (
            dict(access_decision)
            if access_decision is not None
            else _access_contract(args)
        )
    except (AcquisitionUnavailableError, CatalogError, OSError, ValueError) as error:
        result = _access_failure(query, error)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result
    if not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    source_client = client or LosAngelesProbateClient(timeout=args.timeout)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except LAProbateQueryError as error:
        result = _query_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
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
    finally:
        if owns_client:
            source_client.close()

    count = (
        len(result.records)
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Los Angeles probate {args.command} ({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Los Angeles probate {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "case":
            print(
                f"  {record.get('raw_case_number') or '?'} | "
                f"{len(record.get('docket_entries') or [])} entries | "
                f"{record.get('caption') or '?'}"
            )
        else:
            print(
                f"  probe | {record.get('probe_case_number')} | "
                f"{record.get('case_summary_counts')}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source and acquisition catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and reviewed access decisions",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds",
    )
    add_output_args(parser)


def _add_optional_paging(
    parser: argparse.ArgumentParser,
    *,
    item_name: str,
) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help=f"Maximum {item_name} to return; omit to return every source row",
    )
    parser.add_argument(
        "--offset",
        type=_nonnegative_int,
        default=0,
        help=f"Number of {item_name} to skip",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Los Angeles Superior Court public probate services"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    case = subparsers.add_parser(
        "case",
        help="Fetch one probate Case Summary by exact case number",
    )
    case.add_argument("case_number")
    case.add_argument(
        "--courthouse",
        help=(
            "Native courthouse code offered by the source; omit to search all "
            "(currently LA or ATP)"
        ),
    )
    _add_optional_paging(case, item_name="combined docket entries")
    _add_runtime_and_output(case)

    notes = subparsers.add_parser(
        "notes",
        help="Fetch time-windowed Probate Notes by exact case number",
    )
    notes.add_argument("case_number")
    notes.add_argument(
        "--view",
        choices=("future", "past", "all"),
        default="future",
    )
    _add_optional_paging(notes, item_name="probate notes")
    _add_runtime_and_output(notes)

    calendar = subparsers.add_parser(
        "calendar",
        help="Fetch upcoming hearings by exact case number",
    )
    calendar.add_argument("case_number")
    _add_optional_paging(calendar, item_name="calendar hearings")
    _add_runtime_and_output(calendar)

    probe = subparsers.add_parser(
        "probe",
        help="Verify case, notes-form, and case-calendar contracts",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
