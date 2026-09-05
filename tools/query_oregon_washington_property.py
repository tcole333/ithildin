#!/usr/bin/env python3
"""Query Washington County, Oregon property and survey record components.

The county publishes related records through several systems with different
native identifiers and capabilities.  This adapter keeps those representations
attributable while exposing their exact joins:

* Survey Explorer JSON search/detail and resolved source documents
* Survey Explorer ArcGIS geometry layers
* the current county taxlot FeatureServer
* the county situs-address MapServer
* legacy Intermap parcel, assessment, and tax-map reports
* the Washington County Tyler guest property and tax-statement site

Examples:
    uv run python tools/query_oregon_washington_property.py sources
    uv run python tools/query_oregon_washington_property.py survey-search \
        survey 35242 --output /tmp/washington-survey.json
    uv run python tools/query_oregon_washington_property.py survey-detail \
        plat 2026-021 --output /tmp/washington-plat.json
    uv run python tools/query_oregon_washington_property.py survey-document \
        survey 35242 --destination /tmp/35242.pdf
    uv run python tools/query_oregon_washington_property.py arcgis \
        survey-taxlots --field TLID --query 2N2330002700 --match exact
    uv run python tools/query_oregon_washington_property.py taxlots \
        2N2330002700 --field TLNO --match exact --geometry
    uv run python tools/query_oregon_washington_property.py situs \
        2N2330002700 --field TAXLOT --match exact
    uv run python tools/query_oregon_washington_property.py intermap \
        2N2330002700 --report all
    uv run python tools/query_oregon_washington_property.py tax-account R2069997
    uv run python tools/query_oregon_washington_property.py tax-statement \
        R2069997 2025 --destination /tmp/R2069997-2025.pdf
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
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
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
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
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )


STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_NAME = "Washington County, Oregon"
COUNTY_GEOID = "41067"

SURVEY_API_SOURCE_ID = "us-or-washington-county-survey-explorer-api"
SURVEY_MAP_SOURCE_ID = "us-or-washington-county-survey-explorer-arcgis"
TAXLOT_SOURCE_ID = "us-or-washington-county-taxlots"
SITUS_SOURCE_ID = "us-or-washington-county-situs-addresses"
INTERMAP_SOURCE_ID = "us-or-washington-county-intermap-property"
TAX_SOURCE_ID = "us-or-washington-county-washcotax"
PORTLAND_REGIONAL_SOURCE_ID = "us-or-portland-regional-taxlots"

SURVEY_APP_URL = "https://webapps.washingtoncountyor.gov/surveyexplorer/"
SURVEY_API_BASE = "https://api.washingtoncountyor.gov/v1/services/survey"
SURVEY_SEARCH_URL = f"{SURVEY_API_BASE}/search/"
SURVEY_DETAIL_URL = f"{SURVEY_API_BASE}/id/"
SURVEY_INPUT_URL = f"{SURVEY_API_BASE}/input"
SURVEY_MAP_URL = (
    "https://gispub.co.washington.or.us/server/rest/services/"
    "LUT_ETS/Survey_Explorer/MapServer"
)
TAXLOT_LAYER_URL = (
    "https://gispub.co.washington.or.us/server/rest/services/"
    "Washington_County_Taxlots/FeatureServer/0"
)
SITUS_LAYER_URL = (
    "https://gispub.co.washington.or.us/server/rest/services/"
    "Intermap/Situs_address_WMAS/MapServer/0"
)
INTERMAP_BASE_URL = "https://gisims.co.washington.or.us/GIS/index.cfm"
TAX_BASE_URL = "https://washcotax.co.washington.or.us"
TAX_DETAIL_ROUTE = "/Property-Detail/PropertyQuickRefID/{account}"
TAX_STATEMENT_GENERATOR_URL = f"{TAX_BASE_URL}/ProxyG/tax/TaxStatement"
TAX_GENERATED_DOCUMENT_BASE = f"{TAX_BASE_URL}/ProxyG/documents/pdf"

SURVEY_DOCUMENT_BASE = "https://mtbachelor.co.washington.or.us/images"
SURVEY_PDF_BUILDER_URL = f"{SURVEY_DOCUMENT_BASE}/pdfbuilderasp/tiff2pdf.asp"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAX_JSON_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_HTML_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_DOCUMENT_BYTES = 32 * 1024 * 1024
# ArcGIS request batch size. Caller result bounds are independent of transport.
DEFAULT_PAGE_SIZE = 100
DEFAULT_RETRY_ATTEMPTS = 3
USER_AGENT = "IthildinOSINT/1.0 Washington County public-record client"
CURSOR_PREFIX = "oregon-washington-property:v1:"
CURSOR_VERSION = 1

PROBE_TAXLOT = "2N2330002700"
PROBE_ACCOUNT = "R2069997"
PROBE_SURVEY = "35242"
PROBE_PLAT = "2026-021"

SURVEY_API_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://webapps.washingtoncountyor.gov",
    "Referer": SURVEY_APP_URL,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Washington County",
    metadata={"state_fips": STATE_FIPS},
)


def _source(
    source_id: str,
    name: str,
    role: str,
    base_url: str,
    dataset_id: str,
    *,
    publisher: str,
    metadata: Mapping[str, Any] | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        name=name,
        source_role=role,
        base_url=base_url,
        dataset_id=dataset_id,
        metadata={
            "publisher": publisher,
            "county_geoid": COUNTY_GEOID,
            **dict(metadata or {}),
        },
    )


SOURCES: dict[str, SourceMetadata] = {
    SURVEY_API_SOURCE_ID: _source(
        SURVEY_API_SOURCE_ID,
        "Washington County Survey Explorer API",
        "official_county_survey_plat_taxlot_and_map_index",
        SURVEY_APP_URL,
        "washington-county-survey-explorer-api",
        publisher="Washington County Surveyor",
        metadata={
            "transport": {
                "api_url": SURVEY_API_BASE,
                "request_profile": "browser_equivalent_public_app_request",
            },
            "native_identifiers": [
                "Surveynumber",
                "Platname",
                "DocNumber",
                "TLID",
                "ACCOUNT",
                "CORNERID",
                "CROAD_ID",
            ],
        },
    ),
    SURVEY_MAP_SOURCE_ID: _source(
        SURVEY_MAP_SOURCE_ID,
        "Washington County Survey Explorer ArcGIS",
        "official_county_survey_and_land_record_geometry",
        SURVEY_MAP_URL,
        "4f7b09aab8eb4033bf5f5d35f11033f7",
        publisher="Washington County Land Use and Transportation",
        metadata={
            "platform_family": "arcgis_mapserver",
            "source_crs": "EPSG:2913",
            "lineage": (
                "Geometry companion to Survey Explorer API records; matching "
                "records are linked representations, not corroboration."
            ),
        },
    ),
    TAXLOT_SOURCE_ID: _source(
        TAXLOT_SOURCE_ID,
        "Washington County Current Taxlots",
        "official_county_current_taxlot_geometry",
        TAXLOT_LAYER_URL,
        "c8d84fcec9574060b05ba3854a2df62e/layer-0",
        publisher="Washington County Cartography Division",
        metadata={
            "platform_family": "arcgis_featureserver",
            "source_crs": "EPSG:2913",
            "publisher_note": (
                "Not all tax lots have been digitized; some boundaries were "
                "drawn with heads-up digitization and may not match imagery."
            ),
        },
    ),
    SITUS_SOURCE_ID: _source(
        SITUS_SOURCE_ID,
        "Washington County Situs Addresses",
        "official_county_situs_address_points",
        SITUS_LAYER_URL,
        "437932a23a944b86a34f10ef756a22c5/layer-0",
        publisher="Washington County GIS",
        metadata={
            "platform_family": "arcgis_mapserver",
            "published_crs": "EPSG:3857",
            "source_crs": "EPSG:2269",
        },
    ),
    INTERMAP_SOURCE_ID: _source(
        INTERMAP_SOURCE_ID,
        "Washington County Legacy Intermap Reports",
        "official_county_property_assessment_and_tax_map_reports",
        INTERMAP_BASE_URL,
        "washington-county-intermap-reports",
        publisher="Washington County GIS and Assessment and Taxation",
        metadata={
            "representations": ["parcel", "assessment", "tax_map"],
            "native_join": "IDValue=TLNO",
        },
    ),
    TAX_SOURCE_ID: _source(
        TAX_SOURCE_ID,
        "Washington County Assessment and Taxation Guest",
        "official_county_property_tax_value_improvement_and_payment_records",
        TAX_BASE_URL,
        "washington-county-tyler-property-tax-guest",
        publisher="Washington County Assessment and Taxation",
        metadata={
            "platform_family": "tyler_property_search_oregon",
            "native_identifiers": [
                "PropertyQuickRefID",
                "PartyQuickRefID",
                "PropertyID",
                "PartyID",
                "transactionID",
            ],
        },
    ),
}

COMPLEMENTS: tuple[Mapping[str, Any], ...] = (
    {
        "source_id": PORTLAND_REGIONAL_SOURCE_ID,
        "name": "Portland/Metro Regional Taxlots",
        "relationship": "regional_standardized_taxlot_representation",
        "join_fields": ["TLID", "account"],
        "adds": [
            "regional parcel schema",
            "public owner and value fields where published",
        ],
        "lineage_note": (
            "County-contributed and regional records may share source lineage; "
            "row overlap alone is not independent corroboration."
        ),
    },
    {
        "name": "Washington County Recording and Copy Requests",
        "url": "https://www.washingtoncountyor.gov/at/recording",
        "relationship": "recorded_instrument_and_copy_route",
        "join_fields": ["DocNumber", "party", "recording date"],
        "adds": ["official recorded instrument index and copies"],
    },
    {
        "name": "Washington County Assessment and Taxation Data Requests",
        "url": "https://www.washingtoncountyor.gov/at",
        "relationship": "bulk_or_custom_assessment_data_route",
        "join_fields": ["account", "TLNO"],
        "adds": ["defined county data-request route"],
    },
    {
        "name": "Washington County Accela Citizen Access",
        "url": "https://washcooraca.com/",
        "relationship": "permit_and_planning_complement",
        "join_fields": ["TLNO", "address", "case number"],
        "adds": ["current permits and land-use records"],
    },
    {
        "name": "Washington County Casefile Archives",
        "url": "https://www.washingtoncountyor.gov/lut/land-use-planning/casefiles",
        "relationship": "older_land_use_casefile_complement",
        "join_fields": ["TLNO", "case number"],
        "adds": ["older casefiles and defined copy routes"],
    },
)


@dataclass(frozen=True)
class SurveyKind:
    key: str
    searchby: str
    default_field: str
    allowed_fields: tuple[str, ...]
    sort_fields: tuple[str, ...]
    native_id_fields: tuple[str, ...]


SURVEY_KINDS: dict[str, SurveyKind] = {
    "survey": SurveyKind(
        "survey",
        "search-survey",
        "surveynumber",
        (
            "surveynumber",
            "surveyornumber",
            "surveyorname",
            "fileddatemin",
            "fileddatemax",
            "receiveddatemin",
            "receiveddatemax",
            "tr",
            "sec",
            "qtr",
            "iclient",
            "city",
            "businessname",
        ),
        ("Surveynumber", "Surveyornumber", "Filed"),
        ("Surveynumber", "Surveyornumber"),
    ),
    "benchmark": SurveyKind(
        "benchmark",
        "search-benchmark",
        "benchmarkid",
        ("benchmarkid", "tr", "sec", "qtr", "city"),
        ("ID", "Benchmark_ID"),
        ("ID", "Benchmark_ID"),
    ),
    "corner": SurveyKind(
        "corner",
        "search-corner",
        "cornerid",
        (
            "cornerid",
            "bookpage",
            "surveyornumber",
            "surveyorname",
            "tr",
            "sec",
            "qtr",
            "city",
        ),
        ("CORNERID", "CORNER_ID", "GPS_ID"),
        ("CORNERID", "CORNER_ID", "GPS_ID"),
    ),
    "geocontrol": SurveyKind(
        "geocontrol",
        "search-geocontrol",
        "controlname",
        (
            "controlname",
            "surveyornumber",
            "surveyorname",
            "tr",
            "sec",
            "qtr",
            "city",
        ),
        ("Fullname", "stationnumber", "Name"),
        ("Fullname", "stationnumber", "corner_id"),
    ),
    "plat": SurveyKind(
        "plat",
        "search-plat",
        "platname",
        (
            "platname",
            "docnumber",
            "bookpage",
            "surveyornumber",
            "surveyorname",
            "recordeddatemin",
            "recordeddatemax",
            "receiveddatemin",
            "receiveddatemax",
            "declarant",
            "tr",
            "sec",
            "qtr",
            "city",
            "businessname",
        ),
        ("Platname", "DocNumber", "Recorded"),
        ("Platname", "DocNumber", "Surveyornumber"),
    ),
    "taxlot": SurveyKind(
        "taxlot",
        "search-taxmap",
        "tlid",
        ("tlid", "sitestrno"),
        ("TLID", "ACCOUNT", "SITEADDR"),
        ("TLID", "ACCOUNT"),
    ),
    "county-road": SurveyKind(
        "county-road",
        "search-countyroad",
        "cntyroadid",
        ("cntyroadid",),
        ("CROAD_ID", "Date"),
        ("CROAD_ID",),
    ),
    "section-map": SurveyKind(
        "section-map",
        "search-smaps",
        "tr",
        ("tr", "sec", "qtr"),
        ("url",),
        ("url",),
    ),
}


@dataclass(frozen=True)
class ArcGISLayer:
    key: str
    source_id: str
    layer_url: str
    sort_fields: tuple[str, ...]
    native_id_fields: tuple[str, ...]
    join_fields: tuple[str, ...]
    source_wkid: int
    expected_count: int | None = None


def _survey_layer(
    key: str,
    layer_id: int,
    sort_fields: Sequence[str],
    native_ids: Sequence[str],
    joins: Sequence[str],
    *,
    expected_count: int | None = None,
) -> ArcGISLayer:
    return ArcGISLayer(
        key=key,
        source_id=SURVEY_MAP_SOURCE_ID,
        layer_url=f"{SURVEY_MAP_URL}/{layer_id}",
        sort_fields=tuple(sort_fields),
        native_id_fields=tuple(native_ids),
        join_fields=tuple(joins),
        source_wkid=2913,
        expected_count=expected_count,
    )


ARCGIS_LAYERS: dict[str, ArcGISLayer] = {
    "addresses": _survey_layer(
        "addresses",
        0,
        ("OBJECTID",),
        ("OBJECTID", "A_ID", "SERIAL", "SITUS_ID"),
        ("TAXLOT", "SERIAL", "FULLADDRESS"),
        expected_count=267_624,
    ),
    "benchmarks": _survey_layer(
        "benchmarks",
        11,
        ("Benchmark_ID", "OBJECTID"),
        ("Benchmark_ID", "OBJECTID"),
        ("Benchmark_ID",),
        expected_count=510,
    ),
    "dedications": _survey_layer(
        "dedications",
        15,
        ("DD_Num", "OBJECTID"),
        ("DD_Num", "GlobalID", "OBJECTID"),
        ("DD_Num",),
        expected_count=8_382,
    ),
    "surveys": _survey_layer(
        "surveys",
        7,
        ("SurvNum", "OBJECTID"),
        ("SurvNum", "Surveyornumber", "OBJECTID"),
        ("SurvNum",),
        expected_count=35_188,
    ),
    "corners": _survey_layer(
        "corners",
        1,
        ("CORNER_ID", "OBJECTID"),
        ("CORNER_ID", "GPS_ID", "OBJECTID"),
        ("CORNER_ID", "GPS_ID"),
        expected_count=3_398,
    ),
    "geocontrol": _survey_layer(
        "geocontrol",
        12,
        ("FULLNAME", "OBJECTID"),
        ("FULLNAME", "STATION_NU", "GlobalID", "OBJECTID"),
        ("FULLNAME", "CORNER_ID"),
        expected_count=1_609,
    ),
    "county-roads": _survey_layer(
        "county-roads",
        13,
        ("CRNUM", "OBJECTID"),
        ("CRNUM", "GlobalID", "OBJECTID"),
        ("CRNUM",),
        expected_count=2_949,
    ),
    "donation-land-claims": _survey_layer(
        "donation-land-claims",
        2,
        ("CLAIM", "OBJECTID"),
        ("CLAIM", "GlobalID", "OBJECTID"),
        ("CLAIM",),
    ),
    "road-vacations": _survey_layer(
        "road-vacations",
        3,
        ("Vac_Num_txt", "OBJECTID"),
        ("Vac_Num_txt", "Document_Number", "GlobalID", "OBJECTID"),
        ("Vac_Num_txt", "Document_Number", "PLAT_NAME"),
        expected_count=583,
    ),
    "plats": _survey_layer(
        "plats",
        4,
        ("Platname", "OBJECTID"),
        ("Platname", "DocNumber", "Surveyornumber", "OBJECTID"),
        ("Platname", "DocNumber"),
        expected_count=9_050,
    ),
    "townships": _survey_layer(
        "townships",
        10,
        ("TILE_NAME", "OBJECTID"),
        ("TILE_NAME", "OBJECTID"),
        ("TILE_NAME",),
    ),
    "sections": _survey_layer(
        "sections",
        9,
        ("TILE_NAME", "Section", "OBJECTID"),
        ("TILE_NAME", "Section", "OBJECTID"),
        ("TILE_NAME", "Section"),
    ),
    "quarter-sections": _survey_layer(
        "quarter-sections",
        5,
        ("TILE", "QTR", "OBJECTID"),
        ("TILE", "QTR", "OBJECTID"),
        ("TILE", "QTR"),
    ),
    "survey-taxlots": _survey_layer(
        "survey-taxlots",
        8,
        ("TLID", "OBJECTID"),
        ("TLNO", "TLID", "ACCOUNT", "OBJECTID"),
        ("TLNO", "TLID", "ACCOUNT", "SITEADDR"),
        expected_count=201_336,
    ),
    "cities": _survey_layer(
        "cities",
        37,
        ("CITYNAME", "OBJECTID"),
        ("CITYNAME", "OBJECTID"),
        ("CITYNAME",),
    ),
    "taxlots": ArcGISLayer(
        key="taxlots",
        source_id=TAXLOT_SOURCE_ID,
        layer_url=TAXLOT_LAYER_URL,
        sort_fields=("TLNO", "OBJECTID"),
        native_id_fields=("TLNO", "MAPNO", "TLNO5", "OBJECTID"),
        join_fields=("TLNO", "MAPNO"),
        source_wkid=2913,
        expected_count=200_588,
    ),
    "situs": ArcGISLayer(
        key="situs",
        source_id=SITUS_SOURCE_ID,
        layer_url=SITUS_LAYER_URL,
        sort_fields=("TAXLOT", "FULLADDRESS", "OBJECTID"),
        native_id_fields=(
            "OBJECTID",
            "A_ID",
            "SERIAL",
            "ACCOUNT_ID",
            "STATICID",
            "SITUS_ID",
        ),
        join_fields=("TAXLOT", "SERIAL", "ACCOUNT_ID", "FULLADDRESS"),
        source_wkid=3857,
        expected_count=267_624,
    ),
}


class WashingtonSelectionError(SourceSchemaError):
    """A query selection or cursor does not match the source contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        url: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, url=url, details=details)
        self.code = code


