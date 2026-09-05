#!/usr/bin/env python3
"""Query verified Oregon Tyler Municipal Record Search tenants.

The public Tyler application uses a reusable tenant-path contract, but access
and selectors vary by court.  This adapter retains each court's own identity,
records direct component observations separately from directory links, and
adds snapshot-bound local cursors to complete server-rendered result pages.

Examples:
    uv run python tools/query_eugene_municipal_court.py search \
        --tenant medford \
        --citation E018359 --output case-search.json
    uv run python tools/query_eugene_municipal_court.py search \
        --last-name ANDERSON --first-name GREGORY --limit 10 --output names.json
    uv run python tools/query_eugene_municipal_court.py dockets \
        --limit 50 --output dockets.json
    uv run python tools/query_eugene_municipal_court.py docket \
        20260729083000 TRAR 1 --output docket-detail.json
    uv run python tools/query_eugene_municipal_court.py case \
        E018359 01 --output case-detail.json
    uv run python tools/query_eugene_municipal_court.py discovery --json
    uv run python tools/query_eugene_municipal_court.py probe --json
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
from datetime import date, datetime
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

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
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        schema_fingerprint,
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
    )
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-or-eugene-municipal-record-search"
STATE_CODE = "OR"
COUNTY_FIPS = "41039"
COURT_ID = "or-eugene-municipal-court"
COURT_NAME = "Eugene Municipal Court"
TENANT_SLUG = "eugeneor"
PLATFORM_FAMILY = "tyler_municipal_record_search"
HOST_URL = "https://www.municipalrecordsearch.com"
BASE_URL = f"{HOST_URL}/{TENANT_SLUG}/"
CASES_URL = urljoin(BASE_URL, "Cases")
CASE_SEARCH_URL = urljoin(BASE_URL, "Cases/Search")
DOCKETS_URL = urljoin(BASE_URL, "Dockets")
OFFICIAL_COURT_URL = "https://www.eugene-or.gov/117/Municipal-Court"
OJD_REGISTRY_URL = "https://www.courts.oregon.gov/courts/Pages/other-courts.aspx"
JUSTFOIA_PORTAL_URL = "https://eugeneor.justfoia.com/publicportal/"
JUSTFOIA_NEW_REQUEST_URL = "https://eugeneor.justfoia.com/publicportal/home/newrequest"
JUSTFOIA_TRACK_URL = "https://eugeneor.justfoia.com/publicportal/home/track"
JUSTFOIA_ARCHIVE_URL = "https://eugeneor.justfoia.com/publicportal/requests"
JUSTFOIA_MUNICIPAL_COURT_FORM_URL = (
    "https://eugeneor.justfoia.com/Forms/Launch/81b9da81-94d7-49b8-8750-3452f260414f"
)
PAYMENT_BASE_URL = "https://www.municipalonlinepayments.com/eugeneor/court/search/api"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.35
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
)
LOCAL_TIMEZONE = ZoneInfo("America/Los_Angeles")
CURSOR_PREFIX = "eugene-mrs:v1:"

SOURCE_WARNINGS = (
    "The portal states that juvenile cases are not displayed online.",
    "Tyler serves complete HTML snapshots; continuation cursors are local and "
    "bound to the query and source snapshot.",
    "The City routes record-copy requests through its dedicated Municipal "
    "Court JustFOIA form.",
)

SEARCH_SELECTOR_FIELDS: Mapping[str, tuple[str, ...]] = {
    "Name": (
        "SearchByCriteria.LastName",
        "SearchByCriteria.FirstName",
        "SearchByCriteria.DateOfBirth",
        "SearchByCriteria.DriversLicenseNumber",
        "SearchByCriteria.UseSoundEX",
        "SearchByCriteria.UsePartialNames",
    ),
    "CitationNumber": ("SearchByCriteria.CitationNumber",),
    "DocketNumber": ("SearchByCriteria.DocketNumber",),
    "CaseNumber": ("SearchByCriteria.PDCaseNumber",),
    "VehiclePlate": (
        "SearchByCriteria.VehiclePlate",
        "SearchByCriteria.VehicleState",
    ),
    "VIN": ("SearchByCriteria.VIN",),
}


@dataclass(frozen=True)
class MunicipalRecordSearchTenant:
    """Configuration for one tenant in the shared Tyler host contract."""

    key: str
    slug: str
    source_id: str
    court_id: str
    court_name: str
    state_code: str
    county_fips: str | None
    locality: str
    official_url: str
    authority: str
    jurisdiction_id: str
    jurisdiction_name: str
    court_type: str = "municipal_court"
    court_level: str = "municipal"
    case_access_state: str = "public"
    docket_access_state: str = "public"
    verified_selectors: tuple[str, ...] = ()
    verified_components: tuple[str, ...] = ()
    observed_upcoming_docket_count: int | None = None
    directly_verified_at: str | None = None
    alternative_routes: tuple[Mapping[str, Any], ...] = ()
    official_link_role: str = "local_official_court_page"

    @property
    def base_url(self) -> str:
        return f"{HOST_URL}/{self.slug}/"

    def url(self, path: str = "") -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    @property
    def source_name(self) -> str:
        return f"{self.court_name} Online Record Search"

    @property
    def source_role(self) -> str:
        if self.case_access_state == "public" and self.docket_access_state == "public":
            return "court_case_search_and_upcoming_dockets"
        return "court_record_search_tenant_and_official_alternatives"


EUGENE_TENANT = MunicipalRecordSearchTenant(
    key="eugene",
    slug=TENANT_SLUG,
    source_id=SOURCE_ID,
    court_id=COURT_ID,
    court_name=COURT_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
    locality="Eugene",
    official_url=OFFICIAL_COURT_URL,
    authority="City of Eugene Municipal Court",
    jurisdiction_id=COUNTY_FIPS,
    jurisdiction_name="City of Eugene, Oregon",
    verified_selectors=(
        "Name",
        "CitationNumber",
        "DocketNumber",
        "CaseNumber",
        "VehiclePlate",
        "VIN",
    ),
    verified_components=(
        "case_form",
        "docket_index",
        "docket_detail",
        "case_detail",
    ),
    directly_verified_at="2026-07-29",
    alternative_routes=(
        {
            "role": "municipal_court_record_request",
            "url": JUSTFOIA_MUNICIPAL_COURT_FORM_URL,
            "provider": "JustFOIA",
        },
        {
            "role": "record_request_portal",
            "url": JUSTFOIA_PORTAL_URL,
            "provider": "JustFOIA",
        },
        {
            "role": "request_archive_search",
            "url": JUSTFOIA_ARCHIVE_URL,
            "provider": "JustFOIA",
        },
    ),
)

HERMISTON_TENANT = MunicipalRecordSearchTenant(
    key="hermiston",
    slug="hermistonor",
    source_id="us-or-hermiston-municipal-record-search",
    court_id="or-hermiston-municipal-court",
    court_name="Hermiston Municipal Court",
    state_code=STATE_CODE,
    county_fips="41059",
    locality="Hermiston",
    official_url="https://www.hermiston.gov/court",
    authority="City of Hermiston Municipal Court",
    jurisdiction_id="41059",
    jurisdiction_name="City of Hermiston, Oregon",
    verified_selectors=(
        "Name",
        "CitationNumber",
        "DocketNumber",
        "VehiclePlate",
    ),
    verified_components=(
        "case_form",
        "docket_index",
        "docket_detail",
        "case_detail",
    ),
    observed_upcoming_docket_count=116,
    directly_verified_at="2026-07-29",
    alternative_routes=(
        {
            "role": "court_records_information_and_request_portal",
            "url": "https://www.hermiston.gov/court/page/court-records",
        },
    ),
)

LINN_COUNTY_TENANT = MunicipalRecordSearchTenant(
    key="linn-county",
    slug="linncountyor",
    source_id="us-or-linn-county-justice-record-search",
    court_id="or-linn-county-justice-court",
    court_name="Linn County Justice Court",
    state_code=STATE_CODE,
    county_fips="41043",
    locality="Linn County",
    official_url="https://www.linncountyor.gov/justicecourt",
    authority="Linn County Justice Court",
    jurisdiction_id="41043",
    jurisdiction_name="Linn County, Oregon",
    court_type="justice_court",
    court_level="county",
    verified_selectors=("Name", "CitationNumber"),
    verified_components=(
        "case_form",
        "docket_index",
        "docket_detail",
        "case_detail",
    ),
    observed_upcoming_docket_count=50,
    directly_verified_at="2026-07-29",
)

MEDFORD_TENANT = MunicipalRecordSearchTenant(
    key="medford",
    slug="medfordor",
    source_id="us-or-medford-municipal-record-search",
    court_id="or-medford-municipal-court",
    court_name="Medford Municipal Court",
    state_code=STATE_CODE,
    county_fips="41029",
    locality="Medford",
    official_url=(
        "https://www.medfordoregon.gov/Government/Departments/Municipal-Court"
    ),
    authority="City of Medford Municipal Court",
    jurisdiction_id="41029",
    jurisdiction_name="City of Medford, Oregon",
    verified_selectors=(
        "Name",
        "CitationNumber",
        "DocketNumber",
        "CaseNumber",
        "VehiclePlate",
        "VIN",
    ),
    verified_components=(
        "case_form",
        "docket_index",
        "docket_detail",
        "case_detail",
    ),
    observed_upcoming_docket_count=141,
    directly_verified_at="2026-07-29",
)

SPRINGFIELD_TENANT = MunicipalRecordSearchTenant(
    key="springfield",
    slug="springfieldor",
    source_id="us-or-springfield-municipal-record-search",
    court_id="or-springfield-municipal-court",
    court_name="Springfield Municipal Court",
    state_code=STATE_CODE,
    county_fips="41039",
    locality="Springfield",
    official_url="https://springfield-or.gov/city/court/",
    authority="City of Springfield Municipal Court",
    jurisdiction_id="41039",
    jurisdiction_name="City of Springfield, Oregon",
    verified_selectors=(
        "Name",
        "CitationNumber",
        "DocketNumber",
        "CaseNumber",
    ),
    verified_components=(
        "case_form",
        "docket_index",
        "docket_detail",
        "case_detail",
    ),
    observed_upcoming_docket_count=155,
    directly_verified_at="2026-07-29",
)

CLACKAMAS_TENANT = MunicipalRecordSearchTenant(
    key="clackamas",
    slug="clackamascountyor",
    source_id="us-or-clackamas-county-justice-record-search",
    court_id="or-clackamas-county-justice-court",
    court_name="Clackamas County Justice Court",
    state_code=STATE_CODE,
    county_fips="41005",
    locality="Happy Valley",
    official_url="https://www.clackamas.us/justice",
    authority="Clackamas County Justice Court",
    jurisdiction_id="41005",
    jurisdiction_name="Clackamas County, Oregon",
    court_type="justice_court",
    court_level="county",
    case_access_state="login_required",
    docket_access_state="not_found",
    verified_components=("case_access", "docket_access"),
    directly_verified_at="2026-07-29",
    alternative_routes=(
        {
            "role": "justice_court_public_records_request_form",
            "url": (
                "https://docs.clackamas.us/documents/drupal/"
                "8e70d6e9-1d13-4dc2-905c-032d29ee9a9f"
            ),
        },
        {
            "role": "county_public_records_routing",
            "url": "https://www.clackamas.us/rm/policy.html",
        },
        {
            "role": "justice_court_information",
            "url": "https://www.clackamas.us/justice",
        },
    ),
)

CORVALLIS_TENANT = MunicipalRecordSearchTenant(
    key="corvallis",
    slug="corvallisor",
    source_id="us-or-corvallis-municipal-record-search",
    court_id="or-corvallis-municipal-court",
    court_name="Corvallis Municipal Court",
    state_code=STATE_CODE,
    county_fips="41003",
    locality="Corvallis",
    official_url="https://www.corvallisoregon.gov/finance/page/municipal-court",
    authority="City of Corvallis Municipal Court",
    jurisdiction_id="41003",
    jurisdiction_name="City of Corvallis, Oregon",
    case_access_state="login_required",
    docket_access_state="login_required",
    verified_components=("case_access", "docket_access"),
    directly_verified_at="2026-07-29",
    alternative_routes=(
        {
            "role": "city_public_records_request_form",
            "url": "https://forms.corvallisoregon.gov/Forms/PRR",
        },
        {
            "role": "city_records_archive",
            "url": "https://archives.corvallisoregon.gov/public/",
        },
        {
            "role": "municipal_court_information",
            "url": "https://www.corvallisoregon.gov/finance/page/municipal-court",
        },
        {
            "role": "municipal_court_payment_and_violation_lookup",
            "url": (
                "https://www.municipalonlinepayments.com/"
                "corvallisor/court/search"
            ),
        },
        {
            "role": "city_recorder_public_records_routing",
            "url": "https://www.corvallisoregon.gov/cm/page/city-recorder",
        },
    ),
)

GRAND_RONDE_TENANT = MunicipalRecordSearchTenant(
    key="grand-ronde",
    slug="confederatedtribesofgrandrondeor",
    source_id="us-tribal-grand-ronde-record-search",
    court_id="grand-ronde-tribal-court",
    court_name="Confederated Tribes of Grand Ronde Tribal Court",
    state_code=STATE_CODE,
    county_fips=None,
    locality="Grand Ronde",
    official_url="https://www.grandronde.org/government/tribal-court/",
    authority="Confederated Tribes of Grand Ronde Tribal Court",
    jurisdiction_id="tribal:grand-ronde",
    jurisdiction_name="Confederated Tribes of Grand Ronde",
    court_type="tribal_court",
    court_level="tribal",
    case_access_state="login_required",
    docket_access_state="login_required",
    verified_components=("case_access", "docket_access"),
    directly_verified_at="2026-07-29",
    official_link_role="tribal_official_court_page",
    alternative_routes=(
        {
            "role": "tribal_court_records_request_form",
            "url": (
                "https://www.grandronde.org/media/mv4nt40h/"
                "records-request-form-tribal-court-2024.pdf"
            ),
            "audience": "court_record_requesters",
        },
        {
            "role": "tribal_court_access_rules",
            "url": (
                "https://www.grandronde.org/media/leaf3czf/"
                "promulgation_frcp_and_frap.pdf"
            ),
        },
        {
            "role": "tribal_court_administrative_orders_and_forms",
            "url": "https://www.grandronde.org/government/tribal-court/",
        },
        {
            "role": "tribal_records_center",
            "url": "https://www.grandronde.org/government/records-center/",
            "audience": "tribal_members",
        },
        {
            "role": "tribal_records_center_request_form",
            "url": (
                "https://www.grandronde.org/media/u4vhfiuy/"
                "2024-07-24-freedom-of-information-form-and-ordinance.pdf"
            ),
            "audience": "tribal_members",
        },
    ),
)

OREGON_TENANTS: Mapping[str, MunicipalRecordSearchTenant] = {
    tenant.key: tenant
    for tenant in (
        CLACKAMAS_TENANT,
        CORVALLIS_TENANT,
        EUGENE_TENANT,
        GRAND_RONDE_TENANT,
        HERMISTON_TENANT,
        LINN_COUNTY_TENANT,
        MEDFORD_TENANT,
        SPRINGFIELD_TENANT,
    )
}
TENANTS_BY_SLUG: Mapping[str, MunicipalRecordSearchTenant] = {
    tenant.slug: tenant for tenant in OREGON_TENANTS.values()
}

def _source_metadata(
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> SourceMetadata:
    authentication = (
        "none"
        if (
            tenant.case_access_state == "public"
            and tenant.docket_access_state == "public"
        )
        else "component_specific"
    )
    return SourceMetadata(
        source_id=tenant.source_id,
        name=tenant.source_name,
        source_role=tenant.source_role,
        base_url=tenant.base_url,
        dataset_id=f"municipalrecordsearch:{tenant.slug}",
        metadata={
            "authority": tenant.authority,
            "state_code": tenant.state_code,
            "county_fips": tenant.county_fips,
            "tenant_slug": tenant.slug,
            "platform_family": PLATFORM_FAMILY,
            "vendor": "Tyler Technologies",
            "authentication": authentication,
            "component_access": {
                "cases": tenant.case_access_state,
                "dockets": tenant.docket_access_state,
            },
            "official_court_url": tenant.official_url,
            "official_registry_url": OJD_REGISTRY_URL,
            "alternative_routes": list(tenant.alternative_routes),
            "native_pagination": False,
        },
    )


SOURCE_METADATA = _source_metadata()


def _source_warnings(
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> tuple[str, ...]:
    if tenant is EUGENE_TENANT:
        return SOURCE_WARNINGS
    warnings = [
        "Tyler serves complete HTML snapshots; continuation cursors are local "
        "and bound to the tenant, query, and source snapshot.",
        "Links in the shared tenant directory are directory claims; component "
        "access is reported from direct tenant probes.",
    ]
    if tenant.case_access_state != "public" or tenant.docket_access_state != "public":
        warnings.append(
            "One or more tenant components currently resolve to sign-in or "
            "unavailable routes; official alternatives are included."
        )
    return tuple(warnings)


class EugeneCourtSelectionError(ValueError):
    """A selector or continuation cannot be represented for this tenant."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})
        self.status = status


