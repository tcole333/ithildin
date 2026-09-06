#!/usr/bin/env python3
"""Query Maryland's statewide Register of Wills estate index.

The official RowNet application exposes decedent and personal-representative
searches, estate status and type, party observations, and estate docket
history. It is an ASP.NET WebForms application, so this adapter discovers form
fields and pager postback targets from each response and reconstructs a fresh
session when a continuation cursor is resumed.

Examples:
    uv run python tools/query_md_estate_search.py decedent Novak \
        --first-name Patricia --county "Baltimore County" --output /tmp/md.json
    uv run python tools/query_md_estate_search.py representative Novak
    uv run python tools/query_md_estate_search.py estate 238438 \
        --county "Baltimore County"
    uv run python tools/query_md_estate_search.py detail 1868548158
    uv run python tools/query_md_estate_search.py routes --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

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
        sha256_fingerprint,
        utc_now_iso,
    )
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
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
        sha256_fingerprint,
        utc_now_iso,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-md-estate-search"
STATE_CODE = "MD"
STATE_GEOID = "24"

AGREEMENT_URL = "https://registers.maryland.gov/main/search.html"
SEARCH_URL = (
    "https://registers.maryland.gov/RowNetWeb/Estates/"
    "frmEstateSearch2.aspx"
)
DETAIL_URL = (
    "https://registers.maryland.gov/RowNetWeb/Estates/"
    "frmDocketImages.aspx"
)
GLOSSARY_URL = "https://registers.maryland.gov/main/searchterms.html"
FAQ_URL = "https://registers.maryland.gov/main/searchfaq.html"
DIRECTORY_URL = "https://registers.maryland.gov/main/directory.html"
LEGAL_NOTICE_URL = (
    "https://registers.maryland.gov/LegalNotice/Notices/NoticeSearch.aspx"
)
CLAIM_SEARCH_URL = (
    "https://registers.maryland.gov/RowNetWeb/Claims/frmClaimSearch.aspx"
)
CASE_SEARCH_URL = "https://casesearch.mdcourts.gov/casesearch/"
MDEC_PUBLIC_CASES_URL = "https://www.mdcourts.gov/mdec/publiccases"
JUDGMENT_LIENS_URL = (
    "https://jportal.mdcourts.gov/judgment/judgementSearch.jsf"
)
MDLANDREC_URL = "https://mdlandrec.net/"
SDAT_PROPERTY_URL = (
    "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
)
CIRCUIT_COURTS_URL = "https://www.mdcourts.gov/circuit"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_LIMIT = 100
DEFAULT_MAX_PAGE_BYTES = 5 * 1024 * 1024
NATIVE_PAGE_SIZE = 20
CURSOR_PREFIX = "md-estate:v1:"
CURSOR_VERSION = 1
OUTPUT_SCHEMA_VERSION = "maryland-estate-search/1.0"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

EXPECTED_RESULT_HEADERS = (
    "County",
    "Estate Number",
    "Filing Date",
    "Date of Death",
    "Type",
    "Status",
    "Name",
)
EXPECTED_DOCKET_HEADERS = (
    "Filed On",
    "Docket#",
    "Code",
    "Description",
    "Page(s)",
    "Request Copy?",
)
FORM_IDS = {
    "estate_number": "txtEstateNo",
    "last_name": "txtLN",
    "first_name": "txtFN",
    "middle_name": "txtMN",
    "exact_last_name": "chkExactMatchLastName",
    "county": "cboCountyId",
    "status": "cboStatus",
    "estate_type": "cboType",
    "filed_from": "DateOfFilingFrom",
    "filed_to": "DateOfFilingTo",
    "filing_date": "txtDOF",
    "party_type": "cboPartyType",
    "submit": "cmdSearch",
}
ESTATE_TYPES = {
    "FP": "Foreign Proceeding",
    "LO": "Limited Order",
    "MA": "Modified Administration",
    "MV": "Motor Vehicle",
    "NP": "NonProbate",
    "RE": "Regular Estate",
    "RJ": "Regular Estate Judicial",
    "SE": "Small Estate",
    "SJ": "Small Estate Judicial",
    "UN": "Unprobated Will Only",
}
STATUS_CODES = {
    "ARCHIV": "Archived",
    "CLOSED": "Closed",
    "OPEN": "Open",
    "PENDIN": "Pending",
}
PROBE_ESTATE_NUMBER = "238438"
PROBE_COUNTY = "Baltimore County"
REFRESH_RE = re.compile(
    r"(?P<stamp>\d{1,2}/\d{1,2}/\d{4}\s+"
    r"\d{1,2}:\d{2}:\d{2}\s+[AP]M)"
    r"(?:\s*\((?P<instance>[^)]+)\))?",
    re.I,
)
STATUS_RE = re.compile(
    r"Viewing\s+Page\s+(?P<page>[\d,]+)\s+of\s+"
    r"(?P<pages>[\d,]+)\s*\((?P<total>[\d,]+)\s+"
    r"RECORDS?\s+TOTAL\)",
    re.I,
)
NO_RESULTS_RE = re.compile(
    r"Search\s+Criteria\s+Returned\s+No\s+Results", re.I
)
POSTBACK_RE = re.compile(
    r"__doPostBack\(\s*['\"](?P<target>[^'\"]+)['\"]\s*,\s*"
    r"['\"](?P<argument>[^'\"]*)['\"]\s*\)",
    re.I,
)
RECORD_ID_RE = re.compile(r"^\d+$")


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Maryland Register of Wills Estate Search",
    source_role="statewide_estate_case_party_and_docket_index",
    base_url=AGREEMENT_URL,
    dataset_id="rownet-estates",
    metadata={
        "authority": "Maryland Registers of Wills",
        "coverage": "all Maryland counties and Baltimore City",
        "update_frequency": "daily",
        "native_page_size": NATIVE_PAGE_SIZE,
        "platform_family": "aspnet_webforms",
        "stable_join_keys": [
            "county",
            "estate_number",
            "decedent_name",
            "date_of_death",
            "personal_representative_name",
            "filing_date",
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Maryland",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "This is a statewide electronic estate index; the Register of Wills "
    "states that the official office file controls if the index differs.",
    "The source publishes a daily data timestamp. Continuation cursors bind "
    "to that timestamp and are invalid after the source refreshes.",
    "A personal-representative search returns the estate's decedent in the "
    "result Name column; fetch detail to inspect the published representative.",
    "Coverage before 1998 varies by jurisdiction, while newer statewide "
    "records are generally represented.",
)

RELATED_ROUTES: tuple[Mapping[str, Any], ...] = (
    {
        "source_id": SOURCE_ID,
        "name": "Maryland Register of Wills Estate Search",
        "url": AGREEMENT_URL,
        "record_role": "estate_case_party_status_and_docket_index",
        "adds": (
            "estate number, decedent, dates, type, status, aliases, personal "
            "representatives, attorneys, and docket history"
        ),
        "join_keys": [
            "county",
            "estate_number",
            "decedent_name",
            "date_of_death",
        ],
    },
    {
        "source_id": "us-md-register-of-wills-offices",
        "name": "Maryland Register of Wills Office Directory",
        "url": DIRECTORY_URL,
        "record_role": "official_estate_file_and_copy_route",
        "adds": (
            "office contact and retrieval route for filed instruments, "
            "certified copies, and older or differently indexed estate files"
        ),
        "join_keys": ["county", "estate_number", "decedent_name"],
    },
    {
        "source_id": "us-md-estate-legal-notices",
        "name": "Maryland Register of Wills Legal Notices",
        "url": LEGAL_NOTICE_URL,
        "record_role": "estate_publication_and_creditor_notice",
        "adds": "published estate notices and notice dates",
        "join_keys": [
            "county",
            "estate_number",
            "decedent_name",
            "personal_representative_name",
        ],
    },
    {
        "source_id": "us-md-estate-claims",
        "name": "Maryland Register of Wills Claim Search",
        "url": CLAIM_SEARCH_URL,
        "record_role": "estate_claim_index",
        "adds": "claims filed against an estate",
        "join_keys": ["county", "estate_number", "claimant_name"],
    },
    {
        "source_id": "us-md-case-search",
        "name": "Maryland Judiciary Case Search",
        "url": CASE_SEARCH_URL,
        "record_role": "related_trial_court_case_index",
        "adds": "related civil, criminal, and appellate case parties and events",
        "join_keys": [
            "party_name",
            "county",
            "case_number",
            "filing_date",
        ],
    },
    {
        "source_id": "us-md-mdec-public-cases",
        "name": "Maryland MDEC Public Case Search",
        "url": MDEC_PUBLIC_CASES_URL,
        "record_role": "recent_public_case_filing_discovery",
        "adds": "rolling public case creations and published party observations",
        "join_keys": ["party_name", "county", "case_number", "filing_date"],
    },
    {
        "source_id": "us-md-judgment-liens",
        "name": "Maryland Judgment and Liens Search",
        "url": JUDGMENT_LIENS_URL,
        "record_role": "judgment_and_lien_index",
        "adds": "circuit-court judgments or liens involving an estate party",
        "join_keys": ["party_name", "county", "case_number", "entry_date"],
    },
    {
        "source_id": "us-md-land-records",
        "name": "Maryland Land Records / MDLandRec",
        "url": MDLANDREC_URL,
        "record_role": "estate_real_property_instruments",
        "adds": "deeds, mortgages, releases, and estate-related instruments",
        "join_keys": [
            "decedent_name",
            "personal_representative_name",
            "county",
            "property_address",
            "liber_folio",
        ],
    },
    {
        "source_id": "us-md-sdat-real-property",
        "name": "Maryland SDAT Real Property",
        "url": SDAT_PROPERTY_URL,
        "record_role": "parcel_assessment_and_deed_reference",
        "adds": "parcel identity, situs, owner display, assessment, and deed links",
        "join_keys": [
            "owner_name",
            "county",
            "property_address",
            "liber_folio",
        ],
    },
    {
        "source_id": "us-md-circuit-clerk-records",
        "name": "Maryland Circuit Court Clerks",
        "url": CIRCUIT_COURTS_URL,
        "record_role": "related_circuit_case_file",
        "adds": "underlying filings when an estate intersects separate litigation",
        "join_keys": ["party_name", "county", "case_number"],
    },
)


class MarylandEstateError(RuntimeError):
    """Source error with explicit public-record result semantics."""

    status = ResultStatus.UNAVAILABLE
    category = "source"
    retryable = False
    code = "maryland_estate_error"

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        details = dict(self.details)
        if self.url:
            details["url"] = _stable_url(self.url)
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=details,
        )


class MarylandEstateSelectionError(MarylandEstateError):
    category = "query"
    code = "invalid_selection"


class MarylandEstateTransportError(MarylandEstateError):
    category = "transport"
    retryable = True
    code = "transport_error"


class MarylandEstateRestrictedError(MarylandEstateError):
    status = ResultStatus.RESTRICTED
    category = "access"
    code = "access_restricted"


class MarylandEstateRateLimitedError(MarylandEstateError):
    status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True
    code = "rate_limited"


class MarylandEstateSourceChangedError(MarylandEstateError):
    status = ResultStatus.SOURCE_CHANGED
    category = "schema"
    code = "source_changed"


class MarylandEstateSourceResponseError(MarylandEstateError):
    category = "source_response"
    code = "source_response_error"


class MarylandEstateCursorError(MarylandEstateError):
    category = "cursor"
    code = "stale_or_invalid_cursor"


@dataclass(frozen=True)
class RefreshMarker:
    raw: str
    timestamp: str
    instance: str | None


@dataclass(frozen=True)
class SearchFormState:
    html: str
    url: str
    action_url: str
    hidden_fields: Mapping[str, str]
    field_names: Mapping[str, str]
    county_values: Mapping[str, str]
    status_values: Mapping[str, str]
    type_values: Mapping[str, str]
    party_values: Mapping[str, str]
    refresh: RefreshMarker
    schema_fingerprint: str


@dataclass(frozen=True)
class SearchCriteria:
    operation: str
    estate_number: str | None = None
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    exact_last_name: bool = False
    county: str | None = None
    status: str | None = None
    estate_type: str | None = None
    filed_from: str | None = None
    filed_to: str | None = None
    filing_date: str | None = None

    def __post_init__(self) -> None:
        if self.operation not in {"decedent", "representative", "estate"}:
            raise MarylandEstateSelectionError(
                f"Unsupported estate search operation: {self.operation}"
            )
        if self.operation == "estate":
            if not _clean(self.estate_number):
                raise MarylandEstateSelectionError(
                    "Estate-number search requires an estate number"
                )
            if any(
                _clean(value)
                for value in (
                    self.last_name,
                    self.first_name,
                    self.middle_name,
                )
            ):
                raise MarylandEstateSelectionError(
                    "Estate-number and party-name criteria cannot be combined"
                )
        elif not _clean(self.last_name):
            raise MarylandEstateSelectionError(
                f"{self.operation} search requires a last name"
            )
        if self.exact_last_name and self.operation == "estate":
            raise MarylandEstateSelectionError(
                "Exact-last-name does not apply to estate-number searches"
            )
        if self.filing_date and (self.filed_from or self.filed_to):
            raise MarylandEstateSelectionError(
                "Use an exact filing date or a filing-date range, not both"
            )
        for value in (self.filed_from, self.filed_to, self.filing_date):
            if value:
                try:
                    date.fromisoformat(value)
                except ValueError as exc:
                    raise MarylandEstateSelectionError(
                        "Filing dates must use YYYY-MM-DD"
                    ) from exc
        if self.filed_from and self.filed_to:
            if self.filed_from > self.filed_to:
                raise MarylandEstateSelectionError(
                    "Filing-date start cannot be after filing-date end"
                )

    @property
    def party_type(self) -> str:
        if self.operation == "representative":
            return "Personal Representative"
        return "Decedent"

    def parameters(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "operation": self.operation,
                "estate_number": _clean(self.estate_number),
                "last_name": _clean(self.last_name),
                "first_name": _clean(self.first_name),
                "middle_name": _clean(self.middle_name),
                "exact_last_name": self.exact_last_name,
                "county": _clean(self.county),
                "status": _clean(self.status),
                "estate_type": _clean(self.estate_type),
                "filed_from": self.filed_from,
                "filed_to": self.filed_to,
                "filing_date": self.filing_date,
                "party_type": self.party_type,
            }.items()
            if value not in {None, "", False}
        }

    def form_data(self, form: SearchFormState) -> dict[str, str]:
        data = dict(form.hidden_fields)
        data["__EVENTTARGET"] = ""
        data["__EVENTARGUMENT"] = ""
        values = {
            "estate_number": _clean(self.estate_number) or "",
            "last_name": _clean(self.last_name) or "",
            "first_name": _clean(self.first_name) or "",
            "middle_name": _clean(self.middle_name) or "",
            "county": _resolve_option(
                self.county, form.county_values, "county"
            ),
            "status": _resolve_option(
                self.status, form.status_values, "status"
            ),
            "estate_type": _resolve_option(
                self.estate_type, form.type_values, "estate type"
            ),
            "filed_from": _source_date(self.filed_from),
            "filed_to": _source_date(self.filed_to),
            "filing_date": _source_date(self.filing_date),
            "party_type": _resolve_option(
                self.party_type, form.party_values, "party type"
            ),
            "submit": "Search",
        }
        for semantic, value in values.items():
            data[form.field_names[semantic]] = value
        if self.exact_last_name:
            data[form.field_names["exact_last_name"]] = "on"
        else:
            data.pop(form.field_names["exact_last_name"], None)
        return data


@dataclass(frozen=True)
class SearchRow:
    county: str
    estate_number: str
    filing_date_raw: str | None
    death_date_raw: str | None
    estate_type: str | None
    estate_status: str | None
    decedent_name: str
    record_id: str
    detail_url: str
    source_page: int


@dataclass(frozen=True)
class ResultsPage:
    html: str
    url: str
    action_url: str
    hidden_fields: Mapping[str, str]
    current_page: int
    total_pages: int
    total_count: int
    rows: tuple[SearchRow, ...]
    page_targets: Mapping[int, str]
    forward_target: str | None
    refresh: RefreshMarker
    schema_fingerprint: str


@dataclass(frozen=True)
class DetailPage:
    records: tuple[Mapping[str, Any], ...]
    url: str
    refresh: RefreshMarker
    schema_fingerprint: str


@dataclass(frozen=True)
class CursorState:
    criteria_fingerprint: str
    result_schema_fingerprint: str
    refresh_raw: str
    refresh_timestamp: str
    total_count: int
    total_pages: int
    page_number: int
    row_offset: int
    emitted_count: int


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Tag):
        text = value.get_text(" ", strip=True)
    else:
        text = str(value)
    normalized = " ".join(text.replace("\xa0", " ").split())
    return normalized or None


def _stable_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(sorted(parse_qs(parts.query).items()), doseq=True),
            "",
        )
    )


def _official_url(base_url: str, candidate: str) -> str:
    resolved = urljoin(base_url, candidate)
    parts = urlsplit(resolved)
    if parts.scheme != "https" or parts.hostname != "registers.maryland.gov":
        raise MarylandEstateSourceChangedError(
            "Maryland estate form points outside the verified official host",
            url=resolved,
        )
    if not parts.path.casefold().startswith("/rownetweb/"):
        raise MarylandEstateSourceChangedError(
            "Maryland estate form action changed outside RowNet",
            url=resolved,
        )
    return resolved


def _source_date(value: str | None) -> str:
    if not value:
        return ""
    return date.fromisoformat(value).strftime("%m/%d/%Y")


def _parse_date(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
        if fmt == "%m/%d/%y":
            year = int(cleaned.rsplit("/", 1)[1])
            parsed = parsed.replace(
                year=(2000 + year if year <= 29 else 1900 + year)
            )
        return parsed.isoformat()
    return None


def _refresh_marker(soup: BeautifulSoup, *, url: str) -> RefreshMarker:
    node = soup.select_one("#lblLatestDataDateTime")
    raw = _clean(node)
    match = REFRESH_RE.search(raw or "")
    if not match:
        raise MarylandEstateSourceChangedError(
            "Maryland estate data-refresh marker is missing or changed",
            url=url,
            details={"observed": raw},
        )
    local = datetime.strptime(
        match.group("stamp"), "%m/%d/%Y %I:%M:%S %p"
    ).replace(tzinfo=ZoneInfo("America/New_York"))
    timestamp = local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return RefreshMarker(
        raw=raw or match.group(0),
        timestamp=timestamp,
        instance=_clean(match.group("instance")),
    )


def _form(soup: BeautifulSoup, *, url: str) -> Tag:
    form = soup.select_one("form#form1") or soup.find("form")
    if not isinstance(form, Tag):
        raise MarylandEstateSourceChangedError(
            "Maryland estate WebForms form is missing", url=url
        )
    return form


def _hidden_fields(form: Tag) -> dict[str, str]:
    return {
        str(node["name"]): str(node.get("value", ""))
        for node in form.select("input[type='hidden'][name]")
    }


def _field_name(form: Tag, element_id: str, *, url: str) -> str:
    node = form.find(id=element_id)
    if not isinstance(node, Tag) or not node.get("name"):
        raise MarylandEstateSourceChangedError(
            f"Maryland estate form field {element_id} is missing",
            url=url,
        )
    return str(node["name"])


def _select_values(
    form: Tag, element_id: str, *, url: str
) -> dict[str, str]:
    node = form.find(id=element_id)
    if not isinstance(node, Tag):
        raise MarylandEstateSourceChangedError(
            f"Maryland estate select {element_id} is missing", url=url
        )
    values: dict[str, str] = {}
    for option in node.find_all("option"):
        value = str(option.get("value", "")).strip()
        label = _clean(option) or ""
        if value or label:
            values[label.casefold()] = value
            if value:
                values[value.casefold()] = value
    return values


def _resolve_option(
    value: str | None,
    options: Mapping[str, str],
    label: str,
) -> str:
    cleaned = _clean(value)
    if not cleaned:
        return ""
    resolved = options.get(cleaned.casefold())
    if resolved is None:
        raise MarylandEstateSelectionError(
            f"Unknown Maryland estate {label}: {cleaned}",
            details={
                "selection": cleaned,
                "available": sorted(
                    key for key in options if not key.isdigit()
                ),
            },
        )
    return resolved


def _canonical_county_name(value: str) -> str:
    cleaned = _clean(value) or ""
    if cleaned.casefold() == "baltimore city":
        return "Baltimore City"
    if cleaned.casefold().endswith(" county"):
        return cleaned
    return f"{cleaned} County"


def parse_search_form(
    html: str, page_url: str = SEARCH_URL
) -> SearchFormState:
    """Discover the live WebForms search contract."""

    safe_url = _official_url(SEARCH_URL, page_url)
    soup = BeautifulSoup(html, "html.parser")
    form = _form(soup, url=safe_url)
    action_url = _official_url(
        safe_url, str(form.get("action") or SEARCH_URL)
    )
    hidden = _hidden_fields(form)
    for required in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        if required not in hidden:
            raise MarylandEstateSourceChangedError(
                f"Maryland estate form is missing {required}", url=safe_url
            )
    field_names = {
        semantic: _field_name(form, element_id, url=safe_url)
        for semantic, element_id in FORM_IDS.items()
    }
    counties = _select_values(form, FORM_IDS["county"], url=safe_url)
    for label, value in list(counties.items()):
        if (
            label
            and not label.isdigit()
            and label != "baltimore city"
            and not label.endswith(" county")
        ):
            counties[f"{label} county"] = value
    statuses = _select_values(form, FORM_IDS["status"], url=safe_url)
    types = _select_values(form, FORM_IDS["estate_type"], url=safe_url)
    parties = _select_values(form, FORM_IDS["party_type"], url=safe_url)
    if len(set(value for value in counties.values() if value)) != 24:
        raise MarylandEstateSourceChangedError(
            "Maryland estate county selector no longer exposes 24 jurisdictions",
            url=safe_url,
            details={"observed_count": len(set(counties.values()) - {""})},
        )
    if not set(STATUS_CODES).issubset(set(statuses.values())):
        raise MarylandEstateSourceChangedError(
            "Maryland estate status values changed",
            url=safe_url,
            details={"observed_values": sorted(set(statuses.values()))},
        )
    if not set(ESTATE_TYPES).issubset(set(types.values())):
        raise MarylandEstateSourceChangedError(
            "Maryland estate type values changed",
            url=safe_url,
            details={"observed_values": sorted(set(types.values()))},
        )
    if not {"Decedent", "Personal Representative"}.issubset(
        set(parties.values())
    ):
        raise MarylandEstateSourceChangedError(
            "Maryland estate party-role values changed",
            url=safe_url,
            details={"observed_values": sorted(set(parties.values()))},
        )
    refresh = _refresh_marker(soup, url=safe_url)
    declared = {
        "form_field_ids": FORM_IDS,
        "field_names": field_names,
        "county_values": sorted(set(counties.values())),
        "status_values": sorted(set(statuses.values())),
        "type_values": sorted(set(types.values())),
        "party_values": sorted(set(parties.values())),
        "hidden_fields": sorted(hidden),
    }
    return SearchFormState(
        html=html,
        url=safe_url,
        action_url=action_url,
        hidden_fields=hidden,
        field_names=field_names,
        county_values=counties,
        status_values=statuses,
        type_values=types,
        party_values=parties,
        refresh=refresh,
        schema_fingerprint=sha256_fingerprint(declared),
    )


def _postback_target(href: str, *, url: str) -> str:
    match = POSTBACK_RE.search(href)
    if not match:
        raise MarylandEstateSourceChangedError(
            "Maryland estate pager postback changed",
            url=url,
            details={"href": href},
        )
    return match.group("target")


def _record_id(href: str, *, page_url: str) -> tuple[str, str]:
    detail_url = _official_url(page_url, href)
    values = parse_qs(urlsplit(detail_url).query)
    record_id = _clean((values.get("RecordId") or [None])[0])
    if not record_id or not RECORD_ID_RE.fullmatch(record_id):
        raise MarylandEstateSourceChangedError(
            "Maryland estate result link lacks a numeric RecordId",
            url=detail_url,
        )
    return record_id, detail_url


def parse_results_page(html: str, page_url: str = SEARCH_URL) -> ResultsPage:
    """Parse one authoritative result page and its dynamic pager targets."""

    safe_url = _official_url(SEARCH_URL, page_url)
    soup = BeautifulSoup(html, "html.parser")
    form = _form(soup, url=safe_url)
    action_url = _official_url(
        safe_url, str(form.get("action") or SEARCH_URL)
    )
    hidden = _hidden_fields(form)
    refresh = _refresh_marker(soup, url=safe_url)
    status_text = _clean(soup.select_one("#tblStatus")) or ""
    if NO_RESULTS_RE.search(status_text):
        if soup.select_one("#dgSearchResults") is not None:
            populated = soup.select_one("#dgSearchResults td a[href*='RecordId']")
            if populated is not None:
                raise MarylandEstateSourceChangedError(
                    "Maryland estate page reports no results with result rows",
                    url=safe_url,
                )
        return ResultsPage(
            html=html,
            url=safe_url,
            action_url=action_url,
            hidden_fields=hidden,
            current_page=1,
            total_pages=0,
            total_count=0,
            rows=(),
            page_targets={},
            forward_target=None,
            refresh=refresh,
            schema_fingerprint=sha256_fingerprint(
                {
                    "headers": EXPECTED_RESULT_HEADERS,
                    "pager": "aspnet_gridview_dynamic_postback",
                    "valid_empty": True,
                }
            ),
        )
    status_match = STATUS_RE.search(status_text)
    if not status_match:
        raise MarylandEstateSourceChangedError(
            "Maryland estate result-count banner changed",
            url=safe_url,
            details={"observed": status_text},
        )
    current_page = int(status_match.group("page").replace(",", ""))
    total_pages = int(status_match.group("pages").replace(",", ""))
    total_count = int(status_match.group("total").replace(",", ""))
    if total_pages != math.ceil(total_count / NATIVE_PAGE_SIZE):
        raise MarylandEstateSourceChangedError(
            "Maryland estate result page count conflicts with the native page size",
            url=safe_url,
            details={
                "total_count": total_count,
                "total_pages": total_pages,
                "native_page_size": NATIVE_PAGE_SIZE,
            },
        )
    table = soup.select_one("#dgSearchResults")
    if not isinstance(table, Tag):
        raise MarylandEstateSourceChangedError(
            "Maryland estate result table is missing", url=safe_url
        )
    header_seen = False
    rows: list[SearchRow] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        values = tuple(_clean(cell) or "" for cell in cells)
        if values == EXPECTED_RESULT_HEADERS:
            header_seen = True
            continue
        link = row.select_one("a[href*='RecordId']")
        if link is None:
            continue
        if len(cells) != len(EXPECTED_RESULT_HEADERS):
            raise MarylandEstateSourceChangedError(
                "Maryland estate result row width changed",
                url=safe_url,
                details={"observed_cell_count": len(cells)},
            )
        record_id, detail_url = _record_id(
            str(link.get("href", "")), page_url=safe_url
        )
        county, estate_number, filed, death, estate_type, status, name = values
        if not county or not estate_number or not name:
            raise MarylandEstateSourceChangedError(
                "Maryland estate result row is missing its case identity",
                url=safe_url,
                details={"record_id": record_id},
            )
        rows.append(
            SearchRow(
                county=county,
                estate_number=estate_number,
                filing_date_raw=filed or None,
                death_date_raw=death or None,
                estate_type=estate_type or None,
                estate_status=status or None,
                decedent_name=name,
                record_id=record_id,
                detail_url=detail_url,
                source_page=current_page,
            )
        )
    if not header_seen:
        raise MarylandEstateSourceChangedError(
            "Maryland estate result columns changed",
            url=safe_url,
            details={"expected_headers": list(EXPECTED_RESULT_HEADERS)},
        )
    expected_rows = min(
        NATIVE_PAGE_SIZE,
        total_count - ((current_page - 1) * NATIVE_PAGE_SIZE),
    )
    if len(rows) != expected_rows:
        raise MarylandEstateSourceChangedError(
            "Maryland estate page row count conflicts with its result banner",
            url=safe_url,
            details={
                "current_page": current_page,
                "expected_rows": expected_rows,
                "observed_rows": len(rows),
            },
        )
    page_targets: dict[int, str] = {}
    ellipsis_targets: list[str] = []
    for link in table.select("a[href*='__doPostBack']"):
        label = _clean(link) or ""
        target = _postback_target(str(link.get("href", "")), url=safe_url)
        if label.isdigit():
            page_targets[int(label)] = target
        elif label == "...":
            ellipsis_targets.append(target)
    declared = {
        "headers": EXPECTED_RESULT_HEADERS,
        "row_fields": list(SearchRow.__dataclass_fields__),
        "pager": "aspnet_gridview_dynamic_postback",
    }
    return ResultsPage(
        html=html,
        url=safe_url,
        action_url=action_url,
        hidden_fields=hidden,
        current_page=current_page,
        total_pages=total_pages,
        total_count=total_count,
        rows=tuple(rows),
        page_targets=page_targets,
        forward_target=ellipsis_targets[-1] if ellipsis_targets else None,
        refresh=refresh,
        schema_fingerprint=sha256_fingerprint(declared),
    )


def _county_court_id(county: str) -> str:
    county = _canonical_county_name(county)
    return "MD-ESTATE-" + re.sub(
        r"[^A-Z0-9]+", "-", county.upper()
    ).strip("-")


def _case_ref(county: str, estate_number: str) -> str:
    return canonical_court_ref(
        SOURCE_ID,
        _county_court_id(county),
        estate_number,
        "estate_case",
    )


def normalize_search_row(
    row: SearchRow,
    *,
    criteria: SearchCriteria,
    refresh: RefreshMarker,
    schema_fingerprint: str,
) -> dict[str, Any]:
    county = _canonical_county_name(row.county)
    case_ref = _case_ref(county, row.estate_number)
    return {
        "source_id": SOURCE_ID,
        "record_kind": "estate_case_index",
        "canonical_ref": case_ref,
        "evidence_ref": case_ref,
        "canonical_case_ref": case_ref,
        "source_internal_id": row.record_id,
        "record_id": row.record_id,
        "county": county,
        "county_raw": row.county,
        "court_id": _county_court_id(county),
        "estate_number": row.estate_number,
        "filing_date_raw": row.filing_date_raw,
        "filing_date": _parse_date(row.filing_date_raw),
        "date_of_death_raw": row.death_date_raw,
        "date_of_death": _parse_date(row.death_date_raw),
        "estate_type": row.estate_type,
        "estate_type_description": ESTATE_TYPES.get(
            row.estate_type or ""
        ),
        "estate_status": row.estate_status,
        "decedent_name": row.decedent_name,
        "queried_party_role": criteria.party_type,
        "searched_name": {
            "last": _clean(criteria.last_name),
            "first": _clean(criteria.first_name),
            "middle": _clean(criteria.middle_name),
            "exact_last_name": criteria.exact_last_name,
        },
        "stable_key_fields": ["county", "estate_number"],
        "join_keys": {
            "estate": {
                "county": county,
                "estate_number": row.estate_number,
            },
            "person": {
                "decedent_name": row.decedent_name,
                "date_of_death": _parse_date(row.death_date_raw),
            },
            "court_and_property": {
                "county": county,
                "decedent_name": row.decedent_name,
            },
        },
        "source_snapshot": {
            "latest_data_raw": refresh.raw,
            "latest_data_at": refresh.timestamp,
            "application_instance": refresh.instance,
            "update_frequency": "daily",
        },
        "source_page": row.source_page,
        "source_url": row.detail_url,
        "search_url": AGREEMENT_URL,
        "response_schema_fingerprint": schema_fingerprint,
    }


def _detail_fields(table: Tag, *, url: str) -> dict[str, str | None]:
    fields: dict[str, str | None] = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        for index in range(0, len(cells) - 1, 2):
            label = (_clean(cells[index]) or "").rstrip(":").strip()
            if label:
                fields[label] = _clean(cells[index + 1])
    required = {"Estate Number", "Type", "Status", "Decedent Name"}
    if not required.issubset(fields):
        raise MarylandEstateSourceChangedError(
            "Maryland estate detail labels changed",
            url=url,
            details={"missing_labels": sorted(required - fields.keys())},
        )
    return fields


def _line_values(node: Tag | None) -> list[str]:
    if not isinstance(node, Tag):
        return []
    values: list[str] = []
    current: list[str] = []
    for child in node.children:
        if isinstance(child, Tag) and child.name == "br":
            value = _clean("".join(current))
            if value:
                values.append(value)
            current = []
            continue
        if isinstance(child, Tag):
            current.append(child.get_text(" ", strip=True))
        else:
            current.append(str(child))
    value = _clean("".join(current))
    if value:
        values.append(value)
    return values


def _party_values(
    node: Tag | None, role: str
) -> list[dict[str, str | None]]:
    values: list[dict[str, str | None]] = []
    for raw in _line_values(node):
        match = re.fullmatch(r"(?P<name>.*?)\s*\[(?P<address>.*)\]\s*", raw)
        name = _clean(match.group("name") if match else raw)
        address = _clean(match.group("address")) if match else None
        if name:
            values.append(
                {
                    "role": role,
                    "name": name,
                    "address_raw": address,
                    "raw": raw,
                }
            )
    return values


def parse_detail_page(
    html: str,
    page_url: str,
    *,
    expected_record_id: str | None = None,
) -> DetailPage:
    """Parse one estate case and emit its docket events separately."""

    safe_url = _official_url(DETAIL_URL, page_url)
    soup = BeautifulSoup(html, "html.parser")
    refresh = _refresh_marker(soup, url=safe_url)
    record_values = parse_qs(urlsplit(safe_url).query).get("RecordId") or []
    record_id = _clean(record_values[0] if record_values else expected_record_id)
    if not record_id or not RECORD_ID_RE.fullmatch(record_id):
        raise MarylandEstateSourceChangedError(
            "Maryland estate detail lacks a numeric RecordId", url=safe_url
        )
    if expected_record_id and record_id != expected_record_id:
        raise MarylandEstateSourceChangedError(
            "Maryland estate detail returned a different RecordId",
            url=safe_url,
            details={
                "expected_record_id": expected_record_id,
                "observed_record_id": record_id,
            },
        )
    page_text = _clean(soup) or ""
    county_match = re.search(r"Estate\s+Record\s*\(([^)]+)\)", page_text, re.I)
    if not county_match:
        raise MarylandEstateSourceChangedError(
            "Maryland estate detail county label changed", url=safe_url
        )
    county_raw = _clean(county_match.group(1)) or ""
    county = _canonical_county_name(county_raw)
    estate_table = soup.select_one("#tblEstateData")
    if not isinstance(estate_table, Tag):
        raise MarylandEstateSourceChangedError(
            "Maryland estate detail table is missing", url=safe_url
        )
    fields = _detail_fields(estate_table, url=safe_url)
    estate_number = _clean(fields["Estate Number"]) or ""
    case_ref = _case_ref(county, estate_number)
    aliases = _line_values(soup.select_one("#lblAliases"))
    representatives = _party_values(
        soup.select_one("#lblPersonalReps"), "personal_representative"
    )
    attorneys = _party_values(
        soup.select_one("#lblAttorney"), "estate_attorney"
    )
    detail_schema = {
        "estate_labels": sorted(fields),
        "docket_headers": EXPECTED_DOCKET_HEADERS,
        "party_shapes": ["name", "address_raw", "raw", "role"],
    }
    schema_fp = sha256_fingerprint(detail_schema)
    case_record: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "record_kind": "estate_case_detail",
        "canonical_ref": case_ref,
        "evidence_ref": case_ref,
        "canonical_case_ref": case_ref,
        "source_internal_id": record_id,
        "record_id": record_id,
        "county": county,
        "county_raw": county_raw,
        "court_id": _county_court_id(county),
        "estate_number": estate_number,
        "estate_type": _clean(fields.get("Type")),
        "estate_type_description": ESTATE_TYPES.get(
            _clean(fields.get("Type")) or ""
        ),
        "estate_status": _clean(fields.get("Status")),
        "date_opened_raw": _clean(fields.get("Date Opened")),
        "date_opened": _parse_date(fields.get("Date Opened")),
        "date_closed_raw": _clean(fields.get("Date Closed")),
        "date_closed": _parse_date(fields.get("Date Closed")),
        "reference_raw": _clean(fields.get("Reference")),
        "decedent_name": _clean(fields.get("Decedent Name")),
        "date_of_death_raw": _clean(fields.get("Date of Death")),
        "date_of_death": _parse_date(fields.get("Date of Death")),
        "filing_date_raw": _clean(fields.get("Date of Filing")),
        "filing_date": _parse_date(fields.get("Date of Filing")),
        "will_status": _clean(fields.get("Will")),
        "will_date_raw": _clean(fields.get("Date of Will")),
        "will_date": _parse_date(fields.get("Date of Will")),
        "probate_date_raw": _clean(fields.get("Date of Probate")),
        "probate_date": _parse_date(fields.get("Date of Probate")),
        "aliases": aliases,
        "personal_representatives": representatives,
        "attorneys": attorneys,
        "stable_key_fields": ["county", "estate_number"],
        "join_keys": {
            "estate": {
                "county": county,
                "estate_number": estate_number,
            },
            "people": {
                "decedent_name": _clean(fields.get("Decedent Name")),
                "aliases": aliases,
                "personal_representative_names": [
                    value["name"] for value in representatives
                ],
                "attorney_names": [value["name"] for value in attorneys],
            },
            "property_and_notices": {
                "county": county,
                "decedent_name": _clean(fields.get("Decedent Name")),
                "date_of_death": _parse_date(fields.get("Date of Death")),
            },
        },
        "source_snapshot": {
            "latest_data_raw": refresh.raw,
            "latest_data_at": refresh.timestamp,
            "application_instance": refresh.instance,
            "update_frequency": "daily",
        },
        "source_url": safe_url,
        "response_schema_fingerprint": schema_fp,
        "source_fields": fields,
    }
    records: list[Mapping[str, Any]] = [case_record]

    docket = soup.select_one("#dgDocketHistory")
    if isinstance(docket, Tag):
        header_seen = False
        sequence = 0
        for row in docket.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            values = tuple(_clean(cell) or "" for cell in cells)
            if values == EXPECTED_DOCKET_HEADERS:
                header_seen = True
                continue
            if not cells:
                continue
            if len(cells) != len(EXPECTED_DOCKET_HEADERS):
                continue
            if not any(values[:5]):
                continue
            sequence += 1
            section_node = row.select_one(
                "input[name$='SecId'], input[id$='SecId']"
            )
            section_id = (
                _clean(section_node.get("value"))
                if isinstance(section_node, Tag)
                else None
            )
            material = {
                "filed_on": values[0],
                "docket_number": values[1],
                "code": values[2],
                "description": values[3],
                "pages": values[4],
                "sequence": sequence,
            }
            native_event_id = section_id or (
                "material-" + sha256_fingerprint(material)[:24]
            )
            event_ref = canonical_court_ref(
                SOURCE_ID,
                _county_court_id(county),
                estate_number,
                "estate_docket_event",
                native_event_id,
            )
            records.append(
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "estate_docket_event",
                    "canonical_ref": event_ref,
                    "evidence_ref": event_ref,
                    "canonical_case_ref": case_ref,
                    "source_internal_id": native_event_id,
                    "native_section_id": section_id,
                    "county": county,
                    "court_id": _county_court_id(county),
                    "estate_number": estate_number,
                    "record_id": record_id,
                    "event_sequence": sequence,
                    "filed_on_raw": values[0] or None,
                    "filed_on": _parse_date(values[0]),
                    "docket_number": values[1] or None,
                    "docket_code": values[2] or None,
                    "description": values[3] or None,
                    "page_count_raw": values[4] or None,
                    "page_count": (
                        int(values[4]) if values[4].isdigit() else None
                    ),
                    "copy_available": section_id is not None,
                    "stable_key_fields": (
                        ["county", "estate_number", "native_section_id"]
                        if section_id
                        else [
                            "county",
                            "estate_number",
                            "event_material_hash",
                        ]
                    ),
                    "join_keys": {
                        "estate": {
                            "county": county,
                            "estate_number": estate_number,
                        },
                        "docket": {
                            "docket_number": values[1] or None,
                            "docket_code": values[2] or None,
                            "filed_on": _parse_date(values[0]),
                        },
                    },
                    "source_snapshot": case_record["source_snapshot"],
                    "source_url": safe_url,
                    "response_schema_fingerprint": schema_fp,
                }
            )
        if not header_seen:
            raise MarylandEstateSourceChangedError(
                "Maryland estate docket columns changed",
                url=safe_url,
                details={"expected_headers": list(EXPECTED_DOCKET_HEADERS)},
            )
    case_record["docket_event_count"] = len(records) - 1
    return DetailPage(
        records=tuple(records),
        url=safe_url,
        refresh=refresh,
        schema_fingerprint=schema_fp,
    )


def _criteria_fingerprint(criteria: SearchCriteria) -> str:
    return sha256_fingerprint(criteria.parameters())


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "schema": state.result_schema_fingerprint,
        "refresh_raw": state.refresh_raw,
        "refresh_at": state.refresh_timestamp,
        "total": state.total_count,
        "pages": state.total_pages,
        "page": state.page_number,
        "offset": state.row_offset,
        "emitted": state.emitted_count,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode()
    ).decode().rstrip("=")
    return CURSOR_PREFIX + encoded


def _decode_cursor(value: str) -> CursorState:
    if not value.startswith(CURSOR_PREFIX):
        raise MarylandEstateCursorError("Continuation cursor format is invalid")
    token = value[len(CURSOR_PREFIX) :]
    try:
        padded = token + ("=" * (-len(token) % 4))
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode()).decode()
        )
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarylandEstateCursorError(
            "Continuation cursor could not be decoded"
        ) from exc
    required = {
        "v",
        "criteria",
        "schema",
        "refresh_raw",
        "refresh_at",
        "total",
        "pages",
        "page",
        "offset",
        "emitted",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise MarylandEstateCursorError(
            "Continuation cursor payload is invalid"
        )
    if payload["v"] != CURSOR_VERSION:
        raise MarylandEstateCursorError(
            "Continuation cursor version is unsupported"
        )
    try:
        state = CursorState(
            criteria_fingerprint=str(payload["criteria"]),
            result_schema_fingerprint=str(payload["schema"]),
            refresh_raw=str(payload["refresh_raw"]),
            refresh_timestamp=str(payload["refresh_at"]),
            total_count=int(payload["total"]),
            total_pages=int(payload["pages"]),
            page_number=int(payload["page"]),
            row_offset=int(payload["offset"]),
            emitted_count=int(payload["emitted"]),
        )
    except (TypeError, ValueError) as exc:
        raise MarylandEstateCursorError(
            "Continuation cursor values are invalid"
        ) from exc
    if (
        state.total_count < 1
        or state.total_pages < 1
        or state.page_number < 1
        or state.page_number > state.total_pages
        or state.row_offset < 0
        or state.row_offset >= NATIVE_PAGE_SIZE
        or state.emitted_count < 0
        or state.emitted_count >= state.total_count
    ):
        raise MarylandEstateCursorError(
            "Continuation cursor position is invalid"
        )
    expected_emitted = (
        (state.page_number - 1) * NATIVE_PAGE_SIZE + state.row_offset
    )
    if state.emitted_count != expected_emitted:
        raise MarylandEstateCursorError(
            "Continuation cursor position is internally inconsistent"
        )
    return state


class MarylandEstateClient:
    """Stateful client for the official ASP.NET estate application."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self._owns_session = session is None
        self.session = session or system_trust_session()
        if hasattr(self.session, "headers"):
            self.session.headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    data=dict(data) if data is not None else None,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if status_code == 429:
                raise MarylandEstateRateLimitedError(
                    "Maryland estate source returned HTTP 429",
                    url=url,
                    details={"status_code": status_code},
                )
            if status_code in {401, 403}:
                raise MarylandEstateRestrictedError(
                    f"Maryland estate source returned HTTP {status_code}",
                    url=url,
                    details={"status_code": status_code},
                )
            if status_code in self.retry_policy.retry_statuses:
                last_error = MarylandEstateTransportError(
                    f"Maryland estate source returned HTTP {status_code}",
                    url=url,
                    details={"status_code": status_code},
                )
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code >= 400:
                raise MarylandEstateTransportError(
                    f"Maryland estate source returned HTTP {status_code}",
                    url=url,
                    details={"status_code": status_code},
                )
            content = getattr(response, "content", None)
            if content is None:
                content = str(getattr(response, "text", "")).encode()
            if len(content) > DEFAULT_MAX_PAGE_BYTES:
                raise MarylandEstateSourceChangedError(
                    "Maryland estate response exceeded the page-size bound",
                    url=url,
                    details={
                        "size_bytes": len(content),
                        "max_bytes": DEFAULT_MAX_PAGE_BYTES,
                    },
                )
            return response
        if isinstance(last_error, MarylandEstateError):
            raise last_error
        raise MarylandEstateTransportError(
            "Could not reach the Maryland estate source",
            url=url,
            details={"reason": str(last_error or "request failed")},
        ) from last_error

    @staticmethod
    def _text(response: Any) -> str:
        text = getattr(response, "text", None)
        if text is not None:
            return str(text)
        return bytes(response.content).decode("utf-8", errors="replace")

    @staticmethod
    def _url(response: Any, fallback: str) -> str:
        return str(getattr(response, "url", None) or fallback)

    def search(self, criteria: SearchCriteria) -> ResultsPage:
        response = self._request("GET", SEARCH_URL)
        form = parse_search_form(
            self._text(response),
            page_url=self._url(response, SEARCH_URL),
        )
        response = self._request(
            "POST",
            form.action_url,
            data=criteria.form_data(form),
        )
        return parse_results_page(
            self._text(response),
            page_url=self._url(response, form.action_url),
        )

    def postback(self, page: ResultsPage, target: str) -> ResultsPage:
        data = dict(page.hidden_fields)
        data["__EVENTTARGET"] = target
        data["__EVENTARGUMENT"] = ""
        response = self._request("POST", page.action_url, data=data)
        return parse_results_page(
            self._text(response),
            page_url=self._url(response, page.action_url),
        )

    def detail(self, record_id: str) -> DetailPage:
        wanted = _clean(record_id)
        if not wanted or not RECORD_ID_RE.fullmatch(wanted):
            raise MarylandEstateSelectionError(
                "Maryland estate RecordId must contain only digits"
            )
        url = f"{DETAIL_URL}?{urlencode({'src': 'row', 'RecordId': wanted})}"
        response = self._request("GET", url)
        return parse_detail_page(
            self._text(response),
            self._url(response, url),
            expected_record_id=wanted,
        )


