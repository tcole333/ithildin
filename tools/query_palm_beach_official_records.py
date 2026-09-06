#!/usr/bin/env python3
"""Retrieve Palm Beach County Official Records by exact clerk identifiers.

The Clerk's Landmark Web portal currently presents reCAPTCHA for broad
name, parcel, legal-description, case-number, and date searches.  After the
normal public acknowledgement, however, the portal's own document viewer
supports deterministic navigation by instrument number or book/page.  This
adapter uses those exact routes and preserves the separately observed image
state for each record.

Examples:
    uv run python tools/query_palm_beach_official_records.py instrument \
        19860255822 --output /tmp/pbc-instrument.json
    uv run python tools/query_palm_beach_official_records.py book-page \
        5021 1011 --output /tmp/pbc-book-page.json
    uv run python tools/query_palm_beach_official_records.py image \
        --instrument 19860255822 --image-page 1 \
        --document-output /tmp/pbc-19860255822-page-1.png \
        --output /tmp/pbc-image-receipt.json
    uv run python tools/query_palm_beach_official_records.py routes --json
    uv run python tools/query_palm_beach_official_records.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

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
    )
    from tools.public_records_store import canonical_property_ref
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
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-fl-palm-beach-official-records"
COUNTY_GEOID = "12099"
BASE_URL = "https://erec.mypalmbeachclerk.com"
HOME_URL = f"{BASE_URL}/"
DISCLAIMER_URL = f"{BASE_URL}/Search/SetDisclaimer"
CAPTCHA_STATE_URL = f"{BASE_URL}/Search/ShowCaptcha"
DIRECT_CFN_URL = f"{BASE_URL}/Document/DirectNavByCFN"
DIRECT_BOOK_PAGE_URL = f"{BASE_URL}/Document/DirectNavByBookPage"
DETAIL_URL = f"{BASE_URL}/Document/Index"
SET_SESSION_DOCUMENT_URL = f"{BASE_URL}/Document/SetSessionDocumentId"
DOCUMENT_DETAILS_URL = f"{BASE_URL}/Document/GetDocumentDetails"
DOCUMENT_INFORMATION_URL = f"{BASE_URL}/Document/GetDocumentInformation"
IMAGE_URL = f"{BASE_URL}/Document/GetDocumentImage/"
OFFICIAL_RECORDS_URL = (
    "https://www.mypalmbeachclerk.com/records/official-records"
)
FTP_INDEX_URL = (
    "https://www.mypalmbeachclerk.com/records/official-records/"
    "electronic-distribution-index-service"
)
CD_ARCHIVE_URL = (
    "https://www.mypalmbeachclerk.com/records/official-records/"
    "official-record-index-and-images-on-cd-rom"
)
RECORDS_SERVICE_URL = (
    "https://www.mypalmbeachclerk.com/records/copies-records-research/"
)
PROPERTY_APPRAISER_URL = "https://pbcpao.gov/"
TAX_COLLECTOR_URL = "https://www.pbctax.gov/"
TAX_DEED_URL = "https://taxdeed.mypalmbeachclerk.com/"
ECASEVIEW_URL = "https://appsgp.mypalmbeachclerk.com/ecaseview"
FL_DOR_URL = (
    "https://www.floridarevenue.com/property/Pages/"
    "DataPortal_RequestAssessmentRollGISData.aspx"
)

USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF = 0.5

SENTINEL_INSTRUMENT = "19860255822"
SENTINEL_DOCUMENT_ID = "6402430"
SENTINEL_BOOK = 5021
SENTINEL_PAGE = 1011
SENTINEL_DOC_TYPE = "DEED"
SENTINEL_RECORD_DATE = "09/30/1986"

BOOK_TYPES: Mapping[str, Mapping[str, Any]] = {
    "all": {"id": 8, "label": "All Books"},
    "backpost": {"id": 12, "label": "BACKPOST"},
    "customer-request": {"id": 10, "label": "CUSTOMER REQUEST"},
    "documents-filed": {"id": 9, "label": "DOCUMENTS FILED"},
    "marriage-license": {"id": 1, "label": "MARRIAGE LICENSE"},
    "misc-plat": {"id": 2, "label": "MISC. PLAT"},
    "official-records": {"id": 3, "label": "OFFICIAL RECORDS"},
    "plat": {"id": 4, "label": "PLAT"},
    "road-plat": {"id": 5, "label": "ROAD PLAT"},
    "sfwmd": {"id": 6, "label": "SFWMD"},
    "search-reports": {"id": 13, "label": "Search Reports"},
    "water-plat": {"id": 7, "label": "WATER PLAT"},
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Palm Beach County Official Records Search",
    source_role="recorder_instrument_detail_and_document_images",
    base_url=HOME_URL,
    dataset_id="landmark-web-official-records",
    metadata={
        "authority": (
            "Palm Beach County Clerk of the Circuit Court and Comptroller"
        ),
        "platform_family": "landmark_web_official_records",
        "record_identity_key": "instrument_number",
        "coverage_statement": "online document images since 1968",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Palm Beach County, Florida",
    state_code="FL",
    county_fips=COUNTY_GEOID,
    locality="Palm Beach County",
)

SOURCE_WARNINGS = (
    (
        "The record fields are Clerk index metadata; a retrieved document page "
        "is a separate evidence artifact."
    ),
    (
        "Broad party, parcel, legal, case, and date discovery currently uses "
        "the Clerk's interactive reCAPTCHA flow."
    ),
)


class PalmBeachRecorderError(RuntimeError):
    """Official recorder request or source-contract error."""


class PalmBeachRecorderSourceChanged(PalmBeachRecorderError):
    """The official route or returned schema no longer matches the probe."""


class PalmBeachRecorderTransportError(PalmBeachRecorderError):
    """The official source could not be reached after bounded retries."""


class PalmBeachRecorderRateLimited(PalmBeachRecorderError):
    """The official source returned HTTP 429 after bounded retries."""


class PalmBeachRecorderHTTPError(PalmBeachRecorderError):
    """The official source returned a non-success response."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(
            f"Palm Beach Official Records returned HTTP {status_code}: {url}"
        )


