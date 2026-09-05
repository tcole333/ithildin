#!/usr/bin/env python3
"""Query Palm Beach County Clerk tax-deed cases, sales, and documents.

The Clerk's anonymous MVC portal stores one submitted search in the HTTP
session and exposes the matching rows through jqGrid.  This adapter submits
the native form, follows all reported grid pages when ``--limit`` is omitted,
and binds continuations to the query, grid schema, reported totals, and the
first-page occurrence snapshot.

The portal row ID is retained as a case-occurrence locator.  Case numbers, tax
certificate numbers, parcel control numbers, auction events, and document
image IDs remain separate identities.

Examples:
    uv run python tools/query_palm_beach_tax_deeds.py parcel \
        04-36-43-25-00-000-5040 --output /tmp/pbc-tax-deed-parcel.json
    uv run python tools/query_palm_beach_tax_deeds.py owner PRIEST \
        --from-date 2023-01-01 --to-date 2024-12-31
    uv run python tools/query_palm_beach_tax_deeds.py lands-available
    uv run python tools/query_palm_beach_tax_deeds.py detail 43079
    uv run python tools/query_palm_beach_tax_deeds.py document \
        43079 24748216 --document-output /tmp/tax-certificate.pdf
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import html as html_lib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, unquote, urljoin, urlparse

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
        sha256_fingerprint,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-fl-palm-beach-tax-deeds"
COUNTY_GEOID = "12099"
BASE_URL = "https://taxdeed.mypalmbeachclerk.com"
HOME_URL = f"{BASE_URL}/Home/"
POST_URL = f"{BASE_URL}/"
GRID_URL = f"{BASE_URL}/Home/GridSearchData"
DETAIL_URL = f"{BASE_URL}/Home/Details"
IMAGE_ROOT = f"{BASE_URL}/Home/Image/"
OFFICIAL_PAGE_URL = (
    "https://www.mypalmbeachclerk.com/departments/courts/tax-deeds"
)
CERTIFIED_COPY_URL = (
    "https://www.mypalmbeachclerk.com/records/official-records/"
    "electronic-certified-copies-of-official-records"
)
OFFICIAL_RECORDS_URL = "https://erec.mypalmbeachclerk.com/"
PROPERTY_APPRAISER_URL = "https://pbcpao.gov/"
TAX_COLLECTOR_URL = "https://www.pbctax.gov/propertytax/"
ECASEVIEW_URL = "https://appsgp.mypalmbeachclerk.com/ecaseview"
LEGAL_NOTICES_URL = "https://www.pbcfllegalnotices.com/"

DEFAULT_TIMEOUT = 45.0
DEFAULT_RETRY_ATTEMPTS = 3
NATIVE_PAGE_SIZE = 100
NATIVE_PAGE_SIZES = (10, 25, 50, 100)
CURSOR_PREFIX = "pbc-tax-deeds:v1:"
CURSOR_VERSION = 1
USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

SENTINEL_ROW_ID = "43079"
SENTINEL_CASE_NUMBER = "2023-0680TD"
SENTINEL_CERTIFICATE_NUMBER = "10687-2015"
SENTINEL_PARCEL_ID = "04-36-43-25-00-000-5040"
SENTINEL_DOCUMENT_ID = "24748216"
SENTINEL_DOCUMENT_LABEL = "Tax Certificate"

GRID_FIELDS = (
    "applicant_names",
    "case_number",
    "certificate_number",
    "parcel_id",
    "auction_date",
    "status",
    "opening_bid",
    "high_bid",
    "surplus",
    "property_owners",
)
GRID_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "transport": "jqgrid",
        "fields": list(GRID_FIELDS),
        "native_page_sizes": list(NATIVE_PAGE_SIZES),
    }
)

SEARCH_CONTRACTS: Mapping[str, Mapping[str, str]] = {
    "certificate": {
        "tab": "certificate",
        "field": "SearchForCertificate",
        "button": "buttonSubmitCertificate",
        "search_type": "Certificate #",
    },
    "case": {
        "tab": "case",
        "field": "SearchForCase",
        "button": "buttonSubmitCase",
        "search_type": "Case #",
    },
    "parcel": {
        "tab": "parcelid",
        "field": "SearchForParcelId",
        "button": "buttonSubmitParcelId",
        "search_type": "Parcel Id",
    },
    "tax-collector": {
        "tab": "taxcollector",
        "field": "SearchForTaxCollector",
        "button": "buttonSubmitTaxCollector",
        "search_type": "Tax Collector #",
    },
    "applicant": {
        "tab": "applicantname",
        "field": "SearchForApplicantName",
        "button": "buttonSubmitApplicantName",
        "from_field": "dateFromApplicantName",
        "to_field": "dateToApplicantName",
        "search_type": "Applicant Name",
    },
    "owner": {
        "tab": "ownername",
        "field": "SearchForOwnerName",
        "button": "buttonSubmitOwnerName",
        "from_field": "dateFromOwnerName",
        "to_field": "dateToOwnerName",
        "search_type": "Owner Name",
    },
    "status": {
        "tab": "status",
        "field": "SearchTypeStatus",
        "button": "buttonSubmitStatus",
        "from_field": "dateFromStatus",
        "to_field": "dateToStatus",
        "search_type": "Status",
    },
    "sale-date": {
        "tab": "saledate",
        "field": "SearchSaleDateFrom",
        "to_field": "SearchSaleDateTo",
        "button": "buttonSubmitSaleDate",
        "search_type": "Sale Date",
    },
    "lands-available": {
        "tab": "landsavailable",
        "button": "buttonSubmitLandsAvailable",
        "search_type": "Lands Available",
    },
}

OBSERVED_STATUS_OPTIONS: Mapping[str, str] = {
    "BANKRUPTCY": "8",
    "ESCHEATED": "7",
    "LANDS AVAILABLE": "5",
    "PENDING SALE": "17",
    "REDEEMED": "4",
    "REMOVE": "13",
    "REMOVESALE": "14",
    "RESCHEDULED": "15",
    "SALE": "2",
    "SOLD": "3",
    "UNSOLD": "16",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Palm Beach County Clerk Tax Deeds",
    source_role="tax_deed_case_sale_status_and_documents",
    base_url=HOME_URL,
    dataset_id="palm-beach-tax-deed-mvc-jqgrid",
    metadata={
        "authority": (
            "Palm Beach County Clerk of the Circuit Court and Comptroller"
        ),
        "county_geoid": COUNTY_GEOID,
        "record_grain": "published_tax_deed_case_occurrence",
        "portal_locator": "row_id",
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
    "The portal row ID is a source case-occurrence locator. Case, tax "
    "certificate, parcel, auction-event, and document identities remain "
    "separate.",
    "Status is the Clerk's mutable tax-deed lifecycle observation. It is not "
    "a conclusion about current recorded title.",
    "Applicant and property-owner labels are preserved as source-reported "
    "roles; they are not converted into current ownership assertions.",
    "Public inline PDFs are uncertified source images. Certified copies use "
    "the Clerk's separate official ordering route.",
)


class PalmBeachTaxDeedError(RuntimeError):
    """Base error for the Palm Beach tax-deed adapter."""


class PalmBeachTaxDeedQueryError(PalmBeachTaxDeedError):
    """The caller's native selector or cursor cannot be used."""


class PalmBeachTaxDeedSourceChanged(PalmBeachTaxDeedError):
    """The official route or schema no longer matches the observed contract."""


