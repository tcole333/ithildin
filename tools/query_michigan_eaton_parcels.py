#!/usr/bin/env python3
"""Query Eaton County's official ArcGIS parcel shapefile snapshot.

The ArcGIS item is a downloadable county snapshot rather than a hosted query
layer.  This adapter therefore separates live item metadata and transfer
operations from deterministic local DBF inspection and search.

Examples:
    uv run python tools/query_michigan_eaton_parcels.py metadata --output /tmp/eaton.json
    uv run python tools/query_michigan_eaton_parcels.py probe --output /tmp/eaton-probe.json
    uv run python tools/query_michigan_eaton_parcels.py download \
        --destination /tmp/eaton --inspect --output /tmp/eaton-download.json
    uv run python tools/query_michigan_eaton_parcels.py search \
        /tmp/eaton/TaxParcel.zip "Smith" --field owner --output /tmp/eaton-search.json
"""

from __future__ import annotations

import argparse
import base64
import codecs
import contextlib
import html
import json
import re
import struct
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping, Sequence

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        ArchiveInspection,
        ArchiveSafetyPolicy,
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        file_sha256,
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
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        ArchiveInspection,
        ArchiveSafetyPolicy,
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        file_sha256,
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
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-mi-eaton-county-parcel-snapshot"
STATE_CODE = "MI"
STATE_FIPS = "26"
COUNTY_FIPS = "26045"
COUNTY_NAME = "Eaton County"

ITEM_ID = "494eb27635154a979d88f4bd83783dd1"
ITEM_API_URL = f"https://www.arcgis.com/sharing/rest/content/items/{ITEM_ID}"
ITEM_DATA_URL = f"{ITEM_API_URL}/data"
ITEM_PAGE_URL = f"https://www.arcgis.com/home/item.html?id={ITEM_ID}"
DTMB_DIRECTORY_URL = (
    "https://www.michigan.gov/dtmb/services/maps/mgf-data-hub/"
    "boundaries-and-mgf/tax-parcels"
)
BSA_HOME_URL = "https://bsaonline.com/"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.1
DEFAULT_CHUNK_SIZE = 1024 * 1024
CURSOR_PREFIX = "eaton-dbf:v1:"

EXPECTED_ITEM_IDENTITY = {
    "id": ITEM_ID,
    "type": "Shapefile",
    "owner": "EatonCounty_GIS",
    "access": "public",
    "name": "TaxParcel.zip",
}
PUBLISHER_DECLARED_FIELDS = ("PARCELID", "BSAONLINE")
OWNER_FIELDS = ("OWNERNME1", "OWNERNME2")
PARCEL_FIELDS = ("PARCELID", "LPARCEL", "LOWPARCELI")
ADDRESS_FIELDS = ("SITEADDRES",)
ASSESSMENT_FIELDS = ("CNTASSDVAL", "CNTTXBLVAL")
SEARCHABLE_ANY_FIELDS = (
    *PARCEL_FIELDS,
    "CNVYNAME",
    *ADDRESS_FIELDS,
    "ZONING_COD",
    "ZONING_DES",
    "SCHLDSCRP",
    "CLASSCD",
    "CLASSDSCRP",
    *OWNER_FIELDS,
    "BSAONLINE",
)

