#!/usr/bin/env python3
"""Query New Jersey DCA property registrations through the official portal.

The Department of Community Affairs (DCA) Service Portal publishes an
anonymous Power Pages OData search over Bureau of Housing Inspection (BHI)
building registrations. The search result is building-granular: a 10-digit
property registration can have multiple 13-digit building registrations.
This adapter preserves every building row and its property-interest link.

The current portal emits unusable OData ``nextLink`` values when ``$top`` is
set. This adapter instead uses the verified, ordered 13-digit building
registration field as a keyset cursor. County and municipality lookup GUIDs
are resolved from the current official search form rather than embedded as a
static mapping.

Examples:
    uv run python tools/query_new_jersey_dca_property.py registration 0714002653
    uv run python tools/query_new_jersey_dca_property.py parcel \
        --county Essex --block 441 --lot 61
    uv run python tools/query_new_jersey_dca_property.py address Broadway \
        --municipality "Newark City" --limit 20
    uv run python tools/query_new_jersey_dca_property.py lookups --county Essex
    uv run python tools/query_new_jersey_dca_property.py manifest
    uv run python tools/query_new_jersey_dca_property.py alternatives
    uv run python tools/query_new_jersey_dca_property.py probe
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Mapping, Sequence
from urllib.error import URLError

import requests

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
        HTTPTransport,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        UrllibTransport,
        failure_result,
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
    from public_records_http import (
        HTTPStatusError,
        HTTPTransport,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        UrllibTransport,
        failure_result,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-nj-dca-property-registration"
STATE_CODE = "NJ"
STATE_FIPS = "34"
PORTAL_BASE_URL = "https://serviceportal.dca.nj.gov"
SEARCH_PAGE_URL = (
    f"{PORTAL_BASE_URL}/ultra-bhi-home/ultra-bhi-propertysearch/"
)
ODATA_URL = f"{PORTAL_BASE_URL}/_odata/bhibuildings"
DETAIL_PATH = (
    "/ultra-bhi-home/ultra-bhi-propertysearch/"
    "ultra-bhi-propertyinterest/"
)
DETAIL_URL_TEMPLATE = f"{PORTAL_BASE_URL}{DETAIL_PATH}?pid={{property_id}}"
DCA_OPRA_URL = "https://www.nj.gov/dca/home/opra.shtml"
BHI_OFFICE_URL = (
    "https://www.nj.gov/dca/codes/offices/housinginspection.shtml"
)
BHI_OPRA_REPORT_URL = (
    "https://app.powerbigov.us/view?"
    "r=eyJrIjoiZmI2MzIxZDEtN2UwNi00M2VlLWJiZjgtNTMzMTExYjc3YzgyIiwidCI6"
    "IjUwNzZjM2QxLTM4MDItNGI5Zi1iMzZhLWUwYTQxYmQ2NDJhNyJ9"
)
NJGIN_URL = (
    "https://njogis-newjersey.opendata.arcgis.com/datasets/"
    "parcels-and-mod-iv-composite-of-nj/about"
)
SR1A_URL = "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml"
ASSESSOR_DIRECTORY_URL = (
    "https://www.nj.gov/treasury/taxation/pdf/lpt/"
    "assessor/statewidebycounty.pdf"
)
COUNTY_DIRECTORY_URL = "https://www.nj.gov/nj/gov/county/counties.shtml"
STATE_OPRA_URL = "https://www.nj.gov/opra/home/request-records.shtml"

PROBE_PROPERTY_REGISTRATION = "0714002653"
PROBE_BUILDING_REGISTRATION = "0714002653001"
PROBE_PROPERTY_INTEREST_ID = "db617ece-2483-4571-bf58-094fb4f14c49"

DEFAULT_PAGE_SIZE = 100
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
CURSOR_PREFIX = "nj-dca-property:v1:"
CURSOR_VERSION = 1

REQUIRED_ODATA_FIELDS = frozenset(
    {
        "ultra_buildingid",
        "ultra_bhibuildingregistrationnum",
        "ultra_propertyinterest",
        "ultra_county",
        "ultra_municipality",
        "ultra_addressline1",
        "ultra_block",
        "ultra_lot",
        "statuscode",
    }
)

COUNTY_FIPS_BY_NAME = {
    "ATLANTIC": "34001",
    "BERGEN": "34003",
    "BURLINGTON": "34005",
    "CAMDEN": "34007",
    "CAPE MAY": "34009",
    "CUMBERLAND": "34011",
    "ESSEX": "34013",
    "GLOUCESTER": "34015",
    "HUDSON": "34017",
    "HUNTERDON": "34019",
    "MERCER": "34021",
    "MIDDLESEX": "34023",
    "MONMOUTH": "34025",
    "MORRIS": "34027",
    "OCEAN": "34029",
    "PASSAIC": "34031",
    "SALEM": "34033",
    "SOMERSET": "34035",
    "SUSSEX": "34037",
    "UNION": "34039",
    "WARREN": "34041",
}

SOURCE_WARNINGS = (
    (
        "The OData index is building-granular. A 10-digit property "
        "registration can have multiple 13-digit building registrations; "
        "each source row is preserved."
    ),
    (
        "The registered-owner relationship is DCA regulatory-registration "
        "context and is not a substitute for county deed-title evidence."
    ),
    (
        "The portal is a live agency-managed index rather than an immutable "
        "release. Continuations use the verified building-registration "
        "keyset and preserve observed count drift."
    ),
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="New Jersey DCA Property Registration Search",
    source_role="property_registration_and_building_regulation_index",
    base_url=SEARCH_PAGE_URL,
    dataset_id="bhibuildings",
    metadata={
        "authority": "New Jersey Department of Community Affairs",
        "operator": "Bureau of Housing Inspection",
        "transport": "Power Pages OData v3",
        "result_granularity": "building_registration",
        "property_registration_digits": 10,
        "building_registration_digits": 13,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_FIPS,
    name="New Jersey",
    state_code=STATE_CODE,
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "normalization_version": 1,
        "required_source_fields": sorted(REQUIRED_ODATA_FIELDS),
        "identity": {
            "record": "ultra_bhibuildingregistrationnum",
            "property": "first 10 digits of building registration",
            "building_locator": "ultra_buildingid",
            "property_locator": "ultra_propertyinterest.Id",
        },
    }
)

OPERATION_ACCESS = {
    "search_registration": {
        "state": "anonymous_machine_readable",
        "method": "GET",
        "route": ODATA_URL,
        "selector": "partial property or building registration number",
        "returns": "building registration rows",
    },
    "search_block_lot_county": {
        "state": "anonymous_machine_readable",
        "method": "GET",
        "route": ODATA_URL,
        "selector": (
            "current county lookup ID with optional partial block and lot"
        ),
        "returns": "building registration rows",
    },
    "search_address_municipality": {
        "state": "anonymous_machine_readable",
        "method": "GET",
        "route": ODATA_URL,
        "selector": "partial primary/AKA address and optional municipality",
        "returns": "building registration rows",
    },
    "county_municipality_lookups": {
        "state": "anonymous_html",
        "method": "GET",
        "route": SEARCH_PAGE_URL,
        "returns": "current official county and municipality names and IDs",
    },
    "property_detail": {
        "state": "anonymous_html",
        "method": "GET",
        "route_template": DETAIL_URL_TEMPLATE,
        "returns": (
            "published property summary, owner/contact publication state, "
            "building, bill, judgment, and inspection sections"
        ),
        "implemented_by_this_adapter": False,
        "verification": {
            "state": "live_verified",
            "date": "2026-07-30",
            "sentinel_property_interest_id": PROBE_PROPERTY_INTEREST_ID,
            "observed": "anonymous official detail HTML returned",
        },
    },
    "detail_subgrids": {
        "state": "anonymous_browser_session_post",
        "method": "POST",
        "route": f"{PORTAL_BASE_URL}/_services/entity-subgrid-data.json/",
        "returns": "property-specific related rows",
        "implemented_by_this_adapter": False,
        "verification": {
            "state": "browser_transport_observed",
            "date": "2026-07-30",
            "observed": (
                "anonymous detail session issued property-related subgrid "
                "POST requests"
            ),
        },
    },
    "published_certificates_and_documents": {
        "state": "conditional_detail_interface",
        "discovery": "anonymous property detail page",
        "returns": (
            "certificate or document rows and links when the portal "
            "publishes them for a property"
        ),
        "implemented_by_this_adapter": False,
        "verification": {
            "state": "detail_interface_observed",
            "date": "2026-07-30",
            "observed": (
                "certificate and document sections are exposed by the "
                "property detail interface; no sentinel document download "
                "was asserted"
            ),
        },
    },
    "registration_and_change_requests": {
        "state": "interactive_portal_workflow",
        "operations": [
            "register new property",
            "transfer ownership",
            "update contact information",
            "appeal/request hearing",
            "request extension",
        ],
        "implemented_by_this_adapter": False,
    },
}

SOURCE_MANIFEST = {
    "record_type": "source_manifest",
    "source_id": SOURCE_ID,
    "name": SOURCE_METADATA.name,
    "authority": "New Jersey Department of Community Affairs",
    "operator": "Bureau of Housing Inspection",
    "official_search_url": SEARCH_PAGE_URL,
    "machine_endpoint": ODATA_URL,
    "record_identity": {
        "building_registration_number": (
            "13-digit ultra_bhibuildingregistrationnum; source record key"
        ),
        "property_registration_number": (
            "first 10 digits displayed by the official portal"
        ),
        "building_id": "Power Pages building locator GUID",
        "property_interest_id": "Power Pages property-detail locator GUID",
    },
    "operation_access": OPERATION_ACCESS,
    "pagination": {
        "strategy": "building-registration keyset",
        "ordering": "ultra_bhibuildingregistrationnum asc",
        "native_next_link": (
            "not followed; live probe emitted negative $top and skip 100000"
        ),
        "cursor_snapshot": "live mutable index with observed count retained",
    },
    "source_semantics": {
        "result_granularity": "one row per building registration",
        "portal_display_granularity": "one row per property interest",
        "registered_owner_role": "DCA regulatory-registration relationship",
        "redaction": (
            "property detail page preserves the portal's published/masked "
            "state, including its Daniel's Law notice"
        ),
    },
}

ALTERNATIVE_ROUTES = (
    {
        "record_type": "alternative_route",
        "source_id": "us-nj-dca-bhi-active-buildings-opra",
        "name": "BHI Active Building database for OPRA",
        "authority": (
            "New Jersey Department of Community Affairs, "
            "Bureau of Housing Inspection"
        ),
        "url": BHI_OPRA_REPORT_URL,
        "official_landing_url": BHI_OFFICE_URL,
        "access": (
            "anonymous official Power BI publish-to-web report; public "
            "report metadata and schema transport verified"
        ),
        "filters": [
            "county",
            "municipality",
            "property interest type",
            "ownership type",
            "property address text",
        ],
        "join_fields": [
            "BHI registration number",
            "county",
            "municipality",
            "address",
            "block",
            "lot",
        ],
        "adds": [
            "property and building status",
            "primary owner name, address, and phone when published",
            "authorized agent name, address, and phone when published",
            "last cyclical inspection date",
            "building units and stories",
            "construction month/year and classification",
        ],
        "coverage": (
            "report queries active buildings with a BHI registration and "
            "excludes rows whose contact is marked redacted"
        ),
        "verification": {
            "state": "official_link_and_public_schema_verified",
            "date": "2026-07-30",
            "report_model": "BHI - Active Building for OPRA",
        },
        "gap_relative_to_dca": (
            "the active-building OPRA view adds report fields but does not "
            "replace inactive, redacted, historical, violation, or "
            "document-level portal and request routes"
        ),
    },
    {
        "record_type": "alternative_route",
        "source_id": "us-nj-njgin-parcels-modiv",
        "name": "NJGIN Parcels and MOD-IV Composite",
        "authority": "New Jersey Office of GIS",
        "url": NJGIN_URL,
        "access": "anonymous ArcGIS and bulk downloads",
        "join_fields": ["county", "municipality", "block", "lot", "address"],
        "adds": [
            "parcel geometry",
            "PAMS PIN and GIS identifiers",
            "assessment attributes",
            "last-sale references",
        ],
        "gap_relative_to_dca": (
            "does not replace BHI registration, building, inspection, or "
            "regulatory-status records"
        ),
    },
    {
        "record_type": "alternative_route",
        "source_id": "us-nj-treasury-sr1a-sales",
        "name": "New Jersey Treasury SR1A property sales",
        "authority": "New Jersey Division of Taxation",
        "url": SR1A_URL,
        "access": "anonymous official bulk releases",
        "join_fields": ["municipality", "block", "lot", "address"],
        "adds": [
            "grantor and grantee",
            "sale date and consideration",
            "deed book/page",
            "assessment at transfer",
        ],
        "gap_relative_to_dca": (
            "transfer observations do not establish current BHI registration "
            "or current deed ownership"
        ),
    },
    {
        "record_type": "alternative_route",
        "source_id": "us-nj-county-clerks-registers",
        "name": "New Jersey county clerks and registers",
        "authority": "County clerk or register for the property county",
        "url": COUNTY_DIRECTORY_URL,
        "access": "county-specific search, copy, and image routes",
        "join_fields": [
            "county",
            "municipality",
            "block",
            "lot",
            "party",
            "book/page",
        ],
        "adds": [
            "deeds",
            "mortgages",
            "releases and assignments",
            "recorded liens",
            "legal descriptions",
        ],
        "gap_relative_to_dca": (
            "county systems vary and do not replace DCA inspection or "
            "registration status"
        ),
    },
    {
        "record_type": "alternative_route",
        "source_id": "us-nj-local-assessors-tax-boards",
        "name": "Municipal assessors and county boards of taxation",
        "authority": "New Jersey Division of Taxation and local offices",
        "url": ASSESSOR_DIRECTORY_URL,
        "access": "official directory to local published and request routes",
        "join_fields": ["county", "municipality", "block", "lot", "address"],
        "adds": [
            "property record cards",
            "certified tax-list detail",
            "assessment and exemption context",
            "local appeal records",
        ],
        "gap_relative_to_dca": (
            "local coverage varies and does not replace BHI regulatory records"
        ),
    },
    {
        "record_type": "alternative_route",
        "source_id": "us-nj-opra-property-records",
        "name": "DCA and statewide OPRA record-request routes",
        "authority": "New Jersey DCA or the relevant public custodian",
        "url": DCA_OPRA_URL,
        "statewide_url": STATE_OPRA_URL,
        "access": "record-specific public-record request",
        "join_fields": [
            "property registration number",
            "address",
            "record series",
            "date range",
        ],
        "adds": [
            "defined unpublished registration records",
            "inspection or violation records not linked online",
            "agency-held record copies",
        ],
        "gap_relative_to_dca": (
            "request response and available record series are "
            "custodian-specific"
        ),
    },
)


class DCASelectionError(RuntimeError):
    """Invalid source-specific selector with structured result semantics."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="query_selection",
            retryable=False,
        )


