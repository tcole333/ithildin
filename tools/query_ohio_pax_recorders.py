#!/usr/bin/env python3
"""Query official Ohio recorder records exposed through the DTS/PAX family.

The adapter treats the shared PAX application shape as a transport family while
preserving each county as its own source component:

* Delaware County exposes anonymous search, detail, image metadata, and PDF
  retrieval after accepting the public-site disclaimer in a cookie session.
* Licking County requires an account for PAX discovery, but the county also
  publishes anonymous exact-instrument detail and PDF routes when an instrument
  number is already known.

Recorder index rows and document images are recorded-instrument evidence.  They
remain distinct from assessor ownership observations, tax accounts, foreclosure
listings, and court dockets.

Omitting ``--limit`` exhausts every native Delaware detail page for the selected
query.  An explicit limit returns a query-bound continuation cursor.

Examples:
    uv run python tools/query_ohio_pax_recorders.py sources
    uv run python tools/query_ohio_pax_recorders.py search \
      --source us-oh-delaware-county-recorder-pax --name SMITH
    uv run python tools/query_ohio_pax_recorders.py instrument \
      --source us-oh-licking-county-recorder-pax 202504110006201
    uv run python tools/query_ohio_pax_recorders.py document-info \
      --source us-oh-delaware-county-recorder-pax 202600019719
    uv run python tools/query_ohio_pax_recorders.py download \
      --source us-oh-licking-county-recorder-pax 202504110006201 \
      --destination /tmp/licking-202504110006201.pdf
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, urljoin, urlparse

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
        TransportError,
        failure_result,
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
        TransportError,
        failure_result,
        system_trust_session,
    )


STATE_CODE = "OH"
STATE_FIPS = "39"
PLATFORM_FAMILY = "dts_paxworld"
CURSOR_PREFIX = "ohio-pax-recorders:v1:"
CURSOR_VERSION = 1
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
OUTPUT_SCHEMA_VERSION = "ohio-pax-recorder-sources/1.0"

DELAWARE_SOURCE_ID = "us-oh-delaware-county-recorder-pax"
LICKING_SOURCE_ID = "us-oh-licking-county-recorder-pax"
LICKING_DETAIL_SOURCE_ID = (
    "us-oh-licking-county-recorder-instrument-detail"
)
SOURCE_IDS = (DELAWARE_SOURCE_ID, LICKING_SOURCE_ID)

OGRIP_SOURCE_ID = "us-oh-ogrip-statewide-parcels"

DELAWARE_SENTINEL = "202600019719"
LICKING_SENTINEL = "202504110006201"
LICKING_DOCUMENT_SENTINEL = "201310100025382"

RECORDER_WARNING = (
    "Recorder index data and public document images identify recorded "
    "instruments; they are not a title opinion or a certified-copy substitute."
)
SOURCE_ROLE_WARNING = (
    "Assessor, tax, foreclosure, and court sources are complementary evidence "
    "domains and are not interchangeable with recorder instruments."
)


@dataclass(frozen=True)
class PAXTenant:
    """One county-owned source component in the DTS/PAX family."""

    key: str
    source_id: str
    county_name: str
    county_fips: str
    authority: str
    pax_root: str
    official_info_url: str
    anonymous_discovery: bool
    sentinel_instrument: str
    exact_detail_url_template: str | None = None
    exact_document_url_template: str | None = None
    access_observation: str = ""
    complements: tuple[Mapping[str, Any], ...] = ()

    @property
    def host(self) -> str:
        host = urlparse(self.pax_root).hostname
        if host is None:
            raise ValueError(f"tenant {self.key} has no PAX host")
        return host

    @property
    def jurisdiction(self) -> JurisdictionMetadata:
        return JurisdictionMetadata(
            jurisdiction_id=self.county_fips,
            name=f"{self.county_name}, Ohio",
            state_code=STATE_CODE,
            county_fips=self.county_fips,
            locality=self.county_name,
            metadata={"state_fips": STATE_FIPS},
        )

    @property
    def source_metadata(self) -> SourceMetadata:
        representations: dict[str, Any] = {
            "pax_entry": "aspnet_disclaimer_or_login",
            "pax_search": (
                "anonymous_session"
                if self.anonymous_discovery
                else "account_required"
            ),
        }
        if self.anonymous_discovery:
            representations.update(
                {
                    "pax_detail": "anonymous_session_html",
                    "image_metadata": "anonymous_session_json",
                    "document": "anonymous_session_pdf",
                }
            )
        if self.exact_detail_url_template:
            representations["exact_instrument_detail"] = "anonymous_html"
        if self.exact_document_url_template:
            representations["document"] = "anonymous_pdf"
        return SourceMetadata(
            source_id=self.source_id,
            name=f"{self.county_name} Recorder DTS/PAX",
            source_role="county_recorded_instrument_index_detail_and_document",
            base_url=self.pax_root,
            dataset_id=f"ohio-pax-{self.key}",
            metadata={
                "authority": self.authority,
                "operator": "Document Technology Systems, Ltd.",
                "platform_family": PLATFORM_FAMILY,
                "county_fips": self.county_fips,
                "official_info_url": self.official_info_url,
                "anonymous_discovery": self.anonymous_discovery,
                "access_observation": self.access_observation,
                "representations": representations,
                "record_identity": (
                    {
                        "stable_key": "InstrumentReferenceId",
                        "record_identity_source_id": self.source_id,
                    }
                    if self.source_id == DELAWARE_SOURCE_ID
                    else {
                        "stable_key": "instrument_number",
                        "record_identity_source_id": self.source_id,
                        "alternate_representation_source_id": (
                            LICKING_DETAIL_SOURCE_ID
                        ),
                    }
                ),
                "family_contract": {
                    "entry": "ASP.NET disclaimer/login form",
                    "search_page": "views/search",
                    "detail_search_api": "api/SearchDetail",
                    "image_metadata_api": "api/ImageDetail",
                    "image_api": "api/Image",
                    "native_pagination": "FirstRecordNum/LastRecordNum",
                    "stable_pax_identity": "InstrumentReferenceId",
                },
                "complements": [dict(value) for value in self.complements],
            },
        )


DELAWARE = PAXTenant(
    key="delaware",
    source_id=DELAWARE_SOURCE_ID,
    county_name="Delaware County",
    county_fips="39041",
    authority="Delaware County Recorder",
    pax_root="https://delaware.dts-central-oh.com/PaxWorld/",
    official_info_url=(
        "https://recorder.co.delaware.oh.us/records-search-page/"
    ),
    anonymous_discovery=True,
    sentinel_instrument=DELAWARE_SENTINEL,
    access_observation=(
        "Anonymous guest search, detail, image metadata, and free PDF viewing "
        "were live-verified after the disclaimer session on 2026-07-30."
    ),
    complements=(
        {
            "source_id": OGRIP_SOURCE_ID,
            "relationship": "parcel_geometry_and_local_cama_routing",
            "join_keys": [
                "parcel_identifier",
                "situs_or_legal_description",
            ],
        },
        {
            "name": "Delaware County Auditor property search and GIS",
            "relationship": "assessment_and_parcel_context",
            "join_keys": [
                "parcel_identifier",
                "situs_address",
                "party_name",
            ],
        },
        {
            "name": "Delaware County Treasurer property lookup",
            "relationship": "tax_account_context",
            "join_keys": ["parcel_identifier"],
        },
    ),
)

LICKING = PAXTenant(
    key="licking",
    source_id=LICKING_SOURCE_ID,
    county_name="Licking County",
    county_fips="39089",
    authority="Licking County Recorder",
    pax_root="https://apps.lickingcounty.gov/recorder/paxworld/",
    official_info_url="https://lickingcounty.gov/depts/recorder/default.htm",
    anonymous_discovery=False,
    sentinel_instrument=LICKING_SENTINEL,
    exact_detail_url_template=(
        "https://apps.lickingcounty.gov/recorder/record-search/"
        "?instrument={instrument}"
    ),
    exact_document_url_template=(
        "https://apps.lickingcounty.gov/recorder/record-search/"
        "document?instrument={instrument}"
    ),
    access_observation=(
        "PAX discovery required an account on 2026-07-30. The county's "
        "exact-instrument detail and range-capable PDF routes were anonymous."
    ),
    complements=(
        {
            "source_id": OGRIP_SOURCE_ID,
            "relationship": "parcel_geometry_and_local_cama_routing",
            "join_keys": [
                "parcel_identifier",
                "situs_or_legal_description",
            ],
        },
        {
            "name": "Licking County Recorder General Index Department",
            "url": "https://lickingcounty.gov/depts/recorder/default.htm",
            "relationship": "in_office_index_search_and_current_copy_request",
            "coverage": "records date to the early 1800s",
            "contact": "740-670-5300",
        },
        {
            "name": "Licking County Records & Archives recorder holdings",
            "url": (
                "https://lickingcounty.gov/depts/records_n_archives/"
                "list_of_record_collections_by_department/recorder.htm"
            ),
            "relationship": "historical_recorder_archive_and_request_route",
            "coverage": {
                "deeds": "1803-1918",
                "mortgages": "1851-1941",
            },
            "request_url": (
                "https://lickingcounty.gov/depts/records_n_archives/"
            ),
            "contact": "740-670-5121",
        },
    ),
)

TENANTS = (DELAWARE, LICKING)
TENANTS_BY_SOURCE = {tenant.source_id: tenant for tenant in TENANTS}
QUERY_SOURCE_IDS = (*SOURCE_IDS, LICKING_DETAIL_SOURCE_ID)
TENANTS_BY_QUERY_SOURCE = {
    **TENANTS_BY_SOURCE,
    LICKING_DETAIL_SOURCE_ID: LICKING,
}


def source_metadata(source_id: str) -> SourceMetadata:
    """Return metadata for a queryable county component."""

    if source_id == LICKING_DETAIL_SOURCE_ID:
        return SourceMetadata(
            source_id=LICKING_DETAIL_SOURCE_ID,
            name="Licking County Recorder Exact-Instrument Detail",
            source_role="county_recorded_instrument_exact_detail_and_document",
            base_url=(
                "https://apps.lickingcounty.gov/recorder/record-search/"
            ),
            dataset_id="ohio-pax-licking-exact-instrument",
            metadata={
                "authority": LICKING.authority,
                "platform_family": "licking_recorder_exact_instrument_detail",
                "county_fips": LICKING.county_fips,
                "record_identity_source_id": LICKING_SOURCE_ID,
                "representation_source_id": LICKING_DETAIL_SOURCE_ID,
                "independent_corroboration": False,
                "stable_key": "instrument_number",
                "representations": {
                    "exact_instrument_detail": "anonymous_html",
                    "document": "anonymous_pdf",
                },
            },
        )
    try:
        return TENANTS_BY_SOURCE[source_id].source_metadata
    except KeyError as error:
        raise PAXSelectionError(
            "source_not_selected",
            "select a supported Ohio recorder source component",
        ) from error


@dataclass(frozen=True)
class TextPage:
    text: str
    source_url: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class BinaryDocument:
    content: bytes
    source_url: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class PAXSessionConfig:
    session_id: str
    session_ticket: str
    user_id: int
    rows_per_page: int
    version: str | None
    data_current_through: str | None
    is_guest: bool
    freedom: bool
    images_enabled: bool
    image_viewing_enabled: bool
    search_url: str


@dataclass(frozen=True)
class DetailBatch:
    records: tuple[Mapping[str, Any], ...]
    total_results: int
    filtered_results: int
    first_position: int | None
    last_position: int | None
    source_url: str


@dataclass(frozen=True)
class CursorState:
    source_id: str
    query_fingerprint: str
    offset: int
    anchor: str
    total_results: int


class PAXSelectionError(ValueError):
    """Structured caller selection or continuation failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        category: str = "query_selection",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=False,
            details=self.details,
        )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _headers(response: Any) -> dict[str, str]:
    return {
        str(key).casefold(): str(value)
        for key, value in dict(getattr(response, "headers", {})).items()
    }


