#!/usr/bin/env python3
"""Query Queensland eCourts Supreme and District Court civil files.

The official eCourts service is an anonymous ASP.NET WebForms application.  It
provides party/file search results, case parties, representatives, events, and
document-list metadata.  The documents themselves are requested through a
separate official court-record-copy route.

Searches return 20 files per native page and stop at the first 500 matches.
With no ``--limit``, this adapter traverses every native page and, when the
500-result marker appears, partitions the query by source-native court,
originating registry, proceeding category, and party role as needed.  A
remaining unsplittable ceiling is returned explicitly as a partial result.

Examples:
    uv run python tools/query_qld_ecourts.py search \
        --party-name COSCOLLUELA --output /tmp/qld-cases.json
    uv run python tools/query_qld_ecourts.py search \
        --file-number 6819/11 --court SUPRE --include-details --json
    uv run python tools/query_qld_ecourts.py case 6819/11 \
        --court SUPRE --location BRISB --json
    uv run python tools/query_qld_ecourts.py detail 6819/11 \
        --court SUPRE --location BRISB --json
    uv run python tools/query_qld_ecourts.py sources --json
    uv run python tools/query_qld_ecourts.py probe --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import deque
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

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
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        system_trust_session,
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
        sha256_fingerprint,
    )
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "au-qld-ecourts-civil"
BASE_URL = "https://apps.courts.qld.gov.au/esearching/"
SEARCH_URL = urljoin(BASE_URL, "Search.aspx")
RESULTS_URL = urljoin(BASE_URL, "Results.aspx")
DETAIL_URL = urljoin(BASE_URL, "FileDetails.aspx")
OFFICIAL_GUIDE_URL = (
    "https://www.courts.qld.gov.au/new/The-Courts/supreme-court/"
    "supreme-court-pathway?a=876721"
)
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.35
DEFAULT_USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
NATIVE_PAGE_SIZE = 20
NATIVE_RESULT_CEILING = 500
PROBE_FILE_NUMBER = "6819/11"
PROBE_COURT = "SUPRE"
PROBE_LOCATION = "BRISB"

COURTS = {
    "DISTR": "District",
    "SUPRE": "Supreme",
}
COURT_IDS = {
    "DISTR": "qld-district-court",
    "SUPRE": "qld-supreme-court",
}
LOCATIONS = {
    "BEEN": "Beenleigh",
    "BOWN": "Bowen",
    "BRISB": "Brisbane",
    "BUN": "Bundaberg",
    "CRNS": "Cairns",
    "CHAR": "Charleville",
    "CHRT": "Charters Towers",
    "CLON": "Cloncurry",
    "CUN": "Cunnamulla",
    "DALB": "Dalby",
    "EMLD": "Emerald",
    "GLAD": "Gladstone",
    "GWI": "Goondiwindi",
    "GYMP": "Gympie",
    "HERB": "Hervey Bay",
    "INFL": "Innisfail",
    "IPS": "Ipswich",
    "KING": "Kingaroy",
    "LONG": "Longreach",
    "MCKY": "Mackay",
    "MDORE": "Maroochydore",
    "MBGH": "Maryborough",
    "MISA": "Mt Isa",
    "ROCK": "Rockhampton",
    "ROMA": "Roma",
    "STHP": "Southport",
    "STAN": "Stanthorpe",
    "TMBA": "Toowoomba",
    "TOWNS": "Townsville",
    "WARW": "Warwick",
}

FORM_FIELDS = {
    "file_number": "ctl00$ContentPlaceHolder1$LayoutPanel1$filenumber",
    "category1": "ctl00$ContentPlaceHolder1$LayoutPanel1$category1",
    "category2": "ctl00$ContentPlaceHolder1$LayoutPanel1$category2",
    "category3": "ctl00$ContentPlaceHolder1$LayoutPanel1$category3",
    "originating_location": (
        "ctl00$ContentPlaceHolder1$LayoutPanel2$OriginatingLocation"
    ),
    "current_location": (
        "ctl00$ContentPlaceHolder1$LayoutPanel2$CurrentLocation"
    ),
    "court": "ctl00$ContentPlaceHolder1$LayoutPanel3$court",
    "listing_from": (
        "ctl00$ContentPlaceHolder1$LayoutPanel4$Datefromlisting"
    ),
    "listing_to": "ctl00$ContentPlaceHolder1$LayoutPanel4$Datetolisting",
    "last_company_name": (
        "ctl00$ContentPlaceHolder1$LayoutPanel5$lastcompanyname"
    ),
    "given_names": "ctl00$ContentPlaceHolder1$LayoutPanel5$givennames",
    "party_role": "ctl00$ContentPlaceHolder1$LayoutPanel5$Partyrole",
    "party_date_from": (
        "ctl00$ContentPlaceHolder1$LayoutPanel5$Datefromparty"
    ),
    "second_last_company_name": (
        "ctl00$ContentPlaceHolder1$LayoutPanel6$lastcompanyname2"
    ),
    "second_given_names": (
        "ctl00$ContentPlaceHolder1$LayoutPanel6$givennames2"
    ),
    "second_party_role": (
        "ctl00$ContentPlaceHolder1$LayoutPanel6$Partyrole2"
    ),
}
SEARCH_BUTTON = "ctl00$ContentPlaceHolder1$SearchButton"
SELECTOR_FIELDS = {
    "court": FORM_FIELDS["court"],
    "originating_location": FORM_FIELDS["originating_location"],
    "current_location": FORM_FIELDS["current_location"],
    "category1": FORM_FIELDS["category1"],
    "category2": FORM_FIELDS["category2"],
    "category3": FORM_FIELDS["category3"],
    "party_role": FORM_FIELDS["party_role"],
    "second_party_role": FORM_FIELDS["second_party_role"],
}

SEARCH_PARTY_HEADERS = (
    "Last/Company name",
    "First name",
    "Proceeding Type",
    "Party role",
    "Date filed",
)
DETAIL_PARTY_HEADERS = (
    "Last/Company name",
    "First name",
    "ACN",
    "Party role",
    "Representative",
)
EVENT_HEADERS = (
    "Date",
    "Event type",
    "Diary Type",
    "Resource",
    "Result",
)
DOCUMENT_HEADERS = (
    "Doc no",
    "Date filed",
    "Document type",
    "Document description",
    "Filed on behalf of",
    "Pages",
)
POSTBACK_RE = re.compile(r"__doPostBack\('([^']*)','([^']*)'\)")
COUNT_RE = re.compile(r"(\d+)\s*-\s*(\d+)\s+of\s+(\d+)")
FILE_NUMBER_RE = re.compile(r"^\s*([A-Za-z0-9.-]+)\s*/\s*(\d{2,4})\s*$")

COMPLEMENTARY_OFFICIAL_ROUTES = (
    {
        "source_id": "au-qld-court-record-copy-request",
        "name": "Queensland Courts search and copy request",
        "role": (
            "Request searches or copies of Supreme, District, Magistrates, "
            "and other court-file documents identified through eCourts"
        ),
        "url": (
            "https://www.qld.gov.au/law/court/court-services/"
            "access-court-records-files-and-services/"
            "apply-to-search-and-copy-court-documents"
        ),
    },
    {
        "source_id": "au-qld-criminal-case-lookup",
        "name": "Queensland Courts criminal case lookup",
        "role": "Upcoming criminal court events; distinct from the civil file index",
        "url": (
            "https://www.courts.qld.gov.au/services-and-online-actions/"
            "file-searches/criminal-case-lookup"
        ),
    },
    {
        "source_id": "au-qld-daily-law-lists",
        "name": "Queensland Courts daily law lists",
        "role": "Current court lists and hearing schedules",
        "url": "https://www.courts.qld.gov.au/services/court-lists",
    },
    {
        "source_id": "au-qld-official-caselaw",
        "name": "Supreme Court Library Queensland CaseLaw",
        "role": (
            "Official unreported judgments and sentencing remarks across "
            "Queensland courts and tribunals"
        ),
        "url": "https://www.sclqld.org.au/caselaw",
    },
    {
        "source_id": "au-qld-authorised-and-unreported-judgments",
        "name": "Queensland Judgments",
        "role": "Authorised reports and official unreported judgments",
        "url": "https://www.queenslandjudgments.com.au/",
    },
    {
        "source_id": "au-qld-state-archives-court-records",
        "name": "Queensland State Archives",
        "role": (
            "Historical court records, including older holdings outside "
            "eCourts registry coverage"
        ),
        "url": "https://www.archivessearch.qld.gov.au/",
    },
)

SOURCE_WARNINGS = (
    "eCourts is a civil-file index and document list; it does not deliver the "
    "listed filing images.",
    "The same file number can exist in more than one registry, so canonical "
    "identity includes court and originating-registry codes.",
    "Registry start dates vary; an empty result does not cover periods before "
    "that registry's published electronic-record start date.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Queensland eCourts Supreme and District Court Civil Files",
    source_role="state_supreme_and_district_civil_case_index_and_docket",
    base_url=SEARCH_URL,
    dataset_id="queensland-ecourts-civil-files",
    metadata={
        "authority": "Queensland Courts",
        "country_code": "AU",
        "state_code": "QLD",
        "authentication": "none",
        "platform_family": "aspnet_webforms",
        "native_page_size": NATIVE_PAGE_SIZE,
        "native_result_ceiling": NATIVE_RESULT_CEILING,
        "official_guide_url": OFFICIAL_GUIDE_URL,
        "detail_url_is_direct": True,
        "document_delivery": "separate_official_search_and_copy_request",
        "complementary_source_ids": [
            route["source_id"] for route in COMPLEMENTARY_OFFICIAL_ROUTES
        ],
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="au-qld",
    name="Queensland, Australia",
    country_code="AU",
    state_code="QLD",
)


class QldECourtsSelectionError(ValueError):
    """A caller selector cannot be represented by the public source."""

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

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="query_selection",
            retryable=False,
            details=self.details,
        )


@dataclass(frozen=True)
class SearchCriteria:
    file_number: str | None = None
    category1: str | None = None
    category2: str | None = None
    category3: str | None = None
    originating_location: str | None = None
    current_location: str | None = None
    court: str | None = None
    listing_from: str | None = None
    listing_to: str | None = None
    last_company_name: str | None = None
    given_names: str | None = None
    party_role: str | None = None
    party_date_from: str | None = None
    second_last_company_name: str | None = None
    second_given_names: str | None = None
    second_party_role: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in vars(self).items()
            if value is not None and str(value).strip()
        }

    def has_selector(self) -> bool:
        return bool(self.to_dict())


@dataclass(frozen=True)
class SearchForm:
    action_url: str
    hidden_fields: Mapping[str, str]
    options: Mapping[str, Mapping[str, str]]
    schema_fingerprint: str


@dataclass(frozen=True)
class SearchParty:
    last_company_name: str
    first_name: str | None
    proceeding_type: str | None
    party_role: str | None
    date_filed_raw: str | None
    date_filed_iso: str | None

    def to_dict(self) -> dict[str, Any]:
        return vars(self)


@dataclass(frozen=True)
class CaseHit:
    file_number: str
    case_name: str
    court_code: str
    court_name: str
    originating_location_code: str
    originating_location: str
    current_location_code: str | None
    current_location: str | None
    related_file_count: int | None
    next_listing_date_raw: str | None
    next_listing_date_iso: str | None
    next_listing_type: str | None
    parties: tuple[SearchParty, ...]
    source_url: str

    @property
    def evidence_ref(self) -> str:
        return qld_evidence_ref(
            self.court_code,
            self.originating_location_code,
            self.file_number,
        )

    @property
    def canonical_ref(self) -> str:
        return qld_canonical_ref(
            self.court_code,
            self.originating_location_code,
            self.file_number,
        )

    @property
    def identity_key(self) -> str:
        return "|".join(
            (
                self.court_code,
                self.originating_location_code,
                self.file_number.casefold(),
            )
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "record_type": "court_case_search_hit",
            "canonical_ref": self.canonical_ref,
            "evidence_ref": self.evidence_ref,
            "file_number": self.file_number,
            "case_name": self.case_name,
            "court_code": self.court_code,
            "court_name": self.court_name,
            "originating_location_code": self.originating_location_code,
            "originating_location": self.originating_location,
            "current_location_code": self.current_location_code,
            "current_location": self.current_location,
            "related_file_count": self.related_file_count,
            "next_listing_date_raw": self.next_listing_date_raw,
            "next_listing_date_iso": self.next_listing_date_iso,
            "next_listing_type": self.next_listing_type,
            "parties": [party.to_dict() for party in self.parties],
            "source_url": self.source_url,
        }


@dataclass(frozen=True)
class SearchPage:
    url: str
    start_record: int
    end_record: int
    reported_total: int
    native_ceiling_reached: bool
    rows: tuple[CaseHit, ...]
    next_target: str | None
    hidden_fields: Mapping[str, str]
    schema_fingerprint: str


@dataclass(frozen=True)
class SearchBatch:
    criteria: SearchCriteria
    form: SearchForm
    first_page: SearchPage


@dataclass(frozen=True)
class CaseDetail:
    hit: CaseHit
    proceeding_type: str | None
    date_filed_raw: str | None
    date_filed_iso: str | None
    parties: tuple[Mapping[str, Any], ...]
    events: tuple[Mapping[str, Any], ...]
    documents: tuple[Mapping[str, Any], ...]
    related_files: tuple[Mapping[str, Any], ...]
    status_notices: tuple[str, ...]
    schema_fingerprint: str

    def to_record(self) -> dict[str, Any]:
        record = self.hit.to_record()
        record.update(
            {
                "record_type": "court_case",
                "proceeding_type": self.proceeding_type,
                "date_filed_raw": self.date_filed_raw,
                "date_filed_iso": self.date_filed_iso,
                "parties": [dict(value) for value in self.parties],
                "events": [dict(value) for value in self.events],
                "documents": [dict(value) for value in self.documents],
                "related_files": [
                    dict(value) for value in self.related_files
                ],
                "status_notices": list(self.status_notices),
                "schema_fingerprint": self.schema_fingerprint,
            }
        )
        return record


@dataclass(frozen=True)
class SearchCollection:
    hits: tuple[CaseHit, ...]
    partitions_fetched: int
    native_pages_fetched: int
    ceiling_splits: int
    unresolved_ceiling_partitions: tuple[Mapping[str, str], ...]
    duplicate_hits_removed: int
    caller_bound_reached: bool
    source_traversal_complete: bool

    def retrieval_metadata(self, client: QldECourtsClient) -> dict[str, Any]:
        return {
            "transport_requests": client.request_count,
            "partitions_fetched": self.partitions_fetched,
            "native_pages_fetched": self.native_pages_fetched,
            "ceiling_splits": self.ceiling_splits,
            "unresolved_ceiling_partitions": [
                dict(value) for value in self.unresolved_ceiling_partitions
            ],
            "duplicate_hits_removed": self.duplicate_hits_removed,
            "caller_bound_reached": self.caller_bound_reached,
            "source_traversal_complete": self.source_traversal_complete,
            "native_page_size": NATIVE_PAGE_SIZE,
            "native_result_ceiling": NATIVE_RESULT_CEILING,
        }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(
        str(value).replace("\xa0", " ").replace("\x00", "").split()
    ).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _source_schema_error(
    message: str,
    *,
    url: str,
    details: Mapping[str, Any] | None = None,
) -> SourceSchemaError:
    return SourceSchemaError(message, url=url, details=details)


def _qld_date(raw: str | None) -> str | None:
    value = _text(raw)
    if value is None:
        return None
    for pattern in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _source_date(value: str | None, field_name: str) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise QldECourtsSelectionError(
            "invalid_date",
            f"{field_name} must use YYYY-MM-DD",
            details={"field": field_name, "value": normalized},
        ) from exc
    return parsed.strftime("%d/%m/%Y")


def _file_parts(file_number: str) -> tuple[str, str]:
    match = FILE_NUMBER_RE.match(file_number)
    if match is None:
        raise QldECourtsSelectionError(
            "invalid_file_number",
            "Queensland eCourts file numbers must look like 6819/11",
            details={"file_number": file_number},
        )
    serial, raw_year = match.groups()
    if len(raw_year) == 2:
        year_value = int(raw_year)
        full_year = 1900 + year_value if year_value >= 90 else 2000 + year_value
    else:
        full_year = int(raw_year)
    return serial.upper(), str(full_year)


def qld_evidence_ref(
    court_code: str,
    location_code: str,
    file_number: str,
) -> str:
    """Return a slash-safe, registry-disambiguated evidence reference."""

    serial, year_value = _file_parts(file_number)
    court = _required_text(court_code, "court code").upper()
    location = _required_text(location_code, "location code").upper()
    return f"QLD-ECOURTS:{court}-{location}-{serial}-{year_value}"


def qld_canonical_ref(
    court_code: str,
    location_code: str,
    file_number: str,
) -> str:
    court = _required_text(court_code, "court code").upper()
    location = _required_text(location_code, "location code").upper()
    court_id = COURT_IDS.get(court, f"qld-{court.casefold()}-court")
    native_id = qld_evidence_ref(court, location, file_number).split(":", 1)[1]
    return canonical_court_ref(
        SOURCE_ID,
        court_id,
        file_number,
        native_id=native_id,
    )


def _options(select: Tag) -> dict[str, str]:
    return {
        str(option.get("value") or ""): _text(
            option.get_text(" ", strip=True)
        )
        or ""
        for option in select.find_all("option")
    }


def _table_headers(table: Tag) -> tuple[str, ...]:
    row = table.find("tr")
    if not isinstance(row, Tag):
        return ()
    return tuple(
        _text(cell.get_text(" ", strip=True)) or ""
        for cell in row.find_all(["th", "td"], recursive=False)
    )


def _table_data_rows(table: Tag) -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        rows.append(
            [_text(cell.get_text(" ", strip=True)) for cell in cells]
        )
    return rows


def _hidden_fields(form: Tag) -> dict[str, str]:
    return {
        str(field.get("name")): str(field.get("value") or "")
        for field in form.select("input[type=hidden][name]")
    }


def parse_search_form(html: str, url: str = SEARCH_URL) -> SearchForm:
    """Parse and validate the anonymous WebForms search contract."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if (
        "Party search" not in page_text
        or "Supreme and District Court - Search civil files" not in page_text
    ):
        raise _source_schema_error(
            "Queensland eCourts search-page identity changed",
            url=url,
        )
    form = soup.select_one("form#aspnetForm")
    if not isinstance(form, Tag):
        raise _source_schema_error(
            "Queensland eCourts search page lacks aspnetForm",
            url=url,
        )
    action_url = urljoin(url, str(form.get("action") or ""))
    if (
        urlparse(action_url).path.casefold()
        != urlparse(SEARCH_URL).path.casefold()
        or str(form.get("method") or "").casefold() != "post"
    ):
        raise _source_schema_error(
            "Queensland eCourts search form action or method changed",
            url=url,
            details={"action": action_url, "method": form.get("method")},
        )
    hidden = _hidden_fields(form)
    required_hidden = {"__VIEWSTATE", "__VIEWSTATEGENERATOR"}
    missing_hidden = sorted(required_hidden - hidden.keys())
    if missing_hidden:
        raise _source_schema_error(
            "Queensland eCourts search form lacks WebForms state",
            url=url,
            details={"missing_fields": missing_hidden},
        )
    missing_fields = [
        name
        for name in (*FORM_FIELDS.values(), SEARCH_BUTTON)
        if form.select_one(f'[name="{name}"]') is None
    ]
    if missing_fields:
        raise _source_schema_error(
            "Queensland eCourts search fields changed",
            url=url,
            details={"missing_fields": missing_fields},
        )

    selector_options: dict[str, dict[str, str]] = {}
    for key, field_name in SELECTOR_FIELDS.items():
        select = form.select_one(f'select[name="{field_name}"]')
        if not isinstance(select, Tag):
            raise _source_schema_error(
                f"Queensland eCourts {key} selector changed",
                url=url,
            )
        selector_options[key] = _options(select)
    if any(
        selector_options["court"].get(code) != label
        for code, label in COURTS.items()
    ):
        raise _source_schema_error(
            "Queensland eCourts court options changed",
            url=url,
            details={"observed": selector_options["court"]},
        )
    observed_locations = selector_options["originating_location"]
    if any(
        observed_locations.get(code) != label
        for code, label in LOCATIONS.items()
    ):
        raise _source_schema_error(
            "Queensland eCourts originating registry options changed",
            url=url,
            details={"observed": observed_locations},
        )
    schema = sha256_fingerprint(
        {
            "hidden_names": sorted(hidden),
            "fields": sorted(FORM_FIELDS.values()),
            "options": selector_options,
        }
    )
    return SearchForm(
        action_url=action_url,
        hidden_fields=hidden,
        options=selector_options,
        schema_fingerprint=schema,
    )