class PalmBeachTaxDeedSnapshotChanged(PalmBeachTaxDeedSourceChanged):
    """The source population changed during or between paginated requests."""

    def __init__(
        self,
        message: str,
        *,
        records: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.records = [dict(record) for record in records]
        super().__init__(message)


class PalmBeachTaxDeedTransportError(PalmBeachTaxDeedError):
    """The official portal could not be reached."""


class PalmBeachTaxDeedRateLimited(PalmBeachTaxDeedError):
    """The official portal returned HTTP 429."""


class PalmBeachTaxDeedHTTPError(PalmBeachTaxDeedError):
    """The official portal returned an unexpected HTTP status."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(
            f"Palm Beach Tax Deeds returned HTTP {status_code}: {url}"
        )


class PalmBeachTaxDeedDocumentUnavailable(PalmBeachTaxDeedError):
    """A listed document is not currently returned as a public PDF."""

    def __init__(
        self,
        message: str,
        *,
        case_record: Mapping[str, Any],
        document: Mapping[str, Any],
    ) -> None:
        self.case_record = dict(case_record)
        self.document = dict(document)
        super().__init__(message)


@dataclass(frozen=True)
class DiscoverySnapshot:
    """Live selector and rolling option state parsed from the home page."""

    status_options: tuple[Mapping[str, str], ...]
    sale_dates: tuple[Mapping[str, str], ...]
    form_action: str
    form_method: str
    website_version: str | None

    def to_record(self) -> dict[str, Any]:
        return {
            "source_id": SOURCE_ID,
            "record_kind": "source_discovery",
            "native_document_id": "live-selector-contract",
            "canonical_ref": canonical_property_ref(
                SOURCE_ID,
                COUNTY_GEOID,
                "source-discovery",
                "live-selector-contract",
            ),
            "search_operations": [
                {
                    "operation": operation,
                    "search_type": contract["search_type"],
                    "input_fields": [
                        value
                        for key in ("field", "from_field", "to_field")
                        if (value := contract.get(key))
                    ],
                }
                for operation, contract in SEARCH_CONTRACTS.items()
            ],
            "status_options": [dict(item) for item in self.status_options],
            "sale_dates": [dict(item) for item in self.sale_dates],
            "sale_date_count": len(self.sale_dates),
            "form_action": self.form_action,
            "form_method": self.form_method,
            "website_version": self.website_version,
            "native_page_sizes": list(NATIVE_PAGE_SIZES),
            "grid_schema_fingerprint": GRID_SCHEMA_FINGERPRINT,
            "official_routes": official_routes(),
            "source_url": HOME_URL,
        }


@dataclass(frozen=True)
class SearchSpec:
    """One native portal search without transport pagination state."""

    operation: str
    value: str | None = None
    from_date: str | None = None
    to_date: str | None = None

    def binding(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "value": self.value,
            "from_date": self.from_date,
            "to_date": self.to_date,
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.binding())


@dataclass(frozen=True)
class GridPage:
    """Validated jqGrid response page."""

    page: int
    total_pages: int
    total_records: int
    rows: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class SearchBatch:
    """Normalized records plus native completeness state."""

    records: tuple[Mapping[str, Any], ...]
    total_records: int
    total_pages: int
    snapshot_fingerprint: str
    next_cursor: str | None
    complete: bool


@dataclass(frozen=True)
class PDFArtifact:
    """Validated public PDF bytes and source response metadata."""

    content: bytes
    media_type: str
    content_disposition: str | None
    sha256: str


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "get_text"):
        text = value.get_text(" ", strip=True)
    else:
        text = str(value)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _iso_date(value: str | None) -> str | None:
    candidate = _clean_text(value)
    if not candidate:
        return None
    for pattern in (
        "%m/%d/%Y",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%d",
        "%A, %B %d, %Y %I:%M %p",
    ):
        try:
            return datetime.strptime(candidate, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _form_date(value: str | None, field_name: str) -> str:
    normalized = _iso_date(value)
    if normalized is None:
        raise PalmBeachTaxDeedQueryError(
            f"{field_name} must use YYYY-MM-DD or MM/DD/YYYY"
        )
    return datetime.strptime(normalized, "%Y-%m-%d").strftime("%m/%d/%Y")


def normalize_pcn(value: Any) -> str | None:
    """Return the reversible 17-digit Palm Beach PCN join candidate."""

    raw = _clean_text(value)
    digits = re.sub(r"\D", "", raw)
    return digits if len(digits) == 17 else None


def _money(value: Any) -> dict[str, Any]:
    raw = _clean_text(value)
    if not raw:
        return {"raw": None, "currency": "USD", "minor_units": None}
    cleaned = re.sub(r"[^0-9.\-]", "", raw)
    try:
        minor_units = int(
            (Decimal(cleaned) * 100).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
    except (InvalidOperation, ValueError):
        minor_units = None
    return {
        "raw": raw,
        "currency": "USD",
        "minor_units": minor_units,
    }


def _grid_people(value: Any) -> list[str]:
    raw = _clean_text(value)
    if not raw:
        return []
    if "~" in raw:
        return _unique(re.split(r"~+", raw))
    return [raw]


def _detail_people(cell: Tag | None) -> tuple[str | None, list[str]]:
    if cell is None:
        return None, []
    raw = html_lib.unescape(cell.get_text("\n", strip=True)).strip()
    if not raw:
        return None, []
    values = re.split(r"\s*,\s*\n+|\n+", raw)
    return raw, _unique(values)


def _header_value(
    headers: Any,
    name: str,
) -> str | None:
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if str(key).casefold() == name.casefold():
            cleaned = _clean_text(value)
            return cleaned or None
    return None


def parse_discovery(html: str) -> DiscoverySnapshot:
    """Parse live search selectors and rolling sale dates from the portal."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form is None:
        raise PalmBeachTaxDeedSourceChanged(
            "tax-deed home page is missing its search form"
        )
    form_method = _clean_text(form.get("method")).upper() or "GET"
    if form_method != "POST":
        raise PalmBeachTaxDeedSourceChanged(
            f"tax-deed search form method changed to {form_method!r}"
        )
    required_fields = {
        contract[key]
        for contract in SEARCH_CONTRACTS.values()
        for key in ("field", "from_field", "to_field", "button")
        if contract.get(key)
    }
    missing = sorted(
        field_name
        for field_name in required_fields
        if form.find(attrs={"name": field_name}) is None
    )
    if missing:
        raise PalmBeachTaxDeedSourceChanged(
            "tax-deed search form is missing fields: " + ", ".join(missing)
        )

    status_select = form.find("select", id="idSearchTypeStatus")
    if status_select is None:
        raise PalmBeachTaxDeedSourceChanged(
            "tax-deed home page is missing status options"
        )
    status_options: list[Mapping[str, str]] = []
    for option in status_select.find_all("option"):
        label = _clean_text(option)
        native_value = _clean_text(option.get("value"))
        if label and native_value:
            status_options.append(
                {"label": label, "native_value": native_value}
            )
    if not status_options:
        raise PalmBeachTaxDeedSourceChanged(
            "tax-deed home page published no status options"
        )

    sale_from = form.find("select", attrs={"name": "SearchSaleDateFrom"})
    sale_to = form.find("select", attrs={"name": "SearchSaleDateTo"})
    if sale_from is None or sale_to is None:
        raise PalmBeachTaxDeedSourceChanged(
            "tax-deed home page is missing sale-date selectors"
        )
    from_values = [
        _clean_text(option.get("value"))
        for option in sale_from.find_all("option")
        if _clean_text(option.get("value"))
    ]
    to_values = [
        _clean_text(option.get("value"))
        for option in sale_to.find_all("option")
        if _clean_text(option.get("value"))
    ]
    if from_values != to_values:
        raise PalmBeachTaxDeedSourceChanged(
            "sale-date from/to option sets no longer match"
        )
    sale_dates = [
        {
            "raw": value,
            "date": _iso_date(value) or "",
        }
        for value in from_values
    ]
    if any(not item["date"] for item in sale_dates):
        raise PalmBeachTaxDeedSourceChanged(
            "a published sale-date option no longer matches the observed format"
        )

    version_match = re.search(r"Website Version\s+([0-9.]+)", html)
    form_action = urljoin(POST_URL, _clean_text(form.get("action")) or "/")
    return DiscoverySnapshot(
        status_options=tuple(status_options),
        sale_dates=tuple(sale_dates),
        form_action=form_action,
        form_method=form_method,
        website_version=version_match.group(1) if version_match else None,
    )


def _selected_tab(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    marker = soup.find(id="idTabToSelectBasedOnLastSearch")
    if marker is None:
        return None
    value = marker.get("value")
    return _clean_text(value) or None


def parse_search_type(html: str, *, expected_tab: str) -> str:
    """Extract the server-rendered jqGrid search type after a form POST."""

    tab = _selected_tab(html)
    if tab != expected_tab:
        raise PalmBeachTaxDeedSourceChanged(
            f"search response selected tab {tab!r}, expected {expected_tab!r}"
        )
    match = re.search(
        r"url:\s*['\"](?P<url>[^'\"]*/Home/GridSearchData"
        r"\?SearchType=[^'\"]+)['\"]",
        html,
    )
    if match is None:
        raise PalmBeachTaxDeedQueryError(
            "the source did not create a grid for this submitted selector"
        )
    parsed = urlparse(html_lib.unescape(match.group("url")))
    values = parse_qs(parsed.query).get("SearchType", [])
    if len(values) != 1 or not _clean_text(values[0]):
        raise PalmBeachTaxDeedSourceChanged(
            "search response is missing one jqGrid search type"
        )
    return unquote(values[0])


def parse_grid_page(payload: Mapping[str, Any]) -> GridPage:
    """Validate one jqGrid response without losing an authoritative zero."""

    try:
        page = int(payload["page"])
        total_pages = int(payload["total"])
        total_records = int(payload["records"])
    except (KeyError, TypeError, ValueError) as error:
        raise PalmBeachTaxDeedSourceChanged(
            "jqGrid response is missing numeric page totals"
        ) from error
    rows_value = payload.get("rows")
    if not isinstance(rows_value, list):
        raise PalmBeachTaxDeedSourceChanged(
            "jqGrid response rows must be an array"
        )
    if page < 1 or total_pages < 0 or total_records < 0:
        raise PalmBeachTaxDeedSourceChanged(
            "jqGrid response contains invalid page totals"
        )
    rows: list[Mapping[str, Any]] = []
    for index, raw_row in enumerate(rows_value):
        if not isinstance(raw_row, Mapping):
            raise PalmBeachTaxDeedSourceChanged(
                f"jqGrid row {index} is not an object"
            )
        row_id = _clean_text(raw_row.get("id"))
        cells = raw_row.get("cell")
        if not row_id.isdigit() or not isinstance(cells, list):
            raise PalmBeachTaxDeedSourceChanged(
                f"jqGrid row {index} lacks its numeric ID or cell array"
            )
        if len(cells) != len(GRID_FIELDS):
            raise PalmBeachTaxDeedSourceChanged(
                f"jqGrid row {index} has {len(cells)} cells; "
                f"expected {len(GRID_FIELDS)}"
            )
        rows.append({"id": row_id, "cell": list(cells)})
    if total_records == 0 and (total_pages != 0 or rows):
        raise PalmBeachTaxDeedSourceChanged(
            "zero-record jqGrid response has pages or rows"
        )
    if total_records > 0 and total_pages < 1:
        raise PalmBeachTaxDeedSourceChanged(
            "non-empty jqGrid response reports no pages"
        )
    return GridPage(
        page=page,
        total_pages=total_pages,
        total_records=total_records,
        rows=tuple(rows),
    )


def _status_value(
    label: str,
    discovery: DiscoverySnapshot,
) -> str | None:
    normalized = _clean_text(label).upper()
    for option in discovery.status_options:
        if _clean_text(option.get("label")).upper() == normalized:
            return _clean_text(option.get("native_value")) or None
    return None


def normalize_grid_row(
    row: Mapping[str, Any],
    *,
    source_page: int,
    source_position: int,
    discovery: DiscoverySnapshot,
    search_spec: SearchSpec,
) -> dict[str, Any]:
    """Normalize one source case occurrence from its fixed jqGrid columns."""

    row_id = _clean_text(row.get("id"))
    cells = list(row.get("cell") or [])
    values = {
        field_name: _clean_text(cells[index])
        for index, field_name in enumerate(GRID_FIELDS)
    }
    auction_date = _iso_date(values["auction_date"])
    parcel_id = values["parcel_id"] or None
    normalized_pcn = normalize_pcn(parcel_id)
    event_identity = ":".join(
        value
        for value in (
            f"row-{row_id}",
            f"auction-{auction_date}" if auction_date else None,
        )
        if value
    )
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "tax-deed-case-occurrence",
        row_id,
    )
    applicants = _grid_people(values["applicant_names"])
    owners = _grid_people(values["property_owners"])
    people = [
        {
            "raw_name": name,
            "role": "applicant",
            "raw_role": "Applicant",
            "assertion_type": "source_reported_tax_deed_applicant",
        }
        for name in applicants
    ]
    people.extend(
        {
            "raw_name": name,
            "role": "source_reported_property_owner",
            "raw_role": "Owners",
            "assertion_type": "source_reported_tax_deed_owner_label",
        }
        for name in owners
    )
    return {
        "source_id": SOURCE_ID,
        "record_kind": "tax_deed_case_occurrence",
        "source_record_id": row_id,
        "portal_row_id": row_id,
        "native_event_id": event_identity,
        "native_case_id": values["case_number"] or None,
        "case_number": values["case_number"] or None,
        "native_certificate_id": values["certificate_number"] or None,
        "certificate_number": values["certificate_number"] or None,
        "parcel_id": parcel_id,
        "parcel_id_normalized": normalized_pcn,
        "parcel_join_evidence": {
            "published_location": {
                "raw": parcel_id,
                "normalized_candidate": normalized_pcn,
            },
            "method": (
                "exact_17_digit_pcn_after_removing_punctuation"
                if normalized_pcn
                else "unresolved_source_parcel_label"
            ),
            "identities_collapsed": False,
        },
        "event_type": "tax_deed_sale",
        "event_dates": {
            "auction": {
                "raw": values["auction_date"] or None,
                "utc_date": auction_date,
            }
        },
        "auction_date_raw": values["auction_date"] or None,
        "auction_date": auction_date,
        "status": values["status"] or None,
        "status_category": (
            re.sub(r"[^a-z0-9]+", "_", values["status"].casefold()).strip("_")
            if values["status"]
            else None
        ),
        "status_observation": {
            "label": values["status"] or None,
            "native_value": _status_value(values["status"], discovery),
            "role": "clerk_published_tax_deed_lifecycle_status",
            "current_title_inference": False,
        },
        "applicants": applicants,
        "source_reported_property_owners": owners,
        "people": people,
        "amounts": {
            "opening_bid": _money(values["opening_bid"]),
            "high_bid": _money(values["high_bid"]),
            "surplus": _money(values["surplus"]),
        },
        "detail_representations": [
            {
                "kind": "tax_deed_case_detail",
                "url": f"{DETAIL_URL}?id={row_id}",
                "relationship": "same_source_exact_portal_occurrence",
                "source_state": "listed",
            }
        ],
        "search_context": search_spec.binding(),
        "source_page": source_page,
        "source_position": source_position,
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_url": f"{DETAIL_URL}?id={row_id}",
        "jurisdiction": JURISDICTION.to_dict(),
    }


def _source_fields(
    fieldset: Tag,
) -> tuple[dict[str, str], dict[str, Tag]]:
    values: dict[str, str] = {}
    cells: dict[str, Tag] = {}
    for row in fieldset.find_all("tr"):
        columns = row.find_all("td", recursive=False)
        if len(columns) < 2:
            continue
        label_node = columns[0].find("b")
        label = _clean_text(label_node or columns[0])
        if not label:
            continue
        values[label] = _clean_text(columns[1])
        cells[label] = columns[1]
    return values, cells


def _section_table(soup: BeautifulSoup, heading: str) -> Tag | None:
    for node in soup.find_all(["h2", "h3"]):
        if _clean_text(node).casefold() == heading.casefold():
            table = node.find_next("table")
            return table if isinstance(table, Tag) else None
    return None


def _document_inventory(
    soup: BeautifulSoup,
    *,
    portal_row_id: str,
    parent_ref: str,
) -> list[dict[str, Any]]:
    table = _section_table(soup, "Documents")
    if table is None:
        return []
    documents: list[dict[str, Any]] = []
    for source_table_row, row in enumerate(
        table.find_all("tr"),
        start=1,
    ):
        text = _clean_text(row)
        if not text:
            continue
        anchor = row.find("a", href=True)
        native_document_id: str | None = None
        label = text
        access_state = "image_not_available"
        source_url: str | None = None
        if anchor is not None:
            match = re.fullmatch(
                r"/Home/Image/(?P<id>\d+)",
                urlparse(_clean_text(anchor.get("href"))).path,
            )
            if match:
                native_document_id = match.group("id")
                label = _clean_text(anchor)
                source_url = f"{IMAGE_ROOT}{native_document_id}"
                access_state = "public_pdf"
        if native_document_id is None:
            label = re.sub(
                r"\s*\(Image Not Available\)\s*$",
                "",
                label,
                flags=re.IGNORECASE,
            ).strip()
            if "Image Not Available" not in text:
                continue
        sequence = len(documents) + 1
        occurrence_id = f"{portal_row_id}:document:{sequence}"
        documents.append(
            {
                "document_occurrence_id": occurrence_id,
                "sequence": sequence,
                "source_table_row": source_table_row,
                "label": label,
                "native_document_id": native_document_id,
                "access_state": access_state,
                "media_type": (
                    "application/pdf"
                    if access_state == "public_pdf"
                    else None
                ),
                "source_url": source_url,
                "canonical_ref": (
                    f"{parent_ref}/document-occurrence/{sequence}"
                ),
                "source_document_identity": {
                    "portal_row_id": portal_row_id,
                    "document_occurrence_sequence": sequence,
                    "image_id": native_document_id,
                },
            }
        )
    return documents


def parse_detail(html: str, *, portal_row_id: str) -> dict[str, Any]:
    """Parse one exact public tax-deed case detail and document inventory."""

    if not str(portal_row_id).isdigit():
        raise PalmBeachTaxDeedQueryError(
            "portal row ID must contain digits only"
        )
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.find("h2"))
    fieldset = next(
        (
            node
            for node in soup.find_all("fieldset")
            if _clean_text(node.find("legend")).casefold() == "case"
        ),
        None,
    )
    if fieldset is None:
        if "not found" in _clean_text(soup).casefold():
            raise PalmBeachTaxDeedQueryError(
                f"tax-deed portal row {portal_row_id} was not found"
            )
        raise PalmBeachTaxDeedSourceChanged(
            "tax-deed detail is missing its Case fieldset"
        )
    fields, cells = _source_fields(fieldset)
    required = ("Case Number", "Certificate", "Parcel ID", "Status")
    missing = [field_name for field_name in required if not fields.get(field_name)]
    if missing:
        raise PalmBeachTaxDeedSourceChanged(
            "tax-deed detail is missing fields: " + ", ".join(missing)
        )

    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "tax-deed-case-occurrence",
        str(portal_row_id),
    )
    applicant_raw, applicants = _detail_people(cells.get("Applicant Names"))
    owner_raw, owners = _detail_people(cells.get("Property Owners"))
    parcel_id = fields.get("Parcel ID") or None
    normalized_pcn = normalize_pcn(parcel_id)
    issued_raw = fields.get("Issued") or None
    auction_raw = fields.get("Auction Date") or None
    issued_date = _iso_date(issued_raw)
    auction_date = _iso_date(auction_raw)

    source_links: dict[str, str] = {}
    for label, key in (
        ("Property Appraiser", "property_appraiser"),
        ("Tax Collector", "tax_collector"),
    ):
        cell = cells.get(label)
        anchor = cell.find("a", href=True) if cell is not None else None
        if anchor is not None:
            source_links[key] = urljoin(BASE_URL, _clean_text(anchor.get("href")))

    appraiser_parameter: str | None = None
    if source_links.get("property_appraiser"):
        appraiser_parameter = next(
            iter(
                parse_qs(
                    urlparse(source_links["property_appraiser"]).query
                ).get("parcelId", [])
            ),
            None,
        )
        appraiser_parameter = _clean_text(appraiser_parameter) or None

    notes_table = _section_table(soup, "Notes")
    notes = (
        _unique([_clean_text(row) for row in notes_table.find_all("tr")])
        if notes_table is not None
        else []
    )
    documents = _document_inventory(
        soup,
        portal_row_id=str(portal_row_id),
        parent_ref=canonical_ref,
    )
    people = [
        {
            "raw_name": name,
            "role": "applicant",
            "raw_role": "Applicant Names",
            "assertion_type": "source_reported_tax_deed_applicant",
        }
        for name in applicants
    ]
    people.extend(
        {
            "raw_name": name,
            "role": "source_reported_property_owner",
            "raw_role": "Property Owners",
            "assertion_type": "source_reported_tax_deed_owner_label",
        }
        for name in owners
    )
    property_address_raw = fields.get("Property Address") or None
    meaningful_address = (
        property_address_raw
        if property_address_raw
        and re.search(r"[A-Z0-9]{2,}", property_address_raw, re.IGNORECASE)
        and property_address_raw.strip(" ,").upper() not in {"FL", "FL  "}
        else None
    )
    event_identity = ":".join(
        value
        for value in (
            f"row-{portal_row_id}",
            f"auction-{auction_date}" if auction_date else None,
        )
        if value
    )
    return {
        "source_id": SOURCE_ID,
        "record_kind": "tax_deed_case_occurrence",
        "record_detail_state": "exact_detail",
        "source_record_id": str(portal_row_id),
        "portal_row_id": str(portal_row_id),
        "native_event_id": event_identity,
        "native_case_id": fields["Case Number"],
        "case_number": fields["Case Number"],
        "native_certificate_id": fields["Certificate"],
        "certificate_number": fields["Certificate"],
        "certificate_issued_date_raw": issued_raw,
        "certificate_issued_date": issued_date,
        "parcel_id": parcel_id,
        "parcel_id_normalized": normalized_pcn,
        "parcel_join_evidence": {
            "published_location": {
                "raw": parcel_id,
                "normalized_candidate": normalized_pcn,
            },
            "property_appraiser_parameter": appraiser_parameter,
            "property_appraiser_parameter_matches": bool(
                normalized_pcn
                and appraiser_parameter
                and normalized_pcn == normalize_pcn(appraiser_parameter)
            ),
            "method": (
                "exact_17_digit_pcn_after_removing_punctuation"
                if normalized_pcn
                else "unresolved_source_parcel_label"
            ),
            "identities_collapsed": False,
        },
        "event_type": "tax_deed_sale",
        "event_dates": {
            "certificate_issued": {
                "raw": issued_raw,
                "utc_date": issued_date,
            },
            "auction": {
                "raw": auction_raw,
                "utc_date": auction_date,
            },
        },
        "auction_date_raw": auction_raw,
        "auction_date": auction_date,
        "status": fields.get("Status") or None,
        "status_category": (
            re.sub(
                r"[^a-z0-9]+",
                "_",
                fields.get("Status", "").casefold(),
            ).strip("_")
            or None
        ),
        "status_observation": {
            "label": fields.get("Status") or None,
            "native_value": OBSERVED_STATUS_OPTIONS.get(
                (fields.get("Status") or "").upper()
            ),
            "role": "clerk_published_tax_deed_lifecycle_status",
            "current_title_inference": False,
        },
        "legal_description": fields.get("Legal Description") or None,
        "applicant_names_raw": applicant_raw,
        "applicants": applicants,
        "property_owners_raw": owner_raw,
        "source_reported_property_owners": owners,
        "people": people,
        "property_address_raw": property_address_raw,
        "address": (
            {"raw": meaningful_address} if meaningful_address else None
        ),
        "assessed_as": fields.get("Assessed As") or None,
        "amounts": {
            "opening_bid": _money(fields.get("Opening Bid")),
            "high_bid": _money(fields.get("High Bid")),
            "surplus": _money(fields.get("Surplus")),
        },
        "notes": notes,
        "documents": documents,
        "document_inventory_state": (
            "published" if documents else "published_empty"
        ),
        "source_links": source_links,
        "detail_representations": [
            {
                "kind": "tax_deed_case_detail",
                "url": f"{DETAIL_URL}?id={portal_row_id}",
                "relationship": "same_source_exact_portal_occurrence",
                "source_state": "public",
            },
            *[
                {
                    "kind": "tax_deed_document",
                    "url": (
                        document.get("source_url")
                        or f"{DETAIL_URL}?id={portal_row_id}"
                        f"#document-occurrence-{document['sequence']}"
                    ),
                    "relationship": (
                        "same_source_case_document_occurrence"
                    ),
                    "source_state": document["access_state"],
                    "document_occurrence_id": (
                        document["document_occurrence_id"]
                    ),
                    "native_document_id": document["native_document_id"],
                    "label": document["label"],
                }
                for document in documents
            ],
        ],
        "source_fields": fields,
        "page_title": title or None,
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_url": f"{DETAIL_URL}?id={portal_row_id}",
        "jurisdiction": JURISDICTION.to_dict(),
    }