class ResponseTooLargeError(SourceResponseError):
    """A streamed response exceeded the caller's declared bound."""

    code = "response_too_large"


@dataclass(frozen=True)
class ResponseArtifact:
    content: bytes
    source_url: str
    headers: Mapping[str, str]
    status_code: int

    @property
    def media_type(self) -> str:
        return str(self.headers.get("content-type", "")).split(";", 1)[0].strip()


class WashingtonClient:
    """Bounded, retrying HTTP client with an injectable requests-like session."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_RETRY_ATTEMPTS
        )
        self.limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper
        self._layer_cache: dict[str, Mapping[str, Any]] = {}

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> WashingtonClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        maximum_bytes: int,
    ) -> ResponseArtifact:
        request_headers = {"User-Agent": USER_AGENT, **dict(headers or {})}
        last_transport: TransportError | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True,
                )
            except requests.RequestException as exc:
                last_transport = TransportError(
                    f"request failed: {exc}",
                    url=url,
                    details={"attempt": attempt},
                )
                if attempt == self.retry_policy.max_attempts:
                    raise last_transport from exc
                self.sleeper(self.retry_policy.delay(attempt))
                continue

            try:
                final_url = str(getattr(response, "url", url) or url)
                raw_headers = {
                    str(key).lower(): str(value)
                    for key, value in dict(getattr(response, "headers", {})).items()
                }
                declared_length = _content_length(raw_headers)
                if declared_length is not None and declared_length > maximum_bytes:
                    raise ResponseTooLargeError(
                        "response Content-Length exceeds configured bound",
                        url=final_url,
                        details={
                            "declared_bytes": declared_length,
                            "maximum_bytes": maximum_bytes,
                        },
                    )
                content = bytearray()
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    content.extend(chunk)
                    if len(content) > maximum_bytes:
                        raise ResponseTooLargeError(
                            "streamed response exceeds configured bound",
                            url=final_url,
                            details={
                                "observed_bytes": len(content),
                                "maximum_bytes": maximum_bytes,
                            },
                        )
                status = int(getattr(response, "status_code", 0))
                if status < 200 or status >= 300:
                    retryable = status in self.retry_policy.retry_statuses
                    if retryable and attempt < self.retry_policy.max_attempts:
                        retry_after = _retry_after(raw_headers)
                        self.sleeper(self.retry_policy.delay(attempt, retry_after))
                        continue
                    body = bytes(content).decode("utf-8", errors="replace")
                    if status in {401, 403}:
                        raise RestrictedHTTPError(
                            status,
                            url=final_url,
                            response_text=body,
                        )
                    if status == 429:
                        raise RateLimitedHTTPError(
                            status,
                            url=final_url,
                            response_text=body,
                        )
                    raise HTTPStatusError(
                        status,
                        url=final_url,
                        response_text=body,
                    )
                return ResponseArtifact(
                    content=bytes(content),
                    source_url=final_url,
                    headers=raw_headers,
                    status_code=status,
                )
            finally:
                response.close()

        if last_transport is not None:
            raise last_transport
        raise TransportError("request attempts exhausted", url=url)

    def json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        method: str = "GET",
        maximum_bytes: int = DEFAULT_MAX_JSON_BYTES,
    ) -> tuple[Any, ResponseArtifact]:
        artifact = self.request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
            maximum_bytes=maximum_bytes,
        )
        try:
            payload = json.loads(artifact.content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceResponseError(
                "source did not return valid JSON",
                url=artifact.source_url,
                details={
                    "content_type": artifact.media_type,
                    "body_prefix": artifact.content[:200].decode(
                        "utf-8",
                        errors="replace",
                    ),
                },
            ) from exc
        return payload, artifact

    def text(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        maximum_bytes: int = DEFAULT_MAX_HTML_BYTES,
    ) -> tuple[str, ResponseArtifact]:
        artifact = self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            maximum_bytes=maximum_bytes,
        )
        return artifact.content.decode("utf-8", errors="replace"), artifact

    def survey_search(
        self,
        kind: SurveyKind,
        filters: Mapping[str, str],
    ) -> tuple[Mapping[str, Any], ResponseArtifact]:
        payload, artifact = self.json(
            SURVEY_SEARCH_URL,
            params={"searchby": kind.searchby, **dict(filters)},
            headers=SURVEY_API_HEADERS,
        )
        return _validate_survey_envelope(payload, artifact.source_url), artifact

    def survey_detail(
        self,
        kind: SurveyKind,
        uid: str,
    ) -> tuple[Mapping[str, Any], ResponseArtifact]:
        payload, artifact = self.json(
            SURVEY_DETAIL_URL,
            params={"type": kind.searchby, "uid": uid},
            headers=SURVEY_API_HEADERS,
        )
        return _validate_survey_envelope(payload, artifact.source_url), artifact

    def layer_metadata(self, config: ArcGISLayer) -> Mapping[str, Any]:
        if config.layer_url not in self._layer_cache:
            payload, artifact = self.json(config.layer_url, params={"f": "json"})
            if not isinstance(payload, Mapping) or "fields" not in payload:
                raise SourceSchemaError(
                    "ArcGIS layer metadata is missing fields",
                    url=artifact.source_url,
                )
            if "error" in payload:
                raise SourceResponseError(
                    "ArcGIS layer returned an error",
                    url=artifact.source_url,
                    details={"error": payload["error"]},
                )
            self._layer_cache[config.layer_url] = payload
        return self._layer_cache[config.layer_url]

    def arcgis_query(
        self,
        config: ArcGISLayer,
        params: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], ResponseArtifact]:
        payload, artifact = self.json(
            f"{config.layer_url}/query",
            params={"f": "json", **dict(params)},
        )
        if not isinstance(payload, Mapping):
            raise SourceResponseError(
                "ArcGIS query returned a non-object",
                url=artifact.source_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "ArcGIS query returned an error",
                url=artifact.source_url,
                details={"error": payload["error"]},
            )
        return payload, artifact


def _content_length(headers: Mapping[str, str]) -> int | None:
    raw = headers.get("content-length")
    if raw is None:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _retry_after(headers: Mapping[str, str]) -> float | None:
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def _validate_survey_envelope(
    payload: Any,
    source_url: str,
) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise SourceResponseError(
            "Survey Explorer returned a non-object response",
            url=source_url,
        )
    data = payload.get("data")
    if isinstance(data, Mapping) and isinstance(data.get("error"), Mapping):
        error = data["error"]
        code = int(error.get("code") or 0)
        if code in {401, 403}:
            raise RestrictedHTTPError(
                code,
                url=source_url,
                response_text=canonical_json(error),
            )
        raise SourceResponseError(
            "Survey Explorer returned an error",
            url=source_url,
            details={"error": error},
        )
    if not isinstance(data, (list, Mapping)):
        raise SourceSchemaError(
            "Survey Explorer response is missing data",
            url=source_url,
            details={"keys": sorted(str(key) for key in payload)},
        )
    total = payload.get("total")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise SourceSchemaError(
            "Survey Explorer response has an invalid total",
            url=source_url,
            details={"total": total},
        )
    return payload


def _normalize_date(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("date")
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate or None


def _sortable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _normalize_date(value) or canonical_json(value)
    if isinstance(value, (str, int, float)) or value is None:
        return value
    return canonical_json(value)


def _sort_key(values: Sequence[Any]) -> tuple[tuple[int, Any], ...]:
    def key(value: Any) -> tuple[int, Any]:
        if value is None:
            return (0, "")
        if isinstance(value, bool):
            return (1, int(value))
        if isinstance(value, (int, float)):
            return (2, value)
        return (3, str(value).casefold())

    return tuple(key(value) for value in values)


def _survey_sort_tuple(record: Mapping[str, Any], kind: SurveyKind) -> list[Any]:
    values = [_sortable(record.get(field)) for field in kind.sort_fields]
    values.append(sha256_fingerprint(record))
    return values


def _native_subset(
    record: Mapping[str, Any],
    field_names: Sequence[str],
) -> dict[str, Any]:
    return {name: record.get(name) for name in field_names if name in record}


def _survey_record(
    record: Mapping[str, Any],
    *,
    kind: SurveyKind,
    operation: str,
    source_url: str,
) -> dict[str, Any]:
    native_ids = _native_subset(record, kind.native_id_fields)
    tlid = record.get("TLID")
    account = record.get("ACCOUNT")
    joins: dict[str, Any] = {
        SURVEY_MAP_SOURCE_ID: _native_subset(
            record,
            (
                "Surveynumber",
                "Platname",
                "DocNumber",
                "TLID",
                "ACCOUNT",
                "CORNERID",
                "CROAD_ID",
            ),
        )
    }
    if tlid or account:
        joins[TAXLOT_SOURCE_ID] = {"TLNO": tlid}
        joins[SITUS_SOURCE_ID] = {"TAXLOT": tlid, "account": account}
        joins[INTERMAP_SOURCE_ID] = {"IDValue": tlid}
        joins[TAX_SOURCE_ID] = {"PropertyQuickRefID": account}
        joins[PORTLAND_REGIONAL_SOURCE_ID] = {
            "TLID": tlid,
            "account": account,
        }
    normalized_dates: dict[str, str] = {}
    for key, value in record.items():
        date_like_key = any(
            token in key.casefold()
            for token in ("date", "filed", "received", "recorded", "established")
        )
        if not isinstance(value, Mapping) and not date_like_key:
            continue
        normalized = _normalize_date(value)
        if normalized is not None:
            normalized_dates[key] = normalized
    return {
        "record_type": f"survey_explorer_{kind.key}",
        "operation": operation,
        "native_ids": native_ids,
        "join_candidates": joins,
        "normalized_dates": normalized_dates,
        "native_fields": dict(record),
        "source_url": source_url,
        "source_id": SURVEY_API_SOURCE_ID,
        "lineage": {
            "system": "Survey Explorer API",
            "geometry_companion": SURVEY_MAP_SOURCE_ID,
        },
    }


def _survey_filters(args: argparse.Namespace, kind: SurveyKind) -> dict[str, str]:
    filters: dict[str, str] = {}
    term = str(getattr(args, "query", "") or "").strip()
    field = str(getattr(args, "field", "") or kind.default_field)
    if term:
        if field not in kind.allowed_fields:
            raise WashingtonSelectionError(
                "invalid_survey_field",
                f"{field!r} is not a search field for {kind.key}",
                url=SURVEY_SEARCH_URL,
                details={"allowed_fields": list(kind.allowed_fields)},
            )
        filters[field] = term
    for raw in getattr(args, "filter", ()) or ():
        key, separator, value = raw.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value:
            raise WashingtonSelectionError(
                "invalid_survey_filter",
                "survey filters must use NAME=VALUE",
                url=SURVEY_SEARCH_URL,
                details={"filter": raw},
            )
        if key not in kind.allowed_fields:
            raise WashingtonSelectionError(
                "invalid_survey_field",
                f"{key!r} is not a search field for {kind.key}",
                url=SURVEY_SEARCH_URL,
                details={"allowed_fields": list(kind.allowed_fields)},
            )
        filters[key] = value
    if not filters:
        raise WashingtonSelectionError(
            "missing_survey_filter",
            "Survey Explorer search requires at least one source search field",
            url=SURVEY_SEARCH_URL,
        )
    return filters


def _cursor_encode(payload: Mapping[str, Any]) -> str:
    token = base64.urlsafe_b64encode(canonical_json(payload).encode()).decode()
    return f"{CURSOR_PREFIX}{token.rstrip('=')}"


def _cursor_decode(cursor: str | None) -> Mapping[str, Any] | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise WashingtonSelectionError(
            "invalid_cursor",
            "cursor does not belong to the Washington County adapter",
            url=SURVEY_APP_URL,
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WashingtonSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
            url=SURVEY_APP_URL,
        ) from exc
    if (
        not isinstance(payload, Mapping)
        or payload.get("version") != CURSOR_VERSION
        or not isinstance(payload.get("last_sort"), list)
        or not isinstance(payload.get("criteria"), str)
        or not isinstance(payload.get("snapshot"), str)
        or not isinstance(payload.get("total"), int)
    ):
        raise WashingtonSelectionError(
            "invalid_cursor",
            "cursor values are inconsistent",
            url=SURVEY_APP_URL,
        )
    return payload


def _page_local_records(
    records: Sequence[Mapping[str, Any]],
    *,
    sort_function: Callable[[Mapping[str, Any]], list[Any]],
    criteria: str,
    source_key: str,
    total: int,
    limit: int | None,
    cursor: str | None,
) -> tuple[list[Mapping[str, Any]], str | None, str]:
    sorted_records = sorted(records, key=lambda item: _sort_key(sort_function(item)))
    snapshot = sha256_fingerprint(sorted_records)
    state = _cursor_decode(cursor)
    if state is not None:
        if state.get("source_key") != source_key or state["criteria"] != criteria:
            raise WashingtonSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to different query criteria",
                url=SURVEY_APP_URL,
            )
        if state["snapshot"] != snapshot or state["total"] != total:
            raise WashingtonSelectionError(
                "cursor_snapshot_changed",
                "source records changed after the cursor was issued",
                url=SURVEY_APP_URL,
                details={
                    "cursor_total": state["total"],
                    "current_total": total,
                },
            )
        last_sort_key = _sort_key(state["last_sort"])
        sorted_records = [
            item
            for item in sorted_records
            if _sort_key(sort_function(item)) > last_sort_key
        ]
    selected = sorted_records if limit is None else sorted_records[:limit]
    next_cursor = None
    if limit is not None and len(sorted_records) > limit and selected:
        next_cursor = _cursor_encode(
            {
                "version": CURSOR_VERSION,
                "source_key": source_key,
                "criteria": criteria,
                "snapshot": snapshot,
                "total": total,
                "last_sort": sort_function(selected[-1]),
            }
        )
    return selected, next_cursor, snapshot


def _public_query(
    source_id: str,
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None = None,
    cursor: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCES[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata=dict(metadata or {}),
        ),
    )


def search_survey_api(
    args: argparse.Namespace,
    client: WashingtonClient,
) -> PublicRecordsResult:
    kind = SURVEY_KINDS[args.kind]
    filters = _survey_filters(args, kind)
    query = _public_query(
        SURVEY_API_SOURCE_ID,
        "search",
        {"kind": kind.key, "filters": filters},
        limit=args.limit,
        cursor=args.cursor,
        metadata={
            "sort_tuple": [*kind.sort_fields, "record_fingerprint"],
            "transport_profile": "browser_equivalent_public_app_request",
        },
    )
    envelope, artifact = client.survey_search(kind, filters)
    raw_records = envelope.get("data")
    if not isinstance(raw_records, list) or not all(
        isinstance(item, Mapping) for item in raw_records
    ):
        raise SourceSchemaError(
            "Survey Explorer search data is not a record list",
            url=artifact.source_url,
        )
    total = int(envelope["total"])
    if total != len(raw_records):
        raise SourceSchemaError(
            "Survey Explorer total does not match returned records",
            url=artifact.source_url,
            details={"total": total, "records": len(raw_records)},
        )
    criteria = sha256_fingerprint({"kind": kind.key, "filters": filters})
    selected, next_cursor, _snapshot = _page_local_records(
        raw_records,
        sort_function=lambda record: _survey_sort_tuple(record, kind),
        criteria=criteria,
        source_key=f"survey-api:{kind.key}",
        total=total,
        limit=args.limit,
        cursor=args.cursor,
    )
    records = [
        _survey_record(
            item,
            kind=kind,
            operation="search",
            source_url=artifact.source_url,
        )
        for item in selected
    ]
    return PublicRecordsResult.success(query, records, next_cursor=next_cursor)


def survey_detail(
    args: argparse.Namespace,
    client: WashingtonClient,
) -> PublicRecordsResult:
    kind = SURVEY_KINDS[args.kind]
    uid = args.uid.strip()
    query = _public_query(
        SURVEY_API_SOURCE_ID,
        "detail",
        {"kind": kind.key, "uid": uid},
    )
    envelope, artifact = client.survey_detail(kind, uid)
    raw_records = envelope.get("data")
    if not isinstance(raw_records, list) or not all(
        isinstance(item, Mapping) for item in raw_records
    ):
        raise SourceSchemaError(
            "Survey Explorer detail data is not a record list",
            url=artifact.source_url,
        )
    records = [
        {
            **_survey_record(
                item,
                kind=kind,
                operation="detail",
                source_url=artifact.source_url,
            ),
            "resolved_documents": resolve_survey_documents(kind.key, item),
        }
        for item in raw_records
    ]
    return PublicRecordsResult.success(query, records)


def resolve_survey_documents(
    kind: str,
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    filenames = record.get("filename")
    if filenames is False or filenames is None:
        return []
    if not isinstance(filenames, list):
        raise SourceSchemaError(
            "Survey Explorer filename value is not a list",
            url=SURVEY_DETAIL_URL,
            details={"kind": kind, "filename_type": type(filenames).__name__},
        )
    documents: list[dict[str, Any]] = []
    for index, value in enumerate(filenames):
        if kind == "taxlot" and isinstance(value, Mapping):
            image_name = str(value.get("TaxmapBW") or "").strip()
            if not image_name:
                continue
            url = f"{SURVEY_PDF_BUILDER_URL}?{urlencode({'doctype': 'taxmaps', 'imageto': image_name})}"
            documents.append(
                {
                    "index": index,
                    "native_filename": dict(value),
                    "resolved_url": url,
                    "retrieval_mode": "server_pdf_builder",
                    "document_type": "tax_map",
                }
            )
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        filename = value.strip()
        stem, dot, extension = filename.rpartition(".")
        if not dot:
            stem, extension = filename, ""
        is_pdf = extension.casefold() == "pdf"
        if kind == "survey":
            survey_number = int(record.get("Surveynumber"))
            folder = ((max(1, survey_number) - 1) // 5_000 + 1) * 5_000
            if is_pdf:
                url = (
                    f"{SURVEY_DOCUMENT_BASE}/survey/surveys/{folder}/"
                    f"{quote(filename)}"
                )
                mode = "direct_pdf"
            else:
                url = (
                    f"{SURVEY_PDF_BUILDER_URL}?"
                    f"{urlencode({'doctype': 'surveys', 'imageto': stem})}"
                )
                mode = "server_tiff_to_pdf"
        elif kind == "plat":
            if is_pdf:
                url = f"{SURVEY_DOCUMENT_BASE}/survey/plats/{quote(filename)}"
                mode = "direct_pdf"
            else:
                url = (
                    f"{SURVEY_PDF_BUILDER_URL}?"
                    f"{urlencode({'doctype': 'plats', 'imageto': stem})}"
                )
                mode = "server_tiff_to_pdf"
        else:
            folder_by_kind = {
                "corner": ("BTBOOKS", "btbooks"),
                "geocontrol": ("control", "control"),
                "county-road": ("CoRoads", "coroads"),
            }
            if kind not in folder_by_kind:
                continue
            direct_folder, doctype = folder_by_kind[kind]
            if is_pdf:
                url = (
                    f"{SURVEY_DOCUMENT_BASE}/survey/{direct_folder}/"
                    f"{quote(filename)}"
                )
                mode = "direct_pdf"
            else:
                url = (
                    f"{SURVEY_PDF_BUILDER_URL}?"
                    f"{urlencode({'doctype': doctype, 'imageto': stem})}"
                )
                mode = "server_tiff_to_pdf"
        documents.append(
            {
                "index": index,
                "native_filename": filename,
                "resolved_url": url,
                "retrieval_mode": mode,
                "document_type": kind,
            }
        )
    return documents


def survey_document(
    args: argparse.Namespace,
    client: WashingtonClient,
) -> PublicRecordsResult:
    kind = SURVEY_KINDS[args.kind]
    uid = args.uid.strip()
    query = _public_query(
        SURVEY_API_SOURCE_ID,
        "document",
        {
            "kind": kind.key,
            "uid": uid,
            "file_index": args.file_index,
            "maximum_bytes": args.max_document_bytes,
        },
    )
    envelope, detail_artifact = client.survey_detail(kind, uid)
    raw_records = envelope.get("data")
    if not isinstance(raw_records, list) or not raw_records:
        return PublicRecordsResult.success(query, [])
    raw_record = raw_records[0]
    if not isinstance(raw_record, Mapping):
        raise SourceSchemaError(
            "Survey Explorer detail record is malformed",
            url=detail_artifact.source_url,
        )
    documents = resolve_survey_documents(kind.key, raw_record)
    if args.file_index < 0 or args.file_index >= len(documents):
        raise WashingtonSelectionError(
            "document_index_out_of_range",
            "requested file index is not present on the Survey Explorer record",
            url=detail_artifact.source_url,
            details={
                "file_index": args.file_index,
                "document_count": len(documents),
            },
        )
    document = documents[args.file_index]
    artifact = client.request(
        "GET",
        str(document["resolved_url"]),
        headers={"Referer": SURVEY_APP_URL},
        maximum_bytes=args.max_document_bytes,
    )
    if not artifact.content.startswith(b"%PDF"):
        raise SourceResponseError(
            "resolved Survey Explorer document is not a PDF",
            url=artifact.source_url,
            details={
                "content_type": artifact.media_type,
                "body_prefix": artifact.content[:80].decode(
                    "utf-8",
                    errors="replace",
                ),
            },
        )
    destination = _write_document(args.destination, artifact.content)
    record = {
        "record_type": "survey_explorer_document",
        "kind": kind.key,
        "uid": uid,
        "native_ids": _native_subset(raw_record, kind.native_id_fields),
        "native_filename": document["native_filename"],
        "resolved_url": document["resolved_url"],
        "source_url": artifact.source_url,
        "retrieval_mode": document["retrieval_mode"],
        "media_type": artifact.media_type or "application/pdf",
        "byte_length": len(artifact.content),
        "sha256": hashlib.sha256(artifact.content).hexdigest(),
        "destination": destination,
        "detail_source_url": detail_artifact.source_url,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[artifact.source_url],
    )


def _write_document(destination: str | None, content: bytes) -> str | None:
    if destination is None:
        return None
    output_path = Path(destination)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)
    return str(output_path.resolve())


def _arcgis_field_map(metadata: Mapping[str, Any], url: str) -> dict[str, str]:
    fields = metadata.get("fields")
    if not isinstance(fields, list):
        raise SourceSchemaError("ArcGIS metadata has no field list", url=url)
    output: dict[str, str] = {}
    for field in fields:
        if isinstance(field, Mapping) and isinstance(field.get("name"), str):
            output[str(field["name"])] = str(field.get("type") or "")
    return output


def _field_lookup(fields: Mapping[str, str], requested: str) -> str:
    by_fold = {name.casefold(): name for name in fields}
    matched = by_fold.get(requested.casefold())
    if matched is None:
        raise WashingtonSelectionError(
            "unknown_arcgis_field",
            f"ArcGIS layer does not publish field {requested!r}",
            url=SURVEY_MAP_URL,
            details={"published_fields": sorted(fields)},
        )
    return matched


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _where_for_search(
    *,
    base_where: str | None,
    field: str | None,
    term: str | None,
    match: str,
    fields: Mapping[str, str],
) -> str:
    pieces: list[str] = []
    if base_where and base_where.strip():
        pieces.append(f"({base_where.strip()})")
    if term is not None:
        if field is None:
            raise WashingtonSelectionError(
                "missing_arcgis_field",
                "--query requires --field",
                url=SURVEY_MAP_URL,
            )
        source_field = _field_lookup(fields, field)
        field_type = fields[source_field]
        if "String" in field_type:
            if match == "exact":
                expression = (
                    f"UPPER({source_field}) = "
                    f"UPPER({_sql_string(term.strip())})"
                )
            else:
                escaped = (
                    term.strip()
                    .replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                )
                expression = (
                    f"UPPER({source_field}) LIKE "
                    f"UPPER({_sql_string('%' + escaped + '%')}) ESCAPE '\\\\'"
                )
        else:
            if match != "exact":
                raise WashingtonSelectionError(
                    "invalid_numeric_match",
                    "numeric ArcGIS fields support exact matching",
                    url=SURVEY_MAP_URL,
                    details={"field": source_field},
                )
            try:
                numeric = float(term)
            except ValueError as exc:
                raise WashingtonSelectionError(
                    "invalid_numeric_query",
                    "numeric ArcGIS field requires a numeric query",
                    url=SURVEY_MAP_URL,
                    details={"field": source_field, "query": term},
                ) from exc
            literal = str(int(numeric)) if numeric.is_integer() else str(numeric)
            expression = f"{source_field} = {literal}"
        pieces.append(f"({expression})")
    return " AND ".join(pieces) if pieces else "1=1"


def _sql_literal(value: Any, field_type: str) -> str:
    if value is None:
        raise ValueError("cursor sort values cannot be null")
    if "String" in field_type or "Date" in field_type or "GUID" in field_type:
        return _sql_string(str(value))
    if isinstance(value, bool):
        raise ValueError("boolean cursor values are not supported")
    if isinstance(value, (int, float)):
        return str(value)
    return _sql_string(str(value))


def _anchor_where(
    sort_fields: Sequence[str],
    last_sort: Sequence[Any],
    field_types: Mapping[str, str],
) -> str:
    if len(sort_fields) != len(last_sort):
        raise ValueError("cursor sort tuple length does not match layer order")
    alternatives: list[str] = []
    for index, field in enumerate(sort_fields):
        prefix = [
            f"{earlier} = {_sql_literal(last_sort[pos], field_types[earlier])}"
            for pos, earlier in enumerate(sort_fields[:index])
        ]
        comparison = (
            f"{field} > {_sql_literal(last_sort[index], field_types[field])}"
        )
        alternatives.append(
            "(" + " AND ".join([*prefix, comparison]) + ")"
        )
    return "(" + " OR ".join(alternatives) + ")"


def _arcgis_cursor_state(
    cursor: str | None,
    *,
    layer: ArcGISLayer,
    criteria: str,
    schema: str,
    total: int,
) -> Mapping[str, Any] | None:
    state = _cursor_decode(cursor)
    if state is None:
        return None
    if (
        state.get("source_key") != f"arcgis:{layer.key}"
        or state.get("criteria") != criteria
    ):
        raise WashingtonSelectionError(
            "cursor_query_mismatch",
            "ArcGIS cursor belongs to different query criteria",
            url=layer.layer_url,
        )
    if state.get("schema") != schema:
        raise WashingtonSelectionError(
            "cursor_schema_changed",
            "ArcGIS schema changed after the cursor was issued",
            url=layer.layer_url,
        )
    if state.get("total") != total:
        raise WashingtonSelectionError(
            "cursor_snapshot_changed",
            "ArcGIS matching count changed after the cursor was issued",
            url=layer.layer_url,
            details={"cursor_total": state.get("total"), "current_total": total},
        )
    return state


def _derived_account(serial: Any) -> str | None:
    if serial is None or isinstance(serial, bool):
        return None
    try:
        return f"R{int(float(serial))}"
    except (TypeError, ValueError, OverflowError):
        return None


def _arcgis_record(
    feature: Mapping[str, Any],
    *,
    layer: ArcGISLayer,
    source_url: str,
    returned_crs: Mapping[str, Any] | None,
    include_geometry: bool,
) -> dict[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "ArcGIS feature has no attributes object",
            url=source_url,
        )
    native_ids = _native_subset(attributes, layer.native_id_fields)
    joins = _native_subset(attributes, layer.join_fields)
    if layer.key == "situs":
        joins["derived_property_quick_ref_candidate"] = _derived_account(
            attributes.get("SERIAL")
        )
    record: dict[str, Any] = {
        "record_type": f"washington_county_arcgis_{layer.key}",
        "source_id": layer.source_id,
        "layer_key": layer.key,
        "native_ids": native_ids,
        "join_candidates": {
            SURVEY_API_SOURCE_ID: joins,
            TAXLOT_SOURCE_ID: joins,
            SITUS_SOURCE_ID: joins,
            INTERMAP_SOURCE_ID: joins,
            TAX_SOURCE_ID: joins,
            PORTLAND_REGIONAL_SOURCE_ID: joins,
        },
        "native_fields": dict(attributes),
        "source_url": source_url,
        "geometry_representation": {
            "included": include_geometry,
            "source_crs": f"EPSG:{layer.source_wkid}",
            "returned_crs": dict(returned_crs or {}),
        },
        "lineage": {
            "component_source_id": layer.source_id,
            "overlapping_rows_are_linked_representations": True,
        },
    }
    if include_geometry and "geometry" in feature:
        record["geometry"] = feature["geometry"]
    return record


def query_arcgis(
    args: argparse.Namespace,
    client: WashingtonClient,
    *,
    forced_layer: str | None = None,
) -> PublicRecordsResult:
    layer_key = forced_layer or args.layer
    layer = ARCGIS_LAYERS[layer_key]
    metadata = client.layer_metadata(layer)
    fields = _arcgis_field_map(metadata, layer.layer_url)
    sort_fields = tuple(_field_lookup(fields, field) for field in layer.sort_fields)
    missing_ids = [
        field
        for field in layer.native_id_fields
        if field.casefold() not in {name.casefold() for name in fields}
    ]
    if missing_ids:
        raise SourceSchemaError(
            "ArcGIS layer no longer publishes expected native identifiers",
            url=layer.layer_url,
            details={"missing_fields": missing_ids},
        )
    source_wkid = int(
        (
            metadata.get("spatialReference")
            or metadata.get("sourceSpatialReference")
            or {}
        ).get("latestWkid")
        or (
            metadata.get("spatialReference")
            or metadata.get("sourceSpatialReference")
            or {}
        ).get("wkid")
        or 0
    )
    if source_wkid != layer.source_wkid:
        raise SourceSchemaError(
            "ArcGIS layer coordinate reference system changed",
            url=layer.layer_url,
            details={"expected_wkid": layer.source_wkid, "observed_wkid": source_wkid},
        )
    declared_schema = schema_fingerprint(
        arcgis_declared_schema(metadata.get("fields", []))
    )
    base_where = _where_for_search(
        base_where=getattr(args, "where", None),
        field=getattr(args, "field", None),
        term=getattr(args, "query", None),
        match=getattr(args, "match", "exact"),
        fields=fields,
    )
    if len(sort_fields) > 1:
        base_where = f"({base_where}) AND {sort_fields[0]} IS NOT NULL"
    criteria_payload = {
        "layer": layer.key,
        "where": base_where,
        "sort_fields": list(sort_fields),
        "geometry": args.geometry,
        "out_sr": args.out_sr,
    }
    criteria = sha256_fingerprint(criteria_payload)
    query = _public_query(
        layer.source_id,
        "arcgis_query",
        criteria_payload,
        limit=args.limit,
        cursor=args.cursor,
        metadata={
            "layer_url": layer.layer_url,
            "source_crs": f"EPSG:{layer.source_wkid}",
            "sort_tuple": list(sort_fields),
        },
    )
    count_payload, count_artifact = client.arcgis_query(
        layer,
        {"where": base_where, "returnCountOnly": "true"},
    )
    total = count_payload.get("count")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise SourceSchemaError(
            "ArcGIS count response is invalid",
            url=count_artifact.source_url,
            details={"count": total},
        )
    state = _arcgis_cursor_state(
        args.cursor,
        layer=layer,
        criteria=criteria,
        schema=declared_schema,
        total=total,
    )
    page_where = base_where
    if state is not None:
        anchor = _anchor_where(sort_fields, state["last_sort"], fields)
        page_where = f"({base_where}) AND {anchor}"
    target_count = None if args.limit is None else args.limit + 1
    features: list[Mapping[str, Any]] = []
    tuples: list[list[Any]] = []
    returned_crs: Mapping[str, Any] | None = None
    artifact = count_artifact
    while (
        (target_count is None or len(features) < target_count)
        and (state is not None or len(features) < total)
    ):
        request_count = DEFAULT_PAGE_SIZE
        if target_count is not None:
            request_count = min(request_count, target_count - len(features))
        page_payload, artifact = client.arcgis_query(
            layer,
            {
                "where": page_where,
                "outFields": "*",
                "returnGeometry": str(bool(args.geometry)).lower(),
                "outSR": args.out_sr,
                "orderByFields": ",".join(
                    f"{field} ASC" for field in sort_fields
                ),
                "resultRecordCount": request_count,
            },
        )
        page_features = page_payload.get("features")
        if not isinstance(page_features, list) or not all(
            isinstance(item, Mapping) for item in page_features
        ):
            raise SourceSchemaError(
                "ArcGIS query response has no feature list",
                url=artifact.source_url,
            )
        if not page_features:
            break
        page_tuples: list[list[Any]] = []
        for feature in page_features:
            attributes = feature.get("attributes")
            if not isinstance(attributes, Mapping):
                raise SourceSchemaError(
                    "ArcGIS feature is missing attributes",
                    url=artifact.source_url,
                )
            sort_tuple = [attributes.get(field) for field in sort_fields]
            if any(value is None for value in sort_tuple):
                raise SourceSchemaError(
                    "ArcGIS feature has a null cursor sort value",
                    url=artifact.source_url,
                    details={"sort_fields": list(sort_fields)},
                )
            page_tuples.append(sort_tuple)
        combined_tuples = [*tuples[-1:], *page_tuples]
        if any(
            _sort_key(current) <= _sort_key(previous)
            for previous, current in zip(
                combined_tuples,
                combined_tuples[1:],
            )
        ):
            raise SourceSchemaError(
                "ArcGIS traversal is not strictly ordered by its cursor tuple",
                url=artifact.source_url,
                details={"sort_fields": list(sort_fields)},
            )
        features.extend(page_features)
        tuples.extend(page_tuples)
        page_crs = page_payload.get("spatialReference")
        if isinstance(page_crs, Mapping):
            returned_crs = page_crs
        if state is None and len(features) > total:
            raise SourceSchemaError(
                "ArcGIS traversal returned more records than its count response",
                url=artifact.source_url,
                details={"count": total, "records": len(features)},
            )
        anchor = _anchor_where(sort_fields, page_tuples[-1], fields)
        page_where = f"({base_where}) AND {anchor}"
        if (
            len(page_features) < request_count
            and page_payload.get("exceededTransferLimit") is not True
            and not (state is None and len(features) < total)
        ):
            break
    if args.limit is None and state is None and len(features) != total:
        raise SourceSchemaError(
            "ArcGIS traversal ended before its count response was exhausted",
            url=artifact.source_url,
            details={"count": total, "records": len(features)},
        )
    selected_features = (
        features if args.limit is None else features[: args.limit]
    )
    selected_tuples = tuples if args.limit is None else tuples[: args.limit]
    next_cursor = None
    if (
        args.limit is not None
        and len(features) > args.limit
        and selected_features
    ):
        next_cursor = _cursor_encode(
            {
                "version": CURSOR_VERSION,
                "source_key": f"arcgis:{layer.key}",
                "criteria": criteria,
                "snapshot": declared_schema,
                "schema": declared_schema,
                "total": total,
                "last_sort": selected_tuples[-1],
            }
        )
    records = [
        _arcgis_record(
            feature,
            layer=layer,
            source_url=artifact.source_url,
            returned_crs=returned_crs,
            include_geometry=args.geometry,
        )
        for feature in selected_features
    ]
    return PublicRecordsResult.success(query, records, next_cursor=next_cursor)


INTERMAP_REPORT_IDS = {"parcel": 20, "assessment": 30, "tax-map": 15}


def intermap_url(tlno: str, report: str) -> str:
    return (
        f"{INTERMAP_BASE_URL}?"
        f"{urlencode({'id': INTERMAP_REPORT_IDS[report], 'sid': 3, 'IDValue': tlno})}"
    )


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def parse_html_representation(
    html: str,
    *,
    source_url: str,
    include_raw_html: bool = False,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else None
    headings = [
        _clean_text(node.get_text(" ", strip=True))
        for node in soup.select("h1,h2,h3,h4,h5,h6")
        if _clean_text(node.get_text(" ", strip=True))
    ]
    tables: list[dict[str, Any]] = []
    field_pairs: list[dict[str, str]] = []
    for table_index, table in enumerate(soup.select("table")):
        rows: list[list[str]] = []
        for row in table.select("tr"):
            cells = [
                _clean_text(cell.get_text(" ", strip=True))
                for cell in row.find_all(["th", "td"], recursive=False)
            ]
            if cells and any(cells):
                rows.append(cells)
                if 2 <= len(cells) <= 4:
                    label = cells[0].rstrip(":").strip()
                    value = " | ".join(cell for cell in cells[1:] if cell)
                    if label and value and len(label) <= 100:
                        field_pairs.append({"label": label, "value": value})
        if rows:
            tables.append({"table_index": table_index, "rows": rows})
    links = []
    for anchor in soup.select("a[href]"):
        raw_href = str(anchor.get("href") or "").strip()
        if not raw_href:
            continue
        resolved = urljoin(source_url, raw_href)
        parsed = urlparse(resolved)
        if parsed.scheme == "http" and parsed.hostname in {
            "mtbachelor.co.washington.or.us",
            "gisims.co.washington.or.us",
        }:
            resolved = parsed._replace(scheme="https").geturl()
        links.append(
            {
                "text": _clean_text(anchor.get_text(" ", strip=True)),
                "native_href": raw_href,
                "resolved_url": resolved,
            }
        )
    representation: dict[str, Any] = {
        "media_type": "text/html",
        "source_url": source_url,
        "title": title,
        "headings": headings,
        "field_pairs": field_pairs,
        "tables": tables,
        "links": links,
        "html_byte_length": len(html.encode("utf-8")),
        "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }
    if include_raw_html:
        representation["raw_html"] = html
    return representation


def _pairs_dict(field_pairs: Sequence[Mapping[str, str]]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for pair in field_pairs:
        label = str(pair.get("label") or "").strip()
        value = str(pair.get("value") or "").strip()
        if label and value:
            output.setdefault(label, []).append(value)
    return output


def _first_pair(
    fields: Mapping[str, Sequence[str]],
    label: str,
) -> str | None:
    values = fields.get(label)
    if not values:
        return None
    value = str(values[0]).strip().rstrip(",")
    return value or None


def intermap_reports(
    args: argparse.Namespace,
    client: WashingtonClient,
) -> PublicRecordsResult:
    tlno = args.tlno.strip().upper()
    requested = (
        tuple(INTERMAP_REPORT_IDS)
        if args.report == "all"
        else (args.report,)
    )
    query = _public_query(
        INTERMAP_SOURCE_ID,
        "reports",
        {
            "TLNO": tlno,
            "reports": list(requested),
            "include_raw_html": args.include_raw_html,
        },
    )
    records: list[dict[str, Any]] = []
    for report in requested:
        url = intermap_url(tlno, report)
        html, artifact = client.text(url, maximum_bytes=args.max_html_bytes)
        representation = parse_html_representation(
            html,
            source_url=artifact.source_url,
            include_raw_html=args.include_raw_html,
        )
        fields = _pairs_dict(representation["field_pairs"])
        records.append(
            {
                "record_type": f"intermap_{report}_report",
                "report": report,
                "native_ids": {
                    "IDValue": tlno,
                    "TLNO": (
                        _first_pair(fields, "Tax Lot ID") or tlno
                        if report == "assessment"
                        else tlno
                    ),
                    "account": (
                        _first_pair(fields, "Property Account ID")
                        if report == "assessment"
                        else _first_pair(fields, "Real Property Account #")
                    ),
                },
                "join_candidates": {
                    SURVEY_API_SOURCE_ID: {"TLID": tlno},
                    SURVEY_MAP_SOURCE_ID: {"TLID": tlno, "TLNO": tlno},
                    TAXLOT_SOURCE_ID: {"TLNO": tlno},
                    SITUS_SOURCE_ID: {"TAXLOT": tlno},
                    TAX_SOURCE_ID: {
                        "PropertyQuickRefID": (
                            _first_pair(fields, "Property Account ID")
                            if report == "assessment"
                            else _first_pair(fields, "Real Property Account #")
                        )
                    },
                },
                "native_representation": representation,
                "source_id": INTERMAP_SOURCE_ID,
                "source_url": artifact.source_url,
            }
        )
    return PublicRecordsResult.success(query, records)


TAX_STATEMENT_ONCLICK = re.compile(
    r"OpenTaxStatementPDF\(\s*['\"]([^'\"]+)['\"]\s*,\s*"
    r"['\"]([^'\"]+)['\"]\s*,\s*['\"]?(\d{4})['\"]?\s*\)",
    re.IGNORECASE,
)
PROPERTY_QUICK_REF_PATTERN = re.compile(
    r"/Property-Detail/PropertyQuickRefID/([^/?#]+)",
    re.IGNORECASE,
)


def parse_tax_account(
    html: str,
    *,
    source_url: str,
    requested_account: str,
    include_raw_html: bool = False,
) -> dict[str, Any]:
    representation = parse_html_representation(
        html,
        source_url=source_url,
        include_raw_html=include_raw_html,
    )
    soup = BeautifulSoup(html, "html.parser")
    route_match = PROPERTY_QUICK_REF_PATTERN.search(source_url)
    property_quick_ref = (
        route_match.group(1)
        if route_match
        else requested_account
    )
    property_id_node = soup.select_one('[id$="_tdPropertyID"]')
    if property_id_node is not None:
        displayed = _clean_text(property_id_node.get_text(" ", strip=True))
        if displayed:
            property_quick_ref = displayed
    owner_node = soup.select_one('[id$="_tdOIOwnerName"], [id$="_divOwnersLabel"]')
    value_node = soup.select_one('[id$="_tdTotalAssessedValue"]')
    legal_node = soup.select_one('[id$="_tdGILegalDescription"]')
    alt_account_node = soup.select_one('[id$="_tdGIAlternateAccountNo"]')
    generated_statements: list[dict[str, Any]] = []
    direct_statements: list[dict[str, Any]] = []
    for anchor in soup.select("a"):
        onclick = str(anchor.get("onclick") or "")
        match = TAX_STATEMENT_ONCLICK.search(onclick)
        if match:
            property_id, party_id, year = match.groups()
            generated_statements.append(
                {
                    "tax_year": int(year),
                    "PropertyID": property_id,
                    "PartyID": party_id,
                    "PropertyQuickRefID": property_quick_ref,
                    "retrieval_mode": "same_session_post_filename_then_pdf",
                }
            )
            continue
        href = str(anchor.get("href") or "")
        direct_match = re.search(
            r"/TaxStatements/(\d{4})/([^/?#]+)\.pdf",
            href,
            re.IGNORECASE,
        )
        if direct_match:
            year, account = direct_match.groups()
            direct_statements.append(
                {
                    "tax_year": int(year),
                    "PropertyQuickRefID": account,
                    "resolved_url": urljoin(source_url, href),
                    "retrieval_mode": "direct_historical_pdf",
                }
            )
    statement_entries = sorted(
        [*generated_statements, *direct_statements],
        key=lambda item: int(item["tax_year"]),
        reverse=True,
    )
    receipts = []
    receipt_pattern = re.compile(
        r"OpenReceiptPDF\(\s*['\"]([^'\"]+)['\"]\s*,\s*"
        r"['\"]([^'\"]+)['\"]\s*\)",
        re.IGNORECASE,
    )
    for anchor in soup.select("a[onclick]"):
        match = receipt_pattern.search(str(anchor.get("onclick") or ""))
        if match:
            quick_ref, transaction_id = match.groups()
            receipts.append(
                {
                    "PropertyQuickRefID": quick_ref,
                    "transactionID": transaction_id,
                    "receipt_number": _clean_text(anchor.get_text(" ", strip=True)),
                }
            )
    return {
        "record_type": "washington_county_tax_account",
        "native_ids": {
            "PropertyQuickRefID": property_quick_ref,
            "alternate_account": (
                _clean_text(alt_account_node.get_text(" ", strip=True))
                if alt_account_node
                else None
            ),
        },
        "owner_name": (
            _clean_text(owner_node.get_text(" ", strip=True))
            if owner_node
            else None
        ),
        "displayed_real_market_value": (
            _clean_text(value_node.get_text(" ", strip=True))
            if value_node
            else None
        ),
        "legal_description": (
            _clean_text(legal_node.get_text(" ", strip=True))
            if legal_node
            else None
        ),
        "tax_statements": statement_entries,
        "payment_receipts": receipts,
        "native_representation": representation,
        "source_id": TAX_SOURCE_ID,
        "source_url": source_url,
    }


def tax_account(
    args: argparse.Namespace,
    client: WashingtonClient,
) -> PublicRecordsResult:
    account = args.account.strip().upper()
    query = _public_query(
        TAX_SOURCE_ID,
        "account",
        {
            "PropertyQuickRefID": account,
            "include_raw_html": args.include_raw_html,
        },
    )
    url = urljoin(TAX_BASE_URL, TAX_DETAIL_ROUTE.format(account=quote(account)))
    html, artifact = client.text(url, maximum_bytes=args.max_html_bytes)
    record = parse_tax_account(
        html,
        source_url=artifact.source_url,
        requested_account=account,
        include_raw_html=args.include_raw_html,
    )
    return PublicRecordsResult.success(query, [record])


def _tax_statement_entry(
    account_record: Mapping[str, Any],
    tax_year: int,
) -> Mapping[str, Any] | None:
    statements = account_record.get("tax_statements")
    if not isinstance(statements, list):
        return None
    for statement in statements:
        if (
            isinstance(statement, Mapping)
            and statement.get("tax_year") == tax_year
        ):
            return statement
    return None


def _parse_generated_filename(payload: Any, source_url: str) -> str:
    if isinstance(payload, str):
        filename = payload.strip()
    elif isinstance(payload, Mapping):
        filename = str(
            payload.get("filename")
            or payload.get("FileName")
            or payload.get("data")
            or ""
        ).strip()
    else:
        filename = ""
    if not filename or "/" in filename or "\\" in filename:
        raise SourceSchemaError(
            "tax-statement generator returned an invalid filename",
            url=source_url,
            details={"payload_type": type(payload).__name__},
        )
    return filename


def tax_statement(
    args: argparse.Namespace,
    client: WashingtonClient,
) -> PublicRecordsResult:
    account = args.account.strip().upper()
    tax_year = int(args.tax_year)
    query = _public_query(
        TAX_SOURCE_ID,
        "tax_statement",
        {
            "PropertyQuickRefID": account,
            "tax_year": tax_year,
            "maximum_bytes": args.max_document_bytes,
        },
    )
    detail_url = urljoin(
        TAX_BASE_URL,
        TAX_DETAIL_ROUTE.format(account=quote(account)),
    )
    html, detail_artifact = client.text(
        detail_url,
        maximum_bytes=args.max_html_bytes,
    )
    account_record = parse_tax_account(
        html,
        source_url=detail_artifact.source_url,
        requested_account=account,
    )
    statement = _tax_statement_entry(account_record, tax_year)
    if statement is None and not (args.property_id and args.party_id):
        return PublicRecordsResult.success(query, [])
    if statement and statement.get("resolved_url"):
        document_url = str(statement["resolved_url"])
        retrieval_mode = "direct_historical_pdf"
        generator_parameters = None
        generated_filename = Path(urlparse(document_url).path).name
    else:
        property_id = (
            args.property_id
            or (str(statement.get("PropertyID")) if statement else None)
        )
        party_id = (
            args.party_id
            or (str(statement.get("PartyID")) if statement else None)
        )
        if not property_id or not party_id:
            raise WashingtonSelectionError(
                "missing_tax_statement_ids",
                "generated tax statement requires PropertyID and PartyID",
                url=detail_artifact.source_url,
            )
        generator_parameters = {
            "PropertyID": property_id,
            "PartyID": party_id,
            "TaxYear": str(tax_year),
            "EffectiveDate": f"11-15-{tax_year}",
        }
        filename_payload, generator_artifact = client.json(
            TAX_STATEMENT_GENERATOR_URL,
            method="POST",
            data=generator_parameters,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": detail_artifact.source_url,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        generated_filename = _parse_generated_filename(
            filename_payload,
            generator_artifact.source_url,
        )
        document_url = (
            f"{TAX_GENERATED_DOCUMENT_BASE}/{quote(generated_filename)}/"
        )
        retrieval_mode = "same_session_post_filename_then_pdf"
    artifact = client.request(
        "GET",
        document_url,
        headers={"Referer": detail_artifact.source_url},
        maximum_bytes=args.max_document_bytes,
    )
    if not artifact.content.startswith(b"%PDF"):
        raise SourceResponseError(
            "Washington County tax statement is not a PDF",
            url=artifact.source_url,
            details={"content_type": artifact.media_type},
        )
    destination = _write_document(args.destination, artifact.content)
    record = {
        "record_type": "washington_county_tax_statement",
        "native_ids": {
            "PropertyQuickRefID": account,
            "PropertyID": (
                generator_parameters.get("PropertyID")
                if generator_parameters
                else None
            ),
            "PartyID": (
                generator_parameters.get("PartyID")
                if generator_parameters
                else None
            ),
            "tax_year": tax_year,
            "generated_filename": generated_filename,
        },
        "retrieval_mode": retrieval_mode,
        "generation_parameters": generator_parameters,
        "source_url": artifact.source_url,
        "detail_source_url": detail_artifact.source_url,
        "media_type": artifact.media_type or "application/pdf",
        "byte_length": len(artifact.content),
        "sha256": hashlib.sha256(artifact.content).hexdigest(),
        "destination": destination,
        "source_id": TAX_SOURCE_ID,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[artifact.source_url],
    )


def source_manifest() -> dict[str, Any]:
    return {
        "schema_version": "oregon-washington-property-sources/1.0",
        "jurisdiction": JURISDICTION.to_dict(),
        "sources": [
            {
                **source.to_dict(),
                "capabilities": _capabilities(source_id),
                "joins": _joins(source_id),
            }
            for source_id, source in SOURCES.items()
        ],
        "survey_api_kinds": {
            key: {
                "searchby": kind.searchby,
                "search_fields": list(kind.allowed_fields),
                "sort_tuple": [*kind.sort_fields, "record_fingerprint"],
                "native_id_fields": list(kind.native_id_fields),
            }
            for key, kind in SURVEY_KINDS.items()
        },
        "arcgis_components": {
            key: {
                "source_id": layer.source_id,
                "layer_url": layer.layer_url,
                "sort_tuple": list(layer.sort_fields),
                "native_id_fields": list(layer.native_id_fields),
                "join_fields": list(layer.join_fields),
                "source_crs": f"EPSG:{layer.source_wkid}",
                "live_count_observation": layer.expected_count,
                "count_observed_at": "2026-07-29",
            }
            for key, layer in ARCGIS_LAYERS.items()
        },
        "complementary_sources": [dict(item) for item in COMPLEMENTS],
        "process_observations": [
            (
                "The family is modeled as component representations so exact "
                "joins do not convert shared lineage into corroboration."
            ),
            (
                "Survey Explorer API request headers reproduce the public web "
                "application's working transport profile."
            ),
            (
                "ArcGIS continuations use the full declared sort tuple plus "
                "schema and matching-count guards."
            ),
        ],
    }


def _capabilities(source_id: str) -> list[str]:
    return {
        SURVEY_API_SOURCE_ID: [
            "survey_search",
            "survey_detail",
            "plat_search",
            "plat_detail",
            "taxlot_account_search",
            "survey_and_plat_pdf_resolution",
        ],
        SURVEY_MAP_SOURCE_ID: [
            "survey_geometry",
            "plat_geometry",
            "taxlot_geometry_and_account_join",
            "corner_control_road_and_section_geometry",
        ],
        TAXLOT_SOURCE_ID: ["current_taxlot_geometry", "map_and_taxlot_identifiers"],
        SITUS_SOURCE_ID: ["situs_address_points", "taxlot_and_account_join"],
        INTERMAP_SOURCE_ID: [
            "parcel_report",
            "assessment_and_taxation_report",
            "tax_map_links",
        ],
        TAX_SOURCE_ID: [
            "owner_and_property_detail",
            "value_and_improvement_history",
            "tax_and_payment_history",
            "current_and_historical_tax_statements",
        ],
    }[source_id]


def _joins(source_id: str) -> Mapping[str, Sequence[str]]:
    return {
        SURVEY_API_SOURCE_ID: {
            SURVEY_MAP_SOURCE_ID: [
                "Surveynumber/SurvNum",
                "Platname",
                "DocNumber",
                "TLID",
            ],
            TAXLOT_SOURCE_ID: ["TLID/TLNO"],
            TAX_SOURCE_ID: ["ACCOUNT/PropertyQuickRefID"],
        },
        SURVEY_MAP_SOURCE_ID: {
            SURVEY_API_SOURCE_ID: ["SurvNum", "Platname", "DocNumber", "TLID"],
            TAXLOT_SOURCE_ID: ["TLID/TLNO"],
        },
        TAXLOT_SOURCE_ID: {
            SURVEY_MAP_SOURCE_ID: ["TLNO/TLID"],
            SITUS_SOURCE_ID: ["TLNO/TAXLOT"],
            INTERMAP_SOURCE_ID: ["TLNO/IDValue"],
            PORTLAND_REGIONAL_SOURCE_ID: ["TLNO/TLID"],
        },
        SITUS_SOURCE_ID: {
            TAXLOT_SOURCE_ID: ["TAXLOT/TLNO"],
            TAX_SOURCE_ID: ["derived R + SERIAL/PropertyQuickRefID"],
        },
        INTERMAP_SOURCE_ID: {
            TAXLOT_SOURCE_ID: ["IDValue/TLNO"],
            TAX_SOURCE_ID: ["Property Account ID/PropertyQuickRefID"],
        },
        TAX_SOURCE_ID: {
            SURVEY_API_SOURCE_ID: ["PropertyQuickRefID/ACCOUNT"],
            INTERMAP_SOURCE_ID: ["PropertyQuickRefID/Property Account ID"],
        },
    }[source_id]


def probe_sources(
    args: argparse.Namespace,
    client: WashingtonClient,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    def record_probe(source_id: str, component: str, callback: Callable[[], Any]) -> None:
        try:
            value = callback()
            results.append(
                {
                    "source_id": source_id,
                    "component": component,
                    "status": "ok",
                    "observation": value,
                }
            )
        except PublicRecordsHTTPError as exc:
            results.append(
                {
                    "source_id": source_id,
                    "component": component,
                    "status": exc.result_status.value,
                    "error": exc.to_contract_error().to_dict(),
                }
            )

    def survey_probe() -> Mapping[str, Any]:
        envelope, artifact = client.survey_search(
            SURVEY_KINDS["survey"],
            {"surveynumber": PROBE_SURVEY},
        )
        return {
            "source_url": artifact.source_url,
            "total": envelope["total"],
            "sentinel": PROBE_SURVEY,
        }

    def layer_probe(layer_key: str, field: str, value: str) -> Mapping[str, Any]:
        layer = ARCGIS_LAYERS[layer_key]
        metadata = client.layer_metadata(layer)
        payload, artifact = client.arcgis_query(
            layer,
            {
                "where": f"{field} = {_sql_string(value)}",
                "outFields": "*",
                "returnGeometry": "false",
                "resultRecordCount": 2,
            },
        )
        return {
            "source_url": artifact.source_url,
            "matches": len(payload.get("features", [])),
            "service_item_id": metadata.get("serviceItemId"),
            "sentinel": value,
        }

    def intermap_probe() -> Mapping[str, Any]:
        url = intermap_url(PROBE_TAXLOT, "assessment")
        html, artifact = client.text(url, maximum_bytes=args.max_html_bytes)
        return {
            "source_url": artifact.source_url,
            "contains_account": PROBE_ACCOUNT in html,
            "sentinel": PROBE_TAXLOT,
        }

    def tax_probe() -> Mapping[str, Any]:
        url = urljoin(
            TAX_BASE_URL,
            TAX_DETAIL_ROUTE.format(account=PROBE_ACCOUNT),
        )
        html, artifact = client.text(url, maximum_bytes=args.max_html_bytes)
        parsed = parse_tax_account(
            html,
            source_url=artifact.source_url,
            requested_account=PROBE_ACCOUNT,
        )
        return {
            "source_url": artifact.source_url,
            "account": parsed["native_ids"]["PropertyQuickRefID"],
            "statement_years": [
                item["tax_year"] for item in parsed["tax_statements"][:5]
            ],
        }

    record_probe(SURVEY_API_SOURCE_ID, "survey_api", survey_probe)
    record_probe(
        SURVEY_MAP_SOURCE_ID,
        "survey_taxlots",
        lambda: layer_probe("survey-taxlots", "TLID", PROBE_TAXLOT),
    )
    record_probe(
        TAXLOT_SOURCE_ID,
        "current_taxlots",
        lambda: layer_probe("taxlots", "TLNO", PROBE_TAXLOT),
    )
    record_probe(
        SITUS_SOURCE_ID,
        "situs",
        lambda: layer_probe("situs", "TAXLOT", PROBE_TAXLOT),
    )
    record_probe(INTERMAP_SOURCE_ID, "assessment_report", intermap_probe)
    record_probe(TAX_SOURCE_ID, "tax_account", tax_probe)
    return {
        "schema_version": "oregon-washington-property-probe/1.0",
        "jurisdiction": JURISDICTION.to_dict(),
        "results": results,
    }


def _result_count(payload: PublicRecordsResult | Mapping[str, Any]) -> int:
    if isinstance(payload, PublicRecordsResult):
        return len(payload.records)
    records = payload.get("results")
    return len(records) if isinstance(records, list) else 0


def _log_result(
    result: PublicRecordsResult,
    *,
    log_results: bool,
) -> None:
    if log_results:
        log_search(
            canonical_json(result.query.to_dict()),
            result.query.source.source_id,
            len(result.records),
        )


def execute(
    args: argparse.Namespace,
    *,
    client: WashingtonClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    if args.command == "sources":
        return source_manifest()
    owns_client = client is None
    active_client = client or WashingtonClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )
    try:
        if args.command == "survey-search":
            result = search_survey_api(args, active_client)
        elif args.command == "survey-detail":
            result = survey_detail(args, active_client)
        elif args.command == "survey-document":
            result = survey_document(args, active_client)
        elif args.command == "arcgis":
            result = query_arcgis(args, active_client)
        elif args.command == "taxlots":
            result = query_arcgis(args, active_client, forced_layer="taxlots")
        elif args.command == "situs":
            result = query_arcgis(args, active_client, forced_layer="situs")
        elif args.command == "intermap":
            result = intermap_reports(args, active_client)
        elif args.command == "tax-account":
            result = tax_account(args, active_client)
        elif args.command == "tax-statement":
            result = tax_statement(args, active_client)
        elif args.command == "probe":
            return probe_sources(args, active_client)
        else:
            raise ValueError(f"unknown command {args.command!r}")
        _log_result(result, log_results=log_results)
        return result
    except PublicRecordsHTTPError as exc:
        source_id = _source_for_command(args)
        query = _public_query(
            source_id,
            args.command,
            _failure_parameters(args),
            limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        )
        result = failure_result(query, exc)
        _log_result(result, log_results=log_results)
        return result
    finally:
        if owns_client:
            active_client.close()


def _source_for_command(args: argparse.Namespace) -> str:
    if args.command.startswith("survey-"):
        return SURVEY_API_SOURCE_ID
    if args.command == "arcgis":
        return ARCGIS_LAYERS[args.layer].source_id
    if args.command == "taxlots":
        return TAXLOT_SOURCE_ID
    if args.command == "situs":
        return SITUS_SOURCE_ID
    if args.command == "intermap":
        return INTERMAP_SOURCE_ID
    return TAX_SOURCE_ID


def _failure_parameters(args: argparse.Namespace) -> dict[str, Any]:
    excluded = {
        "output",
        "json_out",
        "timeout",
        "minimum_interval",
        "retry_attempts",
        "destination",
    }
    return {
        key: value
        for key, value in vars(args).items()
        if key not in excluded and value is not None
    }


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )


def _add_output(parser: argparse.ArgumentParser) -> None:
    _add_transport_args(parser)
    add_output_args(parser)


def _add_arcgis_args(
    parser: argparse.ArgumentParser,
    *,
    positional_query: bool = False,
) -> None:
    if positional_query:
        parser.add_argument("query", nargs="?")
    else:
        parser.add_argument("--query")
    parser.add_argument("--field")
    parser.add_argument("--where")
    parser.add_argument("--match", choices=("exact", "contains"), default="exact")
    parser.add_argument(
        "--limit",
        type=int,
        help="Return at most this many records; omitted traverses all matches",
    )
    parser.add_argument("--cursor")
    parser.add_argument("--geometry", action="store_true")
    parser.add_argument(
        "--out-sr",
        default="4326",
        help="ArcGIS output spatial reference (default: EPSG:4326)",
    )
    _add_output(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Washington County Oregon Survey Explorer, property, taxlot, "
            "situs, Intermap, and guest tax records"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Describe attributable components, joins, and alternatives",
    )
    add_output_args(sources)

    search = sub.add_parser(
        "survey-search",
        help="Search a Survey Explorer API record type",
    )
    search.add_argument("kind", choices=sorted(SURVEY_KINDS))
    search.add_argument("query", nargs="?")
    search.add_argument("--field")
    search.add_argument(
        "--filter",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Add a source-native Survey Explorer search field",
    )
    search.add_argument(
        "--limit",
        type=int,
        help="Return at most this many records; omitted returns the complete response",
    )
    search.add_argument("--cursor")
    _add_output(search)

    detail = sub.add_parser(
        "survey-detail",
        help="Fetch exact Survey Explorer detail by native ID",
    )
    detail.add_argument("kind", choices=sorted(SURVEY_KINDS))
    detail.add_argument("uid")
    _add_output(detail)

    document = sub.add_parser(
        "survey-document",
        help="Resolve and download a Survey Explorer source PDF",
    )
    document.add_argument(
        "kind",
        choices=("survey", "plat", "taxlot", "corner", "geocontrol", "county-road"),
    )
    document.add_argument("uid")
    document.add_argument("--file-index", type=int, default=0)
    document.add_argument("--destination")
    document.add_argument(
        "--max-document-bytes",
        type=int,
        default=DEFAULT_MAX_DOCUMENT_BYTES,
    )
    _add_output(document)

    arcgis = sub.add_parser(
        "arcgis",
        help="Query a Survey Explorer or county ArcGIS component",
    )
    arcgis.add_argument("layer", choices=sorted(ARCGIS_LAYERS))
    _add_arcgis_args(arcgis)

    taxlots = sub.add_parser(
        "taxlots",
        help="Query the current county taxlot FeatureServer",
    )
    _add_arcgis_args(taxlots, positional_query=True)
    taxlots.set_defaults(field="TLNO")

    situs = sub.add_parser(
        "situs",
        help="Query the county situs-address service",
    )
    _add_arcgis_args(situs, positional_query=True)
    situs.set_defaults(field="TAXLOT")

    intermap = sub.add_parser(
        "intermap",
        help="Fetch legacy parcel, assessment, and tax-map reports",
    )
    intermap.add_argument("tlno")
    intermap.add_argument(
        "--report",
        choices=(*INTERMAP_REPORT_IDS, "all"),
        default="all",
    )
    intermap.add_argument("--include-raw-html", action="store_true")
    intermap.add_argument(
        "--max-html-bytes",
        type=int,
        default=DEFAULT_MAX_HTML_BYTES,
    )
    _add_output(intermap)

    account = sub.add_parser(
        "tax-account",
        help="Fetch a Washington County guest property-tax account",
    )
    account.add_argument("account")
    account.add_argument("--include-raw-html", action="store_true")
    account.add_argument(
        "--max-html-bytes",
        type=int,
        default=DEFAULT_MAX_HTML_BYTES,
    )
    _add_output(account)

    statement = sub.add_parser(
        "tax-statement",
        help="Download a current/generated or historical tax statement",
    )
    statement.add_argument("account")
    statement.add_argument("tax_year", type=int)
    statement.add_argument("--property-id")
    statement.add_argument("--party-id")
    statement.add_argument("--destination")
    statement.add_argument(
        "--max-html-bytes",
        type=int,
        default=DEFAULT_MAX_HTML_BYTES,
    )
    statement.add_argument(
        "--max-document-bytes",
        type=int,
        default=DEFAULT_MAX_DOCUMENT_BYTES,
    )
    _add_output(statement)

    probe = sub.add_parser(
        "probe",
        help="Run bounded source-family sentinel probes",
    )
    probe.add_argument(
        "--max-html-bytes",
        type=int,
        default=DEFAULT_MAX_HTML_BYTES,
    )
    _add_output(probe)
    return parser


def _validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    for name in ("limit", "max_html_bytes", "max_document_bytes"):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if getattr(args, "timeout", 1.0) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0.0) < 0:
        parser.error("--minimum-interval cannot be negative")
    if getattr(args, "retry_attempts", 1) < 1:
        parser.error("--retry-attempts must be at least 1")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(args, parser)
    payload = execute(args)
    serialized = payload.to_dict() if isinstance(payload, PublicRecordsResult) else payload
    if write_output(
        serialized,
        args,
        summary=f"Washington County {args.command}",
        result_count=_result_count(payload),
    ):
        return
    print(json.dumps(serialized, indent=2, default=str))


if __name__ == "__main__":
    main()