def _code_for_label(
    label: str | None,
    values: Mapping[str, str],
    field_name: str,
    *,
    url: str,
) -> str | None:
    normalized = _text(label)
    if normalized is None:
        return None
    matches = [
        code
        for code, display in values.items()
        if display.casefold() == normalized.casefold()
    ]
    if len(matches) != 1:
        raise _source_schema_error(
            f"Queensland eCourts returned an unknown {field_name}",
            url=url,
            details={"label": normalized},
        )
    return matches[0]


def _span_text(cell: Tag, suffix: str) -> str | None:
    span = cell.select_one(f'span[id$="_{suffix}"]')
    if not isinstance(span, Tag):
        return None
    return _text(span.get_text(" ", strip=True))


def _parse_search_hit(file_span: Tag, url: str) -> CaseHit:
    cell = file_span.find_parent("td")
    if not isinstance(cell, Tag):
        raise _source_schema_error(
            "Queensland eCourts result file row lost its containing cell",
            url=url,
        )
    file_number = _required_text(
        file_span.get_text(" ", strip=True),
        "file number",
    )
    case_name = _span_text(cell, "filename")
    court_name = _span_text(cell, "court")
    originating_location = _span_text(cell, "originatinglocation")
    if case_name is None or court_name is None or originating_location is None:
        raise _source_schema_error(
            "Queensland eCourts result row lacks case identity fields",
            url=url,
            details={"file_number": file_number},
        )
    court_code = _code_for_label(
        court_name,
        COURTS,
        "court",
        url=url,
    )
    originating_code = _code_for_label(
        originating_location,
        LOCATIONS,
        "originating registry",
        url=url,
    )
    if court_code is None or originating_code is None:
        raise _source_schema_error(
            "Queensland eCourts result row has blank case identity codes",
            url=url,
        )
    current_location = _span_text(cell, "currentlocation")
    current_code = _code_for_label(
        current_location,
        LOCATIONS,
        "current registry",
        url=url,
    )
    related_raw = _span_text(cell, "relatedfiles")
    related_count = (
        int(related_raw)
        if related_raw is not None and related_raw.isdigit()
        else None
    )
    party_table = cell.select_one('table[id$="_PartyGrid"]')
    if not isinstance(party_table, Tag):
        raise _source_schema_error(
            "Queensland eCourts result row lacks its party table",
            url=url,
            details={"file_number": file_number},
        )
    headers = _table_headers(party_table)
    if headers != SEARCH_PARTY_HEADERS:
        raise _source_schema_error(
            "Queensland eCourts result-party columns changed",
            url=url,
            details={
                "expected": SEARCH_PARTY_HEADERS,
                "observed": headers,
            },
        )
    parties = tuple(
        SearchParty(
            last_company_name=_required_text(row[0], "party name"),
            first_name=row[1],
            proceeding_type=row[2],
            party_role=row[3],
            date_filed_raw=row[4],
            date_filed_iso=_qld_date(row[4]),
        )
        for row in _table_data_rows(party_table)
        if len(row) == len(SEARCH_PARTY_HEADERS)
    )
    detail_url = _detail_url(
        file_number=file_number,
        court=court_code,
        location=originating_code,
    )
    listing_raw = _span_text(cell, "bookingdate")
    return CaseHit(
        file_number=file_number,
        case_name=case_name,
        court_code=court_code,
        court_name=court_name,
        originating_location_code=originating_code,
        originating_location=originating_location,
        current_location_code=current_code,
        current_location=current_location,
        related_file_count=related_count,
        next_listing_date_raw=listing_raw,
        next_listing_date_iso=_qld_date(listing_raw),
        next_listing_type=_span_text(cell, "eventtype"),
        parties=parties,
        source_url=detail_url,
    )