def _same_snapshot(
    page: ResultsPage,
    first: ResultsPage,
    *,
    cursor: CursorState | None = None,
) -> None:
    if page.schema_fingerprint != first.schema_fingerprint:
        raise MarylandEstateSourceChangedError(
            "Maryland estate result schema changed during traversal",
            url=page.url,
        )
    if page.refresh.raw != first.refresh.raw:
        raise MarylandEstateCursorError(
            "Maryland estate data refreshed during result traversal",
            url=page.url,
            details={
                "initial_refresh": first.refresh.raw,
                "observed_refresh": page.refresh.raw,
            },
        )
    if (
        page.total_count != first.total_count
        or page.total_pages != first.total_pages
    ):
        raise MarylandEstateCursorError(
            "Maryland estate result count changed during traversal",
            url=page.url,
            details={
                "initial_total": first.total_count,
                "observed_total": page.total_count,
            },
        )
    if cursor is not None:
        if cursor.result_schema_fingerprint != first.schema_fingerprint:
            raise MarylandEstateCursorError(
                "Maryland estate result schema changed since the cursor was issued"
            )
        if (
            cursor.refresh_raw != first.refresh.raw
            or cursor.refresh_timestamp != first.refresh.timestamp
        ):
            raise MarylandEstateCursorError(
                "Maryland estate data refreshed since the cursor was issued",
                details={
                    "cursor_refresh": cursor.refresh_raw,
                    "current_refresh": first.refresh.raw,
                },
            )
        if (
            cursor.total_count != first.total_count
            or cursor.total_pages != first.total_pages
        ):
            raise MarylandEstateCursorError(
                "Maryland estate result count changed since the cursor was issued",
                details={
                    "cursor_total": cursor.total_count,
                    "current_total": first.total_count,
                },
            )


