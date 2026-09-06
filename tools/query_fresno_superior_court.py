#!/usr/bin/env python3
"""Query Fresno Superior Court's public record publications and notes.

The court's current e-Court portal landing page, daily hearing calendars,
civil tentative rulings, Probate Examiner Notes application, case-index
product, and records-request routes are separate surfaces.  This adapter keeps
their lineage distinct while exposing every verified anonymous data operation
that currently contributes case or filing metadata.

Examples:
    uv run python tools/query_fresno_superior_court.py sources --json
    uv run python tools/query_fresno_superior_court.py portal --json
    uv run python tools/query_fresno_superior_court.py calendar-index --json
    uv run python tools/query_fresno_superior_court.py calendar \
        --date 2026-07-30 --output /tmp/fresno-calendar.json
    uv run python tools/query_fresno_superior_court.py rulings-index --json
    uv run python tools/query_fresno_superior_court.py rulings \
        --department 501 --date 2026-07-30 \
        --output /tmp/fresno-rulings.json
    uv run python tools/query_fresno_superior_court.py probate-notes \
        --case-number 19CEPR00967 --output /tmp/fresno-probate.json
    uv run python tools/query_fresno_superior_court.py alternatives --json
    uv run python tools/query_fresno_superior_court.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlparse

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
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
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
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )


STATE_CODE = "CA"
COUNTY_FIPS = "06019"
COURT_ID = "ca-fresno-superior-court"
COURT_NAME = "Superior Court of California, County of Fresno"
BASE_URL = "https://www.fresno.courts.ca.gov"
PORTAL_URL = "https://publicportal.fresno.courts.ca.gov/public-portal/?q=Home"
PORTAL_REGISTER_URL = (
    "https://publicportal.fresno.courts.ca.gov/public-portal/?q=user/register"
)
PORTAL_FAQ_URL = (
    "https://publicportal.fresno.courts.ca.gov/public-portal/?q=node/445"
)
CASE_INFORMATION_URL = f"{BASE_URL}/online-services/case-information"
CMS_NOTICE_URL = f"{BASE_URL}/system/files/general/court-cms-notice.pdf"
CALENDAR_INDEX_URL = (
    f"{BASE_URL}/general-information/calendar-daily-hearings"
)
RULINGS_INDEX_URL = f"{BASE_URL}/online-services/tentative-rulings"
PROBATE_NOTES_URL = (
    "https://info.fresno.courts.ca.gov/ProbateExaminersNotes/"
    "ProbateExaminerNotesSearch.aspx"
)
CASE_INDEX_URL = (
    f"{CASE_INFORMATION_URL}/case-index-ordering"
)
CASE_INDEX_FORM_URL = (
    f"{BASE_URL}/system/files/forms-and-filings/"
    "pgn-81-case-index-order-form100125.pdf"
)
ARCHIVES_URL = f"{CASE_INFORMATION_URL}/archives"
GENERAL_INFORMATION_URL = f"{BASE_URL}/general-information"
ELEVATED_ACCESS_FORM_URL = (
    f"{BASE_URL}/system/files/general/"
    "portal-attorney-elevated-request-form-final.pdf"
)
CIVIL_CONTACT_URL = (
    "https://info.fresno.courts.ca.gov/InfoDesk-Civil/"
    "InfoDeskForm-CivilGeneral.aspx"
)
CRIMINAL_CONTACT_URL = (
    "https://info.fresno.courts.ca.gov/InfoDesk-Criminal/"
    "InfoDeskForm-CriminalTraffic.aspx"
)
APPELLATE_SEARCH_URL = (
    "https://appellatecases.courtinfo.ca.gov/search.cfm?dist=5"
)

FAMILY_SOURCE_ID = "us-ca-fresno-superior-court-public-records"
PORTAL_SOURCE_ID = "us-ca-fresno-superior-court-ecourt-portal"
CALENDAR_SOURCE_ID = "us-ca-fresno-superior-court-daily-calendar"
RULINGS_SOURCE_ID = "us-ca-fresno-superior-court-tentative-rulings"
PROBATE_SOURCE_ID = "us-ca-fresno-superior-court-probate-examiner-notes"
INDEX_SOURCE_ID = "us-ca-fresno-superior-court-case-index-product"
RECORDS_SOURCE_ID = "us-ca-fresno-superior-court-records-routes"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

_OFFICIAL_HOSTS = frozenset(
    {
        "www.fresno.courts.ca.gov",
        "fresno.courts.ca.gov",
        "publicportal.fresno.courts.ca.gov",
        "info.fresno.courts.ca.gov",
    }
)
_CALENDAR_PATH_RE = re.compile(
    r"^/system/files/general/merged-calendar-(\d{8})\.pdf$",
    re.I,
)
_RULING_PATH_RE = re.compile(
    r"^/system/files/tentative-rulings/"
    r"(\d{2})-(\d{2})-(\d{2})-dept-(\d+)-[^/]+\.pdf$",
    re.I,
)
_CASE_TOKEN_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{4,}$")
_MASTER_CASE_RE = re.compile(
    r"^\s*([A-Z0-9][A-Z0-9_-]{4,})\s{2,}(\S.*)$"
)
_TIME_RE = re.compile(r"^\s*(\d{1,2}:\d{2})\s*(AM|PM)\s*$", re.I)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)
_PROBATE_REQUIRED_HIDDEN = (
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
    "__ncforminfo",
)

SOURCE_METADATA = {
    FAMILY_SOURCE_ID: SourceMetadata(
        source_id=FAMILY_SOURCE_ID,
        name="Fresno Superior Court Public Record Surfaces",
        source_role="official_county_court_source_family",
        base_url=CASE_INFORMATION_URL,
        dataset_id="fresno-superior-court-public-records",
        metadata={
            "authority": COURT_NAME,
            "county_fips": COUNTY_FIPS,
            "component_source_ids": [
                PORTAL_SOURCE_ID,
                CALENDAR_SOURCE_ID,
                RULINGS_SOURCE_ID,
                PROBATE_SOURCE_ID,
                INDEX_SOURCE_ID,
                RECORDS_SOURCE_ID,
            ],
        },
    ),
    PORTAL_SOURCE_ID: SourceMetadata(
        source_id=PORTAL_SOURCE_ID,
        name="Fresno Superior Court e-Court Public Portal",
        source_role="official_interactive_case_information_portal",
        base_url=PORTAL_URL,
        dataset_id="fresno-ecourt-public-portal",
        metadata={
            "authority": COURT_NAME,
            "county_fips": COUNTY_FIPS,
            "system": "Journal Technologies e-Court",
            "effective_date": "2026-04-01",
            "observed_landing_operations": [
                "home",
                "faq",
                "register",
                "login",
            ],
        },
    ),
    CALENDAR_SOURCE_ID: SourceMetadata(
        source_id=CALENDAR_SOURCE_ID,
        name="Fresno Superior Court Daily Hearing Calendars",
        source_role="official_daily_hearing_schedule_pdfs",
        base_url=CALENDAR_INDEX_URL,
        dataset_id="fresno-superior-court-daily-calendars",
        metadata={
            "authority": COURT_NAME,
            "county_fips": COUNTY_FIPS,
            "authentication": "none",
            "publication_format": "pdf",
        },
    ),
    RULINGS_SOURCE_ID: SourceMetadata(
        source_id=RULINGS_SOURCE_ID,
        name="Fresno Superior Court Civil Tentative Rulings",
        source_role="official_civil_tentative_ruling_pdfs",
        base_url=RULINGS_INDEX_URL,
        dataset_id="fresno-superior-court-tentative-rulings",
        metadata={
            "authority": COURT_NAME,
            "county_fips": COUNTY_FIPS,
            "authentication": "none",
            "observed_departments": [403, 501, 502, 503],
            "source_stated_posting": "3 PM on the court day before hearing",
        },
    ),
    PROBATE_SOURCE_ID: SourceMetadata(
        source_id=PROBATE_SOURCE_ID,
        name="Fresno Superior Court Probate Examiner Notes",
        source_role="official_probate_examiner_note_application",
        base_url=PROBATE_NOTES_URL,
        dataset_id="fresno-probate-examiner-notes",
        metadata={
            "authority": COURT_NAME,
            "county_fips": COUNTY_FIPS,
            "authentication": "none",
            "query_fields": ["case_number", "optional_hearing_date"],
            "record_lineage": "examiner_note_not_part_of_official_court_file",
        },
    ),
    INDEX_SOURCE_ID: SourceMetadata(
        source_id=INDEX_SOURCE_ID,
        name="Fresno Superior Court Monthly Case Index Reports",
        source_role="official_ordered_monthly_case_index_product",
        base_url=CASE_INDEX_URL,
        dataset_id="fresno-superior-court-monthly-case-index",
        metadata={
            "authority": COURT_NAME,
            "county_fips": COUNTY_FIPS,
            "delivery_formats": ["pdf", "text"],
            "delivery": "email",
        },
    ),
    RECORDS_SOURCE_ID: SourceMetadata(
        source_id=RECORDS_SOURCE_ID,
        name="Fresno Superior Court Case Record and Contact Routes",
        source_role="official_case_copy_contact_and_archive_routes",
        base_url=ARCHIVES_URL,
        dataset_id="fresno-superior-court-records-routes",
        metadata={
            "authority": COURT_NAME,
            "county_fips": COUNTY_FIPS,
        },
    ),
}

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_FIPS,
    name="Fresno County",
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
)

SOURCE_WARNINGS = (
    "Daily calendars are court-published hearing schedules, not complete case dockets.",
    "Tentative-ruling records retain their tentative status; the court page describes when an unchallenged tentative ruling may become the order.",
    "The Probate Examiner Notes page states that its notes are not part of the official court file.",
)


class FresnoCourtError(RuntimeError):
    """One Fresno source, query, transport, or parsing error."""

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

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class FresnoSelectionError(FresnoCourtError):
    """A source-native selector is invalid or ambiguous."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="query_selection",
            details=details,
        )