def parse_results_page(html: str, url: str = RESULTS_URL) -> SearchPage:
    """Parse one native result page, including its ceiling and pager state."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if (
        "Party search - results" not in page_text
        or "Supreme and District Court - Search civil files" not in page_text
    ):
        raise _source_schema_error(
            "Queensland eCourts result-page identity changed",
            url=url,
        )
    count_span = soup.select_one(
        "#ctl00_ContentPlaceHolder1_recordcounts"
    )
    count_match = (
        COUNT_RE.search(count_span.get_text(" ", strip=True))
        if isinstance(count_span, Tag)
        else None
    )
    if count_match is None:
        raise _source_schema_error(
            "Queensland eCourts result page lacks its record count",
            url=url,
        )
    start_record, end_record, reported_total = (
        int(value) for value in count_match.groups()
    )
    ceiling_panel = soup.select_one(
        "#ctl00_ContentPlaceHolder1_Result500Panel"
    )
    if not isinstance(ceiling_panel, Tag):
        raise _source_schema_error(
            "Queensland eCourts result page lacks its ceiling marker",
            url=url,
        )
    style = str(ceiling_panel.get("style") or "").replace(" ", "").casefold()
    native_ceiling = "display:none" not in style
    if native_ceiling and "more than 500 results" not in (
        _text(ceiling_panel.get_text(" ", strip=True)) or ""
    ).casefold():
        raise _source_schema_error(
            "Queensland eCourts ceiling marker text changed",
            url=url,
        )

    file_grid = soup.select_one("#ctl00_ContentPlaceHolder1_FileGrid")
    if not isinstance(file_grid, Tag):
        raise _source_schema_error(
            "Queensland eCourts result page lacks its file grid",
            url=url,
        )
    file_spans = file_grid.select('span[id$="_filenumber"]')
    rows = tuple(_parse_search_hit(span, url) for span in file_spans)
    expected_page_rows = 0 if reported_total == 0 else end_record - start_record + 1
    if len(rows) != expected_page_rows:
        raise _source_schema_error(
            "Queensland eCourts result count and file rows disagree",
            url=url,
            details={
                "reported_page_rows": expected_page_rows,
                "parsed_rows": len(rows),
            },
        )
    if reported_total == 0 and (
        "did not return any results" not in page_text.casefold()
    ):
        raise _source_schema_error(
            "Queensland eCourts empty-result marker changed",
            url=url,
        )

    next_target: str | None = None
    if end_record < reported_total:
        for anchor in file_grid.select('a[title="Next"]'):
            anchor_style = str(anchor.get("style") or "").replace(
                " ", ""
            ).casefold()
            if "display:none" in anchor_style:
                continue
            match = POSTBACK_RE.search(str(anchor.get("href") or ""))
            if match:
                next_target = match.group(1)
                break
        if next_target is None:
            raise _source_schema_error(
                "Queensland eCourts result pager lacks its next target",
                url=url,
                details={"end_record": end_record, "total": reported_total},
            )
    form = soup.select_one("form#aspnetForm")
    if not isinstance(form, Tag):
        raise _source_schema_error(
            "Queensland eCourts result page lacks aspnetForm",
            url=url,
        )
    hidden = _hidden_fields(form)
    if "__VIEWSTATE" not in hidden or "__VIEWSTATEGENERATOR" not in hidden:
        raise _source_schema_error(
            "Queensland eCourts result page lacks pager state",
            url=url,
        )
    schema = sha256_fingerprint(
        {
            "party_headers": SEARCH_PARTY_HEADERS,
            "hidden_names": sorted(hidden),
            "has_ceiling_panel": True,
            "native_page_size": NATIVE_PAGE_SIZE,
        }
    )
    return SearchPage(
        url=url,
        start_record=start_record,
        end_record=end_record,
        reported_total=reported_total,
        native_ceiling_reached=native_ceiling,
        rows=rows,
        next_target=next_target,
        hidden_fields=hidden,
        schema_fingerprint=schema,
    )


def _visible_status_notices(soup: BeautifulSoup) -> tuple[str, ...]:
    suffixes = (
        "TransferredStatusPanel",
        "ConsolidatedNonCarriagePanel",
        "CaveatStatusPanel",
    )
    notices: list[str] = []
    for suffix in suffixes:
        panel = soup.select_one(f'div[id$="{suffix}"]')
        if not isinstance(panel, Tag):
            continue
        style = str(panel.get("style") or "").replace(" ", "").casefold()
        if "display:none" in style:
            continue
        text = _text(panel.get_text(" ", strip=True))
        if text is not None:
            notices.append(text)
    return tuple(notices)


def _generic_table_rows(table: Tag) -> tuple[Mapping[str, Any], ...]:
    table_text = (_text(table.get_text(" ", strip=True)) or "").casefold()
    if "there are no related files" in table_text:
        return ()
    headers = _table_headers(table)
    if not headers or not any(headers) or table.find("th") is None:
        return ()
    keys = [
        re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
        or f"column_{index + 1}"
        for index, value in enumerate(headers)
    ]
    return tuple(
        {keys[index]: value for index, value in enumerate(row)}
        for row in _table_data_rows(table)
        if len(row) == len(keys)
    )


def parse_detail_page(
    html: str,
    url: str,
) -> CaseDetail | None:
    """Parse one direct eCourts case-detail page."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if "No such file found." in page_text:
        return None
    file_span = soup.select_one("#ctl00_ContentPlaceHolder1_filenumber")
    if not isinstance(file_span, Tag):
        raise _source_schema_error(
            "Queensland eCourts detail-page identity changed",
            url=url,
        )
    file_number = _required_text(
        file_span.get_text(" ", strip=True),
        "file number",
    )
    case_name_tag = soup.select_one("#ctl00_ContentPlaceHolder1_filename")
    court_tag = soup.select_one("#ctl00_ContentPlaceHolder1_court")
    origin_tag = soup.select_one(
        "#ctl00_ContentPlaceHolder1_originatinglocation"
    )
    current_tag = soup.select_one(
        "#ctl00_ContentPlaceHolder1_currentlocation"
    )
    if not all(
        isinstance(value, Tag)
        for value in (case_name_tag, court_tag, origin_tag)
    ):
        raise _source_schema_error(
            "Queensland eCourts detail page lacks case identity fields",
            url=url,
        )
    case_name = _required_text(
        case_name_tag.get_text(" ", strip=True),
        "case name",
    )
    court_name = _required_text(
        court_tag.get_text(" ", strip=True),
        "court",
    )
    origin_name = _required_text(
        origin_tag.get_text(" ", strip=True),
        "originating registry",
    )
    current_name = (
        _text(current_tag.get_text(" ", strip=True))
        if isinstance(current_tag, Tag)
        else None
    )
    court_code = _code_for_label(court_name, COURTS, "court", url=url)
    origin_code = _code_for_label(
        origin_name,
        LOCATIONS,
        "originating registry",
        url=url,
    )
    current_code = _code_for_label(
        current_name,
        LOCATIONS,
        "current registry",
        url=url,
    )
    if court_code is None or origin_code is None:
        raise _source_schema_error(
            "Queensland eCourts detail page has blank identity codes",
            url=url,
        )
    proceeding_tag = soup.select_one(
        "#ctl00_ContentPlaceHolder1_proceedingtype"
    )
    filed_tag = soup.select_one("#ctl00_ContentPlaceHolder1_datefiled")
    booking_tag = soup.select_one("#ctl00_ContentPlaceHolder1_bookingdate")
    filing_raw = (
        _text(filed_tag.get_text(" ", strip=True))
        if isinstance(filed_tag, Tag)
        else None
    )
    listing_raw = (
        _text(booking_tag.get_text(" ", strip=True))
        if isinstance(booking_tag, Tag)
        else None
    )

    party_table = soup.select_one("#ctl00_ContentPlaceHolder1_PartyGrid")
    event_table = soup.select_one("#ctl00_ContentPlaceHolder1_EventGrid")
    document_table = soup.select_one(
        "#ctl00_ContentPlaceHolder1_DocumentGrid"
    )
    if not all(
        isinstance(value, Tag)
        for value in (party_table, event_table, document_table)
    ):
        raise _source_schema_error(
            "Queensland eCourts detail tables changed",
            url=url,
        )
    expected_tables = (
        (party_table, DETAIL_PARTY_HEADERS, "party"),
        (event_table, EVENT_HEADERS, "event"),
        (document_table, DOCUMENT_HEADERS, "document"),
    )
    for table, expected, label in expected_tables:
        observed = _table_headers(table)
        if observed != expected:
            raise _source_schema_error(
                f"Queensland eCourts detail {label} columns changed",
                url=url,
                details={"expected": expected, "observed": observed},
            )

    parties = tuple(
        {
            "last_company_name": row[0],
            "first_name": row[1],
            "acn": row[2],
            "party_role": row[3],
            "representative": row[4],
        }
        for row in _table_data_rows(party_table)
        if len(row) == len(DETAIL_PARTY_HEADERS)
    )
    events = tuple(
        {
            "date_raw": row[0],
            "date_iso": _qld_date(row[0]),
            "event_type": row[1],
            "diary_type": row[2],
            "resource": row[3],
            "result": row[4],
        }
        for row in _table_data_rows(event_table)
        if len(row) == len(EVENT_HEADERS)
    )
    case_evidence_ref = qld_evidence_ref(
        court_code,
        origin_code,
        file_number,
    )
    documents: list[Mapping[str, Any]] = []
    for row in _table_data_rows(document_table):
        if len(row) != len(DOCUMENT_HEADERS):
            continue
        pages = int(row[5]) if row[5] and row[5].isdigit() else None
        document_ref = (
            f"{case_evidence_ref}:DOC-{row[0]}"
            if row[0]
            else case_evidence_ref
        )
        documents.append(
            {
                "evidence_ref": document_ref,
                "document_number": row[0],
                "date_filed_raw": row[1],
                "date_filed_iso": _qld_date(row[1]),
                "document_type": row[2],
                "description": row[3],
                "filed_on_behalf_of": row[4],
                "pages": pages,
                "document_available_online": False,
            }
        )
    related_table = soup.select_one(
        "#ctl00_ContentPlaceHolder1_RelatedFilesGrid"
    )
    related_files = (
        _generic_table_rows(related_table)
        if isinstance(related_table, Tag)
        else ()
    )
    search_parties = tuple(
        SearchParty(
            last_company_name=_required_text(
                value["last_company_name"],
                "party name",
            ),
            first_name=value["first_name"],
            proceeding_type=(
                _text(proceeding_tag.get_text(" ", strip=True))
                if isinstance(proceeding_tag, Tag)
                else None
            ),
            party_role=value["party_role"],
            date_filed_raw=filing_raw,
            date_filed_iso=_qld_date(filing_raw),
        )
        for value in parties
    )
    hit = CaseHit(
        file_number=file_number,
        case_name=case_name,
        court_code=court_code,
        court_name=court_name,
        originating_location_code=origin_code,
        originating_location=origin_name,
        current_location_code=current_code,
        current_location=current_name,
        related_file_count=len(related_files),
        next_listing_date_raw=listing_raw,
        next_listing_date_iso=_qld_date(listing_raw),
        next_listing_type=None,
        parties=search_parties,
        source_url=url,
    )
    schema = sha256_fingerprint(
        {
            "party_headers": DETAIL_PARTY_HEADERS,
            "event_headers": EVENT_HEADERS,
            "document_headers": DOCUMENT_HEADERS,
            "has_related_files": isinstance(related_table, Tag),
        }
    )
    return CaseDetail(
        hit=hit,
        proceeding_type=(
            _text(proceeding_tag.get_text(" ", strip=True))
            if isinstance(proceeding_tag, Tag)
            else None
        ),
        date_filed_raw=filing_raw,
        date_filed_iso=_qld_date(filing_raw),
        parties=parties,
        events=events,
        documents=tuple(documents),
        related_files=related_files,
        status_notices=_visible_status_notices(soup),
        schema_fingerprint=schema,
    )