class PalmBeachImageUnavailable(PalmBeachRecorderError):
    """A located record has no publicly retrievable image for this request."""

    def __init__(
        self,
        message: str,
        *,
        record: Mapping[str, Any],
    ) -> None:
        self.record = dict(record)
        super().__init__(message)


@dataclass(frozen=True)
class DocumentImage:
    """Validated public image response for one document page."""

    content: bytes
    media_type: str
    page_number: int
    sha256: str


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "get_text"):
        text = value.get_text(" ", strip=True)
    else:
        text = str(value)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if cleaned and cleaned not in seen:
            result.append(cleaned)
            seen.add(cleaned)
    return result


def _split_cell_values(cell: Tag) -> list[str]:
    values = [
        _clean_text(value)
        for value in cell.get_text("\n", strip=True).splitlines()
    ]
    return _unique(values)


def _iso_date(value: str) -> str | None:
    for pattern in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _currency_value(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _instrument_source_url(
    *,
    book_type: str | None,
    book: str | None,
    page: str | None,
) -> str:
    if book_type == "O" and book and page:
        query = urlencode(
            {
                "Key": "Assessor",
                "booknumber": book,
                "booktype": book_type,
                "pagenumber": page,
            }
        )
        return f"{BASE_URL}/Search/DocumentAndInfoByBookPage?{query}"
    return HOME_URL


def parse_document_detail(
    html: str,
    *,
    document_id: str,
) -> dict[str, Any]:
    """Normalize the Clerk's detail-view HTML for one exact instrument."""
    soup = BeautifulSoup(html, "html.parser")
    if "Session has Expired" in _clean_text(soup):
        raise PalmBeachRecorderSourceChanged(
            "the detail route returned a session-expired page"
        )

    source_fields: dict[str, list[str]] = {}
    source_cells: dict[str, Tag] = {}
    for row in soup.find_all("tr"):
        label = row.find("label")
        cells = row.find_all("td", recursive=False)
        if label is None or len(cells) < 2:
            continue
        field_name = _clean_text(label).rstrip(":").strip()
        if not field_name:
            continue
        values = _split_cell_values(cells[-1])
        source_fields[field_name] = values
        source_cells[field_name] = cells[-1]

    instrument_values = source_fields.get("Instrument #", [])
    if not instrument_values or not re.fullmatch(r"\d+", instrument_values[0]):
        raise PalmBeachRecorderSourceChanged(
            "document detail is missing a numeric instrument number"
        )
    instrument_number = instrument_values[0]

    book_type: str | None = None
    book: str | None = None
    page: str | None = None
    book_page_raw = next(iter(source_fields.get("Book/Page", [])), None)
    if book_page_raw:
        match = re.fullmatch(
            r"(?P<book_type>\S+)\s+(?P<book>\d+)\s*/\s*(?P<page>\d+)",
            book_page_raw,
        )
        if match:
            book_type = match.group("book_type")
            book = match.group("book")
            page = match.group("page")

    record_date_raw = next(
        iter(source_fields.get("Record Date", [])),
        None,
    )
    doc_type = next(iter(source_fields.get("Doc Type", [])), None)
    page_count_raw = next(
        iter(source_fields.get("Number of Pages", [])),
        None,
    )
    name_count_raw = next(
        iter(source_fields.get("Number of Names", [])),
        None,
    )

    image_match = re.search(r"\bvar\s+imageCount\s*=\s*(\d+)\s*;", html)
    image_page_count = int(image_match.group(1)) if image_match else None
    if image_page_count is None:
        raise PalmBeachRecorderSourceChanged(
            "document detail is missing its image-count state"
        )

    grantors = source_fields.get("Grantor", [])
    grantees = source_fields.get("Grantee", [])
    parties = [
        {"name": name, "role": "grantor", "raw_role": "Grantor"}
        for name in grantors
    ]
    parties.extend(
        {"name": name, "role": "grantee", "raw_role": "Grantee"}
        for name in grantees
    )

    parcel_values: list[str] = []
    property_links: dict[str, str] = {}
    for source_label in ("PCN", "Parcel ID"):
        cell = source_cells.get(source_label)
        if cell is None:
            continue
        for anchor in cell.find_all("a", href=True):
            title = _clean_text(anchor.get("title", "")).casefold()
            link_text = _clean_text(anchor)
            if "link to parcel" in title and link_text:
                parcel_values.append(link_text)
            if "property appraiser" in title:
                property_links["property_appraiser"] = str(anchor["href"])
            if "tax collector" in title:
                property_links["tax_collector"] = str(anchor["href"])
        if not parcel_values:
            parcel_values.extend(source_fields.get(source_label, []))
    parcel_ids = _unique(parcel_values)
    normalized_parcel_ids = _unique(
        [re.sub(r"[^0-9A-Za-z]", "", value) for value in parcel_ids]
    )

    legal_descriptions = source_fields.get("Doc. Legals", [])
    case_number = next(iter(source_fields.get("Case Number", [])), None)
    consideration_label = next(
        (
            label
            for label in source_fields
            if "consideration" in label.casefold()
        ),
        None,
    )
    consideration_raw = (
        next(iter(source_fields.get(consideration_label, [])), None)
        if consideration_label
        else None
    )

    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "instrument",
        instrument_number,
    )
    source_url = _instrument_source_url(
        book_type=book_type,
        book=book,
        page=page,
    )

    return {
        "source_id": SOURCE_ID,
        "record_kind": "recorded_instrument",
        "record_scope": "clerk_index_metadata_and_online_image_state",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "native_document_id": str(document_id),
        "instrument_number": instrument_number,
        "document_number": instrument_number,
        "book_type": book_type,
        "book": book,
        "page": page,
        "book_page_raw": book_page_raw,
        "recording_date": _iso_date(record_date_raw or ""),
        "recording_date_raw": record_date_raw,
        "document_type": doc_type,
        "page_count": (
            int(page_count_raw)
            if page_count_raw and page_count_raw.isdigit()
            else None
        ),
        "indexed_name_count": (
            int(name_count_raw)
            if name_count_raw and name_count_raw.isdigit()
            else None
        ),
        "consideration": _currency_value(consideration_raw),
        "consideration_raw": consideration_raw,
        "consideration_label": consideration_label,
        "grantors": grantors,
        "grantees": grantees,
        "parties": parties,
        "case_number": case_number,
        "parcel_ids": parcel_ids,
        "parcel_ids_normalized": normalized_parcel_ids,
        "legal_descriptions": legal_descriptions,
        "property_links": property_links,
        "image_access": {
            "status": (
                "available_online"
                if image_page_count > 0
                else "unavailable_online"
            ),
            "online_page_count": image_page_count,
            "media_type_observed": (
                "image/png" if image_page_count > 0 else None
            ),
            "endpoint": IMAGE_URL,
            "record_specific": True,
        },
        "source_locator": {
            "document_id": str(document_id),
            "instrument_number": instrument_number,
            "book_type": book_type,
            "book": book,
            "page": page,
        },
        "source_url": source_url,
        "jurisdiction": {
            "geoid": COUNTY_GEOID,
            "name": "Palm Beach County, Florida",
            "state_code": "FL",
        },
        "source_fields": source_fields,
    }