def _navigate(
    client: MarylandEstateClient | Any,
    first: ResultsPage,
    target_page: int,
) -> tuple[ResultsPage, list[str]]:
    current = first
    artifacts = [first.url]
    while current.current_page < target_page:
        target = current.page_targets.get(target_page)
        visible_max = max(
            current.page_targets,
            default=current.current_page,
        )
        if (
            target is None
            and target_page > visible_max
            and current.forward_target is not None
        ):
            target = current.forward_target
        if target is None:
            target = current.page_targets.get(current.current_page + 1)
        if target is None:
            target = current.forward_target
        if target is None:
            raise MarylandEstateSourceChangedError(
                "Maryland estate pager cannot reach the requested page",
                url=current.url,
                details={
                    "current_page": current.current_page,
                    "target_page": target_page,
                    "visible_pages": sorted(current.page_targets),
                },
            )
        next_page = client.postback(current, target)
        _same_snapshot(next_page, first)
        if (
            next_page.current_page <= current.current_page
            or next_page.current_page > target_page
        ):
            raise MarylandEstateSourceChangedError(
                "Maryland estate pager advanced to an unexpected page",
                url=next_page.url,
                details={
                    "previous_page": current.current_page,
                    "observed_page": next_page.current_page,
                    "target_page": target_page,
                },
            )
        current = next_page
        artifacts.append(current.url)
    return current, artifacts