def _detail_url(*, file_number: str, court: str, location: str) -> str:
    prepared = requests.Request(
        "GET",
        DETAIL_URL,
        params={
            "Location": location,
            "Court": court,
            "Filenumber": file_number,
        },
    ).prepare()
    return str(prepared.url)


def _resolve_option(
    requested: str | None,
    options: Mapping[str, str],
    field_name: str,
) -> str | None:
    value = _text(requested)
    if value is None:
        return None
    if value in options:
        return value
    matches = [
        code
        for code, label in options.items()
        if label and label.casefold() == value.casefold()
    ]
    if len(matches) == 1:
        return matches[0]
    raise QldECourtsSelectionError(
        "unknown_selector",
        f"Unknown Queensland eCourts {field_name}: {value}",
        details={
            "field": field_name,
            "requested": value,
            "available": {
                code: label for code, label in options.items() if code
            },
        },
    )


def _form_payload(
    criteria: SearchCriteria,
    form: SearchForm,
) -> dict[str, str]:
    payload = dict(form.hidden_fields)
    values = criteria.to_dict()
    for key, value in values.items():
        if key in SELECTOR_FIELDS:
            value = _resolve_option(
                value,
                form.options[key],
                key.replace("_", " "),
            )
            if value is None:
                continue
        payload[FORM_FIELDS[key]] = value
    payload[SEARCH_BUTTON] = "Search"
    return payload


