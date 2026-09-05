#!/usr/bin/env python3
"""Query Oregon Helion/ORCATS Property Search Online county tenants.

The county portals share a Blazor Server application shape, but each tenant is
kept as a distinct source with its own native search options, access observation,
county authority, and official complements.

Examples:
    uv run python tools/query_oregon_helion_property.py sources
    uv run python tools/query_oregon_helion_property.py source \
      --source us-or-columbia-helion-property
    uv run python tools/query_oregon_helion_property.py search smith \
      --field name --source us-or-morrow-helion-property --limit 10
    uv run python tools/query_oregon_helion_property.py detail 171 \
      --roll-type R --source us-or-morrow-helion-property
    uv run python tools/query_oregon_helion_property.py probe \
      --source us-or-tillamook-helion-property
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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


STATE_CODE = "OR"
STATE_FIPS = "41"
PLATFORM_FAMILY = "helion_orcats_property_search_online"
CURSOR_PREFIX = "orpso:v1:"
NATIVE_PAGE_SIZE = 10
DEFAULT_TIMEOUT = 45.0
HELPER_PATH = Path(__file__).with_name("_oregon_helion_property_browser_helper.js")


@dataclass(frozen=True)
class PropertyTenant:
    """One independently operated county PSO source."""

    key: str
    source_id: str
    county_name: str
    county_fips: str
    authority: str
    portal_root: str
    official_linking_page: str
    search_options: Mapping[str, str]
    access_observation: Mapping[str, Any]
    data_observation: str
    complements: tuple[Mapping[str, Any], ...] = ()

    @property
    def jurisdiction(self) -> JurisdictionMetadata:
        return JurisdictionMetadata(
            jurisdiction_id=f"us-or-{self.key}",
            name=f"{self.county_name}, Oregon",
            state_code=STATE_CODE,
            county_fips=self.county_fips,
            locality=self.county_name,
            metadata={"state_fips": STATE_FIPS},
        )

    @property
    def source(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=f"{self.county_name} Property Search Online",
            source_role=("county_assessor_property_account_assessment_tax_and_sales"),
            base_url=self.portal_root,
            dataset_id=f"helion-pso-{self.key}",
            metadata={
                "authority": self.authority,
                "operator": "Helion Software",
                "platform_family": PLATFORM_FAMILY,
                "county_fips": self.county_fips,
                "official_linking_page": self.official_linking_page,
                "native_search_options": dict(self.search_options),
                "access_observation": dict(self.access_observation),
                "data_observation": self.data_observation,
                "complements": [dict(value) for value in self.complements],
                "render_contract": {
                    "application": "Blazor Server",
                    "search_route": (
                        "search?searchOption={option}&searchValue={value}"
                        "&pageNumber={page}"
                    ),
                    "detail_route": "detail/{account_id}/{roll_type}",
                    "native_page_size_observed": NATIVE_PAGE_SIZE,
                },
            },
        )


TENANTS = (
    PropertyTenant(
        key="umatilla",
        source_id="us-or-umatilla-helion-property",
        county_name="Umatilla County",
        county_fips="41059",
        authority="Umatilla County Assessment and Taxation",
        portal_root="https://public.co.umatilla.or.us/pso/",
        official_linking_page="https://co.umatilla.or.us/departments/at",
        search_options={
            "account": "AccountId",
            "tax_account": "TaxAccountId",
            "name": "Name",
            "address": "Address",
            "map": "Map",
            "legal": "Legal",
        },
        access_observation={
            "observed_at": "2026-07-29",
            "outcome": "public_search_and_detail_ready",
            "blazor_transport": "websocket",
        },
        data_observation=(
            "The county links PSO as its property search and states that taxes "
            "are updated after October 25; combined split-code figures may "
            "require comparison with county assessment records."
        ),
        complements=(
            {
                "kind": "umatilla_interactive_county_map",
                "url": (
                    "https://experience.arcgis.com/experience/"
                    "2cabcc1b565f4c1cb2e808e91451ca7d"
                ),
                "join_keys": ["account_id", "map_taxlot"],
                "relationship": "parcel_geometry_and_map_context",
            },
            {
                "kind": "umatilla_sales_files_and_assessment_reports",
                "url": "https://co.umatilla.or.us/departments/at",
                "join_keys": ["account_id", "map_taxlot", "tax_year"],
                "relationship": "bulk_sales_and_annual_report_complement",
            },
        ),
    ),
    PropertyTenant(
        key="morrow",
        source_id="us-or-morrow-helion-property",
        county_name="Morrow County",
        county_fips="41049",
        authority="Morrow County Assessment and Tax",
        portal_root="https://records.morrowcountyor.gov/PSO/",
        official_linking_page=(
            "https://www.morrowcountyor.gov/tax/page/property-records"
        ),
        search_options={
            "account": "AccountId",
            "tax_account": "TaxAccountId",
            "name": "Name",
            "address": "Address",
            "map": "Map",
            "legal": "Legal",
        },
        access_observation={
            "observed_at": "2026-07-29",
            "outcome": "public_search_and_detail_ready",
            "blazor_transport": "websocket",
        },
        data_observation=(
            "The county states that PSO derives assessment and tax information "
            "from the last certified assessment roll and links the portal for "
            "more detailed property tax and assessment information."
        ),
        complements=(
            {
                "kind": "morrow_taxlot_maps",
                "url": "https://www.morrowcountyor.gov/tax/page/tax-lot-maps",
                "join_keys": ["map_taxlot"],
                "relationship": "official_taxlot_map_complement",
            },
            {
                "kind": "morrow_tax_levy_district_reports",
                "url": (
                    "https://www.morrowcountyor.gov/tax/page/"
                    "taxes-levies-and-district-reports"
                ),
                "join_keys": ["tax_year", "code_area"],
                "relationship": "annual_tax_report_complement",
            },
        ),
    ),
    PropertyTenant(
        key="polk",
        source_id="us-or-polk-helion-property",
        county_name="Polk County",
        county_fips="41053",
        authority="Polk County Assessor",
        portal_root="https://apps2.co.polk.or.us/pso/",
        official_linking_page=(
            "https://www.co.polk.or.us/services?term_node_tid_depth=104"
        ),
        search_options={
            "account": "AccountId",
            "tax_account": "TaxAccountId",
            "name": "Name",
            "address": "Address",
            "map": "Map",
            "legal": "Legal",
        },
        access_observation={
            "observed_at": "2026-07-29",
            "outcome": "public_search_and_detail_ready",
            "blazor_transport": "websocket",
        },
        data_observation=(
            "Polk County links this tenant as Assessor's Property Search and "
            "publishes separate GIS download and assessment/tax data routes."
        ),
        complements=(
            {
                "kind": "polk_gis_and_assessment_data_download",
                "url": "https://polkdatadownload-polkor.hub.arcgis.com/",
                "join_keys": ["account_id", "map_taxlot"],
                "relationship": "bulk_gis_and_assessment_complement",
            },
            {
                "kind": "polk_taxlots_arcgis",
                "url": "https://maps.co.polk.or.us/gis/rest/services/Assessor",
                "join_keys": ["account_id", "map_taxlot"],
                "relationship": "parcel_geometry_complement",
            },
        ),
    ),
    PropertyTenant(
        key="tillamook",
        source_id="us-or-tillamook-helion-property",
        county_name="Tillamook County",
        county_fips="41057",
        authority="Tillamook County Assessment and Taxation",
        portal_root="https://query.co.tillamook.or.us/PSO/",
        official_linking_page=(
            "https://www.tillamookcounty.gov/assessment/page/account-web-query"
        ),
        search_options={
            "account": "AccountId",
            "tax_account": "TaxAccountId",
            "name": "Name",
            "address": "Address",
            "map": "Map",
            "legal": "Legal",
        },
        access_observation={
            "observed_at": "2026-07-29",
            "outcome": "public_search_and_detail_ready",
            "blazor_transport": "long_polling_after_websocket_handshake_200",
        },
        data_observation=(
            "The public tenant completed searches through SignalR long polling "
            "after its websocket handshake returned HTTP 200."
        ),
        complements=(
            {
                "kind": "tillamook_prior_assessment_tax_rolls",
                "url": (
                    "https://www.tillamookcounty.gov/assessment/page/"
                    "prior-assessmenttax-rolls"
                ),
                "join_keys": ["account_id", "map_taxlot", "tax_year"],
                "relationship": "historical_bulk_roll_complement",
                "coverage_observation": (
                    "2001/02 and annual rolls from 2007/08 through 2025/26 "
                    "were linked on 2026-07-29."
                ),
            },
            {
                "kind": "tillamook_tax_maps",
                "url": ("https://www.tillamookcounty.gov/assessment/page/tax-maps"),
                "join_keys": ["map_taxlot"],
                "relationship": "keyed_tax_map_complement",
            },
            {
                "kind": "tillamook_sales_data",
                "url": ("https://www.tillamookcounty.gov/assessment/page/sales-data"),
                "join_keys": ["account_id", "map_taxlot", "sale_date"],
                "relationship": "bulk_sales_excel_complement",
            },
            {
                "kind": "tillamook_real_property_tax_foreclosure",
                "url": (
                    "https://www.tillamookcounty.gov/assessment/page/"
                    "real-property-tax-foreclosure"
                ),
                "join_keys": ["account_id", "map_taxlot", "case_number"],
                "relationship": "current_foreclosure_list_complement",
            },
            {
                "kind": "tillamook_county_real_property_sales",
                "url": (
                    "https://www.tillamookcounty.gov/bocc/page/real-property-sales"
                ),
                "join_keys": ["account_id", "map_taxlot"],
                "relationship": "county_tax_deed_sale_complement",
            },
        ),
    ),
    PropertyTenant(
        key="columbia",
        source_id="us-or-columbia-helion-property",
        county_name="Columbia County",
        county_fips="41009",
        authority="Columbia County Assessor and Tax Office",
        portal_root="https://propertysearch.columbiacountyor.gov/PSO/",
        official_linking_page=(
            "https://www.columbiacountyor.gov/departments/TaxOffice/"
            "find-property-tax-records"
        ),
        search_options={
            "account": "TaxAccountId",
            "name": "Name",
            "address": "Address",
            "map": "Map",
        },
        access_observation={
            "observed_at": "2026-07-29",
            "outcome": "public_search_and_detail_ready",
            "blazor_transport": "websocket",
        },
        data_observation=(
            "The county describes PSO as detailed certified-roll assessment "
            "and tax data with updated payoff amounts. Ownership updates are "
            "included; next-year segregations and combinations appear after "
            "the next roll is certified."
        ),
        complements=(
            {
                "kind": "columbia_current_noncertified_webmaps",
                "url": "https://gis.columbiacountymaps.com/",
                "join_keys": ["account_id", "map_taxlot"],
                "relationship": (
                    "current_geometry_and_next_year_split_combine_complement"
                ),
                "data_observation": (
                    "County web maps carry one year of less-detailed current "
                    "non-certified assessment data and show next-year "
                    "segregations and combinations."
                ),
            },
            {
                "kind": "columbia_certified_tax_roll_data",
                "url": (
                    "https://www.columbiacountyor.gov/property-tax-data-and-reports"
                ),
                "join_keys": ["account_id", "map_taxlot", "tax_year"],
                "relationship": "bulk_certified_roll_tab_files",
            },
            {
                "kind": "columbia_quarterly_property_sales",
                "url": (
                    "https://www.columbiacountyor.gov/property-tax-data-and-reports"
                ),
                "join_keys": ["account_id", "map_taxlot", "sale_date"],
                "relationship": "quarterly_real_property_sales_excel",
            },
        ),
    ),
    PropertyTenant(
        key="coos",
        source_id="us-or-coos-helion-property",
        county_name="Coos County",
        county_fips="41011",
        authority="Coos County Assessor and Tax Department",
        portal_root="https://records.co.coos.or.us/PSO/",
        official_linking_page="https://co.coos.or.us/taxes",
        search_options={
            "account": "AccountId",
            "tax_account": "TaxAccountId",
            "name": "Name",
            "address": "Address",
            "map": "Map",
        },
        access_observation={
            "observed_at": "2026-07-29",
            "outcome": "public_search_and_detail_ready",
            "blazor_transport": "websocket",
        },
        data_observation=(
            "Coos County links this Account Search and describes its property "
            "information as derived from the Coos County Tax Roll."
        ),
        complements=(
            {
                "kind": "coos_tax_and_assessor_routes",
                "url": "https://co.coos.or.us/taxes",
                "join_keys": ["account_id", "map_taxlot", "tax_year"],
                "relationship": (
                    "county_tax_reports_foreclosure_and_payment_complement"
                ),
            },
        ),
    ),
    PropertyTenant(
        key="benton",
        source_id="us-or-benton-helion-property",
        county_name="Benton County",
        county_fips="41003",
        authority="Benton County Assessment",
        portal_root="https://apps.benton-or.helioncloud.com/PSO/",
        official_linking_page=(
            "https://assessment.bentoncountyor.gov/property-account-search/"
        ),
        search_options={
            "account": "AccountId",
            "tax_account": "TaxAccountId",
            "name": "Name",
            "address": "Address",
            "map": "Map",
            "legal": "Legal",
        },
        access_observation={
            "observed_at": "2026-07-29",
            "outcome": "public_search_and_detail_ready",
            "blazor_transport": "websocket",
        },
        data_observation=(
            "Benton County's assessment search links current owner, tax, and "
            "post-June-2025 sales follow-up to this PSO tenant during the "
            "county's assessment-system transition."
        ),
        complements=(
            {
                "kind": "benton_assessment_search_and_history",
                "url": (
                    "https://assessment.bentoncountyor.gov/property-account-search/"
                ),
                "join_keys": ["account_id", "map_taxlot", "owner_name"],
                "relationship": (
                    "county_search_summary_value_sales_and_improvement_history"
                ),
                "data_observation": (
                    "The county WordPress search exposes anonymous account "
                    "matches and separate REST-backed summary, value, sales, "
                    "improvements, and value-graph representations."
                ),
            },
            {
                "kind": "benton_taxlot_owner_arcgis_and_bulk",
                "url": (
                    "https://gis.co.benton.or.us/arcgis/rest/services/"
                    "Public/TaxlotOwners/MapServer/0"
                ),
                "join_keys": ["account_id", "map_taxlot", "or_taxlot"],
                "relationship": (
                    "owner_situs_mailing_geometry_and_downloadable_gis_complement"
                ),
            },
            {
                "kind": "benton_helion_recorder",
                "url": "https://records.co.benton.or.us/",
                "join_keys": [
                    "deed_reference",
                    "party_name",
                    "recording_date",
                ],
                "relationship": "recorded_instrument_and_image_complement",
            },
        ),
    ),
)

TENANTS_BY_SOURCE = {tenant.source_id: tenant for tenant in TENANTS}
SOURCE_IDS = tuple(TENANTS_BY_SOURCE)


class OregonPSOError(RuntimeError):
    """Base adapter error."""


class SelectionError(OregonPSOError):
    """Invalid tenant, native selector, record key, or continuation."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = dict(details or {})