@dataclass(frozen=True)
class LookupOption:
    option_id: str
    name: str
    county_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.option_id,
            "name": self.name,
            "county_id": self.county_id,
        }


@dataclass(frozen=True)
class LookupCatalog:
    counties: tuple[LookupOption, ...]
    municipalities: tuple[LookupOption, ...]
    fingerprint: str

    def resolve_county(self, value: str) -> LookupOption:
        return _resolve_lookup(
            value,
            self.counties,
            label="county",
            strip_suffix="county",
        )

    def resolve_municipality(self, value: str) -> LookupOption:
        return _resolve_lookup(value, self.municipalities, label="municipality")


@dataclass(frozen=True)
class SearchCriteria:
    mode: str
    registration: str | None = None
    block: str | None = None
    lot: str | None = None
    county_name: str | None = None
    county_id: str | None = None
    address: str | None = None
    municipality_name: str | None = None
    municipality_id: str | None = None
    lookup_fingerprint: str | None = None

    @property
    def fingerprint(self) -> str:
        payload = self.to_dict()
        payload.pop("lookup_fingerprint", None)
        return sha256_fingerprint(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "registration": self.registration,
            "block": self.block,
            "lot": self.lot,
            "county_name": self.county_name,
            "county_id": self.county_id,
            "address": self.address,
            "municipality_name": self.municipality_name,
            "municipality_id": self.municipality_id,
            "lookup_fingerprint": self.lookup_fingerprint,
        }


