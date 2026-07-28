#!/usr/bin/env python3
"""MassGIS municipal property-parcel bulk release adapter.

MassGIS publishes a statewide ArcGIS layer whose records contain direct
shapefile and file-geodatabase download URLs for each municipality. The
archives are municipality-scoped snapshots with the assessor fiscal year in
the source manifest.

Usage:
    uv run python tools/query_massgis_property.py manifest --town GOSNOLD
    uv run python tools/query_massgis_property.py probe --town GOSNOLD
    uv run python tools/query_massgis_property.py download --town GOSNOLD \
        --format shapefile --destination /tmp/massgis --dry-run
    uv run python tools/query_massgis_property.py inspect /tmp/M109.zip
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

try:
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
        safe_extract_zip,
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
    )
    from tools.public_records_http import (
        ArcGISRESTClient,
        PaginatedFetch,
        PublicRecordsHTTPError,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
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
        safe_extract_zip,
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
    )
    from public_records_http import (
        ArcGISRESTClient,
        PaginatedFetch,
        PublicRecordsHTTPError,
        failure_result,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-ma-massgis-parcels"
SOURCE_PAGE = "https://www.mass.gov/info-details/massgis-data-property-tax-parcels"
MANIFEST_LAYER_URL = (
    "https://services9.arcgis.com/2ynJbr9BE17vXxR8/ArcGIS/rest/services/"
    "MassGIS_L3_Parcels_gdb/FeatureServer/2"
)
MANIFEST_FIELDS = (
    "OBJECTID",
    "TOWN",
    "TOWN_ID",
    "SHAPE_LINK",
    "FGDB_LINK",
    "FY",
    "NOTE",
)
SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="MassGIS Standardized Property Tax Parcels",
    source_role="assessment_parcel_geometry_bulk",
    base_url=MANIFEST_LAYER_URL,
    dataset_id="L3_PARCEL_FTP_LINKS",
    metadata={
        "authority": "Massachusetts Bureau of Geographic Information",
        "coverage": "351 Massachusetts municipalities",
        "release_scope": "municipality",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-ma",
    name="Massachusetts",
    state_code="MA",
    metadata={"state_fips": "25"},
)
DECLARED_DATA_MODEL = {
    "standard": "MassGIS Digital Parcel Standard Level 3",
    "logical_components": [
        "L3_ASSESS",
        "L3_LUT",
        "L3_MISC_POLY",
        "L3_OTHLEG_POLY",
        "L3_TAXPAR_POLY",
        "L3_UC_LUT",
    ],
    "parcel_assessment_join_key": "LOC_ID",
    "source_description": SOURCE_PAGE,
}


def _sql_literal(value: str) -> str:
    cleaned = " ".join(str(value).replace("\x00", "").split()).strip().upper()
    if not cleaned:
        raise ValueError("town must not be blank")
    return cleaned.replace("'", "''")


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog_db = Path(
        getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
    ).expanduser()
    catalog_config = Path(
        getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
    ).expanduser()
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=catalog_db,
        config_path=catalog_config,
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _manifest_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> ArcGISRESTClient:
    limits = access_contract.get("limits") or {}
    reviewed_page_size = limits.get("maximum_page_size")
    page_size = args.page_size
    if reviewed_page_size is not None:
        page_size = min(page_size, int(reviewed_page_size))
    return ArcGISRESTClient(
        MANIFEST_LAYER_URL,
        page_size=page_size,
        max_records=args.max_records,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
    )


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=getattr(args, "retry_attempts", 3),
        chunk_size=getattr(args, "chunk_size", 1024 * 1024),
    )


def _where(town: str | None) -> str:
    return "1=1" if town is None else f"TOWN = '{_sql_literal(town)}'"


def _attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError("MassGIS manifest feature is missing attributes")
    return attributes


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer") from error


def _artifact(
    *,
    artifact_format: str,
    url: Any,
    town: str,
    town_id: int,
    fiscal_year: int,
) -> BulkArtifact:
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"MassGIS manifest lacks a {artifact_format} URL")
    return BulkArtifact.from_url(
        artifact_format,
        url.strip(),
        media_type="application/zip",
        archive_format="zip",
        metadata={
            "municipality": town,
            "town_id": town_id,
            "assessor_fiscal_year": fiscal_year,
        },
    )


def normalize_manifest_feature(
    feature: Mapping[str, Any],
    *,
    source_manifest_schema_fingerprint: str,
) -> dict[str, Any]:
    """Normalize one official MassGIS download-link feature."""
    attributes = _attributes(feature)
    town = str(attributes.get("TOWN") or "").strip().upper()
    if not town:
        raise ValueError("MassGIS manifest lacks TOWN")
    town_id = _integer(attributes.get("TOWN_ID"), "TOWN_ID")
    fiscal_year = _integer(attributes.get("FY"), "FY")
    release_id = f"M{town_id:03d}:FY{fiscal_year}"
    artifacts = (
        _artifact(
            artifact_format="shapefile",
            url=attributes.get("SHAPE_LINK"),
            town=town,
            town_id=town_id,
            fiscal_year=fiscal_year,
        ),
        _artifact(
            artifact_format="file_geodatabase",
            url=attributes.get("FGDB_LINK"),
            town=town,
            town_id=town_id,
            fiscal_year=fiscal_year,
        ),
    )
    manifest = BulkDatasetManifest(
        source_id=SOURCE_ID,
        dataset_id="MassGIS-L3-Parcels",
        release=BulkReleaseMetadata(
            release_id=release_id,
            kind="snapshot",
            coverage={
                "municipality": town,
                "town_id": town_id,
                "assessor_fiscal_year": fiscal_year,
            },
        ),
        artifacts=artifacts,
        schema=DECLARED_DATA_MODEL,
        metadata={
            "source_manifest_object_id": attributes.get("OBJECTID"),
            "source_note": attributes.get("NOTE"),
            "source_manifest_schema_fingerprint": (
                source_manifest_schema_fingerprint
            ),
        },
    )
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            "25",
            "bulk_release",
            release_id,
        ),
        "town": town,
        "town_id": town_id,
        "assessor_fiscal_year": fiscal_year,
        "release_kind": "snapshot",
        "manifest": manifest.to_dict(),
    }


def _fetch_manifests(
    args: argparse.Namespace,
    client: ArcGISRESTClient,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], PaginatedFetch]:
    fetched = client.query(
        where=_where(getattr(args, "town", None)),
        out_fields=MANIFEST_FIELDS,
        requested_limit=limit,
        max_records=args.max_records,
        cursor=getattr(args, "cursor", None),
        return_geometry=False,
    )
    records = [
        normalize_manifest_feature(
            feature,
            source_manifest_schema_fingerprint=fetched.schema_fingerprint,
        )
        for feature in fetched.records
    ]
    return records, fetched


def _select_artifact(record: Mapping[str, Any], artifact_format: str) -> BulkArtifact:
    manifest = record["manifest"]
    artifacts = manifest["artifacts"]
    for artifact_data in artifacts:
        if artifact_data["artifact_id"] == artifact_format:
            return BulkArtifact(
                artifact_id=artifact_data["artifact_id"],
                url=artifact_data["url"],
                filename=artifact_data["filename"],
                media_type=artifact_data.get("media_type"),
                archive_format=artifact_data.get("archive_format"),
                expected_size=artifact_data.get("expected_size"),
                expected_sha256=artifact_data.get("expected_sha256"),
                etag=artifact_data.get("etag"),
                last_modified=artifact_data.get("last_modified"),
                metadata=artifact_data.get("metadata") or {},
            )
    raise ValueError(f"MassGIS release does not declare {artifact_format}")


def _archive_policy(args: argparse.Namespace) -> ArchiveSafetyPolicy:
    return ArchiveSafetyPolicy(
        max_members=getattr(args, "max_archive_members", None),
        max_total_uncompressed_bytes=getattr(
            args, "max_uncompressed_bytes", None
        ),
        max_member_uncompressed_bytes=getattr(
            args, "max_member_uncompressed_bytes", None
        ),
        max_compression_ratio=getattr(args, "max_compression_ratio", None),
    )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in (
        "town",
        "format",
        "destination",
        "archive",
        "extract_to",
        "dry_run",
        "range_bytes",
        "expected_sha256",
        "max_download_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = str(value) if isinstance(value, Path) else value
    if args.command in {"inspect", "extract"}:
        parameters["archive_policy"] = _archive_policy(args).to_dict()
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


def _access_failure(
    query: PublicRecordsQuery,
    error: AcquisitionUnavailableError,
) -> PublicRecordsResult:
    decision = error.decision
    status = ResultStatus(acquisition_result_status(decision))
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=str(decision.get("reason_code") or "machine_acquisition_denied"),
                message=str(error),
                category="access_policy",
                details=decision,
            )
        ],
    )


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    manifest_client: ArcGISRESTClient | None = None,
    bulk_client: BulkTransferClient | None = None,
) -> PublicRecordsResult:
    """Execute one CLI operation and return the canonical result envelope."""
    query = build_query(args)
    try:
        if args.command in {"inspect", "extract"}:
            policy = _archive_policy(args)
            if args.command == "inspect":
                inspection = inspect_zip(args.archive, policy=policy)
                result = PublicRecordsResult.success(
                    query,
                    [{"archive": inspection.to_dict()}],
                    raw_artifact_refs=[str(Path(args.archive))],
                )
            else:
                extraction = safe_extract_zip(
                    args.archive,
                    args.destination,
                    policy=policy,
                    overwrite=args.overwrite,
                )
                result = PublicRecordsResult.success(
                    query,
                    [{"extraction": extraction}],
                    raw_artifact_refs=[str(Path(args.archive))],
                )
        else:
            contract = access_contract or _access_contract(args)
            source_client = manifest_client or _manifest_client(args, contract)
            limit = args.limit if args.command == "manifest" else 1
            records, fetched = _fetch_manifests(args, source_client, limit=limit)
            if args.command == "manifest":
                if fetched.truncated_by_cap:
                    result = PublicRecordsResult(
                        query=query,
                        status=ResultStatus.PARTIAL,
                        records=records,
                        next_cursor=fetched.next_cursor,
                        warnings=fetched.warnings,
                    )
                else:
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        next_cursor=fetched.next_cursor,
                        warnings=fetched.warnings,
                    )
            elif not records:
                result = PublicRecordsResult.success(query, [])
            else:
                record = records[0]
                artifact = _select_artifact(record, args.format)
                transfer = bulk_client or _bulk_client(args)
                if args.command == "probe":
                    probe = transfer.probe(
                        artifact,
                        sample_bytes=args.range_bytes,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        [
                            {
                                **record,
                                "selected_artifact": artifact.to_dict(),
                                "probe": probe.to_dict(),
                            }
                        ],
                    )
                elif args.dry_run:
                    destination = Path(args.destination)
                    if destination.exists() and destination.is_dir():
                        destination = destination / artifact.filename
                    result = PublicRecordsResult.success(
                        query,
                        [
                            {
                                **record,
                                "selected_artifact": artifact.to_dict(),
                                "download": {
                                    "status": "planned",
                                    "destination": str(destination),
                                    "resume": args.resume,
                                    "max_bytes": args.max_download_bytes,
                                },
                            }
                        ],
                    )
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
                    inspection = inspect_zip(
                        download.path,
                        policy=_archive_policy(args),
                    )
                    output_record: dict[str, Any] = {
                        **record,
                        "selected_artifact": artifact.to_dict(),
                        "download": download.to_dict(),
                        "archive": inspection.to_dict(),
                    }
                    if args.extract_to:
                        output_record["extraction"] = safe_extract_zip(
                            download.path,
                            args.extract_to,
                            policy=_archive_policy(args),
                            overwrite=args.overwrite,
                        )
                    result = PublicRecordsResult.success(
                        query,
                        [output_record],
                        raw_artifact_refs=[download.path],
                    )
    except AcquisitionUnavailableError as error:
        result = _access_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
        )
    except (OSError, ValueError, TypeError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="bulk_operation_failed",
                    message=str(error),
                    category="bulk_source",
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
    log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"MassGIS property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"MassGIS property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if "town" in record:
            print(
                f"  {record['town']} | FY {record['assessor_fiscal_year']} | "
                f"{record['canonical_ref']}"
            )
        elif "archive" in record:
            archive = record["archive"]
            print(
                f"  {archive['path']} | {archive['member_count']} members | "
                f"{archive['archive_sha256']}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_catalog_args(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional user-selected record ceiling for manifest queries",
    )


def _add_archive_policy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-archive-members", type=int)
    parser.add_argument("--max-uncompressed-bytes", type=int)
    parser.add_argument("--max-member-uncompressed-bytes", type=int)
    parser.add_argument("--max-compression-ratio", type=float)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query and download official MassGIS municipal parcel releases"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser("manifest", help="List municipal release manifests")
    manifest.add_argument("--town", help="Exact municipality name")
    manifest.add_argument("--limit", type=int, default=50)
    manifest.add_argument("--cursor")
    _add_catalog_args(manifest)
    add_output_args(manifest)

    probe = sub.add_parser(
        "probe",
        help="Resolve one release and make a bounded artifact metadata/range probe",
    )
    probe.add_argument("--town", required=True)
    probe.add_argument(
        "--format",
        choices=("shapefile", "file_geodatabase"),
        default="shapefile",
    )
    probe.add_argument("--range-bytes", type=int, default=4096)
    _add_catalog_args(probe)
    add_output_args(probe)

    download = sub.add_parser(
        "download",
        help="Resolve and download one municipal snapshot",
    )
    download.add_argument("--town", required=True)
    download.add_argument(
        "--format",
        choices=("shapefile", "file_geodatabase"),
        default="shapefile",
    )
    download.add_argument("--destination", required=True)
    download.add_argument("--dry-run", action="store_true")
    download.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="Start a new partial transfer",
    )
    download.set_defaults(resume=True)
    download.add_argument("--expected-sha256")
    download.add_argument("--max-download-bytes", type=int)
    download.add_argument("--retry-attempts", type=int, default=3)
    download.add_argument("--chunk-size", type=int, default=1024 * 1024)
    download.add_argument("--extract-to")
    download.add_argument("--overwrite", action="store_true")
    _add_archive_policy_args(download)
    _add_catalog_args(download)
    add_output_args(download)

    inspect_parser = sub.add_parser(
        "inspect",
        help="Inspect and fingerprint a local ZIP without extraction",
    )
    inspect_parser.add_argument("archive")
    _add_archive_policy_args(inspect_parser)
    add_output_args(inspect_parser)

    extract = sub.add_parser("extract", help="Safely extract a local ZIP")
    extract.add_argument("archive")
    extract.add_argument("destination")
    extract.add_argument("--overwrite", action="store_true")
    _add_archive_policy_args(extract)
    add_output_args(extract)
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    for name in (
        "limit",
        "page_size",
        "max_records",
        "retry_attempts",
        "chunk_size",
        "max_download_bytes",
        "max_archive_members",
        "max_uncompressed_bytes",
        "max_member_uncompressed_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if getattr(args, "range_bytes", 0) < 0:
        parser.error("--range-bytes must not be negative")
    if (
        getattr(args, "max_compression_ratio", None) is not None
        and args.max_compression_ratio <= 0
    ):
        parser.error("--max-compression-ratio must be positive")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
