#!/usr/bin/env python3
"""Query and transfer Montana State Library cadastral data.

Montana State Library (MSL) publishes the statewide cadastral framework in
three useful forms:

* a live ArcGIS parcel layer with selected ORION CAMA attributes;
* monthly statewide and county parcel archives in SHP and file-geodatabase
  formats; and
* monthly county and statewide ORION SQL Server database archives.

This adapter discovers the current files from the publisher's directory
listings rather than treating the mutable monthly filenames as version
numbers.  Each bulk manifest derives its release identity from the exact
filename, publisher-local modification marker, and byte size observed in the
listing.

Parcel queries use ordered OBJECTID keyset traversal.  Cursors are bound to
the query criteria and an observed source snapshot.  ``PARCELID`` is preserved
as Montana's parcel/geocode join identifier, but it is nullable in the live
layer; source occurrences therefore retain ``GlobalID`` and ``OBJECTID`` too.

Examples:
    uv run python tools/query_montana_cadastral.py metadata --json
    uv run python tools/query_montana_cadastral.py parcel 56382732101040000
    uv run python tools/query_montana_cadastral.py owner "THOMPSON CONTRACTING"
    uv run python tools/query_montana_cadastral.py search \
        --county Petroleum --tax-year 2026 --limit 20
    uv run python tools/query_montana_cadastral.py point -110.7 46.9 --geometry
    uv run python tools/query_montana_cadastral.py releases --json
    uv run python tools/query_montana_cadastral.py manifest \
        --dataset parcel-shp --county Petroleum
    uv run python tools/query_montana_cadastral.py artifact-probe \
        --dataset parcel-shp --county Petroleum
    uv run python tools/query_montana_cadastral.py download \
        --dataset parcel-shp --county Petroleum --destination /tmp/mt-cadastral
    uv run python tools/query_montana_cadastral.py alternatives --json
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import URLError
from urllib.parse import urljoin

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        inspect_zip,
    )
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
        ArcGISRESTClient,
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        inspect_zip,
    )
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
        ArcGISRESTClient,
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-mt-msl-cadastral"
STATE_CODE = "MT"
STATE_FIPS = "30"

LANDING_URL = "https://msl.mt.gov/geoinfo/msdi/cadastral/"
APPLICATION_URL = "https://svc.mt.gov/msl/cadastral/"
SERVICE_URL = (
    "https://gisservice.mt.gov/arcgis/rest/services/"
    "msdi_cadastral_map_v1/MapServer"
)
LAYER_URL = f"{SERVICE_URL}/1"
QUERY_URL = f"{LAYER_URL}/query"

BULK_ROOT = "https://ftpgeoinfo.msl.mt.gov/Data/Spatial/MSDI/Cadastral/"
PARCEL_ROOT = f"{BULK_ROOT}Parcels/"
ORION_ROOT = f"{BULK_ROOT}ORION_SQLDatabases/"
PARCEL_METADATA_URL = (
    f"{PARCEL_ROOT}MontanaCadastral_ParcelMetadata.xml"
)
MONTHLY_UPDATE_MAP_URL = (
    f"{PARCEL_ROOT}Statewide/MonthlyCadastralUpdateMap.pdf"
)
ORION_COUNTY_NUMBER_URL = f"{ORION_ROOT}CountyNumber.pdf"
ORION_DIAGRAM_URL = f"{ORION_ROOT}Orion_Diagram.pdf"
ORION_SETUP_URL = f"{ORION_ROOT}BEGIN%20HERE.zip"
CADNSDI_URL = "https://msl.mt.gov/geoinfo/msdi/cadastral/CadNSDI"
PLSS_ROOT = f"{BULK_ROOT}PLSS/"
PUBLIC_LANDS_ROOT = f"{BULK_ROOT}PublicLands/"
CONSERVATION_EASEMENTS_ROOT = f"{BULK_ROOT}ConservationEasements/"
HISTORIC_ROOT = f"{BULK_ROOT}CadastralHistoric/"

DEFAULT_PAGE_SIZE = 500
DEFAULT_LIMIT = 100
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = "mt-msl-cadastral:v1:"
CURSOR_VERSION = 1

DATASET_TYPES = ("parcel-shp", "parcel-gdb", "orion")

REQUIRED_FIELDS = (
    "OBJECTID",
    "GlobalID",
    "PARCELID",
    "COUNTYCD",
    "CountyName",
    "CountyAbbr",
    "TaxYear",
    "PropertyID",
    "AssessmentCode",
    "AddressLine1",
    "CityStateZip",
    "LegalDescriptionShort",
    "TotalBuildingValue",
    "TotalLandValue",
    "TotalValue",
    "OwnerName",
)

QUERY_FIELDS = (
    "OBJECTID",
    "GlobalID",
    "PARCELID",
    "COUNTYCD",
    "CountyName",
    "CountyAbbr",
    "GISAcres",
    "TaxYear",
    "PropertyID",
    "AssessmentCode",
    "Township",
    "Range",
    "Section",
    "LegalDescriptionShort",
    "Subdivision",
    "CertificateOfSurvey",
    "AddressLine1",
    "AddressLine2",
    "CityStateZip",
    "PropAccess",
    "LevyDistrict",
    "PropType",
    "ContinuousCropAcres",
    "FallowAcres",
    "FarmsiteAcres",
    "ForestAcres",
    "GrazingAcres",
    "WildHayAcres",
    "IrrigatedAcres",
    "NonQualAcres",
    "TotalAcres",
    "TotalBuildingValue",
    "TotalLandValue",
    "TotalValue",
    "OwnerName",
    "OwnerAddress1",
    "OwnerAddress2",
    "OwnerAddress3",
    "OwnerCity",
    "OwnerState",
    "OwnerZipCode",
    "DbaName",
    "CareOfTaxpayer",
)

SOURCE_WARNINGS = (
    "The live layer contains selected CAMA attributes and parcel geometry; "
    "recorded deed, mortgage, lien, and instrument history belongs to the "
    "relevant county clerk/recorder system.",
    "MSL integrates Department of Revenue data with county-maintained parcel "
    "data for Ravalli, Silver Bow, Missoula, Flathead, and Yellowstone.",
    "PARCELID is Montana's published parcel/geocode join identifier, but some "
    "live features do not carry one. Preserve GlobalID and OBJECTID with each "
    "source occurrence.",
    "Bulk filenames are rolling aliases. The adapter versions an observation "
    "with the publisher listing's modification marker and byte size.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Montana State Library Cadastral Framework",
    source_role="statewide_parcel_discovery_selected_cama_and_bulk_release",
    base_url=LANDING_URL,
    dataset_id="msdi-cadastral-map-v1-layer-1",
    metadata={
        "authority": "State of Montana",
        "operator": "Montana State Library",
        "live_layer": LAYER_URL,
        "bulk_root": BULK_ROOT,
        "coverage": "Montana statewide, 56 counties",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-mt",
    name="Montana",
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS},
)


@dataclass(frozen=True)
class County:
    prefix: int
    name: str
    abbreviation: str
    directory: str
    geoid: str


# CountyPrefix and abbreviations are the publisher's ORION identifiers from
# CountyNumber.pdf. They are not Census county FIPS codes. The GEOIDs below
# are the explicit Census county crosswalk; directory spellings are discovered
# in the parcel root.
COUNTIES = (
    County(1, "Silver Bow", "SB", "SilverBow", "30093"),
    County(2, "Cascade", "CS", "Cascade", "30013"),
    County(3, "Yellowstone", "YE", "Yellowstone", "30111"),
    County(4, "Missoula", "MS", "Missoula", "30063"),
    County(5, "Lewis and Clark", "LC", "LewisClark", "30049"),
    County(6, "Gallatin", "GA", "Gallatin", "30031"),
    County(7, "Flathead", "FL", "Flathead", "30029"),
    County(8, "Fergus", "FE", "Fergus", "30027"),
    County(9, "Powder River", "PR", "PowderRiver", "30075"),
    County(10, "Carbon", "CA", "Carbon", "30009"),
    County(11, "Phillips", "PH", "Phillips", "30071"),
    County(12, "Hill", "HI", "Hill", "30041"),
    County(13, "Ravalli", "RA", "Ravalli", "30081"),
    County(14, "Custer", "CU", "Custer", "30017"),
    County(15, "Lake", "LA", "Lake", "30047"),
    County(16, "Dawson", "DW", "Dawson", "30021"),
    County(17, "Roosevelt", "RO", "Roosevelt", "30085"),
    County(18, "Beaverhead", "BE", "Beaverhead", "30001"),
    County(19, "Chouteau", "CH", "Chouteau", "30015"),
    County(20, "Valley", "VA", "Valley", "30105"),
    County(21, "Toole", "TO", "Toole", "30101"),
    County(22, "Big Horn", "BH", "BigHorn", "30003"),
    County(23, "Musselshell", "MU", "Musselshell", "30065"),
    County(24, "Blaine", "BL", "Blaine", "30005"),
    County(25, "Madison", "MA", "Madison", "30057"),
    County(26, "Pondera", "PO", "Pondera", "30073"),
    County(27, "Richland", "RI", "Richland", "30083"),
    County(28, "Powell", "PW", "Powell", "30077"),
    County(29, "Rosebud", "RS", "Rosebud", "30087"),
    County(30, "Deer Lodge", "DL", "DeerLodge", "30023"),
    County(31, "Teton", "TE", "Teton", "30099"),
    County(32, "Stillwater", "ST", "Stillwater", "30095"),
    County(33, "Treasure", "TR", "Treasure", "30103"),
    County(34, "Sheridan", "SH", "Sheridan", "30091"),
    County(35, "Sanders", "SA", "Sanders", "30089"),
    County(36, "Judith Basin", "JB", "JudithBasin", "30045"),
    County(37, "Daniels", "DA", "Daniels", "30019"),
    County(38, "Glacier", "GL", "Glacier", "30035"),
    County(39, "Fallon", "FA", "Fallon", "30025"),
    County(40, "Sweet Grass", "SG", "SweetGrass", "30097"),
    County(41, "McCone", "MC", "McCone", "30055"),
    County(42, "Carter", "CR", "Carter", "30011"),
    County(43, "Broadwater", "BR", "Broadwater", "30007"),
    County(44, "Wheatland", "WH", "Wheatland", "30107"),
    County(45, "Prairie", "PI", "Prairie", "30079"),
    County(46, "Granite", "GR", "Granite", "30039"),
    County(47, "Meagher", "ME", "Meagher", "30059"),
    County(48, "Liberty", "LI", "Liberty", "30051"),
    County(49, "Park", "PA", "Park", "30067"),
    County(50, "Garfield", "GF", "Garfield", "30033"),
    County(51, "Jefferson", "JE", "Jefferson", "30043"),
    County(52, "Wibaux", "WI", "Wibaux", "30109"),
    County(53, "Golden Valley", "GV", "GoldenValley", "30037"),
    County(54, "Mineral", "MI", "Mineral", "30061"),
    County(55, "Petroleum", "PE", "Petroleum", "30069"),
    County(56, "Lincoln", "LN", "Lincoln", "30053"),
)


def _selector_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


COUNTY_BY_PREFIX = {county.prefix: county for county in COUNTIES}
COUNTY_BY_GEOID = {county.geoid: county for county in COUNTIES}
COUNTY_ALIASES: dict[str, County] = {}
for _county in COUNTIES:
    for _alias in (
        str(_county.prefix),
        _county.name,
        _county.abbreviation,
        _county.directory,
        _county.geoid,
        _county.geoid[-3:],
        f"{_county.name} County",
    ):
        COUNTY_ALIASES[_selector_key(_alias)] = _county
COUNTY_ALIASES["buttesilverbow"] = COUNTY_BY_PREFIX[1]
COUNTY_ALIASES["lewisclark"] = COUNTY_BY_PREFIX[5]

if (
    len(COUNTIES) != 56
    or len(COUNTY_BY_PREFIX) != 56
    or set(COUNTY_BY_PREFIX) != set(range(1, 57))
    or len(COUNTY_BY_GEOID) != 56
    or any(
        not re.fullmatch(r"30\d{3}", county.geoid)
        for county in COUNTIES
    )
):
    raise RuntimeError("Montana ORION-to-Census county crosswalk is invalid")


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    url: str
    modified_local: str
    modified_sort: str
    size: int | None
    is_directory: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "publisher_modified_local": self.modified_local,
            "publisher_modified_sort": self.modified_sort,
            "size": self.size,
            "is_directory": self.is_directory,
        }


@dataclass(frozen=True)
class SourceSnapshot:
    schema_fingerprint: str
    data_fingerprint: str
    native_page_size: int
    total_features: int
    features_with_parcel_id: int
    maximum_object_id: int
    edge_tax_year: int | None
    layer_metadata: Mapping[str, Any]


@dataclass(frozen=True)
class CursorState:
    criteria_fingerprint: str
    last_object_id: int
    total_count: int
    schema_fingerprint: str
    data_fingerprint: str


@dataclass(frozen=True)
class Selection:
    where: str
    spatial_parameters: Mapping[str, Any]
    county: County | None = None


class MontanaCadastralError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "selection",
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


_DIRECTORY_ENTRY_RE = re.compile(
    r"(?P<modified>\d{1,2}/\d{1,2}/\d{4}\s+"
    r"\d{1,2}:\d{2}\s+[AP]M)\s+"
    r"(?P<size>\d+|&lt;dir&gt;|<dir>)\s+"
    r'<A\s+HREF="(?P<href>[^"]+)">(?P<name>[^<]+)</A>',
    flags=re.IGNORECASE,
)


def parse_directory_listing(body: str, base_url: str) -> tuple[DirectoryEntry, ...]:
    """Parse the publisher's IIS-style directory listing."""
    entries: list[DirectoryEntry] = []
    for match in _DIRECTORY_ENTRY_RE.finditer(body):
        raw_modified = " ".join(match.group("modified").split())
        try:
            parsed_modified = datetime.strptime(
                raw_modified,
                "%m/%d/%Y %I:%M %p",
            )
        except ValueError as error:
            raise SourceSchemaError(
                "MSL directory contains an invalid modification marker",
                url=base_url,
                details={"value": raw_modified},
            ) from error
        size_token = match.group("size").casefold()
        is_directory = "dir" in size_token
        name = html.unescape(match.group("name")).strip()
        entries.append(
            DirectoryEntry(
                name=name,
                url=urljoin(base_url, html.unescape(match.group("href"))),
                modified_local=raw_modified,
                modified_sort=parsed_modified.strftime("%Y-%m-%dT%H:%M:%S"),
                size=None if is_directory else int(match.group("size")),
                is_directory=is_directory,
            )
        )
    if not entries:
        raise SourceSchemaError(
            "MSL directory listing contains no parseable entries",
            url=base_url,
            details={"body_prefix": body[:300]},
        )
    return tuple(sorted(entries, key=lambda entry: entry.name.casefold()))


