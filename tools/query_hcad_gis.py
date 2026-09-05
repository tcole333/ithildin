#!/usr/bin/env python3
"""Query and acquire Harris County HCAD parcel GIS data.

HCAD publishes current GIS archives and historical October parcel snapshots
through public JSON manifests. The current parcel archive is a File
Geodatabase. Harris County also republishes the HCAD parcel dataset through an
anonymous ArcGIS MapServer, which provides a machine-queryable representation
with parcel geometry, owner/address snapshots, values, and legal-description
fields.

Examples:
    uv run python tools/query_hcad_gis.py releases
    uv run python tools/query_hcad_gis.py manifest
    uv run python tools/query_hcad_gis.py probe
    uv run python tools/query_hcad_gis.py download \
        --destination /tmp/hcad-parcels.zip
    uv run python tools/query_hcad_gis.py search "WOODSMAN" --field address
    uv run python tools/query_hcad_gis.py account 1144740190749 --geometry
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

try:
    from tools import oregon_arcgis_keyset as arcgis_keyset
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        ArchiveSafetyPolicy,
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        inspect_zip,
    )
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        acquisition_result_status,
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
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceSchemaError,
        _BaseJSONClient,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    import oregon_arcgis_keyset as arcgis_keyset
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        ArchiveSafetyPolicy,
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        inspect_zip,
    )
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        acquisition_result_status,
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
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceSchemaError,
        _BaseJSONClient,
        failure_result,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-tx-harris-hcad-gis"
COUNTY_GEOID = "48201"
SOURCE_PAGE = "https://hcad.org/pdata/pdata-gis-downloads.html/"
ACTION_ROOT = "https://hcad.org/actions/hcad-pdata/default"
LAST_UPDATE_ENDPOINT = f"{ACTION_ROOT}/get-gis-last-update"
PUBLIC_ENDPOINT = f"{ACTION_ROOT}/get-gis-public"
FILES_ENDPOINT = f"{ACTION_ROOT}/get-gis-files"
PRIOR_YEAR_ENDPOINT = f"{ACTION_ROOT}/get-gis-prior-year"
SCHEMA_URL = "https://hcad.org/assets/uploads/pdf/resources/2026/GIS-ReadMeV2-2.pdf"
MAPSERVER_LAYER_URL = (
    "https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer/0"
)
TXGIO_SOURCE_URL = "https://gio.texas.gov/stratmap/land-parcels.html"
HCAD_CAMA_SOURCE_URL = "https://hcad.org/pdata/pdata-property-downloads.html/"
HCAD_PARCEL_VIEWER_URL = "https://arcweb.hcad.org/parcel-viewer-v2.0/"

DEFAULT_TIMEOUT = 60.0
DEFAULT_MINIMUM_INTERVAL = 0.15
DEFAULT_PAGE_SIZE = 250
DEFAULT_LIMIT = 25

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="HCAD Parcel GIS",
    source_role="parcel_geometry_assessment_snapshot_bulk_and_map_service",
    base_url=SOURCE_PAGE,
    dataset_id="HCAD-GIS-Parcels",
    metadata={
        "record_publisher": "Harris Central Appraisal District",
        "bulk_transport": "HCAD public JSON manifests and download host",
        "query_transport": "Harris County GIS ArcGIS MapServer",
        "release_scope": "Harris County",
        "bulk_refresh": "quarterly",
        "mapserver_representation": "HCAD parcel data on an official county host",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-tx-harris",
    name="Harris County, Texas",
    state_code="TX",
    county_fips=COUNTY_GEOID,
    locality="Harris County",
)

MAP_REQUIRED_FIELDS = (
    "OBJECTID",
    "LOWPARCELID",
    "HCAD_NUM",
    "acct_num",
    "tax_year",
    "owner_name_1",
    "mail_addr_1",
    "mail_city",
    "mail_state",
    "mail_zip",
    "site_str_num",
    "site_str_name",
    "site_city",
    "site_county",
    "site_zip",
    "land_value",
    "impr_value",
    "total_appraised_val",
    "total_market_val",
    "legal_dscr_1",
    "GlobalID",
)
MAP_MANIFEST = arcgis_keyset.ArcGISLayerManifest(
    source_id=SOURCE_ID,
    name="Harris County GIS HCAD Parcels",
    layer_url=MAPSERVER_LAYER_URL,
    layer_id=0,
    service_item_id=None,
    expected_layer_name="HCAD Parcels",
    object_id_field="OBJECTID",
    required_fields=MAP_REQUIRED_FIELDS,
    source_crs_wkids=(102740, 2278),
    record_kind="parcel_assessment_geometry_snapshot",
    publisher="Harris Central Appraisal District via Harris County GIS",
)

ENDPOINT_SCHEMA = {
    "last_update": [{"lastUpdatedDate": "Month DD, YYYY"}],
    "artifacts": [
        {
            "taxYear": "scope_label",
            "category": "GIS",
            "subCategory": "artifact_group",
            "downloadLinkText": "artifact_label",
            "description": "artifact_description",
            "downloadLink": "https_download_url",
            "filename": "zip_filename",
        }
    ],
}
ENDPOINT_SCHEMA_FINGERPRINT = sha256_fingerprint(ENDPOINT_SCHEMA)

SEARCH_FIELDS = {
    "owner": ("owner_name_1", "owner_name_2", "owner_name_3"),
    "address": (
        "mail_addr_1",
        "mail_addr_2",
        "mail_city",
        "mail_state",
        "mail_zip",
        "site_str_pfx",
        "site_str_num_sfx",
        "site_str_name",
        "site_str_sfx",
        "site_str_sfx_dir",
        "site_city",
        "site_county",
        "site_zip",
    ),
    "legal": (
        "legal_dscr_1",
        "legal_dscr_2",
        "legal_dscr_3",
        "legal_dscr_4",
        "BLK_NUM",
        "LOT_NUM",
    ),
    "account": ("HCAD_NUM", "acct_num", "LOWPARCELID"),
}
SEARCH_FIELDS["any"] = tuple(
    dict.fromkeys(
        field
        for group in ("owner", "address", "legal", "account")
        for field in SEARCH_FIELDS[group]
    )
)

PRIOR_FILENAME_RE = re.compile(r"^Parcels_(?P<year>\d{4})_Oct\.zip$", re.I)


class HCADGISError(RuntimeError):
    """Source, selection, or local-artifact failure with envelope semantics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        category: str = "source_schema",
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


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _require_text(value: Any, field: str, *, url: str) -> str:
    text = _clean_text(value)
    if text is None:
        raise SourceSchemaError(
            f"HCAD GIS response is missing {field}",
            url=url,
            details={"field": field},
        )
    return text


