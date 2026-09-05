#!/usr/bin/env python3
"""Query Washington county TaxSifter/PublicAccessNow property deployments.

The adapter discovers county tenants from official statewide parcel ``DATA_LINK``
values and keeps assessor, treasurer, appraisal, assessor-sale, permit, map, and
recorder representations independently attributable.

Examples:
    uv run python tools/query_washington_taxsifter.py sources
    uv run python tools/query_washington_taxsifter.py metadata --county adams
    uv run python tools/query_washington_taxsifter.py discover \
        "https://adamswa-taxsifter.publicaccessnow.com/Assessor.aspx?..."
    uv run python tools/query_washington_taxsifter.py search SMITH \
        --county adams --limit 25
    uv run python tools/query_washington_taxsifter.py detail 2038010000001 \
        --county adams
    uv run python tools/query_washington_taxsifter.py sales \
        --county adams --parcel 2038010000001
    uv run python tools/query_washington_taxsifter.py probe --verified
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from html import unescape
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urljoin, urlparse

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
        utc_now_iso,
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
        utc_now_iso,
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
    from public_records_store import canonical_property_ref


STATE_CODE = "WA"
STATE_FIPS = "53"
PLATFORM_FAMILY = "terrascan_taxsifter_publicaccessnow"
UMBRELLA_SOURCE_ID = "us-wa-taxsifter-property-family"
STATEWIDE_PARCEL_SOURCE_ID = "us-wa-state-parcels-normalized"
OUTPUT_SCHEMA_VERSION = "washington-taxsifter/1.0"
PROBE_SCHEMA_VERSION = "washington-taxsifter-probe/1.0"
CURSOR_PREFIX = "washington-taxsifter:v2:"
CURSOR_VERSION = 2
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_NATIVE_PAGE_SIZE = 20
DEFAULT_USER_AGENT = "Ithildin-Public-Records/1.0"
MAX_HTML_BYTES = 12 * 1024 * 1024

ASSESSOR_LINEAGE = "county_assessor_property_account"
TREASURER_LINEAGE = "county_treasurer_tax_account"
RECORDER_LINEAGE = "county_auditor_recorded_instrument"
MAP_LINEAGE = "county_assessor_parcel_map"
SALES_PAGINATION_STATE = "postback_observed_continuation_not_verified"
SALES_PAGINATION_NOTE = (
    "TaxSifter publishes a result count, a selected-page field, and WebForms "
    "pager postbacks, but bounded live probes did not establish a reliable "
    "continuation request. Direct sales search therefore returns the current "
    "native response and reports whether that response is exhaustive."
)


class ResponseState(StrEnum):
    """Typed state observed for one TaxSifter operation response."""

    LIVE = "live"
    NO_RESULT = "no_result"
    DISCLAIMER = "disclaimer"
    CHALLENGE = "challenge"
    MAINTENANCE = "maintenance"
    SCHEMA_ERROR = "schema_error"


class Operation(StrEnum):
    SEARCH = "search"
    ASSESSOR = "assessor"
    TREASURER = "treasurer"
    APPRAISAL = "appraisal"
    SALES = "sales"


OPERATION_LINEAGES: Mapping[str, Mapping[str, str]] = {
    Operation.SEARCH: {
        "lineage_id": ASSESSOR_LINEAGE,
        "source_role": "county_assessor_property_search",
        "representation": "search_result",
    },
    Operation.ASSESSOR: {
        "lineage_id": ASSESSOR_LINEAGE,
        "source_role": "county_assessor_property_account",
        "representation": "assessor_detail",
    },
    Operation.TREASURER: {
        "lineage_id": TREASURER_LINEAGE,
        "source_role": "county_treasurer_tax_account",
        "representation": "treasurer_detail",
    },
    Operation.APPRAISAL: {
        "lineage_id": ASSESSOR_LINEAGE,
        "source_role": "county_assessor_appraisal",
        "representation": "appraisal_detail",
    },
    Operation.SALES: {
        "lineage_id": ASSESSOR_LINEAGE,
        "source_role": "county_assessor_sales_search",
        "representation": "assessor_sale_index",
    },
}


@dataclass(frozen=True)
class TenantConfig:
    """One county deployment observed from an official parcel ``DATA_LINK``."""

    key: str
    source_id: str
    county_name: str
    county_geoid: str
    authority: str
    portal_root: str
    search_path: str
    observed_data_link: str
    observed_hosts: tuple[str, ...]
    deployment_variant: str
    access_state: str
    verified_operations: tuple[str, ...]
    observed_capabilities: tuple[str, ...]
    sentinel_query: str
    observed_at: str = "2026-07-30"
    digital_archives_title_id: int | None = None
    notes: tuple[str, ...] = ()

    @property
    def county_fips(self) -> str:
        return self.county_geoid[-3:]

    @property
    def jurisdiction(self) -> JurisdictionMetadata:
        return JurisdictionMetadata(
            jurisdiction_id=self.county_geoid,
            name=f"{self.county_name}, Washington",
            state_code=STATE_CODE,
            county_fips=self.county_fips,
            locality=self.county_name,
            metadata={"state_fips": STATE_FIPS},
        )

    @property
    def source(self) -> SourceMetadata:
        operation_states = {
            operation.value: (
                "live_verified"
                if operation.value in self.verified_operations
                else (
                    "challenge_observed"
                    if self.access_state == "challenge_observed"
                    else "discovered_from_official_data_link"
                )
            )
            for operation in Operation
        }
        complements: list[dict[str, Any]] = []
        if self.digital_archives_title_id is not None:
            complements.append(
                {
                    "kind": "washington_digital_archives_recorded_land_title",
                    "source_lineage": RECORDER_LINEAGE,
                    "title_id": self.digital_archives_title_id,
                    "url": (
                        "https://digitalarchives.wa.gov/Collections/TitleInfo/"
                        f"{self.digital_archives_title_id}"
                    ),
                    "relationship": "independent_recorded_instrument_index",
                    "join_keys": [
                        "party_name",
                        "recording_date",
                        "instrument_number",
                        "excise_number",
                    ],
                }
            )
        return SourceMetadata(
            source_id=self.source_id,
            name=f"{self.county_name} TaxSifter Property Records",
            source_role=(
                "official_county_assessor_treasurer_property_enrichment_family"
            ),
            base_url=self.portal_root,
            dataset_id=f"taxsifter-{self.key}",
            metadata={
                "authority": self.authority,
                "operator": "Aumentum Technologies / TerraScan TaxSifter",
                "platform_family": PLATFORM_FAMILY,
                "umbrella_source_id": UMBRELLA_SOURCE_ID,
                "county_geoid": self.county_geoid,
                "official_data_link_observed": self.observed_data_link,
                "observed_at": self.observed_at,
                "deployment_variant": self.deployment_variant,
                "access_state": self.access_state,
                "operation_states": operation_states,
                "observed_capabilities": list(self.observed_capabilities),
                "operation_lineages": {
                    key.value: dict(value) for key, value in OPERATION_LINEAGES.items()
                },
                "same_lineage_interpretation": (
                    "assessor_search_detail_appraisal_sales_permit_and_map_"
                    "representations_are_not_independent_corroboration"
                ),
                "recorder_lineage_interpretation": (
                    "auditor_instrument_indexes_and_images_are_distinct_"
                    "official_evidence_when_the_record_supports_the_claim"
                ),
                "complementary_sources": complements,
                "notes": list(self.notes),
            },
        )


TENANTS = (
    TenantConfig(
        key="adams",
        source_id="us-wa-adams-county-taxsifter",
        county_name="Adams County",
        county_geoid="53001",
        authority="Adams County Assessor and Treasurer",
        portal_root="https://adamswa-taxsifter.publicaccessnow.com/",
        search_path="Search/Results.aspx",
        observed_data_link=(
            "https://adamswa-taxsifter.publicaccessnow.com/"
            "Assessor.aspx?keyId=593482&parcelNumber=2038010000001&typeID=1"
        ),
        observed_hosts=("adamswa-taxsifter.publicaccessnow.com",),
        deployment_variant="publicaccessnow_root",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel",
            "owner",
            "mailing",
            "situs",
            "legal",
            "assessment",
            "valuation_history",
            "sale_history",
            "permit_section",
            "tax_due",
            "payment_history",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="2038010000001",
        digital_archives_title_id=93,
    ),
    TenantConfig(
        key="douglas",
        source_id="us-wa-douglas-county-taxsifter",
        county_name="Douglas County",
        county_geoid="53017",
        authority="Douglas County Assessor and Treasurer",
        portal_root="https://douglaswa-taxsifter.publicaccessnow.com/",
        search_path="Search/Results.aspx",
        observed_data_link=(
            "http://douglaswa.taxsifter.com/"
            "Assessor.aspx?keyId=1088458&parcelNumber=07000000504&typeID=1"
        ),
        observed_hosts=(
            "douglaswa.taxsifter.com",
            "douglaswa-taxsifter.publicaccessnow.com",
        ),
        deployment_variant="legacy_taxsifter_redirect_to_publicaccessnow",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel",
            "owner",
            "mailing",
            "situs",
            "legal",
            "assessment",
            "valuation_history",
            "sale_history",
            "building_permits",
            "tax_due",
            "payment_history",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="07000000504",
    ),
    TenantConfig(
        key="ferry",
        source_id="us-wa-ferry-county-taxsifter",
        county_name="Ferry County",
        county_geoid="53019",
        authority="Ferry County Assessor and Treasurer",
        portal_root="https://ferrywa-taxsifter.publicaccessnow.com/",
        search_path="Search/Results.aspx",
        observed_data_link=(
            "https://ferrywa-taxsifter.publicaccessnow.com/"
            "Search/Results.aspx?q=63715340001000"
        ),
        observed_hosts=("ferrywa-taxsifter.publicaccessnow.com",),
        deployment_variant="publicaccessnow_root",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel_search",
            "owner_in_search",
            "property_class_in_search",
            "deterministic_assessor_link",
            "deterministic_treasurer_link",
            "deterministic_appraisal_link",
            "assessor_sale_history",
            "treasurer_detail",
            "appraisal",
            "sales_search",
            "map_pivot",
        ),
        sentinel_query="63715340001000",
    ),
    TenantConfig(
        key="franklin",
        source_id="us-wa-franklin-county-taxsifter",
        county_name="Franklin County",
        county_geoid="53021",
        authority="Franklin County Assessor and Treasurer",
        portal_root="http://terra.co.franklin.wa.us/TaxSifter/",
        search_path="Search/results.aspx",
        observed_data_link=(
            "http://terra.co.franklin.wa.us/TaxSifter/Search/results.aspx?q=114181136"
        ),
        observed_hosts=("terra.co.franklin.wa.us",),
        deployment_variant="county_hosted_nested_path",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel_search",
            "owner_in_search",
            "deterministic_detail_links",
            "assessor_sale_history",
            "building_permits",
            "treasurer_detail",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="114181136",
        digital_archives_title_id=197,
    ),
    TenantConfig(
        key="kittitas",
        source_id="us-wa-kittitas-county-taxsifter",
        county_name="Kittitas County",
        county_geoid="53037",
        authority="Kittitas County Assessor and Treasurer",
        portal_root="https://taxsifter.co.kittitas.wa.us/",
        search_path="Search/Results.aspx",
        observed_data_link=(
            "https://taxsifter.co.kittitas.wa.us/Search/Results.aspx?q=18-18-25056-0008"
        ),
        observed_hosts=("taxsifter.co.kittitas.wa.us",),
        deployment_variant="county_hosted_root",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel_search",
            "owner_in_search",
            "deterministic_detail_links",
            "assessor_sale_history",
            "building_permits",
            "treasurer_detail",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="18-18-25056-0008",
    ),
    TenantConfig(
        key="lincoln",
        source_id="us-wa-lincoln-county-taxsifter",
        county_name="Lincoln County",
        county_geoid="53043",
        authority="Lincoln County Assessor and Treasurer",
        portal_root="https://lincolnwa-taxsifter.publicaccessnow.com/",
        search_path="Search/results.aspx",
        observed_data_link=(
            "https://lincolnwa.taxsifter.com/Search/results.aspx?q=2836010000000"
        ),
        observed_hosts=(
            "lincolnwa.taxsifter.com",
            "lincolnwa-taxsifter.publicaccessnow.com",
        ),
        deployment_variant="legacy_taxsifter_migrated_to_publicaccessnow",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel_search",
            "owner_in_search",
            "deterministic_detail_links",
            "assessor_sale_history",
            "treasurer_detail",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="2836010000000",
        notes=(
            "The official county property-search page now links the "
            "publicaccessnow deployment; the legacy taxsifter host remains an "
            "observed discovery alias.",
            "The bounded sentinel sales query returned an authoritative "
            "no-result response while the sales operation remained available.",
        ),
    ),
    TenantConfig(
        key="mason",
        source_id="us-wa-mason-county-taxsifter",
        county_name="Mason County",
        county_geoid="53045",
        authority="Mason County Assessor and Treasurer",
        portal_root="https://property.masoncountywa.gov/TaxSifter/",
        search_path="Search/Results.aspx",
        observed_data_link=(
            "https://property.masoncountywa.gov/TaxSifter/"
            "Search/Results.aspx?q=21901-00-90040"
        ),
        observed_hosts=("property.masoncountywa.gov",),
        deployment_variant="county_hosted_nested_path",
        access_state="challenge_observed",
        verified_operations=(),
        observed_capabilities=("official_parcel_search_route",),
        sentinel_query="21901-00-90040",
        digital_archives_title_id=56,
        notes=(
            "The HTTP search probe observed a JavaScript/cookie challenge on "
            "this deployment; this state is scoped to Mason's operation.",
        ),
    ),
    TenantConfig(
        key="okanogan",
        source_id="us-wa-okanogan-county-taxsifter",
        county_name="Okanogan County",
        county_geoid="53047",
        authority="Okanogan County Assessor and Treasurer",
        portal_root="https://okanoganwa-taxsifter.publicaccessnow.com/",
        search_path="Search/results.aspx",
        observed_data_link=(
            "http://okanoganwa.taxsifter.com/Search/results.aspx?q=4030014005"
        ),
        observed_hosts=(
            "okanoganwa.taxsifter.com",
            "okanoganwa-taxsifter.publicaccessnow.com",
        ),
        deployment_variant="legacy_taxsifter_migrated_to_publicaccessnow",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel_search",
            "owner_in_search",
            "deterministic_detail_links",
            "assessor_sale_history",
            "treasurer_detail",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="4030014005",
        digital_archives_title_id=1778,
    ),
    TenantConfig(
        key="pacific",
        source_id="us-wa-pacific-county-taxsifter",
        county_name="Pacific County",
        county_geoid="53049",
        authority="Pacific County Assessor and Treasurer",
        portal_root="http://pacificwa.taxsifter.com/",
        search_path="Search/results.aspx",
        observed_data_link=(
            "http://pacificwa.taxsifter.com/Search/results.aspx?q=15111821012"
        ),
        observed_hosts=(
            "pacificwa.taxsifter.com",
            "pacificwa-taxsifter.publicaccessnow.com",
        ),
        deployment_variant="legacy_taxsifter_redirect_to_publicaccessnow",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel_search",
            "owner_in_search",
            "deterministic_detail_links",
            "assessor_sale_history",
            "treasurer_detail",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="15111821012",
        digital_archives_title_id=64,
        notes=(
            "The ordinary disclaimer session completed in the adapter even "
            "when a generic crawler could not reach the deployment.",
            "The bounded sentinel sales query returned an authoritative "
            "no-result response while the sales operation remained available.",
        ),
    ),
    TenantConfig(
        key="skamania",
        source_id="us-wa-skamania-county-taxsifter",
        county_name="Skamania County",
        county_geoid="53059",
        authority="Skamania County Assessor and Treasurer",
        portal_root="https://skamaniawa-taxsifter.publicaccessnow.com/",
        search_path="Search/Results.aspx",
        observed_data_link=(
            "https://skamaniawa-taxsifter.publicaccessnow.com/"
            "Search/Results.aspx?q=01051900050000"
        ),
        observed_hosts=("skamaniawa-taxsifter.publicaccessnow.com",),
        deployment_variant="publicaccessnow_root",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel_search",
            "owner_in_search",
            "deterministic_detail_links",
            "assessor_sale_history",
            "treasurer_detail",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="01051900050000",
        digital_archives_title_id=1188,
    ),
    TenantConfig(
        key="whitman",
        source_id="us-wa-whitman-county-taxsifter",
        county_name="Whitman County",
        county_geoid="53075",
        authority="Whitman County Assessor and Treasurer",
        portal_root="https://terrascan.whitmancounty.net/Taxsifter/",
        search_path="Search/Results.aspx",
        observed_data_link=(
            "https://terrascan.whitmancounty.net/Taxsifter/"
            "Assessor.aspx?keyId=985740&parcelNumber=200004216132902&typeID=1"
        ),
        observed_hosts=("terrascan.whitmancounty.net",),
        deployment_variant="county_hosted_nested_path",
        access_state="live_verified",
        verified_operations=("search", "assessor", "treasurer", "appraisal", "sales"),
        observed_capabilities=(
            "parcel_search",
            "owner_in_search",
            "deterministic_detail_links",
            "assessor_sale_history",
            "treasurer_detail",
            "appraisal",
            "sales_search",
        ),
        sentinel_query="200004216132902",
        digital_archives_title_id=2107,
    ),
)

TENANTS_BY_KEY = {tenant.key: tenant for tenant in TENANTS}
TENANTS_BY_SOURCE = {tenant.source_id: tenant for tenant in TENANTS}
TENANTS_BY_HOST: dict[str, TenantConfig] = {}
for _tenant in TENANTS:
    for _host in _tenant.observed_hosts:
        TENANTS_BY_HOST[_host.lower()] = _tenant

VERIFIED_TENANT_KEYS = tuple(
    tenant.key for tenant in TENANTS if tenant.access_state == "live_verified"
)


@dataclass(frozen=True)
class DataLinkDiscovery:
    """Parsed identity from one official statewide parcel destination."""

    url: str
    tenant: TenantConfig | None
    operation: str | None
    parcel_number: str | None
    key_id: str | None
    type_id: str | None
    search_query: str | None
    observed_host: str
    path_prefix: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "matched": self.tenant is not None,
            "county": self.tenant.key if self.tenant else None,
            "source_id": self.tenant.source_id if self.tenant else None,
            "operation": self.operation,
            "parcel_number": self.parcel_number,
            "key_id": self.key_id,
            "type_id": self.type_id,
            "search_query": self.search_query,
            "observed_host": self.observed_host,
            "path_prefix": self.path_prefix,
        }


@dataclass(frozen=True)
class SourcePage:
    """One operation response with typed state and source provenance."""

    operation: str
    state: ResponseState
    url: str
    status_code: int
    html: str
    title: str | None
    retrieved_at: str
    schema_fingerprint: str
    data_current_as: str | None
    roll_year: str | None
    transition_urls: tuple[str, ...] = ()

    def provenance(
        self,
        tenant: TenantConfig,
        *,
        lineage_id: str,
        source_role: str,
        representation: str,
    ) -> dict[str, Any]:
        return {
            "source_id": tenant.source_id,
            "source_url": self.url,
            "retrieved_at": self.retrieved_at,
            "response_state": self.state.value,
            "operation": self.operation,
            "lineage_id": lineage_id,
            "source_role": source_role,
            "representation": representation,
            "data_current_as": self.data_current_as,
            "roll_year": self.roll_year,
            "source_response_schema_fingerprint": self.schema_fingerprint,
        }


@dataclass(frozen=True)
class SearchPage:
    records: tuple[Mapping[str, Any], ...]
    total_count: int
    native_page: int
    maximum_page: int
    native_page_size: int
    source_page: SourcePage


@dataclass(frozen=True)
class SearchBatch:
    records: tuple[Mapping[str, Any], ...]
    total_count: int
    next_cursor: str | None
    pages_fetched: int
    native_page_size: int
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class SalesForm:
    action_url: str
    fields: Mapping[str, str]
    options: Mapping[str, tuple[Mapping[str, Any], ...]]
    defaults: Mapping[str, str]
    source_page: SourcePage


class SourceChallengeError(PublicRecordsHTTPError):
    result_status = ResultStatus.HUMAN_REQUIRED
    category = "source_access"
    code = "source_challenge_required"


class SourceMaintenanceError(PublicRecordsHTTPError):
    result_status = ResultStatus.UNAVAILABLE
    category = "source_availability"
    code = "source_maintenance"
    retryable = True


class UnresolvedDisclaimerError(PublicRecordsHTTPError):
    result_status = ResultStatus.TERMS_BLOCKED
    category = "source_session"
    code = "source_disclaimer_unresolved"


class SourceSelectionError(RuntimeError):
    """Invalid source, operation, identifier, or continuation selection."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="query",
            retryable=False,
            details=self.details,
        )