class MontanaCadastralClient(ArcGISRESTClient):
    """Live ArcGIS and publisher-directory client."""

    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            LAYER_URL,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            **kwargs,
        )

    def _request_text(self, url: str) -> str:
        headers = {
            "Accept": "text/html,text/plain,*/*",
            "User-Agent": self.user_agent,
        }
        transient_errors = (URLError, TimeoutError, ConnectionError, OSError)
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.transport.request(
                    "GET",
                    url,
                    params=None,
                    headers=headers,
                    timeout=self.timeout,
                )
            except transient_errors as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        f"MSL directory request failed after {attempt} attempts: "
                        f"{error}",
                        url=url,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue
            status = int(
                getattr(response, "status_code", getattr(response, "status", 0))
            )
            text = str(getattr(response, "text", ""))
            if status in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                if status == 429:
                    raise RateLimitedHTTPError(status, url=url, response_text=text)
                raise HTTPStatusError(status, url=url, response_text=text)
            if status in {401, 403}:
                raise RestrictedHTTPError(status, url=url, response_text=text)
            if status in {404, 410}:
                raise SourceChangedHTTPError(status, url=url, response_text=text)
            if status < 200 or status >= 300:
                raise HTTPStatusError(status, url=url, response_text=text)
            return text
        raise TransportError(
            "MSL directory request failed",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )

    def fetch_directory(self, url: str) -> tuple[DirectoryEntry, ...]:
        return parse_directory_listing(self._request_text(url), url)

    def fetch_count(
        self,
        where: str,
        spatial_parameters: Mapping[str, Any] | None = None,
    ) -> int:
        payload = self._request_json(
            QUERY_URL,
            params={
                "where": where,
                **dict(spatial_parameters or {}),
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        if (
            not isinstance(payload, Mapping)
            or "error" in payload
            or isinstance(payload.get("count"), bool)
            or not isinstance(payload.get("count"), int)
            or payload["count"] < 0
        ):
            raise SourceResponseError(
                "MSL ArcGIS count response is invalid",
                url=QUERY_URL,
                details={"response": payload},
            )
        return int(payload["count"])

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        spatial_parameters: Mapping[str, Any] | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        payload = self._request_json(
            QUERY_URL,
            params={
                "where": where,
                **dict(spatial_parameters or {}),
                "outFields": ",".join(QUERY_FIELDS),
                "orderByFields": "OBJECTID ASC",
                "resultRecordCount": record_count,
                "returnGeometry": str(return_geometry).lower(),
                **({"outSR": 4326} if return_geometry else {}),
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "MSL ArcGIS query response is invalid",
                url=QUERY_URL,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "MSL ArcGIS query response lacks a valid features array",
                url=QUERY_URL,
            )
        return tuple(features)

    def fetch_county_statistics(self) -> tuple[Mapping[str, Any], ...]:
        payload = self._request_json(
            QUERY_URL,
            params={
                "where": "1=1",
                "outStatistics": canonical_json(
                    [
                        {
                            "statisticType": "count",
                            "onStatisticField": "OBJECTID",
                            "outStatisticFieldName": "feature_count",
                        }
                    ]
                ),
                "groupByFieldsForStatistics": (
                    "COUNTYCD,CountyName,CountyAbbr"
                ),
                "orderByFields": "COUNTYCD ASC",
                "returnGeometry": "false",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "MSL county-statistics response is invalid",
                url=QUERY_URL,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list):
            raise SourceSchemaError(
                "MSL county-statistics response lacks features",
                url=QUERY_URL,
            )
        rows: list[Mapping[str, Any]] = []
        for feature in features:
            attributes = (
                feature.get("attributes")
                if isinstance(feature, Mapping)
                else None
            )
            if not isinstance(attributes, Mapping):
                raise SourceSchemaError(
                    "MSL county-statistics row lacks attributes",
                    url=QUERY_URL,
                )
            rows.append(attributes)
        return tuple(rows)

    def fetch_snapshot(self) -> SourceSnapshot:
        layer = self._request_json(LAYER_URL, params={"f": "json"})
        if not isinstance(layer, Mapping) or "error" in layer:
            raise SourceResponseError(
                "MSL parcel layer metadata is invalid",
                url=LAYER_URL,
                details={"response": layer},
            )
        return _compatible_snapshot(
            layer,
            total_features=self.fetch_count("1=1"),
            features_with_parcel_id=self.fetch_count("PARCELID IS NOT NULL"),
            edge=self._fetch_edge(),
        )

    def _fetch_edge(self) -> Mapping[str, Any]:
        payload = self._request_json(
            QUERY_URL,
            params={
                "where": "1=1",
                "outFields": "OBJECTID,TaxYear",
                "orderByFields": "OBJECTID DESC",
                "resultRecordCount": 1,
                "returnGeometry": "false",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "MSL parcel edge response is invalid",
                url=QUERY_URL,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or len(features) != 1:
            raise SourceSchemaError(
                "MSL parcel edge response does not contain one feature",
                url=QUERY_URL,
            )
        attributes = features[0].get("attributes")
        if not isinstance(attributes, Mapping):
            raise SourceSchemaError(
                "MSL parcel edge response lacks attributes",
                url=QUERY_URL,
            )
        return attributes


def _compatible_snapshot(
    layer: Mapping[str, Any],
    *,
    total_features: int,
    features_with_parcel_id: int,
    edge: Mapping[str, Any],
) -> SourceSnapshot:
    identity = {
        "id": layer.get("id"),
        "name": layer.get("name"),
        "type": layer.get("type"),
        "geometryType": layer.get("geometryType"),
    }
    expected = {
        "id": 1,
        "name": "Montana Parcels",
        "type": "Feature Layer",
        "geometryType": "esriGeometryPolygon",
    }
    if identity != expected:
        raise SourceSchemaError(
            "MSL parcel layer identity changed",
            url=LAYER_URL,
            details={"expected": expected, "observed": identity},
        )
    if "Query" not in str(layer.get("capabilities", "")).split(","):
        raise SourceSchemaError(
            "MSL parcel layer no longer declares query capability",
            url=LAYER_URL,
        )
    advanced = layer.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping) or not (
        advanced.get("supportsOrderBy") is True
        and advanced.get("supportsPagination") is True
    ):
        raise SourceSchemaError(
            "MSL parcel layer lacks ordered/paginated query support",
            url=LAYER_URL,
        )
    fields = layer.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "MSL parcel layer lacks field declarations",
            url=LAYER_URL,
        )
    definitions = {
        str(field.get("name")): {
            key: field.get(key)
            for key in ("name", "type", "alias", "length", "nullable")
            if key in field
        }
        for field in fields
        if isinstance(field.get("name"), str)
    }
    missing = sorted(set(REQUIRED_FIELDS) - set(definitions))
    if missing:
        raise SourceSchemaError(
            "MSL parcel layer is missing required fields",
            url=LAYER_URL,
            details={"missing_fields": missing},
        )
    if definitions["OBJECTID"].get("type") != "esriFieldTypeOID":
        raise SourceSchemaError(
            "MSL OBJECTID is no longer the ArcGIS occurrence key",
            url=LAYER_URL,
        )
    native_page_size = layer.get("maxRecordCount")
    if (
        isinstance(native_page_size, bool)
        or not isinstance(native_page_size, int)
        or native_page_size <= 0
    ):
        raise SourceSchemaError(
            "MSL parcel layer lacks a usable maxRecordCount",
            url=LAYER_URL,
        )
    maximum_object_id = edge.get("OBJECTID")
    edge_tax_year = edge.get("TaxYear")
    if (
        isinstance(maximum_object_id, bool)
        or not isinstance(maximum_object_id, int)
        or maximum_object_id <= 0
    ):
        raise SourceSchemaError(
            "MSL parcel edge lacks a valid OBJECTID",
            url=QUERY_URL,
            details={"edge": dict(edge)},
        )
    if edge_tax_year is not None and (
        isinstance(edge_tax_year, bool) or not isinstance(edge_tax_year, int)
    ):
        raise SourceSchemaError(
            "MSL parcel edge contains an invalid TaxYear",
            url=QUERY_URL,
            details={"edge": dict(edge)},
        )
    if not 0 <= features_with_parcel_id <= total_features:
        raise SourceSchemaError(
            "MSL parcel identifier counts are inconsistent",
            url=QUERY_URL,
            details={
                "total_features": total_features,
                "features_with_parcel_id": features_with_parcel_id,
            },
        )
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "identity": identity,
            "fields": definitions,
            "max_record_count": native_page_size,
        }
    )
    data_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "total_features": total_features,
            "features_with_parcel_id": features_with_parcel_id,
            "maximum_object_id": maximum_object_id,
            "edge_tax_year": edge_tax_year,
        }
    )
    return SourceSnapshot(
        schema_fingerprint=schema_fingerprint,
        data_fingerprint=data_fingerprint,
        native_page_size=native_page_size,
        total_features=total_features,
        features_with_parcel_id=features_with_parcel_id,
        maximum_object_id=maximum_object_id,
        edge_tax_year=edge_tax_year,
        layer_metadata=dict(layer),
    )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any, field_name: str = "selector") -> str:
    text = _clean_text(value)
    if text is None:
        raise MontanaCadastralError(
            "blank_selector",
            f"{field_name} must not be blank",
            details={"field": field_name},
        )
    return text.replace("'", "''")


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