def _expect_rows(payload: Any, *, url: str) -> list[Mapping[str, Any]]:
    if not isinstance(payload, list):
        raise SourceSchemaError(
            "HCAD GIS response is not a JSON array",
            url=url,
            details={"observed_type": type(payload).__name__},
        )
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(payload):
        if not isinstance(row, Mapping):
            raise SourceSchemaError(
                "HCAD GIS response contains a non-object row",
                url=url,
                details={"row_index": index},
            )
        rows.append(row)
    return rows


def _artifact_row(
    row: Mapping[str, Any],
    *,
    endpoint: str,
    role: str,
) -> dict[str, Any]:
    filename = _require_text(row.get("filename"), "filename", url=endpoint)
    url = _require_text(row.get("downloadLink"), "downloadLink", url=endpoint)
    parsed = urlsplit(url)
    if (
        parsed.scheme.casefold() != "https"
        or parsed.hostname != "download.hcad.org"
        or not parsed.path.startswith("/data/GIS/")
        or not filename.casefold().endswith(".zip")
        or PurePosixPath(parsed.path).name.casefold() != filename.casefold()
    ):
        raise SourceSchemaError(
            "HCAD GIS artifact URL or filename changed",
            url=endpoint,
            details={"filename": filename, "download_url": url},
        )
    tax_year = _require_text(row.get("taxYear"), "taxYear", url=endpoint)
    category = _require_text(row.get("category"), "category", url=endpoint)
    if category.casefold() != "gis":
        raise SourceSchemaError(
            "HCAD GIS artifact category changed",
            url=endpoint,
            details={"category": category, "filename": filename},
        )
    record = {
        "artifact_id": filename.removesuffix(".zip").casefold(),
        "filename": filename,
        "url": url,
        "label": _clean_text(row.get("downloadLinkText")) or filename,
        "description": _clean_text(row.get("description")),
        "native_tax_year": tax_year,
        "category": category,
        "sub_category": _clean_text(row.get("subCategory")),
        "artifact_role": role,
    }
    if role == "historical_parcel_snapshot":
        match = PRIOR_FILENAME_RE.fullmatch(filename)
        if match is None:
            raise SourceSchemaError(
                "HCAD prior-year parcel filename changed",
                url=endpoint,
                details={"filename": filename},
            )
        record["snapshot_year"] = int(match.group("year"))
        record["effective_at"] = f"{match.group('year')}-10"
        record["date_precision"] = "month"
    return record


class HCADGISManifestClient(_BaseJSONClient):
    """Client for the JSON endpoints behind HCAD's GIS download page."""

    def last_update(self) -> dict[str, Any]:
        rows = _expect_rows(
            self._request_json(LAST_UPDATE_ENDPOINT, params={}),
            url=LAST_UPDATE_ENDPOINT,
        )
        if len(rows) != 1:
            raise SourceSchemaError(
                "HCAD GIS last-update response must contain one row",
                url=LAST_UPDATE_ENDPOINT,
                details={"row_count": len(rows)},
            )
        native = _require_text(
            rows[0].get("lastUpdatedDate"),
            "lastUpdatedDate",
            url=LAST_UPDATE_ENDPOINT,
        )
        try:
            effective = datetime.strptime(native, "%B %d, %Y").date().isoformat()
        except ValueError as error:
            raise SourceSchemaError(
                "HCAD GIS last-update date format changed",
                url=LAST_UPDATE_ENDPOINT,
                details={"value": native},
            ) from error
        return {
            "last_updated": effective,
            "native_last_updated": native,
            "source_manifest_schema_fingerprint": ENDPOINT_SCHEMA_FINGERPRINT,
        }

    def _artifacts(
        self,
        endpoint: str,
        *,
        role: str,
    ) -> list[dict[str, Any]]:
        rows = _expect_rows(
            self._request_json(endpoint, params={}),
            url=endpoint,
        )
        records = [_artifact_row(row, endpoint=endpoint, role=role) for row in rows]
        filenames = [record["filename"].casefold() for record in records]
        if len(filenames) != len(set(filenames)):
            raise SourceSchemaError(
                "HCAD GIS manifest contains duplicate filenames",
                url=endpoint,
                details={"filenames": filenames},
            )
        return records

    def current_components(self) -> list[dict[str, Any]]:
        return self._artifacts(
            FILES_ENDPOINT,
            role="current_component",
        )

    def current_bundle(self) -> list[dict[str, Any]]:
        records = self._artifacts(
            PUBLIC_ENDPOINT,
            role="current_combined_bundle",
        )
        if len(records) != 1:
            raise SourceSchemaError(
                "HCAD GIS combined-bundle response must contain one row",
                url=PUBLIC_ENDPOINT,
                details={"row_count": len(records)},
            )
        return records

    def historical_parcels(self) -> list[dict[str, Any]]:
        records = self._artifacts(
            PRIOR_YEAR_ENDPOINT,
            role="historical_parcel_snapshot",
        )
        years = [int(record["snapshot_year"]) for record in records]
        if len(years) != len(set(years)):
            raise SourceSchemaError(
                "HCAD GIS prior-year manifest contains duplicate years",
                url=PRIOR_YEAR_ENDPOINT,
                details={"years": years},
            )
        return sorted(
            records,
            key=lambda record: int(record["snapshot_year"]),
            reverse=True,
        )