SOURCE_WARNINGS = (
    "This is a county-published snapshot. Preserve the ArcGIS modified marker, "
    "DBF header date, and artifact digest with derived records.",
    "The ArcGIS description says the shapefile contains geometry, a parcel "
    "identifier, and a current-information URL; inspect each downloaded DBF "
    "before relying on additional owner or assessment columns.",
    "Published parcel polygons are approximate mapping geometry. Recorded "
    "instruments and surveys remain separate sources for legal boundaries and title.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Eaton County Parcel Shapefile",
    source_role="county_parcel_geometry_and_assessment_snapshot_bulk",
    base_url=ITEM_PAGE_URL,
    dataset_id=ITEM_ID,
    metadata={
        "authority": "County of Eaton, Michigan",
        "operator": "Eaton County GIS",
        "official_arcgis_item": ITEM_API_URL,
        "official_download": ITEM_DATA_URL,
        "state_directory": DTMB_DIRECTORY_URL,
        "coverage": COUNTY_NAME,
        "release_kind": "snapshot",
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_FIPS,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
    metadata={"state_fips": STATE_FIPS},
)


class EatonParcelError(RuntimeError):
    """Local selection or artifact error with result-envelope semantics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        category: str = "source_artifact",
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


@dataclass(frozen=True)
class DBFField:
    name: str
    field_type: str
    length: int
    decimal_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.field_type,
            "length": self.length,
            "decimal_count": self.decimal_count,
        }


@dataclass(frozen=True)
class DBFSchema:
    member_name: str
    version: int
    last_update: str | None
    record_count: int
    header_length: int
    record_length: int
    language_driver: int
    encoding: str
    fields: tuple[DBFField, ...]

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    @property
    def field_lookup(self) -> dict[str, str]:
        return {field.name.casefold(): field.name for field in self.fields}

    @property
    def schema_fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "dbf_version": self.version,
                "record_length": self.record_length,
                "encoding": self.encoding,
                "fields": [field.to_dict() for field in self.fields],
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_name": self.member_name,
            "version": self.version,
            "last_update": self.last_update,
            "record_count": self.record_count,
            "header_length": self.header_length,
            "record_length": self.record_length,
            "language_driver": self.language_driver,
            "encoding": self.encoding,
            "fields": [field.to_dict() for field in self.fields],
            "schema_fingerprint": self.schema_fingerprint,
        }


@dataclass(frozen=True)
class LocalDatasetInspection:
    path: str
    artifact_sha256: str
    archive: Mapping[str, Any] | None
    dbf: DBFSchema
    shapefile: Mapping[str, Any] | None
    projection_wkt: str | None
    compatibility: Mapping[str, Any]
    schema_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "artifact_sha256": self.artifact_sha256,
            "archive": dict(self.archive) if self.archive is not None else None,
            "dbf": self.dbf.to_dict(),
            "shapefile": (
                dict(self.shapefile) if self.shapefile is not None else None
            ),
            "projection_wkt": self.projection_wkt,
            "compatibility": dict(self.compatibility),
            "schema_fingerprint": self.schema_fingerprint,
        }


class EatonArcGISItemClient(ArcGISRESTClient):
    """Fetch and validate the official Eaton County ArcGIS item."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
        transport: Any | None = None,
    ) -> None:
        super().__init__(
            ITEM_API_URL,
            page_size=1,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
            transport=transport,
        )

    def fetch_item(self) -> Mapping[str, Any]:
        payload = self._request_json(ITEM_API_URL, params={"f": "json"})
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Eaton County returned invalid ArcGIS item metadata",
                url=ITEM_API_URL,
                details={"response": payload},
            )
        _validate_item(payload)
        return dict(payload)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _html_text(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    without_tags = re.sub(r"<[^>]+>", " ", html.unescape(text))
    return _clean_text(without_tags)


def _epoch_iso(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _validate_item(item: Mapping[str, Any]) -> None:
    identity = {
        key: item.get(key)
        for key in ("id", "type", "owner", "access", "name")
    }
    if identity != EXPECTED_ITEM_IDENTITY:
        raise SourceSchemaError(
            "Eaton County ArcGIS item identity changed",
            url=ITEM_API_URL,
            details={
                "expected": EXPECTED_ITEM_IDENTITY,
                "observed": identity,
            },
        )
    for field_name in ("modified", "size"):
        value = item.get(field_name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise SourceSchemaError(
                f"Eaton County ArcGIS item lacks a valid {field_name} marker",
                url=ITEM_API_URL,
                details={field_name: value},
            )
    if not _clean_text(item.get("description")):
        raise SourceSchemaError(
            "Eaton County ArcGIS item lacks its dataset description",
            url=ITEM_API_URL,
        )
    if not _clean_text(item.get("licenseInfo")):
        raise SourceSchemaError(
            "Eaton County ArcGIS item lacks its published license information",
            url=ITEM_API_URL,
        )


def _item_artifact(item: Mapping[str, Any]) -> BulkArtifact:
    _validate_item(item)
    return BulkArtifact(
        artifact_id="eaton-tax-parcel-shapefile",
        url=ITEM_DATA_URL,
        filename=str(item["name"]),
        media_type="application/zip",
        archive_format="zip",
        expected_size=int(item["size"]),
        last_modified=_epoch_iso(int(item["modified"])),
        metadata={
            "arcgis_item_id": ITEM_ID,
            "arcgis_item_page": ITEM_PAGE_URL,
            "publisher": "County of Eaton, Michigan",
            "attribution": item.get("accessInformation"),
        },
    )


def _item_manifest(item: Mapping[str, Any]) -> BulkDatasetManifest:
    artifact = _item_artifact(item)
    modified = int(item["modified"])
    return BulkDatasetManifest(
        source_id=SOURCE_ID,
        dataset_id=ITEM_ID,
        release=BulkReleaseMetadata(
            release_id=f"{ITEM_ID}:{modified}",
            kind="snapshot",
            effective_at=_epoch_iso(modified),
            coverage={
                "jurisdiction_geoid": COUNTY_FIPS,
                "jurisdiction_name": COUNTY_NAME,
            },
        ),
        artifacts=(artifact,),
        schema={
            "container": "zip",
            "declared_dataset_type": item.get("type"),
            "publisher_declared_attribute_scope": [
                "parcel_geometry",
                "parcel_identifier",
                "current_information_url",
            ],
            "local_inspection_required_for_current_dbf_fields": True,
        },
        metadata={
            "item_identity": dict(EXPECTED_ITEM_IDENTITY),
            "item_title": item.get("title"),
            "item_description": item.get("description"),
            "item_license_info_html": item.get("licenseInfo"),
            "item_attribution": item.get("accessInformation"),
            "item_created": item.get("created"),
            "item_modified": modified,
        },
    )


def _source_record() -> dict[str, Any]:
    return {
        "canonical_ref": f"MI-EATON-PARCEL-SOURCE:{ITEM_ID}",
        "source_id": SOURCE_ID,
        "record_kind": "source_description",
        "jurisdiction": {
            "county_geoid": COUNTY_FIPS,
            "county_name": COUNTY_NAME,
            "state_code": STATE_CODE,
        },
        "official_item_url": ITEM_PAGE_URL,
        "metadata_endpoint": ITEM_API_URL,
        "download_endpoint": ITEM_DATA_URL,
        "operations": [
            "metadata",
            "manifest",
            "probe",
            "download",
            "inspect",
            "search",
        ],
        "search_workflow": (
            "Download once, retain the artifact digest, then search the DBF "
            "inside the ZIP by parcel, owner, address, or any available field."
        ),
        "snapshot_semantics": {
            "release_kind": "county_snapshot",
            "assessment_year": "not_declared_in_current_dbf",
            "owner_fields": "assessment_snapshot_names_not_title_determination",
            "geometry": "approximate_county_mapping_polygons",
        },
        "source_url": ITEM_PAGE_URL,
    }


def _alternative_records() -> list[dict[str, Any]]:
    return [
        {
            "canonical_ref": "MI-EATON-PROPERTY-COMPLEMENT:BSA",
            "source_id": SOURCE_ID,
            "record_kind": "official_complement",
            "complement_id": "bsa-current-detail",
            "name": "BS&A Online current parcel detail",
            "url": BSA_HOME_URL,
            "role": (
                "The DBF's BSAOnline value is the record-specific current-detail "
                "route for a parcel."
            ),
            "access_observation": (
                "Known parcel detail routes are directly readable in a public "
                "session; fresh generic searches may present human verification."
            ),
        },
        {
            "canonical_ref": "MI-EATON-PROPERTY-COMPLEMENT:DTMB",
            "source_id": SOURCE_ID,
            "record_kind": "official_complement",
            "complement_id": "michigan-county-route-directory",
            "name": "Michigan DTMB county tax-parcel directory",
            "url": DTMB_DIRECTORY_URL,
            "role": "State-published provenance for the Eaton County source route.",
        },
    ]


def _metadata_record(
    item: Mapping[str, Any],
    manifest: BulkDatasetManifest,
) -> dict[str, Any]:
    modified = int(item["modified"])
    return {
        "canonical_ref": f"MI-EATON-PARCEL-METADATA:{modified}",
        "source_id": SOURCE_ID,
        "record_kind": "bulk_dataset_metadata",
        "jurisdiction": {
            "county_geoid": COUNTY_FIPS,
            "county_name": COUNTY_NAME,
            "state_code": STATE_CODE,
        },
        "item": {
            key: item.get(key)
            for key in (
                "id",
                "owner",
                "orgId",
                "created",
                "modified",
                "name",
                "title",
                "type",
                "typeKeywords",
                "description",
                "tags",
                "snippet",
                "access",
                "size",
                "accessInformation",
                "licenseInfo",
            )
        },
        "release": manifest.release.to_dict(),
        "artifact": manifest.artifacts[0].to_dict(),
        "license": {
            "published_html": item.get("licenseInfo"),
            "published_text": _html_text(item.get("licenseInfo")),
            "attribution": item.get("accessInformation"),
            "item_page": ITEM_PAGE_URL,
        },
        "publisher_declared_attribute_scope": {
            "description": item.get("description"),
            "roles": [
                "parcel_geometry",
                "parcel_identifier",
                "current_information_url",
            ],
        },
        "current_artifact_attribute_scope": {
            "status": "inspect_downloaded_dbf",
            "reason": (
                "The live item description and the current DBF schema are "
                "preserved separately so additional snapshot fields are not "
                "mistaken for an evergreen publication promise."
            ),
        },
        "schema_fingerprint": manifest.schema_fingerprint,
        "manifest_fingerprint": manifest.manifest_fingerprint,
        "source_url": ITEM_PAGE_URL,
    }


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
        max_compression_ratio=getattr(args, "max_compression_ratio", None),
    )


def _dbf_date(header: bytes) -> str | None:
    year = 1900 + header[1]
    month = header[2]
    day = header[3]
    try:
        return datetime(year, month, day, tzinfo=timezone.utc).date().isoformat()
    except ValueError:
        return None


def _parse_dbf_header(
    stream: BinaryIO,
    *,
    member_name: str,
    member_size: int,
    encoding: str,
) -> DBFSchema:
    header = stream.read(32)
    if len(header) != 32:
        raise EatonParcelError(
            "eaton_dbf_header_truncated",
            "Eaton parcel DBF header is truncated",
            details={"member": member_name, "bytes_read": len(header)},
        )
    version = header[0]
    record_count = struct.unpack("<I", header[4:8])[0]
    header_length = struct.unpack("<H", header[8:10])[0]
    record_length = struct.unpack("<H", header[10:12])[0]
    language_driver = header[29]
    if header_length < 33 or record_length < 2 or header_length > member_size:
        raise EatonParcelError(
            "eaton_dbf_header_invalid",
            "Eaton parcel DBF declares invalid header or record lengths",
            details={
                "member": member_name,
                "member_size": member_size,
                "header_length": header_length,
                "record_length": record_length,
            },
        )
    declared_records_end = header_length + record_count * record_length
    if declared_records_end > member_size:
        raise EatonParcelError(
            "eaton_dbf_records_truncated",
            "Eaton parcel DBF is shorter than its declared record table",
            details={
                "member": member_name,
                "member_size": member_size,
                "declared_records_end": declared_records_end,
            },
        )

    fields: list[DBFField] = []
    consumed = 32
    while consumed < header_length:
        first = stream.read(1)
        consumed += 1
        if first == b"\r":
            break
        remainder = stream.read(31)
        consumed += len(remainder)
        if len(remainder) != 31:
            raise EatonParcelError(
                "eaton_dbf_field_descriptor_truncated",
                "Eaton parcel DBF field descriptor is truncated",
                details={"member": member_name},
            )
        descriptor = first + remainder
        name = descriptor[:11].split(b"\x00", 1)[0].decode(
            "ascii",
            errors="strict",
        )
        field_type = chr(descriptor[11])
        length = descriptor[16]
        decimals = descriptor[17]
        if not name or length <= 0:
            raise EatonParcelError(
                "eaton_dbf_field_descriptor_invalid",
                "Eaton parcel DBF contains an invalid field descriptor",
                details={
                    "member": member_name,
                    "field_name": name,
                    "field_length": length,
                },
            )
        fields.append(
            DBFField(
                name=name,
                field_type=field_type,
                length=length,
                decimal_count=decimals,
            )
        )
    else:
        raise EatonParcelError(
            "eaton_dbf_field_terminator_missing",
            "Eaton parcel DBF header lacks its field terminator",
            details={"member": member_name},
        )

    if consumed < header_length:
        padding = stream.read(header_length - consumed)
        if len(padding) != header_length - consumed:
            raise EatonParcelError(
                "eaton_dbf_header_truncated",
                "Eaton parcel DBF header padding is truncated",
                details={"member": member_name},
            )
    expected_record_length = 1 + sum(field.length for field in fields)
    if expected_record_length != record_length:
        raise EatonParcelError(
            "eaton_dbf_record_layout_changed",
            "Eaton parcel DBF record length does not match its fields",
            details={
                "member": member_name,
                "declared_record_length": record_length,
                "field_record_length": expected_record_length,
            },
        )
    names = [field.name.casefold() for field in fields]
    if len(names) != len(set(names)):
        raise EatonParcelError(
            "eaton_dbf_duplicate_fields",
            "Eaton parcel DBF contains duplicate field names",
            details={"member": member_name},
        )
    return DBFSchema(
        member_name=member_name,
        version=version,
        last_update=_dbf_date(header),
        record_count=record_count,
        header_length=header_length,
        record_length=record_length,
        language_driver=language_driver,
        encoding=encoding,
        fields=tuple(fields),
    )


def _zip_members_by_suffix(
    archive: zipfile.ZipFile,
    suffix: str,
) -> list[zipfile.ZipInfo]:
    suffix = suffix.casefold()
    return [
        info
        for info in archive.infolist()
        if not info.is_dir() and Path(info.filename).suffix.casefold() == suffix
    ]


def _zip_text(
    archive: zipfile.ZipFile,
    suffix: str,
    *,
    default: str | None = None,
) -> str | None:
    members = _zip_members_by_suffix(archive, suffix)
    if not members:
        return default
    if len(members) != 1:
        raise EatonParcelError(
            "eaton_archive_ambiguous_members",
            f"Eaton parcel archive contains multiple {suffix} members",
            details={"members": [member.filename for member in members]},
        )
    return archive.read(members[0]).decode("utf-8-sig", errors="replace").strip()


def _encoding_from_cpg(value: str | None) -> str:
    candidate = _clean_text(value) or "cp1252"
    aliases = {
        "65001": "utf-8",
        "utf8": "utf-8",
        "ansi 1252": "cp1252",
        "1252": "cp1252",
    }
    candidate = aliases.get(candidate.casefold(), candidate)
    try:
        return codecs.lookup(candidate).name
    except LookupError as error:
        raise EatonParcelError(
            "eaton_dbf_encoding_unknown",
            "Eaton parcel archive declares an unknown DBF encoding",
            details={"cpg": value},
        ) from error


@contextlib.contextmanager
def _open_dbf(
    path: Path,
    *,
    member_name: str | None = None,
) -> Iterator[tuple[BinaryIO, int, str, str]]:
    if path.suffix.casefold() == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = _zip_members_by_suffix(archive, ".dbf")
            if member_name is not None:
                members = [member for member in members if member.filename == member_name]
            if len(members) != 1:
                raise EatonParcelError(
                    "eaton_archive_dbf_count",
                    "Eaton parcel archive must contain exactly one DBF",
                    details={"members": [member.filename for member in members]},
                )
            cpg = _zip_text(archive, ".cpg")
            encoding = _encoding_from_cpg(cpg)
            member = members[0]
            with archive.open(member) as stream:
                yield stream, member.file_size, member.filename, encoding
        return
    if path.suffix.casefold() != ".dbf":
        raise EatonParcelError(
            "eaton_artifact_type",
            "Local Eaton search accepts a .zip shapefile archive or .dbf file",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
            details={"path": str(path)},
        )
    with path.open("rb") as stream:
        yield stream, path.stat().st_size, path.name, "cp1252"


def _shapefile_header(data: bytes, member_name: str) -> dict[str, Any]:
    if len(data) < 100:
        raise EatonParcelError(
            "eaton_shapefile_header_truncated",
            "Eaton parcel shapefile header is truncated",
            details={"member": member_name, "bytes_read": len(data)},
        )
    file_code = struct.unpack(">i", data[0:4])[0]
    file_length_words = struct.unpack(">i", data[24:28])[0]
    version = struct.unpack("<i", data[28:32])[0]
    shape_type = struct.unpack("<i", data[32:36])[0]
    xmin, ymin, xmax, ymax = struct.unpack("<4d", data[36:68])
    if file_code != 9994 or version != 1000:
        raise EatonParcelError(
            "eaton_shapefile_header_invalid",
            "Eaton parcel artifact is not a compatible Esri shapefile",
            details={
                "member": member_name,
                "file_code": file_code,
                "version": version,
            },
        )
    return {
        "member_name": member_name,
        "file_code": file_code,
        "file_length_bytes": file_length_words * 2,
        "version": version,
        "shape_type": shape_type,
        "shape_type_role": (
            "polygon" if shape_type in {5, 15, 25} else "other"
        ),
        "bounds": {
            "xmin": xmin,
            "ymin": ymin,
            "xmax": xmax,
            "ymax": ymax,
        },
    }


def _compatibility(schema: DBFSchema) -> dict[str, Any]:
    lookup = schema.field_lookup

    def present(names: Sequence[str]) -> list[str]:
        return [lookup[name.casefold()] for name in names if name.casefold() in lookup]

    publisher_fields = present(PUBLISHER_DECLARED_FIELDS)
    owner_fields = present(OWNER_FIELDS)
    assessment_fields = present(ASSESSMENT_FIELDS)
    address_fields = present(ADDRESS_FIELDS)
    expanded = [*owner_fields, *assessment_fields, *address_fields]
    missing_publisher = [
        name for name in PUBLISHER_DECLARED_FIELDS if name.casefold() not in lookup
    ]
    return {
        "search_ready": not missing_publisher,
        "missing_publisher_declared_fields": missing_publisher,
        "publisher_declared_fields_observed": publisher_fields,
        "verified_snapshot_roles": {
            "parcel_identifier": present(PARCEL_FIELDS),
            "situs_address": address_fields,
            "assessment_roll_owner_names": owner_fields,
            "county_assessed_and_taxable_values": assessment_fields,
            "parcel_detail_link": present(("BSAONLINE",)),
            "approximate_polygon_geometry": True,
        },
        "publisher_description_comparison": {
            "publisher_declared_scope": [
                "parcel_geometry",
                "parcel_identifier",
                "current_information_url",
            ],
            "additional_current_dbf_fields_observed": expanded,
            "status": (
                "current_dbf_contains_additional_snapshot_fields"
                if expanded
                else "matches_declared_minimum_scope"
            ),
        },
    }


def inspect_local_dataset(
    path: Path | str,
    *,
    policy: ArchiveSafetyPolicy | None = None,
) -> LocalDatasetInspection:
    artifact_path = Path(path).expanduser().resolve()
    if not artifact_path.is_file():
        raise EatonParcelError(
            "eaton_artifact_missing",
            "Eaton parcel artifact does not exist or is not a file",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
            details={"path": str(artifact_path)},
        )

    archive_inspection: ArchiveInspection | None = None
    shapefile: dict[str, Any] | None = None
    projection_wkt: str | None = None
    dbf_member: str | None = None
    if artifact_path.suffix.casefold() == ".zip":
        archive_inspection = inspect_zip(artifact_path, policy=policy)
        with zipfile.ZipFile(artifact_path) as archive:
            dbf_members = _zip_members_by_suffix(archive, ".dbf")
            shp_members = _zip_members_by_suffix(archive, ".shp")
            if len(dbf_members) != 1 or len(shp_members) != 1:
                raise EatonParcelError(
                    "eaton_archive_dataset_count",
                    "Eaton parcel archive must contain one DBF and one shapefile",
                    details={
                        "dbf_members": [member.filename for member in dbf_members],
                        "shapefile_members": [
                            member.filename for member in shp_members
                        ],
                    },
                )
            dbf_member = dbf_members[0].filename
            dbf_stem = Path(dbf_member).stem.casefold()
            shp_stem = Path(shp_members[0].filename).stem.casefold()
            if dbf_stem != shp_stem:
                raise EatonParcelError(
                    "eaton_archive_dataset_mismatch",
                    "Eaton parcel DBF and shapefile names do not match",
                    details={
                        "dbf_member": dbf_member,
                        "shapefile_member": shp_members[0].filename,
                    },
                )
            shapefile = _shapefile_header(
                archive.read(shp_members[0])[:100],
                shp_members[0].filename,
            )
            projection_wkt = _zip_text(archive, ".prj")

    with _open_dbf(artifact_path, member_name=dbf_member) as (
        stream,
        size,
        member_name,
        encoding,
    ):
        dbf = _parse_dbf_header(
            stream,
            member_name=member_name,
            member_size=size,
            encoding=encoding,
        )

    compatibility = _compatibility(dbf)
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "dbf": {
                "version": dbf.version,
                "record_length": dbf.record_length,
                "encoding": dbf.encoding,
                "fields": [field.to_dict() for field in dbf.fields],
            },
            "shapefile": shapefile,
            "projection_wkt": projection_wkt,
        }
    )
    return LocalDatasetInspection(
        path=str(artifact_path),
        artifact_sha256=(
            archive_inspection.archive_sha256
            if archive_inspection is not None
            else file_sha256(artifact_path)
        ),
        archive=(
            archive_inspection.to_dict()
            if archive_inspection is not None
            else None
        ),
        dbf=dbf,
        shapefile=shapefile,
        projection_wkt=projection_wkt,
        compatibility=compatibility,
        schema_fingerprint=schema_fingerprint,
    )