def _county_from_selector(value: str | None) -> County | None:
    if value is None:
        return None
    county = COUNTY_ALIASES.get(_selector_key(value))
    if county is None:
        raise MontanaCadastralError(
            "unknown_county",
            "county must be a Montana county name, MSL abbreviation, or "
            "ORION CountyPrefix, or Census county GEOID/FIPS suffix",
            details={"county": value},
        )
    return county


def _optional_clauses(args: argparse.Namespace) -> tuple[list[str], County | None]:
    clauses: list[str] = []
    county = _county_from_selector(getattr(args, "county", None))
    if county is not None:
        clauses.append(f"COUNTYCD={county.prefix}")
    if getattr(args, "tax_year", None) is not None:
        clauses.append(f"TaxYear={int(args.tax_year)}")
    query = getattr(args, "query", None)
    if query:
        selector = _sql_text(query, "query")
        upper = selector.upper()
        numeric_property = (
            f"PropertyID={int(selector)} OR "
            if selector.isdigit()
            else ""
        )
        clauses.append(
            "("
            f"{numeric_property}"
            f"UPPER(PARCELID) LIKE '%{upper}%' OR "
            f"UPPER(AssessmentCode) LIKE '%{upper}%' OR "
            f"UPPER(OwnerName) LIKE '%{upper}%' OR "
            f"UPPER(DbaName) LIKE '%{upper}%' OR "
            f"UPPER(CareOfTaxpayer) LIKE '%{upper}%' OR "
            f"UPPER(AddressLine1) LIKE '%{upper}%' OR "
            f"UPPER(AddressLine2) LIKE '%{upper}%' OR "
            f"UPPER(CityStateZip) LIKE '%{upper}%'"
            ")"
        )
    parcel_id = getattr(args, "parcel_id", None)
    if parcel_id:
        clauses.append(f"PARCELID='{_sql_text(parcel_id, 'parcel_id')}'")
    property_id = getattr(args, "property_id", None)
    if property_id:
        selector = _sql_text(property_id, "property_id")
        numeric_clause = (
            f"PropertyID={int(selector)} OR "
            if selector.isdigit()
            else ""
        )
        clauses.append(
            f"({numeric_clause}AssessmentCode='{selector}')"
        )
    owner = getattr(args, "owner", None)
    if owner:
        selector = _sql_text(owner, "owner").upper()
        clauses.append(
            "("
            f"UPPER(OwnerName) LIKE '%{selector}%' OR "
            f"UPPER(DbaName) LIKE '%{selector}%' OR "
            f"UPPER(CareOfTaxpayer) LIKE '%{selector}%'"
            ")"
        )
    address = getattr(args, "address", None)
    if address:
        selector = _sql_text(address, "address").upper()
        clauses.append(
            "("
            f"UPPER(AddressLine1) LIKE '%{selector}%' OR "
            f"UPPER(AddressLine2) LIKE '%{selector}%' OR "
            f"UPPER(CityStateZip) LIKE '%{selector}%'"
            ")"
        )
    return clauses, county