def _manifest_client(args: argparse.Namespace) -> HCADGISManifestClient:
    return HCADGISManifestClient(
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
    )


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=getattr(args, "chunk_size", 1024 * 1024),
    )


def _arcgis_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> arcgis_keyset.BoundedArcGISClient:
    limits = access_contract.get("limits") or {}
    page_size = min(
        args.page_size,
        int(limits.get("maximum_page_size") or args.page_size),
    )
    minimum_interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return arcgis_keyset.BoundedArcGISClient(
        MAP_MANIFEST,
        page_size=page_size,
        timeout=args.timeout,
        minimum_interval=minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def release_inventory(
    client: HCADGISManifestClient | Any,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    update = client.last_update()
    components = client.current_components()
    bundle = client.current_bundle()
    historical = client.historical_parcels()
    current_artifacts = [*components, *bundle]
    current_release_id = f"current:{update['last_updated']}"
    releases = [
        {
            "canonical_ref": canonical_property_ref(
                SOURCE_ID,
                COUNTY_GEOID,
                "bulk_release",
                current_release_id,
            ),
            "release_id": current_release_id,
            "release_kind": "rolling_snapshot",
            "effective_at": update["last_updated"],
            "date_precision": "day",
            "component_artifact_count": len(components),
            "combined_bundle_count": len(bundle),
            "artifact_count": len(current_artifacts),
            "source_manifest_schema_fingerprint": (ENDPOINT_SCHEMA_FINGERPRINT),
            "source_url": SOURCE_PAGE,
        }
    ]
    by_release = {current_release_id: current_artifacts}
    for artifact in historical:
        year = int(artifact["snapshot_year"])
        release_id = f"parcels:{year}-10"
        releases.append(
            {
                "canonical_ref": canonical_property_ref(
                    SOURCE_ID,
                    COUNTY_GEOID,
                    "bulk_release",
                    release_id,
                ),
                "release_id": release_id,
                "release_kind": "historical_snapshot",
                "snapshot_year": year,
                "effective_at": artifact["effective_at"],
                "date_precision": artifact["date_precision"],
                "artifact_count": 1,
                "source_manifest_schema_fingerprint": (ENDPOINT_SCHEMA_FINGERPRINT),
                "source_url": SOURCE_PAGE,
            }
        )
        by_release[release_id] = [artifact]
    return releases, by_release


def _selected_release(
    releases: Sequence[Mapping[str, Any]],
    *,
    year: int | None,
) -> Mapping[str, Any] | None:
    if year is None:
        return next(
            (
                release
                for release in releases
                if release.get("release_kind") == "rolling_snapshot"
            ),
            None,
        )
    return next(
        (release for release in releases if release.get("snapshot_year") == year),
        None,
    )


def normalize_manifest(
    release: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_artifacts = [
        BulkArtifact(
            artifact_id=str(artifact["artifact_id"]),
            url=str(artifact["url"]),
            filename=str(artifact["filename"]),
            media_type="application/zip",
            archive_format="zip",
            metadata={
                key: artifact.get(key)
                for key in (
                    "label",
                    "description",
                    "native_tax_year",
                    "category",
                    "sub_category",
                    "artifact_role",
                    "snapshot_year",
                    "effective_at",
                    "date_precision",
                )
                if artifact.get(key) is not None
            },
        )
        for artifact in artifacts
    ]
    release_id = str(release["release_id"])
    manifest = BulkDatasetManifest(
        source_id=SOURCE_ID,
        dataset_id="HCAD-GIS",
        release=BulkReleaseMetadata(
            release_id=release_id,
            kind="snapshot",
            effective_at=str(release["effective_at"]),
            coverage={
                "state": "Texas",
                "county": "Harris",
                "county_geoid": COUNTY_GEOID,
                "snapshot_year": release.get("snapshot_year"),
                "date_precision": release.get("date_precision"),
                "artifact_roles": sorted(
                    {str(artifact["artifact_role"]) for artifact in artifacts}
                ),
            },
        ),
        artifacts=normalized_artifacts,
        schema={
            "schema_reference": SCHEMA_URL,
            "projection": {
                "epsg": 2278,
                "wkid": 102740,
                "name": "NAD83 Texas South Central (US feet)",
            },
            "parcel_join_field": "HCAD_NUM",
            "representation": (
                "published ZIPs may contain a shapefile or File Geodatabase"
            ),
        },
        metadata={
            "source_page": SOURCE_PAGE,
            "manifest_endpoints": {
                "last_update": LAST_UPDATE_ENDPOINT,
                "current_components": FILES_ENDPOINT,
                "current_bundle": PUBLIC_ENDPOINT,
                "historical_parcels": PRIOR_YEAR_ENDPOINT,
            },
            "source_manifest_schema_fingerprint": (ENDPOINT_SCHEMA_FINGERPRINT),
            "combined_bundle_is_acquisition_redundancy": True,
        },
    )
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "bulk_release",
            release_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "bulk_release_manifest",
        "release_id": release_id,
        "release_kind": release["release_kind"],
        "effective_at": release["effective_at"],
        "date_precision": release["date_precision"],
        "manifest": manifest.to_dict(),
        "source_url": SOURCE_PAGE,
    }


def _select_artifacts(
    artifacts: Sequence[Mapping[str, Any]],
    selector: str | None,
    *,
    single_default: bool,
) -> list[Mapping[str, Any]]:
    if selector:
        key = selector.strip().casefold()
        selected = [
            artifact
            for artifact in artifacts
            if key
            in {
                str(artifact["artifact_id"]).casefold(),
                str(artifact["filename"]).casefold(),
                str(artifact.get("label") or "").casefold(),
            }
        ]
        if not selected:
            return []
        return selected
    if not single_default:
        return list(artifacts)
    parcel = [
        artifact
        for artifact in artifacts
        if str(artifact["filename"]).casefold() == "parcels.zip"
    ]
    return parcel or (list(artifacts) if len(artifacts) == 1 else [])


def _manifest_artifact(record: Mapping[str, Any]) -> BulkArtifact:
    artifacts = record["manifest"]["artifacts"]
    if len(artifacts) != 1:
        raise HCADGISError(
            "hcad_gis_artifact_selection_required",
            "Select one HCAD GIS artifact for this operation",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
            details={"available": [artifact.get("filename") for artifact in artifacts]},
        )
    artifact = artifacts[0]
    return BulkArtifact(
        artifact_id=artifact["artifact_id"],
        url=artifact["url"],
        filename=artifact["filename"],
        media_type=artifact.get("media_type"),
        archive_format=artifact.get("archive_format"),
        expected_size=artifact.get("expected_size"),
        expected_sha256=artifact.get("expected_sha256"),
        etag=artifact.get("etag"),
        last_modified=artifact.get("last_modified"),
        metadata=artifact.get("metadata") or {},
    )


def _archive_policy(args: argparse.Namespace) -> ArchiveSafetyPolicy:
    return ArchiveSafetyPolicy(
        max_members=getattr(args, "max_archive_members", None),
        max_total_uncompressed_bytes=getattr(
            args,
            "max_uncompressed_bytes",
            None,
        ),
        max_member_uncompressed_bytes=getattr(
            args,
            "max_member_uncompressed_bytes",
            None,
        ),
        max_compression_ratio=getattr(
            args,
            "max_compression_ratio",
            None,
        ),
    )


def inspect_local_artifact(
    path: Path | str,
    *,
    policy: ArchiveSafetyPolicy | None = None,
) -> dict[str, Any]:
    artifact_path = Path(path).expanduser().resolve()
    if not artifact_path.is_file():
        raise HCADGISError(
            "hcad_gis_artifact_missing",
            "HCAD GIS artifact does not exist",
            status=ResultStatus.UNAVAILABLE,
            category="local_artifact",
            details={"path": str(artifact_path)},
        )
    archive = inspect_zip(artifact_path, policy=policy)
    with zipfile.ZipFile(artifact_path) as source:
        filenames = [
            member.filename for member in source.infolist() if not member.is_dir()
        ]
    gdb_roots = sorted(
        {
            "/".join(PurePosixPath(filename).parts[: index + 1])
            for filename in filenames
            for index, part in enumerate(PurePosixPath(filename).parts)
            if part.casefold().endswith(".gdb")
        }
    )
    shapefile_stems = sorted(
        {
            str(PurePosixPath(filename).with_suffix(""))
            for filename in filenames
            if filename.casefold().endswith(".shp")
        }
    )
    if not gdb_roots and not shapefile_stems:
        raise HCADGISError(
            "hcad_gis_representation_changed",
            "HCAD GIS archive contains neither a File Geodatabase nor shapefile",
            details={"path": str(artifact_path)},
        )
    representation = (
        "mixed"
        if gdb_roots and shapefile_stems
        else ("file_geodatabase" if gdb_roots else "shapefile")
    )
    inspection = {
        "path": str(artifact_path),
        "artifact_sha256": archive.archive_sha256,
        "archive": archive.to_dict(),
        "representation": representation,
        "file_geodatabases": gdb_roots,
        "shapefile_datasets": shapefile_stems,
        "published_projection": {
            "epsg": 2278,
            "wkid": 102740,
            "name": "NAD83 Texas South Central (US feet)",
        },
        "parcel_join_field": "HCAD_NUM",
        "record_query_route": MAPSERVER_LAYER_URL,
        "schema_reference": SCHEMA_URL,
    }
    inspection["representation_fingerprint"] = sha256_fingerprint(
        {
            "representation": representation,
            "file_geodatabases": gdb_roots,
            "shapefile_datasets": shapefile_stems,
            "member_suffixes": sorted(
                {PurePosixPath(filename).suffix.casefold() for filename in filenames}
            ),
        }
    )
    return inspection


def _query_text(value: str) -> str:
    text = _clean_text(value)
    if text is None:
        raise HCADGISError(
            "hcad_gis_query_empty",
            "HCAD GIS query must not be empty",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    return text


def _sql_text(value: str) -> str:
    return value.replace("'", "''").upper()


def _string_condition(field: str, value: str, match: str) -> str:
    literal = _sql_text(value)
    if match == "exact":
        return f"UPPER({field}) = '{literal}'"
    if match == "prefix":
        return f"UPPER({field}) LIKE '{literal}%'"
    return f"UPPER({field}) LIKE '%{literal}%'"


def _where(field: str, query: str, match: str) -> str:
    text = _query_text(query)
    if field == "account":
        identifier = re.sub(r"[^A-Za-z0-9]", "", text)
        if not identifier:
            raise HCADGISError(
                "hcad_gis_query_empty",
                "HCAD account query must contain a letter or number",
                status=ResultStatus.UNAVAILABLE,
                category="query_selection",
            )
        return " OR ".join(
            _string_condition(native, identifier, "exact")
            for native in SEARCH_FIELDS["account"]
        )
    fields = SEARCH_FIELDS[field]
    if match == "exact" or len(text.split()) == 1:
        return " OR ".join(_string_condition(native, text, match) for native in fields)
    term_conditions = []
    for term in text.split():
        clauses = [_string_condition(native, term, match) for native in fields]
        if field in {"address", "any"} and term.isdigit():
            clauses.append(f"site_str_num = {int(term)}")
        term_conditions.append(f"({' OR '.join(clauses)})")
    return " AND ".join(term_conditions)


def _epoch_date(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _clean_text(value)
    try:
        return (
            datetime.fromtimestamp(
                float(value) / 1000,
                tz=timezone.utc,
            )
            .date()
            .isoformat()
        )
    except (OverflowError, OSError, ValueError):
        return str(value)


def _site_address(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    street = " ".join(
        part
        for part in (
            _clean_text(attributes.get("site_str_pfx")),
            _clean_text(attributes.get("site_str_num")),
            _clean_text(attributes.get("site_str_num_sfx")),
            _clean_text(attributes.get("site_str_name")),
            _clean_text(attributes.get("site_str_sfx")),
            _clean_text(attributes.get("site_str_sfx_dir")),
        )
        if part
    )
    city = _clean_text(attributes.get("site_city"))
    postal_code = _clean_text(attributes.get("site_zip"))
    if not street and not city and not postal_code:
        return None
    raw = ", ".join(
        part
        for part in (
            street or None,
            city,
            "TX",
            postal_code,
        )
        if part
    )
    return {
        "raw": raw or None,
        "street": street or None,
        "city": city,
        "county": _clean_text(attributes.get("site_county")),
        "state": "TX",
        "postal_code": postal_code,
        "country": "US",
    }


def _mailing_address(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    line1 = _clean_text(attributes.get("mail_addr_1"))
    line2 = _clean_text(attributes.get("mail_addr_2"))
    city = _clean_text(attributes.get("mail_city"))
    state = _clean_text(attributes.get("mail_state"))
    postal_code = _clean_text(attributes.get("mail_zip"))
    if not any((line1, line2, city, state, postal_code)):
        return None
    return {
        "raw": ", ".join(
            part for part in (line1, line2, city, state, postal_code) if part
        ),
        "line1": line1,
        "line2": line2,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "country": "US",
    }


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
) -> dict[str, Any]:
    attributes = dict(arcgis_keyset.feature_attributes(feature))
    object_id = attributes.get("OBJECTID")
    if isinstance(object_id, bool) or not isinstance(object_id, int):
        raise SourceSchemaError(
            "HCAD parcel feature lacks an integer OBJECTID",
            url=MAPSERVER_LAYER_URL,
            details={"value": object_id},
        )
    account_field, account = next(
        (
            (key, value)
            for key in ("HCAD_NUM", "acct_num", "LOWPARCELID")
            if (value := _clean_text(attributes.get(key))) is not None
        ),
        (None, None),
    )
    canonical_ref = (
        canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            account,
        )
        if account
        else None
    )
    feature_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "parcel_feature",
        f"{account or 'unlinked'}:{object_id}",
    )
    owners = []
    for index in range(1, 4):
        name = _clean_text(attributes.get(f"owner_name_{index}"))
        if name:
            owners.append(
                {
                    "raw_name": name,
                    "role": "assessment_snapshot_owner_name",
                    "ownership_percentage": attributes.get(f"owner_pct_{index}"),
                    "source_field": f"owner_name_{index}",
                }
            )
    legal_description = (
        " ".join(
            value
            for index in range(1, 5)
            if (value := _clean_text(attributes.get(f"legal_dscr_{index}")))
        )
        or None
    )
    tax_year_text = _clean_text(attributes.get("tax_year"))
    tax_year: int | str | None = (
        int(tax_year_text)
        if tax_year_text and re.fullmatch(r"\d{4}", tax_year_text)
        else tax_year_text
    )
    record = {
        "canonical_ref": canonical_ref,
        "feature_ref": feature_ref,
        "evidence_ref": f"HCAD-GIS-MAPSERVER:{object_id}",
        "source_id": SOURCE_ID,
        "record_kind": "parcel_assessment_geometry_snapshot",
        "record_type": "hcad_mapserver_parcel_feature",
        "jurisdiction": {
            "state_code": "TX",
            "state_fips": "48",
            "county_name": "Harris",
            "county_geoid": COUNTY_GEOID,
        },
        "native_parcel_id": account,
        "parcel_identifiers": {
            "hcad_num": _clean_text(attributes.get("HCAD_NUM")),
            "cama_account": _clean_text(attributes.get("acct_num")),
            "lowest_parcel_id": _clean_text(attributes.get("LOWPARCELID")),
            "global_id": _clean_text(attributes.get("GlobalID")),
        },
        "parcel_join_key": {
            "county_geoid": COUNTY_GEOID,
            "field": account_field,
            "value": account,
            "uniqueness_in_layer": "not_assumed",
        },
        "feature_occurrence": {
            "object_id": object_id,
            "feature_ref": feature_ref,
            "stacked": attributes.get("Stacked"),
            "condo_flag": _clean_text(attributes.get("CONDO_FLAG")),
        },
        "owners": owners,
        "situs_address": _site_address(attributes),
        "mailing_address": _mailing_address(attributes),
        "assessment": {
            "tax_year": tax_year,
            "land_value": attributes.get("land_value"),
            "building_value": attributes.get("bld_value"),
            "improvement_value": attributes.get("impr_value"),
            "productivity_value": attributes.get("productivity_value"),
            "appraised_value": attributes.get("total_appraised_val"),
            "market_value": attributes.get("total_market_val"),
            "tax_value": attributes.get("tax_value"),
            "currency": "USD",
        },
        "land": {
            "stated_area": _clean_text(attributes.get("StatedArea")),
            "published_acreage": _clean_text(attributes.get("Acreage")),
            "acreage": attributes.get("acreage_1"),
            "square_feet": attributes.get("land_sqft"),
            "land_use": _clean_text(attributes.get("land_use")),
            "state_class": _clean_text(attributes.get("state_class")),
        },
        "legal_description": legal_description,
        "legal_components": {
            "block": _clean_text(attributes.get("BLK_NUM")),
            "lot": _clean_text(attributes.get("LOT_NUM")),
            "clerk_id": _clean_text(attributes.get("clerk_id")),
        },
        "new_owner_date": _epoch_date(attributes.get("new_owner_date")),
        "confidential_flag": _clean_text(attributes.get("confidential_flag")),
        "active_account_flag": _clean_text(attributes.get("activeAccount_flag")),
        "in_cama_flag": _clean_text(attributes.get("isInCama")),
        "neighborhood": {
            "code": attributes.get("nh_cd"),
            "description": _clean_text(attributes.get("dscr")),
            "group": attributes.get("nh_grp"),
        },
        "schema_fingerprint": schema_fingerprint,
        "source_roles": {
            "geometry": "HCAD parcel mapping feature",
            "owner_and_values": "HCAD appraisal snapshot",
            "transport": "Harris County GIS MapServer",
        },
        "source_url": MAPSERVER_LAYER_URL,
        "raw_attributes": attributes,
    }
    geometry = feature.get("geometry")
    if isinstance(geometry, Mapping):
        record["geometry"] = dict(geometry)
        record["geometry_crs"] = "EPSG:4326"
    return record


def _search_records(
    args: argparse.Namespace,
    *,
    client: arcgis_keyset.BoundedArcGISClient | Any,
) -> tuple[list[dict[str, Any]], arcgis_keyset.ArcGISBatch]:
    if args.command == "objectid":
        where = f"OBJECTID = {args.object_id}"
        operation = "objectid"
    else:
        field = "account" if args.command == "account" else args.field
        where = _where(
            field,
            args.query,
            "exact" if args.command == "account" else args.match,
        )
        operation = args.command if args.command != "search" else field
    batch = arcgis_keyset.fetch_batch(
        client,
        MAP_MANIFEST,
        adapter_slug="parcels",
        operation=operation,
        where=where,
        limit=args.limit,
        cursor=args.cursor,
        return_geometry=args.geometry,
        cursor_namespace="hcad",
    )
    records = [
        _normalize_feature(
            feature,
            schema_fingerprint=batch.schema_fingerprint,
        )
        for feature in batch.features
    ]
    return records, batch


def _source_record() -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_description",
        "source_page": SOURCE_PAGE,
        "schema_reference": SCHEMA_URL,
        "bulk_manifest_endpoints": {
            "last_update": LAST_UPDATE_ENDPOINT,
            "current_components": FILES_ENDPOINT,
            "current_bundle": PUBLIC_ENDPOINT,
            "historical_parcels": PRIOR_YEAR_ENDPOINT,
        },
        "queryable_representation": {
            "url": MAPSERVER_LAYER_URL,
            "operator": "Harris County GIS",
            "record_publisher": "Harris Central Appraisal District",
            "identity": "OBJECTID feature occurrence plus HCAD_NUM parcel join",
        },
        "projection": {
            "epsg": 2278,
            "wkid": 102740,
            "name": "NAD83 Texas South Central (US feet)",
        },
        "parcel_join_field": "HCAD_NUM",
        "source_manifest_schema_fingerprint": ENDPOINT_SCHEMA_FINGERPRINT,
    }


def _alternatives() -> list[dict[str, Any]]:
    return [
        {
            "route_id": "hcad-cama-bulk",
            "name": "HCAD CAMA bulk files",
            "url": HCAD_CAMA_SOURCE_URL,
            "role": (
                "current account, ownership, ownership-history, building, "
                "land, value, exemption, and hearing attributes"
            ),
            "integration": "implemented complement joined by HCAD account",
        },
        {
            "route_id": "harris-county-hcad-mapserver",
            "name": "Harris County GIS HCAD parcel MapServer",
            "url": MAPSERVER_LAYER_URL,
            "role": "queryable parcel geometry and joined appraisal snapshot",
            "integration": "implemented query transport",
        },
        {
            "route_id": "txgio-harris-parcels",
            "name": "TxGIO Harris County land-parcel archive",
            "url": TXGIO_SOURCE_URL,
            "role": "standardized statewide parcel snapshot and shapefile",
            "integration": "implemented substitute for local FileGDB decoding",
        },
        {
            "route_id": "hcad-parcel-viewer",
            "name": "HCAD Parcel Viewer",
            "url": HCAD_PARCEL_VIEWER_URL,
            "role": "interactive current parcel and appraisal lookup",
            "integration": "browser complement",
        },
    ]


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in (
        "year",
        "artifact_name",
        "destination",
        "query",
        "field",
        "match",
        "object_id",
        "geometry",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = str(value)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: HCADGISError | BulkSourceError,
) -> PublicRecordsResult:
    status = getattr(error, "status", getattr(error, "result_status", None))
    return PublicRecordsResult.failure(
        query,
        status or ResultStatus.UNAVAILABLE,
        [error.to_contract_error()],
    )


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    manifest_client: HCADGISManifestClient | Any | None = None,
    bulk_client: BulkTransferClient | Any | None = None,
    arcgis_client: arcgis_keyset.BoundedArcGISClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(query, [_source_record()])
        elif args.command == "alternatives":
            result = PublicRecordsResult.success(query, _alternatives())
        elif args.command == "inspect":
            inspection = inspect_local_artifact(
                args.artifact,
                policy=_archive_policy(args),
            )
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "canonical_ref": (
                            f"HCAD-GIS-INSPECTION:{inspection['artifact_sha256']}"
                        ),
                        "source_id": SOURCE_ID,
                        "record_kind": "local_artifact_inspection",
                        "inspection": inspection,
                        "source_url": SOURCE_PAGE,
                    }
                ],
                raw_artifact_refs=[inspection["path"]],
            )
        elif args.command in {"search", "account", "objectid"}:
            contract = access_contract or _access_contract(args)
            source_client = arcgis_client or _arcgis_client(args, contract)
            records, batch = _search_records(args, client=source_client)
            retrieval = {
                "transport": "arcgis_keyset",
                "total_matching_count": batch.total_count,
                "bounded_snapshot_count": batch.bounded_count,
                "boundary_object_id": batch.boundary_object_id,
                "pages_fetched": batch.pages_fetched,
                "source_schema_fingerprint": batch.schema_fingerprint,
            }
            records = [{**record, "retrieval": retrieval} for record in records]
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=batch.next_cursor,
                warnings=(
                    ["Bounded source count changed since this cursor was issued."]
                    if batch.count_changed_since_cursor
                    else []
                ),
            )
        else:
            if access_contract is None:
                _access_contract(args)
            source_client = manifest_client or _manifest_client(args)
            releases, by_release = release_inventory(source_client)
            if args.command == "releases":
                result = PublicRecordsResult.success(query, releases)
            else:
                release = _selected_release(releases, year=args.year)
                if release is None:
                    result = PublicRecordsResult.success(query, [])
                else:
                    selected = _select_artifacts(
                        by_release[str(release["release_id"])],
                        args.artifact_name,
                        single_default=args.command in {"probe", "download"},
                    )
                    if not selected:
                        result = PublicRecordsResult.success(query, [])
                    else:
                        manifest = normalize_manifest(release, selected)
                        if args.command == "manifest":
                            result = PublicRecordsResult.success(
                                query,
                                [manifest],
                            )
                        else:
                            artifact = _manifest_artifact(manifest)
                            transfer = bulk_client or _bulk_client(args)
                            if args.command == "probe":
                                probe = transfer.probe(
                                    artifact,
                                    sample_bytes=args.sample_bytes,
                                )
                                if probe.format_hint != "zip":
                                    raise HCADGISError(
                                        "hcad_gis_artifact_format_changed",
                                        "HCAD GIS artifact no longer has a ZIP signature",
                                        details={"probe": probe.to_dict()},
                                    )
                                result = PublicRecordsResult.success(
                                    query,
                                    [
                                        {
                                            **manifest,
                                            "record_kind": "source_probe",
                                            "selected_artifact": artifact.to_dict(),
                                            "probe": probe.to_dict(),
                                        }
                                    ],
                                )
                            elif args.command == "download":
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
                                record = {
                                    **manifest,
                                    "record_kind": "bulk_artifact_download",
                                    "selected_artifact": artifact.to_dict(),
                                    "download": download.to_dict(),
                                }
                                if args.inspect:
                                    record["inspection"] = inspect_local_artifact(
                                        download.path,
                                        policy=_archive_policy(args),
                                    )
                                result = PublicRecordsResult.success(
                                    query,
                                    [record],
                                    raw_artifact_refs=[download.path],
                                )
                            else:
                                raise ValueError(
                                    f"unsupported HCAD GIS command {args.command}"
                                )
    except AcquisitionUnavailableError as error:
        decision = error.decision
        result = PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code")
                        or "machine_acquisition_not_available"
                    ),
                    message=str(error),
                    category="access_policy",
                    details=decision,
                )
            ],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (HCADGISError, BulkSourceError) as error:
        result = _failure(query, error)
    except (OSError, zipfile.BadZipFile) as error:
        result = _failure(
            query,
            HCADGISError(
                "hcad_gis_local_artifact_error",
                f"Could not read HCAD GIS artifact: {error}",
                status=ResultStatus.UNAVAILABLE,
                category="local_artifact",
                details={"artifact": getattr(args, "artifact", None)},
            ),
        )
    except ValueError as error:
        result = _failure(
            query,
            HCADGISError(
                "hcad_gis_query_invalid",
                str(error),
                status=ResultStatus.UNAVAILABLE,
                category="query_selection",
            ),
        )
    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and access reviews",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)