def source_routes() -> dict[str, Any]:
    """Return verified discovery, detail, image, bulk, and substitute routes."""
    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_access_routes",
        "native_document_id": "verified-routes-2026-07-30",
        "as_observed": "2026-07-30",
        "official_record_portal": {
            "url": HOME_URL,
            "coverage": {
                "digital_document_images": "1968-present",
                "marriage_license_listings": "1909-present",
                "plats_and_right_of_way_maps": "late-1800s-present",
            },
            "exact_machine_routes": {
                "instrument_number": DIRECT_CFN_URL,
                "book_page": DIRECT_BOOK_PAGE_URL,
                "set_session_document": SET_SESSION_DOCUMENT_URL,
                "document_details": DOCUMENT_DETAILS_URL,
                "document_information": DOCUMENT_INFORMATION_URL,
                "combined_detail_view": DETAIL_URL,
                "image": IMAGE_URL,
            },
            "interactive_discovery": {
                "selectors": [
                    "party_name",
                    "document_type",
                    "case_number",
                    "book_page",
                    "consideration",
                    "parcel_id",
                    "record_date",
                    "instrument_number",
                    "legal_description",
                    "advanced_legal",
                    "marriage",
                ],
                "captcha_observed": True,
                "result_choices": [200, 700, 3000, 5000, 10000],
                "index_groups_optional": True,
            },
            "record_states": {
                "provisional_marker": "I",
                "verified_marker": "V",
                "typical_verification_lag": "within 3 business days",
                "image_availability": "record-specific",
            },
        },
        "complementary_routes": [
            {
                "source_id": (
                    "us-fl-palm-beach-official-records-daily-index"
                ),
                "kind": "paid_daily_official_index",
                "url": FTP_INDEX_URL,
                "relationship": "bulk_discovery_without_images",
                "join_keys": [
                    "instrument_number",
                    "book_page",
                    "party_name",
                    "legal_description",
                    "linked_document",
                ],
                "format": "pipe-delimited daily .dat",
                "record_types": [
                    "document_header",
                    "party",
                    "legal_description",
                    "linked_document",
                    "cross_footing_trailer",
                ],
                "content": "new and edited verified recordings",
                "retention": "not less than 45 days",
                "images_included": False,
                "annual_fee_usd": 600,
                "prorated_monthly_fee_usd": 50,
            },
            {
                "source_id": (
                    "us-fl-palm-beach-official-records-cd-archive"
                ),
                "kind": "official_index_and_images_cd_archive",
                "url": CD_ARCHIVE_URL,
                "relationship": "historical_bulk_and_image_complement",
                "join_keys": ["instrument_number", "book_page"],
                "coverage": "1968-present",
                "index_price_usd_per_year": 40,
                "index_price_usd_per_decade": 400,
                "image_price_usd_per_book": 20,
            },
            {
                "source_id": "us-fl-palm-beach-records-service",
                "kind": "clerk_records_service",
                "url": RECORDS_SERVICE_URL,
                "relationship": (
                    "search_copy_certification_and_unavailable_image_complement"
                ),
                "join_keys": [
                    "party_name",
                    "legal_description",
                    "instrument_number",
                    "book_page",
                    "recording_period",
                ],
                "routes": ["online", "phone", "mail", "in_person"],
            },
            {
                "source_id": "us-fl-palm-beach-property-appraiser",
                "kind": "palm_beach_property_appraiser",
                "url": PROPERTY_APPRAISER_URL,
                "relationship": "parcel_owner_value_and_sale_context",
                "join_keys": [
                    "parcel_id",
                    "owner_name",
                    "property_address",
                    "sale_history",
                ],
            },
            {
                "kind": "florida_dor_property_bulk",
                "source_id": "us-fl-dor-property-roll",
                "tool": "tools/query_fl_dor_property.py",
                "url": FL_DOR_URL,
                "relationship": "state_bulk_roll_sales_and_geometry_context",
                "join_keys": ["parcel_id", "owner_name", "sale_date"],
            },
            {
                "source_id": "us-fl-palm-beach-tax-collector",
                "kind": "palm_beach_tax_collector",
                "url": TAX_COLLECTOR_URL,
                "relationship": "property_tax_and_delinquency_context",
                "join_keys": ["parcel_id", "property_address"],
            },
            {
                "source_id": "us-fl-palm-beach-tax-deeds",
                "kind": "palm_beach_tax_deeds",
                "url": TAX_DEED_URL,
                "relationship": "tax_deed_case_sale_and_document_complement",
                "join_keys": [
                    "parcel_id",
                    "owner_name",
                    "tax_deed_case_number",
                    "certificate_number",
                ],
            },
            {
                "kind": "palm_beach_ecaseview",
                "source_id": "us-fl-palm-beach-ecaseview",
                "tool": "tools/query_palm_beach_courts.py",
                "url": ECASEVIEW_URL,
                "relationship": "underlying_trial_case_and_docket_complement",
                "join_keys": ["case_number", "party_name", "judgment_date"],
            },
        ],
        "online_image_exceptions": {
            "effective_date": "2002-06-05",
            "document_types": [
                "death_certificates",
                "military_records",
                "court_records_relating_to_family",
                "guardianship",
                "juvenile",
                "mental_health",
                "probate",
            ],
            "fallback": RECORDS_SERVICE_URL,
        },
    }