def _selection_from_args(args: argparse.Namespace) -> Selection:
    command = args.command
    spatial: dict[str, Any] = {}
    clauses, county = _optional_clauses(args)
    if command == "parcel":
        clauses.insert(0, f"PARCELID='{_sql_text(args.identifier, 'parcel_id')}'")
    elif command == "owner":
        selector = _sql_text(args.name, "owner").upper()
        clauses.insert(
            0,
            "("
            f"UPPER(OwnerName) LIKE '%{selector}%' OR "
            f"UPPER(DbaName) LIKE '%{selector}%' OR "
            f"UPPER(CareOfTaxpayer) LIKE '%{selector}%'"
            ")",
        )
    elif command == "address":
        selector = _sql_text(args.query, "address").upper()
        clauses.insert(
            0,
            "("
            f"UPPER(AddressLine1) LIKE '%{selector}%' OR "
            f"UPPER(AddressLine2) LIKE '%{selector}%' OR "
            f"UPPER(CityStateZip) LIKE '%{selector}%'"
            ")",
        )
    elif command == "objectid":
        clauses.insert(0, f"OBJECTID={int(args.object_id)}")
    elif command == "point":
        spatial = {
            "geometry": f"{args.longitude},{args.latitude}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        }
    elif command == "probe":
        clauses.insert(0, "PARCELID IS NOT NULL")
    return Selection(
        where=" AND ".join(f"({clause})" for clause in clauses) or "1=1",
        spatial_parameters=spatial,
        county=county,
    )


def _criteria_fingerprint(
    selection: Selection,
    *,
    operation: str,
    return_geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "operation": operation,
            "where": selection.where,
            "spatial_parameters": dict(selection.spatial_parameters),
            "return_geometry": return_geometry,
            "out_fields": QUERY_FIELDS,
            "ordering": "OBJECTID ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "criteria": state.criteria_fingerprint,
        "last_oid": state.last_object_id,
        "total": state.total_count,
        "schema": state.schema_fingerprint,
        "data": state.data_fingerprint,
    }
    payload["check"] = sha256_fingerprint(payload)[:16]
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(value: str | None) -> CursorState | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise MontanaCadastralError(
            "invalid_cursor",
            "cursor does not belong to the Montana cadastral adapter",
        )
    token = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(token + padding).decode("utf-8")
        )
        supplied_check = str(payload.pop("check"))
        expected_check = sha256_fingerprint(payload)[:16]
        state = CursorState(
            criteria_fingerprint=str(payload["criteria"]),
            last_object_id=int(payload["last_oid"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
            data_fingerprint=str(payload["data"]),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise MontanaCadastralError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if (
        payload.get("v") != CURSOR_VERSION
        or supplied_check != expected_check
        or state.last_object_id < 0
        or state.total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.data_fingerprint)
    ):
        raise MontanaCadastralError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _validate_cursor(
    state: CursorState | None,
    *,
    criteria: str,
    snapshot: SourceSnapshot,
) -> None:
    if state is None:
        return
    if state.criteria_fingerprint != criteria:
        raise MontanaCadastralError(
            "cursor_query_mismatch",
            "cursor belongs to different query criteria",
        )
    if state.schema_fingerprint != snapshot.schema_fingerprint:
        raise MontanaCadastralError(
            "cursor_schema_changed",
            "the MSL parcel schema changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
        )
    if state.data_fingerprint != snapshot.data_fingerprint:
        raise MontanaCadastralError(
            "cursor_snapshot_changed",
            "the observed MSL parcel snapshot changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
        )


def _feature_attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "MSL parcel feature lacks attributes",
            url=QUERY_URL,
        )
    return attributes


def _object_id(feature: Mapping[str, Any]) -> int:
    value = _feature_attributes(feature).get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SourceSchemaError(
            "MSL parcel feature lacks a valid OBJECTID",
            url=QUERY_URL,
            details={"OBJECTID": value},
        )
    return value


def _keyset_where(where: str, last_object_id: int | None) -> str:
    if last_object_id is None:
        return where
    return f"({where}) AND OBJECTID > {last_object_id}"


def _snapshots_match(left: SourceSnapshot, right: SourceSnapshot) -> bool:
    return (
        left.schema_fingerprint == right.schema_fingerprint
        and left.data_fingerprint == right.data_fingerprint
    )


def _snapshot_record(snapshot: SourceSnapshot) -> dict[str, Any]:
    return {
        "schema_fingerprint": snapshot.schema_fingerprint,
        "data_fingerprint": snapshot.data_fingerprint,
        "total_features": snapshot.total_features,
        "features_with_parcel_id": snapshot.features_with_parcel_id,
        "features_without_parcel_id": (
            snapshot.total_features - snapshot.features_with_parcel_id
        ),
        "maximum_object_id": snapshot.maximum_object_id,
        "edge_tax_year": snapshot.edge_tax_year,
        "native_page_size": snapshot.native_page_size,
        "layer_url": LAYER_URL,
    }


def _traverse(
    client: MontanaCadastralClient,
    *,
    operation: str,
    selection: Selection,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
) -> tuple[
    tuple[Mapping[str, Any], ...],
    str | None,
    SourceSnapshot,
    int,
    int,
]:
    start = client.fetch_snapshot()
    criteria = _criteria_fingerprint(
        selection,
        operation=operation,
        return_geometry=return_geometry,
    )
    state = _decode_cursor(cursor)
    _validate_cursor(state, criteria=criteria, snapshot=start)
    total_count = client.fetch_count(
        selection.where,
        selection.spatial_parameters,
    )
    if state is not None and state.total_count != total_count:
        raise MontanaCadastralError(
            "cursor_count_changed",
            "the matching MSL parcel count changed after the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "cursor_total_count": state.total_count,
                "current_total_count": total_count,
            },
        )
    last_object_id = state.last_object_id if state is not None else None
    remaining_where = _keyset_where(selection.where, last_object_id)
    remaining_count = (
        total_count
        if last_object_id is None
        else client.fetch_count(
            remaining_where,
            selection.spatial_parameters,
        )
    )
    target = min(limit, remaining_count)
    page_size = min(client.page_size, start.native_page_size)
    records: list[Mapping[str, Any]] = []
    while len(records) < target:
        requested = min(page_size, target - len(records))
        page = client.fetch_page(
            where=_keyset_where(selection.where, last_object_id),
            record_count=requested,
            return_geometry=return_geometry,
            spatial_parameters=selection.spatial_parameters,
        )
        if not page:
            raise SourceSchemaError(
                "MSL keyset traversal ended before the reported count",
                url=QUERY_URL,
                details={"target": target, "retrieved": len(records)},
            )
        for feature in page:
            current_object_id = _object_id(feature)
            if last_object_id is not None and current_object_id <= last_object_id:
                raise SourceSchemaError(
                    "MSL keyset traversal repeated or reordered a feature",
                    url=QUERY_URL,
                    details={
                        "previous_object_id": last_object_id,
                        "object_id": current_object_id,
                    },
                )
            records.append(feature)
            last_object_id = current_object_id
        if len(page) < requested and len(records) < target:
            raise SourceSchemaError(
                "MSL keyset traversal returned a short page before its count",
                url=QUERY_URL,
                details={
                    "target": target,
                    "retrieved": len(records),
                    "page_size": len(page),
                },
            )
    end = client.fetch_snapshot()
    end_count = client.fetch_count(
        selection.where,
        selection.spatial_parameters,
    )
    if not _snapshots_match(start, end) or total_count != end_count:
        raise MontanaCadastralError(
            "source_changed_during_query",
            "the observed MSL parcel snapshot changed during traversal",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_snapshot",
            details={
                "start_data_fingerprint": start.data_fingerprint,
                "end_data_fingerprint": end.data_fingerprint,
                "start_count": total_count,
                "end_count": end_count,
            },
        )
    next_cursor = None
    if remaining_count > len(records) and records:
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria,
                last_object_id=_object_id(records[-1]),
                total_count=total_count,
                schema_fingerprint=start.schema_fingerprint,
                data_fingerprint=start.data_fingerprint,
            )
        )
    return tuple(records), next_cursor, start, total_count, remaining_count


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    snapshot: SourceSnapshot,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = dict(_feature_attributes(feature))
    object_id = _object_id(feature)
    county = _county_from_feature_attributes(attributes)
    global_id = _clean_text(attributes.get("GlobalID"))
    parcel_id = _clean_text(attributes.get("PARCELID"))
    native_id = global_id or f"OBJECTID-{object_id}"
    geometry = feature.get("geometry") if geometry_requested else None
    if geometry_requested and not isinstance(geometry, Mapping):
        raise SourceSchemaError(
            "MSL parcel feature lacks requested geometry",
            url=QUERY_URL,
            details={"object_id": object_id},
        )
    return {
        "source_id": SOURCE_ID,
        "record_type": "parcel_feature_occurrence",
        "source_record_id": native_id,
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            county.geoid,
            "parcel-feature",
            native_id,
        ),
        "identity": {
            "object_id": object_id,
            "global_id": global_id,
            "parcel_id": parcel_id,
            "property_id": attributes.get("PropertyID"),
            "assessment_code": _clean_text(attributes.get("AssessmentCode")),
            "occurrence_key": (
                "GlobalID" if global_id is not None else "OBJECTID"
            ),
            "transport_cursor_key": "OBJECTID",
            "parcel_join_key": "PARCELID",
            "parcel_join_key_present": parcel_id is not None,
        },
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_geoid": county.geoid,
            "county_name": county.name,
            "county_abbreviation": county.abbreviation,
            "orion_county_prefix": county.prefix,
        },
        "site_address": {
            "line1": _clean_text(attributes.get("AddressLine1")),
            "line2": _clean_text(attributes.get("AddressLine2")),
            "city_state_zip": _clean_text(attributes.get("CityStateZip")),
            "access": _clean_text(attributes.get("PropAccess")),
        },
        "owner": {
            "name": _clean_text(attributes.get("OwnerName")),
            "dba_name": _clean_text(attributes.get("DbaName")),
            "care_of": _clean_text(attributes.get("CareOfTaxpayer")),
            "address_lines": [
                value
                for value in (
                    _clean_text(attributes.get("OwnerAddress1")),
                    _clean_text(attributes.get("OwnerAddress2")),
                    _clean_text(attributes.get("OwnerAddress3")),
                )
                if value is not None
            ],
            "city": _clean_text(attributes.get("OwnerCity")),
            "state": _clean_text(attributes.get("OwnerState")),
            "postal_code": _clean_text(attributes.get("OwnerZipCode")),
        },
        "assessment": {
            "tax_year": attributes.get("TaxYear"),
            "property_type": _clean_text(attributes.get("PropType")),
            "levy_district": _clean_text(attributes.get("LevyDistrict")),
            "building_value": attributes.get("TotalBuildingValue"),
            "land_value": attributes.get("TotalLandValue"),
            "total_value": attributes.get("TotalValue"),
        },
        "land": {
            "gis_acres": attributes.get("GISAcres"),
            "reported_total_acres": attributes.get("TotalAcres"),
            "township": _clean_text(attributes.get("Township")),
            "range": _clean_text(attributes.get("Range")),
            "section": _clean_text(attributes.get("Section")),
            "legal_description_short": _clean_text(
                attributes.get("LegalDescriptionShort")
            ),
            "subdivision": _clean_text(attributes.get("Subdivision")),
            "certificate_of_survey": _clean_text(
                attributes.get("CertificateOfSurvey")
            ),
            "agricultural_acres": {
                "continuous_crop": attributes.get("ContinuousCropAcres"),
                "fallow": attributes.get("FallowAcres"),
                "farmsite": attributes.get("FarmsiteAcres"),
                "forest": attributes.get("ForestAcres"),
                "grazing": attributes.get("GrazingAcres"),
                "wild_hay": attributes.get("WildHayAcres"),
                "irrigated": attributes.get("IrrigatedAcres"),
                "nonqualifying": attributes.get("NonQualAcres"),
            },
        },
        "geometry": dict(geometry) if isinstance(geometry, Mapping) else None,
        "geometry_crs": "EPSG:4326" if geometry_requested else None,
        "source_attributes": attributes,
        "source_snapshot": _snapshot_record(snapshot),
    }