def _retry_after(response: Any) -> float | None:
    value = _headers(response).get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _tenant_url(tenant: PAXTenant, value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != tenant.host:
        raise SourceSchemaError(
            "Ohio recorder source returned an unexpected host",
            url=value,
            details={"expected_host": tenant.host},
        )
    return value


def parse_entry_access(html: str, source_url: str) -> dict[str, Any]:
    """Parse the PAX entry page's observed access settings."""

    if "(DTS)Public Access" not in html:
        raise SourceSchemaError(
            "PAX entry marker is missing",
            url=source_url,
        )
    login_match = re.search(
        r"\bvar\s+loginRequired\s*=\s*['\"](True|False)['\"]",
        html,
        re.IGNORECASE,
    )
    if login_match is None:
        raise SourceSchemaError(
            "PAX entry page no longer publishes loginRequired",
            url=source_url,
        )
    register_match = re.search(
        r"\bvar\s+registerNewUserEnabled\s*=\s*['\"](True|False)['\"]",
        html,
        re.IGNORECASE,
    )
    version_match = re.search(r"\b20\d{2}\.\d+\.\d+\.\d+\b", html)
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#form1")
    if form is None:
        raise SourceSchemaError(
            "PAX entry form is missing",
            url=source_url,
        )
    hidden_fields = {
        str(element.get("name")): str(element.get("value") or "")
        for element in form.select("input[type=hidden][name]")
    }
    if "__VIEWSTATE" not in hidden_fields:
        raise SourceSchemaError(
            "PAX entry form no longer contains __VIEWSTATE",
            url=source_url,
        )
    return {
        "login_required": login_match.group(1).casefold() == "true",
        "registration_enabled": (
            register_match is not None
            and register_match.group(1).casefold() == "true"
        ),
        "version": version_match.group(0) if version_match else None,
        "form_action": urljoin(source_url, str(form.get("action") or "./")),
        "hidden_fields": hidden_fields,
        "disclaimer_present": bool(soup.select_one("#disclaimerAgreement")),
    }


def _js_string(html: str, key: str, source_url: str) -> str:
    match = re.search(
        rf"['\"]{re.escape(key)}['\"]\s*:\s*['\"]([^'\"]*)['\"]",
        html,
    )
    if match is None:
        raise SourceSchemaError(
            f"PAX search page no longer publishes {key}",
            url=source_url,
        )
    return match.group(1)


def _js_int(html: str, key: str, source_url: str) -> int:
    match = re.search(
        rf"['\"]{re.escape(key)}['\"]\s*:\s*(\d+)",
        html,
    )
    if match is None:
        raise SourceSchemaError(
            f"PAX search page no longer publishes {key}",
            url=source_url,
        )
    return int(match.group(1))


def _js_bool(html: str, key: str, source_url: str) -> bool:
    match = re.search(
        rf"['\"]{re.escape(key)}['\"]\s*:\s*(true|false)",
        html,
        re.IGNORECASE,
    )
    if match is None:
        raise SourceSchemaError(
            f"PAX search page no longer publishes {key}",
            url=source_url,
        )
    return match.group(1).casefold() == "true"


def parse_search_config(html: str, source_url: str) -> PAXSessionConfig:
    """Parse the guest-session identifiers and native page size."""

    required_markers = ("../api/SearchDetail", "Search_2.js", "InstrumentReferenceId")
    missing = [marker for marker in required_markers if marker not in html]
    if missing:
        raise SourceSchemaError(
            "PAX search contract markers changed",
            url=source_url,
            details={"missing_markers": missing},
        )
    rows_per_page = _js_int(html, "RowsPerPage", source_url)
    if rows_per_page <= 0:
        raise SourceSchemaError(
            "PAX native page size is invalid",
            url=source_url,
            details={"rows_per_page": rows_per_page},
        )
    current_label = _js_string(html, "SearchValidThruLabel", source_url)
    current_match = re.search(
        r"(\d{1,2})-(\d{1,2})-(\d{4})",
        current_label,
    )
    current_iso = None
    if current_match:
        month, day, year = (int(value) for value in current_match.groups())
        try:
            current_iso = date(year, month, day).isoformat()
        except ValueError:
            current_iso = None
    version = _js_string(html, "Version", source_url)
    return PAXSessionConfig(
        session_id=_js_string(html, "SessionId", source_url),
        session_ticket=_js_string(html, "SessionTicket", source_url),
        user_id=_js_int(html, "UserId", source_url),
        rows_per_page=rows_per_page,
        version=version or None,
        data_current_through=current_iso,
        is_guest=_js_bool(html, "IsGuest", source_url),
        freedom=_js_bool(html, "Freedom", source_url),
        images_enabled=_js_bool(html, "ImagesEnabled", source_url),
        image_viewing_enabled=_js_bool(
            html,
            "IsImageViewingEnabled",
            source_url,
        ),
        search_url=source_url,
    )


def _parse_outer_json(body: str, source_url: str) -> Any:
    try:
        outer = json.loads(body)
    except json.JSONDecodeError as error:
        raise SourceSchemaError(
            "PAX API returned malformed JSON",
            url=source_url,
        ) from error
    if isinstance(outer, str):
        try:
            return json.loads(outer)
        except json.JSONDecodeError as error:
            raise SourceSchemaError(
                "PAX API returned a non-object JSON string",
                url=source_url,
                details={"value": outer[:200]},
            ) from error
    return outer


def _field_values(detail_html: str) -> dict[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    fields: dict[str, str] = {}
    for label in soup.find_all("b"):
        key = _clean(label.get_text(" ", strip=True).rstrip(":"))
        if key is None:
            continue
        container = label.find_parent("span") or label.parent
        if not isinstance(container, Tag):
            continue
        text = _clean(container.get_text(" ", strip=True))
        label_text = _clean(label.get_text(" ", strip=True))
        if text is None or label_text is None:
            continue
        if text.casefold().startswith(label_text.casefold()):
            text = _clean(text[len(label_text) :])
        fields[key] = text or ""
    return fields


def _normalize_date(value: str | None) -> tuple[str | None, str | None]:
    text = _clean(value)
    if text is None:
        return None, None
    collapsed = re.sub(r"\s+", " ", text)
    patterns = (
        "%b %d %Y %I:%M%p",
        "%b %d %Y %I:%M:%S%p",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y",
    )
    for pattern in patterns:
        try:
            parsed = datetime.strptime(collapsed, pattern)
        except ValueError:
            continue
        return parsed.date().isoformat(), parsed.isoformat(timespec="seconds")
    return None, None


def _money_value(value: str | None) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    candidate = re.sub(r"[^0-9.-]", "", text)
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", candidate):
        return None
    return candidate


def _split_parties(value: str | None) -> list[str]:
    text = _clean(value)
    if text is None:
        return []
    return [
        party
        for party in (_clean(item) for item in re.split(r"\s+/\s+", text))
        if party is not None
    ]


def _detail_record(
    tenant: PAXTenant,
    *,
    reference_id: str,
    detail_html: str,
    source_url: str,
    source_position: int,
) -> dict[str, Any]:
    fields = _field_values(detail_html)
    instrument = _clean(fields.get("Instrument"))
    if instrument is None:
        raise SourceSchemaError(
            "PAX detail row does not contain an instrument number",
            url=source_url,
        )
    html_reference_match = re.search(
        r"\bid=['\"]detail(\d+)['\"]",
        detail_html,
        re.IGNORECASE,
    )
    if html_reference_match and html_reference_match.group(1) != reference_id:
        raise SourceSchemaError(
            "PAX detail row reference identity changed",
            url=source_url,
            details={
                "row_reference_id": reference_id,
                "html_reference_id": html_reference_match.group(1),
            },
        )
    recorded_date, recorded_at = _normalize_date(fields.get("Recorded"))
    grantors = _split_parties(fields.get("Grantor"))
    grantees = _split_parties(fields.get("Grantee"))
    page_count = None
    pages = _clean(fields.get("Pages"))
    if pages is not None and re.fullmatch(r"\d+", pages):
        page_count = int(pages)
    record = {
        "canonical_ref": (
            f"OHREC:{tenant.county_fips}:reference:{reference_id}"
        ),
        "evidence_ref": (
            f"PAX:{tenant.county_fips}:reference:{reference_id}"
        ),
        "source_id": tenant.source_id,
        "record_identity_source_id": tenant.source_id,
        "representation_source_id": tenant.source_id,
        "source_url": source_url,
        "portal_url": tenant.pax_root,
        "record_kind": "recorded_instrument_detail",
        "representation_kind": "pax_detail_html",
        "source_record_id": reference_id,
        "source_position": source_position,
        "instrument_reference_id": reference_id,
        "instrument_number": instrument,
        "recorded_at_source": _clean(fields.get("Recorded")),
        "recorded_date_iso": recorded_date,
        "recorded_at_iso": recorded_at,
        "instrument_status": _clean(fields.get("Status")),
        "document_type": _clean(fields.get("Document Type")),
        "page_count": page_count,
        "consideration_source": _clean(fields.get("Consideration")),
        "consideration_amount": _money_value(fields.get("Consideration")),
        "remarks": _clean(fields.get("Remarks")),
        "grantors": grantors,
        "grantees": grantees,
        "party_occurrences": [
            *[
                {"role": "grantor", "display_name": value}
                for value in grantors
            ],
            *[
                {"role": "grantee", "display_name": value}
                for value in grantees
            ],
        ],
        "legal_description": _clean(fields.get("Legal Description")),
        "return_to": _clean(fields.get("Return to")),
        "marginal_reference": _clean(fields.get("Marginal")),
        "book_page": _clean(fields.get("Book/Page")),
        "document_id": _clean(fields.get("Document Id")),
        "native_detail_fields": fields,
        "stable_identity": {
            "primary": "instrument_reference_id",
            "instrument_reference_id": reference_id,
            "instrument_number": instrument,
        },
        "source_response_schema_fingerprint": sha256_fingerprint(
            {"detail_labels": sorted(fields)}
        ),
    }
    return record


def parse_detail_response(
    body: str,
    tenant: PAXTenant,
    source_url: str,
) -> DetailBatch:
    """Normalize one native ``SearchDetail`` response page."""

    payload = _parse_outer_json(body, source_url)
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "PAX detail response is not an object",
            url=source_url,
        )
    required = {"recordsTotal", "recordsFiltered", "aaData", "Messages"}
    missing = sorted(required - set(payload))
    if missing:
        raise SourceSchemaError(
            "PAX detail response fields changed",
            url=source_url,
            details={"missing_fields": missing},
        )
    try:
        total = int(payload["recordsTotal"])
        filtered = int(payload["recordsFiltered"])
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "PAX detail response counts are invalid",
            url=source_url,
        ) from error
    rows = payload["aaData"]
    if not isinstance(rows, list):
        raise SourceSchemaError(
            "PAX detail response aaData is not a list",
            url=source_url,
        )
    messages = payload["Messages"]
    if not isinstance(messages, list):
        raise SourceSchemaError(
            "PAX detail response Messages is not a list",
            url=source_url,
        )
    records: list[dict[str, Any]] = []
    positions: list[int] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 3:
            raise SourceSchemaError(
                "PAX detail row shape changed",
                url=source_url,
            )
        try:
            position = int(row[0])
        except (TypeError, ValueError) as error:
            raise SourceSchemaError(
                "PAX detail row position is invalid",
                url=source_url,
            ) from error
        reference_id = _clean(row[1])
        detail_html = row[2]
        if reference_id is None or not isinstance(detail_html, str):
            raise SourceSchemaError(
                "PAX detail row identity or HTML is missing",
                url=source_url,
            )
        positions.append(position)
        records.append(
            _detail_record(
                tenant,
                reference_id=reference_id,
                detail_html=detail_html,
                source_url=source_url,
                source_position=position,
            )
        )
    if positions and positions != list(range(positions[0], positions[-1] + 1)):
        raise SourceSchemaError(
            "PAX detail page positions are not contiguous",
            url=source_url,
            details={"positions": positions},
        )
    return DetailBatch(
        records=tuple(records),
        total_results=total,
        filtered_results=filtered,
        first_position=positions[0] if positions else None,
        last_position=positions[-1] if positions else None,
        source_url=source_url,
    )


