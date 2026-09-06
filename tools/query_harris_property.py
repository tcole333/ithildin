#!/usr/bin/env python3
"""Harris Central Appraisal District bulk-property release adapter.

HCAD's Public Data page loads available tax years, release state, and download
links from public JSON endpoints. The linked ZIP archives contain the district's
real-property, personal-property, and hearings text-file exports.

Usage:
    uv run python tools/query_harris_property.py list
    uv run python tools/query_harris_property.py manifest --year 2026
    uv run python tools/query_harris_property.py probe --year 2026 \
        --artifact Real_acct_owner.zip
    uv run python tools/query_harris_property.py dry-run --year 2026 \
        --artifact Real_acct_owner.zip --destination /tmp/hcad
    uv run python tools/query_harris_property.py download --year 2026 \
        --artifact Real_acct_owner.zip --destination /tmp/hcad
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
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
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
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


SOURCE_ID = "us-tx-harris-hcad-property"
SOURCE_PAGE = "https://hcad.org/pdata/pdata-property-downloads.html/"
ACTION_ROOT = "https://hcad.org/actions/hcad-pdata/default"
TAX_YEARS_ENDPOINT = f"{ACTION_ROOT}/get-tax-years"
CERTIFICATION_ENDPOINT = f"{ACTION_ROOT}/get-certification-flag"
DOWNLOADS_ENDPOINT = f"{ACTION_ROOT}/get-property-downloads"
CODEBOOK_URL = "https://hcad.org/assets/uploads/pdf/pdataCodebook.pdf"

GROUPS = {
    "real-property": "Real Property",
    "personal-property": "Personal Property",
    "hearings": "Hearings",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Harris Central Appraisal District Public Data",
    source_role="assessment_ownership_improvements_hearings_bulk",
    base_url=SOURCE_PAGE,
    dataset_id="HCAD-CAMA",
    metadata={
        "authority": "Harris Central Appraisal District",
        "release_scope": "Harris County",
        "manifest_transport": "official_json_endpoints",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-tx-harris",
    name="Harris County, Texas",
    state_code="TX",
    county_fips="48201",
    locality="Harris County",
)

ENDPOINT_SCHEMA = {
    "tax_years": [{"taxyears": "year_string"}],
    "certification": [
        {
            "taxyear": "year_string",
            "certflg": "Y_or_N",
            "lastUpdatedDate": "Month_DD_YYYY",
        }
    ],
    "downloads": [
        {
            "taxYear": "year_string",
            "category": "CAMA",
            "subCategory": "group_label",
            "downloadLinkText": "artifact_label",
            "description": "artifact_description",
            "downloadLink": "artifact_url",
            "filename": "native_filename",
        }
    ],
}
ENDPOINT_SCHEMA_FINGERPRINT = sha256_fingerprint(ENDPOINT_SCHEMA)

DECLARED_DATA_MODEL = {
    "format": "zip_archives_of_text_files",
    "schema_reference": CODEBOOK_URL,
    "native_account_key": "acct",
    "release_groups": {
        "real-property": {
            "contents": [
                "parcel_and_owner",
                "ownership_history",
                "building_and_land",
                "jurisdiction_and_exemption",
                "code_descriptions",
            ]
        },
        "personal-property": {
            "contents": ["personal_property", "code_descriptions"]
        },
        "hearings": {"contents": ["appraisal_review_board_hearings"]},
    },
}

_DOWNLOAD_REQUIRED_FIELDS = (
    "taxYear",
    "category",
    "subCategory",
    "downloadLink",
    "filename",
)


def _clean_text(value: Any, field_name: str, *, url: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceSchemaError(
            f"HCAD response is missing {field_name}",
            url=url,
            details={"field": field_name},
        )
    return value.strip()


def _parse_year(value: Any, field_name: str, *, url: str) -> int:
    text = _clean_text(value, field_name, url=url)
    if len(text) != 4 or not text.isdigit():
        raise SourceSchemaError(
            f"HCAD {field_name} is not a four-digit year",
            url=url,
            details={"field": field_name, "value": text},
        )
    return int(text)


def _expect_list(payload: Any, *, url: str, response_name: str) -> list[Any]:
    if not isinstance(payload, list):
        raise SourceSchemaError(
            f"HCAD {response_name} response is not a JSON array",
            url=url,
            details={"observed_type": type(payload).__name__},
        )
    return payload


class HCADManifestClient(_BaseJSONClient):
    """Client for the JSON endpoints used by HCAD's Public Data page."""

    def list_tax_years(self) -> list[dict[str, Any]]:
        payload = self._request_json(TAX_YEARS_ENDPOINT, params={})
        rows = _expect_list(
            payload,
            url=TAX_YEARS_ENDPOINT,
            response_name="tax-year",
        )
        records: list[dict[str, Any]] = []
        seen: set[int] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise SourceSchemaError(
                    "HCAD tax-year row is not an object",
                    url=TAX_YEARS_ENDPOINT,
                    details={"row_index": index},
                )
            year = _parse_year(
                row.get("taxyears"),
                "taxyears",
                url=TAX_YEARS_ENDPOINT,
            )
            if year in seen:
                raise SourceSchemaError(
                    "HCAD tax-year response contains a duplicate year",
                    url=TAX_YEARS_ENDPOINT,
                    details={"tax_year": year},
                )
            seen.add(year)
            records.append(
                {
                    "tax_year": year,
                    "native_tax_year": str(row["taxyears"]).strip(),
                    "canonical_ref": canonical_property_ref(
                        SOURCE_ID,
                        "48201",
                        "bulk_release_year",
                        str(year),
                    ),
                    "source_manifest_schema_fingerprint": (
                        ENDPOINT_SCHEMA_FINGERPRINT
                    ),
                }
            )
        return records

    def certification(self, year: int) -> dict[str, Any]:
        payload = self._request_json(
            CERTIFICATION_ENDPOINT,
            params={"t": year},
        )
        rows = _expect_list(
            payload,
            url=CERTIFICATION_ENDPOINT,
            response_name="certification",
        )
        if len(rows) != 1 or not isinstance(rows[0], Mapping):
            raise SourceSchemaError(
                "HCAD certification response must contain one object",
                url=CERTIFICATION_ENDPOINT,
                details={"row_count": len(rows)},
            )
        row = rows[0]
        response_year = _parse_year(
            row.get("taxyear"),
            "taxyear",
            url=CERTIFICATION_ENDPOINT,
        )
        if response_year != year:
            raise SourceSchemaError(
                "HCAD certification response returned a different tax year",
                url=CERTIFICATION_ENDPOINT,
                details={"requested_year": year, "response_year": response_year},
            )
        native_flag = _clean_text(
            row.get("certflg"),
            "certflg",
            url=CERTIFICATION_ENDPOINT,
        ).upper()
        if native_flag not in {"Y", "N"}:
            raise SourceSchemaError(
                "HCAD certification flag is not Y or N",
                url=CERTIFICATION_ENDPOINT,
                details={"value": native_flag},
            )
        native_updated = _clean_text(
            row.get("lastUpdatedDate"),
            "lastUpdatedDate",
            url=CERTIFICATION_ENDPOINT,
        )
        try:
            updated_date = datetime.strptime(
                native_updated,
                "%B %d, %Y",
            ).date().isoformat()
        except ValueError as error:
            raise SourceSchemaError(
                "HCAD last-updated date format changed",
                url=CERTIFICATION_ENDPOINT,
                details={"value": native_updated},
            ) from error
        return {
            "tax_year": response_year,
            "native_certification_flag": native_flag,
            "certification_status": (
                "certified" if native_flag == "Y" else "preliminary"
            ),
            "is_certified": native_flag == "Y",
            "last_updated_date": updated_date,
            "native_last_updated_date": native_updated,
        }

    def downloads(self, year: int, group: str) -> list[dict[str, Any]]:
        native_group = GROUPS[group]
        payload = self._request_json(
            DOWNLOADS_ENDPOINT,
            params={"t": year, "c": "CAMA", "s": native_group},
        )
        rows = _expect_list(
            payload,
            url=DOWNLOADS_ENDPOINT,
            response_name="download-manifest",
        )
        records: list[dict[str, Any]] = []
        seen_filenames: set[str] = set()
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise SourceSchemaError(
                    "HCAD download-manifest row is not an object",
                    url=DOWNLOADS_ENDPOINT,
                    details={"row_index": index},
                )
            missing = [
                field_name
                for field_name in _DOWNLOAD_REQUIRED_FIELDS
                if not isinstance(row.get(field_name), str)
                or not str(row[field_name]).strip()
            ]
            if missing:
                raise SourceSchemaError(
                    "HCAD download-manifest row is missing required fields",
                    url=DOWNLOADS_ENDPOINT,
                    details={"row_index": index, "fields": missing},
                )
            response_year = _parse_year(
                row["taxYear"],
                "taxYear",
                url=DOWNLOADS_ENDPOINT,
            )
            response_group = str(row["subCategory"]).strip()
            category = str(row["category"]).strip()
            if response_year != year or response_group != native_group or category != "CAMA":
                raise SourceSchemaError(
                    "HCAD download-manifest row does not match the request",
                    url=DOWNLOADS_ENDPOINT,
                    details={
                        "row_index": index,
                        "requested_year": year,
                        "response_year": response_year,
                        "requested_group": native_group,
                        "response_group": response_group,
                        "category": category,
                    },
                )
            filename = str(row["filename"]).strip()
            if Path(filename).name != filename or filename in seen_filenames:
                raise SourceSchemaError(
                    "HCAD download manifest has an invalid or duplicate filename",
                    url=DOWNLOADS_ENDPOINT,
                    details={"row_index": index, "filename": filename},
                )
            seen_filenames.add(filename)
            records.append(
                {
                    "tax_year": response_year,
                    "native_tax_year": str(row["taxYear"]).strip(),
                    "category": category,
                    "group": group,
                    "native_subcategory": response_group,
                    "label": str(row.get("downloadLinkText") or "").strip(),
                    "description": str(row.get("description") or "").strip(),
                    "url": str(row["downloadLink"]).strip(),
                    "filename": filename,
                }
            )
        return records


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog_db = Path(args.catalog_db).expanduser()
    catalog_config = Path(args.catalog_config).expanduser()
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=catalog_db,
        config_path=catalog_config,
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _manifest_client(args: argparse.Namespace) -> HCADManifestClient:
    return HCADManifestClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
        minimum_interval=args.minimum_interval,
    )


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=getattr(args, "chunk_size", 1024 * 1024),
    )