def _county_from_feature_attributes(
    attributes: Mapping[str, Any],
) -> County:
    raw_prefix = attributes.get("COUNTYCD")
    if isinstance(raw_prefix, bool):
        prefix = None
    elif isinstance(raw_prefix, int):
        prefix = raw_prefix
    else:
        text = _clean_text(raw_prefix)
        prefix = int(text) if text and text.isdigit() else None
    county = COUNTY_BY_PREFIX.get(prefix) if prefix is not None else None
    if county is None:
        raise SourceSchemaError(
            "MSL parcel feature has an unknown ORION county prefix",
            url=QUERY_URL,
            details={"COUNTYCD": raw_prefix},
        )

    conflicts: dict[str, Any] = {}
    for field_name, expected in (
        ("CountyName", county.name),
        ("CountyAbbr", county.abbreviation),
    ):
        observed = _clean_text(attributes.get(field_name))
        if observed is None:
            continue
        resolved = COUNTY_ALIASES.get(_selector_key(observed))
        if resolved is not county:
            conflicts[field_name] = {
                "observed": observed,
                "expected": expected,
            }
    if conflicts:
        raise SourceSchemaError(
            "MSL parcel feature county labels conflict with COUNTYCD",
            url=QUERY_URL,
            details={
                "COUNTYCD": county.prefix,
                "county_geoid": county.geoid,
                "conflicts": conflicts,
            },
        )
    return county


def _entry_by_name(
    entries: Sequence[DirectoryEntry],
    name: str,
    *,
    directory_url: str,
) -> DirectoryEntry:
    matches = [entry for entry in entries if entry.name.casefold() == name.casefold()]
    if len(matches) != 1:
        raise SourceSchemaError(
            "MSL directory does not contain one expected artifact",
            url=directory_url,
            details={"filename": name, "match_count": len(matches)},
        )
    return matches[0]


def _release_marker(entry: DirectoryEntry) -> str:
    compact = entry.modified_sort.replace("-", "").replace(":", "")
    return f"{compact}:{entry.size}"


def _bulk_artifact(
    entry: DirectoryEntry,
    *,
    artifact_id: str,
    role: str,
    media_type: str | None,
    archive_format: str | None,
) -> BulkArtifact:
    return BulkArtifact(
        artifact_id=artifact_id,
        url=entry.url,
        filename=entry.name,
        media_type=media_type,
        archive_format=archive_format,
        expected_size=entry.size,
        last_modified=entry.modified_local,
        metadata={
            "role": role,
            "publisher_modified_local": entry.modified_local,
            "publisher_modified_timezone": "not_declared_in_directory_listing",
        },
    )