class TenantLoginRequiredError(PublicRecordsHTTPError):
    """A tenant component redirected to the shared sign-in route."""

    result_status = ResultStatus.RESTRICTED
    category = "access"
    retryable = False
    code = "login_required"


@dataclass(frozen=True)
class FetchedHTML:
    """One exact public HTML response and its content fingerprint."""

    url: str
    text: str
    status_code: int
    content_type: str | None
    sha256: str

    def snapshot(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "http_status": self.status_code,
            "content_type": self.content_type,
            "sha256": self.sha256,
            "byte_length": len(self.text.encode("utf-8")),
        }


@dataclass(frozen=True)
class ParsedCollection:
    """A normalized collection from one complete server-rendered page."""

    records: tuple[dict[str, Any], ...]
    page: FetchedHTML
    schema_fingerprint: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class ParsedDocket:
    """One docket session plus the cases returned by its detail route."""

    record: dict[str, Any]
    page: FetchedHTML
    schema_fingerprint: str


@dataclass(frozen=True)
class ParsedRecord:
    """One case-detail record and its exact source response."""

    record: dict[str, Any]
    page: FetchedHTML
    schema_fingerprint: str


@dataclass(frozen=True)
class CursorState:
    operation: str
    query_fingerprint: str
    snapshot_fingerprint: str
    offset: int
    anchor: str


@dataclass(frozen=True)
class SearchSpec:
    search_by: str
    parameters: Mapping[str, str]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split())
    return normalized or None


def _direct_text(tag: Tag | None) -> str | None:
    if tag is None:
        return None
    parts = [str(child) for child in tag.children if isinstance(child, NavigableString)]
    return _text(" ".join(parts))


def _headers(response: Any) -> Mapping[str, Any]:
    values = getattr(response, "headers", {})
    return values if isinstance(values, Mapping) else {}


def _header(response: Any, name: str) -> str | None:
    for key, value in _headers(response).items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def _response_url(
    response: Any,
    requested_url: str,
    params: Mapping[str, Any] | None,
) -> str:
    value = _text(getattr(response, "url", None))
    if value:
        return value
    if not params:
        return requested_url
    separator = "&" if "?" in requested_url else "?"
    return f"{requested_url}{separator}{urlencode(params, doseq=True)}"


def _application_error(page: FetchedHTML) -> bool:
    prefix = page.text[:5000].lower()
    return (
        "<title>application error" in prefix
        or "application error | online record search" in prefix
    )


def _login_redirect_observed(url: str, text: str) -> bool:
    path = urlsplit(url).path.rstrip("/").casefold()
    if path.endswith("/account/login"):
        return True
    prefix = text[:12000].casefold()
    return (
        "account/login" in prefix
        and (
            "<title>log in" in prefix
            or "<title>login" in prefix
            or 'name="password"' in prefix
        )
    )