@dataclass(frozen=True)
class CursorState:
    criteria_fingerprint: str
    last_building_registration: str
    emitted_count: int
    observed_total: int


@dataclass(frozen=True)
class ODataPage:
    records: tuple[Mapping[str, Any], ...]
    remaining_count: int
    native_next_link: str | None
    response_field_fingerprint: str


@dataclass(frozen=True)
class SearchFetch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    observed_total: int
    emitted_count: int
    pages_fetched: int
    response_field_fingerprint: str
    count_drift: Mapping[str, int] | None = None
    capped: bool = False


class _LookupHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_select: str | None = None
        self.current_option_id: str | None = None
        self.current_option_text: list[str] = []
        self.counties: list[tuple[str, str]] = []
        self.municipalities: list[tuple[str, str]] = []
        self.municipality_counties: dict[str, str] = {}

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key: value for key, value in attrs}
        if tag == "select" and values.get("id") in {
            "ultra_county",
            "ultra_municipality",
        }:
            self.current_select = values["id"]
            return
        if tag == "option" and self.current_select:
            self.current_option_id = values.get("value") or ""
            self.current_option_text = []
            return
        if (
            tag == "input"
            and values.get("type", "").casefold() == "hidden"
            and _is_guid(values.get("id"))
            and _is_guid(values.get("value"))
        ):
            self.municipality_counties[str(values["id"]).casefold()] = str(
                values["value"]
            ).casefold()

    def handle_data(self, data: str) -> None:
        if self.current_option_id is not None:
            self.current_option_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self.current_option_id is not None:
            name = _clean_text("".join(self.current_option_text))
            if self.current_option_id and name:
                target = (
                    self.counties
                    if self.current_select == "ultra_county"
                    else self.municipalities
                )
                target.append((self.current_option_id.casefold(), name))
            self.current_option_id = None
            self.current_option_text = []
            return
        if tag == "select":
            self.current_select = None