def _decode_field(raw: bytes, field: DBFField, encoding: str) -> Any:
    field_type = field.field_type.upper()
    if field_type in {"C", "M"}:
        return raw.decode(encoding, errors="replace").replace("\x00", "").strip() or None
    text = raw.decode("ascii", errors="replace").strip()
    if not text or set(text) <= {"*"}:
        return None
    if field_type in {"N", "F"}:
        try:
            return float(text) if field.decimal_count else int(text)
        except ValueError:
            return text
    if field_type == "L":
        if text[:1].upper() in {"T", "Y"}:
            return True
        if text[:1].upper() in {"F", "N"}:
            return False
        return None
    if field_type == "D" and re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date().isoformat()
        except ValueError:
            return text
    if field_type == "I" and len(raw) == 4:
        return struct.unpack("<i", raw)[0]
    return text


def _dbf_rows(stream: BinaryIO, schema: DBFSchema) -> Iterator[tuple[int, dict[str, Any]]]:
    for row_index in range(schema.record_count):
        raw_record = stream.read(schema.record_length)
        if len(raw_record) != schema.record_length:
            raise EatonParcelError(
                "eaton_dbf_record_truncated",
                "Eaton parcel DBF record table ended unexpectedly",
                details={
                    "member": schema.member_name,
                    "row_index": row_index,
                },
            )
        if raw_record[:1] == b"*":
            continue
        if raw_record[:1] != b" ":
            raise EatonParcelError(
                "eaton_dbf_record_marker",
                "Eaton parcel DBF contains an unknown record marker",
                details={
                    "member": schema.member_name,
                    "row_index": row_index,
                    "marker": raw_record[:1].hex(),
                },
            )
        values: dict[str, Any] = {}
        offset = 1
        for field in schema.fields:
            raw_value = raw_record[offset : offset + field.length]
            offset += field.length
            values[field.name] = _decode_field(raw_value, field, schema.encoding)
        yield row_index, values