def _add_release_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--year",
        type=int,
        help="Historical October parcel snapshot year; omit for current",
    )
    parser.add_argument(
        "--artifact",
        dest="artifact_name",
        help="Artifact filename, label, or ID",
    )
    _add_runtime_args(parser)


def _add_archive_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-archive-members", type=int)
    parser.add_argument("--max-uncompressed-bytes", type=int)
    parser.add_argument("--max-member-uncompressed-bytes", type=int)
    parser.add_argument("--max-compression-ratio", type=float)


def _add_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--cursor")
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Return polygon coordinates projected to EPSG:4326",
    )
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    _add_runtime_args(parser)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query and acquire official HCAD parcel GIS data"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("sources", "Describe HCAD GIS representations and identity"),
        ("alternatives", "List complementary official property routes"),
    ):
        command = sub.add_parser(name, help=help_text)
        add_output_args(command)

    releases = sub.add_parser(
        "releases",
        help="List the current GIS release and historical parcel snapshots",
    )
    _add_runtime_args(releases)
    add_output_args(releases)

    manifest = sub.add_parser(
        "manifest",
        help="Build a current or historical deterministic manifest",
    )
    _add_release_args(manifest)
    add_output_args(manifest)

    probe = sub.add_parser(
        "probe",
        help="Probe one published GIS archive",
    )
    _add_release_args(probe)
    probe.add_argument("--sample-bytes", type=int, default=4096)
    add_output_args(probe)

    download = sub.add_parser(
        "download",
        help="Download and fingerprint one GIS archive",
    )
    _add_release_args(download)
    download.add_argument("--destination", required=True)
    download.add_argument("--expected-sha256")
    download.add_argument("--max-download-bytes", type=int)
    download.add_argument("--chunk-size", type=int, default=1024 * 1024)
    download.add_argument("--no-resume", action="store_false", dest="resume")
    download.add_argument("--inspect", action="store_true")
    download.set_defaults(resume=True)
    _add_archive_args(download)
    add_output_args(download)

    inspect_command = sub.add_parser(
        "inspect",
        help="Inspect a downloaded HCAD GIS archive representation",
    )
    inspect_command.add_argument("artifact")
    _add_archive_args(inspect_command)
    add_output_args(inspect_command)

    search = sub.add_parser(
        "search",
        help="Search the queryable HCAD parcel representation",
    )
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=tuple(SEARCH_FIELDS),
        default="any",
    )
    search.add_argument(
        "--match",
        choices=("contains", "prefix", "exact"),
        default="contains",
    )
    _add_search_args(search)

    account = sub.add_parser(
        "account",
        help="Look up an exact HCAD parcel account",
    )
    account.add_argument("query")
    account.set_defaults(match="exact", field="account")
    _add_search_args(account)

    objectid = sub.add_parser(
        "objectid",
        help="Look up one MapServer feature occurrence",
    )
    objectid.add_argument("object_id", type=int)
    objectid.set_defaults(query=None, match="exact", field="objectid")
    _add_search_args(objectid)
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    for name in (
        "timeout",
        "retry_attempts",
        "sample_bytes",
        "chunk_size",
        "limit",
        "page_size",
        "max_download_bytes",
        "max_archive_members",
        "max_uncompressed_bytes",
        "max_member_uncompressed_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    ratio = getattr(args, "max_compression_ratio", None)
    if ratio is not None and ratio <= 0:
        parser.error("--max-compression-ratio must be positive")
    if getattr(args, "object_id", 1) < 0:
        parser.error("object_id must not be negative")


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"HCAD GIS {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"HCAD GIS {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("native_parcel_id")
            or record.get("release_id")
            or record.get("canonical_ref")
        )
        if label:
            print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