def build_bulk_manifest(
    client: MontanaCadastralClient,
    *,
    dataset_type: str,
    county: County | None,
) -> BulkDatasetManifest:
    """Discover one exact current bulk artifact and its official metadata."""
    if dataset_type not in DATASET_TYPES:
        raise MontanaCadastralError(
            "unknown_dataset",
            f"dataset must be one of {', '.join(DATASET_TYPES)}",
        )
    scope = county.directory if county is not None else "Statewide"
    artifacts: list[BulkArtifact] = []
    if dataset_type in {"parcel-shp", "parcel-gdb"}:
        suffix = "SHP.zip" if dataset_type == "parcel-shp" else "GDB.zip"
        if county is None:
            directory_url = BULK_ROOT
            entries = client.fetch_directory(directory_url)
            filename = f"MontanaCadastral_{suffix}"
        else:
            directory_url = f"{PARCEL_ROOT}{county.directory}/"
            entries = client.fetch_directory(directory_url)
            filename = f"{county.directory}_{suffix}"
        data_entry = _entry_by_name(entries, filename, directory_url=directory_url)
        artifacts.append(
            _bulk_artifact(
                data_entry,
                artifact_id="data",
                role="parcel_data",
                media_type="application/zip",
                archive_format="zip",
            )
        )
        if county is None:
            metadata_entries = client.fetch_directory(PARCEL_ROOT)
        else:
            metadata_entries = entries
        metadata_entry = _entry_by_name(
            metadata_entries,
            "MontanaCadastral_ParcelMetadata.xml",
            directory_url=(
                PARCEL_ROOT if county is None else directory_url
            ),
        )
        artifacts.append(
            _bulk_artifact(
                metadata_entry,
                artifact_id="parcel-metadata",
                role="schema_and_lineage_metadata",
                media_type="application/xml",
                archive_format=None,
            )
        )
        schema = {
            "format": (
                "ESRI Shapefile"
                if dataset_type == "parcel-shp"
                else "ESRI File Geodatabase"
            ),
            "metadata_url": metadata_entry.url,
            "parcel_join_key": "PARCELID",
            "identity_note": (
                "Preserve each feature occurrence and PARCELID; the live layer "
                "shows PARCELID is not populated on every feature."
            ),
        }
    else:
        directory_url = ORION_ROOT
        entries = client.fetch_directory(directory_url)
        filename = (
            f"COUNTY{county.prefix}.ZIP"
            if county is not None
            else "STATE-WIDE.ZIP"
        )
        data_entry = _entry_by_name(entries, filename, directory_url=directory_url)
        artifacts.append(
            _bulk_artifact(
                data_entry,
                artifact_id="data",
                role="orion_cama_sql_database",
                media_type="application/zip",
                archive_format="zip",
            )
        )
        for filename, artifact_id, role, media_type, archive_format in (
            (
                "BEGIN HERE.zip",
                "setup-and-data-dictionary",
                "database_loading_instructions_and_data_dictionary",
                "application/zip",
                "zip",
            ),
            (
                "ChangeLog.txt",
                "change-log",
                "publisher_change_log",
                "text/plain",
                None,
            ),
            (
                "CountyNumber.pdf",
                "county-number-crosswalk",
                "orion_county_prefix_crosswalk",
                "application/pdf",
                None,
            ),
            (
                "Orion_Diagram.pdf",
                "database-diagram",
                "database_schema_diagram",
                "application/pdf",
                None,
            ),
        ):
            entry = _entry_by_name(entries, filename, directory_url=directory_url)
            artifacts.append(
                _bulk_artifact(
                    entry,
                    artifact_id=artifact_id,
                    role=role,
                    media_type=media_type,
                    archive_format=archive_format,
                )
            )
        schema = {
            "format": "Microsoft SQL Server database archive",
            "publisher_runtime": "Microsoft SQL Server 2019 Express",
            "setup_and_data_dictionary_url": ORION_SETUP_URL,
            "database_diagram_url": ORION_DIAGRAM_URL,
            "county_crosswalk_url": ORION_COUNTY_NUMBER_URL,
            "county_archive_join": (
                "COUNTY{CountyPrefix}.ZIP, using the publisher's "
                "CountyNumber.pdf crosswalk"
            ),
        }
    release_id = (
        f"{dataset_type}:{scope.casefold()}:"
        f"{_release_marker(data_entry)}"
    )
    release = BulkReleaseMetadata(
        release_id=release_id,
        kind="snapshot",
        coverage={
            "scope": "county" if county is not None else "statewide",
            "county_name": county.name if county is not None else None,
            "county_geoid": county.geoid if county is not None else None,
            "orion_county_prefix": county.prefix if county is not None else None,
            "publisher_modified_local": data_entry.modified_local,
            "publisher_modified_timezone": "not_declared_in_directory_listing",
            "artifact_size": data_entry.size,
        },
    )
    return BulkDatasetManifest(
        source_id=SOURCE_ID,
        dataset_id=f"{dataset_type}:{scope}",
        release=release,
        artifacts=artifacts,
        schema=schema,
        metadata={
            "landing_url": LANDING_URL,
            "directory_url": directory_url,
            "rolling_alias": True,
            "release_identity_semantics": (
                "dataset, scope, exact filename, publisher-local modification "
                "marker, and listed byte size"
            ),
        },
    )


def discover_releases(
    client: MontanaCadastralClient,
) -> dict[str, Any]:
    """Discover current statewide aliases and county archive coverage."""
    root_entries = client.fetch_directory(BULK_ROOT)
    parcel_entries = client.fetch_directory(PARCEL_ROOT)
    orion_entries = client.fetch_directory(ORION_ROOT)
    statewide_names = (
        "MontanaCadastral_GDB.zip",
        "MontanaCadastral_SHP.zip",
    )
    statewide_parcels = [
        _entry_by_name(root_entries, name, directory_url=BULK_ROOT).to_dict()
        for name in statewide_names
    ]
    statewide_orion = _entry_by_name(
        orion_entries,
        "STATE-WIDE.ZIP",
        directory_url=ORION_ROOT,
    ).to_dict()
    county_directories = [
        entry
        for entry in parcel_entries
        if entry.is_directory and entry.name.casefold() != "statewide"
    ]
    orion_county_archives = [
        entry
        for entry in orion_entries
        if re.fullmatch(r"COUNTY(?:[1-9]|[1-4][0-9]|5[0-6])\.ZIP", entry.name)
    ]
    expected_directories = {county.directory for county in COUNTIES}
    observed_directories = {entry.name for entry in county_directories}
    observed_orion_prefixes = {
        int(re.fullmatch(r"COUNTY(\d+)\.ZIP", entry.name).group(1))
        for entry in orion_county_archives
    }
    record = {
        "source_id": SOURCE_ID,
        "record_type": "bulk_release_discovery",
        "statewide_parcel_artifacts": statewide_parcels,
        "statewide_orion_artifact": statewide_orion,
        "parcel_county_directory_count": len(county_directories),
        "orion_county_archive_count": len(orion_county_archives),
        "missing_parcel_county_directories": sorted(
            expected_directories - observed_directories
        ),
        "unexpected_parcel_county_directories": sorted(
            observed_directories - expected_directories
        ),
        "missing_orion_county_prefixes": sorted(
            set(COUNTY_BY_PREFIX) - observed_orion_prefixes
        ),
        "parcel_counties": [
            {
                "county_name": county.name,
                "county_geoid": county.geoid,
                "directory": county.directory,
                "orion_county_prefix": county.prefix,
                "abbreviation": county.abbreviation,
            }
            for county in COUNTIES
            if county.directory in observed_directories
        ],
        "orion_county_archives": [
            entry.to_dict() for entry in orion_county_archives
        ],
    }
    record["release_discovery_fingerprint"] = sha256_fingerprint(record)
    return record