def _row_value(
    row: Mapping[str, Any],
    schema: DBFSchema,
    *names: str,
) -> Any:
    lookup = schema.field_lookup
    for name in names:
        observed = lookup.get(name.casefold())
        if observed is not None and row.get(observed) not in (None, ""):
            return row.get(observed)
    return None


def _search_fields(field: str, schema: DBFSchema) -> tuple[str, ...]:
    candidates = {
        "parcel": PARCEL_FIELDS,
        "owner": OWNER_FIELDS,
        "address": ADDRESS_FIELDS,
        "bsa-url": ("BSAONLINE",),
        "any": SEARCHABLE_ANY_FIELDS,
    }[field]
    lookup = schema.field_lookup
    observed = tuple(
        lookup[name.casefold()] for name in candidates if name.casefold() in lookup
    )
    if not observed:
        raise EatonParcelError(
            "eaton_search_field_unavailable",
            f"Eaton parcel DBF has no fields for {field!r} search",
            details={
                "requested_field": field,
                "available_fields": list(schema.field_names),
            },
        )
    return observed


def _parcel_token(value: Any) -> str:
    return re.sub(r"[^0-9A-Z]", "", str(value or "").upper())


def _matches(
    row: Mapping[str, Any],
    *,
    fields: Sequence[str],
    query: str,
    match: str,
    parcel_search: bool,
) -> bool:
    query_text = " ".join(query.split()).casefold()
    query_parcel = _parcel_token(query)
    for field in fields:
        value = _clean_text(row.get(field))
        if not value:
            continue
        candidate = value.casefold()
        if match == "exact" and candidate == query_text:
            return True
        if match == "prefix" and candidate.startswith(query_text):
            return True
        if match == "contains" and query_text in candidate:
            return True
        if parcel_search and query_parcel:
            candidate_parcel = _parcel_token(value)
            if match == "exact" and candidate_parcel == query_parcel:
                return True
            if match == "prefix" and candidate_parcel.startswith(query_parcel):
                return True
            if match == "contains" and query_parcel in candidate_parcel:
                return True
    return False