def _run_search(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    criteria: SearchCriteria,
    client: MarylandEstateClient | Any,
    *,
    retrieved_at: str,
) -> PublicRecordsResult:
    first = client.search(criteria)
    if first.total_count == 0:
        if args.cursor:
            raise MarylandEstateCursorError(
                "Continuation cursor no longer points to a matching result set"
            )
        return PublicRecordsResult.success(
            query,
            [],
            retrieved_at=retrieved_at,
            raw_artifact_refs=[first.url],
            warnings=SOURCE_WARNINGS,
        )
    cursor = _decode_cursor(args.cursor) if args.cursor else None
    if cursor:
        if cursor.criteria_fingerprint != _criteria_fingerprint(criteria):
            raise MarylandEstateCursorError(
                "Continuation cursor belongs to different search criteria"
            )
        _same_snapshot(first, first, cursor=cursor)
        page_number = cursor.page_number
        row_offset = cursor.row_offset
        emitted_before = cursor.emitted_count
    else:
        page_number = 1
        row_offset = 0
        emitted_before = 0
    current, artifacts = _navigate(client, first, page_number)
    remaining = first.total_count - emitted_before
    wanted = remaining if args.limit is None else min(args.limit, remaining)
    records: list[dict[str, Any]] = []
    while len(records) < wanted:
        available = current.rows[row_offset:]
        take = min(len(available), wanted - len(records))
        records.extend(
            normalize_search_row(
                row,
                criteria=criteria,
                refresh=first.refresh,
                schema_fingerprint=first.schema_fingerprint,
            )
            for row in available[:take]
        )
        row_offset += take
        if len(records) == wanted:
            break
        if current.current_page >= first.total_pages:
            raise MarylandEstateSourceChangedError(
                "Maryland estate traversal ended before its published total",
                url=current.url,
            )
        current, more_artifacts = _navigate(
            client, current, current.current_page + 1
        )
        _same_snapshot(current, first)
        artifacts.extend(more_artifacts[1:])
        row_offset = 0
    emitted = emitted_before + len(records)
    next_cursor = None
    if emitted < first.total_count:
        next_page = current.current_page
        next_offset = row_offset
        if next_offset == len(current.rows):
            next_page += 1
            next_offset = 0
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=_criteria_fingerprint(criteria),
                result_schema_fingerprint=first.schema_fingerprint,
                refresh_raw=first.refresh.raw,
                refresh_timestamp=first.refresh.timestamp,
                total_count=first.total_count,
                total_pages=first.total_pages,
                page_number=next_page,
                row_offset=next_offset,
                emitted_count=emitted,
            )
        )
    warnings = (
        *SOURCE_WARNINGS,
        f"Authoritative source count for this query snapshot: {first.total_count}.",
    )
    if next_cursor:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="caller_result_limit",
                    message=(
                        "More source rows are available; continue with the "
                        "returned snapshot-bound cursor."
                    ),
                    category="pagination",
                    retryable=False,
                    details={
                        "source_total": first.total_count,
                        "emitted_through": emitted,
                    },
                )
            ],
            records=records,
            next_cursor=next_cursor,
            retrieved_at=retrieved_at,
            raw_artifact_refs=list(dict.fromkeys(artifacts)),
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=retrieved_at,
        raw_artifact_refs=list(dict.fromkeys(artifacts)),
        warnings=warnings,
    )