def official_routes() -> list[dict[str, Any]]:
    """Return field-specific official complements without merging identities."""

    return [
        {
            "kind": "property_appraiser",
            "source_id": "us-fl-palm-beach-property-appraiser",
            "url": PROPERTY_APPRAISER_URL,
            "adds": [
                "assessment_roll_names",
                "values",
                "situs_and_mailing_addresses",
                "parcel_geometry",
                "assessor_last_sale_labels",
            ],
            "join_keys": ["17_digit_parcel_control_number"],
        },
        {
            "kind": "tax_collector",
            "source_id": "us-fl-palm-beach-tax-collector",
            "url": TAX_COLLECTOR_URL,
            "adds": [
                "tax_account",
                "current_and_delinquent_bills",
                "balances",
                "payment_history",
            ],
            "join_keys": ["parcel_control_number", "tax_year"],
        },
        {
            "kind": "official_records",
            "source_id": "us-fl-palm-beach-official-records",
            "url": OFFICIAL_RECORDS_URL,
            "adds": [
                "recorded_instrument_index",
                "deeds",
                "liens",
                "judgments",
                "uncertified_recorded_document_images",
            ],
            "join_keys": [
                "parcel_control_number",
                "party_name",
                "book_and_page",
                "instrument_number",
            ],
        },
        {
            "kind": "ecaseview",
            "source_id": "us-fl-palm-beach-ecaseview",
            "url": ECASEVIEW_URL,
            "adds": [
                "court_case_metadata",
                "parties",
                "docket_entries",
                "public_court_documents",
            ],
            "join_keys": ["full_case_number", "party_name"],
        },
        {
            "kind": "certified_official_record_copy",
            "source_id": "us-fl-palm-beach-records-service",
            "url": CERTIFIED_COPY_URL,
            "adds": ["certified_tax_deed_or_other_official_record_copy"],
            "relationship": "separate_order_and_payment_route",
        },
        {
            "kind": "tax_deed_legal_notices",
            "url": LEGAL_NOTICES_URL,
            "adds": ["published_tax_deed_sale_legal_notices"],
            "join_keys": [
                "case_number",
                "parcel_control_number",
                "owner_name",
                "publication_date",
            ],
        },
        {
            "kind": "clerk_tax_deed_information",
            "url": OFFICIAL_PAGE_URL,
            "adds": [
                "sale_procedures",
                "redemption_guidance",
                "department_contact",
                "auction_and_notice_routes",
            ],
        },
    ]