class BrowserHelperError(OregonPSOError):
    """Structured browser-rendering failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})
        self.retryable = retryable


@dataclass(frozen=True)
class CursorState:
    source_id: str
    query_fingerprint: str
    page_number: int
    position_on_page: int
    anchor: str
    total_pages: int


BrowserRunner = Callable[..., Mapping[str, Any]]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _money(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    normalized = re.sub(r"[^0-9.\-]", "", text)
    if not normalized:
        return None
    try:
        return format(Decimal(normalized), "f")
    except InvalidOperation:
        return None


def _integer(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    normalized = re.sub(r"[^0-9\-]", "", text)
    try:
        return int(normalized)
    except (TypeError, ValueError):
        return None


def _date_iso(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    for pattern in (
        "%d-%b-%Y",
        "%d %b %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _address(raw: Any) -> dict[str, Any] | None:
    text = _clean(raw)
    if text is None:
        return None
    return {
        "raw_address": text,
        "state": STATE_CODE if re.search(r"\bOR\b", text) else None,
        "country": "US",
    }


def _mailing_address(lines: Any) -> dict[str, Any] | None:
    if not isinstance(lines, Sequence) or isinstance(lines, (str, bytes)):
        return None
    cleaned = [_clean(value) for value in lines]
    values = [value for value in cleaned if value]
    if not values:
        return None
    return {
        "raw_address": ", ".join(values),
        "address_lines": values,
        "country": "US",
    }


def _tenant_from_args(args: argparse.Namespace) -> PropertyTenant:
    source_id = getattr(args, "source", None)
    if source_id not in TENANTS_BY_SOURCE:
        raise SelectionError(
            "source_not_selected",
            "select one Oregon Property Search Online county source",
        )
    return TENANTS_BY_SOURCE[str(source_id)]


def _source_record(tenant: PropertyTenant) -> dict[str, Any]:
    return {
        "canonical_ref": f"ORPSO_SOURCE:{tenant.county_fips}",
        "record_kind": "source_metadata",
        "source_id": tenant.source_id,
        "name": tenant.source.name,
        "authority": tenant.authority,
        "county_name": tenant.county_name,
        "county_fips": tenant.county_fips,
        "portal_root": tenant.portal_root,
        "official_linking_page": tenant.official_linking_page,
        "native_search_options": dict(tenant.search_options),
        "access_observation": dict(tenant.access_observation),
        "data_observation": tenant.data_observation,
        "complements": [dict(value) for value in tenant.complements],
    }


def _run_browser_helper(
    command: str,
    *,
    tenant: PropertyTenant | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    **parameters: Any,
) -> Mapping[str, Any]:
    if not HELPER_PATH.exists():
        raise BrowserHelperError(
            "browser_helper_missing",
            f"Browser helper is missing: {HELPER_PATH}",
        )
    node = shutil.which("node")
    if node is None:
        raise BrowserHelperError(
            "node_runtime_unavailable",
            "Node.js is not available in PATH",
        )
    command_line = [node, str(HELPER_PATH), command]
    if tenant is not None:
        command_line.extend(["--base-url", tenant.portal_root])
    option_names = {
        "search_option": "--search-option",
        "query": "--query",
        "page": "--page",
        "account": "--account",
        "roll_type": "--roll-type",
    }
    for key, flag in option_names.items():
        if parameters.get(key) is not None:
            command_line.extend([flag, str(parameters[key])])
    environment = dict(os.environ)
    environment["OR_PSO_TIMEOUT_MS"] = str(max(1, int(timeout * 1000)))
    try:
        completed = subprocess.run(
            command_line,
            capture_output=True,
            text=True,
            timeout=max(timeout * 4, timeout + 30),
            env=environment,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise BrowserHelperError(
            "browser_helper_timeout",
            f"Browser helper exceeded {timeout * 4:g} seconds",
            retryable=True,
        ) from error
    except OSError as error:
        raise BrowserHelperError(
            "browser_helper_start_failed",
            str(error),
            retryable=True,
        ) from error
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise BrowserHelperError(
            "browser_helper_invalid_json",
            "Browser helper returned invalid JSON",
            details={
                "returncode": completed.returncode,
                "stderr": completed.stderr[-2000:],
            },
            retryable=completed.returncode != 0,
        ) from error
    if not isinstance(payload, Mapping):
        raise BrowserHelperError(
            "browser_helper_invalid_payload",
            "Browser helper payload is not an object",
        )
    if not payload.get("ok", False):
        raw_error = payload.get("error")
        error_data = raw_error if isinstance(raw_error, Mapping) else {}
        code = str(error_data.get("code") or "browser_render_failed")
        raise BrowserHelperError(
            code,
            str(error_data.get("message") or "Browser render failed"),
            details=(
                error_data.get("details")
                if isinstance(error_data.get("details"), Mapping)
                else {}
            ),
            retryable=code
            in {
                "browser_helper_timeout",
                "browser_render_failed",
                "source_http_429",
                "source_http_500",
                "source_http_502",
                "source_http_503",
                "source_http_504",
            },
        )
    if completed.returncode != 0:
        raise BrowserHelperError(
            "browser_helper_failed",
            f"Browser helper exited with code {completed.returncode}",
            details={"stderr": completed.stderr[-2000:]},
            retryable=True,
        )
    return dict(payload)


class OregonPSOClient:
    """Thin source client around the browser renderer."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        runner: BrowserRunner | None = None,
    ) -> None:
        self.timeout = timeout
        self.runner = runner or _run_browser_helper

    def probe(self, tenant: PropertyTenant) -> Mapping[str, Any]:
        return self.runner("probe", tenant=tenant, timeout=self.timeout)

    def search(
        self,
        tenant: PropertyTenant,
        *,
        search_option: str,
        query: str,
        page: int,
    ) -> Mapping[str, Any]:
        return self.runner(
            "search",
            tenant=tenant,
            timeout=self.timeout,
            search_option=search_option,
            query=query,
            page=page,
        )

    def detail(
        self,
        tenant: PropertyTenant,
        *,
        account: str,
        roll_type: str,
    ) -> Mapping[str, Any]:
        return self.runner(
            "detail",
            tenant=tenant,
            timeout=self.timeout,
            account=account,
            roll_type=roll_type,
        )

    def close(self) -> None:
        return None