def _criteria_from_args(args: argparse.Namespace) -> SearchCriteria:
    if args.command == "decedent":
        return SearchCriteria(
            operation="decedent",
            last_name=args.last_name,
            first_name=args.first_name,
            middle_name=args.middle_name,
            exact_last_name=args.exact_last_name,
            county=args.county,
            status=args.status,
            estate_type=args.estate_type,
            filed_from=args.filed_from,
            filed_to=args.filed_to,
            filing_date=args.filing_date,
        )
    if args.command == "representative":
        return SearchCriteria(
            operation="representative",
            last_name=args.last_name,
            first_name=args.first_name,
            middle_name=args.middle_name,
            exact_last_name=args.exact_last_name,
            county=args.county,
            status=args.status,
            estate_type=args.estate_type,
            filed_from=args.filed_from,
            filed_to=args.filed_to,
            filing_date=args.filing_date,
        )
    if args.command == "estate":
        return SearchCriteria(
            operation="estate",
            estate_number=args.estate_number,
            county=args.county,
            status=args.status,
            estate_type=args.estate_type,
            filed_from=args.filed_from,
            filed_to=args.filed_to,
            filing_date=args.filing_date,
        )
    if args.command == "probe":
        return SearchCriteria(
            operation="estate",
            estate_number=PROBE_ESTATE_NUMBER,
            county=PROBE_COUNTY,
        )
    raise MarylandEstateSelectionError(
        f"Unsupported Maryland estate operation: {args.command}"
    )