class DCAPropertyClient:
    """Bounded anonymous client for the official DCA portal routes."""

    def __init__(
        self,
        *,
        transport: HTTPTransport | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if minimum_interval < 0:
            raise ValueError("minimum_interval must not be negative")
        self.transport = transport or UrllibTransport()
        self.page_size = page_size
        self.timeout = timeout
        self.retry_policy = RetryPolicy(max_attempts=retry_attempts)
        self._rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self._sleeper = time.sleep
        self.request_count = 0

    def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        accept: str,
    ) -> Any:
        headers = {
            "Accept": accept,
            "User-Agent": "Ithildin-Public-Records/1.0",
            "Referer": SEARCH_PAGE_URL,
            "X-Requested-With": "XMLHttpRequest",
        }
        transient_errors = (
            TimeoutError,
            ConnectionError,
            URLError,
            requests.RequestException,
        )
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.transport.request(
                    "GET",
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
            except transient_errors as error:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise TransportError(
                    f"DCA portal request failed after {attempt} attempts: {error}",
                    url=url,
                    details={"attempts": attempt},
                ) from error

            status_code = int(getattr(response, "status_code", 0))
            response_text = str(getattr(response, "text", ""))
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                if status_code == 429:
                    raise RateLimitedHTTPError(
                        status_code,
                        url=url,
                        response_text=response_text,
                    )
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            if status_code == 451:
                raise TermsBlockedHTTPError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            if status_code in {404, 410}:
                raise SourceChangedHTTPError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            return response
        raise AssertionError("bounded retry loop exited unexpectedly")

    def fetch_lookup_catalog(self) -> LookupCatalog:
        response = self._request(SEARCH_PAGE_URL, accept="text/html")
        return parse_lookup_html(str(response.text))

    def fetch_page(
        self,
        criteria: SearchCriteria,
        *,
        last_building_registration: str | None,
        top: int,
    ) -> ODataPage:
        filter_value = build_odata_filter(
            criteria,
            last_building_registration=last_building_registration,
        )
        response = self._request(
            ODATA_URL,
            params={
                "$inlinecount": "allpages",
                "$filter": filter_value,
                "$orderby": "ultra_bhibuildingregistrationnum asc",
                "$top": top,
            },
            accept="application/json",
        )
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SourceSchemaError(
                "DCA OData route returned invalid JSON",
                url=ODATA_URL,
                details={"response_text": str(response.text)[:500]},
            ) from error
        return parse_odata_page(payload)

    def search(
        self,
        criteria: SearchCriteria,
        *,
        requested_limit: int | None,
        max_records: int | None,
        cursor: str | None,
    ) -> SearchFetch:
        if requested_limit is not None and requested_limit <= 0:
            raise ValueError("requested_limit must be positive")
        if max_records is not None and max_records <= 0:
            raise ValueError("max_records must be positive")

        state = decode_cursor(cursor, criteria) if cursor else None
        last_key = state.last_building_registration if state else None
        prior_emitted = state.emitted_count if state else 0
        prior_total = state.observed_total if state else None

        effective_limit = requested_limit
        cap_applied = False
        if max_records is not None and (
            effective_limit is None or max_records < effective_limit
        ):
            effective_limit = max_records
            cap_applied = True

        records: list[Mapping[str, Any]] = []
        pages_fetched = 0
        page_response_fingerprints: set[str] = set()
        current_total = prior_total or 0
        count_drift: dict[str, int] | None = None
        source_remaining = 0

        while True:
            remaining_limit = (
                None
                if effective_limit is None
                else effective_limit - len(records)
            )
            if remaining_limit is not None and remaining_limit <= 0:
                break
            top = (
                self.page_size
                if remaining_limit is None
                else min(self.page_size, remaining_limit)
            )
            page = self.fetch_page(
                criteria,
                last_building_registration=last_key,
                top=top,
            )
            pages_fetched += 1
            page_response_fingerprints.add(page.response_field_fingerprint)
            estimated_total = prior_emitted + len(records) + page.remaining_count
            if current_total == 0:
                current_total = estimated_total
            elif estimated_total != current_total:
                if count_drift is None:
                    count_drift = {
                        "initial_observed_total": current_total,
                        "latest_observed_total": estimated_total,
                        "changes": 1,
                    }
                else:
                    count_drift["latest_observed_total"] = estimated_total
                    count_drift["changes"] += 1
                current_total = estimated_total

            page_records = list(page.records)
            _validate_ordered_page(page_records, after=last_key)
            if not page_records:
                source_remaining = page.remaining_count
                if source_remaining:
                    raise SourceSchemaError(
                        "DCA keyset page returned no rows while count remained",
                        url=ODATA_URL,
                        details={
                            "remaining_count": source_remaining,
                            "last_key": last_key,
                        },
                    )
                break

            records.extend(page_records)
            last_key = _required_text(
                page_records[-1].get("ultra_bhibuildingregistrationnum"),
                "ultra_bhibuildingregistrationnum",
            )
            source_remaining = page.remaining_count - len(page_records)
            if source_remaining <= 0:
                source_remaining = 0
                break
            if len(page_records) < top:
                raise SourceSchemaError(
                    "DCA keyset page stopped before the advertised count",
                    url=ODATA_URL,
                    details={
                        "returned": len(page_records),
                        "requested_top": top,
                        "remaining_count": page.remaining_count,
                    },
                )

        emitted_count = prior_emitted + len(records)
        next_cursor = None
        if source_remaining > 0 and last_key:
            next_cursor = encode_cursor(
                CursorState(
                    criteria_fingerprint=criteria.fingerprint,
                    last_building_registration=last_key,
                    emitted_count=emitted_count,
                    observed_total=current_total,
                )
            )
        return SearchFetch(
            records=tuple(records),
            next_cursor=next_cursor,
            observed_total=current_total,
            emitted_count=emitted_count,
            pages_fetched=pages_fetched,
            response_field_fingerprint=sha256_fingerprint(
                {
                    "page_response_field_fingerprints": sorted(
                        page_response_fingerprints
                    )
                }
            ),
            count_drift=count_drift,
            capped=bool(cap_applied and next_cursor),
        )


def _clean_text(value: Any) -> str | None:
    text = " ".join(str(value or "").replace("\x00", "").split()).strip()
    return text or None


def _required_text(value: Any, field_name: str) -> str:
    text = _clean_text(value)
    if not text:
        raise ValueError(f"DCA source row lacks {field_name}")
    return text


def _is_guid(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            value,
        )
    )


def _normalized_lookup_name(value: str, *, strip_suffix: str | None = None) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    if strip_suffix and normalized.endswith(f" {strip_suffix}"):
        normalized = normalized[: -(len(strip_suffix) + 1)].strip()
    return normalized