class NoParcelResult(RuntimeError):
    """Authoritative empty parcel lookup used by the detail operation."""


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", unescape(str(value))).strip()
    return text or None


def _slug(value: Any) -> str:
    text = (_clean(value) or "").lower()
    text = text.replace("%", " percent ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _string(value: Any) -> str | None:
    cleaned = _clean(value)
    return str(cleaned) if cleaned is not None else None


def _account_occurrence(
    tenant: TenantConfig,
    *,
    key_id: Any,
    type_id: Any,
    source_url: str,
) -> dict[str, str]:
    """Return the source-native account occurrence, distinct from its parcel join."""

    native_key = _string(key_id)
    native_type = _string(type_id)
    if native_key is None or native_type is None:
        raise SourceSchemaError(
            "TaxSifter account locator lacks keyId or typeID",
            url=source_url,
            details={
                "key_id_present": native_key is not None,
                "type_id_present": native_type is not None,
            },
        )
    return {
        "source_id": tenant.source_id,
        "key_id": native_key,
        "type_id": native_type,
        "native_id": f"keyId={native_key};typeID={native_type}",
    }


def _parcel_join(tenant: TenantConfig, parcel_number: Any) -> dict[str, str]:
    parcel = _string(parcel_number)
    if parcel is None:
        raise ValueError("TaxSifter parcel join requires a parcel number")
    return {
        "county_geoid": tenant.county_geoid,
        "parcel_number": parcel,
    }


def _search_record_identity(record: Mapping[str, Any]) -> str:
    key_id = _string(record.get("key_id"))
    type_id = _string(record.get("type_id"))
    source_id = _string(record.get("source_id"))
    if source_id is None or key_id is None or type_id is None:
        raise SourceSelectionError(
            "invalid_search_identity",
            "TaxSifter search record lacks its source-native account identity",
        )
    return f"{source_id}|keyId={key_id}|typeID={type_id}"


def _ordered_search_page_digest(
    records: Sequence[Mapping[str, Any]],
) -> str:
    """Hash ordered stable row content without retrieval-position metadata."""

    payload = [
        {
            "account_identity": _search_record_identity(record),
            "parcel_number": _string(record.get("parcel_number")),
            "display_lines": list(record.get("display_lines") or ()),
            "operation_links": dict(record.get("operation_links") or {}),
        }
        for record in records
    ]
    return sha256_fingerprint(payload)


def _criteria_fingerprint(selector: str) -> str:
    return sha256_fingerprint({"selector": str(selector)})


def _money(value: Any) -> dict[str, Any]:
    raw = _clean(value)
    if raw is None:
        return {"raw": None, "amount": None, "currency": "USD"}
    normalized = raw.replace("$", "").replace(",", "").strip()
    negative = normalized.startswith("(") and normalized.endswith(")")
    if negative:
        normalized = f"-{normalized[1:-1]}"
    try:
        amount: int | float | None = float(normalized)
        if amount.is_integer():
            amount = int(amount)
    except ValueError:
        amount = None
    return {"raw": raw, "amount": amount, "currency": "USD"}


def _number(value: Any) -> int | float | None:
    raw = _clean(value)
    if raw is None:
        return None
    normalized = raw.replace(",", "").replace("%", "").strip()
    try:
        result = float(normalized)
    except ValueError:
        return None
    return int(result) if result.is_integer() else result


def _date_iso(value: Any) -> str | None:
    raw = _clean(value)
    if raw is None:
        return None
    for pattern in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _title(soup: BeautifulSoup) -> str | None:
    return _clean(soup.title.get_text(" ", strip=True)) if soup.title else None


def _suffix_node(soup: BeautifulSoup, suffix: str) -> Tag | None:
    return soup.find(id=re.compile(re.escape(suffix) + r"$", re.I))


def _suffix_text(soup: BeautifulSoup, suffix: str) -> str | None:
    node = _suffix_node(soup, suffix)
    return _clean(node.get_text(" ", strip=True)) if node else None


def _data_current_as(soup: BeautifulSoup) -> str | None:
    raw = _suffix_text(soup, "lblDataDate")
    if raw is None:
        return None
    match = re.search(r"(?:as of\s*:|:)\s*(.+)$", raw, flags=re.I)
    return _clean(match.group(1)) if match else raw


def _roll_year(soup: BeautifulSoup) -> str | None:
    raw = _suffix_text(soup, "lblRollYear")
    if raw:
        match = re.search(r"\b(19|20|21)\d{2}\b", raw)
        if match:
            return match.group(0)
    for caption in soup.select("caption"):
        match = re.search(r"\b(19|20|21)\d{2}\b", caption.get_text(" ", strip=True))
        if match:
            return match.group(0)
    return None


def _schema_shape(soup: BeautifulSoup, operation: str) -> dict[str, Any]:
    table_shapes = []
    for table in soup.select("table"):
        table_shapes.append(
            {
                "id": table.get("id"),
                "caption": _clean(
                    table.caption.get_text(" ", strip=True) if table.caption else None
                ),
                "headers": [
                    _clean(node.get_text(" ", strip=True))
                    for node in table.select("th")
                ],
            }
        )
    return {
        "operation": operation,
        "form_action": (
            str(soup.select_one("form").get("action") or "")
            if soup.select_one("form")
            else None
        ),
        "named_controls": sorted(
            {
                str(node.get("name"))
                for node in soup.select("[name]")
                if node.get("name") and not str(node.get("name")).startswith("__")
            }
        ),
        "tables": table_shapes,
        "result_panel_present": bool(soup.select('[id*="pnlResult"]')),
    }


def classify_response(
    html: str,
    *,
    url: str,
    operation: str,
) -> ResponseState:
    """Classify a response without collapsing access and source failures."""

    soup = BeautifulSoup(html, "lxml")
    title = (_title(soup) or "").lower()
    lowered = html.lower()
    if (
        "cf-chl-" in lowered
        or "challenge-platform" in lowered
        or "just a moment" in title
        or "checking your browser" in lowered
        or "enable javascript and cookies to continue" in lowered
    ):
        return ResponseState.CHALLENGE
    if any(
        marker in lowered
        for marker in (
            "scheduled maintenance",
            "down for maintenance",
            "currently unavailable for maintenance",
            "temporarily unavailable due to maintenance",
        )
    ):
        return ResponseState.MAINTENANCE
    if (
        "disclaimer" in urlparse(url).path.lower()
        or soup.select_one('input[name*="btnAgree"]') is not None
        or "disclaimer and terms" in lowered
    ):
        return ResponseState.DISCLAIMER
    result_count = soup.select_one(".resultCount")
    if soup.select_one("#no-results") is not None or (
        result_count is not None
        and re.search(
            r"\b0\s+records?\s+found\b",
            result_count.get_text(" ", strip=True),
            flags=re.I,
        )
    ):
        return ResponseState.NO_RESULT

    markers = {
        Operation.SEARCH: (
            soup.select_one("#result-area") is not None
            or result_count is not None
            or soup.select_one('input[name="q"]') is not None
        ),
        Operation.ASSESSOR: (
            _suffix_node(soup, "ParcelOwnerInfo1_lbParcelNumber") is not None
            and (
                soup.find(id=re.compile(r"dvMarketValues$", re.I)) is not None
                or soup.find(id=re.compile(r"dvAssessmentData$", re.I)) is not None
                or soup.find(id=re.compile(r"grdParcelOwnership$", re.I)) is not None
            )
        ),
        Operation.TREASURER: (
            _suffix_node(soup, "ParcelOwnerInfo1_lbParcelNumber") is not None
            and (
                soup.find(id=re.compile(r"CurrentTaxYear.*GridView1$", re.I))
                is not None
                or "balances due" in lowered
            )
        ),
        Operation.APPRAISAL: (
            _suffix_node(soup, "ParcelOwnerInfo1_lbParcelNumber") is not None
            and (
                soup.select_one(".sliceContainer") is not None
                or soup.find(id=re.compile(r"grdLand$", re.I)) is not None
                or soup.find(id=re.compile(r"pnlContainer$", re.I)) is not None
            )
        ),
        Operation.SALES: (
            soup.find("input", attrs={"name": re.compile(r"txtparcelNumber$", re.I)})
            is not None
            and soup.find("input", attrs={"name": re.compile(r"searchbutton$", re.I)})
            is not None
        )
        or result_count is not None,
    }
    return (
        ResponseState.LIVE
        if markers.get(Operation(operation), False)
        else ResponseState.SCHEMA_ERROR
    )


def _source_page(
    response: Any,
    *,
    operation: str,
    transition_urls: Sequence[str] = (),
) -> SourcePage:
    html = str(getattr(response, "text", ""))
    url = str(getattr(response, "url", ""))
    soup = BeautifulSoup(html, "lxml")
    state = classify_response(html, url=url, operation=operation)
    return SourcePage(
        operation=operation,
        state=state,
        url=url,
        status_code=int(getattr(response, "status_code", 0)),
        html=html,
        title=_title(soup),
        retrieved_at=utc_now_iso(),
        schema_fingerprint=sha256_fingerprint(_schema_shape(soup, operation)),
        data_current_as=_data_current_as(soup),
        roll_year=_roll_year(soup),
        transition_urls=tuple(transition_urls),
    )


def discover_data_link(url: str) -> DataLinkDiscovery:
    """Resolve a statewide parcel destination to its observed tenant/operation."""

    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    tenant = TENANTS_BY_HOST.get(host)
    path = parsed.path or "/"
    operation = None
    operation_match = re.search(
        r"/(Search/Results|Assessor|Treasurer|AppraisalDetails|"
        r"SalesSearch/SalesSearch)\.aspx$",
        path,
        flags=re.I,
    )
    if operation_match:
        leaf = operation_match.group(1).lower()
        if leaf == "search/results":
            operation = Operation.SEARCH
        elif leaf == "assessor":
            operation = Operation.ASSESSOR
        elif leaf == "treasurer":
            operation = Operation.TREASURER
        elif leaf == "appraisaldetails":
            operation = Operation.APPRAISAL
        elif leaf == "salessearch/salessearch":
            operation = Operation.SALES
    query = parse_qs(parsed.query, keep_blank_values=True)

    def first(*names: str) -> str | None:
        for name in names:
            for key, values in query.items():
                if key.lower() == name.lower() and values:
                    return str(values[0])
        return None

    prefix = "/"
    if operation_match:
        prefix = path[: operation_match.start() + 1] or "/"
    return DataLinkDiscovery(
        url=url,
        tenant=tenant,
        operation=str(operation) if operation else None,
        parcel_number=first("parcelNumber"),
        key_id=first("keyId"),
        type_id=first("typeID"),
        search_query=first("q"),
        observed_host=host,
        path_prefix=prefix,
    )


def _account_locator_from_url(
    url: str,
    tenant: TenantConfig,
) -> dict[str, str]:
    discovery = discover_data_link(url)
    if discovery.tenant != tenant:
        raise SourceSchemaError(
            "TaxSifter operation link resolves outside the selected source",
            url=url,
            details={
                "selected_source": tenant.source_id,
                "observed_source": (
                    discovery.tenant.source_id if discovery.tenant else None
                ),
            },
        )
    parcel = _string(discovery.parcel_number)
    if parcel is None:
        raise SourceSchemaError(
            "TaxSifter operation link lacks a parcelNumber",
            url=url,
        )
    occurrence = _account_occurrence(
        tenant,
        key_id=discovery.key_id,
        type_id=discovery.type_id,
        source_url=url,
    )
    return {
        **occurrence,
        "parcel_number": parcel,
    }


def _validate_account_consistency(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    tenant: TenantConfig,
    operation: str,
    source_url: str,
) -> None:
    expected_occurrence = _account_occurrence(
        tenant,
        key_id=expected.get("key_id"),
        type_id=expected.get("type_id"),
        source_url=source_url,
    )
    actual_occurrence = _account_occurrence(
        tenant,
        key_id=actual.get("key_id"),
        type_id=actual.get("type_id"),
        source_url=source_url,
    )
    expected_values = {
        "parcel_number": _string(
            expected.get("parcel_number") or expected.get("native_parcel_id")
        ),
        "key_id": expected_occurrence["key_id"],
        "type_id": expected_occurrence["type_id"],
    }
    actual_values = {
        "parcel_number": _string(
            actual.get("parcel_number") or actual.get("native_parcel_id")
        ),
        "key_id": actual_occurrence["key_id"],
        "type_id": actual_occurrence["type_id"],
    }
    if (
        expected_values["parcel_number"] is None
        or actual_values["parcel_number"] is None
        or expected_values != actual_values
    ):
        raise SourceSchemaError(
            "TaxSifter detail identity does not match its selected account",
            url=source_url,
            details={
                "operation": str(operation),
                "expected": expected_values,
                "actual": actual_values,
            },
        )


def _hidden_fields(soup: BeautifulSoup) -> dict[str, str]:
    return {
        str(node.get("name")): str(node.get("value") or "")
        for node in soup.select('input[type="hidden"][name]')
    }


def _form_action(soup: BeautifulSoup, source_url: str) -> str:
    form = soup.select_one("form")
    if form is None:
        raise SourceSchemaError(
            "TaxSifter page lacks the expected form",
            url=source_url,
        )
    return urljoin(source_url, str(form.get("action") or source_url))


def _response_header(response: Any, name: str) -> str | None:
    for key, value in dict(getattr(response, "headers", {})).items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


class TaxSifterClient:
    """Session-aware, rate-limited client for one county deployment."""

    def __init__(
        self,
        tenant: TenantConfig,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.tenant = tenant
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            clock=clock,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "User-Agent": user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                }
            )

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> Any:
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        f"TaxSifter request failed after {attempt} attempts: {error}",
                        url=url,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(getattr(response, "status_code", 0))
            if status_code in self.retry_policy.retry_statuses:
                retry_after = _response_header(response, "Retry-After")
                delay = None
                if retry_after is not None:
                    try:
                        delay = max(0.0, float(retry_after))
                    except ValueError:
                        delay = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt, delay))
                    continue
                if status_code == 429:
                    raise RateLimitedHTTPError(
                        status_code,
                        url=str(getattr(response, "url", url)),
                        response_text=str(getattr(response, "text", "")),
                    )
                raise HTTPStatusError(
                    status_code,
                    url=str(getattr(response, "url", url)),
                    response_text=str(getattr(response, "text", "")),
                )
            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=str(getattr(response, "url", url)),
                    response_text=str(getattr(response, "text", "")),
                )
            if status_code == 451:
                raise TermsBlockedHTTPError(
                    status_code,
                    url=str(getattr(response, "url", url)),
                    response_text=str(getattr(response, "text", "")),
                )
            if status_code in {404, 410}:
                raise SourceChangedHTTPError(
                    status_code,
                    url=str(getattr(response, "url", url)),
                    response_text=str(getattr(response, "text", "")),
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=str(getattr(response, "url", url)),
                    response_text=str(getattr(response, "text", "")),
                )
            body = str(getattr(response, "text", ""))
            if len(body.encode("utf-8")) > MAX_HTML_BYTES:
                raise SourceSchemaError(
                    "TaxSifter response exceeded the bounded HTML size",
                    url=str(getattr(response, "url", url)),
                    details={"maximum_bytes": MAX_HTML_BYTES},
                )
            return response
        raise TransportError(
            f"TaxSifter request failed: {last_error}",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )

    @staticmethod
    def _raise_for_page(page: SourcePage) -> None:
        details = {
            "response_state": page.state.value,
            "operation": page.operation,
            "status_code": page.status_code,
            "title": page.title,
        }
        if page.state == ResponseState.CHALLENGE:
            raise SourceChallengeError(
                "TaxSifter operation presented an interactive challenge",
                url=page.url,
                details=details,
            )
        if page.state == ResponseState.MAINTENANCE:
            raise SourceMaintenanceError(
                "TaxSifter operation is displaying a maintenance state",
                url=page.url,
                details=details,
            )
        if page.state == ResponseState.DISCLAIMER:
            raise UnresolvedDisclaimerError(
                "TaxSifter disclaimer remained after the ordinary session flow",
                url=page.url,
                details=details,
            )
        if page.state == ResponseState.SCHEMA_ERROR:
            raise SourceSchemaError(
                "TaxSifter operation response no longer matches its observed schema",
                url=page.url,
                details=details,
            )

    def fetch_page(
        self,
        url: str,
        *,
        operation: str,
        params: Mapping[str, Any] | None = None,
        establish_session: bool = True,
    ) -> SourcePage:
        """Fetch one page and replay the ordinary disclaimer agreement if needed."""

        initial = self._request("GET", url, params=params)
        history = [
            str(getattr(item, "url", "")) for item in getattr(initial, "history", ())
        ]
        initial_page = _source_page(
            initial,
            operation=operation,
            transition_urls=history,
        )
        page = initial_page
        if page.state == ResponseState.DISCLAIMER and establish_session:
            soup = BeautifulSoup(page.html, "lxml")
            agree = soup.find(
                "input",
                attrs={"name": re.compile(r"btnAgree$", re.I)},
            )
            if agree is None or not agree.get("name"):
                raise SourceSchemaError(
                    "TaxSifter disclaimer lacks its agreement control",
                    url=page.url,
                    details={"response_state": page.state.value},
                )
            payload = _hidden_fields(soup)
            payload[str(agree.get("name"))] = str(agree.get("value") or "I Agree")
            agreement_url = _form_action(soup, page.url)
            agreed = self._request("POST", agreement_url, data=payload)
            transitions = [
                *page.transition_urls,
                page.url,
                *[
                    str(getattr(item, "url", ""))
                    for item in getattr(agreed, "history", ())
                ],
                str(getattr(agreed, "url", agreement_url)),
            ]
            final = self._request("GET", url, params=params)
            page = _source_page(
                final,
                operation=operation,
                transition_urls=transitions,
            )
        self._raise_for_page(page)
        return page

    def search_page(self, selector: str, *, page: int = 1) -> SearchPage:
        if page <= 0:
            raise ValueError("page must be positive")
        source_page = self.fetch_page(
            urljoin(self.tenant.portal_root, self.tenant.search_path),
            operation=Operation.SEARCH,
            params={"q": selector, "page": page},
        )
        return parse_search_page(source_page, self.tenant, native_page=page)

    def search(
        self,
        selector: str,
        *,
        limit: int | None,
        cursor: str | None = None,
    ) -> SearchBatch:
        """Traverse native search pages with a page-integrity-bound cursor."""

        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive")
        native_page = 1
        offset = 0
        expected_total: int | None = None
        expected_schema: str | None = None
        expected_page_digest: str | None = None
        expected_last_identity: str | None = None
        criteria = _criteria_fingerprint(selector)
        if cursor:
            payload = _decode_cursor(cursor)
            try:
                if payload["source"] != self.tenant.source_id:
                    raise KeyError("source")
                if payload["criteria"] != criteria:
                    raise KeyError("criteria")
                native_page = int(payload["page"])
                offset = int(payload["offset"])
                expected_total = int(payload["total"])
                expected_schema = str(payload["schema"])
                expected_page_digest = str(payload["ordered_page_digest"])
                expected_last_identity = str(payload["last_emitted_identity"])
            except (KeyError, TypeError, ValueError) as error:
                raise SourceSelectionError(
                    "cursor_query_mismatch",
                    "TaxSifter continuation belongs to different criteria",
                ) from error
            if (
                native_page <= 0
                or offset <= 0
                or not expected_schema
                or not expected_page_digest
                or not expected_last_identity
            ):
                raise SourceSelectionError(
                    "invalid_cursor",
                    "TaxSifter continuation position is invalid",
                )

        records: list[Mapping[str, Any]] = []
        pages_fetched = 0
        source_urls: list[str] = []
        total_count = 0
        next_page = native_page
        next_offset = offset
        maximum_page = native_page
        native_page_size = DEFAULT_NATIVE_PAGE_SIZE
        source_exhausted = False
        cursor_schema: str | None = None
        cursor_page_digest: str | None = None
        cursor_last_identity: str | None = None

        while limit is None or len(records) < limit:
            parsed = self.search_page(selector, page=next_page)
            pages_fetched += 1
            source_urls.append(parsed.source_page.url)
            total_count = parsed.total_count
            maximum_page = parsed.maximum_page
            native_page_size = parsed.native_page_size
            ordered_identities = [
                _search_record_identity(record) for record in parsed.records
            ]
            page_digest = _ordered_search_page_digest(parsed.records)
            if expected_total is not None and total_count != expected_total:
                raise SourceSchemaError(
                    "TaxSifter result count changed after cursor issuance",
                    url=parsed.source_page.url,
                    details={
                        "cursor_total": expected_total,
                        "current_total": total_count,
                    },
                )
            if (
                expected_schema is not None
                and parsed.source_page.schema_fingerprint != expected_schema
            ):
                raise SourceSchemaError(
                    "TaxSifter search schema changed after cursor issuance",
                    url=parsed.source_page.url,
                    details={
                        "cursor_schema": expected_schema,
                        "current_schema": parsed.source_page.schema_fingerprint,
                    },
                )
            if expected_page_digest is not None and page_digest != expected_page_digest:
                raise SourceSchemaError(
                    "TaxSifter ordered search page changed after cursor issuance",
                    url=parsed.source_page.url,
                    details={
                        "cursor_ordered_page_digest": expected_page_digest,
                        "current_ordered_page_digest": page_digest,
                    },
                )
            expected_total = total_count
            if parsed.source_page.state == ResponseState.NO_RESULT:
                return SearchBatch(
                    records=(),
                    total_count=0,
                    next_cursor=None,
                    pages_fetched=pages_fetched,
                    native_page_size=native_page_size,
                    source_urls=tuple(source_urls),
                )
            if next_offset > len(parsed.records):
                raise SourceSelectionError(
                    "invalid_cursor",
                    "TaxSifter continuation offset exceeds its native page",
                )
            if expected_last_identity is not None:
                if (
                    next_offset == 0
                    or ordered_identities[next_offset - 1] != expected_last_identity
                ):
                    raise SourceSchemaError(
                        "TaxSifter continuation boundary changed after issuance",
                        url=parsed.source_page.url,
                        details={
                            "cursor_last_emitted_identity": (expected_last_identity),
                            "current_boundary_identity": (
                                ordered_identities[next_offset - 1]
                                if next_offset > 0
                                else None
                            ),
                        },
                    )
            expected_schema = None
            expected_page_digest = None
            expected_last_identity = None

            if next_offset == len(parsed.records):
                if next_page >= maximum_page:
                    source_exhausted = True
                    break
                next_page += 1
                next_offset = 0
                continue

            available = parsed.records[next_offset:]
            needed = None if limit is None else limit - len(records)
            selected = available if needed is None else available[:needed]
            records.extend(selected)
            consumed = len(selected)
            next_offset += consumed
            cursor_schema = parsed.source_page.schema_fingerprint
            cursor_page_digest = page_digest
            cursor_last_identity = ordered_identities[next_offset - 1]
            if limit is not None and len(records) >= limit:
                if next_offset == len(parsed.records) and next_page >= maximum_page:
                    source_exhausted = True
                break
            if next_offset < len(parsed.records):
                continue
            if next_page >= maximum_page:
                source_exhausted = True
                break
            next_page += 1
            next_offset = 0

        has_more = not source_exhausted and total_count > 0
        next_cursor = None
        if has_more:
            if (
                cursor_schema is None
                or cursor_page_digest is None
                or cursor_last_identity is None
                or next_offset <= 0
            ):
                raise SourceSelectionError(
                    "invalid_cursor_state",
                    "TaxSifter search could not produce a stable continuation",
                )
            next_cursor = _encode_cursor(
                {
                    "source": self.tenant.source_id,
                    "criteria": criteria,
                    "schema": cursor_schema,
                    "page": next_page,
                    "offset": next_offset,
                    "total": total_count,
                    "ordered_page_digest": cursor_page_digest,
                    "last_emitted_identity": cursor_last_identity,
                }
            )
        return SearchBatch(
            records=tuple(records),
            total_count=total_count,
            next_cursor=next_cursor,
            pages_fetched=pages_fetched,
            native_page_size=native_page_size,
            source_urls=tuple(source_urls),
        )

    def fetch_operation(self, url: str, *, operation: str) -> SourcePage:
        return self.fetch_page(url, operation=operation)

    def fetch_sales(
        self,
        filters: Mapping[str, str | None],
    ) -> tuple[SalesForm, SourcePage]:
        form_page = self.fetch_page(
            urljoin(self.tenant.portal_root, "SalesSearch/SalesSearch.aspx"),
            operation=Operation.SALES,
        )
        form = parse_sales_form(form_page)
        payload = dict(form.defaults)
        for semantic, value in filters.items():
            if value is None:
                continue
            native_name = form.fields.get(semantic)
            if native_name:
                payload[native_name] = str(value)
        submit_name = form.fields.get("submit")
        if submit_name:
            payload[submit_name] = "Search"
        response = self._request("POST", form.action_url, data=payload)
        result_page = _source_page(response, operation=Operation.SALES)
        self._raise_for_page(result_page)
        return form, result_page


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "checksum"}
    body["v"] = CURSOR_VERSION
    envelope = {
        **body,
        "checksum": sha256_fingerprint(body),
    }
    encoded = base64.urlsafe_b64encode(canonical_json(envelope).encode("utf-8")).decode(
        "ascii"
    )
    return f"{CURSOR_PREFIX}{encoded.rstrip('=')}"