def source_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = [
        {
            "source_id": SOURCE_ID,
            "record_kind": "source_manifest",
            "name": SOURCE_METADATA.name,
            "url": AGREEMENT_URL,
            "application_url": SEARCH_URL,
            "glossary_url": GLOSSARY_URL,
            "faq_url": FAQ_URL,
            "implemented_operations": [
                "decedent",
                "representative",
                "estate",
                "detail",
                "probe",
                "routes",
            ],
            "coverage": {
                "jurisdictions": (
                    "all 23 Maryland counties and Baltimore City"
                ),
                "records": (
                    "estate case index, estate detail, parties, and docket"
                ),
                "statewide_period": "generally 1998-present",
                "older_records": "varies by jurisdiction",
                "update_frequency": "daily",
                "fields": list(EXPECTED_RESULT_HEADERS),
            },
            "bounds": {
                "native_page_size": NATIVE_PAGE_SIZE,
                "observed_native_pagination": (
                    "live result counts can exceed the older FAQ's "
                    "500-record description"
                ),
                "caller_limit": (
                    "default 100; --all-results traverses every native page"
                ),
            },
            "identity": {
                "estate_case": ["county", "estate_number"],
                "source_locator": ["RecordId"],
                "docket_event": [
                    "county",
                    "estate_number",
                    "SecId",
                ],
                "docket_fallback": [
                    "county",
                    "estate_number",
                    "filed_on",
                    "docket_number",
                    "code",
                    "description",
                    "sequence",
                ],
            },
        }
    ]
    records.extend(
        {"record_kind": "complementary_source", **route}
        for route in RELATED_ROUTES
    )
    return records