def _cursor_encode(
    *,
    artifact_sha256: str,
    criteria_fingerprint: str,
    match_offset: int,
) -> str:
    payload = canonical_json(
        {
            "artifact_sha256": artifact_sha256,
            "criteria_fingerprint": criteria_fingerprint,
            "match_offset": match_offset,
        }
    ).encode()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _cursor_decode(
    cursor: str | None,
    *,
    artifact_sha256: str,
    criteria_fingerprint: str,
) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise EatonParcelError(
            "eaton_cursor_invalid",
            "Eaton parcel cursor has an invalid prefix",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as error:
        raise EatonParcelError(
            "eaton_cursor_invalid",
            "Eaton parcel cursor is malformed",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        ) from error
    if not isinstance(payload, Mapping):
        raise EatonParcelError(
            "eaton_cursor_invalid",
            "Eaton parcel cursor payload is invalid",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    if payload.get("artifact_sha256") != artifact_sha256:
        raise EatonParcelError(
            "eaton_cursor_snapshot_changed",
            "Eaton parcel cursor belongs to a different artifact snapshot",
            status=ResultStatus.SOURCE_CHANGED,
            category="pagination",
        )
    if payload.get("criteria_fingerprint") != criteria_fingerprint:
        raise EatonParcelError(
            "eaton_cursor_query_changed",
            "Eaton parcel cursor belongs to different search criteria",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    offset = payload.get("match_offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise EatonParcelError(
            "eaton_cursor_invalid",
            "Eaton parcel cursor offset is invalid",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    return offset


def _record_from_row(
    row: Mapping[str, Any],
    *,
    row_index: int,
    inspection: LocalDatasetInspection,
) -> dict[str, Any]:
    schema = inspection.dbf
    native_parcel_id = _clean_text(
        _row_value(row, schema, "LPARCEL", "PARCELID")
    )
    if not native_parcel_id:
        raise EatonParcelError(
            "eaton_parcel_identifier_missing",
            "Eaton parcel DBF row lacks a parcel identifier",
            details={"row_index": row_index},
        )
    aliases = []
    for field_name in PARCEL_FIELDS:
        value = _clean_text(_row_value(row, schema, field_name))
        if value and value not in aliases and value != native_parcel_id:
            aliases.append(value)

    owners = []
    for field_name in OWNER_FIELDS:
        value = _clean_text(_row_value(row, schema, field_name))
        if value:
            owners.append(
                {
                    "raw_name": value,
                    "source_field": field_name,
                    "role": "assessment_snapshot_owner_name",
                    "confidence": "high",
                }
            )
    situs = _clean_text(_row_value(row, schema, "SITEADDRES"))
    assessed = _row_value(row, schema, "CNTASSDVAL")
    taxable = _row_value(row, schema, "CNTTXBLVAL")
    assessment: dict[str, Any] = {
        "assessed_value": assessed,
        "taxable_value": taxable,
        "assessment_class": _clean_text(_row_value(row, schema, "CLASSCD")),
        "assessment_class_description": _clean_text(
            _row_value(row, schema, "CLASSDSCRP")
        ),
        "tax_year": None,
        "value_units": "USD",
        "source_fields": {
            "assessed_value": "CNTASSDVAL",
            "taxable_value": "CNTTXBLVAL",
        },
    }
    bsa_url = _clean_text(_row_value(row, schema, "BSAONLINE"))
    bing_url = _clean_text(_row_value(row, schema, "BingMap"))
    geometry_available = (
        {
            "artifact_path": inspection.path,
            "shapefile": dict(inspection.shapefile),
            "projection_wkt": inspection.projection_wkt,
            "dbf_record_index": row_index,
            "projection_status": "geometry_not_loaded_by_dbf_search",
        }
        if inspection.shapefile is not None
        else None
    )
    snapshot_date = schema.last_update
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_FIPS,
            "parcel",
            native_parcel_id,
        ),
        "evidence_ref": (
            f"MI-EATON-TAXPARCEL:{inspection.artifact_sha256}:{row_index}"
        ),
        "source_id": SOURCE_ID,
        "record_kind": "parcel_assessment_snapshot",
        "record_type": "eaton_parcel_assessment_snapshot",
        "jurisdiction": {
            "county_geoid": COUNTY_FIPS,
            "county_name": COUNTY_NAME,
            "state_code": STATE_CODE,
        },
        "native_parcel_id": native_parcel_id,
        "alternate_parcel_ids": aliases,
        "conveyance_or_legal_name": _clean_text(
            _row_value(row, schema, "CNVYNAME")
        ),
        "situs_address": (
            {
                "raw": situs,
                "state": STATE_CODE,
                "country": "US",
                "source_field": "SITEADDRES",
            }
            if situs
            else None
        ),
        "owners": owners,
        "assessment": assessment,
        "classification": {
            "code": _clean_text(_row_value(row, schema, "CLASSCD")),
            "description": _clean_text(_row_value(row, schema, "CLASSDSCRP")),
            "zoning_code": _clean_text(_row_value(row, schema, "ZONING_COD")),
            "zoning_description": _clean_text(
                _row_value(row, schema, "ZONING_DES")
            ),
            "school_tax_code": _clean_text(_row_value(row, schema, "SCHLTXCD")),
            "school_description": _clean_text(
                _row_value(row, schema, "SCHLDSCRP")
            ),
        },
        "land": {
            "acreage": _row_value(row, schema, "Acreage"),
            "stated_area": _row_value(row, schema, "STATEDAREA"),
        },
        "taxing_jurisdiction": {
            "code": _clean_text(_row_value(row, schema, "CVTTXCD")),
            "description": _clean_text(_row_value(row, schema, "CVTTXDSCRP")),
            "dda": _clean_text(_row_value(row, schema, "DDA")),
        },
        "source_links": {
            "record": bsa_url,
            "bsa_current_detail": bsa_url,
            "bing_map": bing_url,
        },
        "geometry_available": geometry_available,
        "geometry_role": (
            "approximate_polygon_in_bulk_artifact_not_loaded_by_dbf_search"
            if geometry_available
            else None
        ),
        "snapshot_complete": True,
        "snapshot_completeness": {
            "scope": "all_fields_published_for_this_parcel_in_the_county_dbf",
            "does_not_establish": [
                "legal_boundary",
                "recorded_title",
                "assessment_tax_year_when_not_declared",
            ],
        },
        "source_last_updated": snapshot_date,
        "artifact_snapshot": {
            "path": inspection.path,
            "sha256": inspection.artifact_sha256,
            "dbf_last_update": snapshot_date,
            "dbf_record_index": row_index,
            "dbf_record_count": schema.record_count,
            "schema_fingerprint": inspection.schema_fingerprint,
        },
        "publisher_declared_attribute_scope": [
            "parcel_geometry",
            "parcel_identifier",
            "current_information_url",
        ],
        "current_artifact_verified_roles": inspection.compatibility[
            "verified_snapshot_roles"
        ],
        "schema_fingerprint": inspection.schema_fingerprint,
        "source_url": ITEM_PAGE_URL,
        "raw_attributes": dict(row),
    }


def search_local_dataset(
    path: Path | str,
    query: str,
    *,
    field: str = "any",
    match: str = "contains",
    limit: int = 50,
    cursor: str | None = None,
    policy: ArchiveSafetyPolicy | None = None,
) -> tuple[list[dict[str, Any]], str | None, LocalDatasetInspection]:
    if not _clean_text(query):
        raise EatonParcelError(
            "eaton_query_blank",
            "Eaton parcel search query must not be blank",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    if limit <= 0:
        raise ValueError("limit must be positive")
    inspection = inspect_local_dataset(path, policy=policy)
    if not inspection.compatibility["search_ready"]:
        raise EatonParcelError(
            "eaton_dbf_declared_fields_missing",
            "Eaton parcel DBF lacks publisher-declared identifier or detail-link fields",
            details=dict(inspection.compatibility),
        )
    fields = _search_fields(field, inspection.dbf)
    criteria_fingerprint = sha256_fingerprint(
        {
            "query": " ".join(query.split()).casefold(),
            "field": field,
            "match": match,
        }
    )
    match_offset = _cursor_decode(
        cursor,
        artifact_sha256=inspection.artifact_sha256,
        criteria_fingerprint=criteria_fingerprint,
    )
    matches: list[tuple[int, dict[str, Any]]] = []
    seen_matches = 0
    artifact_path = Path(inspection.path)
    with _open_dbf(
        artifact_path,
        member_name=inspection.dbf.member_name,
    ) as (stream, size, member_name, encoding):
        schema = _parse_dbf_header(
            stream,
            member_name=member_name,
            member_size=size,
            encoding=encoding,
        )
        if schema.schema_fingerprint != inspection.dbf.schema_fingerprint:
            raise EatonParcelError(
                "eaton_dbf_changed_during_search",
                "Eaton parcel DBF schema changed during local search",
                status=ResultStatus.SOURCE_CHANGED,
                category="integrity",
            )
        for row_index, row in _dbf_rows(stream, schema):
            if not _matches(
                row,
                fields=fields,
                query=query,
                match=match,
                parcel_search=field == "parcel",
            ):
                continue
            if seen_matches < match_offset:
                seen_matches += 1
                continue
            matches.append((row_index, row))
            if len(matches) >= limit + 1:
                break
            seen_matches += 1

    has_more = len(matches) > limit
    page = matches[:limit]
    records = [
        _record_from_row(
            row,
            row_index=row_index,
            inspection=inspection,
        )
        for row_index, row in page
    ]
    next_cursor = (
        _cursor_encode(
            artifact_sha256=inspection.artifact_sha256,
            criteria_fingerprint=criteria_fingerprint,
            match_offset=match_offset + limit,
        )
        if has_more
        else None
    )
    return records, next_cursor, inspection


def _query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for field_name in (
        "artifact",
        "field",
        "match",
        "sample_bytes",
        "destination",
    ):
        value = getattr(args, field_name, None)
        if value is not None:
            parameters[field_name] = str(value)
    if getattr(args, "query", None) is not None:
        parameters["query"] = str(args.query)
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
    error: EatonParcelError | PublicRecordsHTTPError | BulkSourceError,
) -> PublicRecordsResult:
    status = getattr(error, "status", getattr(error, "result_status", None))
    if status is None:
        status = ResultStatus.UNAVAILABLE
    return PublicRecordsResult.failure(
        query,
        status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: EatonArcGISItemClient | Any | None = None,
    bulk_client: BulkTransferClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _query(args)
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                [_source_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "alternatives":
            result = PublicRecordsResult.success(
                query,
                _alternative_records(),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "inspect":
            inspection = inspect_local_dataset(
                args.artifact,
                policy=_archive_policy(args),
            )
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "canonical_ref": (
                            f"MI-EATON-PARCEL-INSPECTION:"
                            f"{inspection.artifact_sha256}"
                        ),
                        "source_id": SOURCE_ID,
                        "record_kind": "local_artifact_inspection",
                        "inspection": inspection.to_dict(),
                        "source_url": ITEM_PAGE_URL,
                    }
                ],
                raw_artifact_refs=[inspection.path],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "search":
            records, next_cursor, inspection = search_local_dataset(
                args.artifact,
                args.query,
                field=args.field,
                match=args.match,
                limit=args.limit,
                cursor=args.cursor,
                policy=_archive_policy(args),
            )
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                raw_artifact_refs=[inspection.path],
                warnings=SOURCE_WARNINGS,
            )
        else:
            source_client = client or EatonArcGISItemClient(
                timeout=args.timeout,
                minimum_interval=args.minimum_interval,
                retry_attempts=args.retry_attempts,
            )
            item = source_client.fetch_item()
            manifest = _item_manifest(item)
            if args.command in {"metadata", "manifest"}:
                record = _metadata_record(item, manifest)
                if args.command == "manifest":
                    record = {
                        **record,
                        "record_kind": "bulk_dataset_manifest",
                        "manifest": manifest.to_dict(),
                    }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[ITEM_API_URL],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                transfer = bulk_client or BulkTransferClient(
                    timeout=args.timeout,
                    max_attempts=args.retry_attempts,
                    chunk_size=DEFAULT_CHUNK_SIZE,
                )
                artifact = manifest.artifacts[0]
                probe = transfer.probe(artifact, sample_bytes=args.sample_bytes)
                if probe.format_hint != "zip":
                    raise EatonParcelError(
                        "eaton_download_format_changed",
                        "Eaton County parcel download no longer has a ZIP signature",
                        details={"probe": probe.to_dict()},
                    )
                if (
                    probe.content_length is not None
                    and probe.content_length != artifact.expected_size
                ):
                    raise EatonParcelError(
                        "eaton_download_size_changed",
                        "Eaton County parcel download size differs from item metadata",
                        details={
                            "item_size": artifact.expected_size,
                            "probe_size": probe.content_length,
                        },
                    )
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "canonical_ref": (
                                f"MI-EATON-PARCEL-PROBE:{item['modified']}"
                            ),
                            "source_id": SOURCE_ID,
                            "record_kind": "source_probe",
                            "item": _metadata_record(item, manifest),
                            "artifact_probe": probe.to_dict(),
                            "schema_fingerprint": manifest.schema_fingerprint,
                            "manifest_fingerprint": manifest.manifest_fingerprint,
                            "source_url": ITEM_PAGE_URL,
                        }
                    ],
                    raw_artifact_refs=[ITEM_API_URL, ITEM_DATA_URL],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "download":
                artifact = manifest.artifacts[0]
                if args.expected_sha256:
                    artifact = BulkArtifact(
                        **{
                            **artifact.to_dict(),
                            "expected_sha256": args.expected_sha256,
                        }
                    )
                transfer = bulk_client or BulkTransferClient(
                    timeout=args.timeout,
                    max_attempts=args.retry_attempts,
                    chunk_size=args.chunk_size,
                )
                download = transfer.download(
                    artifact,
                    args.destination,
                    resume=args.resume,
                    max_bytes=args.max_download_bytes,
                )
                record: dict[str, Any] = {
                    "canonical_ref": (
                        f"MI-EATON-PARCEL-DOWNLOAD:{download.sha256}"
                    ),
                    "source_id": SOURCE_ID,
                    "record_kind": "bulk_artifact_download",
                    "item": _metadata_record(item, manifest),
                    "download": download.to_dict(),
                    "source_url": ITEM_PAGE_URL,
                }
                if args.inspect:
                    inspection = inspect_local_dataset(
                        download.path,
                        policy=_archive_policy(args),
                    )
                    record["inspection"] = inspection.to_dict()
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[download.path],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                raise ValueError(f"unsupported Eaton parcel command {args.command}")
    except (EatonParcelError, PublicRecordsHTTPError, BulkSourceError) as error:
        result = _failure(query, error)
    except (OSError, zipfile.BadZipFile) as error:
        wrapped = EatonParcelError(
            "eaton_local_artifact_error",
            f"Could not read Eaton parcel artifact: {error}",
            status=ResultStatus.UNAVAILABLE,
            category="local_artifact",
            details={"artifact": getattr(args, "artifact", None)},
        )
        result = _failure(query, wrapped)

    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        log_search(
            canonical_json(result.query.to_dict()),
            SOURCE_ID,
            result_count,
        )
    return result


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)