def _source_scope(
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> dict[str, Any]:
    jurisdiction = tenant.jurisdiction_name
    if tenant is EUGENE_TENANT:
        jurisdiction = "City of Eugene, Lane County, Oregon"
    return {
        "jurisdiction": jurisdiction,
        "jurisdiction_id": tenant.jurisdiction_id,
        "court_level": tenant.court_level,
        "record_scope": (
            "tenant case index and upcoming court dockets"
        ),
        "platform_family": PLATFORM_FAMILY,
        "tenant_slug": tenant.slug,
        "component_access": {
            "cases": tenant.case_access_state,
            "dockets": tenant.docket_access_state,
        },
    }


def _court_payload(
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> dict[str, Any]:
    return {
        "court_id": tenant.court_id,
        "native_court_id": tenant.court_id,
        "name": tenant.court_name,
        "court_type": tenant.court_type,
        "court_level": tenant.court_level,
        "state_code": tenant.state_code,
        "county_fips": tenant.county_fips,
        "county_geoid": tenant.county_fips,
        "locality": tenant.locality,
        "jurisdiction_id": tenant.jurisdiction_id,
        "jurisdiction_name": tenant.jurisdiction_name,
        "authority": tenant.authority,
        "official_url": tenant.official_url,
    }


def _official_chain(
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> list[dict[str, str]]:
    if tenant is EUGENE_TENANT:
        return [
            {
                "role": "state_official_registry",
                "url": OJD_REGISTRY_URL,
            },
            {
                "role": "city_official_court_page",
                "url": OFFICIAL_COURT_URL,
            },
            {
                "role": "city_linked_record_search_tenant",
                "url": BASE_URL,
            },
        ]
    chain = [
        {
            "role": tenant.official_link_role,
            "url": tenant.official_url,
        },
        {
            "role": "court_record_search_tenant",
            "url": tenant.base_url,
        },
    ]
    if tenant.court_type != "tribal_court":
        chain.insert(
            0,
            {
                "role": "state_official_registry",
                "url": OJD_REGISTRY_URL,
            },
        )
    return chain


def _request_complement(
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> dict[str, Any]:
    if tenant is EUGENE_TENANT:
        return {
            "kind": "official_record_request_and_file_delivery",
            "provider": "JustFOIA",
            "portal_url": JUSTFOIA_PORTAL_URL,
            "new_request_url": JUSTFOIA_NEW_REQUEST_URL,
            "municipal_court_form_url": JUSTFOIA_MUNICIPAL_COURT_FORM_URL,
            "track_url": JUSTFOIA_TRACK_URL,
            "archive_search_url": JUSTFOIA_ARCHIVE_URL,
            "distinct_from_case_index": True,
        }
    return {
        "kind": "official_alternative_routes",
        "routes": [dict(route) for route in tenant.alternative_routes],
        "distinct_from_case_index": True,
    }


def _source_provenance(
    page: FetchedHTML,
    *,
    schema: str,
    request_parameters: Mapping[str, Any] | None = None,
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> dict[str, Any]:
    return {
        "official_referrer_chain": _official_chain(tenant),
        "platform_family": PLATFORM_FAMILY,
        "tenant_slug": tenant.slug,
        "source_id": tenant.source_id,
        "court_id": tenant.court_id,
        "request_parameters": dict(request_parameters or {}),
        "source_snapshot": page.snapshot(),
        "schema_fingerprint": schema,
    }


def _date_from_sort(value: str | None) -> str | None:
    if not value or not re.fullmatch(r"\d{8}", value):
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _date_from_display(value: str | None) -> str | None:
    if value is None:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%Y %I:%M%p"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _session_datetime(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise EugeneCourtSelectionError(
            "invalid_docket_date",
            "docket date must use YYYYMMDDHHMMSS",
            details={"date": value},
        ) from exc
    return parsed.replace(tzinfo=LOCAL_TIMEZONE).isoformat()


def _normalize_case_selector(value: str, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None or len(normalized) > 120:
        raise EugeneCourtSelectionError(
            "invalid_selector",
            f"{field_name} must be a non-empty value of at most 120 characters",
            details={"field": field_name},
        )
    return normalized


def _search_options(
    soup: BeautifulSoup,
    page_url: str,
    *,
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> dict[str, str]:
    select = soup.select_one("form[action$='/Cases/Search'] select#SearchBy")
    if not isinstance(select, Tag):
        raise SourceChangedHTTPError(
            200,
            url=page_url,
            response_text=f"{tenant.court_name} case-search selector was not found",
        )
    options: dict[str, str] = {}
    for option in select.find_all("option"):
        value = _text(option.get("value"))
        label = _text(option.get_text(" ", strip=True))
        if value and label:
            options[value] = label
    if not options:
        raise SourceChangedHTTPError(
            200,
            url=page_url,
            response_text=f"{tenant.court_name} case-search selector has no options",
        )
    return options


def parse_case_search(
    page: FetchedHTML,
    *,
    expected_search_by: str,
    request_parameters: Mapping[str, str],
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> ParsedCollection:
    """Parse one tenant case-search result snapshot."""

    if _application_error(page):
        raise SourceResponseError(
            f"{tenant.court_name} record search returned its application error page",
            url=page.url,
        )
    soup = BeautifulSoup(page.text, "html.parser")
    options = _search_options(soup, page.url, tenant=tenant)
    if expected_search_by not in options:
        raise EugeneCourtSelectionError(
            "selector_not_available",
            f"{tenant.court_name} does not expose the {expected_search_by} selector",
            details={
                "requested_selector": expected_search_by,
                "available_selectors": sorted(options),
            },
        )

    result_table = None
    rows = soup.select("tr[data-sort-citation-number]")
    if rows:
        result_table = rows[0].find_parent("table")
    no_results = "No results found" in soup.get_text(" ", strip=True)
    if not rows and not no_results:
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text=(
                f"{tenant.court_name} search page has neither result rows nor the "
                "authoritative no-results marker"
            ),
        )

    headers = []
    if isinstance(result_table, Tag):
        headers = [
            _text(header.get_text(" ", strip=True)) or ""
            for header in result_table.select("thead th")
        ]
    row_attributes = sorted(
        {
            str(key)
            for row in rows
            for key in row.attrs
            if str(key).startswith("data-sort-")
        }
    )
    schema = schema_fingerprint(
        {
            "kind": "tyler_municipal_record_search_case_results",
            "search_options": options,
            "headers": headers,
            "row_attributes": row_attributes,
            "detail_route": f"/{tenant.slug}/Cases/Detail",
        }
    )

    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Tag):
            continue
        detail_anchor = row.select_one("a[href*='/Cases/Detail']")
        if not isinstance(detail_anchor, Tag):
            raise SourceChangedHTTPError(
                200,
                url=page.url,
                response_text=f"{tenant.court_name} case result lacks its detail link",
            )
        detail_url = urljoin(page.url, str(detail_anchor.get("href") or ""))
        detail_params = parse_qs(urlsplit(detail_url).query)
        citation_number = _text((detail_params.get("citationNumber") or [None])[0])
        violation_number = _text((detail_params.get("violationNumber") or [None])[0])
        if not citation_number or not violation_number:
            raise SourceChangedHTTPError(
                200,
                url=page.url,
                response_text=(
                    f"{tenant.court_name} case detail link lacks citationNumber "
                    "or violationNumber"
                ),
            )

        raw_case_number = f"{citation_number}-{violation_number}"
        cells = [cell for cell in row.find_all("td", recursive=False)]
        display_cells = [_text(cell.get_text(" ", strip=True)) for cell in cells]
        large_cells = [
            cell
            for cell in cells
            if "visible-lg" in (cell.get("class") or [])
            and "visible-md" not in (cell.get("class") or [])
        ]
        last_name = (
            _text(large_cells[0].get_text(" ", strip=True)) if large_cells else None
        )
        first_name = (
            _text(large_cells[1].get_text(" ", strip=True))
            if len(large_cells) > 1
            else None
        )
        full_name = _text(" ".join(value for value in (first_name, last_name) if value))

        data_attributes = {
            str(key): _text(value)
            for key, value in row.attrs.items()
            if str(key).startswith("data-sort-")
        }
        warrant_text = _text(cells[0].get_text(" ", strip=True)) if cells else None
        has_warrant = bool(
            warrant_text
            and warrant_text.casefold() not in {"no", "--"}
            and "warrant" in warrant_text.casefold()
        )
        violation_date = _date_from_sort(_text(row.get("data-sort-violation-date")))
        status_date = _date_from_sort(_text(row.get("data-sort-status-date")))
        docket_number = _text(row.get("data-sort-docket-number"))
        if docket_number and docket_number.startswith("D-"):
            docket_number = docket_number[2:]
        fine_amount = _text(row.get("data-sort-fine-amount"))
        case_ref = canonical_court_ref(
            tenant.source_id,
            tenant.court_id,
            raw_case_number,
        )
        records.append(
            {
                "canonical_ref": case_ref,
                "source_id": tenant.source_id,
                "record_kind": "case",
                "court": _court_payload(tenant),
                "raw_case_number": raw_case_number,
                "citation_number": citation_number,
                "violation_number": violation_number,
                "docket_number": docket_number,
                "caption": full_name,
                "defendant": {
                    "full_name": full_name,
                    "first_name": first_name,
                    "last_name": last_name,
                },
                "parties": (
                    [{"name": full_name, "role": "defendant"}] if full_name else []
                ),
                "offense": _text(row.get("data-sort-offense")),
                "violation_date": violation_date,
                "status": _text(row.get("data-sort-status")),
                "status_date": status_date,
                "fine_amount": fine_amount,
                "warrant": {
                    "active": has_warrant,
                    "display": warrant_text,
                },
                "detail_url": detail_url,
                "source_url": page.url,
                "access_state": "public",
                "documents": [],
                "document_request": _request_complement(tenant),
                "source_scope": _source_scope(tenant),
                "source_fields": {
                    "data_attributes": data_attributes,
                    "display_cells": display_cells,
                    "detail_query": {
                        key: values for key, values in detail_params.items()
                    },
                },
                "source_provenance": _source_provenance(
                    page,
                    schema=schema,
                    request_parameters=request_parameters,
                    tenant=tenant,
                ),
                "schema_fingerprint": schema,
            }
        )

    return ParsedCollection(
        records=tuple(records),
        page=page,
        schema_fingerprint=schema,
        metadata={
            "available_search_options": options,
            "native_result_count": len(records),
            "native_pagination": False,
            "authoritative_no_results": no_results,
        },
    )


def parse_docket_index(
    page: FetchedHTML,
    *,
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> ParsedCollection:
    """Parse one tenant's complete upcoming-docket index."""

    if _application_error(page):
        raise SourceResponseError(
            f"{tenant.court_name} upcoming dockets returned an application error",
            url=page.url,
        )
    soup = BeautifulSoup(page.text, "html.parser")
    rows = soup.select("tr[data-sort-date]")
    table = rows[0].find_parent("table") if rows else soup.select_one("table")
    if not isinstance(table, Tag):
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text=f"{tenant.court_name} upcoming-docket table was not found",
        )
    headers = [
        _text(header.get_text(" ", strip=True)) or ""
        for header in table.select("thead th")
    ]
    required = {"Date", "Time", "Docket", "Courtroom", "Judge", "Actions"}
    if not required.issubset(set(headers)):
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text=(
                f"{tenant.court_name} upcoming-docket columns changed: "
                f"{', '.join(headers)}"
            ),
        )
    schema = schema_fingerprint(
        {
            "kind": "tyler_municipal_record_search_docket_index",
            "headers": headers,
            "row_attributes": [
                "data-sort-date",
                "data-sort-docket",
                "data-sort-courtroom",
                "data-sort-judge",
            ],
            "detail_route": f"/{tenant.slug}/Dockets/Detail",
        }
    )

    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Tag):
            continue
        anchor = row.select_one("a[href*='/Dockets/Detail']")
        if not isinstance(anchor, Tag):
            raise SourceChangedHTTPError(
                200,
                url=page.url,
                response_text=f"{tenant.court_name} docket row lacks its detail link",
            )
        detail_url = urljoin(page.url, str(anchor.get("href") or ""))
        query = parse_qs(urlsplit(detail_url).query)
        native_date = _text((query.get("date") or [None])[0])
        calendar_code = _text((query.get("calendarCode") or [None])[0])
        room_code = _text((query.get("roomCode") or [None])[0])
        if not native_date or not calendar_code or not room_code:
            raise SourceChangedHTTPError(
                200,
                url=page.url,
                response_text=(
                    f"{tenant.court_name} docket detail link lacks date, "
                    "calendarCode, or roomCode"
                ),
            )
        cells = [cell for cell in row.find_all("td", recursive=False)]
        if len(cells) < 6:
            raise SourceChangedHTTPError(
                200,
                url=page.url,
                response_text=(
                    f"{tenant.court_name} docket row has fewer than six cells"
                ),
            )
        session_id = f"{native_date}|{calendar_code}|{room_code}"
        session_ref = canonical_court_ref(
            tenant.source_id,
            tenant.court_id,
            session_id,
            "calendar_session",
        )
        record_date = _date_from_sort(native_date[:8])
        records.append(
            {
                "canonical_ref": session_ref,
                "source_id": tenant.source_id,
                "record_kind": "calendar_session",
                "court": _court_payload(tenant),
                "native_session_id": session_id,
                "native_date": native_date,
                "calendar_code": calendar_code,
                "room_code": room_code,
                "date": record_date,
                "start_at": _session_datetime(native_date),
                "date_raw": _direct_text(cells[0]),
                "time_raw": _direct_text(cells[1]),
                "docket_name": _direct_text(cells[2])
                or _text(row.get("data-sort-docket")),
                "courtroom": _direct_text(cells[3])
                or _text(row.get("data-sort-courtroom")),
                "judge": _direct_text(cells[4]) or _text(row.get("data-sort-judge")),
                "detail_url": detail_url,
                "underlying_cases_available": True,
                "source_url": page.url,
                "source_scope": _source_scope(tenant),
                "source_fields": {
                    "data_attributes": {
                        str(key): _text(value)
                        for key, value in row.attrs.items()
                        if str(key).startswith("data-sort-")
                    },
                    "display_cells": [
                        _text(cell.get_text(" ", strip=True)) for cell in cells
                    ],
                    "detail_query": {key: values for key, values in query.items()},
                },
                "source_provenance": _source_provenance(
                    page,
                    schema=schema,
                    tenant=tenant,
                ),
                "schema_fingerprint": schema,
            }
        )
    return ParsedCollection(
        records=tuple(records),
        page=page,
        schema_fingerprint=schema,
        metadata={
            "native_result_count": len(records),
            "native_pagination": False,
        },
    )


def _table_pairs(container: Tag | None) -> dict[str, str | None]:
    if container is None:
        return {}
    table = container if container.name == "table" else container.find("table")
    if not isinstance(table, Tag):
        return {}
    values: dict[str, str | None] = {}
    for row in table.find_all("tr"):
        header = row.find("th")
        cell = row.find("td")
        if not isinstance(header, Tag) or not isinstance(cell, Tag):
            continue
        key = _text(header.get_text(" ", strip=True))
        if key:
            values[key] = _text(cell.get_text(" ", strip=True))
    return values


def parse_docket_detail(
    page: FetchedHTML,
    *,
    native_date: str,
    calendar_code: str,
    room_code: str,
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> ParsedDocket:
    """Parse one tenant docket session and its underlying cases."""

    if _application_error(page):
        raise SourceResponseError(
            f"{tenant.court_name} docket detail returned an application error",
            url=page.url,
        )
    soup = BeautifulSoup(page.text, "html.parser")
    heading = soup.select_one("main h1, [role='main'] h1, .page-header h1")
    if not isinstance(heading, Tag):
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text=f"{tenant.court_name} docket detail heading was not found",
        )
    small = heading.find("small")
    time_raw = (
        _text(small.get_text(" ", strip=True)) if isinstance(small, Tag) else None
    )
    if isinstance(small, Tag):
        small.extract()
    docket_name = _text(heading.get_text(" ", strip=True))
    summary = _table_pairs(soup.select_one(".page-header"))
    rows = soup.select("tr[data-sort-citation]")
    table = (
        rows[0].find_parent("table") if rows else soup.select_one("table.table-striped")
    )
    headers = (
        [
            _text(header.get_text(" ", strip=True)) or ""
            for header in table.select("thead th")
        ]
        if isinstance(table, Tag)
        else []
    )
    if rows and not {"Case", "Defendant", "Offense"}.issubset(set(headers)):
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text=(
                f"{tenant.court_name} docket-detail case columns changed: "
                f"{', '.join(headers)}"
            ),
        )
    schema = schema_fingerprint(
        {
            "kind": "tyler_municipal_record_search_docket_detail",
            "headers": headers,
            "row_attributes": sorted(
                {
                    str(key)
                    for row in rows
                    for key in row.attrs
                    if str(key).startswith("data-sort-")
                }
            ),
            "case_detail_route": f"/{tenant.slug}/Cases/Detail",
        }
    )
    session_id = f"{native_date}|{calendar_code}|{room_code}"
    session_ref = canonical_court_ref(
        tenant.source_id,
        tenant.court_id,
        session_id,
        "calendar_session",
    )
    cases: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Tag):
            continue
        anchor = row.select_one("a[href*='/Cases/Detail']")
        if not isinstance(anchor, Tag):
            raise SourceChangedHTTPError(
                200,
                url=page.url,
                response_text=f"{tenant.court_name} docket case lacks its detail link",
            )
        detail_url = urljoin(page.url, str(anchor.get("href") or ""))
        query = parse_qs(urlsplit(detail_url).query)
        citation_number = _text((query.get("citationNumber") or [None])[0])
        violation_number = _text((query.get("violationNumber") or [None])[0])
        if not citation_number or not violation_number:
            raise SourceChangedHTTPError(
                200,
                url=page.url,
                response_text=(
                    f"{tenant.court_name} docket case link lacks a stable selector"
                ),
            )
        raw_case_number = f"{citation_number}-{violation_number}"
        cells = [cell for cell in row.find_all("td", recursive=False)]
        if len(cells) < 4:
            raise SourceChangedHTTPError(
                200,
                url=page.url,
                response_text=(
                    f"{tenant.court_name} docket case has fewer than four cells"
                ),
            )
        attorney_index = 2 if len(cells) >= 5 else None
        offense_index = 3 if len(cells) >= 5 else 2
        case_ref = canonical_court_ref(
            tenant.source_id,
            tenant.court_id,
            raw_case_number,
        )
        occurrence_ref = canonical_court_ref(
            tenant.source_id,
            tenant.court_id,
            raw_case_number,
            "calendar_case",
            session_id,
        )
        cases.append(
            {
                "canonical_ref": occurrence_ref,
                "case_ref": case_ref,
                "raw_case_number": raw_case_number,
                "citation_number": citation_number,
                "violation_number": violation_number,
                "defendant_name": _direct_text(cells[1]),
                "attorney": (
                    _direct_text(cells[attorney_index])
                    if attorney_index is not None
                    else None
                ),
                "offense": _direct_text(cells[offense_index])
                or _text(row.get("data-sort-offense")),
                "detail_url": detail_url,
                "source_fields": {
                    "data_attributes": {
                        str(key): _text(value)
                        for key, value in row.attrs.items()
                        if str(key).startswith("data-sort-")
                    },
                    "display_cells": [
                        _text(cell.get_text(" ", strip=True)) for cell in cells
                    ],
                    "detail_query": {key: values for key, values in query.items()},
                },
            }
        )

    record = {
        "canonical_ref": session_ref,
        "source_id": tenant.source_id,
        "record_kind": "calendar_session",
        "court": _court_payload(tenant),
        "native_session_id": session_id,
        "native_date": native_date,
        "calendar_code": calendar_code,
        "room_code": room_code,
        "date": _date_from_sort(native_date[:8]),
        "start_at": _session_datetime(native_date),
        "docket_name": docket_name,
        "time_raw": time_raw,
        "judge": summary.get("Judge"),
        "courtroom": summary.get("Courtroom"),
        "case_count": len(cases),
        "cases": cases,
        "detail_url": page.url,
        "source_url": page.url,
        "source_scope": _source_scope(tenant),
        "source_fields": {
            "summary": summary,
            "headers": headers,
        },
        "source_provenance": _source_provenance(
            page,
            schema=schema,
            request_parameters={
                "date": native_date,
                "calendarCode": calendar_code,
                "roomCode": room_code,
            },
            tenant=tenant,
        ),
        "schema_fingerprint": schema,
    }
    return ParsedDocket(record=record, page=page, schema_fingerprint=schema)


def _section_pairs(soup: BeautifulSoup, selector: str) -> dict[str, str | None]:
    section = soup.select_one(selector)
    return _table_pairs(section if isinstance(section, Tag) else None)


_JSON_ROUTE_RE = re.compile(r"\$\.getJSON\(\s*['\"]([^'\"]+)['\"]")


def parse_case_detail(
    page: FetchedHTML,
    *,
    citation_number: str,
    violation_number: str,
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> ParsedRecord:
    """Parse one stable tenant citation/violation detail page."""

    if _application_error(page):
        raise SourceResponseError(
            f"{tenant.court_name} case detail returned its application error page",
            url=page.url,
        )
    soup = BeautifulSoup(page.text, "html.parser")
    heading = soup.select_one(".page-header h1")
    if not isinstance(heading, Tag):
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text=f"{tenant.court_name} case detail heading was not found",
        )
    heading_text = _text(heading.get_text(" ", strip=True)) or ""
    match = re.search(r"Citation\s+(\S+)-(\S+)", heading_text)
    if not match:
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text=f"{tenant.court_name} case detail lacks its citation heading",
        )
    observed_citation, observed_violation = match.groups()
    if (
        observed_citation.casefold() != citation_number.casefold()
        or observed_violation.casefold() != violation_number.casefold()
    ):
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text=f"{tenant.court_name} case detail resolved to another case",
        )

    defendant_label = soup.find(
        lambda tag: (
            isinstance(tag, Tag)
            and tag.name in {"div", "h2", "h3"}
            and _text(tag.get_text(" ", strip=True)) == "Defendant"
        )
    )
    defendant_table = (
        defendant_label.find_next("table") if isinstance(defendant_label, Tag) else None
    )
    defendant = _table_pairs(
        defendant_table if isinstance(defendant_table, Tag) else None
    )
    citation_info = _section_pairs(soup, "#citation-information")
    miscellaneous = _section_pairs(soup, "#miscellaneous")
    status_fields = _section_pairs(soup, "#status")
    fee_info = _section_pairs(soup, "#fee-info")
    judgment = _section_pairs(soup, "#judgement-info")

    summary_heading = soup.find(
        lambda tag: (
            isinstance(tag, Tag)
            and tag.name == "h3"
            and (_text(tag.get_text(" ", strip=True)) or "").startswith("Violations")
        )
    )
    summary_table = (
        summary_heading.find_next("table") if isinstance(summary_heading, Tag) else None
    )
    violation_headers = (
        [
            _text(value.get_text(" ", strip=True)) or ""
            for value in summary_table.select("thead th")
        ]
        if isinstance(summary_table, Tag)
        else []
    )
    violation_rows = []
    if isinstance(summary_table, Tag):
        for row in summary_table.select("tbody tr"):
            violation_rows.append(
                [
                    _text(cell.get_text(" ", strip=True))
                    for cell in row.find_all("td", recursive=False)
                ]
            )

    links: list[dict[str, str | None]] = []
    document_links: list[dict[str, str | None]] = []
    payment_urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page.url, str(anchor.get("href")))
        label = _text(anchor.get_text(" ", strip=True))
        lowered = href.casefold()
        if lowered.startswith(("javascript:", "mailto:", "tel:")):
            continue
        value = {"url": href, "label": label}
        links.append(value)
        if "municipalonlinepayments.com" in lowered:
            payment_urls.append(href)
        if (
            "document" in lowered
            or "attachment" in lowered
            or "download" in lowered
            or re.search(r"\.(pdf|tiff?|docx?|xlsx?)(?:$|\?)", lowered)
        ):
            document_links.append(value)

    dynamic_routes = [
        urljoin(page.url, route) for route in _JSON_ROUTE_RE.findall(page.text)
    ]
    documents_route = next(
        (value for value in dynamic_routes if "ViolationDocuments" in value),
        None,
    )
    history_route = next(
        (value for value in dynamic_routes if "ViolationHistory" in value),
        None,
    )
    priors_route = next(
        (value for value in dynamic_routes if "ViolationPriors" in value),
        None,
    )
    raw_case_number = f"{citation_number}-{violation_number}"
    schema = schema_fingerprint(
        {
            "kind": "tyler_municipal_record_search_case_detail",
            "sections": sorted(
                section.get("id")
                for section in soup.find_all("section", id=True)
                if section.get("id")
            ),
            "citation_fields": sorted(citation_info),
            "status_fields": sorted(status_fields),
            "fee_fields": sorted(fee_info),
            "judgment_fields": sorted(judgment),
            "violation_headers": violation_headers,
            "dynamic_route_families": sorted(
                {urlsplit(value).path.rsplit("/", 1)[0] for value in dynamic_routes}
            ),
        }
    )
    case_ref = canonical_court_ref(
        tenant.source_id,
        tenant.court_id,
        raw_case_number,
    )
    detail_url = tenant.url("Cases/Detail") + "?" + urlencode(
        {
            "citationNumber": citation_number,
            "violationNumber": violation_number,
        }
    )
    record = {
        "canonical_ref": case_ref,
        "source_id": tenant.source_id,
        "record_kind": "case",
        "court": _court_payload(tenant),
        "raw_case_number": raw_case_number,
        "citation_number": citation_number,
        "violation_number": violation_number,
        "docket_number": citation_info.get("Docket Number"),
        "caption": defendant.get("Name"),
        "defendant": {
            "full_name": defendant.get("Name"),
        },
        "parties": (
            [{"name": defendant["Name"], "role": "defendant"}]
            if defendant.get("Name")
            else []
        ),
        "offense": citation_info.get("Offense Description"),
        "citation_date_raw": citation_info.get("Citation Date"),
        "filed_date": _date_from_display(citation_info.get("Filed Date")),
        "police_case_number": citation_info.get("PD Case Number"),
        "status": status_fields.get("Status"),
        "status_fields": status_fields,
        "active_warrant": (
            (status_fields.get("Active Warrant") or "").casefold() == "yes"
        ),
        "citation_information": citation_info,
        "miscellaneous": miscellaneous,
        "fees": fee_info,
        "judgment": judgment,
        "payment_urls": sorted(set(payment_urls)),
        "detail_url": detail_url,
        "source_url": page.url,
        "documents": document_links,
        "document_available": bool(document_links or soup.select_one("#documents")),
        "related_routes": {
            "priors": priors_route,
            "history": history_route,
            "documents": documents_route,
        },
        "document_request": _request_complement(tenant),
        "access_state": "public",
        "source_scope": _source_scope(tenant),
        "source_fields": {
            "heading": heading_text,
            "defendant": defendant,
            "citation_information": citation_info,
            "miscellaneous": miscellaneous,
            "status": status_fields,
            "fees": fee_info,
            "judgment": judgment,
            "violation_headers": violation_headers,
            "violation_rows": violation_rows,
            "links": links,
            "dynamic_json_routes": dynamic_routes,
        },
        "source_provenance": _source_provenance(
            page,
            schema=schema,
            request_parameters={
                "citationNumber": citation_number,
                "violationNumber": violation_number,
            },
            tenant=tenant,
        ),
        "schema_fingerprint": schema,
    }
    return ParsedRecord(record=record, page=page, schema_fingerprint=schema)