def _resolve_status(
    value: str | None,
    discovery: DiscoverySnapshot,
) -> tuple[str, str]:
    candidate = _clean_text(value)
    if not candidate:
        raise PalmBeachTaxDeedQueryError("status search requires a value")
    for option in discovery.status_options:
        label = _clean_text(option.get("label"))
        native_value = _clean_text(option.get("native_value"))
        if (
            candidate.casefold() == label.casefold()
            or candidate == native_value
        ):
            return native_value, label
    raise PalmBeachTaxDeedQueryError(
        "status must match one of the source's current label/value options"
    )


def _resolve_sale_date(
    value: str | None,
    discovery: DiscoverySnapshot,
    field_name: str,
) -> tuple[str, str]:
    normalized = _iso_date(value)
    if normalized is None:
        raise PalmBeachTaxDeedQueryError(
            f"{field_name} must use a published sale date"
        )
    for option in discovery.sale_dates:
        if option.get("date") == normalized:
            return _clean_text(option.get("raw")), normalized
    raise PalmBeachTaxDeedQueryError(
        f"{field_name} is not in the source's current sale-date choices"
    )


def build_search_payload(
    spec: SearchSpec,
    discovery: DiscoverySnapshot,
) -> tuple[dict[str, str], str]:
    """Build one exact native form payload from validated live selectors."""

    try:
        contract = SEARCH_CONTRACTS[spec.operation]
    except KeyError as error:
        raise PalmBeachTaxDeedQueryError(
            f"unsupported tax-deed search operation: {spec.operation}"
        ) from error
    payload: dict[str, str] = {contract["button"]: "Search"}
    resolved_value = _clean_text(spec.value)
    if spec.operation == "status":
        resolved_value, _label = _resolve_status(spec.value, discovery)
    elif spec.operation == "sale-date":
        resolved_value, _from_iso = _resolve_sale_date(
            spec.from_date or spec.value,
            discovery,
            "from date",
        )
        to_raw, _to_iso = _resolve_sale_date(
            spec.to_date or spec.from_date or spec.value,
            discovery,
            "to date",
        )
        payload[contract["field"]] = resolved_value
        payload[contract["to_field"]] = to_raw
        return payload, contract["search_type"]
    elif spec.operation != "lands-available" and not resolved_value:
        raise PalmBeachTaxDeedQueryError(
            f"{spec.operation} search requires a value"
        )

    if field_name := contract.get("field"):
        payload[field_name] = resolved_value
    if from_field := contract.get("from_field"):
        payload[from_field] = _form_date(spec.from_date, "from date")
    if to_field := contract.get("to_field"):
        payload[to_field] = _form_date(spec.to_date, "to date")
    return payload, contract["search_type"]