class FresnoSourceChangedError(FresnoCourtError):
    """A verified official source no longer has its expected structure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


@dataclass(frozen=True)
class ArtifactIndex:
    """An official page and every matching PDF link found on it."""

    source_url: str
    records: tuple[Mapping[str, Any], ...]
    schema_fingerprint: str


@dataclass(frozen=True)
class PDFArtifact:
    """Validated PDF bytes and extracted layout text."""

    source_url: str
    content: bytes
    sha256: str
    text: str


@dataclass(frozen=True)
class ProbateSearchPage:
    """Validated WebForms search page and transient hidden values."""

    source_url: str
    hidden_fields: Mapping[str, str]
    schema_fingerprint: str


@dataclass(frozen=True)
class ProbateResults:
    """Parsed summary and all notes returned by one authoritative query."""

    source_url: str
    case_number: str
    case_style: str | None
    date_printed: str | None
    notes_found: int
    records: tuple[Mapping[str, Any], ...]
    no_results_message: str | None
    schema_fingerprint: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _multiline_text(value: Any) -> str | None:
    if value is None:
        return None
    lines = [
        " ".join(line.replace("\xa0", " ").split())
        for line in str(value).splitlines()
    ]
    normalized = "\n".join(line for line in lines if line).strip()
    return normalized or None


def _schema_fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def _parse_date(value: str, formats: Sequence[str]) -> str:
    for date_format in formats:
        try:
            return datetime.strptime(value.strip(), date_format).date().isoformat()
        except ValueError:
            continue
    raise FresnoSourceChangedError(
        "date_format_changed",
        f"Fresno court date does not match a verified format: {value!r}",
    )


def _validate_iso_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise FresnoSelectionError(
            "invalid_date",
            "date must use YYYY-MM-DD",
            details={"value": value},
        ) from error


def _validate_hearing_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        datetime.strptime(value, "%m/%d/%Y")
    except ValueError as error:
        raise FresnoSelectionError(
            "invalid_hearing_date",
            "hearing date must use MM/DD/YYYY",
            details={"value": value},
        ) from error
    return value


def _official_url(
    value: str,
    *,
    pdf_family: str | None = None,
) -> str:
    url = urljoin(BASE_URL, value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_HOSTS:
        raise FresnoSelectionError(
            "invalid_official_url",
            "URL must identify an official Fresno Superior Court host",
            details={"url": value},
        )
    if pdf_family == "calendar" and _CALENDAR_PATH_RE.match(parsed.path) is None:
        raise FresnoSelectionError(
            "invalid_calendar_url",
            "calendar URL does not match the court's merged-calendar PDF route",
            details={"url": value},
        )
    if pdf_family == "ruling" and _RULING_PATH_RE.match(parsed.path) is None:
        raise FresnoSelectionError(
            "invalid_ruling_url",
            "ruling URL does not match the court's tentative-rulings PDF route",
            details={"url": value},
        )
    return url


def _court_provenance(
    source_id: str,
    source_url: str,
    *,
    sha256: str | None = None,
    page_number: int | None = None,
    response_schema_fingerprint: str | None = None,
) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "source_id": source_id,
        "source_url": source_url,
        "authority": COURT_NAME,
    }
    if sha256 is not None:
        provenance["artifact_sha256"] = sha256
    if page_number is not None:
        provenance["page_number"] = page_number
    if response_schema_fingerprint is not None:
        provenance["response_schema_fingerprint"] = (
            response_schema_fingerprint
        )
    return provenance


def parse_portal_state(
    home_html: str,
    registration_html: str,
    *,
    source_url: str = PORTAL_URL,
    registration_url: str = PORTAL_REGISTER_URL,
) -> Mapping[str, Any]:
    """Describe controls actually present in the rendered portal HTML."""

    home = BeautifulSoup(home_html, "html.parser")
    registration = BeautifulSoup(registration_html, "html.parser")
    title = _text(home.title.get_text(" ", strip=True)) if home.title else None
    if title is None or "Fresno Superior Court Portal" not in title:
        raise FresnoSourceChangedError(
            "portal_title_changed",
            "Fresno e-Court landing page title changed",
            details={"observed_title": title},
        )
    register_form = registration.select_one("form#user-register-form")
    if register_form is None:
        raise FresnoSourceChangedError(
            "registration_form_missing",
            "Fresno e-Court registration page lacks its account form",
        )
    visible_fields: list[dict[str, Any]] = []
    for control in register_form.select("input[name], select[name], textarea[name]"):
        input_type = str(control.get("type", "")).casefold()
        if input_type in {"hidden", "submit", "button", "image"}:
            continue
        name = str(control["name"])
        visible_fields.append(
            {
                "name": name,
                "type": input_type or control.name,
                "required": (
                    control.has_attr("required")
                    or "required" in control.get("class", [])
                ),
            }
        )
    expected_fields = {
        "mail",
        "conf_mail",
        "profile_firstName",
        "profile_lastName",
        "profile_phone",
        "terms_of_use",
    }
    observed_fields = {field["name"] for field in visible_fields}
    if not expected_fields.issubset(observed_fields):
        raise FresnoSourceChangedError(
            "registration_fields_changed",
            "Fresno e-Court registration fields changed",
            details={
                "expected_fields": sorted(expected_fields),
                "observed_fields": sorted(observed_fields),
            },
        )
    home_forms = home.find_all("form")
    search_forms = [
        form
        for form in home_forms
        if "search"
        in " ".join(
            [
                str(form.get("id", "")),
                str(form.get("name", "")),
                str(form.get("action", "")),
                " ".join(
                    str(control.get("name", ""))
                    for control in form.select("[name]")
                ),
            ]
        ).casefold()
    ]
    links = []
    for link in home.select("a[href]"):
        label = _text(link.get_text(" ", strip=True))
        if label:
            links.append(
                {
                    "label": label,
                    "url": urljoin(source_url, str(link["href"])),
                }
            )
    schema = _schema_fingerprint(
        {
            "title": title,
            "home_form_count": len(home_forms),
            "search_form_count": len(search_forms),
            "visible_registration_fields": visible_fields,
        }
    )
    return {
        "canonical_ref": "FRESNO-ECOURT:LANDING-STATE",
        "evidence_ref": "FRESNO-ECOURT:LANDING-STATE",
        "source_id": PORTAL_SOURCE_ID,
        "record_kind": "portal_observation",
        "system": "Journal Technologies e-Court",
        "title": title,
        "source_url": source_url,
        "registration_url": registration_url,
        "anonymous_case_search_control_present": bool(search_forms),
        "home_form_count": len(home_forms),
        "landing_links": links,
        "registration": {
            "visible_fields": visible_fields,
            "requires_email_confirmation": {
                "mail",
                "conf_mail",
            }.issubset(observed_fields),
        },
        "effective_date": "2026-04-01",
        "cms_notice_url": CMS_NOTICE_URL,
        "case_information_url": CASE_INFORMATION_URL,
        "provenance": _court_provenance(
            PORTAL_SOURCE_ID,
            source_url,
            response_schema_fingerprint=schema,
        ),
    }


def parse_calendar_index(
    html_text: str,
    *,
    source_url: str = CALENDAR_INDEX_URL,
) -> ArtifactIndex:
    """Parse every daily calendar PDF currently linked by the court."""

    soup = BeautifulSoup(html_text, "html.parser")
    records: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        resolved = urljoin(source_url, str(link["href"]))
        parsed = urlparse(resolved)
        match = _CALENDAR_PATH_RE.match(parsed.path)
        if parsed.hostname not in _OFFICIAL_HOSTS or match is None:
            continue
        url = _official_url(resolved, pdf_family="calendar")
        if url in seen:
            continue
        seen.add(url)
        label = _text(link.get_text(" ", strip=True))
        publication_date = (
            _parse_date(label, ("%B %d, %Y",))
            if label is not None
            else _parse_date(match.group(1), ("%m%d%Y",))
        )
        canonical_ref = f"FRESNO-CALENDAR-PDF:{publication_date}"
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": CALENDAR_SOURCE_ID,
                "record_kind": "document_artifact",
                "document_type": "daily_hearing_calendar",
                "publication_date": publication_date,
                "label": label,
                "source_url": url,
                "index_url": source_url,
                "mime_type": "application/pdf",
                "provenance": _court_provenance(
                    CALENDAR_SOURCE_ID,
                    source_url,
                ),
            }
        )
    if not records:
        raise FresnoSourceChangedError(
            "calendar_links_missing",
            "Fresno daily-hearing page has no merged-calendar PDF links",
        )
    schema = _schema_fingerprint(
        {
            "path_pattern": "/system/files/general/merged-calendar-MMDDYYYY.pdf",
            "artifact_count": len(records),
        }
    )
    return ArtifactIndex(
        source_url=source_url,
        records=tuple(records),
        schema_fingerprint=schema,
    )


def parse_rulings_index(
    html_text: str,
    *,
    source_url: str = RULINGS_INDEX_URL,
) -> ArtifactIndex:
    """Parse every tentative-ruling PDF currently linked by the court."""

    soup = BeautifulSoup(html_text, "html.parser")
    records: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        resolved = urljoin(source_url, str(link["href"]))
        parsed = urlparse(resolved)
        match = _RULING_PATH_RE.match(parsed.path)
        if parsed.hostname not in _OFFICIAL_HOSTS or match is None:
            continue
        url = _official_url(resolved, pdf_family="ruling")
        if url in seen:
            continue
        seen.add(url)
        month, day, year, department = match.groups()
        publication_date = _parse_date(
            f"{month}/{day}/{year}",
            ("%m/%d/%y",),
        )
        label = _text(link.get_text(" ", strip=True))
        canonical_ref = (
            f"FRESNO-TENTATIVE-PDF:{publication_date}:D{department}"
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": RULINGS_SOURCE_ID,
                "record_kind": "document_artifact",
                "document_type": "civil_tentative_rulings",
                "publication_date": publication_date,
                "department": int(department),
                "label": label,
                "source_url": url,
                "index_url": source_url,
                "mime_type": "application/pdf",
                "provenance": _court_provenance(
                    RULINGS_SOURCE_ID,
                    source_url,
                ),
            }
        )
    if not records:
        raise FresnoSourceChangedError(
            "ruling_links_missing",
            "Fresno tentative-rulings page has no ruling PDF links",
        )
    schema = _schema_fingerprint(
        {
            "path_pattern": (
                "/system/files/tentative-rulings/"
                "MM-DD-YY-dept-DEPARTMENT-*.pdf"
            ),
            "departments": sorted(
                {int(record["department"]) for record in records}
            ),
            "artifact_count": len(records),
        }
    )
    return ArtifactIndex(
        source_url=source_url,
        records=tuple(records),
        schema_fingerprint=schema,
    )


def _calendar_record(
    *,
    case_number: str,
    case_style: str,
    hearing_date: str,
    hearing_time: str | None,
    department: str,
    judge: str | None,
    hearing_type: str | None,
    status: str | None,
    attorney: str | None,
    filing_agency_number: str | None,
    page_number: int,
    layout: str,
    source_text: str,
    source_url: str,
    artifact_sha256: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity = {
        "case_number": case_number,
        "hearing_date": hearing_date,
        "hearing_time": hearing_time,
        "department": department,
        "hearing_type": hearing_type,
        "source_text": source_text,
    }
    suffix = _schema_fingerprint(identity)[:20]
    record: dict[str, Any] = {
        "canonical_ref": f"FRESNO-CALENDAR:{case_number}:{suffix}",
        "evidence_ref": f"FRESNO-CALENDAR:{case_number}:{suffix}",
        "source_id": CALENDAR_SOURCE_ID,
        "record_kind": "court_hearing",
        "case_number": case_number,
        "case_style": case_style,
        "hearing_date": hearing_date,
        "hearing_time": hearing_time,
        "department": department,
        "judge": judge,
        "hearing_type": hearing_type,
        "status_or_custody": status,
        "attorney": attorney,
        "filing_or_prosecuting_agency_number": filing_agency_number,
        "calendar_layout": layout,
        "source_text": source_text,
        "source_url": source_url,
        "court": {
            "court_id": COURT_ID,
            "name": COURT_NAME,
            "state_code": STATE_CODE,
            "county_fips": COUNTY_FIPS,
        },
        "provenance": _court_provenance(
            CALENDAR_SOURCE_ID,
            source_url,
            sha256=artifact_sha256,
            page_number=page_number,
        ),
    }
    if extra:
        record.update(extra)
    return record


def _split_attorney(value: str) -> tuple[str, str | None]:
    if "ATTY:" not in value.upper():
        return value.strip(), None
    match = re.search(r"\bATTY:\s*", value, re.I)
    if match is None:
        return value.strip(), None
    return value[: match.start()].strip(), value[match.end() :].strip() or None


def _parse_master_calendar(
    pages: Sequence[str],
    *,
    source_url: str,
    artifact_sha256: str,
) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    last_time_by_calendar: dict[tuple[str, str], str] = {}
    for page_number, page in enumerate(pages, start=1):
        if "Master Calendar Report" not in page:
            continue
        judge_match = re.search(r"(?m)^\s*Judge:\s*(.*?)\s*$", page)
        date_match = re.search(r"(?m)^\s*Date:\s*(.*?)\s*$", page)
        department_match = re.search(
            r"(?m)^\s*Department:\s*(?:Department\s+)?(.+?)\s*$",
            page,
        )
        if date_match is None or department_match is None:
            raise FresnoSourceChangedError(
                "master_calendar_header_changed",
                "Fresno master-calendar page lacks date or department",
                details={"page_number": page_number},
            )
        hearing_date = _parse_date(
            date_match.group(1),
            ("%A, %B %d, %Y", "%B %d, %Y"),
        )
        department = department_match.group(1).strip()
        judge = _text(judge_match.group(1)) if judge_match else None
        calendar_key = (hearing_date, department)
        current_time = last_time_by_calendar.get(calendar_key)
        lines = page.splitlines()
        case_entries: list[tuple[int, str | None]] = []
        for index, line in enumerate(lines):
            time_match = _TIME_RE.match(line)
            if time_match:
                current_time = (
                    f"{time_match.group(1)} {time_match.group(2).upper()}"
                )
                last_time_by_calendar[calendar_key] = current_time
                continue
            case_match = _MASTER_CASE_RE.match(line)
            if (
                case_match is not None
                and _CASE_TOKEN_RE.match(case_match.group(1)) is not None
                and any(character.isdigit() for character in case_match.group(1))
            ):
                case_entries.append((index, current_time))
        for position, (line_index, case_time) in enumerate(case_entries):
            line = lines[line_index]
            match = _MASTER_CASE_RE.match(line)
            assert match is not None
            case_number = match.group(1)
            case_style, attorney = _split_attorney(match.group(2))
            next_index = (
                case_entries[position + 1][0]
                if position + 1 < len(case_entries)
                else len(lines)
            )
            block_lines = [line]
            detail_lines: list[str] = []
            for detail_line in lines[line_index + 1 : next_index]:
                if (
                    detail_line.lstrip().startswith("Run:")
                    or "Master Calendar Report" in detail_line
                    or re.match(
                        r"^\s*(?:Judge|Date|Department):",
                        detail_line,
                    )
                ):
                    continue
                if _TIME_RE.match(detail_line):
                    break
                if detail_line.strip():
                    detail_lines.append(detail_line)
                    block_lines.append(detail_line)
            party_column = match.start(2)
            split_details: list[tuple[str, str]] = []
            for detail_line in detail_lines:
                left = detail_line[:party_column].strip()
                right = detail_line[party_column:].strip()
                split_details.append((left, right))
            right_only = [
                right
                for left, right in split_details
                if not left and right
            ]
            if (
                len(right_only) >= 2
                and (
                    " vs " in case_style.casefold()
                    or re.search(r"(?:,|&|\bvs\.?|\bv\.?)\s*$", case_style, re.I)
                )
            ):
                continuation = right_only[0]
                case_style = f"{case_style} {continuation}"
                for detail_index, (left, right) in enumerate(split_details):
                    if not left and right == continuation:
                        split_details.pop(detail_index)
                        break
            left_parts = [left for left, _ in split_details if left]
            right_parts = [right for _, right in split_details if right]
            status = _text(" ".join(left_parts))
            right_text = " ".join(right_parts)
            agency_match = re.search(
                r"\bFiling Agency #:\s*(.+)$",
                right_text,
                re.I,
            )
            filing_agency_number = (
                _text(agency_match.group(1)) if agency_match else None
            )
            if agency_match:
                right_text = right_text[: agency_match.start()].strip()
            hearing_type = _text(right_text)
            records.append(
                _calendar_record(
                    case_number=case_number,
                    case_style=case_style,
                    hearing_date=hearing_date,
                    hearing_time=case_time,
                    department=department,
                    judge=judge,
                    hearing_type=hearing_type,
                    status=status,
                    attorney=attorney,
                    filing_agency_number=filing_agency_number,
                    page_number=page_number,
                    layout="master_calendar_report",
                    source_text="\n".join(block_lines),
                    source_url=source_url,
                    artifact_sha256=artifact_sha256,
                )
            )
    return records


def _parse_trial_calendars(
    pages: Sequence[str],
    *,
    source_url: str,
    artifact_sha256: str,
) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for page_number, page in enumerate(pages, start=1):
        if (
            "Superior Court, County of Fresno" not in page
            or "Master Calendar Report" in page
        ):
            continue
        sections = re.split(
            r"(?i)(?=\s*Superior Court, County of Fresno)",
            page,
        )
        for section in sections:
            if "Superior Court, County of Fresno" not in section:
                continue
            judge_match = re.search(r"(?m)^\s*Hon\.\s*(.*?)\s*$", section)
            date_match = re.search(r"(?m)^\s*Date:\s*(.*?)\s*$", section)
            department_match = re.search(
                r"(?m)^\s*Dept\.\s*(.*?)\s*$",
                section,
            )
            time_match = re.search(
                r"(?m)^\s*Hearings for\s+(.+?)\s*$",
                section,
            )
            if (
                date_match is None
                or department_match is None
                or time_match is None
            ):
                raise FresnoSourceChangedError(
                    "trial_calendar_header_changed",
                    "Fresno trial-calendar section lacks date, department, or time",
                    details={"page_number": page_number},
                )
            hearing_date = _parse_date(date_match.group(1), ("%m/%d/%Y",))
            department = department_match.group(1).strip()
            hearing_time = _text(time_match.group(1))
            judge = _text(judge_match.group(1)) if judge_match else None
            lines = section.splitlines()
            case_indexes = []
            for index, line in enumerate(lines):
                match = _MASTER_CASE_RE.match(line)
                if (
                    match is not None
                    and _CASE_TOKEN_RE.match(match.group(1)) is not None
                    and any(character.isdigit() for character in match.group(1))
                ):
                    case_indexes.append(index)
            for position, line_index in enumerate(case_indexes):
                line = lines[line_index]
                match = _MASTER_CASE_RE.match(line)
                assert match is not None
                case_number = match.group(1)
                case_style, attorney = _split_attorney(match.group(2))
                next_index = (
                    case_indexes[position + 1]
                    if position + 1 < len(case_indexes)
                    else len(lines)
                )
                block = "\n".join(lines[line_index:next_index]).strip()
                block = re.split(r"\n\s*-{8,}", block, maxsplit=1)[0]
                jail_match = re.search(r"\bJail ID:\s*(\S+)", block, re.I)
                booking_match = re.search(
                    r"\bBooking Number:\s*(\S+)",
                    block,
                    re.I,
                )
                agency_match = re.search(
                    r"\bProsecuting Agency Number:\s*([^\n]+)",
                    block,
                    re.I,
                )
                interpreter_match = re.search(
                    r"\bInterpreter:\s*([^\n]+)",
                    block,
                    re.I,
                )
                hearing_match = re.search(
                    r"(?m)^\s*Hearing:\s*(.*?)(?:\s{2,}DDA:.*)?$",
                    block,
                    re.I,
                )
                dda_match = re.search(r"\bDDA:\s*([^\n]+)", block, re.I)
                status = None
                if len(block.splitlines()) > 1:
                    candidate = block.splitlines()[1]
                    candidate = re.split(
                        r"\s{2,}(?:Jail ID|Booking Number|"
                        r"Prosecuting Agency Number|Interpreter|Hearing|DDA):",
                        candidate,
                        maxsplit=1,
                    )[0]
                    status = _text(candidate)
                notes_lines = []
                for detail_line in block.splitlines()[1:]:
                    if re.search(
                        r"\b(?:Jail ID|Booking Number|"
                        r"Prosecuting Agency Number|Interpreter|Hearing):",
                        detail_line,
                        re.I,
                    ):
                        continue
                    candidate = re.split(
                        r"\s{2,}DDA:",
                        detail_line,
                        maxsplit=1,
                        flags=re.I,
                    )[0]
                    if _text(candidate) and _text(candidate) != status:
                        notes_lines.append(candidate.strip())
                records.append(
                    _calendar_record(
                        case_number=case_number,
                        case_style=case_style,
                        hearing_date=hearing_date,
                        hearing_time=hearing_time,
                        department=department,
                        judge=judge,
                        hearing_type=(
                            _text(hearing_match.group(1))
                            if hearing_match
                            else None
                        ),
                        status=status,
                        attorney=attorney,
                        filing_agency_number=(
                            _text(agency_match.group(1))
                            if agency_match
                            else None
                        ),
                        page_number=page_number,
                        layout="trial_calendar",
                        source_text=block,
                        source_url=source_url,
                        artifact_sha256=artifact_sha256,
                        extra={
                            "jail_id": (
                                _text(jail_match.group(1))
                                if jail_match
                                else None
                            ),
                            "booking_number": (
                                _text(booking_match.group(1))
                                if booking_match
                                else None
                            ),
                            "interpreter": (
                                _text(interpreter_match.group(1))
                                if interpreter_match
                                else None
                            ),
                            "deputy_district_attorney": (
                                _text(dda_match.group(1))
                                if dda_match
                                else None
                            ),
                            "calendar_notes": _text(" ".join(notes_lines)),
                        },
                    )
                )
    return records


def parse_calendar_text(
    text: str,
    *,
    source_url: str,
    artifact_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    """Parse every case row from both Fresno daily-calendar layouts."""

    pages = text.split("\f")
    records = [
        *_parse_trial_calendars(
            pages,
            source_url=source_url,
            artifact_sha256=artifact_sha256,
        ),
        *_parse_master_calendar(
            pages,
            source_url=source_url,
            artifact_sha256=artifact_sha256,
        ),
    ]
    if not records:
        raise FresnoSourceChangedError(
            "calendar_records_missing",
            "Fresno daily-calendar PDF contains no recognized hearing rows",
        )
    return tuple(records)


def _clean_pdf_block(value: str) -> str:
    lines: list[str] = []
    for line in value.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"\d+", stripped):
            continue
        if re.fullmatch(
            r"Tentative Rulings for Department \d+",
            stripped,
            re.I,
        ):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _tentative_record(
    *,
    record_kind: str,
    case_number: str,
    case_style: str,
    hearing_date: str,
    department: int,
    source_text: str,
    source_url: str,
    artifact_sha256: str,
    page_number: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    suffix = _schema_fingerprint(
        {
            "record_kind": record_kind,
            "case_number": case_number,
            "hearing_date": hearing_date,
            "department": department,
            "source_text": source_text,
        }
    )[:20]
    record: dict[str, Any] = {
        "canonical_ref": f"FRESNO-TENTATIVE:{case_number}:{suffix}",
        "evidence_ref": f"FRESNO-TENTATIVE:{case_number}:{suffix}",
        "source_id": RULINGS_SOURCE_ID,
        "record_kind": record_kind,
        "case_number": case_number,
        "case_style": case_style,
        "hearing_date": hearing_date,
        "department": department,
        "source_text": source_text,
        "source_url": source_url,
        "court": {
            "court_id": COURT_ID,
            "name": COURT_NAME,
            "state_code": STATE_CODE,
            "county_fips": COUNTY_FIPS,
        },
        "provenance": _court_provenance(
            RULINGS_SOURCE_ID,
            source_url,
            sha256=artifact_sha256,
            page_number=page_number,
        ),
    }
    if extra:
        record.update(extra)
    return record


def parse_tentative_rulings_text(
    text: str,
    *,
    source_url: str,
    artifact_sha256: str,
) -> tuple[Mapping[str, Any], ...]:
    """Parse all structured rulings and listed exceptions from one PDF."""

    header_date = re.search(
        r"Tentative Rulings for\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        text,
        re.I,
    )
    header_department = re.search(r"\bDepartment\s+(\d+)\b", text, re.I)
    if header_date is None or header_department is None:
        raise FresnoSourceChangedError(
            "tentative_header_changed",
            "Fresno tentative-ruling PDF lacks its date or department header",
        )
    publication_date = _parse_date(header_date.group(1), ("%B %d, %Y",))
    department = int(header_department.group(1))
    pages = text.split("\f")
    records: list[Mapping[str, Any]] = []

    continued_match = re.search(
        r"The court has continued the following cases\.(.*?)(?:_{8,}|"
        r"Tentative Rulings begin|\n\s*\(\d+\))",
        text,
        re.I | re.S,
    )
    if continued_match:
        continued_text = continued_match.group(1)
        for match in re.finditer(
            r"(?ms)^\s*([A-Z0-9][A-Z0-9_-]{4,})\s{2,}"
            r"(.+?)\s+is continued to\s+(.+?)"
            r"(?=^\s*[A-Z0-9][A-Z0-9_-]{4,}\s{2,}|\Z)",
            continued_text,
        ):
            case_number = match.group(1)
            if not any(character.isdigit() for character in case_number):
                continue
            case_style = _text(match.group(2))
            continuation_text = _text(match.group(3))
            if case_style is None or continuation_text is None:
                continue
            target_date_match = re.search(
                r"([A-Za-z]+ \d{1,2}, \d{4})",
                continuation_text,
            )
            target_time_match = re.search(
                r"(\d{1,2}:\d{2}\s*[ap]\.?m\.?)",
                continuation_text,
                re.I,
            )
            target_department_match = re.search(
                r"\bDepartment\s+(\d+)",
                continuation_text,
                re.I,
            )
            source_block = _clean_pdf_block(match.group(0))
            records.append(
                _tentative_record(
                    record_kind="tentative_ruling_continuance",
                    case_number=case_number,
                    case_style=case_style,
                    hearing_date=publication_date,
                    department=department,
                    source_text=source_block,
                    source_url=source_url,
                    artifact_sha256=artifact_sha256,
                    extra={
                        "continued_to_date": (
                            _parse_date(
                                target_date_match.group(1),
                                ("%B %d, %Y",),
                            )
                            if target_date_match
                            else None
                        ),
                        "continued_to_time": (
                            _text(target_time_match.group(1))
                            if target_time_match
                            else None
                        ),
                        "continued_to_department": (
                            int(target_department_match.group(1))
                            if target_department_match
                            else None
                        ),
                    },
                )
            )

    must_appear_match = re.search(
        r"must appear[”\"]? section\.(.*?)(?:"
        r"The court has continued the following cases|"
        r"Tentative Rulings begin|\n\s*\(\d+\))",
        text,
        re.I | re.S,
    )
    if must_appear_match:
        for match in re.finditer(
            r"(?m)^\s*([A-Z0-9][A-Z0-9_-]{4,})\s{2,}(.+?)\s*$",
            must_appear_match.group(1),
        ):
            case_number = match.group(1)
            if not any(character.isdigit() for character in case_number):
                continue
            case_style = _text(match.group(2))
            if case_style is None:
                continue
            records.append(
                _tentative_record(
                    record_kind="tentative_ruling_must_appear",
                    case_number=case_number,
                    case_style=case_style,
                    hearing_date=publication_date,
                    department=department,
                    source_text=_clean_pdf_block(match.group(0)),
                    source_url=source_url,
                    artifact_sha256=artifact_sha256,
                )
            )

    matter_matches = list(re.finditer(r"(?m)^\s*\((\d+)\)\s*$", text))
    for index, matter_match in enumerate(matter_matches):
        end = (
            matter_matches[index + 1].start()
            if index + 1 < len(matter_matches)
            else len(text)
        )
        block = _clean_pdf_block(text[matter_match.start() : end])
        identity_match = re.search(
            r"Re:\s*(.*?)\s+Superior Court Case No\.\s*"
            r"([A-Z0-9_-]+)",
            block,
            re.I | re.S,
        )
        hearing_match = re.search(
            r"Hearing Date:\s*(.+?)(?:\n|$)",
            block,
            re.I,
        )
        motion_match = re.search(
            r"Motion:\s*(.*?)(?=\n\s*(?:If oral argument|"
            r"Tentative Ruling:))",
            block,
            re.I | re.S,
        )
        ruling_match = re.search(
            r"Tentative Ruling:\s*(.*?)(?=\n\s*Explanation:|"
            r"\n\s*Tentative Ruling\s*\n?\s*Issued By:|\Z)",
            block,
            re.I | re.S,
        )
        explanation_match = re.search(
            r"Explanation:\s*(.*?)(?=\n\s*Tentative Ruling\s*"
            r"\n?\s*Issued By:|\Z)",
            block,
            re.I | re.S,
        )
        issued_match = re.search(
            r"Tentative Ruling\s*Issued By:\s*([A-Z]+)\s+on\s+"
            r"(\d{2}/\d{2}/\d{2})",
            block,
            re.I | re.S,
        )
        if (
            identity_match is None
            or hearing_match is None
            or motion_match is None
            or ruling_match is None
        ):
            raise FresnoSourceChangedError(
                "tentative_matter_changed",
                "Fresno tentative-ruling matter lacks a verified field",
                details={"matter_number": int(matter_match.group(1))},
            )
        case_style = _text(identity_match.group(1))
        case_number = identity_match.group(2)
        hearing_raw = _text(hearing_match.group(1))
        if case_style is None or hearing_raw is None:
            raise FresnoSourceChangedError(
                "tentative_identity_empty",
                "Fresno tentative-ruling matter has an empty identity field",
            )
        matter_date_match = re.search(
            r"([A-Za-z]+ \d{1,2}, \d{4})",
            hearing_raw,
        )
        matter_department_match = re.search(
            r"\bDept\.\s*(\d+)",
            hearing_raw,
            re.I,
        )
        matter_hearing_date = (
            _parse_date(matter_date_match.group(1), ("%B %d, %Y",))
            if matter_date_match
            else publication_date
        )
        page_number = next(
            (
                page_index
                for page_index, page in enumerate(pages, start=1)
                if matter_match.group(0).strip() in page
                and case_number in page
            ),
            None,
        )
        oral_match = re.search(
            r"If oral argument.*?on\s+([A-Za-z]+,\s+"
            r"[A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+"
            r"(\d{1,2}:\d{2}\s*[ap]\.?m\.?).*?"
            r"Department\s+(\d+)",
            block,
            re.I | re.S,
        )
        records.append(
            _tentative_record(
                record_kind="tentative_ruling",
                case_number=case_number,
                case_style=case_style,
                hearing_date=matter_hearing_date,
                department=(
                    int(matter_department_match.group(1))
                    if matter_department_match
                    else department
                ),
                source_text=block,
                source_url=source_url,
                artifact_sha256=artifact_sha256,
                page_number=page_number,
                extra={
                    "matter_number": int(matter_match.group(1)),
                    "motion": _multiline_text(motion_match.group(1)),
                    "tentative_ruling": _multiline_text(
                        ruling_match.group(1)
                    ),
                    "explanation": (
                        _multiline_text(explanation_match.group(1))
                        if explanation_match
                        else None
                    ),
                    "issued_by_initials": (
                        issued_match.group(1).upper()
                        if issued_match
                        else None
                    ),
                    "issued_date": (
                        _parse_date(issued_match.group(2), ("%m/%d/%y",))
                        if issued_match
                        else None
                    ),
                    "oral_argument": (
                        {
                            "date": _parse_date(
                                oral_match.group(1),
                                ("%A, %B %d, %Y",),
                            ),
                            "time": _text(oral_match.group(2)),
                            "department": int(oral_match.group(3)),
                        }
                        if oral_match
                        else None
                    ),
                },
            )
        )
    return tuple(records)


def parse_probate_search_page(
    html_text: str,
    *,
    source_url: str = PROBATE_NOTES_URL,
) -> ProbateSearchPage:
    """Validate the anonymous WebForms search operation."""

    soup = BeautifulSoup(html_text, "html.parser")
    form = soup.select_one("form#notesSearchForm")
    if form is None:
        raise FresnoSourceChangedError(
            "probate_search_form_missing",
            "Fresno Probate Examiner Notes search form is missing",
        )
    if form.select_one("[name='CaseNumberTextBox']") is None:
        raise FresnoSourceChangedError(
            "probate_case_field_missing",
            "Fresno probate-note form lacks its case-number field",
        )
    if form.select_one("[name='SearchButton']") is None:
        raise FresnoSourceChangedError(
            "probate_search_button_missing",
            "Fresno probate-note form lacks its search action",
        )
    hidden = {
        str(control["name"]): str(control.get("value", ""))
        for control in form.select("input[type='hidden'][name]")
    }
    missing = [
        name for name in _PROBATE_REQUIRED_HIDDEN if not hidden.get(name)
    ]
    if missing:
        raise FresnoSourceChangedError(
            "probate_hidden_fields_changed",
            "Fresno probate-note form lacks a required transient field",
            details={"missing_fields": missing},
        )
    info_text = _text(soup.get_text(" ", strip=True)) or ""
    if "Probate Examiner Notes are not part of the official Court file" not in info_text:
        raise FresnoSourceChangedError(
            "probate_lineage_notice_changed",
            "Fresno probate-note page lacks its court-file lineage notice",
        )
    schema = _schema_fingerprint(
        {
            "form_id": "notesSearchForm",
            "query_fields": ["CaseNumberTextBox", "EventDateTextBox"],
            "hidden_field_names": sorted(hidden),
            "result_table_id": "NotesGridView",
        }
    )
    return ProbateSearchPage(
        source_url=source_url,
        hidden_fields=hidden,
        schema_fingerprint=schema,
    )


def _reviewer_from_note(note_text: str) -> str | None:
    explicit = re.search(r"\bReviewed by:\s*([A-Z]{2,6})\b", note_text, re.I)
    if explicit:
        return explicit.group(1).upper()
    dated_initials = re.search(
        r"(?:^|\n)([a-z]{2,6})\s+\d{1,2}/\d{1,2}/\d{2,4}\s*$",
        note_text,
        re.I,
    )
    return dated_initials.group(1).upper() if dated_initials else None


def parse_probate_results(
    html_text: str,
    *,
    requested_case_number: str,
    source_url: str = PROBATE_NOTES_URL,
    search_schema_fingerprint: str | None = None,
) -> ProbateResults:
    """Parse all rows or the explicit no-notes response from the application."""

    soup = BeautifulSoup(html_text, "html.parser")
    results_label = soup.select_one("#ResultsLabel")
    label_text = (
        _text(results_label.get_text(" ", strip=True))
        if results_label
        else None
    )
    no_result_pattern = re.compile(
        r"^No notes found for Case Number:\s*(\S+)\s*$",
        re.I,
    )
    no_result_match = (
        no_result_pattern.match(label_text) if label_text is not None else None
    )
    if no_result_match:
        returned_case = no_result_match.group(1)
        if returned_case.casefold() != requested_case_number.casefold():
            raise FresnoSourceChangedError(
                "probate_no_result_case_mismatch",
                "Fresno probate-note empty response names a different case",
                details={
                    "requested": requested_case_number,
                    "returned": returned_case,
                },
            )
        schema = _schema_fingerprint(
            {
                "result": "no_notes",
                "message_pattern": (
                    "No notes found for Case Number: {case_number}"
                ),
                "search_schema_fingerprint": search_schema_fingerprint,
            }
        )
        return ProbateResults(
            source_url=source_url,
            case_number=returned_case,
            case_style=None,
            date_printed=None,
            notes_found=0,
            records=(),
            no_results_message=label_text,
            schema_fingerprint=schema,
        )

    summary = soup.select_one("table#tblResults")
    notes_table = soup.select_one("table#NotesGridView")
    if summary is None or notes_table is None:
        raise FresnoSourceChangedError(
            "probate_results_missing",
            "Fresno probate-note response is neither results nor explicit no-notes",
            details={"results_label": label_text},
        )
    summary_values: dict[str, str] = {}
    for row in summary.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        label = (_text(cells[0].get_text(" ", strip=True)) or "").rstrip(":")
        value = _text(cells[1].get_text(" ", strip=True))
        if label and value:
            summary_values[label] = value
    expected_summary = {"Case Style", "Case #", "Date Printed", "Notes Found"}
    if not expected_summary.issubset(summary_values):
        raise FresnoSourceChangedError(
            "probate_summary_changed",
            "Fresno probate-note results summary changed",
            details={"observed_labels": sorted(summary_values)},
        )
    case_number = summary_values["Case #"]
    if case_number.casefold() != requested_case_number.casefold():
        raise FresnoSourceChangedError(
            "probate_result_case_mismatch",
            "Fresno probate-note response names a different case",
            details={
                "requested": requested_case_number,
                "returned": case_number,
            },
        )
    try:
        notes_found = int(summary_values["Notes Found"])
    except ValueError as error:
        raise FresnoSourceChangedError(
            "probate_count_changed",
            "Fresno probate-note summary count is not numeric",
        ) from error
    headers = [
        _text(cell.get_text(" ", strip=True)) or ""
        for cell in notes_table.select("tr:first-child th")
    ]
    expected_headers = ["Case Number", "Hearing Date", "Note"]
    if headers != expected_headers:
        raise FresnoSourceChangedError(
            "probate_headers_changed",
            "Fresno probate-note table headers changed",
            details={"expected": expected_headers, "observed": headers},
        )
    records: list[Mapping[str, Any]] = []
    for row_number, row in enumerate(notes_table.select("tr")[1:], start=1):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 3:
            raise FresnoSourceChangedError(
                "probate_row_width_changed",
                "Fresno probate-note row does not have three columns",
                details={"row_number": row_number, "columns": len(cells)},
            )
        row_case_number = _text(cells[0].get_text(" ", strip=True))
        hearing_date_raw = _text(cells[1].get_text(" ", strip=True))
        note_text = _multiline_text(
            cells[2].get_text("\n", strip=True)
        )
        if (
            row_case_number is None
            or hearing_date_raw is None
            or note_text is None
        ):
            raise FresnoSourceChangedError(
                "probate_row_empty",
                "Fresno probate-note row contains an empty required value",
                details={"row_number": row_number},
            )
        hearing_date = _parse_date(hearing_date_raw, ("%m/%d/%Y",))
        suffix = _schema_fingerprint(
            {
                "case_number": row_case_number,
                "hearing_date": hearing_date,
                "note_text": note_text,
            }
        )[:20]
        canonical_ref = (
            f"FRESNO-PROBATE-NOTE:{row_case_number}:{suffix}"
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": PROBATE_SOURCE_ID,
                "record_kind": "probate_examiner_note",
                "case_number": row_case_number,
                "case_style": summary_values["Case Style"],
                "hearing_date": hearing_date,
                "hearing_date_raw": hearing_date_raw,
                "note_text": note_text,
                "reviewer_initials": _reviewer_from_note(note_text),
                "date_printed": _parse_date(
                    summary_values["Date Printed"],
                    ("%B %d, %Y",),
                ),
                "record_lineage": (
                    "examiner_note_not_part_of_official_court_file"
                ),
                "source_url": source_url,
                "provenance": _court_provenance(
                    PROBATE_SOURCE_ID,
                    source_url,
                    response_schema_fingerprint=(
                        search_schema_fingerprint
                    ),
                ),
            }
        )
    if len(records) != notes_found:
        raise FresnoSourceChangedError(
            "probate_result_count_mismatch",
            "Fresno probate-note summary count differs from returned rows",
            details={
                "summary_count": notes_found,
                "row_count": len(records),
            },
        )
    schema = _schema_fingerprint(
        {
            "summary_labels": sorted(summary_values),
            "headers": headers,
            "search_schema_fingerprint": search_schema_fingerprint,
        }
    )
    return ProbateResults(
        source_url=source_url,
        case_number=case_number,
        case_style=summary_values["Case Style"],
        date_printed=_parse_date(
            summary_values["Date Printed"],
            ("%B %d, %Y",),
        ),
        notes_found=notes_found,
        records=tuple(records),
        no_results_message=None,
        schema_fingerprint=schema,
    )


def _sources() -> list[dict[str, Any]]:
    return [
        {
            "source_id": PORTAL_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[PORTAL_SOURCE_ID].name,
            "official_url": PORTAL_URL,
            "operations": [
                {
                    "name": "landing_and_registration_observation",
                    "command": "portal",
                    "observed_state": (
                        "landing exposes home, FAQ, registration, and login; "
                        "no anonymous case-search form is present"
                    ),
                }
            ],
            "complements": [
                CALENDAR_SOURCE_ID,
                RULINGS_SOURCE_ID,
                PROBATE_SOURCE_ID,
                INDEX_SOURCE_ID,
                RECORDS_SOURCE_ID,
            ],
        },
        {
            "source_id": CALENDAR_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[CALENDAR_SOURCE_ID].name,
            "official_url": CALENDAR_INDEX_URL,
            "operations": ["calendar-index", "calendar"],
            "contribution": (
                "Case number, party, hearing date/time/type, department, "
                "judge, status or custody, attorney, and agency identifiers"
            ),
        },
        {
            "source_id": RULINGS_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[RULINGS_SOURCE_ID].name,
            "official_url": RULINGS_INDEX_URL,
            "operations": ["rulings-index", "rulings"],
            "contribution": (
                "Case style and number, motion, tentative disposition, "
                "explanation, continuances, appearance status, and issuance"
            ),
        },
        {
            "source_id": PROBATE_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[PROBATE_SOURCE_ID].name,
            "official_url": PROBATE_NOTES_URL,
            "operations": ["probate-notes"],
            "contribution": (
                "Case style, hearing date, petition or status context, filing "
                "deficiencies, minute-order references, and examiner comments"
            ),
            "record_lineage": (
                "examiner_note_not_part_of_official_court_file"
            ),
        },
        {
            "source_id": INDEX_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[INDEX_SOURCE_ID].name,
            "official_url": CASE_INDEX_URL,
            "operations": ["alternatives"],
            "contribution": (
                "Court-ordered monthly case-index reports delivered as PDF "
                "or text by email"
            ),
        },
        {
            "source_id": RECORDS_SOURCE_ID,
            "record_kind": "source_description",
            "name": SOURCE_METADATA[RECORDS_SOURCE_ID].name,
            "official_url": ARCHIVES_URL,
            "operations": ["alternatives"],
            "contribution": (
                "Official file-copy, archive, case-contact, elevated-access, "
                "administrative-record, and appellate complement routes"
            ),
        },
    ]


def _alternatives() -> list[dict[str, Any]]:
    return [
        {
            "canonical_ref": "FRESNO-CASE-INDEX:MONTHLY-ORDER",
            "evidence_ref": "FRESNO-CASE-INDEX:MONTHLY-ORDER",
            "source_id": INDEX_SOURCE_ID,
            "record_kind": "court_data_product",
            "name": "Monthly Case Index Report",
            "official_url": CASE_INDEX_URL,
            "request_form_url": CASE_INDEX_FORM_URL,
            "delivery_formats": ["pdf", "text"],
            "delivery": "email",
            "report_categories": [
                "criminal_traffic",
                "civil_small_claims",
                "family_law",
                "probate",
            ],
            "published_fields": {
                "criminal_traffic": [
                    "case_number",
                    "case_style_or_party",
                    "offenses",
                    "case_type",
                    "filing_date",
                    "status_date",
                    "current_status",
                ],
                "civil_small_claims": [
                    "case_number",
                    "case_style_or_party",
                    "case_type",
                    "filing_date",
                    "status_date",
                    "current_status",
                ],
                "family_law": None,
                "probate": None,
            },
            "form_price": {
                "amount_usd": 70,
                "unit": "per_report_per_month",
            },
            "request_email": "CaseIndexReports@fresno.courts.ca.gov",
            "mailing_address": (
                "Accounting Department, 4th Floor, Case Index Request, "
                "1100 Van Ness Avenue, Fresno, CA 93724-0002"
            ),
            "provenance": _court_provenance(
                INDEX_SOURCE_ID,
                CASE_INDEX_URL,
            ),
        },
        {
            "canonical_ref": "FRESNO-RECORDS:ARCHIVES",
            "evidence_ref": "FRESNO-RECORDS:ARCHIVES",
            "source_id": RECORDS_SOURCE_ID,
            "record_kind": "case_record_copy_route",
            "name": "Fresno Superior Court Archives",
            "official_url": ARCHIVES_URL,
            "holdings": [
                "appellate",
                "civil_limited",
                "civil_unlimited",
                "criminal_felony",
                "criminal_misdemeanor",
                "family",
                "family_support",
                "juvenile_dependency",
                "probate",
                "small_claims",
                "traffic",
            ],
            "observed_earliest_year": 1860,
            "services": [
                "view_non_confidential_case_file",
                "copy_non_confidential_case_file",
                "certify_non_confidential_case_file",
            ],
            "facility": "1963 E Street, Fresno, CA 93706",
            "phone": "559-457-4903",
            "hours": {
                "monday_thursday": "8:00 AM-3:00 PM",
                "friday": "8:00 AM-12:00 PM",
            },
            "provenance": _court_provenance(
                RECORDS_SOURCE_ID,
                ARCHIVES_URL,
            ),
        },
        {
            "canonical_ref": "FRESNO-RECORDS:CASE-INFORMATION",
            "evidence_ref": "FRESNO-RECORDS:CASE-INFORMATION",
            "source_id": RECORDS_SOURCE_ID,
            "record_kind": "case_record_copy_route",
            "name": "Case Information and Official Record Route",
            "official_url": CASE_INFORMATION_URL,
            "official_or_certified_record_routes": ["visit_court", "write_court"],
            "civil_case_number_search_note": (
                "omit the final three letters; for example, "
                "03CECG00001SJK becomes 03CECG00001"
            ),
            "unlawful_detainer_display_note": (
                "case information is not available until 60 days after "
                "the complaint is filed"
            ),
            "elevated_access_form_url": ELEVATED_ACCESS_FORM_URL,
            "provenance": _court_provenance(
                RECORDS_SOURCE_ID,
                CASE_INFORMATION_URL,
            ),
        },
        {
            "canonical_ref": "FRESNO-CONTACT:CIVIL",
            "evidence_ref": "FRESNO-CONTACT:CIVIL",
            "source_id": RECORDS_SOURCE_ID,
            "record_kind": "case_information_contact_route",
            "case_area": "civil",
            "official_url": CIVIL_CONTACT_URL,
            "observed_fields": [
                "requester_identity_and_contact",
                "optional_date_of_birth",
                "case_number",
                "case_title",
                "question",
            ],
            "interaction": "form_submission",
            "provenance": _court_provenance(
                RECORDS_SOURCE_ID,
                CIVIL_CONTACT_URL,
            ),
        },
        {
            "canonical_ref": "FRESNO-CONTACT:CRIMINAL-TRAFFIC",
            "evidence_ref": "FRESNO-CONTACT:CRIMINAL-TRAFFIC",
            "source_id": RECORDS_SOURCE_ID,
            "record_kind": "case_information_contact_route",
            "case_area": "criminal_traffic",
            "official_url": CRIMINAL_CONTACT_URL,
            "observed_fields": [
                "requester_identity_and_contact",
                "defendant_identity",
                "defendant_date_of_birth",
                "drivers_license",
                "case_or_citation_number",
                "question",
            ],
            "observed_topic": "juvenile_traffic_status",
            "interaction": "form_submission",
            "provenance": _court_provenance(
                RECORDS_SOURCE_ID,
                CRIMINAL_CONTACT_URL,
            ),
        },
        {
            "canonical_ref": "FRESNO-RECORDS:ADMINISTRATIVE",
            "evidence_ref": "FRESNO-RECORDS:ADMINISTRATIVE",
            "source_id": RECORDS_SOURCE_ID,
            "record_kind": "administrative_record_request_route",
            "official_url": GENERAL_INFORMATION_URL,
            "request_method": "specific_written_request_by_mail",
            "addressee": "Managing Judicial Staff Attorney",
            "mailing_address": (
                "1100 Van Ness Avenue, Fresno, CA 93724-0002"
            ),
            "scope_distinction": (
                "the court page directs case-record copies to Archives or "
                "the appropriate clerk rather than this administrative route"
            ),
            "provenance": _court_provenance(
                RECORDS_SOURCE_ID,
                GENERAL_INFORMATION_URL,
            ),
        },
        {
            "canonical_ref": "CA-APPELLATE:FIFTH-DISTRICT-SEARCH",
            "evidence_ref": "CA-APPELLATE:FIFTH-DISTRICT-SEARCH",
            "source_id": RECORDS_SOURCE_ID,
            "record_kind": "appellate_case_information_complement",
            "official_url": APPELLATE_SEARCH_URL,
            "court": "California Court of Appeal, Fifth Appellate District",
            "search_fields": [
                "trial_court_case_number",
                "appellate_case_number",
                "case_name_or_party",
            ],
            "coverage_relation": (
                "appellate summaries and dockets for matters reaching the "
                "Fifth District; not a substitute for the Fresno trial docket"
            ),
            "provenance": {
                "source_url": APPELLATE_SEARCH_URL,
                "authority": "California Courts",
            },
        },
    ]


class FresnoSuperiorCourtClient:
    """Paced client for the verified Fresno court HTML, PDF, and form routes."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/pdf;q=0.9,*/*;q=0.5"
                    ),
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
        referer: str | None = None,
    ) -> Any:
        response = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                request_method = getattr(self.session, method.casefold())
                kwargs: dict[str, Any] = {
                    "timeout": self.timeout,
                    "allow_redirects": True,
                }
                if data is not None:
                    kwargs["data"] = data
                if referer is not None:
                    kwargs["headers"] = {"Referer": referer}
                response = request_method(url, **kwargs)
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise FresnoCourtError(
                        "transport_error",
                        f"Fresno court request failed: {error}",
                        category="transport",
                        retryable=True,
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if status_code == 200:
                return response
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise FresnoCourtError(
                    "rate_limited",
                    "Fresno court source returned HTTP 429",
                    status=ResultStatus.RATE_LIMITED,
                    category="transport",
                    retryable=True,
                )
            if status_code in {401, 403}:
                raise FresnoCourtError(
                    "access_response",
                    f"Fresno court source returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "status_code": status_code},
                )
            raise FresnoCourtError(
                "http_error",
                f"Fresno court source returned HTTP {status_code}",
                category="transport",
                details={"url": url, "status_code": status_code},
            )
        raise AssertionError("Fresno request ended without a response")

    def text(self, url: str) -> tuple[str, str]:
        safe_url = _official_url(url)
        response = self._request("get", safe_url)
        final_url = _official_url(str(getattr(response, "url", safe_url)))
        html_text = str(response.text)
        lowered = html_text.casefold()
        if any(marker in lowered for marker in _CHALLENGE_MARKERS):
            raise FresnoCourtError(
                "human_verification",
                "Fresno court source returned a verification page",
                status=ResultStatus.HUMAN_REQUIRED,
                category="access",
            )
        return html_text, final_url

    def portal(self) -> Mapping[str, Any]:
        home_html, home_url = self.text(PORTAL_URL)
        register_html, register_url = self.text(PORTAL_REGISTER_URL)
        return parse_portal_state(
            home_html,
            register_html,
            source_url=home_url,
            registration_url=register_url,
        )

    def calendar_index(self) -> ArtifactIndex:
        html_text, source_url = self.text(CALENDAR_INDEX_URL)
        return parse_calendar_index(html_text, source_url=source_url)

    def rulings_index(self) -> ArtifactIndex:
        html_text, source_url = self.text(RULINGS_INDEX_URL)
        return parse_rulings_index(html_text, source_url=source_url)

    def pdf(self, url: str, *, family: str) -> PDFArtifact:
        safe_url = _official_url(url, pdf_family=family)
        response = self._request("get", safe_url)
        final_url = _official_url(
            str(getattr(response, "url", safe_url)),
            pdf_family=family,
        )
        content = bytes(response.content)
        if not content.startswith(b"%PDF-"):
            raise FresnoSourceChangedError(
                "pdf_signature_missing",
                "Fresno court artifact is not a PDF",
                details={
                    "url": final_url,
                    "content_type": str(
                        getattr(response, "headers", {}).get(
                            "Content-Type",
                            "",
                        )
                    ),
                    "size_bytes": len(content),
                },
            )
        try:
            completed = subprocess.run(
                ["pdftotext", "-layout", "-", "-"],
                input=content,
                capture_output=True,
                check=True,
            )
        except FileNotFoundError as error:
            raise FresnoCourtError(
                "pdftotext_missing",
                "pdftotext is required to parse Fresno court PDF records",
                category="local_dependency",
            ) from error
        except subprocess.CalledProcessError as error:
            raise FresnoCourtError(
                "pdf_text_extraction_failed",
                "pdftotext could not extract the Fresno court artifact",
                category="document_processing",
                details={
                    "url": final_url,
                    "stderr": error.stderr.decode(
                        "utf-8",
                        errors="replace",
                    )[:1000],
                },
            ) from error
        text = completed.stdout.decode("utf-8", errors="replace")
        if not text.strip():
            raise FresnoSourceChangedError(
                "pdf_text_empty",
                "Fresno court PDF yielded no extractable text",
                details={"url": final_url},
            )
        return PDFArtifact(
            source_url=final_url,
            content=content,
            sha256=hashlib.sha256(content).hexdigest(),
            text=text,
        )

    def probate_notes(
        self,
        case_number: str,
        *,
        hearing_date: str | None = None,
    ) -> ProbateResults:
        normalized_case = case_number.strip()
        if not normalized_case:
            raise FresnoSelectionError(
                "case_number_required",
                "case number must not be empty",
            )
        normalized_hearing_date = _validate_hearing_date(hearing_date)
        search_response = self._request("get", PROBATE_NOTES_URL)
        search_url = _official_url(
            str(getattr(search_response, "url", PROBATE_NOTES_URL))
        )
        search_page = parse_probate_search_page(
            str(search_response.text),
            source_url=search_url,
        )
        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            **dict(search_page.hidden_fields),
            "CaseNumberTextBox": normalized_case,
            "EventDateTextBox": normalized_hearing_date or "",
            "EventDateTextBox_MaskedEditExtender_ClientState": "",
            "SearchButton": "Search",
        }
        result_response = self._request(
            "post",
            PROBATE_NOTES_URL,
            data=payload,
            referer=search_url,
        )
        result_url = _official_url(
            str(getattr(result_response, "url", PROBATE_NOTES_URL))
        )
        return parse_probate_results(
            str(result_response.text),
            requested_case_number=normalized_case,
            source_url=result_url,
            search_schema_fingerprint=search_page.schema_fingerprint,
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _artifact_by_selector(
    index: ArtifactIndex,
    *,
    url: str | None,
    publication_date: str | None,
    department: int | None = None,
) -> Mapping[str, Any]:
    if url is not None:
        family = "ruling" if department is not None else "calendar"
        selected_url = _official_url(
            url,
            pdf_family=family,
        )
        matches = [
            record
            for record in index.records
            if record["source_url"] == selected_url
        ]
        if matches:
            return matches[0]
        parsed_path = urlparse(selected_url).path
        if family == "calendar":
            path_match = _CALENDAR_PATH_RE.match(parsed_path)
            assert path_match is not None
            inferred_date = _parse_date(path_match.group(1), ("%m%d%Y",))
        else:
            path_match = _RULING_PATH_RE.match(parsed_path)
            assert path_match is not None
            inferred_date = _parse_date(
                "/".join(path_match.groups()[:3]),
                ("%m/%d/%y",),
            )
        return {
            "source_url": selected_url,
            "publication_date": inferred_date,
            "index_url": index.source_url,
            "currently_linked": False,
        }
    candidates = list(index.records)
    if publication_date is not None:
        normalized_date = _validate_iso_date(publication_date)
        candidates = [
            record
            for record in candidates
            if record["publication_date"] == normalized_date
        ]
    if department is not None:
        candidates = [
            record
            for record in candidates
            if int(record["department"]) == department
        ]
    if not candidates:
        raise FresnoSelectionError(
            "artifact_not_found",
            "no current Fresno court PDF matches the requested selectors",
            details={
                "publication_date": publication_date,
                "department": department,
            },
        )
    return max(candidates, key=lambda record: str(record["publication_date"]))


def _source_for_args(args: argparse.Namespace) -> SourceMetadata:
    if args.command == "portal":
        return SOURCE_METADATA[PORTAL_SOURCE_ID]
    if args.command in {"calendar-index", "calendar"}:
        return SOURCE_METADATA[CALENDAR_SOURCE_ID]
    if args.command in {"rulings-index", "rulings"}:
        return SOURCE_METADATA[RULINGS_SOURCE_ID]
    if args.command == "probate-notes":
        return SOURCE_METADATA[PROBATE_SOURCE_ID]
    if args.command == "alternatives":
        return SOURCE_METADATA[RECORDS_SOURCE_ID]
    return SOURCE_METADATA[FAMILY_SOURCE_ID]


def _query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in (
        "url",
        "date",
        "department",
        "case_number",
        "hearing_date",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = value
    return PublicRecordsQuery(
        source=_source_for_args(args),
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: FresnoCourtError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: FresnoSuperiorCourtClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _query(args)
    own_client = client is None
    source_client = client or FresnoSuperiorCourtClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                _sources(),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "portal":
            portal = source_client.portal()
            result = PublicRecordsResult.success(
                query,
                [portal],
                raw_artifact_refs=[
                    PORTAL_URL,
                    PORTAL_REGISTER_URL,
                    CMS_NOTICE_URL,
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "calendar-index":
            index = source_client.calendar_index()
            result = PublicRecordsResult.success(
                query,
                index.records,
                raw_artifact_refs=[index.source_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "calendar":
            index = source_client.calendar_index()
            artifact_record = _artifact_by_selector(
                index,
                url=args.url,
                publication_date=args.date,
            )
            artifact = source_client.pdf(
                str(artifact_record["source_url"]),
                family="calendar",
            )
            records = parse_calendar_text(
                artifact.text,
                source_url=artifact.source_url,
                artifact_sha256=artifact.sha256,
            )
            result = PublicRecordsResult.success(
                query,
                records,
                raw_artifact_refs=[
                    index.source_url,
                    artifact.source_url,
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "rulings-index":
            index = source_client.rulings_index()
            result = PublicRecordsResult.success(
                query,
                index.records,
                raw_artifact_refs=[index.source_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "rulings":
            if args.url is None and args.department is None:
                raise FresnoSelectionError(
                    "department_required",
                    "--department is required when --url is not provided",
                )
            index = source_client.rulings_index()
            selector_department = args.department
            if args.url is not None and selector_department is None:
                url_match = _RULING_PATH_RE.match(
                    urlparse(_official_url(args.url, pdf_family="ruling")).path
                )
                assert url_match is not None
                selector_department = int(url_match.group(4))
            artifact_record = _artifact_by_selector(
                index,
                url=args.url,
                publication_date=args.date,
                department=selector_department,
            )
            artifact = source_client.pdf(
                str(artifact_record["source_url"]),
                family="ruling",
            )
            records = parse_tentative_rulings_text(
                artifact.text,
                source_url=artifact.source_url,
                artifact_sha256=artifact.sha256,
            )
            result = PublicRecordsResult.success(
                query,
                records,
                raw_artifact_refs=[
                    index.source_url,
                    artifact.source_url,
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probate-notes":
            probate = source_client.probate_notes(
                args.case_number,
                hearing_date=args.hearing_date,
            )
            result = PublicRecordsResult.success(
                query,
                probate.records,
                raw_artifact_refs=[probate.source_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "alternatives":
            result = PublicRecordsResult.success(
                query,
                _alternatives(),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            portal = source_client.portal()
            calendar_index = source_client.calendar_index()
            ruling_index = source_client.rulings_index()
            latest_calendar_record = _artifact_by_selector(
                calendar_index,
                url=None,
                publication_date=None,
            )
            latest_calendar = source_client.pdf(
                str(latest_calendar_record["source_url"]),
                family="calendar",
            )
            calendar_records = parse_calendar_text(
                latest_calendar.text,
                source_url=latest_calendar.source_url,
                artifact_sha256=latest_calendar.sha256,
            )
            ruling_501 = _artifact_by_selector(
                ruling_index,
                url=None,
                publication_date=None,
                department=501,
            )
            ruling_pdf = source_client.pdf(
                str(ruling_501["source_url"]),
                family="ruling",
            )
            ruling_records = parse_tentative_rulings_text(
                ruling_pdf.text,
                source_url=ruling_pdf.source_url,
                artifact_sha256=ruling_pdf.sha256,
            )
            probate = source_client.probate_notes("19CEPR00967")
            record = {
                "canonical_ref": "FRESNO-COURT:SOURCE-PROBE",
                "evidence_ref": "FRESNO-COURT:SOURCE-PROBE",
                "source_id": FAMILY_SOURCE_ID,
                "record_kind": "source_probe",
                "portal": {
                    "anonymous_case_search_control_present": portal[
                        "anonymous_case_search_control_present"
                    ],
                    "visible_registration_field_count": len(
                        portal["registration"]["visible_fields"]
                    ),
                },
                "calendar": {
                    "index_artifact_count": len(calendar_index.records),
                    "selected_url": latest_calendar.source_url,
                    "parsed_record_count": len(calendar_records),
                    "sha256": latest_calendar.sha256,
                },
                "tentative_rulings": {
                    "index_artifact_count": len(ruling_index.records),
                    "departments": sorted(
                        {
                            int(item["department"])
                            for item in ruling_index.records
                        }
                    ),
                    "selected_url": ruling_pdf.source_url,
                    "parsed_record_count": len(ruling_records),
                    "sha256": ruling_pdf.sha256,
                },
                "probate_examiner_notes": {
                    "case_number": probate.case_number,
                    "case_style": probate.case_style,
                    "date_printed": probate.date_printed,
                    "parsed_record_count": len(probate.records),
                    "result_schema_fingerprint": (
                        probate.schema_fingerprint
                    ),
                },
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[
                    PORTAL_URL,
                    PORTAL_REGISTER_URL,
                    calendar_index.source_url,
                    latest_calendar.source_url,
                    ruling_index.source_url,
                    ruling_pdf.source_url,
                    probate.source_url,
                ],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise FresnoSelectionError(
                "unknown_command",
                f"unknown Fresno court command: {args.command}",
            )
    except FresnoCourtError as error:
        result = _failure(query, error)
    finally:
        if own_client:
            source_client.close()
    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(
            canonical_json(result.query.to_dict()),
            result.query.source.source_id,
            result_count,
        )
    return result


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Fresno court calendars, tentative rulings, probate notes, "
            "and official alternatives"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe each Fresno court source and its contribution",
    )
    _add_runtime_and_output(sources)

    portal = subparsers.add_parser(
        "portal",
        help="Inspect the current e-Court landing and registration controls",
    )
    _add_runtime_and_output(portal)

    calendar_index = subparsers.add_parser(
        "calendar-index",
        help="List every daily calendar PDF on the current court page",
    )
    _add_runtime_and_output(calendar_index)

    calendar = subparsers.add_parser(
        "calendar",
        help="Parse every hearing row from one current daily-calendar PDF",
    )
    calendar.add_argument("--url")
    calendar.add_argument("--date", help="Publication date in YYYY-MM-DD")
    _add_runtime_and_output(calendar)

    rulings_index = subparsers.add_parser(
        "rulings-index",
        help="List every tentative-ruling PDF on the current court page",
    )
    _add_runtime_and_output(rulings_index)

    rulings = subparsers.add_parser(
        "rulings",
        help="Parse all case entries from one current tentative-ruling PDF",
    )
    rulings.add_argument("--url")
    rulings.add_argument("--department", type=int)
    rulings.add_argument("--date", help="Publication date in YYYY-MM-DD")
    _add_runtime_and_output(rulings)

    probate = subparsers.add_parser(
        "probate-notes",
        help="Search and return all Probate Examiner Notes for one case",
    )
    probate.add_argument("--case-number", required=True)
    probate.add_argument(
        "--hearing-date",
        help="Optional exact hearing date in MM/DD/YYYY",
    )
    _add_runtime_and_output(probate)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="Describe case-index, copy, archive, contact, and appellate routes",
    )
    _add_runtime_and_output(alternatives)

    probe = subparsers.add_parser(
        "probe",
        help="Verify all anonymous data operations and the portal observation",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Fresno Superior Court {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Fresno Superior Court {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("case_number")
            or record.get("publication_date")
            or record.get("name")
            or record.get("record_kind")
            or "?"
        )
        print(f"  {label} | {record.get('source_url') or record.get('official_url') or '?'}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        raise SystemExit("--max-attempts must be positive")
    if args.retry_backoff < 0:
        raise SystemExit("--retry-backoff must not be negative")
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