def alternative_routes() -> list[dict[str, Any]]:
    return [
        {
            "name": "Montana Cadastral Application",
            "role": "interactive_parcel_and_property_research",
            "url": APPLICATION_URL,
            "relationship": "interactive_view_of_the_same_state_framework",
        },
        {
            "name": "MSL monthly parcel archives",
            "role": "statewide_and_county_geometry_and_selected_cama_bulk",
            "url": PARCEL_ROOT,
            "relationship": "bulk_complement_to_the_live_layer",
        },
        {
            "name": "Montana DOR ORION SQL databases",
            "role": "richer_county_and_statewide_cama_bulk",
            "url": ORION_ROOT,
            "relationship": "attribute_complement_to_selected_live_fields",
        },
        {
            "name": "MSL CadNSDI / PLSS",
            "role": "authoritative_public_land_survey_geometry",
            "url": PLSS_ROOT,
            "landing_url": CADNSDI_URL,
            "relationship": "boundary_and_legal_description_context",
        },
        {
            "name": "MSL Public Lands",
            "role": "public_land_ownership_context",
            "url": PUBLIC_LANDS_ROOT,
            "relationship": "ownership_classification_complement",
        },
        {
            "name": "MSL Conservation Easements",
            "role": "conservation_easement_geometry",
            "url": CONSERVATION_EASEMENTS_ROOT,
            "relationship": "land_constraint_and_interest_complement",
        },
        {
            "name": "MSL historic cadastral releases",
            "role": "prior_parcel_snapshots",
            "url": HISTORIC_ROOT,
            "relationship": "change_over_time_complement",
        },
        {
            "name": "County assessor, treasurer, and clerk/recorder systems",
            "role": "current_local_assessment_tax_and_recorded_instruments",
            "url": LANDING_URL,
            "relationship": (
                "local substitutes for newer assessment detail and deed, "
                "mortgage, lien, and instrument history absent from the "
                "statewide live projection"
            ),
        },
    ]


def _metadata_record(snapshot: SourceSnapshot) -> dict[str, Any]:
    fields = snapshot.layer_metadata.get("fields", [])
    return {
        "source_id": SOURCE_ID,
        "record_type": "source_metadata",
        "layer_id": snapshot.layer_metadata.get("id"),
        "layer_name": snapshot.layer_metadata.get("name"),
        "layer_url": LAYER_URL,
        "service_version": snapshot.layer_metadata.get("currentVersion"),
        "geometry_type": snapshot.layer_metadata.get("geometryType"),
        "spatial_reference": (
            snapshot.layer_metadata.get("extent", {}).get("spatialReference")
            if isinstance(snapshot.layer_metadata.get("extent"), Mapping)
            else None
        ),
        "supported_query_formats": snapshot.layer_metadata.get(
            "supportedQueryFormats"
        ),
        "capabilities": snapshot.layer_metadata.get("capabilities"),
        "field_definitions": fields,
        "identity_contract": {
            "source_occurrence_keys": ["GlobalID", "OBJECTID"],
            "transport_cursor_key": "OBJECTID",
            "parcel_join_key": "PARCELID",
            "parcel_join_key_complete": (
                snapshot.features_with_parcel_id == snapshot.total_features
            ),
            "property_attribute_keys": ["PropertyID", "AssessmentCode"],
            "county_jurisdiction_key": "county_geoid",
            "county_crosswalk": (
                "ORION COUNTYCD/CountyPrefix is mapped explicitly to Census "
                "county GEOID and is not itself a Census FIPS code."
            ),
        },
        "source_snapshot": _snapshot_record(snapshot),
        "official_release_and_update_map": MONTHLY_UPDATE_MAP_URL,
    }


def _county_records(
    rows: Sequence[Mapping[str, Any]],
    snapshot: SourceSnapshot,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    total = 0
    observed_prefixes: set[int] = set()
    for row in rows:
        prefix = row.get("COUNTYCD")
        count = row.get("feature_count")
        if (
            isinstance(prefix, bool)
            or not isinstance(prefix, int)
            or prefix not in COUNTY_BY_PREFIX
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            raise SourceSchemaError(
                "MSL county-statistics row is invalid",
                url=QUERY_URL,
                details={"row": dict(row)},
            )
        county = COUNTY_BY_PREFIX[prefix]
        observed_prefixes.add(prefix)
        total += count
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_type": "county_coverage",
                "county_name": _clean_text(row.get("CountyName")),
                "county_abbreviation": _clean_text(row.get("CountyAbbr")),
                "county_geoid": county.geoid,
                "orion_county_prefix": prefix,
                "parcel_directory": county.directory,
                "feature_count": count,
                "parcel_bulk_url": f"{PARCEL_ROOT}{county.directory}/",
                "orion_bulk_url": f"{ORION_ROOT}COUNTY{prefix}.ZIP",
            }
        )
    if total != snapshot.total_features:
        raise SourceSchemaError(
            "MSL county groups do not reconcile to the statewide count",
            url=QUERY_URL,
            details={
                "county_group_total": total,
                "statewide_total": snapshot.total_features,
            },
        )
    if observed_prefixes != set(COUNTY_BY_PREFIX):
        raise SourceSchemaError(
            "MSL county groups no longer match the 56-county crosswalk",
            url=QUERY_URL,
            details={
                "missing": sorted(set(COUNTY_BY_PREFIX) - observed_prefixes),
                "unexpected": sorted(observed_prefixes - set(COUNTY_BY_PREFIX)),
            },
        )
    return records


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for name in (
        "identifier",
        "name",
        "query",
        "object_id",
        "owner",
        "address",
        "parcel_id",
        "property_id",
        "county",
        "tax_year",
        "longitude",
        "latitude",
        "geometry",
        "dataset_type",
        "destination",
        "range_bytes",
        "max_download_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = value
    return parameters


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    requested_limit = (
        getattr(args, "limit", None)
        if args.command
        in {"parcel", "owner", "address", "objectid", "point", "search", "probe"}
        else None
    )
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
        ),
    )


def _client_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "page_size": getattr(args, "page_size", DEFAULT_PAGE_SIZE),
        "timeout": getattr(args, "timeout", DEFAULT_TIMEOUT),
        "minimum_interval": getattr(
            args,
            "minimum_interval",
            DEFAULT_MINIMUM_INTERVAL,
        ),
        "retry_attempts": getattr(args, "retry_attempts", 3),
    }


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=getattr(args, "timeout", 60.0),
        max_attempts=getattr(args, "retry_attempts", 3),
        chunk_size=getattr(args, "chunk_size", 1024 * 1024),
    )


def _data_artifact(manifest: BulkDatasetManifest) -> BulkArtifact:
    matches = [
        artifact for artifact in manifest.artifacts if artifact.artifact_id == "data"
    ]
    if len(matches) != 1:
        raise MontanaCadastralError(
            "manifest_data_artifact",
            "bulk manifest does not contain one data artifact",
            status=ResultStatus.SOURCE_CHANGED,
            category="bulk_source",
        )
    return matches[0]