def _page_snapshot_fingerprint(page: GridPage) -> str:
    return sha256_fingerprint(
        {
            "page": page.page,
            "total_pages": page.total_pages,
            "total_records": page.total_records,
            "rows": [dict(row) for row in page.rows],
        }
    )


def _encode_cursor(
    *,
    spec: SearchSpec,
    page: int,
    offset: int,
    total_records: int,
    total_pages: int,
    snapshot_fingerprint: str,
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "source_id": SOURCE_ID,
        "criteria_fingerprint": spec.fingerprint,
        "grid_schema_fingerprint": GRID_SCHEMA_FINGERPRINT,
        "native_page_size": NATIVE_PAGE_SIZE,
        "page": page,
        "offset": offset,
        "total_records": total_records,
        "total_pages": total_pages,
        "snapshot_fingerprint": snapshot_fingerprint,
    }
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return CURSOR_PREFIX + encoded


def _decode_cursor(cursor: str, *, spec: SearchSpec) -> dict[str, Any]:
    if not cursor.startswith(CURSOR_PREFIX):
        raise PalmBeachTaxDeedQueryError(
            "cursor does not belong to Palm Beach Tax Deeds"
        )
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        )
    except (binascii.Error, ValueError) as error:
        raise PalmBeachTaxDeedQueryError(
            "cursor payload is not valid"
        ) from error
    if not isinstance(payload, Mapping):
        raise PalmBeachTaxDeedQueryError("cursor payload must be an object")
    expected = {
        "version": CURSOR_VERSION,
        "source_id": SOURCE_ID,
        "criteria_fingerprint": spec.fingerprint,
        "grid_schema_fingerprint": GRID_SCHEMA_FINGERPRINT,
        "native_page_size": NATIVE_PAGE_SIZE,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise PalmBeachTaxDeedQueryError(
            "cursor does not match this source, query, or grid schema"
        )
    for field_name in ("page", "offset", "total_records", "total_pages"):
        if isinstance(payload.get(field_name), bool) or not isinstance(
            payload.get(field_name),
            int,
        ):
            raise PalmBeachTaxDeedQueryError(
                f"cursor {field_name} must be an integer"
            )
    if (
        payload["page"] < 1
        or payload["offset"] < 0
        or payload["offset"] >= NATIVE_PAGE_SIZE
        or payload["total_records"] < 0
        or payload["total_pages"] < 0
        or not _clean_text(payload.get("snapshot_fingerprint"))
    ):
        raise PalmBeachTaxDeedQueryError(
            "cursor contains invalid continuation state"
        )
    return dict(payload)


class PalmBeachTaxDeedClient:
    """HTTP client for the Clerk's anonymous MVC and jqGrid routes."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/json,application/pdf,*/*;q=0.8"
                    ),
                }
            )
        self.timeout = timeout
        self.retry_attempts = max(1, retry_attempts)
        self.request_count = 0

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        accepted_statuses: set[int] | None = None,
    ) -> Any:
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_attempts + 1):
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    params=dict(params or {}),
                    data=dict(data or {}),
                    timeout=self.timeout,
                )
            except (requests.RequestException, OSError, TimeoutError) as error:
                last_error = error
                if attempt < self.retry_attempts:
                    continue
                raise PalmBeachTaxDeedTransportError(
                    f"request failed after {attempt} attempts: {error}"
                ) from error
            status_code = int(getattr(response, "status_code", 0))
            if status_code in {500, 502, 503, 504} and attempt < self.retry_attempts:
                continue
            if status_code == 429:
                raise PalmBeachTaxDeedRateLimited(
                    "Palm Beach Tax Deeds rate limited the request"
                )
            if accepted_statuses and status_code in accepted_statuses:
                return response
            if status_code < 200 or status_code >= 300:
                raise PalmBeachTaxDeedHTTPError(status_code, url)
            return response
        raise PalmBeachTaxDeedTransportError(
            f"request failed: {last_error}"
        )

    def discovery(self) -> DiscoverySnapshot:
        response = self._request("GET", HOME_URL)
        return parse_discovery(str(getattr(response, "text", "")))

    def submit_search(
        self,
        spec: SearchSpec,
        discovery: DiscoverySnapshot,
    ) -> str:
        payload, expected_search_type = build_search_payload(spec, discovery)
        response = self._request(
            "POST",
            discovery.form_action,
            data=payload,
        )
        search_type = parse_search_type(
            str(getattr(response, "text", "")),
            expected_tab=SEARCH_CONTRACTS[spec.operation]["tab"],
        )
        if search_type != expected_search_type:
            raise PalmBeachTaxDeedSourceChanged(
                f"search type changed from {expected_search_type!r} "
                f"to {search_type!r}"
            )
        return search_type

    def grid_page(
        self,
        search_type: str,
        *,
        page: int,
        rows: int = NATIVE_PAGE_SIZE,
    ) -> GridPage:
        if rows not in NATIVE_PAGE_SIZES:
            raise PalmBeachTaxDeedQueryError(
                "grid page size must be one of the source's native choices"
            )
        response = self._request(
            "GET",
            GRID_URL,
            params={
                "SearchType": search_type,
                "_search": "false",
                "rows": rows,
                "page": page,
                "sidx": "",
                "sord": "asc",
            },
        )
        try:
            if hasattr(response, "json"):
                payload = response.json()
            else:
                payload = json.loads(str(getattr(response, "text", "")))
        except (TypeError, ValueError) as error:
            raise PalmBeachTaxDeedSourceChanged(
                "grid endpoint did not return JSON"
            ) from error
        if not isinstance(payload, Mapping):
            raise PalmBeachTaxDeedSourceChanged(
                "grid endpoint returned a non-object JSON value"
            )
        parsed = parse_grid_page(payload)
        if parsed.page != page and not (
            parsed.total_records == 0 and page == 1
        ):
            raise PalmBeachTaxDeedSourceChanged(
                f"grid returned page {parsed.page}, expected {page}"
            )
        return parsed

    def search(
        self,
        spec: SearchSpec,
        *,
        limit: int | None,
        cursor: str | None,
    ) -> SearchBatch:
        if limit is not None and limit < 1:
            raise PalmBeachTaxDeedQueryError("limit must be positive")
        discovery = self.discovery()
        search_type = self.submit_search(spec, discovery)
        first_page = self.grid_page(search_type, page=1)
        snapshot_fingerprint = _page_snapshot_fingerprint(first_page)
        cursor_state = (
            _decode_cursor(cursor, spec=spec) if cursor is not None else None
        )
        if cursor_state is not None:
            current_snapshot = {
                "total_records": first_page.total_records,
                "total_pages": first_page.total_pages,
                "snapshot_fingerprint": snapshot_fingerprint,
            }
            expected_snapshot = {
                key: cursor_state[key]
                for key in current_snapshot
            }
            if current_snapshot != expected_snapshot:
                raise PalmBeachTaxDeedSnapshotChanged(
                    "the source result snapshot changed; restart this search"
                )
            page_number = int(cursor_state["page"])
            row_offset = int(cursor_state["offset"])
        else:
            page_number = 1
            row_offset = 0

        if first_page.total_records == 0:
            return SearchBatch(
                records=(),
                total_records=0,
                total_pages=0,
                snapshot_fingerprint=snapshot_fingerprint,
                next_cursor=None,
                complete=True,
            )
        expected_total_pages = (
            first_page.total_records + NATIVE_PAGE_SIZE - 1
        ) // NATIVE_PAGE_SIZE
        if first_page.total_pages != expected_total_pages:
            raise PalmBeachTaxDeedSourceChanged(
                "jqGrid page total does not match its record total and "
                "requested native page size"
            )
        if page_number > first_page.total_pages:
            raise PalmBeachTaxDeedQueryError(
                "cursor page is beyond the current source result set"
            )

        records: list[dict[str, Any]] = []
        seen_row_ids: set[str] = set()
        next_page = page_number
        next_offset = row_offset
        complete = False
        while page_number <= first_page.total_pages:
            page = (
                first_page
                if page_number == 1
                else self.grid_page(search_type, page=page_number)
            )
            if (
                page.total_records != first_page.total_records
                or page.total_pages != first_page.total_pages
            ):
                raise PalmBeachTaxDeedSnapshotChanged(
                    "jqGrid totals changed during traversal",
                    records=records,
                )
            expected_rows = (
                NATIVE_PAGE_SIZE
                if page_number < first_page.total_pages
                else first_page.total_records
                - NATIVE_PAGE_SIZE * (first_page.total_pages - 1)
            )
            if len(page.rows) != expected_rows:
                raise PalmBeachTaxDeedSnapshotChanged(
                    f"jqGrid page {page_number} returned {len(page.rows)} "
                    f"rows; expected {expected_rows}",
                    records=records,
                )
            if row_offset > len(page.rows):
                raise PalmBeachTaxDeedSnapshotChanged(
                    "cursor offset exceeds the current source page",
                    records=records,
                )
            for index in range(row_offset, len(page.rows)):
                raw_row = page.rows[index]
                row_id = _clean_text(raw_row.get("id"))
                if row_id in seen_row_ids:
                    raise PalmBeachTaxDeedSnapshotChanged(
                        "a portal row repeated across source pages",
                        records=records,
                    )
                seen_row_ids.add(row_id)
                records.append(
                    normalize_grid_row(
                        raw_row,
                        source_page=page_number,
                        source_position=(page_number - 1) * NATIVE_PAGE_SIZE
                        + index
                        + 1,
                        discovery=discovery,
                        search_spec=spec,
                    )
                )
                if limit is not None and len(records) >= limit:
                    if index + 1 < len(page.rows):
                        next_page = page_number
                        next_offset = index + 1
                    else:
                        next_page = page_number + 1
                        next_offset = 0
                    complete = next_page > first_page.total_pages
                    break
            else:
                page_number += 1
                row_offset = 0
                next_page = page_number
                next_offset = 0
                continue
            break
        else:
            complete = True

        if next_page > first_page.total_pages:
            complete = True
        if complete and first_page.total_pages > 1:
            final_first_page = self.grid_page(search_type, page=1)
            if _page_snapshot_fingerprint(final_first_page) != snapshot_fingerprint:
                raise PalmBeachTaxDeedSnapshotChanged(
                    "the source result snapshot changed before traversal completed",
                    records=records,
                )
        next_cursor = (
            None
            if complete
            else _encode_cursor(
                spec=spec,
                page=next_page,
                offset=next_offset,
                total_records=first_page.total_records,
                total_pages=first_page.total_pages,
                snapshot_fingerprint=snapshot_fingerprint,
            )
        )
        completeness = {
            "source_reported_total": first_page.total_records,
            "source_reported_pages": first_page.total_pages,
            "native_page_size": NATIVE_PAGE_SIZE,
            "records_returned": len(records),
            "complete_for_bound_snapshot": complete,
            "snapshot_fingerprint": snapshot_fingerprint,
        }
        for record in records:
            record["retrieval_completeness"] = completeness
        return SearchBatch(
            records=tuple(records),
            total_records=first_page.total_records,
            total_pages=first_page.total_pages,
            snapshot_fingerprint=snapshot_fingerprint,
            next_cursor=next_cursor,
            complete=complete,
        )

    def detail(self, portal_row_id: str) -> dict[str, Any] | None:
        if not str(portal_row_id).isdigit():
            raise PalmBeachTaxDeedQueryError(
                "portal row ID must contain digits only"
            )
        response = self._request(
            "GET",
            DETAIL_URL,
            params={"id": str(portal_row_id)},
            accepted_statuses={404},
        )
        if int(getattr(response, "status_code", 0)) == 404:
            return None
        return parse_detail(
            str(getattr(response, "text", "")),
            portal_row_id=str(portal_row_id),
        )

    def document(
        self,
        case_record: Mapping[str, Any],
        native_document_id: str,
    ) -> tuple[Mapping[str, Any], PDFArtifact]:
        document_id = _clean_text(native_document_id)
        if not document_id.isdigit():
            raise PalmBeachTaxDeedQueryError(
                "document image ID must contain digits only"
            )
        documents = case_record.get("documents")
        if not isinstance(documents, list):
            raise PalmBeachTaxDeedSourceChanged(
                "case detail is missing its document inventory"
            )
        matches = [
            document
            for document in documents
            if isinstance(document, Mapping)
            and _clean_text(document.get("native_document_id")) == document_id
        ]
        if len(matches) != 1:
            raise PalmBeachTaxDeedQueryError(
                "document image ID is not a unique available document "
                "on this case occurrence"
            )
        document = matches[0]
        if document.get("access_state") != "public_pdf":
            raise PalmBeachTaxDeedDocumentUnavailable(
                "the selected source document is marked Image Not Available",
                case_record=case_record,
                document=document,
            )
        response = self._request(
            "GET",
            f"{IMAGE_ROOT}{document_id}",
            accepted_statuses={404},
        )
        if int(getattr(response, "status_code", 0)) == 404:
            raise PalmBeachTaxDeedDocumentUnavailable(
                "the listed source document no longer returns a public image",
                case_record=case_record,
                document=document,
            )
        content = bytes(getattr(response, "content", b""))
        media_type = (
            _header_value(getattr(response, "headers", {}), "Content-Type")
            or ""
        ).split(";", 1)[0].strip()
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise PalmBeachTaxDeedDocumentUnavailable(
                "the source document route did not return a public PDF",
                case_record=case_record,
                document=document,
            )
        return document, PDFArtifact(
            content=content,
            media_type=media_type,
            content_disposition=_header_value(
                getattr(response, "headers", {}),
                "Content-Disposition",
            ),
            sha256=hashlib.sha256(content).hexdigest(),
        )


def _search_spec(args: argparse.Namespace) -> SearchSpec:
    if args.command not in SEARCH_CONTRACTS:
        raise PalmBeachTaxDeedQueryError(
            f"{args.command} is not a search operation"
        )
    value = getattr(args, "value", None)
    from_date = getattr(args, "from_date", None)
    to_date = getattr(args, "to_date", None)
    if args.command == "sale-date":
        from_date = value
        to_date = getattr(args, "to_sale_date", None) or value
        value = None
    return SearchSpec(
        operation=args.command,
        value=_clean_text(value) or None,
        from_date=_iso_date(from_date) or _clean_text(from_date) or None,
        to_date=_iso_date(to_date) or _clean_text(to_date) or None,
    )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    if args.command in SEARCH_CONTRACTS:
        spec = _search_spec(args)
        parameters = {
            **spec.binding(),
            "native_page_size": NATIVE_PAGE_SIZE,
        }
        requested_limit = args.limit
        cursor = args.cursor
    elif args.command == "detail":
        parameters = {"portal_row_id": args.portal_row_id}
        requested_limit = None
        cursor = None
    elif args.command == "document":
        parameters = {
            "portal_row_id": args.portal_row_id,
            "native_document_id": args.native_document_id,
        }
        requested_limit = None
        cursor = None
    elif args.command == "probe":
        parameters = {"sentinel_portal_row_id": SENTINEL_ROW_ID}
        requested_limit = None
        cursor = None
    else:
        parameters = {}
        requested_limit = None
        cursor = None
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata={
                "transport_contract": (
                    "native_form_session_then_jqgrid_pages"
                ),
                "grid_schema_fingerprint": GRID_SCHEMA_FINGERPRINT,
            },
        ),
    )


def _artifact_record(
    case_record: Mapping[str, Any],
    document: Mapping[str, Any],
    artifact: PDFArtifact,
    destination: Path,
) -> dict[str, Any]:
    document_id = _clean_text(document.get("native_document_id"))
    return {
        "source_id": SOURCE_ID,
        "record_kind": "tax_deed_document_artifact",
        "source_record_id": _clean_text(case_record.get("source_record_id")),
        "portal_row_id": _clean_text(case_record.get("portal_row_id")),
        "native_case_id": _clean_text(case_record.get("native_case_id")),
        "case_number": _clean_text(case_record.get("case_number")),
        "native_certificate_id": _clean_text(
            case_record.get("native_certificate_id")
        ),
        "certificate_number": _clean_text(
            case_record.get("certificate_number")
        ),
        "native_document_id": document_id,
        "document_occurrence_id": document.get("document_occurrence_id"),
        "document_label": document.get("label"),
        "parent_canonical_ref": case_record.get("canonical_ref"),
        "canonical_ref": (
            f"{case_record['canonical_ref']}/document/{document_id}"
        ),
        "evidence_ref": document.get("canonical_ref"),
        "media_type": artifact.media_type,
        "byte_count": len(artifact.content),
        "sha256": artifact.sha256,
        "content_disposition": artifact.content_disposition,
        "document_output": str(destination),
        "source_url": f"{IMAGE_ROOT}{document_id}",
        "jurisdiction": JURISDICTION.to_dict(),
    }


def run_probe(
    client: PalmBeachTaxDeedClient | Any | None = None,
) -> dict[str, Any]:
    """Probe stable routes/schema separately from rolling selector/grid state."""

    source_client = client or PalmBeachTaxDeedClient()
    discovery = source_client.discovery()
    observed_statuses = {
        _clean_text(item.get("label")): _clean_text(item.get("native_value"))
        for item in discovery.status_options
    }
    if observed_statuses != dict(OBSERVED_STATUS_OPTIONS):
        raise PalmBeachTaxDeedSourceChanged(
            "the source's status label/value contract changed"
        )
    spec = SearchSpec(operation="lands-available")
    search_type = source_client.submit_search(spec, discovery)
    lands_page = source_client.grid_page(search_type, page=1)
    detail = source_client.detail(SENTINEL_ROW_ID)
    if detail is None:
        raise PalmBeachTaxDeedSourceChanged(
            "known tax-deed detail sentinel no longer resolves"
        )
    expected = {
        "case_number": SENTINEL_CASE_NUMBER,
        "certificate_number": SENTINEL_CERTIFICATE_NUMBER,
        "parcel_id": SENTINEL_PARCEL_ID,
    }
    if any(detail.get(key) != value for key, value in expected.items()):
        raise PalmBeachTaxDeedSourceChanged(
            "known tax-deed detail sentinel changed identity"
        )
    documents = detail.get("documents")
    sentinel_documents = [
        document
        for document in documents
        if isinstance(document, Mapping)
        and document.get("native_document_id") == SENTINEL_DOCUMENT_ID
        and document.get("label") == SENTINEL_DOCUMENT_LABEL
    ]
    if len(sentinel_documents) != 1:
        raise PalmBeachTaxDeedSourceChanged(
            "known tax-deed document sentinel changed identity"
        )
    document, artifact = source_client.document(
        detail,
        SENTINEL_DOCUMENT_ID,
    )
    sale_dates = list(discovery.sale_dates)
    sale_date_values = [
        item["date"] for item in sale_dates if item.get("date")
    ]
    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_health_check",
        "native_document_id": "live-sentinel",
        "status": "ok",
        "stable_contract": {
            "home_url": HOME_URL,
            "post_url": POST_URL,
            "grid_url": GRID_URL,
            "detail_url": DETAIL_URL,
            "image_root": IMAGE_ROOT,
            "search_types": {
                operation: contract["search_type"]
                for operation, contract in SEARCH_CONTRACTS.items()
            },
            "status_label_value_map": observed_statuses,
            "native_page_sizes": list(NATIVE_PAGE_SIZES),
            "grid_fields": list(GRID_FIELDS),
            "grid_schema_fingerprint": GRID_SCHEMA_FINGERPRINT,
            "identity_contract": {
                "portal_case_occurrence_locator": "row_id",
                "case_identity": "case_number",
                "certificate_identity": "certificate_number",
                "parcel_join": "reversible_17_digit_pcn",
                "document_identity": "image_id",
                "identities_collapsed": False,
            },
        },
        "rolling_observation": {
            "website_version": discovery.website_version,
            "sale_date_count": len(sale_dates),
            "first_published_sale_date": (
                min(sale_date_values) if sale_date_values else None
            ),
            "last_published_sale_date": (
                max(sale_date_values) if sale_date_values else None
            ),
            "lands_available_total": lands_page.total_records,
            "lands_available_pages": lands_page.total_pages,
            "lands_available_first_page_row_ids": [
                row["id"] for row in lands_page.rows
            ],
            "sentinel_status": detail.get("status"),
            "sentinel_document_inventory_count": len(documents),
        },
        "artifact_identity": {
            "portal_row_id": SENTINEL_ROW_ID,
            "case_number": SENTINEL_CASE_NUMBER,
            "certificate_number": SENTINEL_CERTIFICATE_NUMBER,
            "native_document_id": SENTINEL_DOCUMENT_ID,
            "document_occurrence_id": document.get(
                "document_occurrence_id"
            ),
            "media_type": artifact.media_type,
            "sha256": artifact.sha256,
        },
        "request_count": source_client.request_count,
        "source_url": HOME_URL,
    }


def _failure(
    query: PublicRecordsQuery,
    error: PalmBeachTaxDeedError,
) -> PublicRecordsResult:
    records: Sequence[Mapping[str, Any]] = ()
    if isinstance(error, PalmBeachTaxDeedSnapshotChanged):
        status = (
            ResultStatus.PARTIAL
            if error.records
            else ResultStatus.SOURCE_CHANGED
        )
        code = "source_snapshot_changed"
        category = "pagination"
        records = error.records
    elif isinstance(error, PalmBeachTaxDeedSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_changed"
        category = "source_schema"
    elif isinstance(error, PalmBeachTaxDeedRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "source_rate_limited"
        category = "rate_limit"
    elif isinstance(error, PalmBeachTaxDeedTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "source_transport_failed"
        category = "transport"
    elif isinstance(error, PalmBeachTaxDeedHTTPError):
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
    elif isinstance(error, PalmBeachTaxDeedDocumentUnavailable):
        status = ResultStatus.HUMAN_REQUIRED
        code = "document_unavailable_online"
        category = "document_access"
        records = [error.case_record]
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
                in {
                    ResultStatus.UNAVAILABLE,
                    ResultStatus.RATE_LIMITED,
                },
                details={
                    "official_alternatives": official_routes(),
                },
            )
        ],
        records=records,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: PalmBeachTaxDeedClient | Any | None = None,
) -> PublicRecordsResult:
    try:
        query = build_query(args)
    except PalmBeachTaxDeedError as error:
        query = PublicRecordsQuery(
            source=SOURCE_METADATA,
            jurisdiction=JURISDICTION,
            query=QueryMetadata(operation=args.command),
        )
        result = _failure(query, error)
        _log(canonical_json(query.to_dict()), None)
        return result

    source_client = client or PalmBeachTaxDeedClient(
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        retry_attempts=getattr(
            args,
            "retry_attempts",
            DEFAULT_RETRY_ATTEMPTS,
        ),
    )
    try:
        if args.command in SEARCH_CONTRACTS:
            batch = source_client.search(
                _search_spec(args),
                limit=args.limit,
                cursor=args.cursor,
            )
            result = PublicRecordsResult.success(
                query,
                batch.records,
                next_cursor=batch.next_cursor,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "detail":
            record = source_client.detail(args.portal_row_id)
            result = PublicRecordsResult.success(
                query,
                [record] if record else [],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "document":
            record = source_client.detail(args.portal_row_id)
            if record is None:
                result = PublicRecordsResult.success(
                    query,
                    [],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                document, artifact = source_client.document(
                    record,
                    args.native_document_id,
                )
                destination = Path(args.document_output).expanduser()
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(artifact.content)
                artifact_record = _artifact_record(
                    record,
                    document,
                    artifact,
                    destination,
                )
                result = PublicRecordsResult.success(
                    query,
                    [artifact_record],
                    raw_artifact_refs=[str(destination)],
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command == "discovery":
            result = PublicRecordsResult.success(
                query,
                [source_client.discovery().to_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "routes":
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "source_id": SOURCE_ID,
                        "record_kind": "official_alternative_routes",
                        "native_document_id": "official-routes",
                        "canonical_ref": canonical_property_ref(
                            SOURCE_ID,
                            COUNTY_GEOID,
                            "source-routes",
                            "official-routes",
                        ),
                        "routes": official_routes(),
                        "source_url": OFFICIAL_PAGE_URL,
                    }
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            result = PublicRecordsResult.success(
                query,
                [run_probe(source_client)],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise PalmBeachTaxDeedQueryError(
                f"unsupported command: {args.command}"
            )
    except PalmBeachTaxDeedError as error:
        result = _failure(query, error)

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
) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Palm Beach Tax Deeds {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Palm Beach Tax Deeds {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "tax_deed_case_occurrence":
            print(
                f"- row {record.get('portal_row_id')} | "
                f"{record.get('case_number') or ''} | "
                f"{record.get('parcel_id') or ''} | "
                f"{record.get('status') or ''}"
            )
        elif record.get("record_kind") == "tax_deed_document_artifact":
            print(
                f"- {record.get('case_number')} | "
                f"{record.get('document_label')} -> "
                f"{record.get('document_output')}"
            )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
        help="Attempts for transient transport failures",
    )
    add_output_args(parser)


def _add_search_args(
    parser: argparse.ArgumentParser,
    *,
    value: bool = True,
    date_range: bool = False,
) -> None:
    if value:
        parser.add_argument("value")
    if date_range:
        parser.add_argument("--from-date", required=True)
        parser.add_argument("--to-date", required=True)
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help=(
            "Return at most this many records and emit a bound continuation; "
            "omit to exhaust the source-reported result set"
        ),
    )
    parser.add_argument("--cursor")
    _add_transport_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search Palm Beach County Clerk tax-deed cases, exact details, "
            "document inventories, and public PDFs"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("certificate", "Search by tax certificate number"),
        ("case", "Search by tax-deed case number"),
        ("parcel", "Search by parcel control number"),
        ("tax-collector", "Search by Tax Collector number"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        _add_search_args(subparser)

    for command, help_text in (
        ("applicant", "Search source-reported applicant names"),
        ("owner", "Search source-reported property-owner labels"),
        ("status", "Search one live source status label/value"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        _add_search_args(subparser, date_range=True)

    sale_date = subparsers.add_parser(
        "sale-date",
        help="Search one current source-published auction-date range",
    )
    sale_date.add_argument("value", help="From date")
    sale_date.add_argument("--to-sale-date", help="To date; defaults to from date")
    sale_date.add_argument("--limit", type=_positive_int)
    sale_date.add_argument("--cursor")
    _add_transport_args(sale_date)

    lands = subparsers.add_parser(
        "lands-available",
        help="Search the current source-published Lands Available set",
    )
    _add_search_args(lands, value=False)

    detail = subparsers.add_parser(
        "detail",
        help="Fetch one exact portal row ID and its document inventory",
    )
    detail.add_argument("portal_row_id")
    _add_transport_args(detail)

    document = subparsers.add_parser(
        "document",
        help="Fetch one listed public PDF after validating its case occurrence",
    )
    document.add_argument("portal_row_id")
    document.add_argument("native_document_id")
    document.add_argument("--document-output", required=True)
    _add_transport_args(document)

    discovery = subparsers.add_parser(
        "discovery",
        help="List live selectors, rolling sale dates, and source routes",
    )
    _add_transport_args(discovery)

    routes = subparsers.add_parser(
        "routes",
        help="List field-specific official complements",
    )
    _add_transport_args(routes)

    probe = subparsers.add_parser(
        "probe",
        help="Probe stable contracts and rolling source state",
    )
    _add_transport_args(probe)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