def _resolve_lookup(
    value: str,
    options: Sequence[LookupOption],
    *,
    label: str,
    strip_suffix: str | None = None,
) -> LookupOption:
    raw = _required_text(value, label)
    if _is_guid(raw):
        matches = [
            option
            for option in options
            if option.option_id.casefold() == raw.casefold()
        ]
    else:
        target = _normalized_lookup_name(raw, strip_suffix=strip_suffix)
        matches = [
            option
            for option in options
            if _normalized_lookup_name(
                option.name,
                strip_suffix=strip_suffix,
            )
            == target
        ]
    if not matches:
        raise DCASelectionError(
            f"unknown_{label}",
            f"Unknown DCA {label}: {raw!r}; use the lookups command",
        )
    if len(matches) > 1:
        raise DCASelectionError(
            f"ambiguous_{label}",
            f"Ambiguous DCA {label}: {raw!r}",
        )
    return matches[0]


def parse_lookup_html(
    source: str,
    *,
    require_complete: bool = True,
) -> LookupCatalog:
    parser = _LookupHTMLParser()
    parser.feed(source)
    counties = tuple(
        LookupOption(option_id=option_id, name=name)
        for option_id, name in parser.counties
    )
    municipalities = tuple(
        LookupOption(
            option_id=option_id,
            name=name,
            county_id=parser.municipality_counties.get(option_id),
        )
        for option_id, name in parser.municipalities
    )
    if not counties:
        raise SourceSchemaError(
            "DCA search form lacks county lookup options",
            url=SEARCH_PAGE_URL,
            details={"observed_count": len(counties)},
        )
    if not municipalities:
        raise SourceSchemaError(
            "DCA search form lacks municipality lookup options",
            url=SEARCH_PAGE_URL,
            details={"observed_count": len(municipalities)},
        )
    missing_county_links = [
        item.option_id for item in municipalities if not item.county_id
    ]
    if missing_county_links:
        raise SourceSchemaError(
            "DCA municipality-to-county lookup mapping is incomplete",
            url=SEARCH_PAGE_URL,
            details={
                "missing_count": len(missing_county_links),
                "sample_ids": missing_county_links[:5],
            },
        )
    county_ids = {item.option_id for item in counties}
    unknown_county_links = [
        {
            "municipality_id": item.option_id,
            "county_id": item.county_id,
        }
        for item in municipalities
        if item.county_id not in county_ids
    ]
    if unknown_county_links:
        raise SourceSchemaError(
            "DCA municipality lookup references an unknown county",
            url=SEARCH_PAGE_URL,
            details={
                "unknown_count": len(unknown_county_links),
                "sample": unknown_county_links[:5],
            },
        )
    if require_complete and (
        len(counties) != 21 or len(municipalities) < 560
    ):
        raise SourceSchemaError(
            "DCA search-form lookup coverage changed",
            url=SEARCH_PAGE_URL,
            details={
                "observed_counties": len(counties),
                "expected_counties": 21,
                "observed_municipalities": len(municipalities),
                "minimum_municipalities": 560,
            },
        )
    fingerprint = sha256_fingerprint(
        {
            "counties": [item.to_dict() for item in counties],
            "municipalities": [item.to_dict() for item in municipalities],
        }
    )
    return LookupCatalog(
        counties=counties,
        municipalities=municipalities,
        fingerprint=fingerprint,
    )


def _odata_literal(value: str, field_name: str) -> str:
    text = _required_text(value, field_name)
    return text.replace("'", "''")


def _registration_value(value: str) -> str:
    text = _required_text(value, "registration").replace("-", "0")
    if not text.isdigit():
        raise DCASelectionError(
            "invalid_registration",
            "DCA registration selectors must contain digits or source dashes",
        )
    return text


def build_odata_filter(
    criteria: SearchCriteria,
    *,
    last_building_registration: str | None = None,
) -> str:
    if criteria.mode == "registration":
        value = _odata_literal(
            _required_text(criteria.registration, "registration"),
            "registration",
        )
        base_filter = (
            f"substringof('{value}', ultra_bhibuildingregistrationnum)"
        )
    elif criteria.mode == "parcel":
        predicates = ["ultra_bhibuildingregistrationnum ne null"]
        if criteria.block:
            block = _odata_literal(criteria.block, "block")
            predicates.append(f"substringof('{block}', ultra_block)")
        if criteria.lot:
            lot = _odata_literal(criteria.lot, "lot")
            predicates.append(f"substringof('{lot}', ultra_lot)")
        if not criteria.county_id or not _is_guid(criteria.county_id):
            raise DCASelectionError(
                "county_required",
                "DCA block/lot searches require a resolved county",
            )
        predicates.append(
            f"ultra_county/Id eq guid'{criteria.county_id.casefold()}'"
        )
        base_filter = " and ".join(predicates)
    elif criteria.mode == "address":
        predicates = ["ultra_bhibuildingregistrationnum ne null"]
        if criteria.address:
            address = _odata_literal(criteria.address, "address")
            address_fields = (
                "ultra_addressline1",
                "ultra_akaaddress1",
                "ultra_akaaddress2",
                "ultra_akaaddress3",
                "ultra_akaaddress4",
            )
            predicates.append(
                "("
                + " or ".join(
                    f"substringof('{address}', {field})"
                    for field in address_fields
                )
                + ")"
            )
        if criteria.municipality_id:
            if not _is_guid(criteria.municipality_id):
                raise DCASelectionError(
                    "invalid_municipality_id",
                    "DCA municipality ID must be a GUID",
                )
            predicates.append(
                "ultra_municipality/Id eq "
                f"guid'{criteria.municipality_id.casefold()}'"
            )
        base_filter = " and ".join(predicates)
    else:
        raise DCASelectionError(
            "unsupported_operation",
            f"Unsupported DCA search mode: {criteria.mode}",
        )

    if last_building_registration:
        last_value = _odata_literal(
            last_building_registration,
            "cursor building registration",
        )
        return (
            f"({base_filter}) and "
            f"ultra_bhibuildingregistrationnum gt '{last_value}'"
        )
    return base_filter