class PalmBeachRecorderClient:
    """Session-aware client for verified Landmark exact-record routes."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        sleeper: Any = time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/json,image/png,*/*;q=0.8"
                    ),
                }
            )
        self.timeout = timeout
        self.minimum_interval = max(0.0, minimum_interval)
        self.max_attempts = max(1, max_attempts)
        self.retry_backoff = max(0.0, retry_backoff)
        self.sleeper = sleeper
        self._last_request_at: float | None = None
        self._accepted = False
        self.request_count = 0

    def _wait(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.minimum_interval - (
            time.monotonic() - self._last_request_at
        )
        if remaining > 0:
            self.sleeper(remaining)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        allow_redirects: bool = True,
        accepted_statuses: set[int] | None = None,
    ) -> Any:
        last_error: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            self._wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    params=dict(params or {}),
                    data=dict(data or {}),
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                )
            except (requests.RequestException, OSError, TimeoutError) as error:
                last_error = error
                self._last_request_at = time.monotonic()
                if attempt >= self.max_attempts:
                    raise PalmBeachRecorderTransportError(
                        f"request failed after {attempt} attempts: {error}"
                    ) from error
                self.sleeper(self.retry_backoff * (2 ** (attempt - 1)))
                continue

            self._last_request_at = time.monotonic()
            status_code = int(getattr(response, "status_code", 0))
            if status_code in {429, 500, 502, 503, 504}:
                if attempt < self.max_attempts:
                    self.sleeper(self.retry_backoff * (2 ** (attempt - 1)))
                    continue
                if status_code == 429:
                    raise PalmBeachRecorderRateLimited(
                        "Palm Beach Official Records rate limited the request"
                    )
            if accepted_statuses is not None and status_code in accepted_statuses:
                return response
            if status_code < 200 or status_code >= 300:
                raise PalmBeachRecorderHTTPError(status_code, url)
            return response

        raise PalmBeachRecorderTransportError(
            f"request failed: {last_error}"
        )

    def accept_disclaimer(self) -> None:
        """Start a public session and record the portal acknowledgement."""
        if self._accepted:
            return
        home = self._request("GET", HOME_URL)
        home_text = str(getattr(home, "text", ""))
        if (
            "Landmark Web Official Records Search" not in home_text
            or "/Search/SetDisclaimer" not in home_text
        ):
            raise PalmBeachRecorderSourceChanged(
                "portal home page is missing Landmark disclaimer markers"
            )
        self._request("POST", DISCLAIMER_URL, data={})
        self._accepted = True

    @staticmethod
    def _document_id(response: Any, route_name: str) -> str | None:
        value = _clean_text(getattr(response, "text", ""))
        if not value:
            return None
        if not re.fullmatch(r"\d+", value):
            raise PalmBeachRecorderSourceChanged(
                f"{route_name} returned a non-numeric document identifier"
            )
        return value

    def fetch_detail(self, document_id: str) -> dict[str, Any]:
        self._request(
            "POST",
            SET_SESSION_DOCUMENT_URL,
            data={"documentId": str(document_id)},
        )
        self._request(
            "POST",
            DETAIL_URL,
            data={
                "id": str(document_id),
                "row": "0",
                "navigationType": "",
            },
            allow_redirects=False,
            accepted_statuses={200, 302},
        )
        information = self._request(
            "POST",
            DOCUMENT_INFORMATION_URL,
            data={"id": str(document_id)},
        )
        details = self._request(
            "POST",
            DOCUMENT_DETAILS_URL,
            data={
                "id": str(document_id),
                "index": "1",
            },
        )
        combined_html = (
            str(getattr(details, "text", ""))
            + "\n"
            + str(getattr(information, "text", ""))
        )
        return parse_document_detail(
            combined_html,
            document_id=str(document_id),
        )

    def instrument(self, instrument_number: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"\d+", instrument_number):
            raise PalmBeachRecorderError(
                "instrument number must contain digits only"
            )
        self.accept_disclaimer()
        response = self._request(
            "GET",
            DIRECT_CFN_URL,
            params={"cfnNumber": instrument_number},
        )
        document_id = self._document_id(response, "exact instrument route")
        return self.fetch_detail(document_id) if document_id else None

    def book_page(
        self,
        book: int,
        page: int,
        *,
        book_type: str = "official-records",
    ) -> dict[str, Any] | None:
        if book < 1 or page < 1:
            raise PalmBeachRecorderError("book and page must be positive")
        try:
            book_type_id = int(BOOK_TYPES[book_type]["id"])
        except KeyError as error:
            raise PalmBeachRecorderError(
                f"unknown book type: {book_type}"
            ) from error
        self.accept_disclaimer()
        response = self._request(
            "GET",
            DIRECT_BOOK_PAGE_URL,
            params={
                "bookPageNumber": f"{book}/{page}",
                "bookType": book_type_id,
            },
        )
        document_id = self._document_id(response, "exact book/page route")
        return self.fetch_detail(document_id) if document_id else None

    def captcha_required(self) -> bool:
        self.accept_disclaimer()
        response = self._request("POST", CAPTCHA_STATE_URL, data={})
        value = _clean_text(getattr(response, "text", "")).casefold()
        if value not in {"true", "false"}:
            raise PalmBeachRecorderSourceChanged(
                "captcha-state route returned an unexpected value"
            )
        return value == "true"

    def image(
        self,
        record: Mapping[str, Any],
        page_number: int,
    ) -> DocumentImage:
        image_access = record.get("image_access")
        if not isinstance(image_access, Mapping):
            raise PalmBeachRecorderSourceChanged(
                "normalized record is missing image-access metadata"
            )
        page_count = image_access.get("online_page_count")
        if not isinstance(page_count, int):
            raise PalmBeachRecorderSourceChanged(
                "normalized record has no numeric online image count"
            )
        if page_count < 1:
            raise PalmBeachImageUnavailable(
                "the Clerk index record has no image available online",
                record=record,
            )
        if page_number < 1 or page_number > page_count:
            raise PalmBeachRecorderError(
                f"image page must be between 1 and {page_count}"
            )

        document_id = str(record.get("native_document_id") or "")
        if not document_id.isdigit():
            raise PalmBeachRecorderSourceChanged(
                "normalized record has no numeric document identifier"
            )
        response = self._request(
            "GET",
            IMAGE_URL,
            params={
                "documentId": document_id,
                "index": 0,
                "pageNum": page_number,
                "type": "normal",
                "rotate": 0,
            },
        )
        content = bytes(getattr(response, "content", b""))
        headers = getattr(response, "headers", {})
        media_type = ""
        if isinstance(headers, Mapping):
            media_type = str(
                next(
                    (
                        value
                        for key, value in headers.items()
                        if str(key).casefold() == "content-type"
                    ),
                    "",
                )
            ).split(";", maxsplit=1)[0].strip()
        if media_type != "image/png" or not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise PalmBeachImageUnavailable(
                "the Clerk did not return a public PNG for this document page",
                record=record,
            )
        return DocumentImage(
            content=content,
            media_type=media_type,
            page_number=page_number,
            sha256=hashlib.sha256(content).hexdigest(),
        )


def _selector_from_image_args(args: argparse.Namespace) -> dict[str, Any]:
    instrument = getattr(args, "instrument", None)
    book = getattr(args, "book", None)
    record_page = getattr(args, "record_page", None)
    if instrument and (book is not None or record_page is not None):
        raise PalmBeachRecorderError(
            "image accepts either --instrument or --book with --record-page"
        )
    if instrument:
        return {"instrument_number": instrument}
    if book is None or record_page is None:
        raise PalmBeachRecorderError(
            "image requires --instrument or both --book and --record-page"
        )
    return {
        "book": book,
        "page": record_page,
        "book_type": args.book_type,
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    if args.command == "instrument":
        parameters = {"instrument_number": args.instrument_number}
    elif args.command == "book-page":
        parameters = {
            "book": args.book,
            "page": args.page,
            "book_type": args.book_type,
        }
    elif args.command == "image":
        parameters = {
            **_selector_from_image_args(args),
            "image_page": args.image_page,
        }
    elif args.command == "routes":
        parameters = {}
    elif args.command == "probe":
        parameters = {"sentinel_instrument": SENTINEL_INSTRUMENT}
    else:
        parameters = {}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            metadata={
                "transport_contract": (
                    "public_terms_session_then_exact_document_navigation"
                ),
            },
        ),
    )


def _source_failure(
    query: PublicRecordsQuery,
    error: PalmBeachRecorderError,
) -> PublicRecordsResult:
    records: list[Mapping[str, Any]] = []
    if isinstance(error, PalmBeachImageUnavailable):
        status = ResultStatus.HUMAN_REQUIRED
        code = "image_unavailable_online"
        category = "document_access"
        records = [error.record]
    elif isinstance(error, PalmBeachRecorderSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_changed"
        category = "source_schema"
    elif isinstance(error, PalmBeachRecorderRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "source_rate_limited"
        category = "rate_limit"
    elif isinstance(error, PalmBeachRecorderTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "source_transport_failed"
        category = "transport"
    elif isinstance(error, PalmBeachRecorderHTTPError):
        if error.status_code in {401, 403}:
            status = ResultStatus.RESTRICTED
            category = "source_access"
        elif error.status_code in {404, 410}:
            status = ResultStatus.SOURCE_CHANGED
            category = "source_route"
        else:
            status = ResultStatus.UNAVAILABLE
            category = "http"
        code = f"source_http_{error.status_code}"
    else:
        status = ResultStatus.UNAVAILABLE
        code = "invalid_source_query"
        category = "source_query"

    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category=category,
                retryable=status
                in {ResultStatus.UNAVAILABLE, ResultStatus.RATE_LIMITED},
                details={
                    "alternative_routes": source_routes()[
                        "complementary_routes"
                    ]
                    if isinstance(error, PalmBeachImageUnavailable)
                    else [],
                },
            )
        ],
        records=records,
        warnings=SOURCE_WARNINGS,
    )


def _artifact_record(
    record: Mapping[str, Any],
    image: DocumentImage,
    destination: Path,
) -> dict[str, Any]:
    image_parameters = {
        "documentId": record["native_document_id"],
        "index": 0,
        "pageNum": image.page_number,
        "type": "normal",
        "rotate": 0,
    }
    source_url = f"{IMAGE_URL}?{urlencode(image_parameters)}"
    return {
        "source_id": SOURCE_ID,
        "record_kind": "document_image_artifact",
        "native_document_id": (
            f"{record['native_document_id']}:normal:{image.page_number}"
        ),
        "canonical_ref": (
            f"{record['canonical_ref']}/image/{image.page_number}"
        ),
        "evidence_ref": record["canonical_ref"],
        "instrument_number": record["instrument_number"],
        "book": record.get("book"),
        "page": record.get("page"),
        "image_page": image.page_number,
        "online_page_count": record["image_access"]["online_page_count"],
        "media_type": image.media_type,
        "byte_count": len(image.content),
        "sha256": image.sha256,
        "document_output": str(destination),
        "source_url": source_url,
    }


def run_probe(
    client: PalmBeachRecorderClient | None = None,
) -> dict[str, Any]:
    """Run a bounded exact-record, detail-schema, image, and CAPTCHA probe."""
    source_client = client or PalmBeachRecorderClient()
    record = source_client.instrument(SENTINEL_INSTRUMENT)
    if record is None:
        raise PalmBeachRecorderSourceChanged(
            "known sentinel instrument no longer resolves"
        )
    expected = {
        "native_document_id": SENTINEL_DOCUMENT_ID,
        "book": str(SENTINEL_BOOK),
        "page": str(SENTINEL_PAGE),
        "document_type": SENTINEL_DOC_TYPE,
        "recording_date_raw": f"{SENTINEL_RECORD_DATE} 11:08:00 AM",
    }
    for field, value in expected.items():
        if record.get(field) != value:
            raise PalmBeachRecorderSourceChanged(
                f"sentinel {field} changed from {value!r}"
            )
    image = source_client.image(record, 1)
    captcha_required = source_client.captcha_required()
    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_health_check",
        "native_document_id": "live-sentinel",
        "status": "ok",
        "sentinel": {
            "instrument_number": record["instrument_number"],
            "document_id": record["native_document_id"],
            "book": record["book"],
            "page": record["page"],
            "document_type": record["document_type"],
            "image_media_type": image.media_type,
            "image_byte_count": len(image.content),
            "image_sha256": image.sha256,
        },
        "broad_search_captcha_required": captcha_required,
        "request_count": source_client.request_count,
        "routes": {
            "home": HOME_URL,
            "instrument": DIRECT_CFN_URL,
            "book_page": DIRECT_BOOK_PAGE_URL,
            "document_details": DOCUMENT_DETAILS_URL,
            "document_information": DOCUMENT_INFORMATION_URL,
            "image": IMAGE_URL,
        },
    }


def execute(
    args: argparse.Namespace,
    *,
    client: PalmBeachRecorderClient | Any | None = None,
) -> PublicRecordsResult:
    try:
        query = build_query(args)
    except PalmBeachRecorderError as error:
        query = PublicRecordsQuery(
            source=SOURCE_METADATA,
            jurisdiction=JURISDICTION,
            query=QueryMetadata(operation=args.command),
        )
        result = _source_failure(query, error)
        _log(canonical_json(query.to_dict()), None)
        return result

    source_client = client or PalmBeachRecorderClient(
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        minimum_interval=getattr(
            args,
            "minimum_interval",
            DEFAULT_MINIMUM_INTERVAL,
        ),
    )
    try:
        if args.command == "instrument":
            record = source_client.instrument(args.instrument_number)
            result = PublicRecordsResult.success(
                query,
                [record] if record else [],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "book-page":
            record = source_client.book_page(
                args.book,
                args.page,
                book_type=args.book_type,
            )
            result = PublicRecordsResult.success(
                query,
                [record] if record else [],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "image":
            selector = _selector_from_image_args(args)
            if "instrument_number" in selector:
                record = source_client.instrument(
                    selector["instrument_number"]
                )
            else:
                record = source_client.book_page(
                    selector["book"],
                    selector["page"],
                    book_type=selector["book_type"],
                )
            if record is None:
                result = PublicRecordsResult.success(
                    query,
                    [],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                image = source_client.image(record, args.image_page)
                destination = Path(args.document_output).expanduser()
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(image.content)
                artifact = _artifact_record(record, image, destination)
                result = PublicRecordsResult.success(
                    query,
                    [artifact],
                    raw_artifact_refs=[str(destination)],
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command == "routes":
            result = PublicRecordsResult.success(
                query,
                [source_routes()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            result = PublicRecordsResult.success(
                query,
                [run_probe(source_client)],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise PalmBeachRecorderError(
                f"unsupported command: {args.command}"
            )
    except PalmBeachRecorderError as error:
        result = _source_failure(query, error)

    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    _log(canonical_json(query.to_dict()), count)
    return result


def _log(query: str, result_count: int | None) -> None:
    try:
        log_search(query, SOURCE_ID, result_count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
    summary: str,
) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"{summary} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return
    print(f"{summary}: {result.status.value} ({len(result.records)} records)")
    for record in result.records:
        if record.get("record_kind") == "recorded_instrument":
            print(
                f"- {record['instrument_number']} | "
                f"{record.get('document_type') or ''} | "
                f"{record.get('recording_date_raw') or ''}"
            )
            print(f"  {record['source_url']}")
        elif record.get("record_kind") == "document_image_artifact":
            print(
                f"- {record['instrument_number']} page "
                f"{record['image_page']} -> {record['document_output']}"
            )
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum interval between source requests",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Retrieve Palm Beach County Official Records by exact instrument "
            "number or book/page and fetch available public PNG pages"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    instrument = subparsers.add_parser(
        "instrument",
        help="Retrieve one exact Clerk instrument number",
    )
    instrument.add_argument("instrument_number")
    _add_transport_args(instrument)

    book_page = subparsers.add_parser(
        "book-page",
        help="Retrieve one exact book/page",
    )
    book_page.add_argument("book", type=int)
    book_page.add_argument("page", type=int)
    book_page.add_argument(
        "--book-type",
        choices=sorted(BOOK_TYPES),
        default="official-records",
    )
    _add_transport_args(book_page)

    image = subparsers.add_parser(
        "image",
        help="Download one public PNG page for an exact record",
    )
    image.add_argument("--instrument")
    image.add_argument("--book", type=int)
    image.add_argument("--record-page", type=int)
    image.add_argument(
        "--book-type",
        choices=sorted(BOOK_TYPES),
        default="official-records",
    )
    image.add_argument("--image-page", type=int, default=1)
    image.add_argument("--document-output", required=True)
    _add_transport_args(image)

    routes = subparsers.add_parser(
        "routes",
        help="Show verified discovery, bulk, copy, property, tax, and court routes",
    )
    add_output_args(routes)

    probe = subparsers.add_parser(
        "probe",
        help="Run bounded exact-record, image, and CAPTCHA checks",
    )
    _add_transport_args(probe)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args, "Palm Beach Official Records")
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
            ResultStatus.HUMAN_REQUIRED,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