def parse_tenant_directory(page: FetchedHTML) -> dict[str, Any]:
    """Parse the shared host's public tenant inventory."""

    soup = BeautifulSoup(page.text, "html.parser")
    tenants: dict[str, dict[str, Any]] = {}
    for item in soup.select("#site-list li"):
        if not isinstance(item, Tag):
            continue
        anchors = [
            anchor
            for anchor in item.select("a.court-name[href]")
            if isinstance(anchor, Tag)
        ]
        if not anchors:
            continue
        anchor = next(
            (
                candidate
                for candidate in anchors
                if _text(candidate.get_text(" ", strip=True))
            ),
            anchors[0],
        )
        path = urlsplit(urljoin(page.url, str(anchor.get("href")))).path
        slug = path.strip("/").split("/", 1)[0]
        if not slug:
            continue
        links = {
            urlsplit(urljoin(page.url, str(link.get("href")))).path
            for link in item.find_all("a", href=True)
        }
        tenants[slug] = {
            "slug": slug,
            "name": _text(anchor.get_text(" ", strip=True)),
            "tenant_url": f"{HOST_URL}/{slug}/",
            "case_search": f"/{slug}/Cases" in links,
            "upcoming_dockets": f"/{slug}/Dockets" in links,
        }
    if not tenants:
        raise SourceChangedHTTPError(
            200,
            url=page.url,
            response_text="Tyler tenant directory contains no court entries",
        )
    tenant_records = [tenants[slug] for slug in sorted(tenants)]
    directory_claims = {
        slug: {
            "basis": "tenant_directory_navigation_link",
            "case_search_link": value["case_search"],
            "upcoming_dockets_link": value["upcoming_dockets"],
            "direct_component_verification": False,
        }
        for slug, value in sorted(tenants.items())
    }
    return {
        "tenant_count": len(tenants),
        "case_search_tenant_count": sum(
            1 for value in tenants.values() if value["case_search"]
        ),
        "docket_tenant_count": sum(
            1 for value in tenants.values() if value["upcoming_dockets"]
        ),
        "eugene": tenants.get(TENANT_SLUG),
        "tenants": tenant_records,
        "directory_claims": directory_claims,
        "oregon_tenants": [
            tenants[slug] for slug in TENANTS_BY_SLUG if slug in tenants
        ],
        "schema_fingerprint": schema_fingerprint(
            {
                "kind": "tyler_municipal_record_search_tenant_directory",
                "tenant_fields": [
                    "slug",
                    "name",
                    "tenant_url",
                    "case_search",
                    "upcoming_dockets",
                ],
                "claim_basis": "tenant_directory_navigation_link",
            }
        ),
    }