def parse_odata_page(payload: Any) -> ODataPage:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "DCA OData response must be a JSON object",
            url=ODATA_URL,
        )
    records_value = payload.get("value")
    if not isinstance(records_value, list):
        raise SourceSchemaError(
            "DCA OData response lacks a value array",
            url=ODATA_URL,
        )
    records: list[Mapping[str, Any]] = []
    field_names: set[str] = set()
    for index, record in enumerate(records_value):
        if not isinstance(record, Mapping):
            raise SourceSchemaError(
                "DCA OData value entry must be an object",
                url=ODATA_URL,
                details={"index": index},
            )
        missing = sorted(REQUIRED_ODATA_FIELDS - set(record))
        if missing:
            raise SourceSchemaError(
                "DCA OData building schema changed",
                url=ODATA_URL,
                details={"index": index, "missing_fields": missing},
            )
        records.append(dict(record))
        field_names.update(str(key) for key in record)
    raw_count = payload.get("odata.count")
    try:
        remaining_count = int(str(raw_count))
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "DCA OData response lacks a valid odata.count",
            url=ODATA_URL,
            details={"observed_value": raw_count},
        ) from error
    if remaining_count < len(records):
        raise SourceSchemaError(
            "DCA OData count is smaller than the returned page",
            url=ODATA_URL,
            details={
                "count": remaining_count,
                "returned": len(records),
            },
        )
    native_next = payload.get("odata.nextLink")
    return ODataPage(
        records=tuple(records),
        remaining_count=remaining_count,
        native_next_link=(
            str(native_next) if isinstance(native_next, str) else None
        ),
        response_field_fingerprint=sha256_fingerprint(
            {"fields": sorted(field_names)}
        ),
    )


def _validate_ordered_page(
    records: Sequence[Mapping[str, Any]],
    *,
    after: str | None,
) -> None:
    values = [
        _required_text(
            record.get("ultra_bhibuildingregistrationnum"),
            "ultra_bhibuildingregistrationnum",
        )
        for record in records
    ]
    if any(not value.isdigit() or len(value) != 13 for value in values):
        raise SourceSchemaError(
            "DCA building registration identity contract changed",
            url=ODATA_URL,
            details={"observed_values": values[:5]},
        )
    if values != sorted(values) or len(values) != len(set(values)):
        raise SourceSchemaError(
            "DCA keyset page is not strictly ordered by building registration",
            url=ODATA_URL,
            details={"observed_values": values[:10]},
        )
    if after and values and values[0] <= after:
        raise SourceSchemaError(
            "DCA keyset continuation did not advance",
            url=ODATA_URL,
            details={"cursor_key": after, "first_value": values[0]},
        )


def encode_cursor(state: CursorState) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "criteria_fingerprint": state.criteria_fingerprint,
        "last_building_registration": state.last_building_registration,
        "emitted_count": state.emitted_count,
        "observed_total": state.observed_total,
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
    }
    token = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return f"{CURSOR_PREFIX}{token.rstrip('=')}"


def decode_cursor(cursor: str, criteria: SearchCriteria) -> CursorState:
    if not cursor.startswith(CURSOR_PREFIX):
        raise DCASelectionError("invalid_cursor", "Invalid DCA cursor prefix")
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(token + padding).decode("utf-8")
        )
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise DCASelectionError(
            "invalid_cursor",
            "Invalid DCA cursor payload",
        ) from error
    if not isinstance(payload, Mapping):
        raise DCASelectionError(
            "invalid_cursor",
            "Invalid DCA cursor payload",
        )
    if payload.get("version") != CURSOR_VERSION:
        raise DCASelectionError(
            "invalid_cursor",
            "Unsupported DCA cursor version",
        )
    if payload.get("adapter_schema_fingerprint") != ADAPTER_SCHEMA_FINGERPRINT:
        raise DCASelectionError(
            "cursor_adapter_changed",
            "DCA cursor was created by a different adapter schema",
        )
    if payload.get("criteria_fingerprint") != criteria.fingerprint:
        raise DCASelectionError(
            "cursor_criteria_mismatch",
            "DCA cursor does not match the current search criteria",
        )
    last_key = payload.get("last_building_registration")
    if not isinstance(last_key, str) or not re.fullmatch(r"\d{13}", last_key):
        raise DCASelectionError(
            "invalid_cursor",
            "DCA cursor building registration is invalid",
        )
    emitted = payload.get("emitted_count")
    observed_total = payload.get("observed_total")
    if (
        isinstance(emitted, bool)
        or not isinstance(emitted, int)
        or emitted < 0
        or isinstance(observed_total, bool)
        or not isinstance(observed_total, int)
        or observed_total < emitted
    ):
        raise DCASelectionError(
            "invalid_cursor",
            "DCA cursor counts are invalid",
        )
    return CursorState(
        criteria_fingerprint=criteria.fingerprint,
        last_building_registration=last_key,
        emitted_count=emitted,
        observed_total=observed_total,
    )


def _lookup_value(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, Mapping):
        return None, None
    option_id = _clean_text(value.get("Id"))
    name = _clean_text(value.get("Name"))
    return option_id, name


def _status_value(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        "name": _clean_text(value.get("Name")),
        "value": value.get("Value"),
    }


