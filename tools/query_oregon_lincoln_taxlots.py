#!/usr/bin/env python3
"""Query Lincoln County, Oregon's official GeoMoose taxlot-owner WFS.

The county publishes parcel identifiers, assessment account identifiers,
owners, mailing and situs addresses, assessor-map links, and taxlot polygons
through the ``ms:Taxlots_selection`` WFS feature type. This adapter uses the
verified WFS 2.0 paging and sorting contract while retaining the source's
declared EPSG:26915 CRS, the requested EPSG:4326 representation, and the CRS84
coordinate order reported by its GeoJSON response.

Examples:
    uv run python tools/query_oregon_lincoln_taxlots.py sources
    uv run python tools/query_oregon_lincoln_taxlots.py search R452940 \
        --field property --match exact
    uv run python tools/query_oregon_lincoln_taxlots.py search "NW INLET" \
        --field address --match contains --geometry
    uv run python tools/query_oregon_lincoln_taxlots.py probe
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

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
        MinimumIntervalRateLimiter,
        PaginationError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        schema_fingerprint,
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
    )
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PaginationError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "OR"
COUNTY_NAME = "Lincoln County, Oregon"
COUNTY_GEOID = "41041"
PUBLISHER = "Lincoln County GIS"

SOURCE_ID = "us-or-lincoln-county-taxlots-wfs"
PROPERTYWEB_SOURCE_ID = "us-or-lincoln-propertyweb"
ORMAP_SOURCE_ID = "us-or-ormap-cadastral-routing"
INTERACTIVE_MAP_SOURCE_ID = SOURCE_ID
RECORDER_SOURCE_ID = "us-or-lincoln-helion-recorder"
STATEWIDE_TAXLOT_SOURCE_ID = "us-or-owrd-public-tax-lots"

APP_URL = "https://maps.co.lincoln.or.us/"
CONFIG_URL = "https://maps.co.lincoln.or.us/config.js"
MAPBOOK_URL = "https://maps.co.lincoln.or.us/mapbook.xml"
MAPSERVER_URL = "https://maps.co.lincoln.or.us/fcgi-bin/mapserv.exe"
MAPFILE = "C:/ms4w/apps/gm3-lincoln-data/a_assessment.map"
TYPE_NAME = "ms:Taxlots_selection"
FEATURE_TYPE_LOCAL_NAME = "Taxlots_selection"
WFS_VERSION = "2.0.0"
SOURCE_DEFAULT_CRS = "urn:ogc:def:crs:EPSG::26915"
REQUESTED_CRS = "urn:ogc:def:crs:EPSG::4326"
EXPECTED_RETURNED_CRS = "urn:ogc:def:crs:OGC:1.3:CRS84"
SORT_BY = "propertyid A,ogc_fid A"

OUTPUT_SCHEMA_VERSION = "oregon-lincoln-taxlots/1.0"
PROBE_SCHEMA_VERSION = "oregon-lincoln-taxlots-probe/1.0"
CURSOR_PREFIX = "oregon-lincoln-taxlots:v1:"
CURSOR_VERSION = 1

DEFAULT_PAGE_SIZE = 250
MAX_PAGE_SIZE = 2_000
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
USER_AGENT = "Ithildin Lincoln County Oregon taxlot WFS client"

SENTINEL_PROPERTY_ID = "R452940"
SENTINEL_PARCEL_ID = "07-11-03-DC-05800-00"
BASELINE_COUNT = 44_966
BASELINE_OBSERVED_AT = "2026-07-29"
EXPECTED_WGS84_BOUNDS = (
    -124.115659,
    44.275093,
    -123.595894,
    45.045777,
)

PROPERTY_FIELDS = (
    "ogc_fid",
    "imagekey",
    "taxlotacre",
    "mapacres",
    "parcelid",
    "ormapfield",
    "propertyid",
    "ownname",
    "address1",
    "address2",
    "address3",
    "ctystzip",
    "situsall",
    "gislink",
)
DECLARED_FIELDS = ("msGeometry", *PROPERTY_FIELDS)
REQUIRED_FIELDS = frozenset(DECLARED_FIELDS)
EXPECTED_SCHEMA_FINGERPRINT = (
    "a58b2ce9ecaef9df7b86bb1275c6be4d2b08bdc1179c0d15cbc372e3f3284107"
)

SEARCH_FIELDS: Mapping[str, tuple[str, ...]] = {
    "owner": ("ownname",),
    "address": (
        "address1",
        "address2",
        "address3",
        "ctystzip",
        "situsall",
    ),
    "property": ("propertyid",),
    "parcel": ("parcelid", "imagekey"),
}
SEARCH_FIELDS = {
    **SEARCH_FIELDS,
    "all": tuple(
        dict.fromkeys(
            field_name
            for group in ("owner", "address", "property", "parcel")
            for field_name in SEARCH_FIELDS[group]
        )
    ),
}

COMPLEMENTARY_SOURCES: tuple[Mapping[str, Any], ...] = (
    {
        "source_id": PROPERTYWEB_SOURCE_ID,
        "name": "Lincoln County PropertyWeb",
        "url": "https://propertyweb.co.lincoln.or.us/Home",
        "join_fields": ["propertyid", "parcelid"],
        "relationship": "assessment_tax_and_sale_detail_complement",
        "adds": [
            "certified and in-process values",
            "owners and legal description",
            "improvements and land segments",
            "sales and recorded-instrument identifiers",
            "tax bills, payments, receipts, and generated PDFs",
        ],
    },
    {
        "source_id": ORMAP_SOURCE_ID,
        "name": "Oregon ORMAP Assessor Maps",
        "url_field": "ormapfield",
        "join_fields": ["parcelid", "imagekey"],
        "relationship": "official_assessor_map_complement",
        "adds": ["county assessor map representation"],
    },
    {
        "source_id": RECORDER_SOURCE_ID,
        "name": "Lincoln County Clerk Digital Research Room",
        "url": "https://helion.co.lincoln.or.us/DigitalResearchRoomPublic/",
        "join_fields": [
            "PropertyWeb sale instrument",
            "party name",
            "recording date",
        ],
        "join_path": (
            "WFS propertyid -> PropertyWeb PropertyQuickRefID -> "
            "sale instrument -> recorder document number"
        ),
        "relationship": "recorded_instrument_complement",
        "adds": [
            "recorded instrument metadata",
            "grantor and grantee roles",
            "consideration",
            "document image when published",
        ],
    },
    {
        "source_id": STATEWIDE_TAXLOT_SOURCE_ID,
        "name": "Oregon Water Resources Department Public Tax Lots",
        "join_fields": ["normalized parcelid", "county_name"],
        "relationship": "statewide_geometry_and_coverage_complement",
        "adds": ["statewide parcel coverage and an independent geometry route"],
        "coverage_note": (
            "The statewide layer is county-contributed and does not publish "
            "Lincoln owner names."
        ),
    },
)


@dataclass(frozen=True)
class SourceConfig:
    """Stable identity and query contract for the county WFS component."""

    source_id: str
    name: str
    publisher: str
    county_name: str
    county_geoid: str
    app_url: str
    endpoint_url: str
    mapfile: str
    type_name: str
    default_crs: str
    requested_crs: str
    expected_returned_crs: str
    search_fields: Mapping[str, tuple[str, ...]]
    complementary_sources: tuple[Mapping[str, Any], ...]

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role="official_county_taxlot_owner_geometry_wfs",
            base_url=self.endpoint_url,
            dataset_id=self.type_name,
            metadata={
                "publisher": self.publisher,
                "county_name": self.county_name,
                "county_geoid": self.county_geoid,
                "official_app_url": self.app_url,
                "protocol": f"WFS {WFS_VERSION}",
                "mapfile": self.mapfile,
                "source_default_crs": self.default_crs,
                "requested_representation_crs": self.requested_crs,
                "expected_geojson_crs": self.expected_returned_crs,
                "record_kind": "taxlot_owner_geometry",
            },
        )


SOURCE = SourceConfig(
    source_id=SOURCE_ID,
    name="Lincoln County Oregon Taxlot Owner WFS",
    publisher=PUBLISHER,
    county_name=COUNTY_NAME,
    county_geoid=COUNTY_GEOID,
    app_url=APP_URL,
    endpoint_url=MAPSERVER_URL,
    mapfile=MAPFILE,
    type_name=TYPE_NAME,
    default_crs=SOURCE_DEFAULT_CRS,
    requested_crs=REQUESTED_CRS,
    expected_returned_crs=EXPECTED_RETURNED_CRS,
    search_fields=SEARCH_FIELDS,
    complementary_sources=COMPLEMENTARY_SOURCES,
)
SOURCES: Mapping[str, SourceConfig] = {SOURCE_ID: SOURCE}

SOURCE_CATALOG_METADATA: Mapping[str, Mapping[str, Any]] = {
    SOURCE_ID: {
        "source_id": SOURCE_ID,
        "name": SOURCE.name,
        "category": "property",
        "record_types": ["parcel", "owner", "address", "geometry"],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "wfs",
        "auth": "none",
        "official": True,
        "url": APP_URL,
        "query_tool": "tools/query_oregon_lincoln_taxlots.py",
        "search_fields": sorted(SEARCH_FIELDS),
        "supports_geometry": True,
        "pagination": "wfs_2_startindex_count_query_bound",
    }
}
CATALOG_METADATA = SOURCE_CATALOG_METADATA


@dataclass(frozen=True)
class CapabilitiesContract:
    """Stable WFS capabilities used for identity and paging checks."""

    service_title: str
    version: str
    result_paging: bool
    sorting: bool
    feature_name: str
    feature_title: str
    default_crs: str
    other_crs: tuple[str, ...]
    output_formats: tuple[str, ...]
    wgs84_bounds: tuple[float, float, float, float]


@dataclass(frozen=True)
class SchemaContract:
    """Normalized XSD declaration and its drift fingerprint."""

    target_namespace: str
    fields: tuple[Mapping[str, str], ...]
    field_names: tuple[str, ...]
    schema: Mapping[str, Any]
    schema_fingerprint: str


@dataclass(frozen=True)
class CountResult:
    """A WFS 2.0 ``resultType=hits`` observation."""

    number_matched: int
    number_returned: int
    timestamp: str | None


@dataclass(frozen=True)
class CursorState:
    """Opaque continuation bound to one query and one source snapshot."""

    criteria_fingerprint: str
    next_start_index: int
    anchor_property_id: str
    anchor_ogc_fid: str
    total_count: int
    schema_fingerprint: str


@dataclass(frozen=True)
class WFSBatch:
    """One count-aware result slice plus traversal provenance."""

    features: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    start_index: int
    end_index: int
    pages_fetched: int
    schema: SchemaContract
    capabilities: CapabilitiesContract
    returned_crs: str | None


class LincolnSelectionError(ValueError):
    """A caller selection or continuation does not match the query contract."""

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


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ogc_exception(text: str) -> tuple[str | None, str | None] | None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    if _local_name(root.tag) not in {
        "ExceptionReport",
        "ServiceExceptionReport",
    }:
        return None
    code = root.attrib.get("exceptionCode") or root.attrib.get("code")
    message = " ".join(
        value.strip()
        for element in root.iter()
        if _local_name(element.tag) in {"ExceptionText", "ServiceException"}
        and (value := (element.text or "")).strip()
    )
    return code, message or "WFS returned an exception report"


class LincolnWFSClient:
    """Bounded, rate-limited WFS 2.0 client with injectable transport."""

    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        transport: Any = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if page_size > MAX_PAGE_SIZE:
            raise ValueError(f"page_size must not exceed {MAX_PAGE_SIZE}")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self.page_size = page_size
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.retry_policy = RetryPolicy(max_attempts=retry_attempts)
        self.transport = transport or system_trust_session()
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.request_count = 0

    def close(self) -> None:
        close = getattr(self.transport, "close", None)
        if callable(close):
            close()

    def _response_text(self, response: Any) -> str:
        headers = getattr(response, "headers", {})
        declared_length = _header(headers, "Content-Length")
        if declared_length is not None:
            try:
                content_length = int(declared_length)
            except ValueError:
                content_length = None
            if content_length is not None and content_length > self.max_response_bytes:
                raise SourceResponseError(
                    "Lincoln County WFS response exceeds the configured byte bound",
                    url=MAPSERVER_URL,
                    details={
                        "content_length": content_length,
                        "max_response_bytes": self.max_response_bytes,
                    },
                )

        chunks: list[bytes] = []
        total_bytes = 0
        iterator = getattr(response, "iter_content", None)
        if callable(iterator):
            raw_chunks = iterator(64 * 1024)
        else:
            content = getattr(response, "content", None)
            if isinstance(content, bytes):
                raw_chunks = (content,)
            else:
                raw_chunks = (str(getattr(response, "text", "")).encode(),)
        for chunk in raw_chunks:
            if not chunk:
                continue
            encoded = chunk if isinstance(chunk, bytes) else str(chunk).encode()
            total_bytes += len(encoded)
            if total_bytes > self.max_response_bytes:
                raise SourceResponseError(
                    "Lincoln County WFS response exceeds the configured byte bound",
                    url=MAPSERVER_URL,
                    details={
                        "received_bytes": total_bytes,
                        "max_response_bytes": self.max_response_bytes,
                    },
                )
            chunks.append(encoded)
        encoding = _clean(getattr(response, "encoding", None)) or "utf-8"
        return b"".join(chunks).decode(encoding, errors="replace")

    def _request_text(
        self,
        params: Mapping[str, Any],
        *,
        accept: str,
    ) -> str:
        request_params = {
            "map": MAPFILE,
            "SERVICE": "WFS",
            "VERSION": WFS_VERSION,
            **dict(params),
        }
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.transport.request(
                    "GET",
                    MAPSERVER_URL,
                    params=request_params,
                    headers={
                        "Accept": accept,
                        "User-Agent": USER_AGENT,
                    },
                    timeout=self.timeout,
                    stream=True,
                )
            except (
                requests.RequestException,
                TimeoutError,
                ConnectionError,
            ) as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        "Lincoln County WFS request failed after "
                        f"{attempt} attempts: {error}",
                        url=MAPSERVER_URL,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            try:
                status_code = int(
                    getattr(response, "status_code", getattr(response, "status", 0))
                )
                text = self._response_text(response)
                headers = getattr(response, "headers", {})
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
            if status_code in self.retry_policy.retry_statuses:
                retry_after = _header(headers, "Retry-After")
                retry_seconds: float | None = None
                if retry_after is not None:
                    try:
                        retry_seconds = max(0.0, float(retry_after))
                    except ValueError:
                        retry_seconds = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt, retry_seconds))
                    continue
                if status_code == 429:
                    raise RateLimitedHTTPError(
                        status_code,
                        url=MAPSERVER_URL,
                        response_text=text,
                    )
                raise HTTPStatusError(
                    status_code,
                    url=MAPSERVER_URL,
                    response_text=text,
                )
            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=MAPSERVER_URL,
                    response_text=text,
                )
            if status_code == 451:
                raise TermsBlockedHTTPError(
                    status_code,
                    url=MAPSERVER_URL,
                    response_text=text,
                )
            if status_code in {404, 410}:
                raise SourceChangedHTTPError(
                    status_code,
                    url=MAPSERVER_URL,
                    response_text=text,
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=MAPSERVER_URL,
                    response_text=text,
                )
            exception = _ogc_exception(text)
            if exception is not None:
                code, message = exception
                raise SourceResponseError(
                    message,
                    url=MAPSERVER_URL,
                    details={"ogc_exception_code": code},
                )
            return text

        raise TransportError(
            f"Lincoln County WFS request failed: {last_error}",
            url=MAPSERVER_URL,
            details={"attempts": self.retry_policy.max_attempts},
        )

    def fetch_capabilities(self) -> str:
        return self._request_text(
            {"REQUEST": "GetCapabilities"},
            accept="application/xml,text/xml",
        )

    def describe_schema(self) -> str:
        return self._request_text(
            {
                "REQUEST": "DescribeFeatureType",
                "TYPENAMES": TYPE_NAME,
            },
            accept="application/xml,text/xml",
        )

    def fetch_count(self, filter_xml: str | None) -> CountResult:
        params: dict[str, Any] = {
            "REQUEST": "GetFeature",
            "TYPENAMES": TYPE_NAME,
            "RESULTTYPE": "hits",
        }
        if filter_xml:
            params["FILTER"] = filter_xml
        text = self._request_text(params, accept="application/xml,text/xml")
        return parse_hits(text)

    def fetch_page(
        self,
        filter_xml: str | None,
        *,
        start_index: int,
        count: int,
    ) -> Mapping[str, Any]:
        params: dict[str, Any] = {
            "REQUEST": "GetFeature",
            "TYPENAMES": TYPE_NAME,
            "OUTPUTFORMAT": "application/json",
            "SRSNAME": REQUESTED_CRS,
            "COUNT": count,
            "STARTINDEX": start_index,
            "SORTBY": SORT_BY,
        }
        if filter_xml:
            params["FILTER"] = filter_xml
        text = self._request_text(params, accept="application/json")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise SourceSchemaError(
                "Lincoln County WFS returned invalid GeoJSON",
                url=MAPSERVER_URL,
                details={"response_text": text[:500]},
            ) from error
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Lincoln County WFS GeoJSON must be an object",
                url=MAPSERVER_URL,
                details={"response_type": type(payload).__name__},
            )
        return payload


_NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "ows": "http://www.opengis.net/ows/1.1",
    "fes": "http://www.opengis.net/fes/2.0",
    "xsd": "http://www.w3.org/2001/XMLSchema",
}
FES_NAMESPACE = _NS["fes"]
ET.register_namespace("fes", FES_NAMESPACE)


def _xml_root(text: str, *, operation: str) -> ET.Element:
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        raise SourceSchemaError(
            f"Lincoln County WFS {operation} returned invalid XML",
            url=MAPSERVER_URL,
            details={"response_text": text[:500]},
        ) from error


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def parse_capabilities(text: str) -> CapabilitiesContract:
    """Parse and validate the WFS 2.0 feature and paging declaration."""

    root = _xml_root(text, operation="GetCapabilities")
    version = root.attrib.get("version", "")
    service_title = _text(root.find(".//ows:ServiceIdentification/ows:Title", _NS))
    feature_element: ET.Element | None = None
    for candidate in root.findall(".//wfs:FeatureType", _NS):
        if _text(candidate.find("wfs:Name", _NS)) == TYPE_NAME:
            feature_element = candidate
            break
    if feature_element is None:
        raise SourceSchemaError(
            f"WFS capabilities no longer advertise {TYPE_NAME}",
            url=MAPSERVER_URL,
        )

    constraints: dict[str, str | None] = {}
    for constraint in (
        *root.findall(".//ows:Constraint", _NS),
        *root.findall(".//fes:Constraint", _NS),
    ):
        name = constraint.attrib.get("name")
        if name:
            constraints[name] = _text(constraint.find("ows:DefaultValue", _NS))
    result_paging = str(constraints.get("ImplementsResultPaging", "")).upper() == "TRUE"
    sorting = str(constraints.get("ImplementsSorting", "")).upper() == "TRUE"

    lower_text = _text(
        feature_element.find(
            "ows:WGS84BoundingBox/ows:LowerCorner",
            _NS,
        )
    )
    upper_text = _text(
        feature_element.find(
            "ows:WGS84BoundingBox/ows:UpperCorner",
            _NS,
        )
    )
    try:
        lower = tuple(float(value) for value in (lower_text or "").split())
        upper = tuple(float(value) for value in (upper_text or "").split())
    except ValueError as error:
        raise SourceSchemaError(
            "WFS capabilities publish an invalid WGS84 extent",
            url=MAPSERVER_URL,
        ) from error
    if len(lower) != 2 or len(upper) != 2:
        raise SourceSchemaError(
            "WFS capabilities lack a two-dimensional WGS84 extent",
            url=MAPSERVER_URL,
        )
    bounds = (lower[0], lower[1], upper[0], upper[1])

    contract = CapabilitiesContract(
        service_title=service_title or "",
        version=version,
        result_paging=result_paging,
        sorting=sorting,
        feature_name=TYPE_NAME,
        feature_title=_text(feature_element.find("wfs:Title", _NS)) or "",
        default_crs=_text(feature_element.find("wfs:DefaultCRS", _NS)) or "",
        other_crs=tuple(
            value
            for element in feature_element.findall("wfs:OtherCRS", _NS)
            if (value := _text(element))
        ),
        output_formats=tuple(
            value
            for element in feature_element.findall(
                "wfs:OutputFormats/wfs:Format",
                _NS,
            )
            if (value := _text(element))
        ),
        wgs84_bounds=bounds,
    )
    if contract.version != WFS_VERSION:
        raise SourceSchemaError(
            "Lincoln County WFS version changed",
            url=MAPSERVER_URL,
            details={"expected": WFS_VERSION, "observed": contract.version},
        )
    if not contract.result_paging or not contract.sorting:
        raise SourceSchemaError(
            "Lincoln County WFS no longer declares ordered result paging",
            url=MAPSERVER_URL,
            details={
                "result_paging": contract.result_paging,
                "sorting": contract.sorting,
            },
        )
    if contract.default_crs != SOURCE_DEFAULT_CRS:
        raise SourceSchemaError(
            "Lincoln County taxlot source CRS changed",
            url=MAPSERVER_URL,
            details={
                "expected": SOURCE_DEFAULT_CRS,
                "observed": contract.default_crs,
            },
        )
    if REQUESTED_CRS not in contract.other_crs:
        raise SourceSchemaError(
            "Lincoln County WFS no longer advertises EPSG:4326 output",
            url=MAPSERVER_URL,
            details={"other_crs": list(contract.other_crs)},
        )
    if "application/json" not in contract.output_formats:
        raise SourceSchemaError(
            "Lincoln County taxlot feature no longer advertises GeoJSON",
            url=MAPSERVER_URL,
            details={"output_formats": list(contract.output_formats)},
        )
    min_x, min_y, max_x, max_y = contract.wgs84_bounds
    if not (-124.6 <= min_x < max_x <= -123.2 and 43.8 <= min_y < max_y <= 45.4):
        raise SourceSchemaError(
            "WFS extent does not identify Lincoln County, Oregon",
            url=MAPSERVER_URL,
            details={"wgs84_bounds": list(contract.wgs84_bounds)},
        )
    return contract


def parse_schema(text: str) -> SchemaContract:
    """Normalize the declared XSD while requiring the searchable fields."""

    root = _xml_root(text, operation="DescribeFeatureType")
    target_namespace = root.attrib.get("targetNamespace", "")
    complex_type: ET.Element | None = None
    for candidate in root.findall(".//xsd:complexType", _NS):
        if candidate.attrib.get("name") == f"{FEATURE_TYPE_LOCAL_NAME}Type":
            complex_type = candidate
            break
    if complex_type is None:
        raise SourceSchemaError(
            f"WFS schema lacks {FEATURE_TYPE_LOCAL_NAME}Type",
            url=MAPSERVER_URL,
        )
    fields: list[dict[str, str]] = []
    for element in complex_type.findall(".//xsd:sequence/xsd:element", _NS):
        name = element.attrib.get("name")
        if not name:
            continue
        fields.append(
            {
                "name": name,
                "type": element.attrib.get("type", ""),
                "min_occurs": element.attrib.get("minOccurs", "1"),
                "max_occurs": element.attrib.get("maxOccurs", "1"),
            }
        )
    names = tuple(field["name"] for field in fields)
    missing = sorted(REQUIRED_FIELDS - set(names))
    if missing:
        raise SourceSchemaError(
            "Lincoln County taxlot WFS schema is missing required fields",
            url=MAPSERVER_URL,
            details={"missing_fields": missing},
        )
    schema = {
        "kind": "wfs_xsd_declared",
        "target_namespace": target_namespace,
        "feature_type": TYPE_NAME,
        "fields": fields,
    }
    return SchemaContract(
        target_namespace=target_namespace,
        fields=tuple(fields),
        field_names=names,
        schema=schema,
        schema_fingerprint=schema_fingerprint(schema),
    )


def parse_hits(text: str) -> CountResult:
    """Parse WFS 2.0 ``resultType=hits`` count metadata."""

    root = _xml_root(text, operation="GetFeature hits")
    if _local_name(root.tag) != "FeatureCollection":
        raise SourceSchemaError(
            "WFS hits response is not a FeatureCollection",
            url=MAPSERVER_URL,
            details={"root": _local_name(root.tag)},
        )
    matched = root.attrib.get("numberMatched")
    returned = root.attrib.get("numberReturned", "0")
    try:
        number_matched = int(matched or "")
        number_returned = int(returned)
    except ValueError as error:
        raise SourceSchemaError(
            "WFS hits response lacks numeric count metadata",
            url=MAPSERVER_URL,
            details={
                "numberMatched": matched,
                "numberReturned": returned,
            },
        ) from error
    if number_matched < 0 or number_returned < 0:
        raise SourceSchemaError(
            "WFS hits response contains a negative count",
            url=MAPSERVER_URL,
        )
    return CountResult(
        number_matched=number_matched,
        number_returned=number_returned,
        timestamp=root.attrib.get("timeStamp"),
    )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _escape_like_literal(value: str) -> str:
    """Escape FES wildcard characters using the declared ``!`` escape."""

    return value.replace("!", "!!").replace("*", "!*").replace("?", "!?")


def build_filter(selector: str, field: str, match: str) -> str:
    """Build an XML-safe FES 2.0 equality or contains filter."""

    value = _clean(selector)
    if not value:
        raise LincolnSelectionError("blank_query", "search query must not be blank")
    if field not in SEARCH_FIELDS:
        raise LincolnSelectionError(
            "unsupported_search_field",
            f"unknown search field {field!r}",
            details={"supported_fields": sorted(SEARCH_FIELDS)},
        )
    if match not in {"exact", "contains"}:
        raise LincolnSelectionError(
            "unsupported_match",
            f"unknown match mode {match!r}",
            details={"supported_matches": ["exact", "contains"]},
        )

    root = ET.Element(f"{{{FES_NAMESPACE}}}Filter")
    parent = root
    fields = SEARCH_FIELDS[field]
    if len(fields) > 1:
        parent = ET.SubElement(root, f"{{{FES_NAMESPACE}}}Or")
    for field_name in fields:
        if match == "exact":
            comparison = ET.SubElement(
                parent,
                f"{{{FES_NAMESPACE}}}PropertyIsEqualTo",
                {"matchCase": "false"},
            )
            literal_value = value
        else:
            comparison = ET.SubElement(
                parent,
                f"{{{FES_NAMESPACE}}}PropertyIsLike",
                {
                    "wildCard": "*",
                    "singleChar": "?",
                    "escapeChar": "!",
                    "matchCase": "false",
                },
            )
            literal_value = f"*{_escape_like_literal(value)}*"
        ET.SubElement(
            comparison,
            f"{{{FES_NAMESPACE}}}ValueReference",
        ).text = field_name
        ET.SubElement(
            comparison,
            f"{{{FES_NAMESPACE}}}Literal",
        ).text = literal_value
    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def _effective_match(field: str, requested: str) -> str:
    if requested != "auto":
        return requested
    return "exact" if field in {"property", "parcel"} else "contains"


def _criteria_fingerprint(
    *,
    filter_xml: str,
    field: str,
    match: str,
    geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "feature_type": TYPE_NAME,
            "wfs_version": WFS_VERSION,
            "filter": filter_xml,
            "field": field,
            "match": match,
            "geometry": geometry,
            "ordering": SORT_BY,
            "requested_crs": REQUESTED_CRS,
            "pagination": "wfs_2_startindex_count",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "start": state.next_start_index,
        "anchor_property": state.anchor_property_id,
        "anchor_fid": state.anchor_ogc_fid,
        "total": state.total_count,
        "schema": state.schema_fingerprint,
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode()).decode().rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(cursor: str | None) -> CursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise LincolnSelectionError(
            "invalid_cursor",
            "cursor does not belong to the Lincoln County taxlot adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode())
        if not isinstance(payload, Mapping):
            raise TypeError("cursor payload must be an object")
        start = payload["start"]
        total = payload["total"]
        criteria = payload["criteria"]
        anchor_property = payload["anchor_property"]
        anchor_fid = payload["anchor_fid"]
        schema_value = payload["schema"]
        if (
            type(start) is not int
            or type(total) is not int
            or not isinstance(criteria, str)
            or not isinstance(anchor_property, str)
            or not isinstance(anchor_fid, str)
            or not isinstance(schema_value, str)
        ):
            raise TypeError("cursor fields have invalid types")
        state = CursorState(
            criteria_fingerprint=criteria,
            next_start_index=start,
            anchor_property_id=anchor_property,
            anchor_ogc_fid=anchor_fid,
            total_count=total,
            schema_fingerprint=schema_value,
        )
    except (
        binascii.Error,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise LincolnSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from None
    if (
        not isinstance(payload, Mapping)
        or payload.get("v") != CURSOR_VERSION
        or state.next_start_index <= 0
        or state.total_count <= state.next_start_index
        or not state.anchor_property_id
        or not state.anchor_ogc_fid
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise LincolnSelectionError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _collection_features(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if payload.get("type") != "FeatureCollection":
        raise SourceSchemaError(
            "WFS GeoJSON is not a FeatureCollection",
            url=MAPSERVER_URL,
            details={"type": payload.get("type")},
        )
    features = payload.get("features")
    if not isinstance(features, list) or any(
        not isinstance(feature, Mapping) for feature in features
    ):
        raise SourceSchemaError(
            "WFS GeoJSON lacks a valid features array",
            url=MAPSERVER_URL,
        )
    return features


def _returned_crs(payload: Mapping[str, Any]) -> str | None:
    crs = payload.get("crs")
    if not isinstance(crs, Mapping):
        return None
    properties = crs.get("properties")
    if not isinstance(properties, Mapping):
        return None
    return _clean(properties.get("name"))


def _properties(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    properties = feature.get("properties")
    if not isinstance(properties, Mapping):
        raise SourceSchemaError(
            "WFS feature lacks a properties object",
            url=MAPSERVER_URL,
        )
    return properties


def _feature_identity(feature: Mapping[str, Any]) -> tuple[str, str]:
    properties = _properties(feature)
    property_id = _clean(properties.get("propertyid"))
    ogc_fid = _clean(properties.get("ogc_fid"))
    if not property_id or not ogc_fid:
        raise SourceSchemaError(
            "WFS feature lacks propertyid or ogc_fid",
            url=MAPSERVER_URL,
            details={"propertyid": property_id, "ogc_fid": ogc_fid},
        )
    return property_id, ogc_fid


def _require_expected_crs(payload: Mapping[str, Any]) -> str:
    returned_crs = _returned_crs(payload)
    if returned_crs != EXPECTED_RETURNED_CRS:
        raise SourceSchemaError(
            "Lincoln County WFS returned an unexpected GeoJSON CRS",
            url=MAPSERVER_URL,
            details={
                "expected": EXPECTED_RETURNED_CRS,
                "observed": returned_crs,
            },
        )
    return returned_crs


def _load_contract(client: Any) -> tuple[CapabilitiesContract, SchemaContract]:
    capabilities = parse_capabilities(client.fetch_capabilities())
    schema = parse_schema(client.describe_schema())
    return capabilities, schema


def _fetch_batch(
    client: Any,
    *,
    filter_xml: str,
    field: str,
    match: str,
    geometry: bool,
    limit: int,
    cursor: str | None,
) -> WFSBatch:
    capabilities, schema = _load_contract(client)
    criteria = _criteria_fingerprint(
        filter_xml=filter_xml,
        field=field,
        match=match,
        geometry=geometry,
    )
    state = _decode_cursor(cursor)
    if state is not None:
        if state.criteria_fingerprint != criteria:
            raise LincolnSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to different Lincoln taxlot query criteria",
            )
        if state.schema_fingerprint != schema.schema_fingerprint:
            raise LincolnSelectionError(
                "cursor_schema_changed",
                "declared WFS schema changed after the cursor was issued",
                details={
                    "cursor_schema": state.schema_fingerprint,
                    "current_schema": schema.schema_fingerprint,
                },
            )

    count_result = client.fetch_count(filter_xml)
    total_count = count_result.number_matched
    if state is not None and total_count != state.total_count:
        raise LincolnSelectionError(
            "cursor_snapshot_changed",
            "matching WFS record count changed after the cursor was issued",
            details={
                "cursor_count": state.total_count,
                "current_count": total_count,
            },
        )

    start_index = state.next_start_index if state else 0
    if start_index > total_count:
        raise LincolnSelectionError(
            "cursor_out_of_range",
            "cursor start index exceeds the current result count",
            details={"start_index": start_index, "total_count": total_count},
        )
    if state is not None:
        boundary_payload = client.fetch_page(
            filter_xml,
            start_index=start_index - 1,
            count=1,
        )
        _require_expected_crs(boundary_payload)
        boundary = _collection_features(boundary_payload)
        if len(boundary) != 1:
            raise LincolnSelectionError(
                "cursor_boundary_changed",
                "cursor boundary row is no longer available",
                details={"start_index": start_index},
            )
        observed_boundary = _feature_identity(boundary[0])
        expected_boundary = (
            state.anchor_property_id,
            state.anchor_ogc_fid,
        )
        if observed_boundary != expected_boundary:
            raise LincolnSelectionError(
                "cursor_boundary_changed",
                "cursor boundary row changed after the cursor was issued",
                details={
                    "expected": list(expected_boundary),
                    "observed": list(observed_boundary),
                },
            )

    offset = start_index
    page_size = int(getattr(client, "page_size", DEFAULT_PAGE_SIZE))
    collected: list[Mapping[str, Any]] = []
    pages_fetched = 0
    seen: set[tuple[str, str]] = set()
    previous_identity = (
        (state.anchor_property_id, state.anchor_ogc_fid) if state else None
    )
    returned_crs: str | None = None

    while len(collected) < limit and offset < total_count:
        requested = min(page_size, limit - len(collected), total_count - offset)
        payload = client.fetch_page(
            filter_xml,
            start_index=offset,
            count=requested,
        )
        pages_fetched += 1
        page_crs = _require_expected_crs(payload)
        if returned_crs is None:
            returned_crs = page_crs
        elif page_crs != returned_crs:
            raise SourceSchemaError(
                "WFS GeoJSON CRS changed between result pages",
                url=MAPSERVER_URL,
                details={"first": returned_crs, "observed": page_crs},
            )
        features = _collection_features(payload)
        if len(features) > requested:
            raise PaginationError(
                "WFS returned more rows than requested",
                url=MAPSERVER_URL,
                details={
                    "requested": requested,
                    "returned": len(features),
                    "start_index": offset,
                },
            )
        if not features:
            raise PaginationError(
                "WFS paging stopped before the advertised count",
                url=MAPSERVER_URL,
                details={"start_index": offset, "total_count": total_count},
            )
        for feature in features:
            identity = _feature_identity(feature)
            if previous_identity is not None and identity <= previous_identity:
                raise PaginationError(
                    "WFS page is not strictly ordered by propertyid and ogc_fid",
                    url=MAPSERVER_URL,
                    details={
                        "previous_identity": list(previous_identity),
                        "observed_identity": list(identity),
                    },
                )
            if identity in seen:
                raise PaginationError(
                    "WFS paging repeated a feature identity",
                    url=MAPSERVER_URL,
                    details={
                        "propertyid": identity[0],
                        "ogc_fid": identity[1],
                    },
                )
            seen.add(identity)
            previous_identity = identity
            collected.append(feature)
        offset += len(features)

    next_cursor = None
    if collected and offset < total_count:
        property_id, ogc_fid = _feature_identity(collected[-1])
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria,
                next_start_index=offset,
                anchor_property_id=property_id,
                anchor_ogc_fid=ogc_fid,
                total_count=total_count,
                schema_fingerprint=schema.schema_fingerprint,
            )
        )
    return WFSBatch(
        features=tuple(collected),
        next_cursor=next_cursor,
        total_count=total_count,
        start_index=start_index,
        end_index=offset,
        pages_fetched=pages_fetched,
        schema=schema,
        capabilities=capabilities,
        returned_crs=returned_crs,
    )


def _float_observation(value: Any, field_name: str, meaning: str) -> dict[str, Any]:
    raw = _clean(value)
    normalized: float | None = None
    if raw is not None:
        try:
            normalized = float(raw)
        except ValueError:
            normalized = None
    return {
        "source_field": field_name,
        "meaning": meaning,
        "raw_value": raw,
        "acres": normalized,
    }


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    geometry_requested: bool,
    returned_crs: str | None,
    schema_value: str,
) -> dict[str, Any]:
    properties = _properties(feature)
    property_id, ogc_fid = _feature_identity(feature)
    parcel_id = _clean(properties.get("parcelid"))
    image_key = _clean(properties.get("imagekey"))
    owner_name = _clean(properties.get("ownname"))
    mailing_lines = [
        value
        for field_name in ("address1", "address2", "address3")
        if (value := _clean(properties.get(field_name)))
    ]
    city_state_zip = _clean(properties.get("ctystzip"))
    formatted_mailing = ", ".join(
        [*mailing_lines, *([city_state_zip] if city_state_zip else [])]
    )
    native_id = ogc_fid
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "taxlot_owner_geometry",
        native_id,
    )
    record: dict[str, Any] = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "record_kind": "taxlot_owner_geometry",
        "source_id": SOURCE_ID,
        "source_url": MAPSERVER_URL,
        "native_id": native_id,
        "native_id_basis": "ogc_fid",
        "source_record_id": ogc_fid,
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "access_state": "public_anonymous",
        "jurisdiction": {
            "state_code": STATE_CODE,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "native_identity": {
            "propertyid": property_id,
            "parcelid": parcel_id,
            "ogc_fid": ogc_fid,
            "imagekey": image_key,
        },
        "property_account_id": property_id,
        "assessment_account_ids": [property_id],
        "map_taxlot_ids": [
            value for value in (parcel_id, image_key) if value is not None
        ],
        "owners": (
            [
                {
                    "raw_name": owner_name,
                    "role": "assessment_roll_owner",
                    "assertion_type": "county_taxlot_layer",
                    "source_field": "ownname",
                }
            ]
            if owner_name
            else []
        ),
        "mailing_address": {
            "raw_lines": mailing_lines,
            "city_state_zip": city_state_zip,
            "formatted": formatted_mailing or None,
            "source_fields": [
                "address1",
                "address2",
                "address3",
                "ctystzip",
            ],
        },
        "situs_address": {
            "raw": _clean(properties.get("situsall")),
            "source_field": "situsall",
        },
        "acreage_observations": [
            _float_observation(
                properties.get("taxlotacre"),
                "taxlotacre",
                "county_taxlot_acres",
            ),
            _float_observation(
                properties.get("mapacres"),
                "mapacres",
                "mapped_polygon_acres",
            ),
        ],
        "official_links": {
            "interactive_map": _clean(properties.get("gislink")),
            "assessor_map": _clean(properties.get("ormapfield")),
            "propertyweb": "https://propertyweb.co.lincoln.or.us/Home",
        },
        "join_keys": {
            "propertyweb_property_quick_ref_id": property_id,
            "parcelid": parcel_id,
            "imagekey": image_key,
            "owner_name": owner_name,
        },
        "join_candidates": {
            PROPERTYWEB_SOURCE_ID: {
                "property_quick_ref": property_id,
                "map_number": parcel_id,
                "relationship": "parcel_geometry_and_owner_to_assessment_tax",
            },
            ORMAP_SOURCE_ID: {
                "parcel_id": parcel_id,
                "image_key": image_key,
                "relationship": "taxlot_to_official_assessor_map",
            },
            STATEWIDE_TAXLOT_SOURCE_ID: {
                "parcel_id": parcel_id,
                "county_name": "Lincoln",
                "relationship": "county_taxlot_to_statewide_geometry",
            },
        },
        "geometry_available": isinstance(feature.get("geometry"), Mapping),
        "geometry_lineage": {
            "source_default_crs": SOURCE_DEFAULT_CRS,
            "wfs_requested_srs": REQUESTED_CRS,
            "geojson_reported_crs": returned_crs,
            "coordinate_order": "longitude_latitude",
            "transformation_performed_by": "Lincoln County MapServer WFS",
        },
        "source_schema": {
            "feature_type": TYPE_NAME,
            "declared_schema_fingerprint": schema_value,
        },
        "source_provenance": {
            "publisher": PUBLISHER,
            "official_app_url": APP_URL,
            "wfs_endpoint": MAPSERVER_URL,
            "mapfile": MAPFILE,
            "feature_type": TYPE_NAME,
            "wfs_version": WFS_VERSION,
            "ordering": SORT_BY,
        },
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
        "source_native": dict(properties),
    }
    if geometry_requested:
        geometry = feature.get("geometry")
        if not isinstance(geometry, Mapping):
            raise SourceSchemaError(
                "geometry was requested but the WFS feature lacks geometry",
                url=MAPSERVER_URL,
                details={"propertyid": property_id},
            )
        record["geometry"] = dict(geometry)
        record["geometry_crs"] = returned_crs
    return record


def _jurisdiction() -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id="us-or-lincoln",
        name=COUNTY_NAME,
        state_code=STATE_CODE,
        county_fips=COUNTY_GEOID,
        locality="Lincoln County",
        metadata={"government_level": "county"},
    )


def _build_query(
    *,
    operation: str,
    selector: str,
    field: str,
    match: str,
    geometry: bool,
    limit: int,
    cursor: str | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE.source_metadata(),
        jurisdiction=_jurisdiction(),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "field": field,
                "match": match,
                "geometry": geometry,
            },
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "protocol": f"WFS {WFS_VERSION}",
                "pagination": "COUNT/STARTINDEX with query-bound cursor",
                "ordering": SORT_BY,
                "source_default_crs": SOURCE_DEFAULT_CRS,
                "requested_srs": REQUESTED_CRS,
            },
        ),
    )


def _client(args: argparse.Namespace) -> LincolnWFSClient:
    return LincolnWFSClient(
        page_size=args.page_size,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
        max_response_bytes=args.max_response_bytes,
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
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _schema_warnings(schema: SchemaContract) -> tuple[str, ...]:
    if schema.schema_fingerprint == EXPECTED_SCHEMA_FINGERPRINT:
        return ()
    return (
        "The live declared WFS schema differs from the observed baseline; "
        "the fields used by this result remain available.",
    )


def _search_result(
    query: PublicRecordsQuery,
    batch: WFSBatch,
    *,
    geometry_requested: bool,
) -> PublicRecordsResult:
    records: list[dict[str, Any]] = []
    errors: list[PublicRecordsError] = []
    for index, feature in enumerate(batch.features):
        try:
            records.append(
                _normalize_feature(
                    feature,
                    geometry_requested=geometry_requested,
                    returned_crs=batch.returned_crs,
                    schema_value=batch.schema.schema_fingerprint,
                )
            )
        except (TypeError, ValueError, PublicRecordsHTTPError) as error:
            errors.append(
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    details={"record_index": index},
                )
            )
            break
    snapshot = {
        "total_matching_records": batch.total_count,
        "start_index": batch.start_index,
        "end_index_exclusive": batch.end_index,
        "returned_records": len(records),
        "continuation_available": batch.next_cursor is not None,
        "pages_fetched": batch.pages_fetched,
        "ordering": SORT_BY,
        "schema_fingerprint": batch.schema.schema_fingerprint,
        "source_default_crs": batch.capabilities.default_crs,
        "geojson_reported_crs": batch.returned_crs,
    }
    for record in records:
        record["retrieval_snapshot"] = snapshot
    warnings = _schema_warnings(batch.schema)
    if errors:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL if records else ResultStatus.SOURCE_CHANGED,
            errors,
            records=records,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=warnings,
    )


def _execute_search(
    args: argparse.Namespace,
    *,
    client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    match = _effective_match(args.field, args.match)
    query = _build_query(
        operation="search",
        selector=args.query,
        field=args.field,
        match=match,
        geometry=args.geometry,
        limit=args.limit,
        cursor=args.cursor,
    )
    active_client: Any = None
    try:
        active_client = client or _client(args)
        filter_xml = build_filter(args.query, args.field, match)
        batch = _fetch_batch(
            active_client,
            filter_xml=filter_xml,
            field=args.field,
            match=match,
            geometry=args.geometry,
            limit=args.limit,
            cursor=args.cursor,
        )
        result = _search_result(
            query,
            batch,
            geometry_requested=args.geometry,
        )
    except LincolnSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="adapter_failure",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    finally:
        if client is None and active_client is not None:
            close = getattr(active_client, "close", None)
            if callable(close):
                close()
    if log_results:
        _best_effort_log(query, result)
    return result


def _execute_probe(
    args: argparse.Namespace,
    *,
    client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _build_query(
        operation="probe",
        selector=SENTINEL_PROPERTY_ID,
        field="property",
        match="exact",
        geometry=True,
        limit=1,
        cursor=None,
    )
    active_client: Any = None
    try:
        active_client = client or _client(args)
        capabilities, schema = _load_contract(active_client)
        total = active_client.fetch_count(None)
        filter_xml = build_filter(
            SENTINEL_PROPERTY_ID,
            "property",
            "exact",
        )
        sentinel_count = active_client.fetch_count(filter_xml)
        if sentinel_count.number_matched != 1:
            raise SourceSchemaError(
                "configured Lincoln WFS sentinel is not uniquely available",
                url=MAPSERVER_URL,
                details={
                    "propertyid": SENTINEL_PROPERTY_ID,
                    "number_matched": sentinel_count.number_matched,
                },
            )
        payload = active_client.fetch_page(
            filter_xml,
            start_index=0,
            count=1,
        )
        features = _collection_features(payload)
        if len(features) != 1:
            raise SourceSchemaError(
                "configured Lincoln WFS sentinel returned an unexpected row count",
                url=MAPSERVER_URL,
                details={"returned": len(features)},
            )
        returned_crs = _require_expected_crs(payload)
        representative = _normalize_feature(
            features[0],
            geometry_requested=True,
            returned_crs=returned_crs,
            schema_value=schema.schema_fingerprint,
        )
        if representative["native_identity"]["parcelid"] != SENTINEL_PARCEL_ID:
            raise SourceSchemaError(
                "configured Lincoln WFS sentinel parcel identity changed",
                url=MAPSERVER_URL,
                details={
                    "expected": SENTINEL_PARCEL_ID,
                    "observed": representative["native_identity"]["parcelid"],
                },
            )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "schema_version": PROBE_SCHEMA_VERSION,
                    "record_kind": "source_probe",
                    "source_id": SOURCE_ID,
                    "service_identity": {
                        "official_app_url": APP_URL,
                        "config_url": CONFIG_URL,
                        "mapbook_url": MAPBOOK_URL,
                        "wfs_endpoint": MAPSERVER_URL,
                        "mapfile": MAPFILE,
                        "feature_type": TYPE_NAME,
                        "service_title": capabilities.service_title,
                        "feature_title": capabilities.feature_title,
                    },
                    "jurisdiction_evidence": {
                        "official_host": urlparse(APP_URL).hostname,
                        "county_geoid": COUNTY_GEOID,
                        "wgs84_bounds": list(capabilities.wgs84_bounds),
                        "verified": True,
                    },
                    "protocol_contract": {
                        "version": capabilities.version,
                        "result_paging": capabilities.result_paging,
                        "sorting": capabilities.sorting,
                        "ordering": SORT_BY,
                        "output_formats": list(capabilities.output_formats),
                    },
                    "crs_lineage": {
                        "source_default_crs": capabilities.default_crs,
                        "other_declared_crs": list(capabilities.other_crs),
                        "requested_srs": REQUESTED_CRS,
                        "geojson_reported_crs": returned_crs,
                        "coordinate_order": "longitude_latitude",
                    },
                    "declared_schema": schema.schema,
                    "schema_baseline": {
                        "expected_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
                        "observed_fingerprint": schema.schema_fingerprint,
                        "matches": (
                            schema.schema_fingerprint == EXPECTED_SCHEMA_FINGERPRINT
                        ),
                        "field_count": len(schema.fields),
                    },
                    "count_baseline": {
                        "observed_count": BASELINE_COUNT,
                        "observed_at": BASELINE_OBSERVED_AT,
                        "current_count": total.number_matched,
                        "source_timestamp": total.timestamp,
                    },
                    "update_observation": {
                        "mapbook_statement": (
                            "The official mapbook identifies county taxlots as "
                            "updated nightly and notes that boundary changes "
                            "recorded after July 1 may not appear until after "
                            "November tax payments."
                        ),
                        "source": MAPBOOK_URL,
                    },
                    "sentinel_strategy": "exact_propertyid",
                    "sentinel_count": sentinel_count.number_matched,
                    "representative_row": representative,
                    "complementary_sources": list(COMPLEMENTARY_SOURCES),
                }
            ],
            warnings=_schema_warnings(schema),
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="probe_failed",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    finally:
        if client is None and active_client is not None:
            close = getattr(active_client, "close", None)
            if callable(close):
                close()
    if log_results:
        _best_effort_log(query, result)
    return result


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "sources": [
            {
                **SOURCE.source_metadata().to_dict(),
                "catalog_metadata": SOURCE_CATALOG_METADATA[SOURCE_ID],
                "official_lineage": {
                    "app_url": APP_URL,
                    "config_url": CONFIG_URL,
                    "mapbook_url": MAPBOOK_URL,
                    "wfs_endpoint": MAPSERVER_URL,
                    "mapfile": MAPFILE,
                    "feature_type": TYPE_NAME,
                },
                "search_fields": {
                    key: list(value) for key, value in SEARCH_FIELDS.items()
                },
                "match_modes": ["exact", "contains"],
                "geometry": {
                    "opt_in": True,
                    "source_default_crs": SOURCE_DEFAULT_CRS,
                    "requested_srs": REQUESTED_CRS,
                    "expected_geojson_crs": EXPECTED_RETURNED_CRS,
                    "expected_wgs84_bounds": list(EXPECTED_WGS84_BOUNDS),
                },
                "declared_fields": list(DECLARED_FIELDS),
                "expected_schema_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
                "baseline_count": BASELINE_COUNT,
                "baseline_observed_at": BASELINE_OBSERVED_AT,
                "request_bounds": {
                    "maximum_page_size": MAX_PAGE_SIZE,
                    "default_max_response_bytes": DEFAULT_MAX_RESPONSE_BYTES,
                },
                "complementary_sources": list(COMPLEMENTARY_SOURCES),
            }
        ],
        "process_learnings": [
            {
                "scope": "protocol_discovery",
                "learning": (
                    "Probe every advertised WFS version: this endpoint's 2.0 "
                    "contract adds working result paging and output-CRS support "
                    "that are not apparent from a 1.0-only probe."
                ),
            },
            {
                "scope": "crs_lineage",
                "learning": (
                    "Retain the declared source CRS, requested representation "
                    "CRS, and GeoJSON-reported CRS as distinct observations."
                ),
            },
            {
                "scope": "identity_and_paging",
                "learning": (
                    "Audit live sort-key uniqueness before cursoring. Lincoln's "
                    "propertyid repeats across feature rows, while the composite "
                    "propertyid and ogc_fid order preserves each source record."
                ),
            },
            {
                "scope": "complementary_records",
                "learning": (
                    "The WFS propertyid and parcelid connect geometry and owner "
                    "rows to richer assessor/tax, map, recorder, and statewide "
                    "coverage components."
                ),
            },
        ],
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute source discovery, record search, or the bounded sentinel probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "probe":
        return _execute_probe(
            args,
            client=client,
            log_results=log_results,
        )
    return _execute_search(
        args,
        client=client,
        log_results=log_results,
    )


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
    count = (
        len(records) if isinstance(records, list) else len(payload.get("sources", []))
    )
    if write_output(
        payload,
        args,
        summary=f"Lincoln County taxlot WFS {args.command}",
        result_count=count,
    ):
        return
    if args.command == "sources":
        print(f"Lincoln County taxlot WFS sources: {count}")
        for source in payload["sources"]:
            print(f"  {source['source_id']} | {', '.join(source['search_fields'])}")
        return
    print(
        f"Lincoln County taxlot WFS {args.command}: "
        f"{payload.get('status')} ({count} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in payload.get("records", []):
        native = record.get("native_identity", {})
        print(
            f"  {native.get('propertyid') or record.get('record_kind')} | "
            f"{native.get('parcelid') or SOURCE_ID}"
        )
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=DEFAULT_MAX_RESPONSE_BYTES,
    )
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
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Lincoln County Oregon's official taxlot-owner WFS"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="List the WFS and its joinable complementary sources",
    )
    add_output_args(sources)

    search = subparsers.add_parser(
        "search",
        help="Search owner, address, property ID, or parcel ID fields",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=sorted(SEARCH_FIELDS),
        default="all",
    )
    search.add_argument(
        "--match",
        choices=("auto", "exact", "contains"),
        default="auto",
        help=(
            "Match mode; auto uses exact for property/parcel and contains "
            "for owner/address/all"
        ),
    )
    search.add_argument("--limit", type=int, default=100)
    search.add_argument(
        "--cursor",
        help="Query-bound continuation cursor from an earlier result",
    )
    search.add_argument(
        "--geometry",
        action="store_true",
        help="Include the WFS GeoJSON polygon and full CRS lineage",
    )
    _add_transport_arguments(search)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded capabilities, schema, count, and sentinel probe",
    )
    _add_transport_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for name in ("page_size", "retry_attempts", "max_response_bytes"):
        if hasattr(args, name) and getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if hasattr(args, "page_size") and args.page_size > MAX_PAGE_SIZE:
        parser.error(f"--page-size must not exceed {MAX_PAGE_SIZE}")
    if hasattr(args, "timeout") and args.timeout <= 0:
        parser.error("--timeout must be positive")
    if hasattr(args, "minimum_interval") and args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if hasattr(args, "limit") and args.limit <= 0:
        parser.error("--limit must be positive")
    if hasattr(args, "query") and not args.query.strip():
        parser.error("query must not be blank")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