def _tenant_configuration_record(
    tenant: MunicipalRecordSearchTenant,
    *,
    directory_entry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    directory_claim = None
    if directory_entry is not None:
        directory_claim = {
            "basis": "tenant_directory_navigation_link",
            "case_search_link": bool(directory_entry.get("case_search")),
            "upcoming_dockets_link": bool(directory_entry.get("upcoming_dockets")),
            "direct_component_verification": False,
        }
    return {
        "canonical_ref": (
            f"PUBLICRECORDSOURCE:{tenant.source_id}/{tenant.slug}/tenant"
        ),
        "source_id": tenant.source_id,
        "record_kind": "source_tenant_configuration",
        "platform_family": PLATFORM_FAMILY,
        "tenant_key": tenant.key,
        "tenant_slug": tenant.slug,
        "tenant_url": tenant.base_url,
        "court": _court_payload(tenant),
        "directory_entry": dict(directory_entry) if directory_entry else None,
        "directory_claim": directory_claim,
        "direct_verification": {
            "verified_at": tenant.directly_verified_at,
            "case_access": tenant.case_access_state,
            "docket_access": tenant.docket_access_state,
            "selectors": list(tenant.verified_selectors),
            "components": list(tenant.verified_components),
            "observed_upcoming_docket_count": (
                tenant.observed_upcoming_docket_count
            ),
        },
        "official_referrer_chain": _official_chain(tenant),
        "official_alternatives": [
            dict(route) for route in tenant.alternative_routes
        ],
    }


def _official_links(
    page: FetchedHTML,
    *,
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> dict[str, bool]:
    soup = BeautifulSoup(page.text, "html.parser")
    links = {
        urljoin(page.url, str(anchor.get("href")))
        for anchor in soup.find_all("a", href=True)
    }
    return {
        "record_search_linked": any(
            urlsplit(value).netloc == "www.municipalrecordsearch.com"
            and urlsplit(value).path.rstrip("/") == f"/{tenant.slug}"
            for value in links
        ),
        "record_request_linked": any(
            route.get("url") in links
            for route in tenant.alternative_routes
            if route.get("url")
        ),
    }


class EugeneMunicipalCourtClient:
    """HTTP client for one configured Tyler tenant (legacy class name)."""

    def __init__(
        self,
        *,
        tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.tenant = tenant
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            clock=clock,
            sleeper=sleeper,
        )
        self.request_count = 0

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def _get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> FetchedHTML:
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._limiter.wait()
            self.request_count += 1
            try:
                response = self.session.get(
                    url,
                    params=dict(params or {}),
                    headers={
                        "Accept": "text/html,application/xhtml+xml",
                        "User-Agent": DEFAULT_USER_AGENT,
                    },
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise TransportError(
                    f"{self.tenant.court_name} transport failed: {error}",
                    url=url,
                    details={"attempts": attempt},
                ) from error

            status = int(getattr(response, "status_code", 0))
            text = str(getattr(response, "text", ""))
            response_url = _response_url(response, url, params)
            if status in self.retry_policy.retry_statuses:
                retry_after: float | None = None
                value = _header(response, "Retry-After")
                if value is not None:
                    try:
                        retry_after = max(0.0, float(value))
                    except ValueError:
                        retry_after = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt, retry_after))
                    continue
                if status == 429:
                    raise RateLimitedHTTPError(
                        status,
                        url=response_url,
                        response_text=text,
                    )
                raise HTTPStatusError(
                    status,
                    url=response_url,
                    response_text=text,
                )
            if status in {401, 403}:
                raise RestrictedHTTPError(
                    status,
                    url=response_url,
                    response_text=text,
                )
            if status == 451:
                raise TermsBlockedHTTPError(
                    status,
                    url=response_url,
                    response_text=text,
                )
            if status in {404, 410}:
                raise SourceChangedHTTPError(
                    status,
                    url=response_url,
                    response_text=text,
                )
            if status < 200 or status >= 300:
                raise HTTPStatusError(
                    status,
                    url=response_url,
                    response_text=text,
                )
            if _login_redirect_observed(response_url, text):
                raise TenantLoginRequiredError(
                    f"{self.tenant.court_name} redirected this component to sign-in",
                    url=response_url,
                    details={
                        "requested_url": url,
                        "http_status": status,
                    },
                )
            return FetchedHTML(
                url=response_url,
                text=text,
                status_code=status,
                content_type=_header(response, "Content-Type"),
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        raise TransportError(
            f"{self.tenant.court_name} transport failed: {last_error}",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )

    def search(self, spec: SearchSpec) -> ParsedCollection:
        page = self._get(
            self.tenant.url("Cases/Search"),
            params={
                "SearchBy": spec.search_by,
                **dict(spec.parameters),
            },
        )
        return parse_case_search(
            page,
            expected_search_by=spec.search_by,
            request_parameters={
                "SearchBy": spec.search_by,
                **dict(spec.parameters),
            },
            tenant=self.tenant,
        )

    def dockets(self) -> ParsedCollection:
        return parse_docket_index(
            self._get(self.tenant.url("Dockets")),
            tenant=self.tenant,
        )

    def docket(
        self,
        *,
        native_date: str,
        calendar_code: str,
        room_code: str,
    ) -> ParsedDocket:
        page = self._get(
            self.tenant.url("Dockets/Detail"),
            params={
                "date": native_date,
                "calendarCode": calendar_code,
                "roomCode": room_code,
            },
        )
        return parse_docket_detail(
            page,
            native_date=native_date,
            calendar_code=calendar_code,
            room_code=room_code,
            tenant=self.tenant,
        )

    def case(
        self,
        *,
        citation_number: str,
        violation_number: str,
    ) -> ParsedRecord:
        page = self._get(
            self.tenant.url("Cases/Detail"),
            params={
                "citationNumber": citation_number,
                "violationNumber": violation_number,
            },
        )
        return parse_case_detail(
            page,
            citation_number=citation_number,
            violation_number=violation_number,
            tenant=self.tenant,
        )

    def probe(self) -> tuple[dict[str, Any], tuple[str, ...]]:
        refs: list[str] = []
        case_page: FetchedHTML | None = None
        docket_page: ParsedCollection | None = None
        case_soup: BeautifulSoup | None = None
        options: dict[str, str] = {}

        try:
            case_page = self._get(self.tenant.url("Cases"))
            refs.append(case_page.url)
            case_soup = BeautifulSoup(case_page.text, "html.parser")
            options = _search_options(
                case_soup,
                case_page.url,
                tenant=self.tenant,
            )
            case_access = {
                "state": "public",
                "directly_verified": True,
                "observed_url": case_page.url,
                "http_status": case_page.status_code,
                "selectors": options,
                "snapshot": case_page.snapshot(),
            }
        except TenantLoginRequiredError as error:
            refs.append(error.url)
            case_access = {
                "state": "login_required",
                "directly_verified": True,
                "observed_url": error.url,
                "http_status": error.details.get("http_status"),
            }

        try:
            docket_page = self.dockets()
            refs.append(docket_page.page.url)
            docket_access = {
                "state": "public",
                "directly_verified": True,
                "observed_url": docket_page.page.url,
                "http_status": docket_page.page.status_code,
                "upcoming_docket_count": len(docket_page.records),
                "snapshot": docket_page.page.snapshot(),
                "schema_fingerprint": docket_page.schema_fingerprint,
            }
        except TenantLoginRequiredError as error:
            refs.append(error.url)
            docket_access = {
                "state": "login_required",
                "directly_verified": True,
                "observed_url": error.url,
                "http_status": error.details.get("http_status"),
            }
        except SourceChangedHTTPError as error:
            if getattr(error, "status_code", None) != 404:
                raise
            refs.append(error.url)
            docket_access = {
                "state": "not_found",
                "directly_verified": True,
                "observed_url": error.url,
                "http_status": error.status_code,
            }

        case_schema = None
        if case_soup is not None:
            case_schema = schema_fingerprint(
                {
                    "search_options": options,
                    "criteria_fields": sorted(
                        {
                            str(field.get("name"))
                            for field in case_soup.select(
                                "[name^='SearchByCriteria.']"
                            )
                            if field.get("name")
                        }
                    ),
                }
            )
        record = {
            "canonical_ref": canonical_court_ref(
                self.tenant.source_id,
                self.tenant.court_id,
                "tenant-contract",
                "source_probe",
            ),
            "source_id": self.tenant.source_id,
            "record_kind": "source_probe",
            "court": _court_payload(self.tenant),
            "platform_family": PLATFORM_FAMILY,
            "tenant_key": self.tenant.key,
            "tenant_slug": self.tenant.slug,
            "case_search_url": self.tenant.url("Cases"),
            "case_search_method": "GET",
            "available_search_options": options,
            "warrant_search_available": "WarrantNumber" in options,
            "dockets_url": self.tenant.url("Dockets"),
            "upcoming_docket_count": (
                len(docket_page.records) if docket_page is not None else None
            ),
            "component_access": {
                "cases": case_access,
                "dockets": docket_access,
            },
            "configured_direct_verification": {
                "cases": self.tenant.case_access_state,
                "dockets": self.tenant.docket_access_state,
                "selectors": list(self.tenant.verified_selectors),
            },
            "native_pagination": False,
            "adapter_cursor": "snapshot_bound_offset",
            "official_referrer_chain": _official_chain(self.tenant),
            "request_complement": _request_complement(self.tenant),
            "case_form_snapshot": (
                case_page.snapshot() if case_page is not None else None
            ),
            "docket_snapshot": (
                docket_page.page.snapshot() if docket_page is not None else None
            ),
            "schema_fingerprints": {
                "case_form": case_schema,
                "dockets": (
                    docket_page.schema_fingerprint
                    if docket_page is not None
                    else None
                ),
            },
        }
        return record, tuple(dict.fromkeys(refs))

    def tenants(
        self,
    ) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
        """Refresh the host directory and reconcile configured Oregon tenants."""

        directory_page = self._get(HOST_URL + "/")
        directory = parse_tenant_directory(directory_page)
        entries = {
            str(entry["slug"]): entry for entry in directory["tenants"]
        }
        configured = tuple(
            _tenant_configuration_record(
                tenant,
                directory_entry=entries.get(tenant.slug),
            )
            for tenant in OREGON_TENANTS.values()
        )
        missing_from_directory = [
            tenant.slug
            for tenant in OREGON_TENANTS.values()
            if tenant.slug not in entries
        ]
        family = {
            "canonical_ref": (
                f"PUBLICRECORDSOURCE:{PLATFORM_FAMILY}/tenant-directory"
            ),
            "source_id": self.tenant.source_id,
            "record_kind": "source_family_directory",
            "platform_family": PLATFORM_FAMILY,
            "vendor": "Tyler Technologies",
            "directory_url": HOST_URL + "/",
            "tenant_count": directory["tenant_count"],
            "case_search_tenant_count": directory["case_search_tenant_count"],
            "docket_tenant_count": directory["docket_tenant_count"],
            "tenants": directory["tenants"],
            "directory_claims": directory["directory_claims"],
            "configured_oregon_tenant_slugs": sorted(TENANTS_BY_SLUG),
            "configured_missing_from_directory": missing_from_directory,
            "source_snapshot": directory_page.snapshot(),
            "schema_fingerprint": directory["schema_fingerprint"],
        }
        return (family, *configured), (directory_page.url,)

    def discovery(
        self,
    ) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
        if self.tenant is not EUGENE_TENANT:
            tenant_directory_page = self._get(HOST_URL + "/")
            tenant_directory = parse_tenant_directory(tenant_directory_page)
            entries = {
                str(entry["slug"]): entry
                for entry in tenant_directory["tenants"]
            }
            probe, probe_refs = self.probe()
            primary = _tenant_configuration_record(
                self.tenant,
                directory_entry=entries.get(self.tenant.slug),
            )
            primary["record_kind"] = "source_discovery"
            primary["direct_probe"] = probe
            family = {
                "canonical_ref": (
                    f"PUBLICRECORDSOURCE:{PLATFORM_FAMILY}/tenant-directory"
                ),
                "source_id": self.tenant.source_id,
                "record_kind": "source_family_discovery",
                "platform_family": PLATFORM_FAMILY,
                "directory_url": HOST_URL + "/",
                "tenant_count": tenant_directory["tenant_count"],
                "case_search_tenant_count": (
                    tenant_directory["case_search_tenant_count"]
                ),
                "docket_tenant_count": tenant_directory["docket_tenant_count"],
                "tenants": tenant_directory["tenants"],
                "directory_claims": tenant_directory["directory_claims"],
                "source_snapshot": tenant_directory_page.snapshot(),
                "schema_fingerprint": tenant_directory["schema_fingerprint"],
            }
            alternatives = {
                "canonical_ref": (
                    f"PUBLICRECORDSOURCE:{self.tenant.source_id}/"
                    "official-alternatives"
                ),
                "source_id": self.tenant.source_id,
                "record_kind": "source_complement",
                "court": _court_payload(self.tenant),
                **_request_complement(self.tenant),
            }
            refs = (
                tenant_directory_page.url,
                *probe_refs,
            )
            return (primary, family, alternatives), tuple(dict.fromkeys(refs))

        tenant_directory_page = self._get(HOST_URL + "/")
        tenant_directory = parse_tenant_directory(tenant_directory_page)
        case_page = self._get(self.tenant.url("Cases"))
        case_soup = BeautifulSoup(case_page.text, "html.parser")
        options = _search_options(case_soup, case_page.url)
        docket_page = self.dockets()
        home_page = self._get(self.tenant.base_url)
        official_page = self._get(OFFICIAL_COURT_URL)
        official_links = _official_links(official_page)
        request_page = self._get(JUSTFOIA_MUNICIPAL_COURT_FORM_URL)

        primary = {
            "canonical_ref": canonical_court_ref(
                SOURCE_ID,
                COURT_ID,
                "eugene-tenant",
                "source_discovery",
            ),
            "source_id": SOURCE_ID,
            "record_kind": "source_discovery",
            "candidate_kind": "official_municipal_case_and_docket_tenant",
            "court": _court_payload(),
            "candidate_url": BASE_URL,
            "platform_family": PLATFORM_FAMILY,
            "tenant_slug": TENANT_SLUG,
            "official_referrer_chain": _official_chain(),
            "official_links_verified": official_links,
            "capabilities": {
                "case_search": {
                    "state": "found",
                    "url": CASES_URL,
                    "method": "GET",
                    "selectors": options,
                    "warrant_selector_available": ("WarrantNumber" in options),
                },
                "upcoming_dockets": {
                    "state": "found",
                    "url": DOCKETS_URL,
                    "native_session_count": len(docket_page.records),
                    "detail_route": f"/{TENANT_SLUG}/Dockets/Detail",
                    "underlying_cases": True,
                },
                "case_detail": {
                    "state": "found",
                    "route": f"/{TENANT_SLUG}/Cases/Detail",
                    "stable_selector": [
                        "citationNumber",
                        "violationNumber",
                    ],
                },
                "direct_documents": {
                    "state": "not_observed",
                },
                "bulk_products": {
                    "state": "not_observed",
                },
                "request_route": {
                    "state": "found",
                    **_request_complement(),
                },
            },
            "snapshots": {
                "tenant_home": home_page.snapshot(),
                "case_form": case_page.snapshot(),
                "dockets": docket_page.page.snapshot(),
                "official_city_page": official_page.snapshot(),
            },
        }
        family = {
            "canonical_ref": (f"PUBLICRECORDSOURCE:{PLATFORM_FAMILY}/tenant-directory"),
            "source_id": SOURCE_ID,
            "record_kind": "source_family_discovery",
            "platform_family": PLATFORM_FAMILY,
            "vendor": "Tyler Technologies",
            "directory_url": HOST_URL + "/",
            "tenant_count": tenant_directory["tenant_count"],
            "case_search_tenant_count": tenant_directory["case_search_tenant_count"],
            "docket_tenant_count": tenant_directory["docket_tenant_count"],
            "eugene_entry": tenant_directory["eugene"],
            "tenants": tenant_directory["tenants"],
            "directory_claims": tenant_directory["directory_claims"],
            "configured_oregon_tenants": [
                _tenant_configuration_record(
                    tenant,
                    directory_entry=next(
                        (
                            entry
                            for entry in tenant_directory["tenants"]
                            if entry["slug"] == tenant.slug
                        ),
                        None,
                    ),
                )
                for tenant in OREGON_TENANTS.values()
            ],
            "reusable_contract": {
                "tenant_root": "/{tenant}/",
                "case_form": "/{tenant}/Cases",
                "case_search": "/{tenant}/Cases/Search",
                "case_detail": "/{tenant}/Cases/Detail",
                "dockets": "/{tenant}/Dockets",
                "docket_detail": "/{tenant}/Dockets/Detail",
                "directory_links_are_capability_claims": True,
                "direct_component_verification_is_separate": True,
            },
            "source_snapshot": tenant_directory_page.snapshot(),
            "schema_fingerprint": tenant_directory["schema_fingerprint"],
        }
        complement = {
            "canonical_ref": (
                f"PUBLICRECORDSOURCE:{SOURCE_ID}/justfoia-municipal-court-request"
            ),
            "source_id": SOURCE_ID,
            "record_kind": "source_complement",
            "candidate_kind": "official_record_request_and_file_delivery",
            "court": _court_payload(),
            **_request_complement(),
            "archive_observation": {
                "archive_search_route": JUSTFOIA_ARCHIVE_URL,
                "live_default_result_count": 0,
            },
            "source_snapshot": request_page.snapshot(),
        }
        refs = (
            tenant_directory_page.url,
            home_page.url,
            case_page.url,
            docket_page.page.url,
            official_page.url,
            request_page.url,
        )
        return (primary, family, complement), refs


def _encode_cursor(state: CursorState) -> str:
    payload = canonical_json(
        {
            "operation": state.operation,
            "query_fingerprint": state.query_fingerprint,
            "snapshot_fingerprint": state.snapshot_fingerprint,
            "offset": state.offset,
            "anchor": state.anchor,
        }
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return CURSOR_PREFIX + encoded


def _decode_cursor(value: str | None) -> CursorState | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise EugeneCourtSelectionError(
            "invalid_cursor",
            "cursor does not belong to Eugene Municipal Record Search",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EugeneCourtSelectionError(
            "invalid_cursor",
            "Eugene continuation cursor is malformed",
        ) from error
    try:
        state = CursorState(
            operation=str(payload["operation"]),
            query_fingerprint=str(payload["query_fingerprint"]),
            snapshot_fingerprint=str(payload["snapshot_fingerprint"]),
            offset=int(payload["offset"]),
            anchor=str(payload["anchor"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EugeneCourtSelectionError(
            "invalid_cursor",
            "Eugene continuation cursor has invalid fields",
        ) from error
    if state.offset <= 0 or not state.anchor:
        raise EugeneCourtSelectionError(
            "invalid_cursor",
            "Eugene continuation cursor boundary is invalid",
        )
    return state


def _selection_fingerprint(
    operation: str,
    parameters: Mapping[str, Any],
) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "operation": operation,
                "parameters": dict(parameters),
            }
        ).encode("utf-8")
    ).hexdigest()


def _paginate(
    records: Sequence[dict[str, Any]],
    *,
    operation: str,
    parameters: Mapping[str, Any],
    limit: int,
    cursor_value: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    query_fingerprint = _selection_fingerprint(operation, parameters)
    snapshot_fingerprint = hashlib.sha256(
        canonical_json(list(records)).encode("utf-8")
    ).hexdigest()
    cursor = _decode_cursor(cursor_value)
    offset = 0
    if cursor is not None:
        if cursor.operation != operation:
            raise EugeneCourtSelectionError(
                "cursor_operation_mismatch",
                "cursor belongs to another Eugene operation",
            )
        if cursor.query_fingerprint != query_fingerprint:
            raise EugeneCourtSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to another Eugene query",
            )
        if cursor.snapshot_fingerprint != snapshot_fingerprint:
            raise EugeneCourtSelectionError(
                "cursor_snapshot_changed",
                "Eugene source results changed since the cursor was issued",
                status=ResultStatus.SOURCE_CHANGED,
            )
        offset = cursor.offset
        if offset > len(records):
            raise EugeneCourtSelectionError(
                "cursor_offset_out_of_range",
                "cursor is beyond the current Eugene result set",
            )
        previous = records[offset - 1] if offset else None
        if previous is None or previous.get("canonical_ref") != cursor.anchor:
            raise EugeneCourtSelectionError(
                "cursor_anchor_changed",
                "Eugene cursor boundary no longer matches the source",
                status=ResultStatus.SOURCE_CHANGED,
            )

    selected = list(records[offset : offset + limit])
    next_cursor = None
    next_offset = offset + len(selected)
    if next_offset < len(records) and selected:
        next_cursor = _encode_cursor(
            CursorState(
                operation=operation,
                query_fingerprint=query_fingerprint,
                snapshot_fingerprint=snapshot_fingerprint,
                offset=next_offset,
                anchor=str(selected[-1]["canonical_ref"]),
            )
        )
    return selected, next_cursor


def _search_spec(args: argparse.Namespace) -> SearchSpec:
    if args.last_name is not None:
        parameters = {
            "SearchByCriteria.LastName": _normalize_case_selector(
                args.last_name,
                "last name",
            )
        }
        optional = {
            "SearchByCriteria.FirstName": args.first_name,
            "SearchByCriteria.DateOfBirth": args.date_of_birth,
            "SearchByCriteria.DriversLicenseNumber": args.drivers_license,
        }
        for key, value in optional.items():
            if _text(value):
                parameters[key] = str(value).strip()
        if args.soundex:
            parameters["SearchByCriteria.UseSoundEX"] = "True"
        if args.partial:
            parameters["SearchByCriteria.UsePartialNames"] = "True"
        return SearchSpec("Name", parameters)
    if args.citation is not None:
        return SearchSpec(
            "CitationNumber",
            {
                "SearchByCriteria.CitationNumber": _normalize_case_selector(
                    args.citation,
                    "citation number",
                )
            },
        )
    if args.docket_number is not None:
        return SearchSpec(
            "DocketNumber",
            {
                "SearchByCriteria.DocketNumber": _normalize_case_selector(
                    args.docket_number,
                    "docket number",
                )
            },
        )
    if args.police_case_number is not None:
        return SearchSpec(
            "CaseNumber",
            {
                "SearchByCriteria.PDCaseNumber": _normalize_case_selector(
                    args.police_case_number,
                    "police case number",
                )
            },
        )
    if args.plate is not None:
        state = _text(args.plate_state)
        if state is None or not re.fullmatch(r"[A-Za-z]{2}", state):
            raise EugeneCourtSelectionError(
                "plate_state_required",
                "vehicle-plate searches require a two-letter --plate-state",
            )
        return SearchSpec(
            "VehiclePlate",
            {
                "SearchByCriteria.VehiclePlate": _normalize_case_selector(
                    args.plate,
                    "vehicle plate",
                ),
                "SearchByCriteria.VehicleState": state.upper(),
            },
        )
    if args.vin is not None:
        return SearchSpec(
            "VIN",
            {
                "SearchByCriteria.VIN": _normalize_case_selector(
                    args.vin,
                    "VIN",
                )
            },
        )
    raise EugeneCourtSelectionError(
        "selector_required",
        "one Eugene case-search selector is required",
    )


def _tenant_for_args(args: argparse.Namespace) -> MunicipalRecordSearchTenant:
    value = str(getattr(args, "tenant", "eugene"))
    tenant = OREGON_TENANTS.get(value) or TENANTS_BY_SLUG.get(value)
    if tenant is None:
        raise EugeneCourtSelectionError(
            "unknown_tenant",
            f"unknown Oregon Municipal Record Search tenant: {value}",
            details={
                "tenant": value,
                "available_tenants": sorted(OREGON_TENANTS),
            },
        )
    return tenant


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    tenant = _tenant_for_args(args)
    if args.command == "search":
        spec = _search_spec(args)
        return {
            "tenant_slug": tenant.slug,
            "search_by": spec.search_by,
            "criteria": dict(spec.parameters),
        }
    if args.command == "dockets":
        return {
            "tenant_slug": tenant.slug,
            "date_from": args.date_from,
            "date_to": args.date_to,
        }
    if args.command == "docket":
        return {
            "tenant_slug": tenant.slug,
            "date": args.native_date,
            "calendar_code": args.calendar_code,
            "room_code": args.room_code,
        }
    if args.command == "case":
        return {
            "tenant_slug": tenant.slug,
            "citation_number": args.citation_number,
            "violation_number": args.violation_number,
        }
    return {"tenant_slug": tenant.slug}


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    tenant = _tenant_for_args(args)
    component = {
        "search": "cases",
        "case": "cases",
        "dockets": "dockets",
        "docket": "dockets",
    }.get(args.command)
    configured_access = None
    if component == "cases":
        configured_access = tenant.case_access_state
    elif component == "dockets":
        configured_access = tenant.docket_access_state
    return PublicRecordsQuery(
        source=_source_metadata(tenant),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=tenant.jurisdiction_id,
            name=tenant.jurisdiction_name,
            state_code=tenant.state_code,
            county_fips=tenant.county_fips,
            locality=tenant.locality,
            metadata={
                "court_id": tenant.court_id,
                "court_type": tenant.court_type,
                "authority": tenant.authority,
            },
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={
                "access_decision": {
                    "mode": "direct_tenant_component",
                    "component": component,
                    "configured_observation": configured_access,
                }
            },
        ),
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: EugeneCourtSelectionError,
    *,
    tenant: MunicipalRecordSearchTenant = EUGENE_TENANT,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="query_selection",
                retryable=False,
                details=error.details,
            )
        ],
        warnings=_source_warnings(tenant),
    )


def _filter_dockets(
    records: Sequence[dict[str, Any]],
    *,
    date_from: str | None,
    date_to: str | None,
) -> list[dict[str, Any]]:
    lower = date.fromisoformat(date_from) if date_from else None
    upper = date.fromisoformat(date_to) if date_to else None
    if lower and upper and lower > upper:
        raise EugeneCourtSelectionError(
            "invalid_date_range",
            "--date-from must not be after --date-to",
        )
    selected = []
    for record in records:
        record_date = date.fromisoformat(str(record["date"]))
        if lower and record_date < lower:
            continue
        if upper and record_date > upper:
            continue
        selected.append(record)
    return selected


def _execute_command(
    args: argparse.Namespace,
    client: EugeneMunicipalCourtClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    tenant = _tenant_for_args(args)
    warnings = _source_warnings(tenant)
    if args.command == "search":
        spec = _search_spec(args)
        page = client.search(spec)
        parameters = {
            "tenant_slug": tenant.slug,
            "search_by": spec.search_by,
            "criteria": dict(spec.parameters),
        }
        selected, next_cursor = _paginate(
            page.records,
            operation="search",
            parameters=parameters,
            limit=args.limit,
            cursor_value=args.cursor,
        )
        return PublicRecordsResult.success(
            query,
            selected,
            next_cursor=next_cursor,
            raw_artifact_refs=(page.page.url,),
            warnings=warnings,
        )
    if args.command == "dockets":
        page = client.dockets()
        records = _filter_dockets(
            page.records,
            date_from=args.date_from,
            date_to=args.date_to,
        )
        parameters = {
            "tenant_slug": tenant.slug,
            "date_from": args.date_from,
            "date_to": args.date_to,
        }
        selected, next_cursor = _paginate(
            records,
            operation="dockets",
            parameters=parameters,
            limit=args.limit,
            cursor_value=args.cursor,
        )
        return PublicRecordsResult.success(
            query,
            selected,
            next_cursor=next_cursor,
            raw_artifact_refs=(page.page.url,),
            warnings=warnings,
        )
    if args.command == "docket":
        parsed = client.docket(
            native_date=args.native_date,
            calendar_code=args.calendar_code,
            room_code=args.room_code,
        )
        record = dict(parsed.record)
        cases = list(record["cases"])
        parameters = {
            "tenant_slug": tenant.slug,
            "date": args.native_date,
            "calendar_code": args.calendar_code,
            "room_code": args.room_code,
        }
        selected, next_cursor = _paginate(
            cases,
            operation="docket",
            parameters=parameters,
            limit=args.limit,
            cursor_value=args.cursor,
        )
        record["case_count_total"] = len(cases)
        record["case_count"] = len(selected)
        record["cases"] = selected
        return PublicRecordsResult.success(
            query,
            [record],
            next_cursor=next_cursor,
            raw_artifact_refs=(parsed.page.url,),
            warnings=warnings,
        )
    if args.command == "case":
        citation = _normalize_case_selector(
            args.citation_number,
            "citation number",
        )
        violation = _normalize_case_selector(
            args.violation_number,
            "violation number",
        )
        parsed = client.case(
            citation_number=citation,
            violation_number=violation,
        )
        refs = [parsed.page.url]
        refs.extend(
            value["url"]
            for value in parsed.record.get("documents", [])
            if value.get("url")
        )
        return PublicRecordsResult.success(
            query,
            [parsed.record],
            raw_artifact_refs=refs,
            warnings=warnings,
        )
    if args.command == "probe":
        record, refs = client.probe()
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=refs,
            warnings=warnings,
        )
    if args.command == "discovery":
        records, refs = client.discovery()
        return PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=refs,
            warnings=warnings,
        )
    if args.command == "tenants":
        records, refs = client.tenants()
        return PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=refs,
            warnings=warnings,
        )
    raise ValueError(f"unsupported Municipal Record Search command: {args.command}")