def _routes_record() -> dict[str, Any]:
    canonical_ref = (
        "MD-ESTATE-ROUTES:" + sha256_fingerprint(RELATED_ROUTES)
    )
    return {
        "source_id": SOURCE_ID,
        "record_kind": "public_record_route_map",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "coverage_strategy": (
            "Use the statewide estate index as the case-and-docket anchor, "
            "then pivot by the strongest available estate, person, court, or "
            "property key to the official source holding the missing role."
        ),
        "jurisdiction": {
            "name": JURISDICTION.name,
            "geoid": STATE_GEOID,
            "state_code": STATE_CODE,
        },
        "routes": list(RELATED_ROUTES),
        "strongest_join_keys": [
            "county and estate number",
            "decedent name and date of death",
            "personal representative name",
            "case number",
            "property address or liber/folio",
        ],
    }


def _query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "ordering": "native estate-index ordering",
                "pagination": "refresh_bound_webforms_replay",
            },
        ),
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _new_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> MarylandEstateClient:
    limits = access_contract.get("limits") or {}
    reviewed_interval = float(limits.get("minimum_interval_seconds") or 0)
    return MarylandEstateClient(
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )


def _access_failure(
    query: PublicRecordsQuery, error: Exception
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        public_error = PublicRecordsError(
            code=str(
                decision.get("reason_code")
                or "acquisition_route_unavailable"
            ),
            message=str(decision.get("reason") or error),
            category="access",
            retryable=False,
            details=decision,
        )
    else:
        status = ResultStatus.UNAVAILABLE
        public_error = PublicRecordsError(
            code="catalog_unavailable",
            message=str(error),
            category="catalog",
            retryable=False,
        )
    return PublicRecordsResult.failure(
        query, status, [public_error], warnings=SOURCE_WARNINGS
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: MarylandEstateClient | Any | None = None,
    retrieved_at: str | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one estate source operation."""

    retrieved_at = retrieved_at or utc_now_iso()
    if args.command == "routes":
        query = _query("routes", {"route_scope": "estate_and_adjacent_records"})
        result = PublicRecordsResult.success(
            query,
            [_routes_record()],
            retrieved_at=retrieved_at,
            raw_artifact_refs=[AGREEMENT_URL, DIRECTORY_URL],
            warnings=SOURCE_WARNINGS,
        )
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, 1)
        return result

    query = _query(args.command, {})
    owns_client = False
    try:
        if args.command in {
            "decedent",
            "representative",
            "estate",
            "probe",
        }:
            criteria = _criteria_from_args(args)
            limit = 1 if args.command == "probe" else (
                None if args.all_results else args.limit
            )
            query = _query(
                args.command,
                criteria.parameters(),
                limit=limit,
                cursor=args.cursor,
            )
        elif args.command == "detail":
            record_id = _clean(args.record_id)
            query = _query("detail", {"record_id": record_id})
        else:
            raise MarylandEstateSelectionError(
                f"Unsupported Maryland estate operation: {args.command}"
            )
        contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args)
        )
        source_client = client or _new_client(args, contract)
        owns_client = client is None
        if args.command == "detail":
            detail = source_client.detail(record_id)
            result = PublicRecordsResult.success(
                query,
                detail.records,
                retrieved_at=retrieved_at,
                raw_artifact_refs=[detail.url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            first = source_client.search(criteria)
            if not first.rows:
                raise MarylandEstateSourceResponseError(
                    "Maryland estate probe sentinel returned no result",
                    url=first.url,
                )
            detail = source_client.detail(first.rows[0].record_id)
            case = detail.records[0]
            probe_ref = (
                "MD-ESTATE-PROBE:"
                + sha256_fingerprint(
                    {
                        "form_and_results": first.schema_fingerprint,
                        "detail": detail.schema_fingerprint,
                        "refresh": first.refresh.raw,
                        "record_id": first.rows[0].record_id,
                    }
                )
            )
            probe = {
                "source_id": SOURCE_ID,
                "record_kind": "source_probe",
                "canonical_ref": probe_ref,
                "evidence_ref": probe_ref,
                "status": "ok",
                "operation_states": {
                    "agreement_navigation": "available",
                    "search_form": "available",
                    "estate_number_search": "available",
                    "dynamic_native_pagination": (
                        "available"
                        if first.total_pages > 1
                        else "not_needed_for_sentinel"
                    ),
                    "estate_detail": "available",
                    "docket_history": (
                        "available"
                        if case["docket_event_count"]
                        else "empty_for_sentinel"
                    ),
                },
                "source_latest_data_raw": first.refresh.raw,
                "source_latest_data_at": first.refresh.timestamp,
                "application_instance": first.refresh.instance,
                "search_result_count": first.total_count,
                "sentinel_record_id": first.rows[0].record_id,
                "sentinel_estate_number": case["estate_number"],
                "sentinel_county": case["county"],
                "sentinel_docket_event_count": case["docket_event_count"],
                "result_schema_fingerprint": first.schema_fingerprint,
                "detail_schema_fingerprint": detail.schema_fingerprint,
            }
            result = PublicRecordsResult.success(
                query,
                [probe],
                retrieved_at=retrieved_at,
                raw_artifact_refs=[first.url, detail.url],
                warnings=SOURCE_WARNINGS,
            )
        else:
            result = _run_search(
                args,
                query,
                criteria,
                source_client,
                retrieved_at=retrieved_at,
            )
    except (AcquisitionUnavailableError, CatalogError, OSError) as error:
        result = _access_failure(query, error)
    except MarylandEstateError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            retrieved_at=retrieved_at,
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client:
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
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
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
    add_output_args(parser)


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--county", help="Maryland jurisdiction label or value")
    parser.add_argument(
        "--status",
        help="Estate status label or native value",
    )
    parser.add_argument(
        "--estate-type",
        help="Estate type code or published label",
    )
    parser.add_argument("--filed-from", help="Filing-date start (YYYY-MM-DD)")
    parser.add_argument("--filed-to", help="Filing-date end (YYYY-MM-DD)")
    parser.add_argument("--filing-date", help="Exact filing date (YYYY-MM-DD)")
    parser.add_argument("--cursor")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--all-results",
        action="store_true",
        help="Traverse every native result page",
    )
    _add_runtime(parser)


def _add_name_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--first-name")
    parser.add_argument("--middle-name")
    parser.add_argument(
        "--exact-last-name",
        action="store_true",
        help="Select the source's exact-last-name option",
    )
    _add_filters(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Maryland Register of Wills estate records"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    decedent = subparsers.add_parser(
        "decedent", help="Search by decedent name"
    )
    decedent.add_argument("last_name")
    _add_name_filters(decedent)

    representative = subparsers.add_parser(
        "representative", help="Search by personal-representative name"
    )
    representative.add_argument("last_name")
    _add_name_filters(representative)

    estate = subparsers.add_parser(
        "estate", help="Search by estate number"
    )
    estate.add_argument("estate_number")
    _add_filters(estate)

    detail = subparsers.add_parser(
        "detail", help="Fetch estate details, parties, and docket events"
    )
    detail.add_argument("record_id", help="Numeric RowNet RecordId")
    _add_runtime(detail)

    probe = subparsers.add_parser(
        "probe", help="Verify search, detail, docket, and refresh markers"
    )
    probe.set_defaults(
        all_results=False,
        limit=1,
        cursor=None,
    )
    _add_runtime(probe)

    routes = subparsers.add_parser(
        "routes", help="Show complementary official sources and join keys"
    )
    add_output_args(routes)
    return parser


def _validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    for name in ("timeout", "max_attempts"):
        if hasattr(args, name) and getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    for name in ("minimum_interval", "retry_backoff"):
        if hasattr(args, name) and getattr(args, name) < 0:
            parser.error(
                f"--{name.replace('_', '-')} must not be negative"
            )
    if hasattr(args, "limit") and args.limit <= 0:
        parser.error("--limit must be positive")


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Maryland estate search {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Maryland estate search {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('estate_number') or record.get('source_id') or '?'}"
            f" | {record.get('record_kind') or '?'}"
            f" | {record.get('decedent_name') or record.get('status') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(args, parser)
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