class QldECourtsClient:
    """Persistent-session client for the official eCourts WebForms flow."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = rate_limiter or MinimumIntervalRateLimiter(
            minimum_interval
        )
        self.sleeper = sleeper
        self.user_agent = user_agent
        self.request_count = 0

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        last_error: BaseException | None = None
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
            **dict(kwargs.pop("headers", {})),
        }
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    **kwargs,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise TransportError(
                    f"Queensland eCourts request failed: {exc}",
                    url=url,
                    details={"attempts": attempt},
                ) from exc
            status = int(getattr(response, "status_code", 0))
            response_url = str(getattr(response, "url", url))
            if status in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                if status == 429:
                    raise RateLimitedHTTPError(
                        status,
                        url=response_url,
                        response_text=str(getattr(response, "text", "")),
                    )
                raise HTTPStatusError(
                    status,
                    url=response_url,
                    response_text=str(getattr(response, "text", "")),
                )
            if status in {401, 403}:
                raise RestrictedHTTPError(
                    status,
                    url=response_url,
                    response_text=str(getattr(response, "text", "")),
                )
            if status == 451:
                raise TermsBlockedHTTPError(
                    status,
                    url=response_url,
                    response_text=str(getattr(response, "text", "")),
                )
            if status in {404, 410}:
                raise SourceChangedHTTPError(
                    status,
                    url=response_url,
                    response_text=str(getattr(response, "text", "")),
                )
            if status < 200 or status >= 300:
                raise HTTPStatusError(
                    status,
                    url=response_url,
                    response_text=str(getattr(response, "text", "")),
                )
            content_type = str(
                getattr(response, "headers", {}).get("Content-Type", "")
            ).casefold()
            if content_type and "html" not in content_type:
                raise _source_schema_error(
                    "Queensland eCourts returned a non-HTML response",
                    url=response_url,
                    details={"content_type": content_type},
                )
            return response
        raise TransportError(
            f"Queensland eCourts request failed: {last_error}",
            url=url,
        )

    def load_search_form(self) -> SearchForm:
        response = self._request("GET", SEARCH_URL)
        return parse_search_form(
            str(getattr(response, "text", "")),
            str(getattr(response, "url", SEARCH_URL)),
        )

    def first_page(self, criteria: SearchCriteria) -> SearchBatch:
        form = self.load_search_form()
        response = self._request(
            "POST",
            form.action_url,
            data=_form_payload(criteria, form),
            allow_redirects=True,
        )
        page = parse_results_page(
            str(getattr(response, "text", "")),
            str(getattr(response, "url", RESULTS_URL)),
        )
        return SearchBatch(criteria=criteria, form=form, first_page=page)

    def next_page(self, page: SearchPage) -> SearchPage:
        if page.next_target is None:
            raise QldECourtsSelectionError(
                "no_next_page",
                "Queensland eCourts result page has no continuation",
            )
        payload = dict(page.hidden_fields)
        payload["__EVENTTARGET"] = page.next_target
        payload["__EVENTARGUMENT"] = ""
        response = self._request(
            "POST",
            page.url,
            data=payload,
            allow_redirects=True,
        )
        next_page = parse_results_page(
            str(getattr(response, "text", "")),
            str(getattr(response, "url", page.url)),
        )
        if next_page.start_record <= page.start_record:
            raise _source_schema_error(
                "Queensland eCourts pagination did not advance",
                url=page.url,
                details={
                    "previous_start": page.start_record,
                    "next_start": next_page.start_record,
                },
            )
        return next_page

    def detail(
        self,
        file_number: str,
        *,
        court: str,
        location: str,
    ) -> CaseDetail | None:
        url = _detail_url(
            file_number=file_number,
            court=court,
            location=location,
        )
        response = self._request("GET", url)
        return parse_detail_page(
            str(getattr(response, "text", "")),
            str(getattr(response, "url", url)),
        )


def _split_partition(
    criteria: SearchCriteria,
    form: SearchForm,
) -> tuple[SearchCriteria, ...]:
    split_order = (
        ("court", "court"),
        ("originating_location", "originating_location"),
        ("category1", "category1"),
    )
    for attribute, option_key in split_order:
        if getattr(criteria, attribute) is not None:
            continue
        values = [
            code for code in form.options[option_key] if _text(code) is not None
        ]
        if values:
            return tuple(
                replace(criteria, **{attribute: value})
                for value in values
            )
    if (
        criteria.last_company_name is not None
        and criteria.party_role is None
    ):
        values = [
            code
            for code in form.options["party_role"]
            if _text(code) is not None
        ]
        if values:
            return tuple(
                replace(criteria, party_role=value) for value in values
            )
    if (
        criteria.second_last_company_name is not None
        and criteria.second_party_role is None
    ):
        values = [
            code
            for code in form.options["second_party_role"]
            if _text(code) is not None
        ]
        if values:
            return tuple(
                replace(criteria, second_party_role=value)
                for value in values
            )
    return ()


def fetch_search(
    client: QldECourtsClient,
    criteria: SearchCriteria,
    *,
    limit: int | None = None,
) -> SearchCollection:
    """Fetch a caller-bounded or exhaustive, ceiling-aware search."""

    if not criteria.has_selector():
        raise QldECourtsSelectionError(
            "missing_criteria",
            "Search requires at least one file, party, date, court, registry, "
            "or proceeding selector",
        )
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0
    ):
        raise QldECourtsSelectionError(
            "invalid_limit",
            "--limit must be a positive integer",
        )

    pending: deque[SearchCriteria] = deque([criteria])
    seen_partitions: set[str] = set()
    hits: dict[str, CaseHit] = {}
    duplicate_hits = 0
    partitions_fetched = 0
    native_pages = 0
    ceiling_splits = 0
    unresolved: list[Mapping[str, str]] = []
    caller_bound = False

    def add_rows(rows: Sequence[CaseHit]) -> None:
        nonlocal duplicate_hits
        for row in rows:
            if row.identity_key in hits:
                duplicate_hits += 1
                continue
            hits[row.identity_key] = row

    while pending:
        partition = pending.popleft()
        partition_key = canonical_json(partition.to_dict())
        if partition_key in seen_partitions:
            continue
        seen_partitions.add(partition_key)
        batch = client.first_page(partition)
        partitions_fetched += 1
        native_pages += 1
        page = batch.first_page
        add_rows(page.rows)
        if limit is not None and len(hits) >= limit:
            caller_bound = (
                page.next_target is not None
                or page.native_ceiling_reached
                or bool(pending)
            )
            break

        if page.native_ceiling_reached:
            children = _split_partition(partition, batch.form)
            if children:
                ceiling_splits += 1
                pending.extend(children)
                continue
            unresolved.append(partition.to_dict())

        while page.next_target is not None:
            page = client.next_page(page)
            native_pages += 1
            add_rows(page.rows)
            if limit is not None and len(hits) >= limit:
                caller_bound = page.next_target is not None or bool(pending)
                break
        if caller_bound:
            break

    selected = tuple(hits.values())
    if limit is not None and len(selected) > limit:
        selected = selected[:limit]
        caller_bound = True
    source_complete = not caller_bound and not unresolved and not pending
    return SearchCollection(
        hits=selected,
        partitions_fetched=partitions_fetched,
        native_pages_fetched=native_pages,
        ceiling_splits=ceiling_splits,
        unresolved_ceiling_partitions=tuple(unresolved),
        duplicate_hits_removed=duplicate_hits,
        caller_bound_reached=caller_bound,
        source_traversal_complete=source_complete,
    )


def _criteria_from_args(args: argparse.Namespace) -> SearchCriteria:
    file_number = _text(getattr(args, "file_number", None))
    if file_number is not None:
        _file_parts(file_number)
    return SearchCriteria(
        file_number=file_number,
        category1=_text(getattr(args, "category", None)),
        originating_location=_text(getattr(args, "location", None)),
        current_location=_text(getattr(args, "current_location", None)),
        court=_text(getattr(args, "court", None)),
        listing_from=_source_date(
            getattr(args, "listing_from", None),
            "--listing-from",
        ),
        listing_to=_source_date(
            getattr(args, "listing_to", None),
            "--listing-to",
        ),
        last_company_name=_text(getattr(args, "party_name", None)),
        given_names=_text(getattr(args, "given_names", None)),
        party_role=_text(getattr(args, "party_role", None)),
        party_date_from=_source_date(
            getattr(args, "party_date_from", None),
            "--party-date-from",
        ),
        second_last_company_name=_text(
            getattr(args, "second_party_name", None)
        ),
        second_given_names=_text(
            getattr(args, "second_given_names", None)
        ),
        second_party_role=_text(
            getattr(args, "second_party_role", None)
        ),
    )


def _query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    requested_limit: int | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            metadata=dict(metadata or {}),
        ),
    )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    command = args.command
    if command == "search":
        criteria = _criteria_from_args(args)
        return _query(
            "search",
            {
                **criteria.to_dict(),
                "include_details": bool(args.include_details),
            },
            requested_limit=args.limit,
            metadata={
                "pagination": (
                    "caller_bound" if args.limit is not None else "exhaustive"
                ),
                "native_result_ceiling": NATIVE_RESULT_CEILING,
                "ceiling_strategy": (
                    "court_then_originating_registry_then_category_then_role"
                ),
            },
        )
    if command == "case":
        _file_parts(args.file_number)
        return _query(
            "case",
            {
                "file_number": args.file_number,
                "court": args.court,
                "originating_location": args.location,
            },
            metadata={"search_then_direct_detail": True},
        )
    if command == "detail":
        _file_parts(args.file_number)
        return _query(
            "detail",
            {
                "file_number": args.file_number,
                "court": args.court,
                "originating_location": args.location,
            },
            requested_limit=1,
        )
    if command == "probe":
        return _query(
            "probe",
            {
                "file_number": PROBE_FILE_NUMBER,
                "court": PROBE_COURT,
                "originating_location": PROBE_LOCATION,
            },
            requested_limit=1,
            metadata={"bounded_probe": True},
        )
    if command == "sources":
        return _query("sources", {}, metadata={"network_required": False})
    raise QldECourtsSelectionError(
        "unknown_command",
        f"Unknown command: {command}",
    )


def _source_records() -> list[dict[str, Any]]:
    primary = {
        "source_id": SOURCE_ID,
        "name": SOURCE_METADATA.name,
        "role": SOURCE_METADATA.source_role,
        "url": SEARCH_URL,
        "authority": "Queensland Courts",
        "coverage": (
            "Supreme and District Court civil files; electronic start date "
            "varies by registry"
        ),
        "access": "anonymous_webforms",
        "native_page_size": NATIVE_PAGE_SIZE,
        "native_result_ceiling": NATIVE_RESULT_CEILING,
        "delivers": [
            "case identity",
            "parties and ACNs",
            "representatives",
            "events",
            "document-list metadata",
        ],
        "does_not_deliver": ["filing images"],
    }
    return [primary, *[dict(route) for route in COMPLEMENTARY_OFFICIAL_ROUTES]]


def _partial_ceiling_result(
    query: PublicRecordsQuery,
    records: Sequence[Mapping[str, Any]],
    collection: SearchCollection,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.PARTIAL,
        [
            PublicRecordsError(
                code="native_result_ceiling",
                message=(
                    "One or more fully partitioned eCourts searches still "
                    "exceeded the source's 500-result ceiling"
                ),
                category="source_limit",
                retryable=False,
                details={
                    "native_result_ceiling": NATIVE_RESULT_CEILING,
                    "unresolved_partitions": [
                        dict(value)
                        for value in collection.unresolved_ceiling_partitions
                    ],
                },
            )
        ],
        records=records,
        warnings=warnings,
    )


def _search_result(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: QldECourtsClient,
) -> PublicRecordsResult:
    criteria = _criteria_from_args(args)
    collection = fetch_search(client, criteria, limit=args.limit)
    retrieval = collection.retrieval_metadata(client)
    records: list[dict[str, Any]] = []
    detail_errors: list[PublicRecordsError] = []
    for hit in collection.hits:
        if not args.include_details:
            record = hit.to_record()
        else:
            try:
                detail = client.detail(
                    hit.file_number,
                    court=hit.court_code,
                    location=hit.originating_location_code,
                )
            except PublicRecordsHTTPError as exc:
                detail_errors.append(exc.to_contract_error())
                record = hit.to_record()
                record["detail_retrieval_error"] = exc.to_contract_error().to_dict()
            else:
                record = (
                    detail.to_record() if detail is not None else hit.to_record()
                )
                if detail is None:
                    detail_errors.append(
                        PublicRecordsError(
                            code="detail_missing_after_search",
                            message=(
                                "A case returned by search had no direct "
                                "detail page"
                            ),
                            category="source_consistency",
                            retryable=False,
                            details={"source_url": hit.source_url},
                        )
                    )
        record["retrieval"] = retrieval
        records.append(record)

    warnings = list(SOURCE_WARNINGS)
    if collection.caller_bound_reached:
        warnings.append(
            "Traversal stopped at the caller-selected --limit; this is a "
            "caller bound, not the source's 500-result ceiling."
        )
    if detail_errors:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            detail_errors,
            records=records,
            warnings=warnings,
        )
    if collection.unresolved_ceiling_partitions:
        return _partial_ceiling_result(
            query,
            records,
            collection,
            warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        warnings=warnings,
    )


def _case_result(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    client: QldECourtsClient,
) -> PublicRecordsResult:
    criteria = SearchCriteria(
        file_number=args.file_number,
        court=_text(args.court),
        originating_location=_text(args.location),
    )
    collection = fetch_search(client, criteria)
    records: list[dict[str, Any]] = []
    for hit in collection.hits:
        detail = client.detail(
            hit.file_number,
            court=hit.court_code,
            location=hit.originating_location_code,
        )
        if detail is not None:
            record = detail.to_record()
            record["retrieval"] = collection.retrieval_metadata(client)
            records.append(record)
    if collection.unresolved_ceiling_partitions:
        return _partial_ceiling_result(
            query,
            records,
            collection,
            SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: QldECourtsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Queensland eCourts operation."""

    query = build_query(args)
    source_client = client
    owns_client = False
    if args.command not in {"sources"} and source_client is None:
        source_client = QldECourtsClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
        )
        owns_client = True
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                _source_records(),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "search":
            result = _search_result(args, query, source_client)
        elif args.command == "case":
            result = _case_result(args, query, source_client)
        elif args.command in {"detail", "probe"}:
            file_number = (
                PROBE_FILE_NUMBER
                if args.command == "probe"
                else args.file_number
            )
            court = (
                PROBE_COURT if args.command == "probe" else args.court
            )
            location = (
                PROBE_LOCATION if args.command == "probe" else args.location
            )
            detail = source_client.detail(
                file_number,
                court=court,
                location=location,
            )
            result = PublicRecordsResult.success(
                query,
                [] if detail is None else [detail.to_record()],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise QldECourtsSelectionError(
                "unknown_command",
                f"Unknown command: {args.command}",
            )
    except QldECourtsSelectionError as exc:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [exc.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except PublicRecordsHTTPError as exc:
        result = failure_result(
            query,
            exc,
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client and source_client is not None:
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


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help=(
            "Minimum seconds between source requests "
            f"(default: {DEFAULT_MINIMUM_INTERVAL:g})"
        ),
    )
    add_output_args(parser)


def _add_search_selectors(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--file-number", help="Source file number, e.g. 6819/11")
    parser.add_argument(
        "--court",
        help="Court code or label (SUPRE/Supreme or DISTR/District)",
    )
    parser.add_argument(
        "--location",
        help="Originating registry code or label (e.g. BRISB or Brisbane)",
    )
    parser.add_argument(
        "--current-location",
        help="Current registry code or label",
    )
    parser.add_argument(
        "--category",
        help="Proceeding Category 1 code or label (e.g. CLM or Claim)",
    )
    parser.add_argument("--party-name", help="Last or company name")
    parser.add_argument("--given-names", help="Given name(s) for the first party")
    parser.add_argument("--party-role", help="First-party role code or label")
    parser.add_argument(
        "--party-date-from",
        help="First-party filing date lower bound, YYYY-MM-DD",
    )
    parser.add_argument("--second-party-name", help="Second last or company name")
    parser.add_argument(
        "--second-given-names",
        help="Given name(s) for the second party",
    )
    parser.add_argument(
        "--second-party-role",
        help="Second-party role code or label",
    )
    parser.add_argument(
        "--listing-from",
        help="Listing date lower bound, YYYY-MM-DD",
    )
    parser.add_argument(
        "--listing-to",
        help="Listing date upper bound, YYYY-MM-DD",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search civil files; exhaustive unless --limit is supplied",
    )
    _add_search_selectors(search)
    search.add_argument(
        "--include-details",
        action="store_true",
        help="Fetch parties, events, and document lists for every returned file",
    )
    search.add_argument(
        "--limit",
        type=int,
        help="Explicit caller bound; omitted means exhaustive traversal",
    )
    _add_runtime_args(search)

    case = subparsers.add_parser(
        "case",
        help="Search an exact file number and retrieve every matching detail",
    )
    case.add_argument("file_number")
    case.add_argument("--court", help="Optional court code or label")
    case.add_argument(
        "--location",
        help="Optional originating registry code or label",
    )
    _add_runtime_args(case)

    detail = subparsers.add_parser(
        "detail",
        help="Retrieve one direct file detail by complete native identity",
    )
    detail.add_argument("file_number")
    detail.add_argument("--court", required=True, choices=tuple(COURTS))
    detail.add_argument("--location", required=True, choices=tuple(LOCATIONS))
    _add_runtime_args(detail)

    sources = subparsers.add_parser(
        "sources",
        help="Show primary and complementary official routes",
    )
    _add_runtime_args(sources)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded exact-file live probe",
    )
    _add_runtime_args(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Queensland eCourts {args.command}",
        result_count=len(result.records),
    ):
        return
    print(json.dumps(payload, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = execute(args)
    except QldECourtsSelectionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    _emit(result, args)
    return 0 if result.status not in {
        ResultStatus.UNAVAILABLE,
        ResultStatus.RESTRICTED,
        ResultStatus.RATE_LIMITED,
        ResultStatus.TERMS_BLOCKED,
        ResultStatus.SOURCE_CHANGED,
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