def normalize_release(
    year: int,
    group: str,
    certification: Mapping[str, Any],
    download_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic bulk manifest from one official HCAD release."""
    status = str(certification["certification_status"])
    updated_date = str(certification["last_updated_date"])
    release_id = f"{year}:{status}:{updated_date}"
    artifacts = [
        BulkArtifact(
            artifact_id=str(row["filename"]),
            url=str(row["url"]),
            filename=str(row["filename"]),
            media_type="application/zip",
            archive_format="zip",
            metadata={
                "native_tax_year": row["native_tax_year"],
                "category": row["category"],
                "native_subcategory": row["native_subcategory"],
                "download_link_text": row["label"],
                "description": row["description"],
            },
        )
        for row in download_rows
    ]
    schema = {
        **DECLARED_DATA_MODEL,
        "selected_group": group,
        "selected_group_model": DECLARED_DATA_MODEL["release_groups"][group],
    }
    manifest = BulkDatasetManifest(
        source_id=SOURCE_ID,
        dataset_id=f"HCAD-CAMA-{group}",
        release=BulkReleaseMetadata(
            release_id=release_id,
            kind="snapshot",
            effective_at=updated_date,
            coverage={
                "tax_year": year,
                "certification_status": status,
                "county_fips": "48201",
                "group": group,
            },
        ),
        artifacts=artifacts,
        schema=schema,
        metadata={
            "certification": dict(certification),
            "source_page": SOURCE_PAGE,
            "tax_years_endpoint": TAX_YEARS_ENDPOINT,
            "certification_endpoint": CERTIFICATION_ENDPOINT,
            "downloads_endpoint": DOWNLOADS_ENDPOINT,
            "source_manifest_schema_fingerprint": ENDPOINT_SCHEMA_FINGERPRINT,
        },
    )
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            "48201",
            "bulk_release",
            release_id,
        ),
        "tax_year": year,
        "group": group,
        "native_subcategory": GROUPS[group],
        "release_kind": "snapshot",
        "certification": dict(certification),
        "manifest": manifest.to_dict(),
    }


def _artifact_from_manifest(
    record: Mapping[str, Any],
    selector: str,
) -> BulkArtifact | None:
    selector_key = selector.strip().casefold()
    for data in record["manifest"]["artifacts"]:
        aliases = {
            str(data["artifact_id"]).casefold(),
            str(data["filename"]).casefold(),
            Path(str(data["filename"])).stem.casefold(),
        }
        if selector_key in aliases:
            return BulkArtifact(
                artifact_id=data["artifact_id"],
                url=data["url"],
                filename=data["filename"],
                media_type=data.get("media_type"),
                archive_format=data.get("archive_format"),
                expected_size=data.get("expected_size"),
                expected_sha256=data.get("expected_sha256"),
                etag=data.get("etag"),
                last_modified=data.get("last_modified"),
                metadata=data.get("metadata") or {},
            )
    return None


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in (
        "year",
        "group",
        "artifact",
        "destination",
        "range_bytes",
        "expected_sha256",
        "max_download_bytes",
        "resume",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = value
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(operation=args.command, parameters=parameters),
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


def _local_failure(
    query: PublicRecordsQuery,
    error: OSError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="local_io_error",
                message=str(error),
                category="local_io",
                retryable=False,
            )
        ],
    )


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    manifest_client: HCADManifestClient | None = None,
    bulk_client: BulkTransferClient | None = None,
) -> PublicRecordsResult:
    """Execute one operation and return the shared public-record envelope."""
    query = build_query(args)
    try:
        if access_contract is None:
            _access_contract(args)
        source_client = manifest_client or _manifest_client(args)

        if args.command == "list":
            result = PublicRecordsResult.success(
                query,
                source_client.list_tax_years(),
            )
        else:
            rows = source_client.downloads(args.year, args.group)
            if not rows:
                result = PublicRecordsResult.success(query, [])
            else:
                certification = source_client.certification(args.year)
                release = normalize_release(
                    args.year,
                    args.group,
                    certification,
                    rows,
                )
                if args.command == "manifest":
                    result = PublicRecordsResult.success(query, [release])
                else:
                    artifact = _artifact_from_manifest(release, args.artifact)
                    if artifact is None:
                        result = PublicRecordsResult.success(query, [])
                    elif args.command == "probe":
                        probe = (bulk_client or _bulk_client(args)).probe(
                            artifact,
                            sample_bytes=args.range_bytes,
                        )
                        result = PublicRecordsResult.success(
                            query,
                            [
                                {
                                    **release,
                                    "selected_artifact": artifact.to_dict(),
                                    "probe": probe.to_dict(),
                                }
                            ],
                        )
                    elif args.command == "dry-run":
                        destination = Path(args.destination)
                        if destination.exists() and destination.is_dir():
                            destination = destination / artifact.filename
                        result = PublicRecordsResult.success(
                            query,
                            [
                                {
                                    **release,
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
                        download = (bulk_client or _bulk_client(args)).download(
                            artifact,
                            args.destination,
                            resume=args.resume,
                            max_bytes=args.max_download_bytes,
                        )
                        result = PublicRecordsResult.success(
                            query,
                            [
                                {
                                    **release,
                                    "selected_artifact": artifact.to_dict(),
                                    "download": download.to_dict(),
                                }
                            ],
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
    except OSError as error:
        result = _local_failure(query, error)
    except (ValueError, TypeError, KeyError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="hcad_manifest_changed",
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
    log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"HCAD property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"HCAD property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if "tax_year" in record:
            summary = f"  {record['tax_year']}"
            if record.get("group"):
                summary += f" | {record['group']}"
            if record.get("canonical_ref"):
                summary += f" | {record['canonical_ref']}"
            print(summary)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_source_args(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--retry-attempts", type=int, default=3)


def _add_release_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--group",
        choices=tuple(GROUPS),
        default="real-property",
    )
    _add_source_args(parser)


def _add_transfer_args(parser: argparse.ArgumentParser) -> None:
    _add_release_args(parser)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="Start a new partial transfer",
    )
    parser.set_defaults(resume=True)
    parser.add_argument("--max-download-bytes", type=int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query official Harris Central Appraisal District bulk releases"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="List tax years published by HCAD")
    _add_source_args(listing)
    add_output_args(listing)

    manifest = sub.add_parser(
        "manifest",
        help="Resolve one tax-year release manifest",
    )
    _add_release_args(manifest)
    add_output_args(manifest)

    probe = sub.add_parser(
        "probe",
        help="Make a bounded metadata/range probe of one published artifact",
    )
    _add_release_args(probe)
    probe.add_argument("--artifact", required=True)
    probe.add_argument("--range-bytes", type=int, default=4096)
    add_output_args(probe)

    dry_run = sub.add_parser(
        "dry-run",
        help="Resolve an artifact and show the planned transfer",
    )
    _add_transfer_args(dry_run)
    add_output_args(dry_run)

    download = sub.add_parser(
        "download",
        help="Download and fingerprint one published archive",
    )
    _add_transfer_args(download)
    download.add_argument("--expected-sha256")
    download.add_argument("--chunk-size", type=int, default=1024 * 1024)
    add_output_args(download)
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    for name in (
        "year",
        "timeout",
        "retry_attempts",
        "chunk_size",
        "max_download_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "range_bytes", 0) < 0:
        parser.error("--range-bytes must not be negative")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