def _decode_cursor(cursor: str) -> dict[str, Any]:
    if not cursor.startswith(CURSOR_PREFIX):
        raise SourceSelectionError(
            "invalid_cursor",
            "TaxSifter continuation has an unknown prefix",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceSelectionError(
            "invalid_cursor",
            "TaxSifter continuation is malformed",
        ) from error
    if not isinstance(payload, dict) or payload.get("v") != CURSOR_VERSION:
        raise SourceSelectionError(
            "invalid_cursor",
            "TaxSifter continuation version is unsupported",
        )
    checksum = payload.get("checksum")
    body = {key: value for key, value in payload.items() if key != "checksum"}
    if not isinstance(checksum, str) or checksum != sha256_fingerprint(body):
        raise SourceSelectionError(
            "invalid_cursor",
            "TaxSifter continuation checksum is invalid",
        )
    return body


def _direct_rows(table: Tag) -> list[Tag]:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _direct_cells(row: Tag) -> list[Tag]:
    return row.find_all(["th", "td"], recursive=False)


def _deduplicate_headers(values: Sequence[str]) -> list[str]:
    counts: dict[str, int] = {}
    result = []
    for index, value in enumerate(values):
        base = _slug(value) or f"column_{index + 1}"
        counts[base] = counts.get(base, 0) + 1
        result.append(base if counts[base] == 1 else f"{base}_{counts[base]}")
    return result


def _row_links(row: Tag, source_url: str) -> list[dict[str, str]]:
    links = []
    for link in row.select("a[href]"):
        href = str(link.get("href") or "").strip()
        if not href or href.lower().startswith("javascript:"):
            continue
        links.append(
            {
                "label": _clean(link.get_text(" ", strip=True)) or "",
                "url": urljoin(source_url, unescape(href)),
            }
        )
    return links


def _parse_table(table: Tag, *, source_url: str) -> dict[str, Any]:
    rows = _direct_rows(table)
    if not rows:
        return {
            "id": table.get("id"),
            "caption": None,
            "headers": [],
            "rows": [],
        }
    first_cells = _direct_cells(rows[0])
    has_header = any(cell.name == "th" for cell in first_cells)
    if not has_header and rows[0].get("class"):
        has_header = any(
            "hdr" in str(value).lower() for value in rows[0].get("class", [])
        )
    header_values = [
        _clean(cell.get_text(" ", strip=True)) or ""
        for cell in (first_cells if has_header else [])
    ]
    headers = _deduplicate_headers(header_values)
    data_rows = rows[1:] if has_header else rows
    parsed_rows: list[dict[str, Any]] = []
    for position, row in enumerate(data_rows, start=1):
        cells = _direct_cells(row)
        if not cells:
            continue
        values = [_clean(cell.get_text(" ", strip=True)) for cell in cells]
        if not any(value for value in values):
            continue
        active_headers = (
            headers
            if headers
            else [f"column_{index + 1}" for index in range(len(values))]
        )
        record = {
            active_headers[index]
            if index < len(active_headers)
            else f"column_{index + 1}": value
            for index, value in enumerate(values)
        }
        links = _row_links(row, source_url)
        if links:
            record["links"] = links
        record["native_position"] = position
        parsed_rows.append(record)
    caption = _clean(table.caption.get_text(" ", strip=True)) if table.caption else None
    if caption is None:
        previous = table.find_previous(["h1", "h2", "h3", "div"])
        if previous is not None and previous.name != "div":
            caption = _clean(previous.get_text(" ", strip=True))
    return {
        "id": str(table.get("id") or ""),
        "caption": caption,
        "headers": headers,
        "rows": parsed_rows,
    }


def _parse_key_value_table(table: Tag | None) -> dict[str, Any]:
    if table is None:
        return {}
    result: dict[str, Any] = {}
    for row in _direct_rows(table):
        cells = _direct_cells(row)
        if len(cells) < 2:
            continue
        key = _slug(cells[0].get_text(" ", strip=True))
        value = _clean(cells[1].get_text(" ", strip=True))
        if key:
            result[key] = value
    caption = _clean(table.caption.get_text(" ", strip=True)) if table.caption else None
    if caption:
        result["_caption"] = caption
        year = re.search(r"\b(19|20|21)\d{2}\b", caption)
        if year:
            result["_tax_year"] = year.group(0)
    return result


def _typed_money_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    money_tokens = (
        "value",
        "price",
        "amount",
        "tax",
        "fee",
        "interest",
        "balance",
        "paid",
        "charged",
        "total",
        "exempt",
        "assessment",
    )
    result = dict(row)
    for key, value in row.items():
        if key in {"links", "native_position"}:
            continue
        if any(token in key for token in money_tokens):
            result[f"{key}_money"] = _money(value)
    return result


def _operation_from_link(label: str, href: str) -> str | None:
    combined = f"{label} {urlparse(href).path}".lower()
    if "apprais" in combined:
        return Operation.APPRAISAL
    if "treasur" in combined:
        return Operation.TREASURER
    if "assessor" in combined:
        return Operation.ASSESSOR
    if "salessearch" in combined or "sales search" in combined:
        return Operation.SALES
    return None


def _page_operation_links(
    soup: BeautifulSoup,
    *,
    source_url: str,
) -> dict[str, str]:
    links: dict[str, str] = {}
    for node in soup.select("a[href]"):
        label = _clean(node.get_text(" ", strip=True)) or ""
        href = urljoin(source_url, unescape(str(node.get("href") or "")))
        operation = _operation_from_link(label, href)
        if operation and operation not in links:
            links[operation] = href
    return links


def _external_pivots(
    soup: BeautifulSoup,
    *,
    source_url: str,
    tenant: TenantConfig,
) -> list[dict[str, Any]]:
    pivots: list[dict[str, Any]] = []
    for node in soup.select("a[href]"):
        label = _clean(node.get_text(" ", strip=True)) or ""
        href = urljoin(source_url, unescape(str(node.get("href") or "")))
        lowered = f"{label} {href}".lower()
        if "mapsifter" in lowered:
            pivots.append(
                {
                    "kind": "mapsifter_parcel_map",
                    "url": href,
                    "label": label,
                    "lineage_id": MAP_LINEAGE,
                    "relationship": "same_assessor_parcel_map_representation",
                }
            )
        elif "reetsifter" in lowered:
            pivots.append(
                {
                    "kind": "real_estate_excise_search",
                    "url": href,
                    "label": label,
                    "lineage_id": RECORDER_LINEAGE,
                    "relationship": "recorded_transfer_excise_pivot",
                }
            )
    if tenant.digital_archives_title_id is not None:
        pivots.append(
            {
                "kind": "washington_digital_archives_recorded_land_title",
                "url": (
                    "https://digitalarchives.wa.gov/Collections/TitleInfo/"
                    f"{tenant.digital_archives_title_id}"
                ),
                "title_id": tenant.digital_archives_title_id,
                "lineage_id": RECORDER_LINEAGE,
                "relationship": "independent_recorded_instrument_index",
            }
        )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for pivot in pivots:
        unique[(str(pivot["kind"]), str(pivot["url"]))] = pivot
    return list(unique.values())


def parse_search_page(
    page: SourcePage,
    tenant: TenantConfig,
    *,
    native_page: int,
) -> SearchPage:
    """Parse deterministic result cards and their native operation links."""

    soup = BeautifulSoup(page.html, "lxml")
    count_node = soup.select_one(".resultCount")
    count_match = (
        re.search(
            r"([0-9,]+)\s+records?\s+found",
            count_node.get_text(" ", strip=True),
            flags=re.I,
        )
        if count_node
        else None
    )
    if page.state == ResponseState.NO_RESULT:
        total_count = int(count_match.group(1).replace(",", "")) if count_match else 0
        return SearchPage(
            records=(),
            total_count=total_count,
            native_page=native_page,
            maximum_page=native_page,
            native_page_size=DEFAULT_NATIVE_PAGE_SIZE,
            source_page=page,
        )
    if count_match is None:
        raise SourceSchemaError(
            "TaxSifter search result lacks its published result count",
            url=page.url,
            details={"response_state": page.state.value},
        )
    total_count = int(count_match.group(1).replace(",", ""))
    records: list[dict[str, Any]] = []
    for position, panel in enumerate(
        soup.select('[id*="pnlResult"]'),
        start=1,
    ):
        operation_links: dict[str, str] = {}
        for link in panel.select("a[href]"):
            label = _clean(link.get_text(" ", strip=True)) or ""
            href = urljoin(page.url, unescape(str(link.get("href") or "")))
            operation = _operation_from_link(label, href)
            if operation:
                operation_links[operation] = href
        assessor_url = operation_links.get(Operation.ASSESSOR)
        if assessor_url is None:
            raise SourceSchemaError(
                "TaxSifter result card lacks a deterministic assessor link",
                url=page.url,
                details={"native_position": position},
            )
        locator = _account_locator_from_url(assessor_url, tenant)
        parcel_number = locator["parcel_number"]
        for operation in (
            Operation.TREASURER,
            Operation.APPRAISAL,
        ):
            operation_url = operation_links.get(operation)
            if operation_url is None:
                continue
            operation_locator = _account_locator_from_url(operation_url, tenant)
            _validate_account_consistency(
                locator,
                operation_locator,
                tenant=tenant,
                operation=operation,
                source_url=operation_url,
            )
        details_node = panel.select_one(".details")
        display_lines = []
        if details_node:
            display_lines = [
                _clean(node.get_text(" ", strip=True))
                for node in details_node.find_all("div", recursive=False)
            ]
            display_lines = [value for value in display_lines if value]
        canonical_ref = canonical_property_ref(
            tenant.source_id,
            tenant.county_geoid,
            "property_search_result",
            locator["native_id"],
        )
        parcel_join = _parcel_join(tenant, parcel_number)
        record = {
            "canonical_ref": canonical_ref,
            "evidence_ref": canonical_ref,
            "source_id": tenant.source_id,
            "source_url": page.url,
            "record_kind": "property_search_result",
            "county_geoid": tenant.county_geoid,
            "native_parcel_id": str(parcel_number),
            "parcel_number": str(parcel_number),
            "key_id": locator["key_id"],
            "type_id": locator["type_id"],
            "account_occurrence": {
                key: locator[key]
                for key in ("source_id", "key_id", "type_id", "native_id")
            },
            "parcel_join": parcel_join,
            "display_lines": display_lines,
            "native_position": position,
            "operation_links": operation_links,
            "provenance": page.provenance(
                tenant,
                **OPERATION_LINEAGES[Operation.SEARCH],
            ),
            "native_joins": {
                STATEWIDE_PARCEL_SOURCE_ID: {
                    **parcel_join,
                    "relationship": "statewide_parcel_to_county_property_account",
                    "lineage_interpretation": (
                        "same_county_assessor_origin_not_independent_corroboration"
                    ),
                },
                tenant.source_id: {
                    **parcel_join,
                    "key_id": locator["key_id"],
                    "type_id": locator["type_id"],
                    "account_occurrence_native_id": locator["native_id"],
                    "relationship": "search_result_to_detail_operations",
                },
            },
            "external_pivots": _external_pivots(
                panel,
                source_url=page.url,
                tenant=tenant,
            ),
        }
        records.append(record)
    if total_count > 0 and not records:
        raise SourceSchemaError(
            "TaxSifter published a nonzero count without recognizable result cards",
            url=page.url,
            details={"total_count": total_count},
        )

    pager_values = []
    for link in soup.select(".pager a[href]"):
        parsed = parse_qs(urlparse(str(link.get("href") or "")).query)
        for value in parsed.get("page", []):
            if str(value).isdigit():
                pager_values.append(int(value))
    maximum_page = max(pager_values, default=native_page)
    native_page_size = (
        max(len(records), DEFAULT_NATIVE_PAGE_SIZE)
        if native_page < maximum_page
        else DEFAULT_NATIVE_PAGE_SIZE
    )
    return SearchPage(
        records=tuple(records),
        total_count=total_count,
        native_page=native_page,
        maximum_page=maximum_page,
        native_page_size=native_page_size,
        source_page=page,
    )


def _value_table(table: Tag | None) -> dict[str, Any]:
    raw = _parse_key_value_table(table)
    if not raw:
        return {}
    return {
        "caption": raw.get("_caption"),
        "tax_year": raw.get("_tax_year"),
        "fields": {
            key: {
                "raw": value,
                "amount": _money(value)["amount"],
                "currency": "USD",
            }
            for key, value in raw.items()
            if not key.startswith("_")
        },
    }


def _table_by_suffix(soup: BeautifulSoup, suffix: str) -> Tag | None:
    node = soup.find("table", id=re.compile(re.escape(suffix) + r"$", re.I))
    return node if isinstance(node, Tag) else None


def _parcel_identity(
    soup: BeautifulSoup,
    *,
    source_url: str,
) -> dict[str, Any]:
    parcel_number = _suffix_text(soup, "ParcelOwnerInfo1_lbParcelNumber")
    if parcel_number is None:
        raise SourceSchemaError(
            "TaxSifter detail lacks a parcel identifier",
            url=source_url,
        )
    source_query = parse_qs(urlparse(source_url).query)
    form = soup.select_one("form")
    form_url = (
        urljoin(source_url, str(form.get("action") or source_url))
        if isinstance(form, Tag)
        else source_url
    )
    form_query = parse_qs(urlparse(form_url).query)

    def query_value(query: Mapping[str, Sequence[str]], name: str) -> str | None:
        for key, values in query.items():
            if key.lower() == name.lower() and values:
                return str(values[0])
        return None

    source_locator = {
        "parcel_number": query_value(source_query, "parcelNumber"),
        "key_id": query_value(source_query, "keyId"),
        "type_id": query_value(source_query, "typeID"),
    }
    form_locator = {
        "parcel_number": query_value(form_query, "parcelNumber"),
        "key_id": query_value(form_query, "keyId"),
        "type_id": query_value(form_query, "typeID"),
    }
    for field in ("parcel_number", "key_id", "type_id"):
        if (
            source_locator[field] is not None
            and form_locator[field] is not None
            and source_locator[field] != form_locator[field]
        ):
            raise SourceSchemaError(
                "TaxSifter detail URL and form action identify different accounts",
                url=source_url,
                details={
                    "field": field,
                    "response_url_value": source_locator[field],
                    "form_action_value": form_locator[field],
                },
            )
    for locator_name, locator in (
        ("response_url", source_locator),
        ("form_action", form_locator),
    ):
        if (
            locator["parcel_number"] is not None
            and str(parcel_number) != locator["parcel_number"]
        ):
            raise SourceSchemaError(
                "TaxSifter rendered parcel differs from its account locator",
                url=source_url,
                details={
                    "locator": locator_name,
                    "rendered_parcel": str(parcel_number),
                    "locator_parcel": locator["parcel_number"],
                },
            )

    mailing_lines = [
        _suffix_text(soup, "ParcelOwnerInfo1_lbAddress"),
        _suffix_text(soup, "ParcelOwnerInfo1_lbAddress2"),
    ]
    mailing_lines = [value for value in mailing_lines if value]
    city = _suffix_text(soup, "ParcelOwnerInfo1_lbCity")
    state = _suffix_text(soup, "ParcelOwnerInfo1_lbState")
    postal_code = _suffix_text(soup, "ParcelOwnerInfo1_lbZip")
    mailing_csz = " ".join(value for value in (city, state, postal_code) if value)
    return {
        "parcel_number": str(parcel_number),
        "key_id": _string(source_locator["key_id"] or form_locator["key_id"]),
        "type_id": _string(source_locator["type_id"] or form_locator["type_id"]),
        "owner_name": _suffix_text(soup, "ParcelOwnerInfo1_lbOwnerName"),
        "mailing_address": {
            "lines": mailing_lines,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "raw": ", ".join([*mailing_lines, mailing_csz])
            if mailing_lines or mailing_csz
            else None,
        },
        "situs_address": _suffix_text(soup, "ParcelOwnerInfo1_lbSitus"),
        "map_number": _suffix_text(soup, "ParcelOwnerInfo1_lbMapNumber"),
        "property_code_label": _suffix_text(
            soup,
            "ParcelOwnerInfo1_lbMID1Label",
        ),
        "property_code": _suffix_text(
            soup,
            "ParcelOwnerInfo1_lbMID1Value",
        ),
        "status": _suffix_text(soup, "ParcelOwnerInfo1_lbStatus"),
        "legal_description": _suffix_text(soup, "ParcelOwnerInfo1_lbLegal"),
        "parcel_comment": _suffix_text(soup, "ParcelOwnerInfo1_lbComment"),
    }


def _normalize_sale_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    tenant: TenantConfig,
) -> list[dict[str, Any]]:
    sales = []
    for row in rows:
        sale = _typed_money_fields(row)
        parcel_number = (
            _string(row.get("parcel_number"))
            or _string(row.get("parcel"))
            or _string(row.get("parcel_no"))
        )
        date_raw = row.get("sale_date") or row.get("date") or row.get("recording_date")
        sale["sale_date_iso"] = _date_iso(date_raw)
        document = (
            _string(row.get("sales_document"))
            or _string(row.get("sale_document"))
            or _string(row.get("document"))
            or _string(row.get("instrument_number"))
        )
        excise = (
            _string(row.get("excise"))
            or _string(row.get("excise_number"))
            or _string(row.get("excise_no"))
        )
        sale["parcel_number"] = parcel_number
        sale["sale_document"] = document
        sale["excise_number"] = excise
        sale["recording_join"] = {
            "lineage_id": RECORDER_LINEAGE,
            "relationship": "recorded_instrument_candidate",
            "instrument_number": document,
            "excise_number": excise,
            "recording_date": sale["sale_date_iso"],
            "grantor": _string(row.get("grantor")),
            "grantee": _string(row.get("grantee")),
            "digital_archives_title_id": tenant.digital_archives_title_id,
        }
        sales.append(sale)
    return sales