def _add_archive_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-archive-members", type=int)
    parser.add_argument("--max-uncompressed-bytes", type=int)
    parser.add_argument("--max-member-uncompressed-bytes", type=int)
    parser.add_argument("--max-compression-ratio", type=float)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect and search Eaton County's official ArcGIS parcel snapshot"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("sources", "Describe source roles and supported operations"),
        ("alternatives", "List official complementary property routes"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        add_output_args(command_parser)

    for command, help_text in (
        ("metadata", "Fetch and validate ArcGIS item metadata"),
        ("manifest", "Build the current deterministic release manifest"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        _add_runtime_args(command_parser)
        add_output_args(command_parser)

    probe = sub.add_parser(
        "probe",
        help="Validate item identity and a bounded ZIP download sample",
    )
    probe.add_argument("--sample-bytes", type=int, default=64)
    _add_runtime_args(probe)
    add_output_args(probe)

    download = sub.add_parser(
        "download",
        help="Download the current ZIP snapshot and optionally inspect it",
    )
    download.add_argument("--destination", required=True)
    download.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    download.add_argument("--expected-sha256")
    download.add_argument("--max-download-bytes", type=int)
    download.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    download.add_argument("--inspect", action="store_true")
    _add_archive_args(download)
    _add_runtime_args(download)
    add_output_args(download)

    inspect_parser = sub.add_parser(
        "inspect",
        help="Inspect a downloaded ZIP or DBF without network access",
    )
    inspect_parser.add_argument("artifact")
    _add_archive_args(inspect_parser)
    add_output_args(inspect_parser)

    search = sub.add_parser(
        "search",
        help="Search a downloaded ZIP or DBF without network access",
    )
    search.add_argument("artifact")
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=("any", "parcel", "owner", "address", "bsa-url"),
        default="any",
    )
    search.add_argument(
        "--match",
        choices=("exact", "prefix", "contains"),
        default="contains",
    )
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--cursor")
    _add_archive_args(search)
    add_output_args(search)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Eaton parcel {args.command} ({result.status.value})",
        result_count=(
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Eaton parcel {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("native_parcel_id")
            or record.get("record_kind")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"  ERROR {error.code}: {error.message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "sample_bytes", 0) < 0:
        parser.error("--sample-bytes must not be negative")
    if getattr(args, "retry_attempts", 1) <= 0:
        parser.error("--retry-attempts must be positive")
    if getattr(args, "chunk_size", 1) <= 0:
        parser.error("--chunk-size must be positive")
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