def _query_fingerprint(
    tenant: PropertyTenant,
    *,
    field: str,
    native_option: str,
    query: str,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": tenant.source_id,
            "field": field,
            "native_option": native_option,
            "query": query,
        }
    )


def _record_anchor(record: Mapping[str, Any]) -> str:
    return canonical_json(
        {
            "account_id": record.get("account_id"),
            "roll_type": record.get("roll_type"),
            "map_taxlot": record.get("map_taxlot"),
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": 1,
        "source_id": state.source_id,
        "query_fingerprint": state.query_fingerprint,
        "page_number": state.page_number,
        "position_on_page": state.position_on_page,
        "anchor": state.anchor,
        "total_pages": state.total_pages,
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(
    cursor: str,
    *,
    tenant: PropertyTenant,
    query_fingerprint: str,
) -> CursorState:
    if not cursor.startswith(CURSOR_PREFIX):
        raise SelectionError(
            "cursor_invalid",
            "cursor does not use the Oregon PSO continuation format",
            status=ResultStatus.SOURCE_CHANGED,
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SelectionError(
            "cursor_invalid",
            "cursor payload is malformed",
            status=ResultStatus.SOURCE_CHANGED,
        ) from error
    if not isinstance(payload, Mapping) or payload.get("v") != 1:
        raise SelectionError(
            "cursor_invalid",
            "cursor version is not supported",
            status=ResultStatus.SOURCE_CHANGED,
        )
    if payload.get("source_id") != tenant.source_id:
        raise SelectionError(
            "cursor_source_mismatch",
            "cursor belongs to another county source",
            status=ResultStatus.SOURCE_CHANGED,
            details={
                "cursor_source_id": payload.get("source_id"),
                "query_source_id": tenant.source_id,
            },
        )
    if payload.get("query_fingerprint") != query_fingerprint:
        raise SelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different search selectors",
            status=ResultStatus.SOURCE_CHANGED,
        )
    try:
        page_number = int(payload["page_number"])
        position = int(payload["position_on_page"])
        total_pages = int(payload["total_pages"])
        anchor = str(payload["anchor"])
    except (KeyError, TypeError, ValueError) as error:
        raise SelectionError(
            "cursor_invalid",
            "cursor boundary fields are malformed",
            status=ResultStatus.SOURCE_CHANGED,
        ) from error
    if page_number < 1 or position < 1 or total_pages < page_number or not anchor:
        raise SelectionError(
            "cursor_invalid",
            "cursor boundary values are inconsistent",
            status=ResultStatus.SOURCE_CHANGED,
        )
    return CursorState(
        source_id=tenant.source_id,
        query_fingerprint=query_fingerprint,
        page_number=page_number,
        position_on_page=position,
        anchor=anchor,
        total_pages=total_pages,
    )


def _jurisdiction_record(tenant: PropertyTenant) -> dict[str, Any]:
    return {
        "country": "US",
        "state_code": STATE_CODE,
        "state_fips": STATE_FIPS,
        "county_name": tenant.county_name,
        "county_geoid": tenant.county_fips,
        "county_fips": tenant.county_fips,
    }


def _normalize_search_record(
    tenant: PropertyTenant,
    raw: Mapping[str, Any],
    *,
    coverage: Mapping[str, Any],
    query_fingerprint: str,
) -> dict[str, Any]:
    account_id = _clean(raw.get("account_id"))
    roll_type = _clean(raw.get("roll_type"))
    if account_id is None or roll_type is None:
        raise SelectionError(
            "source_search_identity_changed",
            "PSO result card is missing account or roll type",
            status=ResultStatus.SOURCE_CHANGED,
            details={"record": dict(raw)},
        )
    map_taxlot = _clean(raw.get("map_taxlot"))
    native_id = map_taxlot or account_id
    owner = _clean(raw.get("owner_name"))
    return {
        "source_id": tenant.source_id,
        "source_name": tenant.source.name,
        "source_url": _clean(raw.get("detail_url")) or tenant.portal_root,
        "record_kind": "property_search_result",
        "record_view": "search_result",
        "snapshot_complete": False,
        "native_parcel_id": native_id,
        "native_account_id": account_id,
        "assessment_account_ids": [account_id],
        "alternate_parcel_ids": [account_id],
        "map_taxlot": map_taxlot,
        "roll_type": roll_type,
        "property_type": _clean(raw.get("property_type")),
        "canonical_ref": canonical_property_ref(
            tenant.source_id,
            tenant.county_fips,
            "parcel",
            native_id,
        ),
        "jurisdiction": _jurisdiction_record(tenant),
        "owner_name": owner,
        "owners": [{"raw_name": owner}] if owner else [],
        "situs_address": _address(raw.get("situs_address")),
        "tax_state": {
            "current_balance_due": _money(raw.get("amount_due")),
            "current_balance_due_raw": _clean(raw.get("amount_due")),
        },
        "detail_url": _clean(raw.get("detail_url")),
        "related_accounts_url": _clean(raw.get("related_accounts_url")),
        "search_metadata": {
            "coverage": dict(coverage),
            "query_fingerprint": query_fingerprint,
            "position_on_page": raw.get("position_on_page"),
        },
        "source_record": dict(raw),
    }


def _assessment(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = raw.get("assessment_rows")
    if not isinstance(rows, Sequence):
        return None
    by_type: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if isinstance(row, Mapping):
            row_type = (_clean(row.get("type")) or "").casefold()
            if row_type:
                by_type[row_type] = row
    total = by_type.get("total", {})
    land = by_type.get("land", {})
    improvements = by_type.get("improvements", {})
    if not by_type:
        return None
    return {
        "tax_year": _integer(raw.get("assessment_year")),
        "land_real_market_value": _money(land.get("rmv")),
        "improvement_real_market_value": _money(improvements.get("rmv")),
        "real_market_value": _money(total.get("rmv")),
        "maximum_assessed_value": _money(total.get("mav")),
        "assessed_value": _money(total.get("av")),
        "source_rows": [dict(row) for row in rows if isinstance(row, Mapping)],
    }


def _assessment_history(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = raw.get("value_history")
    if not isinstance(rows, Sequence):
        return []
    result = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result.append(
            {
                "tax_year": _integer(row.get("year")),
                "real_market_value": _money(row.get("rmv")),
                "maximum_assessed_value": _money(row.get("mav")),
                "assessed_value": _money(row.get("av")),
                "source_row": dict(row),
            }
        )
    return result


def _sales(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = raw.get("sales_history")
    if not isinstance(rows, Sequence):
        return []
    result = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result.append(
            {
                "sale_date": _date_iso(row.get("sales_date")),
                "sale_date_raw": _clean(row.get("sales_date")),
                "document_id": _clean(row.get("year_doc_id")),
                "source_id": _clean(row.get("source_id")),
                "document_type": _clean(row.get("doc_type")),
                "condition_code": _clean(row.get("cd_co")),
                "sale_price": _money(row.get("total_sales_price")),
                "sale_price_raw": _clean(row.get("total_sales_price")),
                "grantor": _clean(row.get("grantor")),
                "grantee": _clean(row.get("grantee")),
                "source_row": dict(row),
            }
        )
    return result


def _improvements(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = raw.get("improvements")
    if not isinstance(rows, Sequence):
        return []
    result = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result.append(
            {
                "building_number": _clean(row.get("bldg_number")),
                "year_built": _integer(row.get("year_built")),
                "description": _clean(row.get("description")),
                "livable_size": _integer(row.get("livable_size")),
                "stat_class": _clean(row.get("stat_class")),
                "code_area": _clean(row.get("code_area")),
                "reports": list(row.get("links") or []),
                "source_row": dict(row),
            }
        )
    return result


def _payoff(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    calculator = raw.get("payment_calculator")
    if not isinstance(calculator, Mapping):
        return None
    tables = calculator.get("tables")
    if not isinstance(tables, Sequence):
        return {"source_dialog": dict(calculator)}
    metadata: dict[str, Any] = {}
    schedule: list[dict[str, Any]] = []
    for table in tables:
        if not isinstance(table, Mapping):
            continue
        headers = table.get("headers")
        rows = table.get("rows")
        if not isinstance(rows, Sequence):
            continue
        if isinstance(headers, Sequence) and headers:
            keys = [
                re.sub(r"[^a-z0-9]+", "_", str(header).casefold()).strip("_")
                for header in headers
            ]
            for row in rows:
                if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
                    continue
                values = list(row)
                item = {
                    key: _clean(values[index]) if index < len(values) else None
                    for index, key in enumerate(keys)
                }
                schedule.append(
                    {
                        "payments_between": item.get("payments_between"),
                        "payoff_amount": _money(item.get("payoff_amount")),
                        "minimum_payment": _money(item.get("minimum_payment")),
                        "interest_included": _money(item.get("interest_included")),
                        "next_payment_date": _date_iso(item.get("next_payment_date")),
                        "source_row": item,
                    }
                )
        else:
            for row in rows:
                if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
                    continue
                values = [_clean(value) for value in row]
                for index in range(0, len(values) - 1, 2):
                    if values[index]:
                        metadata[values[index].casefold().replace(" ", "_")] = values[
                            index + 1
                        ]
    return {
        "tax_id": metadata.get("tax_id"),
        "as_of_date": _date_iso(metadata.get("as_of_date")),
        "current_due": _money(metadata.get("current_due")),
        "amount_due_by_month": schedule,
        "source_dialog": dict(calculator),
    }


def _normalize_detail_record(
    tenant: PropertyTenant,
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    account_id = _clean(raw.get("account_id"))
    roll_type = _clean(raw.get("roll_type"))
    if account_id is None or roll_type is None:
        raise SelectionError(
            "source_detail_identity_changed",
            "PSO detail is missing account or roll type",
            status=ResultStatus.SOURCE_CHANGED,
        )
    map_taxlot = _clean(raw.get("map_taxlot"))
    native_id = map_taxlot or account_id
    owners_raw = raw.get("owners")
    owners = []
    if isinstance(owners_raw, Sequence):
        for owner in owners_raw:
            if not isinstance(owner, Mapping):
                continue
            name = _clean(owner.get("raw_name"))
            if name:
                owners.append(
                    {
                        "raw_name": name,
                        "role": _clean(owner.get("role")),
                    }
                )
    assessment = _assessment(raw)
    history = _assessment_history(raw)
    if assessment is not None and not history:
        history = [dict(assessment)]
    sales = _sales(raw)
    facts = (
        dict(raw.get("property_facts"))
        if isinstance(raw.get("property_facts"), Mapping)
        else {}
    )
    tax_raw = (
        dict(raw.get("tax_account"))
        if isinstance(raw.get("tax_account"), Mapping)
        else {}
    )
    payoff = _payoff(raw)
    return {
        "source_id": tenant.source_id,
        "source_name": tenant.source.name,
        "source_url": _clean(raw.get("source_url")) or tenant.portal_root,
        "record_kind": "property_account",
        "record_view": "full_detail",
        "snapshot_complete": True,
        "native_parcel_id": native_id,
        "native_account_id": account_id,
        "assessment_account_ids": [account_id],
        "alternate_parcel_ids": [account_id],
        "map_taxlot": map_taxlot,
        "roll_type": roll_type,
        "property_type": _clean(raw.get("property_heading")),
        "canonical_ref": canonical_property_ref(
            tenant.source_id,
            tenant.county_fips,
            "parcel",
            native_id,
        ),
        "jurisdiction": _jurisdiction_record(tenant),
        "situs_address": _address(raw.get("situs_address")),
        "additional_situs_addresses": [
            address
            for address in (
                _address(value)
                for value in (raw.get("additional_situs_addresses") or [])
            )
            if address is not None
        ],
        "mailing_address": _mailing_address(raw.get("mailing_address_lines")),
        "owners": owners,
        "assessment": assessment,
        "assessment_history": history,
        "tax_year": (
            assessment.get("tax_year") if isinstance(assessment, Mapping) else None
        ),
        "tax_status": _clean(facts.get("account_status")),
        "tax_code_area": _clean(tax_raw.get("code_area")),
        "tax_state": {
            "tax_account_id": _clean(tax_raw.get("tax_id")),
            "current_balance_due": _money(tax_raw.get("amount_due")),
            "current_balance_due_raw": _clean(tax_raw.get("amount_due")),
            "payoff": payoff,
            "payment_history": (
                dict(raw.get("payment_history"))
                if isinstance(raw.get("payment_history"), Mapping)
                else None
            ),
        },
        "sale_history": sales,
        "last_sale": sales[0] if sales else None,
        "physical_characteristics": {
            "size": _clean(facts.get("size")),
            "property_class": _clean(facts.get("property_class")),
            "legal_description": _clean(facts.get("legal_description")),
        },
        "notations": [
            dict(value)
            for value in (raw.get("notations") or [])
            if isinstance(value, Mapping)
        ],
        "special_assessments": [
            dict(value)
            for value in (raw.get("special_assessments") or [])
            if isinstance(value, Mapping)
        ],
        "improvements": _improvements(raw),
        "account_history": [
            dict(value)
            for value in (raw.get("account_history") or [])
            if isinstance(value, Mapping)
        ],
        "documents": [
            dict(value)
            for value in [
                *(raw.get("downloads") or []),
                *(raw.get("files") or []),
            ]
            if isinstance(value, Mapping)
        ],
        "response_schema_fingerprint": sha256_fingerprint(
            raw.get("schema_shape") or {}
        ),
        "source_record": dict(raw),
    }


def _validate_search_page(
    raw: Mapping[str, Any],
    *,
    native_option: str,
    query: str,
    page: int,
) -> tuple[list[Mapping[str, Any]], int]:
    if raw.get("authoritative_empty"):
        return [], int(raw.get("total_pages") or 1)
    records_raw = raw.get("records")
    if not isinstance(records_raw, Sequence):
        raise SelectionError(
            "source_search_schema_changed",
            "PSO search payload has no result list",
            status=ResultStatus.SOURCE_CHANGED,
        )
    records = [value for value in records_raw if isinstance(value, Mapping)]
    if not records:
        raise SelectionError(
            "source_search_outcome_unknown",
            "PSO rendered neither result cards nor an explicit empty outcome",
            status=ResultStatus.SOURCE_CHANGED,
        )
    if raw.get("search_option") != native_option:
        raise SelectionError(
            "source_search_selector_mismatch",
            "PSO rendered a different native search option",
            status=ResultStatus.SOURCE_CHANGED,
            details={
                "expected": native_option,
                "observed": raw.get("search_option"),
            },
        )
    if _clean(raw.get("search_value")) != query:
        raise SelectionError(
            "source_search_value_mismatch",
            "PSO rendered a different search value",
            status=ResultStatus.SOURCE_CHANGED,
        )
    try:
        observed_page = int(raw.get("page_number"))
        total_pages = int(raw.get("total_pages"))
    except (TypeError, ValueError) as error:
        raise SelectionError(
            "source_pagination_changed",
            "PSO pagination fields are malformed",
            status=ResultStatus.SOURCE_CHANGED,
        ) from error
    if observed_page != page or total_pages < observed_page:
        raise SelectionError(
            "source_pagination_changed",
            "PSO returned an inconsistent page boundary",
            status=ResultStatus.SOURCE_CHANGED,
            details={
                "expected_page": page,
                "observed_page": observed_page,
                "total_pages": total_pages,
            },
        )
    return records, total_pages


def _search_result(
    query_envelope: PublicRecordsQuery,
    tenant: PropertyTenant,
    *,
    field: str,
    native_option: str,
    value: str,
    limit: int,
    cursor: str | None,
    client: OregonPSOClient,
) -> PublicRecordsResult:
    fingerprint = _query_fingerprint(
        tenant,
        field=field,
        native_option=native_option,
        query=value,
    )
    state = (
        _decode_cursor(
            cursor,
            tenant=tenant,
            query_fingerprint=fingerprint,
        )
        if cursor
        else None
    )
    current_page = state.page_number if state else 1
    raw = client.search(
        tenant,
        search_option=native_option,
        query=value,
        page=current_page,
    )
    page_records, total_pages = _validate_search_page(
        raw,
        native_option=native_option,
        query=value,
        page=current_page,
    )
    if not page_records:
        if state is not None:
            raise SelectionError(
                "cursor_result_set_changed",
                "the resumed query is now empty",
                status=ResultStatus.SOURCE_CHANGED,
            )
        return PublicRecordsResult.success(query_envelope, [])

    count_changed = state is not None and state.total_pages != total_pages
    start_index = 0
    if state is not None:
        anchor_index = state.position_on_page - 1
        if anchor_index >= len(page_records):
            raise SelectionError(
                "cursor_anchor_not_in_page",
                "the prior boundary position is no longer present",
                status=ResultStatus.SOURCE_CHANGED,
            )
        observed_anchor = _record_anchor(page_records[anchor_index])
        if observed_anchor != state.anchor:
            raise SelectionError(
                "cursor_anchor_mismatch",
                "the prior boundary record changed before continuation",
                status=ResultStatus.SOURCE_CHANGED,
                details={
                    "expected_anchor": state.anchor,
                    "observed_anchor": observed_anchor,
                },
            )
        start_index = anchor_index + 1

    collected: list[tuple[int, int, Mapping[str, Any]]] = []
    page = current_page
    records = page_records
    index = start_index
    while len(collected) < limit:
        while index < len(records) and len(collected) < limit:
            collected.append((page, index + 1, records[index]))
            index += 1
        if len(collected) >= limit or page >= total_pages:
            break
        page += 1
        raw = client.search(
            tenant,
            search_option=native_option,
            query=value,
            page=page,
        )
        records, observed_total_pages = _validate_search_page(
            raw,
            native_option=native_option,
            query=value,
            page=page,
        )
        if observed_total_pages != total_pages:
            count_changed = True
            total_pages = observed_total_pages
        index = 0
        if not records:
            break

    if not collected:
        return PublicRecordsResult.success(query_envelope, [])
    last_page, last_position, last_record = collected[-1]
    page_length = len(records) if last_page == page else NATIVE_PAGE_SIZE
    has_more = last_position < page_length or last_page < total_pages
    next_cursor = (
        _encode_cursor(
            CursorState(
                source_id=tenant.source_id,
                query_fingerprint=fingerprint,
                page_number=last_page,
                position_on_page=last_position,
                anchor=_record_anchor(last_record),
                total_pages=total_pages,
            )
        )
        if has_more
        else None
    )
    coverage = {
        "returned_records": len(collected),
        "native_page_size": NATIVE_PAGE_SIZE,
        "source_reported_total_pages": total_pages,
        "first_returned_page": collected[0][0],
        "first_position_on_page": collected[0][1],
        "last_returned_page": last_page,
        "last_position_on_page": last_position,
        "cursor_anchor_verified": state is not None,
        "total_pages_changed_since_cursor": count_changed,
        "complete_for_selected_query": not has_more and not count_changed,
    }
    normalized = [
        _normalize_search_record(
            tenant,
            item,
            coverage=coverage,
            query_fingerprint=fingerprint,
        )
        for _, _, item in collected
    ]
    if count_changed:
        return PublicRecordsResult.failure(
            query_envelope,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="result_pages_changed_during_continuation",
                    message=(
                        "The source-reported page count changed while the "
                        "boundary anchor still matched."
                    ),
                    category="pagination",
                    retryable=True,
                    details=coverage,
                )
            ],
            records=normalized,
            next_cursor=next_cursor,
        )
    return PublicRecordsResult.success(
        query_envelope,
        normalized,
        next_cursor=next_cursor,
    )


def _build_query(
    args: argparse.Namespace,
    tenant: PropertyTenant,
    *,
    search_field: str | None = None,
    native_option: str | None = None,
    search_value: str | None = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {
        "tenant_key": tenant.key,
        "platform_family": PLATFORM_FAMILY,
    }
    if args.command == "search":
        parameters.update(
            {
                "field": search_field,
                "native_search_option": native_option,
                "value": search_value,
                "continuation": ("query_bound_native_page_and_boundary_anchor"),
            }
        )
    elif args.command == "detail":
        parameters.update(
            {
                "account_id": args.account,
                "roll_type": args.roll_type,
            }
        )
    return PublicRecordsQuery(
        source=tenant.source,
        jurisdiction=tenant.jurisdiction,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=(args.limit if args.command == "search" else None),
            cursor=(args.cursor if args.command == "search" else None),
            metadata={"access_decision": dict(access_decision or {})},
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    if isinstance(error, SelectionError):
        return PublicRecordsResult.failure(
            query,
            error.status,
            [
                PublicRecordsError(
                    code=error.code,
                    message=str(error),
                    category="query_or_source_boundary",
                    retryable=False,
                    details=error.details,
                )
            ],
        )
    if isinstance(error, BrowserHelperError):
        code = error.code
        if code == "source_http_429":
            status = ResultStatus.RATE_LIMITED
            category = "rate_limit"
        elif code in {"source_http_401", "source_http_403"}:
            status = ResultStatus.RESTRICTED
            category = "source_access"
        elif code in {"source_http_404", "source_http_410"}:
            status = ResultStatus.SOURCE_CHANGED
            category = "source_route"
        elif code in {
            "browser_runtime_unavailable",
            "node_runtime_unavailable",
            "browser_helper_missing",
        }:
            status = ResultStatus.UNAVAILABLE
            category = "runtime"
        else:
            status = ResultStatus.UNAVAILABLE
            category = "browser_transport"
        return PublicRecordsResult.failure(
            query,
            status,
            [
                PublicRecordsError(
                    code=code,
                    message=str(error),
                    category=category,
                    retryable=error.retryable,
                    details=error.details,
                )
            ],
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
    )


def _log(query: PublicRecordsQuery, source_id: str, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), source_id, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: OregonPSOClient | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one PSO operation through the shared public-record envelope."""

    tenant = _tenant_from_args(args)
    search_field = None
    native_option = None
    search_value = None
    try:
        if args.command == "search":
            search_field = str(args.field)
            if search_field not in tenant.search_options:
                raise SelectionError(
                    "search_field_not_available",
                    (
                        f"{tenant.county_name} exposes: "
                        f"{', '.join(tenant.search_options)}"
                    ),
                    details={
                        "requested_field": search_field,
                        "available_fields": list(tenant.search_options),
                    },
                )
            native_option = tenant.search_options[search_field]
            search_value = _clean(args.query)
            if search_value is None:
                raise SelectionError(
                    "empty_search_value",
                    "search value must not be blank",
                )
            if args.limit <= 0:
                raise SelectionError(
                    "invalid_limit",
                    "--limit must be a positive integer",
                )
        elif args.command == "detail":
            if _clean(args.account) is None:
                raise SelectionError(
                    "empty_account_id",
                    "account ID must not be blank",
                )
            if not re.fullmatch(r"[A-Za-z0-9_-]+", args.roll_type):
                raise SelectionError(
                    "invalid_roll_type",
                    "roll type must use the source route token",
                )
        query = _build_query(
            args,
            tenant,
            search_field=search_field,
            native_option=native_option,
            search_value=search_value,
            access_decision=access_decision,
        )
    except SelectionError as error:
        query = _build_query(
            args,
            tenant,
            access_decision=access_decision,
        )
        result = _failure(query, error)
        if log_results:
            _log(query, tenant.source_id, None)
        return result

    source_client = client or OregonPSOClient(timeout=float(args.timeout))
    try:
        if args.command == "source":
            result = PublicRecordsResult.success(
                query,
                [_source_record(tenant)],
            )
        elif args.command == "probe":
            raw = source_client.probe(tenant)
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "canonical_ref": (
                            f"ORPSO_PROBE:{tenant.county_fips}:"
                            f"{hashlib.sha256(tenant.portal_root.encode()).hexdigest()[:12]}"
                        ),
                        "record_kind": "source_probe",
                        "source_id": tenant.source_id,
                        "county_name": tenant.county_name,
                        "observed_access": dict(tenant.access_observation),
                        "live_probe": dict(raw),
                        "search_option_match": {
                            option.get("value"): option.get("label")
                            for option in raw.get("search_options", [])
                            if isinstance(option, Mapping)
                        },
                    }
                ],
            )
        elif args.command == "search":
            assert native_option is not None
            assert search_field is not None
            assert search_value is not None
            result = _search_result(
                query,
                tenant,
                field=search_field,
                native_option=native_option,
                value=search_value,
                limit=int(args.limit),
                cursor=args.cursor,
                client=source_client,
            )
        elif args.command == "detail":
            raw = source_client.detail(
                tenant,
                account=str(args.account),
                roll_type=str(args.roll_type),
            )
            result = PublicRecordsResult.success(
                query,
                [_normalize_detail_record(tenant, raw)],
            )
        else:
            raise SelectionError(
                "unsupported_command",
                f"unsupported command: {args.command}",
            )
    except (OregonPSOError, TypeError, ValueError) as error:
        result = _failure(query, error)
    finally:
        if client is None:
            source_client.close()

    if log_results:
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
        _log(query, tenant.source_id, count)
    return result


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True, choices=SOURCE_IDS)


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Query distinct Oregon county Helion/ORCATS property sources")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="List all county source components",
    )
    add_output_args(sources)

    source = subparsers.add_parser(
        "source",
        help="Show one county source, observed access, and complements",
    )
    _add_source(source)
    _add_runtime(source)

    probe = subparsers.add_parser(
        "probe",
        help="Render the live public search form and native option set",
    )
    _add_source(probe)
    _add_runtime(probe)

    search = subparsers.add_parser(
        "search",
        help="Search one county's public property accounts",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=("account", "tax_account", "name", "address", "map", "legal"),
        default="name",
    )
    search.add_argument("--limit", type=int, default=NATIVE_PAGE_SIZE)
    search.add_argument("--cursor")
    _add_source(search)
    _add_runtime(search)

    detail = subparsers.add_parser(
        "detail",
        help="Render one account's assessment, tax, sale, and improvement detail",
    )
    detail.add_argument("account")
    detail.add_argument("--roll-type", default="R")
    _add_source(detail)
    _add_runtime(detail)
    return parser


def _emit_sources(args: argparse.Namespace) -> None:
    records = [_source_record(tenant) for tenant in TENANTS]
    payload = {
        "platform_family": PLATFORM_FAMILY,
        "source_count": len(records),
        "sources": records,
    }
    if write_output(
        payload,
        args,
        summary="Oregon PSO county sources",
        result_count=len(records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for record in records:
        print(
            f"{record['source_id']} | {record['county_name']} | "
            f"{record['access_observation']['outcome']}"
        )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    tenant = TENANTS_BY_SOURCE[args.source]
    if write_output(
        payload,
        args,
        summary=(f"{tenant.county_name} PSO {args.command} ({result.status.value})"),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"{tenant.source.name} {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            "  "
            f"{record.get('native_account_id') or record.get('name') or '?'} "
            f"| {record.get('map_taxlot') or record.get('record_kind') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "sources":
        _emit_sources(args)
        return
    try:
        result = execute(args)
    except (OregonPSOError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