def parse_image_detail(
    body: str,
    source_url: str,
    *,
    expected_instrument: str,
    reference_id: str,
) -> dict[str, Any]:
    payload = _parse_outer_json(body, source_url)
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "PAX image metadata response is not an object",
            url=source_url,
        )
    required = {
        "InstrumentNumber",
        "HasImage",
        "IsOwned",
        "IsSearchOnly",
        "NumberOfPages",
        "IsVerified",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise SourceSchemaError(
            "PAX image metadata fields changed",
            url=source_url,
            details={"missing_fields": missing},
        )
    observed_instrument = _clean(payload.get("InstrumentNumber"))
    if observed_instrument != expected_instrument:
        raise SourceSchemaError(
            "PAX image metadata returned another instrument",
            url=source_url,
            details={
                "expected_instrument": expected_instrument,
                "observed_instrument": observed_instrument,
            },
        )
    page_count = payload.get("NumberOfPages")
    if isinstance(page_count, bool) or not isinstance(page_count, int):
        raise SourceSchemaError(
            "PAX image metadata page count is invalid",
            url=source_url,
        )
    return {
        "instrument_reference_id": reference_id,
        "instrument_number": observed_instrument,
        "has_image": bool(payload["HasImage"]),
        "page_count": page_count,
        "source_entitlement_owned": bool(payload["IsOwned"]),
        "search_only": bool(payload["IsSearchOnly"]),
        "verified": bool(payload["IsVerified"]),
        "single_page_archive": bool(payload.get("IsSinglePageArchive")),
        "image_recorded_date": _clean(payload.get("ImageRecordedDate")),
        "owned_pages": _clean(payload.get("OwnedPages")),
        "source_url": source_url,
        "source_response_schema_fingerprint": sha256_fingerprint(
            {"fields": sorted(payload)}
        ),
    }


def parse_licking_exact(
    html: str,
    source_url: str,
    *,
    expected_instrument: str,
) -> dict[str, Any] | None:
    """Parse Licking County's anonymous exact-instrument sidecar."""

    if "Licking County Recorder Document Information" not in html:
        raise SourceSchemaError(
            "Licking exact-instrument page marker is missing",
            url=source_url,
        )
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#content")
    if content is None:
        raise SourceSchemaError(
            "Licking exact-instrument content container is missing",
            url=source_url,
        )
    text = content.get_text(" ", strip=True)
    if re.search(r"\bNo results found\b", text, re.IGNORECASE):
        return None
    if re.search(r"\bFailed to retrieve URL parameters\b", text, re.IGNORECASE):
        raise SourceSchemaError(
            "Licking exact-instrument route did not receive an instrument",
            url=source_url,
        )
    fields: dict[str, str] = {}
    document_url = None
    for group in content.select(".form-group"):
        label = group.select_one("label")
        if label is None:
            continue
        key = _clean(label.get_text(" ", strip=True).rstrip(":"))
        if key is None:
            continue
        value_element = group.select_one("span")
        value = (
            _clean(value_element.get_text(" ", strip=True))
            if value_element is not None
            else None
        )
        link = group.select_one("a[href]")
        if link is not None:
            document_url = urljoin(source_url, str(link.get("href")))
            value = _clean(link.get_text(" ", strip=True))
        fields[key] = value or ""
    instrument = _clean(fields.get("Instrument #"))
    if instrument is None:
        raise SourceSchemaError(
            "Licking exact-instrument page has no instrument identity",
            url=source_url,
        )
    if instrument != expected_instrument:
        raise SourceSchemaError(
            "Licking exact-instrument page returned another instrument",
            url=source_url,
            details={
                "expected_instrument": expected_instrument,
                "observed_instrument": instrument,
            },
        )
    recorded_date, recorded_at = _normalize_date(fields.get("Recorded Date"))
    page_count = None
    pages = _clean(fields.get("Page Count"))
    if pages is not None and re.fullmatch(r"\d+", pages):
        page_count = int(pages)
    grantors = _split_parties(fields.get("Grantor"))
    grantees = _split_parties(fields.get("Grantee"))
    return {
        "canonical_ref": (
            f"OHREC:{LICKING.county_fips}:instrument:{instrument}"
        ),
        "evidence_ref": (
            f"PAX:{LICKING.county_fips}:instrument:{instrument}"
        ),
        "source_id": LICKING.source_id,
        "representation_source_id": LICKING_DETAIL_SOURCE_ID,
        "record_identity_source_id": LICKING.source_id,
        "source_url": source_url,
        "portal_url": LICKING.pax_root,
        "record_kind": "recorded_instrument_detail",
        "representation_kind": "county_exact_instrument_html",
        "source_record_id": instrument,
        "instrument_reference_id": None,
        "instrument_number": instrument,
        "recorded_at_source": _clean(fields.get("Recorded Date")),
        "recorded_date_iso": recorded_date,
        "recorded_at_iso": recorded_at,
        "document_type": _clean(fields.get("Document Type")),
        "grantors": grantors,
        "grantees": grantees,
        "party_occurrences": [
            *[
                {"role": "grantor", "display_name": value}
                for value in grantors
            ],
            *[
                {"role": "grantee", "display_name": value}
                for value in grantees
            ],
        ],
        "legal_description": _clean(fields.get("Legal Description")),
        "page_count": page_count,
        "document": {
            "available": document_url is not None,
            "media_type": "application/pdf" if document_url else None,
            "source_url": document_url,
        },
        "native_detail_fields": fields,
        "stable_identity": {
            "primary": "instrument_number",
            "instrument_number": instrument,
        },
        "source_response_schema_fingerprint": sha256_fingerprint(
            {"detail_labels": sorted(fields)}
        ),
    }


def _source_date(value: str | None) -> str:
    text = _clean(value)
    if text is None:
        return ""
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            parsed = datetime.strptime(text, pattern).date()
        except ValueError:
            continue
        return f"{parsed.month}/{parsed.day}/{parsed.year}"
    raise PAXSelectionError(
        "invalid_date",
        f"date is not YYYY-MM-DD or M/D/YYYY: {text}",
    )


def normalize_selectors(
    values: Mapping[str, Any],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    selectors = {
        "name": _clean(values.get("name")),
        "first_name": _clean(values.get("first_name")),
        "party": _clean(values.get("party")) or "any",
        "last_name_comparison": (
            _clean(values.get("last_name_comparison")) or "LIKE"
        ).upper(),
        "first_name_comparison": (
            _clean(values.get("first_name_comparison")) or "LIKE"
        ).upper(),
        "recorded_from": _source_date(values.get("recorded_from")),
        "recorded_to": _source_date(values.get("recorded_to")),
        "instrument": _clean(values.get("instrument")),
        "book_type": _clean(values.get("book_type")),
        "book": _clean(values.get("book")),
        "page": _clean(values.get("page")),
        "document_id": _clean(values.get("document_id")),
        "include_cross_references": bool(
            values.get("include_cross_references")
        ),
    }
    if selectors["recorded_from"] and not selectors["recorded_to"]:
        current = today or date.today()
        selectors["recorded_to"] = (
            f"{current.month}/{current.day}/{current.year}"
        )
    if selectors["party"] not in {"any", "first", "second"}:
        raise PAXSelectionError(
            "invalid_party_role",
            "party must be any, first, or second",
        )
    comparisons = {"LIKE", "CONTAINS", "IS"}
    if selectors["last_name_comparison"] not in comparisons:
        raise PAXSelectionError(
            "invalid_name_comparison",
            "last-name comparison must be LIKE, CONTAINS, or IS",
        )
    if selectors["first_name_comparison"] not in comparisons:
        raise PAXSelectionError(
            "invalid_first_name_comparison",
            "first-name comparison must be LIKE, CONTAINS, or IS",
        )
    instrument_fields = any(
        selectors[key]
        for key in ("instrument", "book_type", "book", "page", "document_id")
    )
    name_fields = any(
        selectors[key]
        for key in ("name", "first_name", "recorded_from", "recorded_to")
    )
    if instrument_fields and name_fields:
        raise PAXSelectionError(
            "mixed_native_search_tabs",
            "PAX instrument and name/date selectors belong to separate native searches",
        )
    if not instrument_fields and not name_fields:
        raise PAXSelectionError(
            "empty_query",
            "select a name, date, instrument, book/page, or document ID",
        )
    selectors["search_type"] = "Instrument" if instrument_fields else "Name"
    return selectors


def build_search_criteria(
    selectors: Mapping[str, Any],
    config: PAXSessionConfig,
    *,
    first_record: int,
    last_record: int,
    draw: int = 1,
) -> dict[str, Any]:
    """Build the observed PAX ``SearchDetail`` form model."""

    if first_record <= 0 or last_record < first_record:
        raise ValueError("invalid PAX detail page boundary")
    return {
        "NameOrganization": (
            quote(str(selectors.get("name") or "").upper(), safe="")
        ),
        "LastNameComparison": selectors.get("last_name_comparison") or "LIKE",
        "FirstNameComparison": (
            selectors.get("first_name_comparison") or "LIKE"
        ),
        "FirstName1": (
            quote(str(selectors.get("first_name") or "").upper(), safe="")
        ),
        "FirstNameAndOr": "Or",
        "FirstName2": "",
        "Party": selectors.get("party") or "any",
        "RecordedDate1": selectors.get("recorded_from") or "",
        "RecordedDate2": selectors.get("recorded_to") or "",
        "Consideration1": "",
        "Consideration2": "",
        "Remarks": "",
        "FileNumber": "",
        "CategoryDocumentTypes": "",
        "CategoryTypes": "",
        "LegalParameters": "",
        "IncludeCrossReferences": (
            "true" if selectors.get("include_cross_references") else "false"
        ),
        "InstrumentId": selectors.get("instrument") or "",
        "BookType": selectors.get("book_type") or "",
        "Book": selectors.get("book") or "",
        "Bookpage": selectors.get("page") or "",
        "DocumentId": selectors.get("document_id") or "",
        "SearchType": selectors["search_type"],
        "SearchTypeResults": "Detail",
        "SessionId": config.session_id,
        "InstrumentReferenceIds": "",
        "Message": "",
        "ParentId": "",
        "SavedSearchId": "",
        "SearchHistoryId": "",
        "LastRecordNum": last_record,
        "FirstRecordNum": first_record,
        "Draw": draw,
        "Columns": " HTMLBlob ",
        "FilterWhere": "",
        "TotalRecords": 0,
        "IsCountLookupEnabled": "true",
        "OrderBy": " recordeddate desc, instrumentnumber desc ",
        "SearchTypeClient": "",
        "GridData": "",
        "isDetailPrint": "false",
        "SessionGuid": config.session_id,
        "SessionTicket": config.session_ticket,
    }


class OhioPAXClient:
    """Retrying client retaining each operation's anonymous cookie session."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: MinimumIntervalRateLimiter | Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = rate_limiter or MinimumIntervalRateLimiter(
            DEFAULT_MINIMUM_INTERVAL
        )
        self.sleeper = sleeper
        self._owns_session = session is None
        self.request_count = 0
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.8",
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        tenant: PAXTenant,
        method: str,
        url: str,
        *,
        data: Mapping[str, Any] | None = None,
        accept: str,
        referer: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        official_url = _tenant_url(tenant, url)
        request_headers = {**self.headers, "Accept": accept}
        if extra_headers:
            request_headers.update(
                {str(key): str(value) for key, value in extra_headers.items()}
            )
        if referer:
            request_headers["Referer"] = _tenant_url(tenant, referer)
        if "json" in accept:
            request_headers["X-Requested-With"] = "XMLHttpRequest"
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                self.request_count += 1
                response = self.session.request(
                    method,
                    official_url,
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                break
            for redirect in [*getattr(response, "history", ()), response]:
                _tenant_url(
                    tenant,
                    str(getattr(redirect, "url", official_url)),
                )
            status = int(getattr(response, "status_code", 0))
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                retry_after = _retry_after(response)
                response.close()
                self.sleeper(
                    self.retry_policy.delay(attempt, retry_after)
                )
                continue
            if status == 429:
                response.close()
                raise RateLimitedHTTPError(status, url=official_url)
            if status in {401, 403}:
                response.close()
                raise RestrictedHTTPError(status, url=official_url)
            if status in {404, 410}:
                response.close()
                raise SourceChangedHTTPError(status, url=official_url)
            if status < 200 or status >= 300:
                response.close()
                raise HTTPStatusError(status, url=official_url)
            return response
        raise TransportError(
            "Ohio PAX recorder request failed",
            url=official_url,
            details={"error": str(last_error or "retry exhausted")},
        )

    def _text(
        self,
        tenant: PAXTenant,
        method: str,
        url: str,
        *,
        data: Mapping[str, Any] | None = None,
        accept: str = "text/html,application/xhtml+xml",
        referer: str | None = None,
    ) -> TextPage:
        response = self._request(
            tenant,
            method,
            url,
            data=data,
            accept=accept,
            referer=referer,
        )
        try:
            response_headers = _headers(response)
            content_type = response_headers.get("content-type", "").casefold()
            if "html" not in content_type and "json" not in content_type:
                raise SourceSchemaError(
                    "Ohio recorder route returned unexpected content",
                    url=str(getattr(response, "url", url)),
                    details={"content_type": content_type},
                )
            return TextPage(
                text=str(response.text),
                source_url=str(getattr(response, "url", url)),
                headers=response_headers,
            )
        finally:
            response.close()

    def entry_access(self, tenant: PAXTenant) -> dict[str, Any]:
        page = self._text(tenant, "GET", tenant.pax_root)
        return parse_entry_access(page.text, page.source_url)

    def bootstrap(self, tenant: PAXTenant) -> PAXSessionConfig:
        entry = self._text(tenant, "GET", tenant.pax_root)
        access = parse_entry_access(entry.text, entry.source_url)
        if access["login_required"]:
            raise PAXSelectionError(
                "account_required_for_discovery",
                f"{tenant.county_name} PAX discovery requires an account",
                status=ResultStatus.RESTRICTED,
                category="source_access",
                details={
                    "pax_root": tenant.pax_root,
                    "official_alternatives": [
                        dict(value) for value in tenant.complements
                    ],
                },
            )
        search_page = self._text(
            tenant,
            "POST",
            str(access["form_action"]),
            data=access["hidden_fields"],
            referer=entry.source_url,
        )
        return parse_search_config(
            search_page.text,
            search_page.source_url,
        )

    def search_detail(
        self,
        tenant: PAXTenant,
        selectors: Mapping[str, Any],
        config: PAXSessionConfig,
        *,
        first_record: int,
        last_record: int,
    ) -> DetailBatch:
        criteria = build_search_criteria(
            selectors,
            config,
            first_record=first_record,
            last_record=last_record,
        )
        url = urljoin(tenant.pax_root, "api/SearchDetail")
        page = self._text(
            tenant,
            "POST",
            url,
            data=criteria,
            accept="application/json,text/javascript,*/*",
            referer=config.search_url,
        )
        return parse_detail_response(page.text, tenant, page.source_url)

    def licking_exact(
        self,
        tenant: PAXTenant,
        instrument: str,
    ) -> dict[str, Any] | None:
        if tenant.exact_detail_url_template is None:
            raise ValueError("tenant has no exact-instrument sidecar")
        url = tenant.exact_detail_url_template.format(
            instrument=quote(instrument, safe="")
        )
        page = self._text(tenant, "GET", url)
        return parse_licking_exact(
            page.text,
            page.source_url,
            expected_instrument=instrument,
        )

    def image_detail(
        self,
        tenant: PAXTenant,
        config: PAXSessionConfig,
        *,
        reference_id: str,
        instrument: str,
    ) -> dict[str, Any]:
        locator = (
            f"{config.session_ticket},{reference_id},{config.session_id}"
        )
        url = urljoin(
            tenant.pax_root,
            f"api/ImageDetail/{quote(locator, safe=',-')}",
        )
        page = self._text(
            tenant,
            "GET",
            url,
            accept="application/json,text/javascript,*/*",
            referer=config.search_url,
        )
        return parse_image_detail(
            page.text,
            page.source_url,
            expected_instrument=instrument,
            reference_id=reference_id,
        )

    def document(
        self,
        tenant: PAXTenant,
        instrument: str,
        *,
        config: PAXSessionConfig | None = None,
        reference_id: str | None = None,
    ) -> BinaryDocument:
        if tenant is LICKING:
            if tenant.exact_document_url_template is None:
                raise ValueError("Licking document route is missing")
            url = tenant.exact_document_url_template.format(
                instrument=quote(instrument, safe="")
            )
            referer = tenant.exact_detail_url_template.format(
                instrument=quote(instrument, safe="")
            )
        else:
            if config is None or reference_id is None:
                raise ValueError("Delaware document retrieval needs PAX identity")
            locator = (
                f"{config.session_ticket},{reference_id},,false,false,,"
                f"{config.user_id}"
            )
            url = urljoin(
                tenant.pax_root,
                f"api/Image/{quote(locator, safe=',-')}",
            )
            referer = config.search_url
        response = self._request(
            tenant,
            "GET",
            url,
            accept="application/pdf,application/octet-stream",
            referer=referer,
        )
        try:
            content = bytes(response.content)
            response_headers = _headers(response)
            media_type = (
                response_headers.get("content-type", "")
                .split(";", 1)[0]
                .strip()
                .casefold()
            )
            if media_type not in {
                "application/pdf",
                "application/octet-stream",
            }:
                raise SourceSchemaError(
                    "Ohio recorder document route returned an unexpected media type",
                    url=str(getattr(response, "url", url)),
                    details={"content_type": media_type},
                )
            if not content.startswith(b"%PDF-"):
                raise SourceSchemaError(
                    "Ohio recorder document route did not return a PDF",
                    url=str(getattr(response, "url", url)),
                    details={
                        "content_type": response_headers.get("content-type"),
                    },
                )
            content_length = response_headers.get("content-length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as error:
                    raise SourceSchemaError(
                        "Ohio recorder document length header is invalid",
                        url=str(getattr(response, "url", url)),
                        details={"content_length": content_length},
                    ) from error
                if declared_length != len(content):
                    raise SourceSchemaError(
                        "Ohio recorder document length does not match its header",
                        url=str(getattr(response, "url", url)),
                        details={
                            "declared_length": declared_length,
                            "observed_length": len(content),
                        },
                    )
            return BinaryDocument(
                content=content,
                source_url=str(getattr(response, "url", url)),
                headers=response_headers,
            )
        finally:
            response.close()

    def document_sample(
        self,
        tenant: PAXTenant,
        instrument: str,
        *,
        sample_bytes: int,
        config: PAXSessionConfig | None = None,
        reference_id: str | None = None,
    ) -> BinaryDocument:
        """Fetch a leading PDF byte range for a low-cost source probe."""

        if sample_bytes <= 0:
            raise ValueError("document sample size must be positive")
        if tenant is LICKING:
            if tenant.exact_document_url_template is None:
                raise ValueError("Licking document route is missing")
            url = tenant.exact_document_url_template.format(
                instrument=quote(instrument, safe="")
            )
            referer = tenant.exact_detail_url_template.format(
                instrument=quote(instrument, safe="")
            )
        else:
            if config is None or reference_id is None:
                raise ValueError("Delaware document retrieval needs PAX identity")
            locator = (
                f"{config.session_ticket},{reference_id},,false,false,,"
                f"{config.user_id}"
            )
            url = urljoin(
                tenant.pax_root,
                f"api/Image/{quote(locator, safe=',-')}",
            )
            referer = config.search_url
        response = self._request(
            tenant,
            "GET",
            url,
            accept="application/pdf,application/octet-stream",
            referer=referer,
            extra_headers={"Range": f"bytes=0-{sample_bytes - 1}"},
        )
        try:
            content = bytes(response.content)
            response_headers = _headers(response)
            media_type = (
                response_headers.get("content-type", "")
                .split(";", 1)[0]
                .strip()
                .casefold()
            )
            if media_type not in {
                "application/pdf",
                "application/octet-stream",
            }:
                raise SourceSchemaError(
                    "Ohio recorder PDF sample returned an unexpected media type",
                    url=str(getattr(response, "url", url)),
                    details={"content_type": media_type},
                )
            if not content.startswith(b"%PDF-"):
                raise SourceSchemaError(
                    "Ohio recorder PDF sample has no PDF signature",
                    url=str(getattr(response, "url", url)),
                )
            content_length = response_headers.get("content-length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as error:
                    raise SourceSchemaError(
                        "Ohio recorder PDF sample length header is invalid",
                        url=str(getattr(response, "url", url)),
                        details={"content_length": content_length},
                    ) from error
                if declared_length != len(content):
                    raise SourceSchemaError(
                        "Ohio recorder PDF sample length does not match its header",
                        url=str(getattr(response, "url", url)),
                        details={
                            "declared_length": declared_length,
                            "observed_length": len(content),
                        },
                    )
            return BinaryDocument(
                content=content,
                source_url=str(getattr(response, "url", url)),
                headers=response_headers,
            )
        finally:
            response.close()


def _tenant(args: argparse.Namespace) -> PAXTenant:
    source_id = getattr(args, "source", None)
    if source_id not in TENANTS_BY_QUERY_SOURCE:
        raise PAXSelectionError(
            "source_not_selected",
            "select a supported Ohio recorder source component",
        )
    return TENANTS_BY_QUERY_SOURCE[str(source_id)]


def sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "platform_family": PLATFORM_FAMILY,
        "observed_at": "2026-07-30",
        "family_boundary": {
            "shared": [
                "ASP.NET disclaimer/login entry",
                "PAX Search_2.js model",
                "SearchDetail response shape",
                "InstrumentReferenceId semantics",
                "image metadata and image routes",
            ],
            "tenant_specific": [
                "login requirement",
                "anonymous search availability",
                "image entitlement and copy settings",
                "exact-detail sidecars",
                "archive and request complements",
            ],
        },
        "sources": [
            {
                **tenant.source_metadata.to_dict(),
                "jurisdiction": tenant.jurisdiction.to_dict(),
                "sentinel_instrument": tenant.sentinel_instrument,
                "exact_detail_url_template": tenant.exact_detail_url_template,
                "exact_document_url_template": tenant.exact_document_url_template,
            }
            for tenant in TENANTS
        ],
        "alternate_representations": [
            {
                "source_id": LICKING_DETAIL_SOURCE_ID,
                "record_identity_source_id": LICKING_SOURCE_ID,
                "name": "Licking County Recorder Exact-Instrument Detail",
                "representation_kind": "county_exact_instrument_html_and_pdf",
                "independent_corroboration": False,
                "stable_key": "instrument_number",
                "url_template": LICKING.exact_detail_url_template,
            }
        ],
        "source_relationships": [
            {
                "left": LICKING_DETAIL_SOURCE_ID,
                "right": LICKING_SOURCE_ID,
                "relationship": "alternate_representation_same_instrument_identity",
                "record_identity_source_id": LICKING_SOURCE_ID,
                "independent_corroboration": False,
            },
            {
                "left": DELAWARE_SOURCE_ID,
                "right": LICKING_SOURCE_ID,
                "relationship": "shared_transport_family_not_same_source",
                "independent_corroboration": False,
            },
            {
                "left": DELAWARE_SOURCE_ID,
                "right": OGRIP_SOURCE_ID,
                "relationship": "instrument_to_parcel_context",
                "join_keys": [
                    "parcel_identifier",
                    "legal_description",
                    "situs_address",
                ],
            },
            {
                "left": LICKING_SOURCE_ID,
                "right": OGRIP_SOURCE_ID,
                "relationship": "instrument_to_parcel_context",
                "join_keys": [
                    "parcel_identifier",
                    "legal_description",
                    "situs_address",
                ],
            },
        ],
        "process_learnings": [
            {
                "learning": "separate_family_shape_from_tenant_capability",
                "evidence": (
                    "The same PAX family exposed anonymous discovery in "
                    "Delaware and account-gated discovery in Licking."
                ),
            },
            {
                "learning": "probe_exact_sidecars_when_discovery_is_gated",
                "evidence": (
                    "Licking's county-owned exact detail and PDF routes remained "
                    "anonymous when an instrument number was known."
                ),
            },
            {
                "learning": "use_detail_pagination_for_instrument_identity",
                "evidence": (
                    "PAX summary search repeats instruments for party rows; "
                    "SearchDetail returns one row per InstrumentReferenceId."
                ),
            },
            {
                "learning": "verify_indexed_routes_live",
                "evidence": (
                    "An indexed recorder-doc.aspx representation returned 404 "
                    "and is not part of the implemented contract."
                ),
            },
            {
                "learning": "resolve_tenant_identity_from_authoritative_context",
                "evidence": (
                    "The Delaware search page retained stale cross-tenant "
                    "configuration strings, so county authority is anchored to "
                    "the official host, FIPS-specific page, and county link."
                ),
            },
        ],
    }


def _query(
    tenant: PAXTenant,
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
    query_source_id: str | None = None,
) -> PublicRecordsQuery:
    selected_source_id = query_source_id or tenant.source_id
    return PublicRecordsQuery(
        source=source_metadata(selected_source_id),
        jurisdiction=tenant.jurisdiction,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _record_anchor(record: Mapping[str, Any]) -> str:
    return sha256_fingerprint(
        {
            "instrument_reference_id": record.get("instrument_reference_id"),
            "instrument_number": record.get("instrument_number"),
        }
    )


def _validate_batch_boundary(
    batch: DetailBatch,
    *,
    expected_first: int,
) -> None:
    if batch.records:
        if batch.first_position != expected_first:
            raise SourceSchemaError(
                "Ohio PAX detail page started at an unexpected position",
                url=batch.source_url,
                details={
                    "expected_first": expected_first,
                    "observed_first": batch.first_position,
                },
            )
        if (
            batch.last_position is None
            or batch.last_position > batch.total_results
        ):
            raise SourceSchemaError(
                "Ohio PAX detail page exceeded its reported total",
                url=batch.source_url,
                details={
                    "last_position": batch.last_position,
                    "reported_total": batch.total_results,
                },
            )
    elif expected_first <= batch.total_results:
        raise SourceSchemaError(
            "Ohio PAX detail page was empty before its reported total",
            url=batch.source_url,
            details={
                "expected_first": expected_first,
                "reported_total": batch.total_results,
            },
        )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source_id": state.source_id,
        "query_fingerprint": state.query_fingerprint,
        "offset": state.offset,
        "anchor": state.anchor,
        "total_results": state.total_results,
    }
    token = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(
    value: str,
    *,
    tenant: PAXTenant,
    query_fingerprint: str,
) -> CursorState:
    if not value.startswith(CURSOR_PREFIX):
        raise PAXSelectionError(
            "cursor_source_mismatch",
            "continuation is not an Ohio PAX recorder cursor",
        )
    token = value[len(CURSOR_PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as error:
        raise PAXSelectionError(
            "cursor_invalid",
            "Ohio PAX continuation is malformed",
        ) from error
    required = {
        "v",
        "source_id",
        "query_fingerprint",
        "offset",
        "anchor",
        "total_results",
    }
    if not isinstance(payload, Mapping) or not required.issubset(payload):
        raise PAXSelectionError(
            "cursor_invalid",
            "Ohio PAX continuation is incomplete",
        )
    if payload["v"] != CURSOR_VERSION:
        raise PAXSelectionError(
            "cursor_version_changed",
            "Ohio PAX continuation version is unsupported",
        )
    if payload["source_id"] != tenant.source_id:
        raise PAXSelectionError(
            "cursor_source_mismatch",
            "continuation belongs to another county source",
        )
    if payload["query_fingerprint"] != query_fingerprint:
        raise PAXSelectionError(
            "cursor_query_mismatch",
            "continuation belongs to different search selectors",
        )
    try:
        offset = int(payload["offset"])
        total = int(payload["total_results"])
        anchor = str(payload["anchor"])
    except (TypeError, ValueError) as error:
        raise PAXSelectionError(
            "cursor_invalid",
            "Ohio PAX continuation boundary is invalid",
        ) from error
    if offset <= 0 or total < offset or not anchor:
        raise PAXSelectionError(
            "cursor_invalid",
            "Ohio PAX continuation boundary is inconsistent",
        )
    return CursorState(
        source_id=tenant.source_id,
        query_fingerprint=query_fingerprint,
        offset=offset,
        anchor=anchor,
        total_results=total,
    )


def _selector_input_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "name": getattr(args, "name", None),
        "first_name": getattr(args, "first_name", None),
        "party": getattr(args, "party", "any"),
        "last_name_comparison": getattr(
            args,
            "last_name_comparison",
            "LIKE",
        ),
        "first_name_comparison": getattr(
            args,
            "first_name_comparison",
            "LIKE",
        ),
        "recorded_from": getattr(args, "recorded_from", None),
        "recorded_to": getattr(args, "recorded_to", None),
        "instrument": getattr(args, "instrument_selector", None),
        "book_type": getattr(args, "book_type", None),
        "book": getattr(args, "book", None),
        "page": getattr(args, "page", None),
        "document_id": getattr(args, "document_id", None),
        "include_cross_references": getattr(
            args,
            "include_cross_references",
            False,
        ),
    }


def _selectors_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return normalize_selectors(_selector_input_from_args(args))


def _query_fingerprint(
    tenant: PAXTenant,
    selectors: Mapping[str, Any],
) -> str:
    return sha256_fingerprint(
        {
            "source_id": tenant.source_id,
            "operation": "SearchDetail",
            "selectors": dict(selectors),
            "order_by": "recordeddate desc, instrumentnumber desc",
        }
    )


def _restricted_discovery_result(
    query: PublicRecordsQuery,
    tenant: PAXTenant,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.RESTRICTED,
        [
            PublicRecordsError(
                code="account_required_for_discovery",
                message=(
                    f"{tenant.county_name} PAX name, date, and book/page "
                    "discovery requires an account; the exact-instrument route "
                    "remains available when an instrument number is known."
                ),
                category="source_access",
                retryable=False,
                details={
                    "pax_root": tenant.pax_root,
                    "exact_detail_url_template": tenant.exact_detail_url_template,
                    "official_alternatives": [
                        dict(value) for value in tenant.complements
                    ],
                },
            )
        ],
        warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
    )


def _search_delaware(
    query: PublicRecordsQuery,
    tenant: PAXTenant,
    selectors: Mapping[str, Any],
    client: Any,
    *,
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsResult:
    if limit is not None and limit <= 0:
        raise PAXSelectionError(
            "invalid_limit",
            "--limit must be a positive integer when supplied",
        )
    fingerprint = _query_fingerprint(tenant, selectors)
    state = (
        _decode_cursor(
            cursor,
            tenant=tenant,
            query_fingerprint=fingerprint,
        )
        if cursor
        else None
    )
    config = client.bootstrap(tenant)
    if not config.is_guest:
        raise SourceSchemaError(
            "Delaware anonymous bootstrap did not create a guest session",
            url=config.search_url,
        )
    page_size = config.rows_per_page
    first = state.offset if state else 1
    batch = client.search_detail(
        tenant,
        selectors,
        config,
        first_record=first,
        last_record=first + page_size - 1,
    )
    _validate_batch_boundary(batch, expected_first=first)
    if batch.total_results == 0:
        if state:
            raise PAXSelectionError(
                "cursor_result_set_changed",
                "resumed Ohio PAX query is now empty",
            )
        return PublicRecordsResult.success(
            query,
            [],
            warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
        )
    if state and batch.total_results != state.total_results:
        raise PAXSelectionError(
            "cursor_result_set_changed",
            "Ohio PAX result count changed before continuation",
            details={
                "prior_total": state.total_results,
                "current_total": batch.total_results,
            },
        )
    records = [dict(record) for record in batch.records]
    consumed_before = state.offset if state else 0
    anchor_verified = state is None
    if state:
        if (
            not records
            or int(records[0]["source_position"]) != state.offset
            or _record_anchor(records[0]) != state.anchor
        ):
            raise PAXSelectionError(
                "cursor_anchor_changed",
                "Ohio PAX continuation boundary record changed",
            )
        anchor_verified = True
        records = records[1:]
    target = (
        limit
        if limit is not None
        else max(batch.total_results - consumed_before, 0)
    )
    collected = records[:target]
    while (
        len(collected) < target
        and consumed_before + len(collected) < batch.total_results
    ):
        next_position = consumed_before + len(collected) + 1
        next_batch = client.search_detail(
            tenant,
            selectors,
            config,
            first_record=next_position,
            last_record=next_position + page_size - 1,
        )
        _validate_batch_boundary(
            next_batch,
            expected_first=next_position,
        )
        if next_batch.total_results != batch.total_results:
            raise PAXSelectionError(
                "result_count_changed_during_search",
                "Ohio PAX result count changed while paging",
            )
        if not next_batch.records:
            raise SourceSchemaError(
                "Ohio PAX pagination ended before its reported total",
                url=next_batch.source_url,
                details={
                    "next_position": next_position,
                    "reported_total": batch.total_results,
                },
            )
        needed = target - len(collected)
        collected.extend(
            dict(record) for record in next_batch.records[:needed]
        )
    new_offset = consumed_before + len(collected)
    next_cursor = None
    if collected and new_offset < batch.total_results:
        next_cursor = _encode_cursor(
            CursorState(
                source_id=tenant.source_id,
                query_fingerprint=fingerprint,
                offset=new_offset,
                anchor=_record_anchor(collected[-1]),
                total_results=batch.total_results,
            )
        )
    coverage = {
        "source_reported_total_instruments": batch.total_results,
        "returned_start_position": (
            consumed_before + 1 if collected else None
        ),
        "returned_end_position": new_offset if collected else None,
        "records_returned": len(collected),
        "native_page_size": page_size,
        "caller_limit": limit,
        "completion_mode": (
            "caller_selected_limit"
            if limit is not None
            else "source_reported_total"
        ),
        "cursor_anchor_verified": anchor_verified,
        "complete_for_selected_query": (
            new_offset >= batch.total_results
        ),
        "data_current_through": config.data_current_through,
        "pax_version": config.version,
    }
    normalized = []
    for record in collected:
        item = dict(record)
        item["retrieval_coverage"] = coverage
        item["query_fingerprint"] = fingerprint
        normalized.append(item)
    return PublicRecordsResult.success(
        query,
        normalized,
        next_cursor=next_cursor,
        warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
    )


def _search_licking_exact(
    query: PublicRecordsQuery,
    tenant: PAXTenant,
    selectors: Mapping[str, Any],
    client: Any,
    *,
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsResult:
    if limit is not None and limit <= 0:
        raise PAXSelectionError(
            "invalid_limit",
            "--limit must be a positive integer when supplied",
        )
    instrument = _clean(selectors.get("instrument"))
    other = any(
        selectors.get(key)
        for key in (
            "name",
            "first_name",
            "recorded_from",
            "recorded_to",
            "book_type",
            "book",
            "page",
            "document_id",
        )
    )
    if instrument is None or other:
        return _restricted_discovery_result(query, tenant)
    if cursor:
        raise PAXSelectionError(
            "cursor_not_applicable",
            "Licking exact-instrument lookup returns a single native record",
        )
    record = client.licking_exact(tenant, instrument)
    return PublicRecordsResult.success(
        query,
        [record] if record else [],
        warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
    )


def _exact_records(
    tenant: PAXTenant,
    instrument: str,
    client: Any,
) -> tuple[list[dict[str, Any]], PAXSessionConfig | None]:
    if tenant is LICKING:
        record = client.licking_exact(tenant, instrument)
        return ([record] if record else []), None
    selectors = normalize_selectors({"instrument": instrument})
    config = client.bootstrap(tenant)
    batch = client.search_detail(
        tenant,
        selectors,
        config,
        first_record=1,
        last_record=config.rows_per_page,
    )
    _validate_batch_boundary(batch, expected_first=1)
    matches: list[dict[str, Any]] = []
    for record in batch.records:
        if record.get("instrument_number") != instrument:
            raise SourceSchemaError(
                "PAX exact-instrument query returned another instrument",
                url=batch.source_url,
                details={
                    "requested_instrument": instrument,
                    "observed_instrument": record.get("instrument_number"),
                },
            )
        matches.append(dict(record))
    while len(batch.records) and (
        batch.last_position is not None
        and batch.last_position < batch.total_results
    ):
        start = batch.last_position + 1
        batch = client.search_detail(
            tenant,
            selectors,
            config,
            first_record=start,
            last_record=start + config.rows_per_page - 1,
        )
        _validate_batch_boundary(batch, expected_first=start)
        for record in batch.records:
            if record.get("instrument_number") != instrument:
                raise SourceSchemaError(
                    "PAX exact-instrument continuation returned another instrument",
                    url=batch.source_url,
                    details={
                        "requested_instrument": instrument,
                        "observed_instrument": record.get("instrument_number"),
                    },
                )
            matches.append(dict(record))
    return matches, config


def _select_reference(
    records: Sequence[Mapping[str, Any]],
    *,
    reference_id: str | None,
    instrument: str,
) -> Mapping[str, Any]:
    if reference_id:
        matches = [
            record
            for record in records
            if str(record.get("instrument_reference_id")) == reference_id
        ]
        if not matches:
            raise PAXSelectionError(
                "reference_not_found",
                "the selected InstrumentReferenceId was not returned",
                details={
                    "instrument": instrument,
                    "reference_id": reference_id,
                },
            )
        return matches[0]
    if len(records) != 1:
        raise PAXSelectionError(
            "ambiguous_instrument_reference",
            "select --reference-id when an instrument resolves to multiple native references",
            details={
                "instrument": instrument,
                "reference_ids": [
                    record.get("instrument_reference_id")
                    for record in records
                ],
            },
        )
    return records[0]


def _execute_instrument(
    query: PublicRecordsQuery,
    tenant: PAXTenant,
    instrument: str,
    client: Any,
) -> PublicRecordsResult:
    records, _ = _exact_records(tenant, instrument, client)
    return PublicRecordsResult.success(
        query,
        records,
        warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
    )


def _execute_document_info(
    query: PublicRecordsQuery,
    tenant: PAXTenant,
    instrument: str,
    reference_id: str | None,
    client: Any,
) -> PublicRecordsResult:
    records, config = _exact_records(tenant, instrument, client)
    if not records:
        return PublicRecordsResult.success(
            query,
            [],
            warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
        )
    if tenant is LICKING:
        if reference_id:
            raise PAXSelectionError(
                "reference_not_applicable",
                "Licking's exact-detail sidecar is keyed by instrument number",
            )
        record = dict(records[0])
        record["document_access"] = {
            "anonymous_exact_detail": True,
            "anonymous_pdf": bool(record.get("document", {}).get("available")),
            "media_type": "application/pdf",
            "range_requests_observed": True,
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
        )
    selected = _select_reference(
        records,
        reference_id=reference_id,
        instrument=instrument,
    )
    assert config is not None
    image = client.image_detail(
        tenant,
        config,
        reference_id=str(selected["instrument_reference_id"]),
        instrument=instrument,
    )
    record = dict(selected)
    record["document_access"] = image
    return PublicRecordsResult.success(
        query,
        [record],
        warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
    )


def _write_document(
    document: BinaryDocument,
    destination: Path,
    *,
    overwrite: bool,
) -> tuple[Path, str]:
    destination = destination.expanduser()
    if destination.exists() and not overwrite:
        raise PAXSelectionError(
            "destination_exists",
            "destination exists; pass --overwrite to replace it",
            details={"destination": str(destination)},
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(document.content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return destination, hashlib.sha256(document.content).hexdigest()


def _execute_download(
    query: PublicRecordsQuery,
    tenant: PAXTenant,
    instrument: str,
    reference_id: str | None,
    destination: Path,
    overwrite: bool,
    client: Any,
) -> PublicRecordsResult:
    if tenant is LICKING and reference_id:
        raise PAXSelectionError(
            "reference_not_applicable",
            "Licking's exact-document sidecar is keyed by instrument number",
        )
    records, config = _exact_records(tenant, instrument, client)
    if not records:
        return PublicRecordsResult.success(
            query,
            [],
            warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
        )
    selected = _select_reference(
        records,
        reference_id=reference_id,
        instrument=instrument,
    )
    selected_reference = _clean(selected.get("instrument_reference_id"))
    document = client.document(
        tenant,
        instrument,
        config=config,
        reference_id=selected_reference,
    )
    local_path, digest = _write_document(
        document,
        destination,
        overwrite=overwrite,
    )
    record = {
        "canonical_ref": (
            f"OHREC_DOCUMENT:{tenant.county_fips}:{instrument}:"
            f"{selected_reference or 'instrument'}"
        ),
        "evidence_ref": (
            f"PAXDOC:{tenant.county_fips}:{instrument}:"
            f"{selected_reference or 'instrument'}"
        ),
        "source_id": tenant.source_id,
        "record_identity_source_id": tenant.source_id,
        "representation_source_id": (
            LICKING_DETAIL_SOURCE_ID
            if tenant is LICKING
            else tenant.source_id
        ),
        "source_url": document.source_url,
        "record_kind": "recorded_instrument_document",
        "representation_kind": "official_public_pdf",
        "instrument_number": instrument,
        "instrument_reference_id": selected_reference,
        "media_type": (
            document.headers.get("content-type", "").split(";", 1)[0]
        ),
        "size_bytes": len(document.content),
        "sha256": digest,
        "local_path": str(local_path),
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[str(local_path)],
        warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
    )


def _execute_probe(
    query: PublicRecordsQuery,
    tenant: PAXTenant,
    client: Any,
    *,
    query_source_id: str,
) -> PublicRecordsResult:
    if query_source_id == LICKING_DETAIL_SOURCE_ID:
        record = client.licking_exact(tenant, tenant.sentinel_instrument)
        if record is None:
            raise SourceSchemaError(
                "Licking exact-instrument sentinel was not returned",
                url=str(tenant.exact_detail_url_template),
            )
        probe = {
            "canonical_ref": (
                f"OHREC_PROBE:{tenant.county_fips}:exact:"
                f"{tenant.sentinel_instrument}"
            ),
            "record_kind": "source_probe",
            "source_id": LICKING_DETAIL_SOURCE_ID,
            "record_identity_source_id": LICKING_SOURCE_ID,
            "representation_source_id": LICKING_DETAIL_SOURCE_ID,
            "independent_corroboration": False,
            "anonymous_exact_detail_verified": True,
            "anonymous_pdf_locator_verified": bool(
                record.get("document", {}).get("available")
            ),
            "sentinel_instrument": tenant.sentinel_instrument,
            "document_page_count": record.get("page_count"),
        }
        return PublicRecordsResult.success(
            query,
            [probe],
            warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
        )

    access = client.entry_access(tenant)
    if tenant is LICKING:
        probe = {
            "canonical_ref": (
                f"OHREC_PROBE:{tenant.county_fips}:pax-access"
            ),
            "record_kind": "source_probe",
            "source_id": tenant.source_id,
            "pax_login_required": access["login_required"],
            "anonymous_entry_verified": True,
            "discovery_access": "account_required",
            "exact_representation_source_id": LICKING_DETAIL_SOURCE_ID,
            "pax_version": access.get("version"),
        }
    else:
        records, config = _exact_records(
            tenant,
            tenant.sentinel_instrument,
            client,
        )
        assert config is not None
        if not records:
            raise SourceSchemaError(
                "Delaware PAX sentinel was not returned",
                url=config.search_url,
            )
        selected = records[0]
        image = client.image_detail(
            tenant,
            config,
            reference_id=str(selected["instrument_reference_id"]),
            instrument=tenant.sentinel_instrument,
        )
        probe = {
            "canonical_ref": (
                f"OHREC_PROBE:{tenant.county_fips}:"
                f"{tenant.sentinel_instrument}"
            ),
            "record_kind": "source_probe",
            "source_id": tenant.source_id,
            "pax_login_required": access["login_required"],
            "anonymous_guest_session_verified": config.is_guest,
            "anonymous_detail_search_verified": True,
            "anonymous_image_metadata_verified": True,
            "sentinel_instrument": tenant.sentinel_instrument,
            "sentinel_reference_id": selected["instrument_reference_id"],
            "has_image": image["has_image"],
            "document_page_count": image["page_count"],
            "data_current_through": config.data_current_through,
            "pax_version": config.version,
        }
    return PublicRecordsResult.success(
        query,
        [probe],
        warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
    )


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), query.source.source_id, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: OhioPAXClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Ohio DTS/PAX recorder operation."""

    tenant = _tenant(args)
    query_source_id = str(args.source)
    selectors: dict[str, Any] | None = None
    preflight_error: PAXSelectionError | None = None
    if args.command == "search":
        try:
            selectors = _selectors_from_args(args)
        except PAXSelectionError as error:
            preflight_error = error
            selectors = _selector_input_from_args(args)
        if (
            preflight_error is None
            and query_source_id == LICKING_DETAIL_SOURCE_ID
            and selectors is not None
            and (
                not selectors.get("instrument")
                or any(
                    selectors.get(field)
                    for field in (
                        "name",
                        "first_name",
                        "recorded_from",
                        "recorded_to",
                        "book_type",
                        "book",
                        "page",
                        "document_id",
                    )
                )
            )
        ):
            preflight_error = PAXSelectionError(
                "capability_not_supported",
                (
                    "Licking's anonymous exact-detail component accepts an "
                    "instrument number; party, date, book/page, and document-ID "
                    "discovery remains in the account portal"
                ),
                details={
                    "record_identity_source_id": LICKING_SOURCE_ID,
                    "representation_source_id": LICKING_DETAIL_SOURCE_ID,
                },
            )
        contract_limit = (
            args.limit
            if isinstance(args.limit, int)
            and not isinstance(args.limit, bool)
            and args.limit > 0
            else None
        )
        query = _query(
            tenant,
            "search",
            parameters={
                "selectors": selectors,
                "continuation": "query_bound_native_detail_page",
                "completeness": (
                    "source_reported_total"
                    if args.limit is None
                    else "caller_selected_window"
                ),
            },
            limit=contract_limit,
            cursor=args.cursor,
            query_source_id=query_source_id,
        )
    elif args.command in {"instrument", "document-info", "download"}:
        instrument = _clean(args.instrument)
        query = _query(
            tenant,
            args.command.replace("-", "_"),
            parameters={
                "instrument_number": instrument,
                "instrument_reference_id": getattr(
                    args,
                    "reference_id",
                    None,
                ),
                "destination": (
                    str(Path(args.destination).expanduser())
                    if args.command == "download"
                    else None
                ),
            },
            query_source_id=query_source_id,
        )
    else:
        query = _query(
            tenant,
            "probe",
            parameters={"structural_sentinel": tenant.sentinel_instrument},
            query_source_id=query_source_id,
        )

    source_client = client or OhioPAXClient(
        timeout=float(args.timeout),
        retry_policy=RetryPolicy(max_attempts=int(args.retry_attempts)),
        rate_limiter=MinimumIntervalRateLimiter(
            float(args.minimum_interval)
        ),
    )
    try:
        if preflight_error is not None:
            raise preflight_error
        if args.command == "search":
            assert selectors is not None
            if tenant.anonymous_discovery:
                result = _search_delaware(
                    query,
                    tenant,
                    selectors,
                    source_client,
                    limit=args.limit,
                    cursor=args.cursor,
                )
            else:
                result = _search_licking_exact(
                    query,
                    tenant,
                    selectors,
                    source_client,
                    limit=args.limit,
                    cursor=args.cursor,
                )
        elif args.command == "instrument":
            if instrument is None:
                raise PAXSelectionError(
                    "empty_instrument",
                    "instrument number must not be blank",
                )
            result = _execute_instrument(
                query,
                tenant,
                instrument,
                source_client,
            )
        elif args.command == "document-info":
            if instrument is None:
                raise PAXSelectionError(
                    "empty_instrument",
                    "instrument number must not be blank",
                )
            result = _execute_document_info(
                query,
                tenant,
                instrument,
                args.reference_id,
                source_client,
            )
        elif args.command == "download":
            if instrument is None:
                raise PAXSelectionError(
                    "empty_instrument",
                    "instrument number must not be blank",
                )
            result = _execute_download(
                query,
                tenant,
                instrument,
                args.reference_id,
                Path(args.destination),
                args.overwrite,
                source_client,
            )
        elif args.command == "probe":
            result = _execute_probe(
                query,
                tenant,
                source_client,
                query_source_id=query_source_id,
            )
        else:
            raise PAXSelectionError(
                "unsupported_command",
                f"unsupported command: {args.command}",
            )
    except PAXSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
            warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
        )
    except (OSError, TypeError, ValueError) as error:
        schema_error = SourceSchemaError(
            str(error),
            url=tenant.pax_root,
        )
        result = failure_result(
            query,
            schema_error,
            warnings=[RECORDER_WARNING, SOURCE_ROLE_WARNING],
        )
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


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=3,
    )
    add_output_args(parser)


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        required=True,
        choices=QUERY_SOURCE_IDS,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query official Ohio DTS/PAX recorder sources"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe county source components, access, and complements",
    )
    add_output_args(sources)

    search = subparsers.add_parser(
        "search",
        help="Search native recorder detail rows",
    )
    _add_source(search)
    search.add_argument("--name")
    search.add_argument("--first-name")
    search.add_argument(
        "--party",
        choices=("any", "first", "second"),
        default="any",
    )
    search.add_argument(
        "--last-name-comparison",
        choices=("LIKE", "CONTAINS", "IS"),
        default="LIKE",
    )
    search.add_argument(
        "--first-name-comparison",
        choices=("LIKE", "CONTAINS", "IS"),
        default="LIKE",
    )
    search.add_argument("--recorded-from")
    search.add_argument("--recorded-to")
    search.add_argument("--instrument", dest="instrument_selector")
    search.add_argument("--book-type")
    search.add_argument("--book")
    search.add_argument("--page")
    search.add_argument("--document-id")
    search.add_argument(
        "--include-cross-references",
        action="store_true",
    )
    search.add_argument(
        "--limit",
        type=int,
        help=(
            "Return an explicit caller-selected window; omitted exhausts every "
            "native detail page for the selected query"
        ),
    )
    search.add_argument("--cursor")
    _add_runtime(search)

    instrument = subparsers.add_parser(
        "instrument",
        help="Retrieve exact recorded-instrument detail",
    )
    _add_source(instrument)
    instrument.add_argument("instrument")
    _add_runtime(instrument)

    document_info = subparsers.add_parser(
        "document-info",
        help="Retrieve exact detail plus public document availability",
    )
    _add_source(document_info)
    document_info.add_argument("instrument")
    document_info.add_argument("--reference-id")
    _add_runtime(document_info)

    download = subparsers.add_parser(
        "download",
        help="Download an official public recorder PDF",
    )
    _add_source(download)
    download.add_argument("instrument")
    download.add_argument("--reference-id")
    download.add_argument("--destination", required=True)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify one county source with a persistent public sentinel",
    )
    _add_source(probe)
    _add_runtime(probe)
    return parser


def _emit_sources(args: argparse.Namespace) -> None:
    payload = sources_payload()
    if write_output(
        payload,
        args,
        summary="Ohio DTS/PAX recorder source components",
        result_count=len(payload["sources"]),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for source in payload["sources"]:
        metadata = source["metadata"]
        print(
            f"{source['source_id']} | {source['name']} | "
            f"anonymous discovery={metadata['anonymous_discovery']}"
        )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Ohio PAX {result.query.source.source_id} "
            f"{args.command} ({result.status.value})"
        ),
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"{result.query.source.name} {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            "  "
            f"{record.get('instrument_number') or record.get('source_record_id') or '?'}"
            f" | {record.get('record_kind') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "sources":
        _emit_sources(args)
        return 0
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