def _make_client(args: argparse.Namespace) -> EugeneMunicipalCourtClient:
    return EugeneMunicipalCourtClient(
        tenant=_tenant_for_args(args),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: EugeneMunicipalCourtClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one source-specific Oregon tenant operation."""

    tenant = _tenant_for_args(args)
    warnings = _source_warnings(tenant)
    try:
        query = build_query(args)
    except EugeneCourtSelectionError as error:
        query = PublicRecordsQuery(
            source=_source_metadata(tenant),
            jurisdiction=JurisdictionMetadata(
                jurisdiction_id=tenant.jurisdiction_id,
                name=tenant.jurisdiction_name,
                state_code=tenant.state_code,
                county_fips=tenant.county_fips,
                locality=tenant.locality,
            ),
            query=QueryMetadata(
                operation=args.command,
                parameters={"invalid_selection": True},
                requested_limit=getattr(args, "limit", None),
                cursor=getattr(args, "cursor", None),
            ),
        )
        result = _selection_failure(query, error, tenant=tenant)
        log_search(canonical_json(query.to_dict()), tenant.source_id, None)
        return result

    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except EugeneCourtSelectionError as error:
        result = _selection_failure(query, error, tenant=tenant)
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
            warnings=warnings,
        )
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
            warnings=warnings,
        )
    finally:
        if owns_client:
            source_client.close()
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), tenant.source_id, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    tenant = _tenant_for_args(args)
    label = (
        "Oregon Municipal Record Search"
        if args.command == "tenants"
        else tenant.court_name
    )
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(f"{label} {args.command} ({result.status.value})"),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"{label} {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


def _add_runtime_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tenant",
        choices=sorted({*OREGON_TENANTS, *TENANTS_BY_SLUG}),
        default="eugene",
        help=(
            "configured Oregon court key or exact Tyler tenant slug "
            "(default: eugene)"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
    )
    parser.add_argument(
        "--retry-backoff",
        type=_nonnegative_float,
        default=0.25,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query verified Oregon courts on Tyler Municipal Record Search"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search cases using one selector exposed by the selected tenant",
    )
    selectors = search.add_mutually_exclusive_group(required=True)
    selectors.add_argument("--last-name")
    selectors.add_argument("--citation")
    selectors.add_argument("--docket-number")
    selectors.add_argument("--police-case-number")
    selectors.add_argument("--plate")
    selectors.add_argument("--vin")
    search.add_argument("--first-name")
    search.add_argument("--date-of-birth")
    search.add_argument("--drivers-license")
    search.add_argument("--soundex", action="store_true")
    search.add_argument("--partial", action="store_true")
    search.add_argument("--plate-state")
    search.add_argument("--limit", type=_positive_int, default=100)
    search.add_argument("--cursor")
    _add_runtime_output(search)

    dockets = subparsers.add_parser(
        "dockets",
        help="List upcoming docket sessions for the selected tenant",
    )
    dockets.add_argument("--date-from", type=_iso_date)
    dockets.add_argument("--date-to", type=_iso_date)
    dockets.add_argument("--limit", type=_positive_int, default=100)
    dockets.add_argument("--cursor")
    _add_runtime_output(dockets)

    docket = subparsers.add_parser(
        "docket",
        help="Fetch underlying cases for one emitted docket session",
    )
    docket.add_argument("native_date", help="Source date in YYYYMMDDHHMMSS")
    docket.add_argument("calendar_code")
    docket.add_argument("room_code")
    docket.add_argument("--limit", type=_positive_int, default=100)
    docket.add_argument("--cursor")
    _add_runtime_output(docket)

    case = subparsers.add_parser(
        "case",
        help="Fetch one case by citation and violation number",
    )
    case.add_argument("citation_number")
    case.add_argument("violation_number")
    _add_runtime_output(case)

    probe = subparsers.add_parser(
        "probe",
        help="Directly verify case and docket component access",
    )
    _add_runtime_output(probe)

    discovery = subparsers.add_parser(
        "discovery",
        help="Describe the selected tenant, shared family, and alternatives",
    )
    _add_runtime_output(discovery)

    tenants = subparsers.add_parser(
        "tenants",
        help="Refresh the tenant directory and reconcile Oregon configurations",
    )
    _add_runtime_output(tenants)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