def normalize_building(
    source: Mapping[str, Any],
    *,
    fetch: SearchFetch,
) -> dict[str, Any]:
    building_registration = _required_text(
        source.get("ultra_bhibuildingregistrationnum"),
        "ultra_bhibuildingregistrationnum",
    )
    if len(building_registration) != 13 or not building_registration.isdigit():
        raise ValueError(
            "DCA building registration must be a 13-digit source key"
        )
    property_registration = building_registration[:10]
    building_id = _required_text(
        source.get("ultra_buildingid"),
        "ultra_buildingid",
    )
    property_id, property_name = _lookup_value(
        source.get("ultra_propertyinterest")
    )
    county_id, county_name = _lookup_value(source.get("ultra_county"))
    municipality_id, municipality_name = _lookup_value(
        source.get("ultra_municipality")
    )
    owner_id, owner_name = _lookup_value(
        source.get("ultra_propertyinterest-ultra_propertyowner")
    )
    county_fips = (
        COUNTY_FIPS_BY_NAME.get(county_name.upper()) if county_name else None
    )
    detail_url = (
        DETAIL_URL_TEMPLATE.format(property_id=property_id)
        if property_id
        else None
    )
    return {
        "record_type": "property_registration_building",
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            STATE_FIPS,
            "building-registration",
            building_registration,
        ),
        "source_id": SOURCE_ID,
        "dataset_id": SOURCE_METADATA.dataset_id,
        "building_registration_number": building_registration,
        "property_registration_number": property_registration,
        "building_id": building_id,
        "property_interest_id": property_id,
        "property_name": property_name,
        "building_name": _clean_text(source.get("ultra_name")),
        "building_address": {
            "line1": _clean_text(source.get("ultra_addressline1")),
            "postal_code": _clean_text(source.get("ultra_zipcode")),
            "aka": [
                text
                for text in (
                    _clean_text(source.get("ultra_akaaddress1")),
                    _clean_text(source.get("ultra_akaaddress2")),
                    _clean_text(source.get("ultra_akaaddress3")),
                    _clean_text(source.get("ultra_akaaddress4")),
                )
                if text
            ],
        },
        "parcel_coordinates": {
            "county": county_name,
            "county_fips": county_fips,
            "county_id": county_id,
            "municipality": municipality_name,
            "municipality_id": municipality_id,
            "block": _clean_text(source.get("ultra_block")),
            "lot": _clean_text(source.get("ultra_lot")),
        },
        "building_registration_status": _status_value(
            source.get("statuscode")
        ),
        "property_registration_status": _status_value(
            source.get("ultra_propertyinterest-statuscode")
        ),
        "registered_owner": (
            {
                "id": owner_id,
                "name": owner_name,
                "role": "DCA property-registration owner relationship",
            }
            if owner_id or owner_name
            else None
        ),
        "registered_owner_publication_state": (
            "published_in_search_index"
            if owner_id or owner_name
            else "not_returned_in_search_index"
        ),
        "detail_url": detail_url,
        "source_match_context": {
            "observed_total_building_rows": fetch.observed_total,
            "emitted_through_this_page": fetch.emitted_count,
            "pages_fetched_this_request": fetch.pages_fetched,
            "count_drift": fetch.count_drift,
        },
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "response_field_fingerprint": fetch.response_field_fingerprint,
        "raw_source": dict(source),
    }


def source_manifest_record() -> dict[str, Any]:
    """Return the source and operation manifest without network access."""
    return json.loads(canonical_json(SOURCE_MANIFEST))


def alternative_route_records() -> list[dict[str, Any]]:
    """Return complementary official routes without network access."""
    return json.loads(canonical_json(ALTERNATIVE_ROUTES))


def _raw_query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "registration": getattr(args, "registration", None),
        "block": getattr(args, "block", None),
        "lot": getattr(args, "lot", None),
        "county": getattr(args, "county", None),
        "address": getattr(args, "address", None),
        "municipality": getattr(args, "municipality", None),
        "county_filter": getattr(args, "county_filter", None),
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    operation = str(args.command)
    limit = getattr(args, "limit", None)
    if operation == "probe":
        limit = 1
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=_raw_query_parameters(args),
            requested_limit=limit,
            cursor=getattr(args, "cursor", None),
            metadata={
                "result_granularity": "building_registration",
                "pagination": "building_registration_keyset",
            },
        ),
    )


def _criteria_from_args(
    args: argparse.Namespace,
    client: DCAPropertyClient,
) -> SearchCriteria:
    command = args.command
    if command == "probe":
        return SearchCriteria(
            mode="registration",
            registration=PROBE_BUILDING_REGISTRATION,
        )
    if command == "registration":
        return SearchCriteria(
            mode="registration",
            registration=_registration_value(args.registration),
        )
    if command == "parcel":
        catalog = client.fetch_lookup_catalog()
        county = catalog.resolve_county(args.county)
        return SearchCriteria(
            mode="parcel",
            block=_clean_text(args.block),
            lot=_clean_text(args.lot),
            county_name=county.name,
            county_id=county.option_id,
            lookup_fingerprint=catalog.fingerprint,
        )
    if command == "address":
        address = _required_text(args.address, "address")
        if len(address) < 3:
            raise DCASelectionError(
                "address_too_short",
                "DCA address search requires at least three characters",
            )
        municipality_name = None
        municipality_id = None
        lookup_fingerprint = None
        if args.municipality:
            catalog = client.fetch_lookup_catalog()
            municipality = catalog.resolve_municipality(args.municipality)
            municipality_name = municipality.name
            municipality_id = municipality.option_id
            lookup_fingerprint = catalog.fingerprint
        return SearchCriteria(
            mode="address",
            address=address,
            municipality_name=municipality_name,
            municipality_id=municipality_id,
            lookup_fingerprint=lookup_fingerprint,
        )
    if command == "search":
        registration = _clean_text(args.registration)
        block = _clean_text(args.block)
        lot = _clean_text(args.lot)
        county_value = _clean_text(args.county)
        address = _clean_text(args.address)
        municipality_value = _clean_text(args.municipality)
        has_parcel = bool(block or lot or county_value)
        has_address = bool(address or municipality_value)
        modes = sum(bool(value) for value in (registration, has_parcel, has_address))
        if modes != 1:
            raise DCASelectionError(
                "mixed_search_modes",
                (
                    "Choose exactly one DCA search mode: registration; "
                    "block/lot/county; or address/municipality"
                ),
            )
        if registration:
            return SearchCriteria(
                mode="registration",
                registration=_registration_value(registration),
            )
        if has_parcel:
            if not county_value:
                raise DCASelectionError(
                    "county_required",
                    "DCA block/lot search requires county",
                )
            catalog = client.fetch_lookup_catalog()
            county = catalog.resolve_county(county_value)
            return SearchCriteria(
                mode="parcel",
                block=block,
                lot=lot,
                county_name=county.name,
                county_id=county.option_id,
                lookup_fingerprint=catalog.fingerprint,
            )
        if address and len(address) < 3:
            raise DCASelectionError(
                "address_too_short",
                "DCA address search requires at least three characters",
            )
        catalog = (
            client.fetch_lookup_catalog() if municipality_value else None
        )
        municipality = (
            catalog.resolve_municipality(municipality_value)
            if catalog and municipality_value
            else None
        )
        return SearchCriteria(
            mode="address",
            address=address,
            municipality_name=municipality.name if municipality else None,
            municipality_id=municipality.option_id if municipality else None,
            lookup_fingerprint=catalog.fingerprint if catalog else None,
        )
    raise DCASelectionError(
        "unsupported_operation",
        f"Unsupported DCA search operation: {command}",
    )