_SALE_RETRIEVAL_FIELDS = frozenset(
    {
        "native_position",
        "position",
        "retrieval_snapshot",
        "source_url",
        "retrieved_at",
    }
)


def _sale_identity(
    normalized: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Build a stable sale identity after canonical alias normalization."""

    native_fields = {
        "parcel_number": _string(normalized.get("parcel_number")),
        "sale_date_iso": _string(normalized.get("sale_date_iso")),
        "sale_document": _string(normalized.get("sale_document")),
        "excise_number": _string(normalized.get("excise_number")),
    }
    native_fields = {
        key: value for key, value in native_fields.items() if value is not None
    }
    has_transaction_locator = bool(
        native_fields.get("sale_document")
        or native_fields.get("excise_number")
        or (native_fields.get("parcel_number") and native_fields.get("sale_date_iso"))
    )
    if has_transaction_locator:
        fingerprint = sha256_fingerprint(native_fields)
        return (
            f"native-{fingerprint}",
            {
                "strategy": "normalized_native_fields",
                "fields": native_fields,
                "fingerprint": fingerprint,
            },
        )

    canonical_row = {
        key: value
        for key, value in normalized.items()
        if key not in _SALE_RETRIEVAL_FIELDS
    }
    fingerprint = sha256_fingerprint(canonical_row)
    return (
        f"row-{fingerprint}",
        {
            "strategy": "canonical_row_hash",
            "excluded_fields": sorted(_SALE_RETRIEVAL_FIELDS),
            "fingerprint": fingerprint,
        },
    )


def parse_assessor_detail(
    page: SourcePage,
    tenant: TenantConfig,
) -> dict[str, Any]:
    """Parse a rich assessor page while retaining native row labels."""

    soup = BeautifulSoup(page.html, "lxml")
    identity = _parcel_identity(soup, source_url=page.url)
    parcel_number = str(identity["parcel_number"])
    occurrence = _account_occurrence(
        tenant,
        key_id=identity["key_id"],
        type_id=identity["type_id"],
        source_url=page.url,
    )
    parcel_join = _parcel_join(tenant, parcel_number)
    ownership_table = soup.find(
        "table",
        id=re.compile(r"grdParcelOwnership$", re.I),
    )
    sales_table = soup.find("table", id=re.compile(r"(ctl02_)?GridView1$", re.I))
    permit_table = soup.find(
        "table",
        id=re.compile(r"grdBuildingPermits$", re.I),
    )
    valuation_table = soup.find(
        "table",
        id=re.compile(r"grdValuations$", re.I),
    )
    comments_table = soup.find(
        "table",
        id=re.compile(r"grdParcelComments$", re.I),
    )
    ownership = (
        _parse_table(ownership_table, source_url=page.url)["rows"]
        if isinstance(ownership_table, Tag)
        else []
    )
    raw_sales = (
        _parse_table(sales_table, source_url=page.url)["rows"]
        if isinstance(sales_table, Tag)
        else []
    )
    permits = (
        [
            {
                **row,
                "date_iso": _date_iso(row.get("date")),
                "amount_money": _money(row.get("amount")),
            }
            for row in _parse_table(permit_table, source_url=page.url)["rows"]
        ]
        if isinstance(permit_table, Tag)
        else []
    )
    valuations = (
        [
            _typed_money_fields(row)
            for row in _parse_table(
                valuation_table,
                source_url=page.url,
            )["rows"]
        ]
        if isinstance(valuation_table, Tag)
        else []
    )
    comments = (
        _parse_table(comments_table, source_url=page.url)["rows"]
        if isinstance(comments_table, Tag)
        else []
    )
    operation_links = _page_operation_links(soup, source_url=page.url)
    canonical_ref = canonical_property_ref(
        tenant.source_id,
        tenant.county_geoid,
        "assessor_property_account",
        occurrence["native_id"],
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": tenant.source_id,
        "source_url": page.url,
        "record_kind": "assessor_property_account",
        "county_geoid": tenant.county_geoid,
        "native_parcel_id": parcel_number,
        "account_occurrence": occurrence,
        "parcel_join": parcel_join,
        "parcel": identity,
        "market_value": _value_table(_table_by_suffix(soup, "dvMarketValues")),
        "taxable_value": _value_table(_table_by_suffix(soup, "dvTaxableValues")),
        "assessment_data": _parse_key_value_table(
            _table_by_suffix(soup, "dvAssessmentData")
        ),
        "ownership": ownership,
        "sales_history": _normalize_sale_rows(raw_sales, tenant=tenant),
        "building_permits": permits,
        "valuation_history": valuations,
        "parcel_comments": comments,
        "operation_links": operation_links,
        "external_pivots": _external_pivots(
            soup,
            source_url=page.url,
            tenant=tenant,
        ),
        "provenance": page.provenance(
            tenant,
            **OPERATION_LINEAGES[Operation.ASSESSOR],
        ),
        "native_joins": {
            STATEWIDE_PARCEL_SOURCE_ID: {
                **parcel_join,
                "relationship": "statewide_parcel_to_assessor_account",
                "lineage_interpretation": (
                    "same_county_assessor_origin_not_independent_corroboration"
                ),
            },
            tenant.source_id: {
                **parcel_join,
                "key_id": occurrence["key_id"],
                "type_id": occurrence["type_id"],
                "account_occurrence_native_id": occurrence["native_id"],
                "relationship": "assessor_to_treasurer_appraisal_operations",
            },
            "county_auditor_recorded_instrument": {
                "candidates": [
                    sale["recording_join"]
                    for sale in _normalize_sale_rows(raw_sales, tenant=tenant)
                ],
                "relationship": "independent_recorded_instrument_candidate",
            },
        },
    }


def parse_treasurer_detail(
    page: SourcePage,
    tenant: TenantConfig,
) -> dict[str, Any]:
    soup = BeautifulSoup(page.html, "lxml")
    identity = _parcel_identity(soup, source_url=page.url)
    parcel_number = str(identity["parcel_number"])
    occurrence = _account_occurrence(
        tenant,
        key_id=identity["key_id"],
        type_id=identity["type_id"],
        source_url=page.url,
    )
    parcel_join = _parcel_join(tenant, parcel_number)
    current = soup.find(
        "table",
        id=re.compile(r"CurrentTaxYear1_GridView1$", re.I),
    )
    balances = soup.find(
        "table",
        id=re.compile(r"CurrentTaxYearInterest1_GridView1$", re.I),
    )
    if current is None and balances is None:
        raise SourceSchemaError(
            "TaxSifter treasurer page lacks current-tax and balance tables",
            url=page.url,
        )
    current_rows = (
        [
            _typed_money_fields(row)
            for row in _parse_table(current, source_url=page.url)["rows"]
        ]
        if isinstance(current, Tag)
        else []
    )
    balance_rows = (
        [
            _typed_money_fields(row)
            for row in _parse_table(balances, source_url=page.url)["rows"]
        ]
        if isinstance(balances, Tag)
        else []
    )
    receipts: list[dict[str, Any]] = []
    for table in soup.select("table.dataGridSecondary"):
        parsed = _parse_table(table, source_url=page.url)
        for row in parsed["rows"]:
            receipts.append(
                {
                    **_typed_money_fields(row),
                    "receipt_date_iso": _date_iso(row.get("receipt_date")),
                }
            )
    statement_links = []
    for link in soup.select('a[href*="StatementDetails.aspx"]'):
        href = urljoin(page.url, unescape(str(link.get("href") or "")))
        statement_links.append(
            {
                "statement_number": _clean(link.get_text(" ", strip=True)),
                "url": href,
            }
        )
    canonical_ref = canonical_property_ref(
        tenant.source_id,
        tenant.county_geoid,
        "treasurer_tax_account",
        occurrence["native_id"],
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": tenant.source_id,
        "source_url": page.url,
        "record_kind": "treasurer_tax_account",
        "county_geoid": tenant.county_geoid,
        "native_parcel_id": parcel_number,
        "account_occurrence": occurrence,
        "parcel_join": parcel_join,
        "parcel": identity,
        "tax_year": page.roll_year,
        "current_tax_year": current_rows,
        "balances_due": balance_rows,
        "payment_receipts": receipts,
        "statement_links": statement_links,
        "operation_links": _page_operation_links(soup, source_url=page.url),
        "provenance": page.provenance(
            tenant,
            **OPERATION_LINEAGES[Operation.TREASURER],
        ),
        "native_joins": {
            tenant.source_id: {
                **parcel_join,
                "key_id": occurrence["key_id"],
                "type_id": occurrence["type_id"],
                "account_occurrence_native_id": occurrence["native_id"],
                "relationship": "treasurer_to_assessor_account",
            }
        },
    }


def parse_appraisal_detail(
    page: SourcePage,
    tenant: TenantConfig,
) -> dict[str, Any]:
    soup = BeautifulSoup(page.html, "lxml")
    identity = _parcel_identity(soup, source_url=page.url)
    parcel_number = str(identity["parcel_number"])
    occurrence = _account_occurrence(
        tenant,
        key_id=identity["key_id"],
        type_id=identity["type_id"],
        source_url=page.url,
    )
    parcel_join = _parcel_join(tenant, parcel_number)
    sections = []
    for table in soup.select(".sliceContainer table, #cphContent_pnlContainer table"):
        parsed = _parse_table(table, source_url=page.url)
        if parsed["rows"]:
            sections.append(parsed)
    if not sections:
        for table in soup.select("table.dataGrid[id]"):
            parsed = _parse_table(table, source_url=page.url)
            if parsed["rows"]:
                sections.append(parsed)
    canonical_ref = canonical_property_ref(
        tenant.source_id,
        tenant.county_geoid,
        "appraisal_detail",
        occurrence["native_id"],
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": tenant.source_id,
        "source_url": page.url,
        "record_kind": "appraisal_detail",
        "county_geoid": tenant.county_geoid,
        "native_parcel_id": parcel_number,
        "account_occurrence": occurrence,
        "parcel_join": parcel_join,
        "parcel": identity,
        "sections": sections,
        "operation_links": _page_operation_links(soup, source_url=page.url),
        "provenance": page.provenance(
            tenant,
            **OPERATION_LINEAGES[Operation.APPRAISAL],
        ),
        "native_joins": {
            tenant.source_id: {
                **parcel_join,
                "key_id": occurrence["key_id"],
                "type_id": occurrence["type_id"],
                "account_occurrence_native_id": occurrence["native_id"],
                "relationship": "appraisal_to_assessor_account",
            }
        },
    }


SALES_FIELD_SUFFIXES: Mapping[str, tuple[str, ...]] = {
    "parcel": ("txtparcelNumber",),
    "date_from": ("txtdateFrom",),
    "date_to": ("txtdateTo",),
    "price_from": ("txtpriceFrom",),
    "price_to": ("txtpriceTo",),
    "acres_from": ("txtacresFrom",),
    "acres_to": ("txtacresTo",),
    "year_built_from": ("txtyearBuiltFrom",),
    "year_built_to": ("txtyearBuiltTo",),
    "map_number": ("txtmapNumber",),
    "township": ("ddlTownship",),
    "range": ("ddlRange",),
    "section": ("ddlSection",),
    "sale_type": ("ddlSaleType",),
    "assessment_type": ("ddlAssessmentType",),
    "building_style": ("ddlBuildingStyle",),
    "building_type": ("ddlSliceType",),
    "dor_codes": ("lbxDORCodes",),
    "page_index": ("hdfSelectedPageIndex",),
    "submit": ("searchbutton",),
}


def parse_sales_form(page: SourcePage) -> SalesForm:
    """Discover county-enabled sale-search controls and their native names."""

    soup = BeautifulSoup(page.html, "lxml")
    form = soup.select_one("form")
    if form is None:
        raise SourceSchemaError(
            "TaxSifter sales page lacks an ASP.NET form",
            url=page.url,
        )
    controls = {
        str(node.get("name")): node
        for node in form.select("[name]")
        if node.get("name")
    }
    fields: dict[str, str] = {}
    for semantic, suffixes in SALES_FIELD_SUFFIXES.items():
        for name in controls:
            if any(name.lower().endswith(suffix.lower()) for suffix in suffixes):
                fields[semantic] = name
                break
    if "parcel" not in fields or "submit" not in fields:
        raise SourceSchemaError(
            "TaxSifter sales form lacks its parcel/search controls",
            url=page.url,
            details={"discovered_fields": sorted(fields)},
        )
    defaults = _hidden_fields(soup)
    options: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for semantic, name in fields.items():
        node = controls[name]
        if node.name == "select":
            choices = []
            for option in node.select("option"):
                choice = {
                    "value": str(option.get("value") or ""),
                    "label": _clean(option.get_text(" ", strip=True)),
                    "selected": option.has_attr("selected"),
                }
                choices.append(choice)
            options[semantic] = tuple(choices)
    return SalesForm(
        action_url=urljoin(page.url, str(form.get("action") or page.url)),
        fields=fields,
        options=options,
        defaults=defaults,
        source_page=page,
    )


def parse_sales_results(
    page: SourcePage,
    tenant: TenantConfig,
) -> tuple[Mapping[str, Any], ...]:
    """Normalize sale-search results while preserving their recorder joins."""

    soup = BeautifulSoup(page.html, "lxml")
    count_node = soup.select_one(".resultCount")
    count_match = (
        re.search(
            r"([0-9,]+)\s+records?\s+found",
            count_node.get_text(" ", strip=True),
            flags=re.I,
        )
        if count_node
        else None
    )
    if page.state == ResponseState.NO_RESULT:
        return ()
    candidate_rows: list[dict[str, Any]] = []
    for table in soup.select("table.dataGrid"):
        parsed = _parse_table(table, source_url=page.url)
        candidate_rows.extend(parsed["rows"])
    for panel in soup.select('[id*="pnlResult"]'):
        values = [
            _clean(node.get_text(" ", strip=True))
            for node in panel.select(".details > div")
        ]
        values = [value for value in values if value]
        if values:
            candidate_rows.append(
                {
                    "display_lines": values,
                    "links": _row_links(panel, page.url),
                    "native_position": len(candidate_rows) + 1,
                }
            )
    if (
        count_match
        and int(count_match.group(1).replace(",", "")) > 0
        and not candidate_rows
    ):
        raise SourceSchemaError(
            "TaxSifter sales search published results in an unrecognized shape",
            url=page.url,
        )
    records = []
    for position, row in enumerate(candidate_rows, start=1):
        normalized = _normalize_sale_rows([row], tenant=tenant)[0]
        parcel_number = _string(normalized.get("parcel_number"))
        if (
            _slug(parcel_number) == "multiple_parcels_in_sale"
            and normalized.get("sale_date_iso") is None
            and normalized.get("sale_document") is None
            and normalized.get("excise_number") is None
        ):
            continue
        native_id, identity = _sale_identity(normalized)
        canonical_ref = canonical_property_ref(
            tenant.source_id,
            tenant.county_geoid,
            "assessor_sale_search_result",
            native_id,
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": tenant.source_id,
                "source_url": page.url,
                "record_kind": "assessor_sale_search_result",
                "county_geoid": tenant.county_geoid,
                "native_parcel_id": parcel_number,
                "sale_identity": identity,
                "sale": normalized,
                "native_position": position,
                "provenance": page.provenance(
                    tenant,
                    **OPERATION_LINEAGES[Operation.SALES],
                ),
                "native_joins": {
                    tenant.source_id: {
                        "parcel_number": parcel_number,
                        "relationship": "sale_search_to_assessor_account",
                    },
                    "county_auditor_recorded_instrument": normalized["recording_join"],
                },
            }
        )
    return tuple(records)


def _sales_published_count(page: SourcePage) -> int | None:
    soup = BeautifulSoup(page.html, "lxml")
    count_node = soup.select_one(".resultCount")
    if count_node is None:
        return 0 if page.state == ResponseState.NO_RESULT else None
    match = re.search(
        r"([0-9,]+)\s+records?\s+found",
        count_node.get_text(" ", strip=True),
        flags=re.I,
    )
    return int(match.group(1).replace(",", "")) if match else None


def _sales_pagination_observation(
    form: SalesForm,
    page: SourcePage,
    *,
    returned_records: int,
) -> dict[str, Any]:
    soup = BeautifulSoup(page.html, "lxml")
    page_field = form.fields.get("page_index")
    page_value = None
    if page_field:
        page_node = soup.find(attrs={"name": page_field})
        if isinstance(page_node, Tag):
            page_value = _string(page_node.get("value"))
    published_count = _sales_published_count(page)
    exhaustive = published_count is not None and published_count <= returned_records
    return {
        "state": SALES_PAGINATION_STATE,
        "published_result_count": published_count,
        "current_native_page": page_value,
        "returned_native_records": returned_records,
        "current_response_exhaustive": exhaustive,
        "continuation_verified": False,
        "note": SALES_PAGINATION_NOTE,
    }


def _tenant(value: str) -> TenantConfig:
    tenant = TENANTS_BY_KEY.get(value) or TENANTS_BY_SOURCE.get(value)
    if tenant is None:
        raise SourceSelectionError(
            "unknown_source",
            f"Unknown Washington TaxSifter source: {value}",
        )
    return tenant


def _tenant_from_args(args: argparse.Namespace) -> TenantConfig:
    value = getattr(args, "county", None) or getattr(args, "source", None)
    if not value:
        raise SourceSelectionError(
            "source_required",
            "Select a TaxSifter county or source ID",
        )
    return _tenant(str(value))


def _source_record(tenant: TenantConfig) -> dict[str, Any]:
    metadata = tenant.source.to_dict()
    metadata.update(
        {
            "county_key": tenant.key,
            "county_name": tenant.county_name,
            "county_geoid": tenant.county_geoid,
            "portal_root": tenant.portal_root,
            "search_url": urljoin(tenant.portal_root, tenant.search_path),
            "observed_hosts": list(tenant.observed_hosts),
            "access_state": tenant.access_state,
            "verified_operations": list(tenant.verified_operations),
            "observed_capabilities": list(tenant.observed_capabilities),
            "sentinel_query": tenant.sentinel_query,
            "data_link_discovery": discover_data_link(
                tenant.observed_data_link
            ).to_dict(),
            "response_states": [state.value for state in ResponseState],
            "native_search_pagination": {
                "mechanism": "q_and_page_query_parameters",
                "native_page_size_observed": DEFAULT_NATIVE_PAGE_SIZE,
                "query_bound_cursor": True,
                "cursor_version": CURSOR_VERSION,
                "cursor_integrity": [
                    "checksum",
                    "source",
                    "criteria",
                    "schema",
                    "total",
                    "ordered_page_digest",
                    "offset",
                    "last_emitted_identity",
                ],
            },
            "native_sales_pagination": {
                "state": SALES_PAGINATION_STATE,
                "continuation_verified": False,
                "note": SALES_PAGINATION_NOTE,
            },
            "identity_contract": {
                "account_occurrence": [
                    "source_id",
                    "key_id",
                    "type_id",
                ],
                "parcel_join": ["county_geoid", "parcel_number"],
                "sale_occurrence": [
                    "parcel_number",
                    "sale_date_iso",
                    "sale_document",
                    "excise_number",
                ],
            },
            "operation_contract": {
                "search": tenant.search_path,
                "assessor": "Assessor.aspx?keyId={key_id}&parcelNumber={parcel}&typeID={type_id}",
                "treasurer": "Treasurer.aspx?keyId={key_id}&parcelNumber={parcel}&typeID={type_id}",
                "appraisal": "AppraisalDetails.aspx?keyId={key_id}&parcelNumber={parcel}&typeID={type_id}",
                "sales": "SalesSearch/SalesSearch.aspx (ASP.NET postback)",
            },
        }
    )
    return metadata


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "source_family_id": UMBRELLA_SOURCE_ID,
        "platform_family": PLATFORM_FAMILY,
        "observed_at": "2026-07-30",
        "source_count": len(TENANTS),
        "live_verified_count": len(VERIFIED_TENANT_KEYS),
        "sources": [_source_record(tenant) for tenant in TENANTS],
        "family_observations": {
            "ordinary_session_flow": (
                "fresh target GET -> Disclaimer.aspx -> replay returned hidden "
                "fields with btnAgree -> retry target in the same session"
            ),
            "verified_counties": list(VERIFIED_TENANT_KEYS),
            "mason_state": (
                "challenge observed on Mason's HTTP search operation; other "
                "deployments retain their own observed states"
            ),
            "lineage": {
                "assessor_family": ASSESSOR_LINEAGE,
                "treasurer": TREASURER_LINEAGE,
                "recorder": RECORDER_LINEAGE,
                "map": MAP_LINEAGE,
            },
        },
        "methodology_learnings": [
            {
                "scope": "session_state",
                "learning": (
                    "A fresh-session disclaimer is an ordinary WebForms state "
                    "transition and does not by itself indicate unavailability."
                ),
            },
            {
                "scope": "deployment_variance",
                "learning": (
                    "Root, nested-path, legacy redirect, and PublicAccessNow "
                    "deployments share operation shapes but retain county "
                    "field and access observations."
                ),
            },
            {
                "scope": "evidence_lineage",
                "learning": (
                    "Assessor search/detail/appraisal/sales/permit/map views "
                    "are same-lineage representations; auditor instruments "
                    "remain independently attributable."
                ),
            },
        ],
    }


def _build_query(
    tenant: TenantConfig,
    *,
    operation: str,
    parameters: Mapping[str, Any],
    requested_limit: int | None,
    cursor: str | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=tenant.source,
        jurisdiction=tenant.jurisdiction,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata={
                "response_state_contract": [state.value for state in ResponseState],
                "continuation_contract": (
                    "query_count_bound_native_page_and_offset"
                    if operation == "search"
                    else "none"
                ),
                "output_schema_version": OUTPUT_SCHEMA_VERSION,
            },
        ),
    )


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            count,
        )
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _new_client(
    args: argparse.Namespace,
    tenant: TenantConfig,
) -> TaxSifterClient:
    return TaxSifterClient(
        tenant,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )


def _selected_client(
    client: Any,
    tenant: TenantConfig,
) -> Any:
    if isinstance(client, Mapping):
        return client.get(tenant.key) or client.get(tenant.source_id)
    return client


def _error_state(error: PublicRecordsHTTPError) -> str:
    if isinstance(error, SourceChallengeError):
        return ResponseState.CHALLENGE
    if isinstance(error, SourceMaintenanceError):
        return ResponseState.MAINTENANCE
    if isinstance(error, UnresolvedDisclaimerError):
        return ResponseState.DISCLAIMER
    if isinstance(error, SourceSchemaError):
        return ResponseState.SCHEMA_ERROR
    return "transport_error"


def _public_failure(
    query: PublicRecordsQuery,
    error: Exception,
    *,
    records: Sequence[Mapping[str, Any]] = (),
    warnings: Sequence[str] = (),
) -> PublicRecordsResult:
    if isinstance(error, PublicRecordsHTTPError):
        if records:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                [error.to_contract_error()],
                records=records,
                warnings=warnings,
            )
        return failure_result(query, error, warnings=warnings)
    if isinstance(error, SourceSelectionError):
        return PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            records=records,
            warnings=warnings,
        )
    return PublicRecordsResult.failure(
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
        records=records,
        warnings=warnings,
    )


def _search_result(
    args: argparse.Namespace,
    tenant: TenantConfig,
    *,
    client: Any,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        tenant,
        operation="search",
        parameters={"selector": args.query},
        requested_limit=args.limit,
        cursor=args.cursor,
    )
    try:
        active = client or _new_client(args, tenant)
        batch = active.search(
            str(args.query),
            limit=args.limit,
            cursor=args.cursor,
        )
        records = [dict(record) for record in batch.records]
        snapshot = {
            "total_matching_records_at_retrieval": batch.total_count,
            "window_returned_records": len(records),
            "pages_fetched": batch.pages_fetched,
            "native_page_size_observed": batch.native_page_size,
            "continuation_available": batch.next_cursor is not None,
            "source_urls": list(batch.source_urls),
        }
        for record in records:
            record["retrieval_snapshot"] = snapshot
        result = PublicRecordsResult.success(
            query,
            records,
            next_cursor=batch.next_cursor,
            warnings=tenant.notes,
        )
    except (
        PublicRecordsHTTPError,
        SourceSelectionError,
        TypeError,
        ValueError,
    ) as error:
        result = _public_failure(query, error, warnings=tenant.notes)
    if log_results:
        _best_effort_log(query, result)
    return result


def _select_detail_link(
    active: Any,
    tenant: TenantConfig,
    *,
    selector: str | None,
    data_link: str | None,
) -> tuple[str, Mapping[str, Any] | None]:
    if data_link:
        discovery = discover_data_link(data_link)
        if discovery.tenant is None:
            raise SourceSelectionError(
                "unrecognized_data_link",
                "The supplied URL does not match an observed TaxSifter deployment",
                details={"url": data_link},
            )
        if discovery.tenant.key != tenant.key:
            raise SourceSelectionError(
                "data_link_county_mismatch",
                "The supplied URL belongs to a different TaxSifter county",
                details={
                    "selected_county": tenant.key,
                    "data_link_county": discovery.tenant.key,
                },
            )
        if discovery.operation == Operation.ASSESSOR:
            return data_link, None
        selector = discovery.parcel_number or discovery.search_query or selector
    if not selector:
        raise SourceSelectionError(
            "parcel_required",
            "Detail requires a parcel selector or official DATA_LINK",
        )
    batch = active.search(str(selector), limit=None)
    exact = [
        record
        for record in batch.records
        if str(record.get("parcel_number")) == str(selector)
    ]
    if len(exact) == 1:
        selected = exact[0]
    elif len(batch.records) == 1:
        selected = batch.records[0]
    elif not batch.records:
        raise NoParcelResult(
            "TaxSifter search returned no parcel for the requested detail"
        )
    else:
        raise SourceSelectionError(
            "ambiguous_parcel",
            "TaxSifter search returned multiple parcels without one exact match",
            details={
                "selector": selector,
                "returned_count": len(batch.records),
            },
        )
    assessor_url = selected.get("operation_links", {}).get(Operation.ASSESSOR)
    if not assessor_url:
        raise SourceSchemaError(
            "TaxSifter search result lacks an assessor detail URL",
            url=batch.source_urls[0] if batch.source_urls else tenant.portal_root,
        )
    return str(assessor_url), selected


def _detail_bundle(
    active: Any,
    tenant: TenantConfig,
    *,
    selector: str | None,
    data_link: str | None,
    operations: Sequence[str],
) -> tuple[Mapping[str, Any], tuple[PublicRecordsError, ...], tuple[str, ...]]:
    assessor_url, search_record = _select_detail_link(
        active,
        tenant,
        selector=selector,
        data_link=data_link,
    )
    assessor_page = active.fetch_operation(
        assessor_url,
        operation=Operation.ASSESSOR,
    )
    assessor = parse_assessor_detail(assessor_page, tenant)
    selected_locator = _account_locator_from_url(assessor_url, tenant)
    if search_record is not None:
        if _string(search_record.get("source_id")) != tenant.source_id:
            raise SourceSchemaError(
                "TaxSifter search result belongs to a different source",
                url=assessor_url,
                details={
                    "selected_source": tenant.source_id,
                    "search_source": search_record.get("source_id"),
                },
            )
        _validate_account_consistency(
            selected_locator,
            search_record,
            tenant=tenant,
            operation=Operation.SEARCH,
            source_url=assessor_url,
        )
    _validate_account_consistency(
        selected_locator,
        assessor["parcel"],
        tenant=tenant,
        operation=Operation.ASSESSOR,
        source_url=assessor_page.url,
    )
    parcel_number = str(assessor["native_parcel_id"])
    representations: dict[str, Any] = {"assessor": assessor}
    representations["permits"] = {
        "record_kind": "assessor_permit_section",
        "source_id": tenant.source_id,
        "source_url": assessor_page.url,
        "lineage_id": ASSESSOR_LINEAGE,
        "response_state": assessor_page.state.value,
        "rows": assessor["building_permits"],
        "relationship": "embedded_assessor_representation",
    }
    errors: list[PublicRecordsError] = []
    warnings: list[str] = list(tenant.notes)
    operation_links = assessor["operation_links"]

    parser_by_operation = {
        Operation.TREASURER: parse_treasurer_detail,
        Operation.APPRAISAL: parse_appraisal_detail,
    }
    for operation in (Operation.TREASURER, Operation.APPRAISAL):
        if operation not in operations:
            continue
        operation_url = operation_links.get(operation)
        if not operation_url:
            warnings.append(
                f"{operation.value} link was not published for parcel {parcel_number}."
            )
            representations[operation.value] = {
                "record_kind": f"{operation.value}_capability_observation",
                "response_state": None,
                "capability_state": "link_not_published",
                "lineage_id": OPERATION_LINEAGES[operation]["lineage_id"],
            }
            continue
        try:
            operation_page = active.fetch_operation(
                operation_url,
                operation=operation,
            )
            operation_record = parser_by_operation[operation](
                operation_page,
                tenant,
            )
            _validate_account_consistency(
                assessor["parcel"],
                operation_record["parcel"],
                tenant=tenant,
                operation=operation,
                source_url=operation_page.url,
            )
            representations[operation.value] = operation_record
        except PublicRecordsHTTPError as error:
            errors.append(error.to_contract_error())
            representations[operation.value] = {
                "record_kind": f"{operation.value}_capability_observation",
                "source_url": error.url,
                "response_state": str(_error_state(error)),
                "lineage_id": OPERATION_LINEAGES[operation]["lineage_id"],
                "error": error.to_contract_error().to_dict(),
            }

    if Operation.SALES in operations:
        try:
            sales_form, sales_page = active.fetch_sales(
                {
                    "parcel": parcel_number,
                    "date_from": None,
                    "date_to": None,
                    "price_from": None,
                    "price_to": None,
                    "acres_from": None,
                    "acres_to": None,
                    "year_built_from": None,
                    "year_built_to": None,
                    "map_number": None,
                }
            )
            sales = parse_sales_results(sales_page, tenant)
            pagination = _sales_pagination_observation(
                sales_form,
                sales_page,
                returned_records=len(sales),
            )
            representations["sales"] = {
                "record_kind": "assessor_sales_search",
                "source_id": tenant.source_id,
                "source_url": sales_page.url,
                "lineage_id": ASSESSOR_LINEAGE,
                "response_state": sales_page.state.value,
                "negotiated_fields": dict(sales_form.fields),
                "results": [dict(record) for record in sales],
                "result_count": len(sales),
                "native_pagination": pagination,
                "provenance": sales_page.provenance(
                    tenant,
                    **OPERATION_LINEAGES[Operation.SALES],
                ),
            }
        except PublicRecordsHTTPError as error:
            errors.append(error.to_contract_error())
            representations["sales"] = {
                "record_kind": "sales_capability_observation",
                "source_url": error.url,
                "response_state": str(_error_state(error)),
                "lineage_id": ASSESSOR_LINEAGE,
                "error": error.to_contract_error().to_dict(),
            }

    canonical_ref = canonical_property_ref(
        tenant.source_id,
        tenant.county_geoid,
        "property_enrichment_bundle",
        assessor["account_occurrence"]["native_id"],
    )
    bundle = {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": tenant.source_id,
        "source_url": assessor_page.url,
        "record_kind": "property_enrichment_bundle",
        "county_geoid": tenant.county_geoid,
        "native_parcel_id": parcel_number,
        "account_occurrence": assessor["account_occurrence"],
        "parcel_join": assessor["parcel_join"],
        "search_result": dict(search_record) if search_record else None,
        "representations": representations,
        "native_joins": assessor["native_joins"],
        "lineage_contract": {
            "assessor": {
                "lineage_id": ASSESSOR_LINEAGE,
                "representations": [
                    "search",
                    "assessor",
                    "appraisal",
                    "sales",
                    "permits",
                    "map",
                ],
                "interpretation": (
                    "same county assessor origin; representations are not "
                    "independent corroboration"
                ),
            },
            "treasurer": {
                "lineage_id": TREASURER_LINEAGE,
                "representations": ["treasurer", "balance", "payment"],
            },
            "recorder": {
                "lineage_id": RECORDER_LINEAGE,
                "representations": ["instrument_index", "instrument_image"],
                "interpretation": (
                    "distinct official evidence when the indexed instrument "
                    "or image supports the claim"
                ),
            },
        },
    }
    return bundle, tuple(errors), tuple(warnings)


def _detail_result(
    args: argparse.Namespace,
    tenant: TenantConfig,
    *,
    client: Any,
    log_results: bool,
) -> PublicRecordsResult:
    operations = _parse_operations(args.operations)
    query = _build_query(
        tenant,
        operation="detail",
        parameters={
            "parcel_selector": args.query,
            "data_link": args.data_link,
            "operations": [operation.value for operation in operations],
        },
        requested_limit=1,
        cursor=None,
    )
    try:
        active = client or _new_client(args, tenant)
        record, errors, warnings = _detail_bundle(
            active,
            tenant,
            selector=args.query,
            data_link=args.data_link,
            operations=operations,
        )
        if errors:
            result = PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                errors,
                records=[record],
                warnings=warnings,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=warnings,
            )
    except NoParcelResult:
        result = PublicRecordsResult.success(query, [], warnings=tenant.notes)
    except (
        PublicRecordsHTTPError,
        SourceSelectionError,
        TypeError,
        ValueError,
    ) as error:
        result = _public_failure(query, error, warnings=tenant.notes)
    if log_results:
        _best_effort_log(query, result)
    return result


def _sales_result(
    args: argparse.Namespace,
    tenant: TenantConfig,
    *,
    client: Any,
    log_results: bool,
) -> PublicRecordsResult:
    filters = {
        "parcel": args.parcel,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "price_from": args.price_from,
        "price_to": args.price_to,
        "acres_from": args.acres_from,
        "acres_to": args.acres_to,
        "year_built_from": args.year_built_from,
        "year_built_to": args.year_built_to,
        "map_number": args.map_number,
    }
    query = _build_query(
        tenant,
        operation="sales",
        parameters={"filters": filters},
        requested_limit=args.limit,
        cursor=None,
    )
    try:
        active = client or _new_client(args, tenant)
        form, page = active.fetch_sales(filters)
        parsed_records = [dict(record) for record in parse_sales_results(page, tenant)]
        pagination = _sales_pagination_observation(
            form,
            page,
            returned_records=len(parsed_records),
        )
        records = list(parsed_records)
        if args.limit is not None and len(records) > args.limit:
            records = records[: args.limit]
        for record in records:
            record["retrieval_snapshot"] = {
                "response_state": page.state.value,
                "negotiated_fields": dict(form.fields),
                "available_options": {
                    key: [dict(value) for value in values]
                    for key, values in form.options.items()
                },
                "returned_records": len(records),
                "native_pagination": pagination,
            }
        warnings = list(tenant.notes)
        if not pagination["current_response_exhaustive"]:
            warnings.append(SALES_PAGINATION_NOTE)
        result = PublicRecordsResult.success(
            query,
            records,
            warnings=warnings,
        )
    except (
        PublicRecordsHTTPError,
        SourceSelectionError,
        TypeError,
        ValueError,
    ) as error:
        result = _public_failure(query, error, warnings=tenant.notes)
    if log_results:
        _best_effort_log(query, result)
    return result


def _probe_result(
    args: argparse.Namespace,
    tenant: TenantConfig,
    *,
    client: Any,
    log_results: bool,
) -> PublicRecordsResult:
    operations = _parse_operations(args.operations)
    query = _build_query(
        tenant,
        operation="probe",
        parameters={
            "sentinel_query": tenant.sentinel_query,
            "operations": [operation.value for operation in operations],
        },
        requested_limit=1,
        cursor=None,
    )
    try:
        active = client or _new_client(args, tenant)
        batch = active.search(tenant.sentinel_query, limit=1)
        if not batch.records:
            raise SourceSchemaError(
                "TaxSifter sentinel search returned no result",
                url=batch.source_urls[0] if batch.source_urls else tenant.portal_root,
                details={"sentinel": tenant.sentinel_query},
            )
        search_record = dict(batch.records[0])
        operation_observations: dict[str, Any] = {
            "search": {
                "response_state": "live",
                "source_urls": list(batch.source_urls),
                "total_count": batch.total_count,
                "parcel_number": search_record.get("parcel_number"),
            }
        }
        if Operation.ASSESSOR in operations:
            assessor_url = search_record["operation_links"][Operation.ASSESSOR]
            assessor_page = active.fetch_operation(
                assessor_url,
                operation=Operation.ASSESSOR,
            )
            assessor = parse_assessor_detail(assessor_page, tenant)
            _validate_account_consistency(
                search_record,
                assessor["parcel"],
                tenant=tenant,
                operation=Operation.ASSESSOR,
                source_url=assessor_page.url,
            )
            operation_observations["assessor"] = {
                "response_state": assessor_page.state.value,
                "source_url": assessor_page.url,
                "parcel_number": assessor["native_parcel_id"],
                "published_operation_links": sorted(assessor["operation_links"]),
                "sale_count": len(assessor["sales_history"]),
                "permit_count": len(assessor["building_permits"]),
                "valuation_count": len(assessor["valuation_history"]),
                "data_current_as": assessor_page.data_current_as,
                "roll_year": assessor_page.roll_year,
            }
            for operation, parser in (
                (Operation.TREASURER, parse_treasurer_detail),
                (Operation.APPRAISAL, parse_appraisal_detail),
            ):
                if operation not in operations:
                    continue
                operation_url = assessor["operation_links"].get(operation)
                if not operation_url:
                    operation_observations[operation.value] = {
                        "response_state": None,
                        "capability_state": "link_not_published",
                    }
                    continue
                operation_page = active.fetch_operation(
                    operation_url,
                    operation=operation,
                )
                operation_record = parser(operation_page, tenant)
                _validate_account_consistency(
                    assessor["parcel"],
                    operation_record["parcel"],
                    tenant=tenant,
                    operation=operation,
                    source_url=operation_page.url,
                )
                observation = {
                    "response_state": operation_page.state.value,
                    "source_url": operation_page.url,
                    "parcel_number": operation_record["native_parcel_id"],
                    "data_current_as": operation_page.data_current_as,
                    "roll_year": operation_page.roll_year,
                }
                if operation == Operation.TREASURER:
                    observation.update(
                        {
                            "current_tax_rows": len(
                                operation_record["current_tax_year"]
                            ),
                            "balance_rows": len(operation_record["balances_due"]),
                            "receipt_rows": len(operation_record["payment_receipts"]),
                        }
                    )
                else:
                    observation["section_count"] = len(operation_record["sections"])
                operation_observations[operation.value] = observation
            if Operation.SALES in operations:
                sales_form, sales_page = active.fetch_sales(
                    {
                        "parcel": assessor["native_parcel_id"],
                        "date_from": None,
                        "date_to": None,
                        "price_from": None,
                        "price_to": None,
                        "acres_from": None,
                        "acres_to": None,
                        "year_built_from": None,
                        "year_built_to": None,
                        "map_number": None,
                    }
                )
                sales = parse_sales_results(sales_page, tenant)
                pagination = _sales_pagination_observation(
                    sales_form,
                    sales_page,
                    returned_records=len(sales),
                )
                operation_observations["sales"] = {
                    "response_state": sales_page.state.value,
                    "source_url": sales_page.url,
                    "result_count": len(sales),
                    "negotiated_fields": dict(sales_form.fields),
                    "native_pagination": pagination,
                    "data_current_as": sales_page.data_current_as,
                    "roll_year": sales_page.roll_year,
                }
        record = {
            "record_kind": "source_probe",
            "probe_schema_version": PROBE_SCHEMA_VERSION,
            "source_id": tenant.source_id,
            "county": tenant.key,
            "access_state_before_probe": tenant.access_state,
            "ordinary_disclaimer_session_supported": True,
            "operation_observations": operation_observations,
            "request_count": getattr(active, "request_count", None),
            "source_contract": _source_record(tenant),
        }
        result = PublicRecordsResult.success(query, [record], warnings=tenant.notes)
    except (
        PublicRecordsHTTPError,
        SourceSelectionError,
        TypeError,
        ValueError,
    ) as error:
        result = _public_failure(query, error, warnings=tenant.notes)
    if log_results:
        _best_effort_log(query, result)
    return result


def _parse_operations(value: str) -> tuple[Operation, ...]:
    raw = [part.strip().lower() for part in str(value).split(",") if part.strip()]
    if not raw:
        raise SourceSelectionError(
            "operation_required",
            "At least one TaxSifter operation is required",
        )
    if "all" in raw:
        return tuple(Operation)
    operations = []
    for item in raw:
        try:
            operation = Operation(item)
        except ValueError as error:
            raise SourceSelectionError(
                "unknown_operation",
                f"Unknown TaxSifter operation: {item}",
            ) from error
        if operation not in operations:
            operations.append(operation)
    if Operation.ASSESSOR not in operations and any(
        value in operations for value in (Operation.TREASURER, Operation.APPRAISAL)
    ):
        operations.insert(0, Operation.ASSESSOR)
    return tuple(operations)


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute discovery, metadata, source queries, or bounded probes."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "discover":
        discovery = discover_data_link(args.data_link)
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "discovery": discovery.to_dict(),
            "source": (
                _source_record(discovery.tenant)
                if discovery.tenant is not None
                else None
            ),
        }
    tenant = _tenant_from_args(args)
    selected = _selected_client(client, tenant)
    if args.command == "metadata":
        query = _build_query(
            tenant,
            operation="metadata",
            parameters={"source_id": tenant.source_id},
            requested_limit=1,
            cursor=None,
        )
        return PublicRecordsResult.success(query, [_source_record(tenant)])
    if args.command == "search":
        return _search_result(
            args,
            tenant,
            client=selected,
            log_results=log_results,
        )
    if args.command == "detail":
        return _detail_result(
            args,
            tenant,
            client=selected,
            log_results=log_results,
        )
    if args.command == "sales":
        return _sales_result(
            args,
            tenant,
            client=selected,
            log_results=log_results,
        )
    if args.command == "probe":
        return _probe_result(
            args,
            tenant,
            client=selected,
            log_results=log_results,
        )
    raise SourceSelectionError(
        "unknown_command",
        f"Unknown TaxSifter command: {args.command}",
    )


def _probe_verified(
    args: argparse.Namespace,
) -> dict[str, Any]:
    components = []
    for key in VERIFIED_TENANT_KEYS:
        tenant = TENANTS_BY_KEY[key]
        component_args = argparse.Namespace(**vars(args))
        component_args.county = tenant.key
        component_args.source = None
        component_args.verified = False
        result = _probe_result(
            component_args,
            tenant,
            client=None,
            log_results=True,
        )
        components.append(result.to_dict())
    statuses = {component["status"] for component in components}
    overall = (
        "ok"
        if statuses <= {"ok", "no_results"}
        else ("partial" if "ok" in statuses else "unavailable")
    )
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": overall,
        "verified_tenants": list(VERIFIED_TENANT_KEYS),
        "components": components,
    }


def _payload(
    value: PublicRecordsResult | Mapping[str, Any],
) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    records = payload.get("records")
    result_count = (
        len(records)
        if isinstance(records, list)
        else len(payload.get("components", payload.get("sources", [])))
    )
    if write_output(
        payload,
        args,
        summary=f"Washington TaxSifter {args.command}",
        result_count=result_count,
    ):
        return
    if args.command == "sources":
        print(f"Washington TaxSifter deployments: {payload['source_count']}")
        for source in payload["sources"]:
            print(
                f"  {source['county_key']} | {source['source_id']} | "
                f"{source['access_state']}"
            )
        return
    if args.command == "discover":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command == "probe" and getattr(args, "verified", False):
        print(f"Washington TaxSifter verified probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | {component['status']}"
            )
        return
    rows = payload.get("records", [])
    print(
        f"Washington TaxSifter {args.command}: "
        f"{payload.get('status')} ({len(rows)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in rows:
        print(
            f"  {record.get('native_parcel_id') or record.get('county')} | "
            f"{record.get('record_kind')}"
        )
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_source_selection(parser: argparse.ArgumentParser) -> None:
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--county", choices=sorted(TENANTS_BY_KEY))
    selection.add_argument("--source", choices=sorted(TENANTS_BY_SOURCE))


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Washington county TaxSifter/PublicAccessNow "
            "property, assessment, tax, appraisal, sale, and permit records"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List discovered county deployments and current capability states",
    )
    add_output_args(sources)

    metadata = sub.add_parser(
        "metadata",
        help="Show one county source and operation contract",
    )
    _add_source_selection(metadata)
    add_output_args(metadata)

    discover = sub.add_parser(
        "discover",
        help="Resolve an official statewide parcel DATA_LINK",
    )
    discover.add_argument("data_link")
    add_output_args(discover)

    search = sub.add_parser(
        "search",
        help="Run the native general parcel/name/address search",
    )
    search.add_argument("query")
    _add_source_selection(search)
    search.add_argument(
        "--limit",
        type=int,
        help=("Maximum records to return; omitted exhausts the native result pages"),
    )
    search.add_argument(
        "--cursor",
        help="Query-bound native page/offset continuation",
    )
    _add_transport_arguments(search)

    detail = sub.add_parser(
        "detail",
        help="Fetch parcel enrichment representations",
    )
    detail.add_argument("query", nargs="?")
    _add_source_selection(detail)
    detail.add_argument(
        "--data-link",
        help="Official statewide parcel DATA_LINK for direct detail",
    )
    detail.add_argument(
        "--operations",
        default="assessor,treasurer,appraisal",
        help="Comma-separated search,assessor,treasurer,appraisal,sales or all",
    )
    _add_transport_arguments(detail)

    sales = sub.add_parser(
        "sales",
        help="Run the county-enabled assessor sales-search postback",
    )
    _add_source_selection(sales)
    sales.add_argument("--parcel")
    sales.add_argument("--date-from")
    sales.add_argument("--date-to")
    sales.add_argument("--price-from")
    sales.add_argument("--price-to")
    sales.add_argument("--acres-from")
    sales.add_argument("--acres-to")
    sales.add_argument("--year-built-from")
    sales.add_argument("--year-built-to")
    sales.add_argument("--map-number")
    sales.add_argument(
        "--limit",
        type=int,
        help=(
            "Maximum records to retain from the native response; omitted "
            "retains every returned row"
        ),
    )
    _add_transport_arguments(sales)

    probe = sub.add_parser(
        "probe",
        help="Run bounded session/search and optional assessor probes",
    )
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--county", choices=sorted(TENANTS_BY_KEY))
    selection.add_argument("--source", choices=sorted(TENANTS_BY_SOURCE))
    selection.add_argument(
        "--verified",
        action="store_true",
        help="Probe all six live-verified deployments",
    )
    probe.add_argument(
        "--operations",
        default="search,assessor",
        help="Comma-separated bounded operations",
    )
    _add_transport_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "retry_attempts", 1) <= 0:
        parser.error("--retry-attempts must be positive")
    limit = getattr(args, "limit", None)
    if limit is not None and limit <= 0:
        parser.error("--limit must be positive")
    if hasattr(args, "query") and args.query is not None and not args.query.strip():
        parser.error("query must not be blank")
    if args.command == "detail" and not args.query and not args.data_link:
        parser.error("detail requires a parcel query or --data-link")
    try:
        if args.command == "probe" and args.verified:
            value: PublicRecordsResult | dict[str, Any] = _probe_verified(args)
        else:
            value = execute(args)
    except SourceSelectionError as error:
        parser.error(str(error))
    _emit(value, args)


if __name__ == "__main__":
    main()