def execute(
    args: argparse.Namespace,
    *,
    client: MontanaCadastralClient | None = None,
    bulk_client: BulkTransferClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    source_client = client
    try:
        if args.command == "alternatives":
            result = PublicRecordsResult.success(query, alternative_routes())
        else:
            source_client = source_client or MontanaCadastralClient(
                **_client_args(args)
            )
            if args.command == "metadata":
                result = PublicRecordsResult.success(
                    query,
                    [_metadata_record(source_client.fetch_snapshot())],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "counties":
                snapshot = source_client.fetch_snapshot()
                rows = source_client.fetch_county_statistics()
                result = PublicRecordsResult.success(
                    query,
                    _county_records(rows, snapshot),
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "releases":
                result = PublicRecordsResult.success(
                    query,
                    [discover_releases(source_client)],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command in {
                "manifest",
                "artifact-probe",
                "dry-run",
                "download",
            }:
                county = _county_from_selector(getattr(args, "county", None))
                manifest = build_bulk_manifest(
                    source_client,
                    dataset_type=args.dataset_type,
                    county=county,
                )
                if args.command == "manifest":
                    records = [manifest.to_dict()]
                    raw_refs: Sequence[str] = ()
                else:
                    artifact = _data_artifact(manifest)
                    transfer = bulk_client or _bulk_client(args)
                    if args.command == "artifact-probe":
                        records = [
                            {
                                "manifest": manifest.to_dict(),
                                "selected_artifact": artifact.to_dict(),
                                "probe": transfer.probe(
                                    artifact,
                                    sample_bytes=args.range_bytes,
                                ).to_dict(),
                            }
                        ]
                        raw_refs = ()
                    elif args.command == "dry-run" or getattr(
                        args, "dry_run", False
                    ):
                        destination = Path(args.destination)
                        if destination.exists() and destination.is_dir():
                            destination = destination / artifact.filename
                        records = [
                            {
                                "manifest": manifest.to_dict(),
                                "selected_artifact": artifact.to_dict(),
                                "download": {
                                    "status": "planned",
                                    "destination": str(destination),
                                    "resume": args.resume,
                                    "max_bytes": args.max_download_bytes,
                                },
                            }
                        ]
                        raw_refs = ()
                    else:
                        if args.expected_sha256:
                            artifact = replace(
                                artifact,
                                expected_sha256=args.expected_sha256,
                            )
                        download = transfer.download(
                            artifact,
                            args.destination,
                            resume=args.resume,
                            max_bytes=args.max_download_bytes,
                        )
                        records = [
                            {
                                "manifest": manifest.to_dict(),
                                "selected_artifact": artifact.to_dict(),
                                "download": download.to_dict(),
                                "archive": inspect_zip(download.path).to_dict(),
                            }
                        ]
                        raw_refs = (download.path,)
                result = PublicRecordsResult.success(
                    query,
                    records,
                    raw_artifact_refs=raw_refs,
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "count":
                selection = _selection_from_args(args)
                snapshot = source_client.fetch_snapshot()
                count = source_client.fetch_count(
                    selection.where,
                    selection.spatial_parameters,
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "source_id": SOURCE_ID,
                            "record_type": "query_count",
                            "count": count,
                            "where": selection.where,
                            "spatial_parameters": dict(
                                selection.spatial_parameters
                            ),
                            "source_snapshot": _snapshot_record(snapshot),
                        }
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                selection = _selection_from_args(args)
                limit = 1 if args.command == "probe" else args.limit
                features, next_cursor, snapshot, total, remaining = _traverse(
                    source_client,
                    operation=args.command,
                    selection=selection,
                    limit=limit,
                    cursor=getattr(args, "cursor", None),
                    return_geometry=bool(args.geometry),
                )
                records = [
                    _normalize_feature(
                        feature,
                        snapshot=snapshot,
                        geometry_requested=bool(args.geometry),
                    )
                    for feature in features
                ]
                records = [
                    {
                        **record,
                        "query_match_context": {
                            "reported_total_matches": total,
                            "reported_remaining_matches_at_start": remaining,
                        },
                    }
                    for record in records
                ]
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
    except MontanaCadastralError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (KeyError, OSError, TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="montana_cadastral_operation_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
        )
    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    if log_results:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Montana cadastral {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Montana cadastral {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command == "alternatives":
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "metadata":
            snapshot = record["source_snapshot"]
            print(
                f"  {record['layer_name']} | "
                f"{snapshot['total_features']} features"
            )
        elif args.command == "counties":
            print(
                f"  {record['orion_county_prefix']:02d} | "
                f"{record['county_name']} | {record['feature_count']}"
            )
        elif args.command == "releases":
            print(
                f"  {record['parcel_county_directory_count']} parcel counties | "
                f"{record['orion_county_archive_count']} ORION counties"
            )
        elif args.command == "count":
            print(f"  {record['count']} | {record['where']}")
        elif args.command in {
            "manifest",
            "artifact-probe",
            "dry-run",
            "download",
        }:
            manifest = record.get("manifest", record)
            print(f"  {manifest['release']['release_id']}")
        else:
            print(
                f"  {record['identity']['parcel_id'] or '?'} | "
                f"{record['jurisdiction']['county_name'] or '?'} | "
                f"{record['owner']['name'] or '?'}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--retry-attempts", type=_positive_int, default=3)


def _add_query_args(
    parser: argparse.ArgumentParser,
    *,
    geometry_default: bool = False,
) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=DEFAULT_LIMIT,
        help="Maximum records returned in this invocation",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation cursor returned by a prior matching query",
    )
    parser.add_argument(
        "--geometry",
        action=argparse.BooleanOptionalAction,
        default=geometry_default,
        help="Return source polygon geometry in EPSG:4326",
    )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
        help="Transport page size, bounded by live layer metadata",
    )
    _add_connection_args(parser)
    add_output_args(parser)


def _add_optional_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--county",
        help=(
            "County name, abbreviation, ORION prefix, or Census "
            "county GEOID/FIPS suffix"
        ),
    )
    parser.add_argument("--tax-year", type=_positive_int)


def _add_bulk_selectors(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dataset",
        dest="dataset_type",
        choices=DATASET_TYPES,
        required=True,
    )
    parser.add_argument(
        "--county",
        help=(
            "Omit for statewide; otherwise county name, abbreviation, ORION "
            "prefix, or Census county GEOID/FIPS suffix"
        ),
    )


def _add_transfer_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--destination", required=True)
    parser.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
    )
    parser.set_defaults(resume=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--max-download-bytes", type=_positive_int)
    parser.add_argument("--chunk-size", type=_positive_int, default=1024 * 1024)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query live Montana parcels and discover/transfer official "
            "cadastral releases"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    metadata = sub.add_parser("metadata", help="Inspect the live layer contract")
    _add_connection_args(metadata)
    add_output_args(metadata)

    counties = sub.add_parser(
        "counties",
        help="List live feature counts and bulk routes for all counties",
    )
    _add_connection_args(counties)
    add_output_args(counties)

    alternatives = sub.add_parser(
        "alternatives",
        help="List official substitutes and complementary datasets",
    )
    add_output_args(alternatives)

    releases = sub.add_parser(
        "releases",
        help="Discover current statewide aliases and county coverage",
    )
    _add_connection_args(releases)
    add_output_args(releases)

    manifest = sub.add_parser(
        "manifest",
        help="Build an exact current bulk manifest",
    )
    _add_bulk_selectors(manifest)
    _add_connection_args(manifest)
    add_output_args(manifest)

    artifact_probe = sub.add_parser(
        "artifact-probe",
        help="Make a bounded metadata and leading-range probe of one artifact",
    )
    _add_bulk_selectors(artifact_probe)
    artifact_probe.add_argument("--range-bytes", type=int, default=4096)
    _add_connection_args(artifact_probe)
    add_output_args(artifact_probe)

    dry_run = sub.add_parser(
        "dry-run",
        help="Resolve an artifact and emit its download plan",
    )
    _add_bulk_selectors(dry_run)
    _add_transfer_args(dry_run)
    _add_connection_args(dry_run)
    add_output_args(dry_run)

    download = sub.add_parser(
        "download",
        help="Download, fingerprint, and inspect one exact current artifact",
    )
    _add_bulk_selectors(download)
    _add_transfer_args(download)
    download.add_argument("--dry-run", action="store_true")
    _add_connection_args(download)
    add_output_args(download)

    parcel = sub.add_parser("parcel", help="Find an exact PARCELID/geocode")
    parcel.add_argument("identifier")
    _add_optional_filters(parcel)
    _add_query_args(parcel)

    owner = sub.add_parser("owner", help="Search owner, DBA, and care-of names")
    owner.add_argument("name")
    _add_optional_filters(owner)
    _add_query_args(owner)

    address = sub.add_parser("address", help="Search the parcel site address")
    address.add_argument("query")
    _add_optional_filters(address)
    _add_query_args(address)

    objectid = sub.add_parser("objectid", help="Fetch one ArcGIS OBJECTID")
    objectid.add_argument("object_id", type=_positive_int)
    _add_query_args(objectid)

    point = sub.add_parser("point", help="Find parcels intersecting a WGS84 point")
    point.add_argument("longitude", type=float)
    point.add_argument("latitude", type=float)
    _add_optional_filters(point)
    _add_query_args(point, geometry_default=True)

    search = sub.add_parser(
        "search",
        help="Combine parcel, property, owner, address, county, and year filters",
    )
    search.add_argument(
        "--query",
        help="Search parcel, account, owner, DBA, care-of, and site-address fields",
    )
    search.add_argument("--owner")
    search.add_argument("--address")
    search.add_argument("--parcel-id")
    search.add_argument("--property-id")
    _add_optional_filters(search)
    _add_query_args(search)

    count = sub.add_parser("count", help="Count records matching combined filters")
    count.add_argument(
        "--query",
        help="Count matches across parcel, account, owner, and site-address fields",
    )
    count.add_argument("--owner")
    count.add_argument("--address")
    count.add_argument("--parcel-id")
    count.add_argument("--property-id")
    _add_optional_filters(count)
    _add_connection_args(count)
    add_output_args(count)

    probe = sub.add_parser(
        "probe",
        help="Run a bounded live schema, query, cursor, and geometry probe",
    )
    _add_query_args(probe, geometry_default=True)
    probe.set_defaults(limit=1)
    return parser


def _validate_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "range_bytes", 0) < 0:
        parser.error("--range-bytes must not be negative")
    if args.command == "point":
        if not -180 <= args.longitude <= 180:
            parser.error("longitude must be between -180 and 180")
        if not -90 <= args.latitude <= 90:
            parser.error("latitude must be between -90 and 90")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