def _lookup_record(
    catalog: LookupCatalog,
    county_filter: str | None,
) -> dict[str, Any]:
    selected_county = (
        catalog.resolve_county(county_filter) if county_filter else None
    )
    municipalities = [
        item
        for item in catalog.municipalities
        if not selected_county or item.county_id == selected_county.option_id
    ]
    return {
        "record_type": "lookup_catalog",
        "source_id": SOURCE_ID,
        "lookup_fingerprint": catalog.fingerprint,
        "county_count": len(catalog.counties),
        "municipality_count": len(catalog.municipalities),
        "selected_county": (
            selected_county.to_dict() if selected_county else None
        ),
        "counties": [item.to_dict() for item in catalog.counties],
        "municipalities": [item.to_dict() for item in municipalities],
    }


def execute(
    args: argparse.Namespace,
    *,
    client: DCAPropertyClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    try:
        if args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [source_manifest_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "alternatives":
            result = PublicRecordsResult.success(
                query,
                alternative_route_records(),
                warnings=SOURCE_WARNINGS,
            )
        else:
            source_client = client or DCAPropertyClient(
                page_size=getattr(args, "page_size", DEFAULT_PAGE_SIZE),
                timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
                minimum_interval=getattr(
                    args,
                    "minimum_interval",
                    DEFAULT_MINIMUM_INTERVAL,
                ),
                retry_attempts=getattr(
                    args,
                    "retry_attempts",
                    DEFAULT_RETRY_ATTEMPTS,
                ),
            )
            if args.command == "lookups":
                catalog = source_client.fetch_lookup_catalog()
                result = PublicRecordsResult.success(
                    query,
                    [_lookup_record(catalog, args.county_filter)],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                criteria = _criteria_from_args(args, source_client)
                requested_limit = (
                    1 if args.command == "probe" else args.limit
                )
                fetch_limit = (
                    2 if args.command == "probe" else requested_limit
                )
                fetched = source_client.search(
                    criteria,
                    requested_limit=fetch_limit,
                    max_records=args.max_records,
                    cursor=args.cursor,
                )
                if args.command == "probe":
                    if (
                        len(fetched.records) != 1
                        or fetched.records[0].get(
                            "ultra_bhibuildingregistrationnum"
                        )
                        != PROBE_BUILDING_REGISTRATION
                    ):
                        raise SourceSchemaError(
                            "DCA live probe building identity changed",
                            url=ODATA_URL,
                            details={
                                "expected": PROBE_BUILDING_REGISTRATION,
                                "returned": [
                                    record.get(
                                        "ultra_bhibuildingregistrationnum"
                                    )
                                    for record in fetched.records
                                ],
                            },
                        )
                selected_records = (
                    fetched.records
                    if requested_limit is None
                    else fetched.records[:requested_limit]
                )
                records = [
                    normalize_building(record, fetch=fetched)
                    for record in selected_records
                ]
                warnings = list(SOURCE_WARNINGS)
                if fetched.count_drift:
                    warnings.append(
                        "The live match count changed after the cursor was "
                        "issued; keyset continuation was preserved."
                    )
                if fetched.capped:
                    warnings.append(
                        "Result stopped at the configured max-records cap."
                    )
                    result = PublicRecordsResult(
                        query=query,
                        status=ResultStatus.PARTIAL,
                        records=records,
                        next_cursor=fetched.next_cursor,
                        warnings=warnings,
                    )
                else:
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        next_cursor=fetched.next_cursor,
                        warnings=warnings,
                    )
    except DCASelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [error.to_contract_error()],
        )
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

    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    if log_results:
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            result_count,
        )
    return result


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_network_args(
    parser: argparse.ArgumentParser,
    *,
    include_limit: bool = True,
) -> None:
    if include_limit:
        parser.add_argument(
            "--limit",
            type=_positive_int,
            help="Optional result bound; omitted traverses every match",
        )
        parser.add_argument(
            "--max-records",
            type=_positive_int,
            help="Optional configured cap distinct from a requested limit",
        )
        parser.add_argument(
            "--cursor",
            help="Keyset cursor returned by a prior bounded query",
        )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
    )
    parser.add_argument(
        "--timeout",
        type=_nonnegative_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query New Jersey DCA BHI property and building registrations"
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    registration = subparsers.add_parser(
        "registration",
        help="Search a partial 10- or 13-digit registration number",
    )
    registration.add_argument("registration")
    _add_network_args(registration)

    parcel = subparsers.add_parser(
        "parcel",
        help="Search partial block/lot within an official county lookup",
    )
    parcel.add_argument("--county", required=True)
    parcel.add_argument("--block")
    parcel.add_argument("--lot")
    _add_network_args(parcel)

    address = subparsers.add_parser(
        "address",
        help="Search primary and AKA building addresses",
    )
    address.add_argument("address")
    address.add_argument("--municipality")
    _add_network_args(address)

    search = subparsers.add_parser(
        "search",
        help="Use one official registration, parcel, or address search branch",
    )
    search.add_argument("--registration")
    search.add_argument("--county")
    search.add_argument("--block")
    search.add_argument("--lot")
    search.add_argument("--address")
    search.add_argument("--municipality")
    _add_network_args(search)

    lookups = subparsers.add_parser(
        "lookups",
        help="Fetch current official county and municipality lookup IDs",
    )
    lookups.add_argument("--county", dest="county_filter")
    _add_network_args(lookups, include_limit=False)

    manifest = subparsers.add_parser(
        "manifest",
        help="Show source identity and operation-level access without network",
    )
    add_output_args(manifest)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="Show complementary official property routes without network",
    )
    add_output_args(alternatives)

    probe = subparsers.add_parser(
        "probe",
        help="Run one exact live building-registration sentinel",
    )
    _add_network_args(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"New Jersey DCA property {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"New Jersey DCA property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_type") == "property_registration_building":
            coordinates = record["parcel_coordinates"]
            print(
                f"  {record['building_registration_number']} | "
                f"{record['building_address']['line1'] or '?'} | "
                f"{coordinates['municipality'] or '?'}"
            )
        elif record.get("record_type") == "alternative_route":
            print(f"  {record['name']} | {record['url']}")
        else:
            print(f"  {record.get('record_type', 'record')}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
