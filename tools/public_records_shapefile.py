#!/usr/bin/env python3
"""Decode local parcel shapefiles while preserving source occurrences.

This module handles the byte-level part of official bulk parcel releases.  It
accepts a ZIP archive or a local ``.shp`` sidecar set, validates aligned
SHP/SHX/DBF members, streams one feature at a time, and emits source-occurrence
records.  Parcel identifiers are retained as join candidates; they are not used
as feature identity and repeated or blank values are not discarded.

Coordinates remain in the CRS declared by the source PRJ member.  The project
does not declare a coordinate-transformation dependency, so this decoder does
not silently reproject coordinates.

Examples:
    uv run python tools/public_records_shapefile.py inspect parcels.zip \
        --output /tmp/parcel-shapefile-inspection.json
    uv run python tools/public_records_shapefile.py search parcels.zip 00123 \
        --source-id us-example-parcels --release-id 2026-final \
        --parcel-field PARCELNO --field PARCELNO --match exact \
        --limit 25 --output /tmp/parcel-shapefile-search.json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import codecs
import contextlib
import hashlib
import json
import math
import re
import struct
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        ArchiveInspection,
        ArchiveSafetyPolicy,
        BulkSourceError,
        file_sha256,
        inspect_zip,
    )
    from tools.public_records_contract import canonical_json, sha256_fingerprint
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        ArchiveInspection,
        ArchiveSafetyPolicy,
        BulkSourceError,
        file_sha256,
        inspect_zip,
    )
    from public_records_contract import canonical_json, sha256_fingerprint


SCHEMA_VERSION = "public-records-shapefile/1.0"
CURSOR_PREFIX = "parcel-shapefile:v1:"
DEFAULT_SOURCE_ID = "local-parcel-shapefile"
DEFAULT_RESULT_LIMIT = 50
DEFAULT_SCAN_LIMIT = 100_000
DEFAULT_MAX_RECORD_BYTES = 128 * 1024 * 1024

SHAPE_TYPE_NAMES: dict[int, str] = {
    0: "NullShape",
    1: "Point",
    3: "PolyLine",
    5: "Polygon",
    8: "MultiPoint",
    11: "PointZ",
    13: "PolyLineZ",
    15: "PolygonZ",
    18: "MultiPointZ",
    21: "PointM",
    23: "PolyLineM",
    25: "PolygonM",
    28: "MultiPointM",
}
POINT_TYPES = frozenset({1, 11, 21})
MULTIPOINT_TYPES = frozenset({8, 18, 28})
POLYLINE_TYPES = frozenset({3, 13, 23})
POLYGON_TYPES = frozenset({5, 15, 25})
Z_TYPES = frozenset({11, 13, 15, 18})
M_TYPES = frozenset({21, 23, 25, 28})

# These names identify parcel keys in common official parcel exports.  Generic
# names such as ID, OBJECTID, FID, and GLOBALID are intentionally excluded
# because they normally identify a feature occurrence rather than a parcel.
CONSERVATIVE_PARCEL_FIELDS = (
    "PARCELNO",
    "PARCEL_NO",
    "PARCEL_ID",
    "PARCELID",
    "PARCEL",
    "APN",
    "PIN",
    "MAPTAXLOT",
    "MAP_TAXLOT",
    "TAXLOT",
    "TAX_LOT",
    "PROP_ID",
    "PROPERTY_ID",
    "PROPERTYID",
    "ACCOUNT_NO",
    "ACCOUNTNO",
    "ACCTID",
    "PARID",
)

DBF_LANGUAGE_DRIVERS: dict[int, str] = {
    0x01: "cp437",
    0x02: "cp850",
    0x03: "cp1252",
    0x57: "cp1252",
    0x64: "cp852",
    0x65: "cp866",
    0x66: "cp865",
    0x67: "cp861",
    0x6A: "cp737",
    0x6B: "cp857",
    0x78: "cp950",
    0x79: "cp949",
    0x7A: "cp936",
    0x7B: "cp932",
    0x7C: "cp874",
    0x7D: "cp1255",
    0x7E: "cp1256",
    0xC8: "cp1250",
    0xC9: "cp1251",
    0xCA: "cp1254",
    0xCB: "cp1253",
}


class ParcelShapefileError(ValueError):
    """A local shapefile cannot be decoded under its published structure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": dict(self.details),
        }


def _positive(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _read_exact(
    stream: BinaryIO,
    length: int,
    *,
    code: str,
    message: str,
    details: Mapping[str, Any] | None = None,
) -> bytes:
    data = stream.read(length)
    if len(data) != length:
        observed = dict(details or {})
        observed.update({"expected_bytes": length, "observed_bytes": len(data)})
        raise ParcelShapefileError(code, message, details=observed)
    return data


def _position_stream(
    stream: BinaryIO,
    offset: int,
    *,
    code: str,
    message: str,
    details: Mapping[str, Any],
) -> None:
    if offset < 0:
        raise ValueError("stream offset must be non-negative")
    try:
        observed = stream.seek(offset)
    except (AttributeError, OSError):
        try:
            current = stream.tell()
        except (AttributeError, OSError):
            current = 0
        if current > offset:
            raise ParcelShapefileError(
                code,
                message,
                details={
                    **details,
                    "requested_offset": offset,
                    "current_offset": current,
                },
            )
        remaining = offset - current
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ParcelShapefileError(
                    code,
                    message,
                    details={
                        **details,
                        "requested_offset": offset,
                        "current_offset": offset - remaining,
                    },
                )
            remaining -= len(chunk)
        return
    if observed is not None and observed != offset:
        raise ParcelShapefileError(
            code,
            message,
            details={
                **details,
                "requested_offset": offset,
                "observed_offset": observed,
            },
        )


def _finite(value: float, *, label: str, details: Mapping[str, Any]) -> float:
    if not math.isfinite(value):
        raise ParcelShapefileError(
            "shapefile_nonfinite_coordinate",
            f"Shapefile {label} is not finite",
            details={**details, "value": value},
        )
    return value


def _member_suffix(name: str) -> str:
    return PurePosixPath(name).suffix.casefold()


def _member_stem(name: str) -> str:
    return str(PurePosixPath(name).with_suffix(""))


def _casefold_unique(values: Sequence[str], *, label: str) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for value in values:
        folded = value.casefold()
        previous = lookup.get(folded)
        if previous is not None and previous != value:
            raise ParcelShapefileError(
                "shapefile_member_case_collision",
                f"Artifact contains case-colliding {label}",
                details={"first": previous, "second": value},
            )
        lookup[folded] = value
    return lookup


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    member_size: int
    version: int
    last_update: str | None
    record_count: int
    header_length: int
    record_length: int
    trailing_record_bytes: int
    language_driver: int
    encoding: str
    encoding_source: str
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
                "version": self.version,
                "record_length": self.record_length,
                "trailing_record_bytes": self.trailing_record_bytes,
                "encoding": self.encoding,
                "fields": [field.to_dict() for field in self.fields],
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_name": self.member_name,
            "member_size": self.member_size,
            "version": self.version,
            "last_update": self.last_update,
            "record_count": self.record_count,
            "header_length": self.header_length,
            "record_length": self.record_length,
            "trailing_record_bytes": self.trailing_record_bytes,
            "language_driver": self.language_driver,
            "encoding": self.encoding,
            "encoding_source": self.encoding_source,
            "fields": [field.to_dict() for field in self.fields],
            "schema_fingerprint": self.schema_fingerprint,
        }


@dataclass(frozen=True)
class DBFRecord:
    record_index: int
    deleted: bool
    attributes: Mapping[str, Any]
    raw_text: Mapping[str, str | None]
    trailing_bytes_hex: str | None


@dataclass(frozen=True)
class ShapeHeader:
    member_name: str
    member_size: int
    file_length_bytes: int
    version: int
    shape_type: int
    bounds: tuple[float, float, float, float]
    z_range: tuple[float, float]
    m_range: tuple[float, float]

    @property
    def shape_type_name(self) -> str:
        return SHAPE_TYPE_NAMES.get(self.shape_type, f"Unsupported({self.shape_type})")

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_name": self.member_name,
            "member_size": self.member_size,
            "file_length_bytes": self.file_length_bytes,
            "version": self.version,
            "shape_type": self.shape_type,
            "shape_type_name": self.shape_type_name,
            "bounds": {
                "xmin": self.bounds[0],
                "ymin": self.bounds[1],
                "xmax": self.bounds[2],
                "ymax": self.bounds[3],
            },
            "z_range": {"minimum": self.z_range[0], "maximum": self.z_range[1]},
            "m_range": {"minimum": self.m_range[0], "maximum": self.m_range[1]},
        }


@dataclass(frozen=True)
class ShapeIndexHeader:
    shape_header: ShapeHeader
    record_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.shape_header.to_dict(),
            "record_count": self.record_count,
        }


@dataclass(frozen=True)
class ShapeIndexEntry:
    feature_ordinal: int
    offset_bytes: int
    content_length_bytes: int


@dataclass(frozen=True)
class CRSMetadata:
    state: str
    member_name: str | None
    encoding: str | None
    wkt: str | None
    byte_sha256: str | None
    authority_candidates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "member_name": self.member_name,
            "encoding": self.encoding,
            "wkt": self.wkt,
            "byte_sha256": self.byte_sha256,
            "authority_candidates": list(self.authority_candidates),
            "coordinates": "published_native_crs",
            "transformed": False,
            "transform_backend": None,
        }


@dataclass(frozen=True)
class DatasetMembers:
    stem: str
    shp: str
    shx: str
    dbf: str
    prj: str | None
    cpg: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stem": self.stem,
            "shp": self.shp,
            "shx": self.shx,
            "dbf": self.dbf,
            "prj": self.prj,
            "cpg": self.cpg,
        }


@dataclass(frozen=True)
class ShapefileDatasetInspection:
    path: str
    container: str
    artifact_sha256: str
    artifact_identity_kind: str
    archive: Mapping[str, Any] | None
    source_id: str
    release_id: str
    release_identity_state: str
    members: DatasetMembers
    member_identity_sha256: str
    shp: ShapeHeader
    shx: ShapeIndexHeader
    dbf: DBFSchema
    crs: CRSMetadata
    parcel_join_fields: tuple[str, ...]
    feature_count: int
    alignment_state: str
    schema_fingerprint: str

    def identity_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "release_id": self.release_id,
            "release_identity_state": self.release_identity_state,
            "artifact_sha256": self.artifact_sha256,
            "artifact_identity_kind": self.artifact_identity_kind,
            "dataset_member": self.members.shp,
            "member_identity_sha256": self.member_identity_sha256,
            "schema_fingerprint": self.schema_fingerprint,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "container": self.container,
            "identity": self.identity_dict(),
            "archive": dict(self.archive) if self.archive is not None else None,
            "members": self.members.to_dict(),
            "shp": self.shp.to_dict(),
            "shx": self.shx.to_dict(),
            "dbf": self.dbf.to_dict(),
            "crs": self.crs.to_dict(),
            "parcel_join_fields": list(self.parcel_join_fields),
            "feature_count": self.feature_count,
            "alignment_state": self.alignment_state,
        }


@dataclass(frozen=True)
class FeaturePage:
    inspection: ShapefileDatasetInspection
    records: tuple[Mapping[str, Any], ...]
    query_contract: Mapping[str, Any]
    query_fingerprint: str
    start_feature_ordinal: int
    result_limit: int
    scan_limit: int
    scanned_count: int
    next_cursor: str | None
    exhausted: bool
    stop_reason: str

    def to_dict(self, *, operation: str) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "operation": operation,
            "identity": self.inspection.identity_dict(),
            "query": {
                **dict(self.query_contract),
                "fingerprint": self.query_fingerprint,
            },
            "records": [dict(record) for record in self.records],
            "next_cursor": self.next_cursor,
            "raw_artifact_refs": [self.inspection.path],
            "page": {
                "query_fingerprint": self.query_fingerprint,
                "start_feature_ordinal": self.start_feature_ordinal,
                "result_limit": self.result_limit,
                "scan_limit": self.scan_limit,
                "scanned_count": self.scanned_count,
                "returned_count": len(self.records),
                "next_cursor": self.next_cursor,
                "exhausted": self.exhausted,
                "stop_reason": self.stop_reason,
            },
            "inspection": self.inspection.to_dict(),
        }


class LocalShapefileArtifact:
    """Validated access to one ZIP archive or direct SHP sidecar set."""

    def __init__(
        self,
        path: Path | str,
        *,
        policy: ArchiveSafetyPolicy | None = None,
    ) -> None:
        artifact_path = Path(path).expanduser().resolve()
        if not artifact_path.is_file():
            raise ParcelShapefileError(
                "shapefile_artifact_missing",
                "Local shapefile artifact does not exist or is not a file",
                details={"path": str(artifact_path)},
            )
        self.path = artifact_path
        self.archive_inspection: ArchiveInspection | None = None
        self._zip_names: dict[str, str] = {}
        self._zip_metadata: dict[str, dict[str, Any]] = {}
        self._local_members: dict[str, Path] = {}
        self._local_metadata: dict[str, dict[str, Any]] = {}

        if artifact_path.suffix.casefold() == ".zip":
            self.container = "zip"
            try:
                self.archive_inspection = inspect_zip(
                    artifact_path,
                    policy=policy,
                )
            except BulkSourceError as error:
                raise ParcelShapefileError(
                    getattr(error, "code", "shapefile_archive_invalid"),
                    str(error),
                    details=getattr(error, "details", {}),
                ) from error
            self.artifact_sha256 = self.archive_inspection.archive_sha256
            self.artifact_identity_kind = "archive_file_sha256"
            file_members = [
                dict(member)
                for member in self.archive_inspection.members
                if member.get("kind") == "file"
            ]
            names = [str(member["path"]) for member in file_members]
            self._zip_names = _casefold_unique(
                names,
                label="ZIP member paths",
            )
            self._zip_metadata = {
                str(member["path"]).casefold(): member for member in file_members
            }
        elif artifact_path.suffix.casefold() == ".shp":
            self.container = "sidecar_set"
            stem = artifact_path.stem.casefold()
            paths = [
                candidate.resolve()
                for candidate in artifact_path.parent.iterdir()
                if candidate.is_file()
                and candidate.stem.casefold() == stem
                and candidate.suffix.casefold()
                in {".shp", ".shx", ".dbf", ".prj", ".cpg"}
            ]
            names = [candidate.name for candidate in paths]
            lookup = _casefold_unique(names, label="local sidecar names")
            self._local_members = {
                folded: next(
                    candidate
                    for candidate in paths
                    if candidate.name == actual_name
                )
                for folded, actual_name in lookup.items()
            }
            member_metadata = []
            for folded in sorted(self._local_members):
                candidate = self._local_members[folded]
                metadata = {
                    "path": candidate.name,
                    "kind": "file",
                    "size": candidate.stat().st_size,
                    "sha256": file_sha256(candidate),
                }
                self._local_metadata[folded] = metadata
                member_metadata.append(metadata)
            self.artifact_sha256 = sha256_fingerprint(
                {
                    "identity_kind": "sidecar_set_manifest_sha256",
                    "members": member_metadata,
                }
            )
            self.artifact_identity_kind = "sidecar_set_manifest_sha256"
        else:
            raise ParcelShapefileError(
                "shapefile_artifact_type",
                "Local shapefile decoding accepts a ZIP archive or .shp file",
                details={"path": str(artifact_path)},
            )

        self.datasets = self._discover_datasets()

    @property
    def archive_dict(self) -> Mapping[str, Any] | None:
        if self.archive_inspection is None:
            return None
        return self.archive_inspection.to_dict()

    def _all_member_names(self) -> list[str]:
        if self.container == "zip":
            return sorted(self._zip_names.values(), key=str.casefold)
        return sorted(
            (path.name for path in self._local_members.values()),
            key=str.casefold,
        )

    def _discover_datasets(self) -> tuple[DatasetMembers, ...]:
        names = self._all_member_names()
        by_name = _casefold_unique(names, label="shapefile sidecar paths")
        shp_names = [
            name for name in names if _member_suffix(name) == ".shp"
        ]
        if not shp_names:
            raise ParcelShapefileError(
                "shapefile_member_missing",
                "Artifact contains no SHP dataset",
                details={"path": str(self.path)},
            )
        datasets: list[DatasetMembers] = []
        for shp_name in shp_names:
            stem = _member_stem(shp_name)

            def companion(suffix: str, *, required: bool) -> str | None:
                expected = f"{stem}{suffix}"
                observed = by_name.get(expected.casefold())
                if observed is None and required:
                    raise ParcelShapefileError(
                        "shapefile_sidecar_missing",
                        f"Shapefile dataset lacks required {suffix.upper()} sidecar",
                        details={
                            "dataset_member": shp_name,
                            "expected_member": expected,
                        },
                    )
                return observed

            shx = companion(".shx", required=True)
            dbf = companion(".dbf", required=True)
            if shx is None or dbf is None:
                raise ParcelShapefileError(
                    "shapefile_sidecar_missing",
                    "Shapefile dataset lacks an aligned SHX or DBF sidecar",
                    details={"dataset_member": shp_name},
                )
            datasets.append(
                DatasetMembers(
                    stem=stem,
                    shp=shp_name,
                    shx=shx,
                    dbf=dbf,
                    prj=companion(".prj", required=False),
                    cpg=companion(".cpg", required=False),
                )
            )
        return tuple(sorted(datasets, key=lambda item: item.shp.casefold()))

    def select_dataset(self, dataset_member: str | None = None) -> DatasetMembers:
        if dataset_member is None:
            if len(self.datasets) != 1:
                raise ParcelShapefileError(
                    "shapefile_dataset_selection_required",
                    "Artifact contains multiple shapefile datasets",
                    details={
                        "dataset_members": [
                            dataset.shp for dataset in self.datasets
                        ]
                    },
                )
            return self.datasets[0]
        requested = dataset_member.strip().casefold()
        matches = [
            dataset
            for dataset in self.datasets
            if requested
            in {
                dataset.shp.casefold(),
                dataset.stem.casefold(),
                PurePosixPath(dataset.shp).name.casefold(),
                PurePosixPath(dataset.stem).name.casefold(),
            }
        ]
        if len(matches) != 1:
            raise ParcelShapefileError(
                "shapefile_dataset_not_found",
                "Requested shapefile dataset member was not uniquely resolved",
                details={
                    "requested": dataset_member,
                    "matches": [dataset.shp for dataset in matches],
                    "available": [dataset.shp for dataset in self.datasets],
                },
            )
        return matches[0]

    @contextlib.contextmanager
    def open_member(self, member_name: str) -> Iterator[BinaryIO]:
        folded = member_name.casefold()
        if self.container == "zip":
            actual = self._zip_names.get(folded)
            if actual is None:
                raise ParcelShapefileError(
                    "shapefile_member_missing",
                    "Requested ZIP member is not present",
                    details={"member": member_name},
                )
            with zipfile.ZipFile(self.path) as archive:
                with archive.open(actual) as stream:
                    yield stream
            return
        member_path = self._local_members.get(folded)
        if member_path is None:
            raise ParcelShapefileError(
                "shapefile_member_missing",
                "Requested local sidecar is not present",
                details={"member": member_name},
            )
        with member_path.open("rb") as stream:
            yield stream

    def member_metadata(self, member_name: str) -> dict[str, Any]:
        folded = member_name.casefold()
        if self.container == "zip":
            metadata = self._zip_metadata.get(folded)
        else:
            metadata = self._local_metadata.get(folded)
        if metadata is None:
            raise ParcelShapefileError(
                "shapefile_member_missing",
                "Requested sidecar metadata is not present",
                details={"member": member_name},
            )
        return dict(metadata)

    def read_member(self, member_name: str, *, max_bytes: int) -> bytes:
        _positive(max_bytes, "max_bytes")
        metadata = self.member_metadata(member_name)
        size = int(metadata["size"])
        if size > max_bytes:
            raise ParcelShapefileError(
                "shapefile_metadata_member_too_large",
                "Metadata sidecar exceeds the requested read bound",
                details={
                    "member": member_name,
                    "member_size": size,
                    "max_bytes": max_bytes,
                },
            )
        with self.open_member(member_name) as stream:
            return _read_exact(
                stream,
                size,
                code="shapefile_member_truncated",
                message="Shapefile sidecar ended before its declared size",
                details={"member": member_name},
            )

    def member_identity(
        self,
        members: DatasetMembers,
    ) -> str:
        roles = {
            "shp": members.shp,
            "shx": members.shx,
            "dbf": members.dbf,
            "prj": members.prj,
            "cpg": members.cpg,
        }
        member_rows = []
        for role, member_name in roles.items():
            if member_name is None:
                continue
            member_rows.append(
                {
                    "role": role,
                    "member": member_name,
                    "metadata": self.member_metadata(member_name),
                }
            )
        return sha256_fingerprint(
            {
                "artifact_sha256": self.artifact_sha256,
                "dataset_stem": members.stem,
                "members": member_rows,
            }
        )


def _decode_cpg(raw: bytes, *, member_name: str) -> tuple[str, str]:
    try:
        label = (
            raw.decode("utf-8-sig", errors="strict")
            .replace("\x00", "")
            .strip()
        )
    except UnicodeDecodeError as error:
        raise ParcelShapefileError(
            "shapefile_cpg_invalid",
            "Shapefile CPG member is not a UTF-8 encoding label",
            details={"member": member_name},
        ) from error
    if not label:
        raise ParcelShapefileError(
            "shapefile_cpg_blank",
            "Shapefile CPG member is blank",
            details={"member": member_name},
        )
    aliases = {
        "65001": "utf-8",
        "utf8": "utf-8",
        "utf-8": "utf-8",
        "ansi 1252": "cp1252",
        "windows-1252": "cp1252",
        "1252": "cp1252",
    }
    requested = aliases.get(label.casefold(), label)
    try:
        return codecs.lookup(requested).name, f"cpg:{label}"
    except LookupError as error:
        raise ParcelShapefileError(
            "shapefile_cpg_unknown",
            "Shapefile CPG declares an unknown encoding",
            details={"member": member_name, "encoding_label": label},
        ) from error


def _dbf_encoding(
    artifact: LocalShapefileArtifact,
    members: DatasetMembers,
    *,
    language_driver: int,
) -> tuple[str, str]:
    if members.cpg is not None:
        return _decode_cpg(
            artifact.read_member(members.cpg, max_bytes=4096),
            member_name=members.cpg,
        )
    declared = DBF_LANGUAGE_DRIVERS.get(language_driver)
    if declared is not None:
        return codecs.lookup(declared).name, (
            f"dbf_language_driver:0x{language_driver:02x}"
        )
    return "cp1252", (
        "fallback_cp1252_no_cpg_or_recognized_language_driver"
    )


def _dbf_last_update(header: bytes) -> str | None:
    year = 1900 + int(header[1])
    month = int(header[2])
    day = int(header[3])
    if month == 0 and day == 0:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _parse_dbf_schema(
    artifact: LocalShapefileArtifact,
    members: DatasetMembers,
) -> DBFSchema:
    metadata = artifact.member_metadata(members.dbf)
    member_size = int(metadata["size"])
    with artifact.open_member(members.dbf) as stream:
        header = _read_exact(
            stream,
            32,
            code="shapefile_dbf_header_truncated",
            message="Shapefile DBF header is truncated",
            details={"member": members.dbf},
        )
        version = int(header[0])
        record_count = struct.unpack_from("<I", header, 4)[0]
        header_length = struct.unpack_from("<H", header, 8)[0]
        record_length = struct.unpack_from("<H", header, 10)[0]
        language_driver = int(header[29])
        if header_length < 33:
            raise ParcelShapefileError(
                "shapefile_dbf_header_length_invalid",
                "Shapefile DBF header length is invalid",
                details={
                    "member": members.dbf,
                    "header_length": header_length,
                },
            )
        descriptor_block = _read_exact(
            stream,
            header_length - 32,
            code="shapefile_dbf_descriptors_truncated",
            message="Shapefile DBF field descriptor block is truncated",
            details={"member": members.dbf},
        )

    terminator_offset: int | None = None
    for offset in range(0, len(descriptor_block), 32):
        if descriptor_block[offset : offset + 1] == b"\r":
            terminator_offset = offset
            break
    if terminator_offset is None:
        raise ParcelShapefileError(
            "shapefile_dbf_descriptor_terminator_missing",
            "Shapefile DBF field descriptors have no aligned terminator",
            details={"member": members.dbf},
        )
    fields: list[DBFField] = []
    for offset in range(0, terminator_offset, 32):
        descriptor = descriptor_block[offset : offset + 32]
        if len(descriptor) != 32:
            raise ParcelShapefileError(
                "shapefile_dbf_descriptor_truncated",
                "Shapefile DBF field descriptor is truncated",
                details={"member": members.dbf, "offset": offset},
            )
        try:
            name = (
                descriptor[:11]
                .split(b"\x00", 1)[0]
                .decode("ascii", errors="strict")
                .strip()
            )
        except UnicodeDecodeError as error:
            raise ParcelShapefileError(
                "shapefile_dbf_field_name_invalid",
                "Shapefile DBF field name is not ASCII",
                details={"member": members.dbf, "offset": offset},
            ) from error
        if not name:
            raise ParcelShapefileError(
                "shapefile_dbf_field_name_blank",
                "Shapefile DBF contains a blank field name",
                details={"member": members.dbf, "offset": offset},
            )
        try:
            field_type = bytes((descriptor[11],)).decode("ascii", errors="strict")
        except UnicodeDecodeError as error:
            raise ParcelShapefileError(
                "shapefile_dbf_field_type_invalid",
                "Shapefile DBF field type is not ASCII",
                details={"member": members.dbf, "field": name},
            ) from error
        length = int(descriptor[16])
        decimal_count = int(descriptor[17])
        if length <= 0:
            raise ParcelShapefileError(
                "shapefile_dbf_field_length_invalid",
                "Shapefile DBF field has no storage length",
                details={"member": members.dbf, "field": name},
            )
        fields.append(
            DBFField(
                name=name,
                field_type=field_type,
                length=length,
                decimal_count=decimal_count,
            )
        )
    folded_names = [field.name.casefold() for field in fields]
    duplicates = sorted(
        {
            fields[index].name
            for index, folded in enumerate(folded_names)
            if folded_names.count(folded) > 1
        }
    )
    if duplicates:
        raise ParcelShapefileError(
            "shapefile_dbf_fields_duplicated",
            "Shapefile DBF field names are duplicated case-insensitively",
            details={"member": members.dbf, "fields": duplicates},
        )
    field_bytes = sum(field.length for field in fields)
    minimum_record_length = 1 + field_bytes
    if record_length < minimum_record_length:
        raise ParcelShapefileError(
            "shapefile_dbf_record_length_invalid",
            "Shapefile DBF record length is shorter than its declared fields",
            details={
                "member": members.dbf,
                "record_length": record_length,
                "minimum_record_length": minimum_record_length,
            },
        )
    expected_size = header_length + record_count * record_length
    if member_size < expected_size:
        raise ParcelShapefileError(
            "shapefile_dbf_table_truncated",
            "Shapefile DBF member is shorter than its declared record table",
            details={
                "member": members.dbf,
                "member_size": member_size,
                "expected_minimum_size": expected_size,
            },
        )
    encoding, encoding_source = _dbf_encoding(
        artifact,
        members,
        language_driver=language_driver,
    )
    return DBFSchema(
        member_name=members.dbf,
        member_size=member_size,
        version=version,
        last_update=_dbf_last_update(header),
        record_count=record_count,
        header_length=header_length,
        record_length=record_length,
        trailing_record_bytes=record_length - minimum_record_length,
        language_driver=language_driver,
        encoding=encoding,
        encoding_source=encoding_source,
        fields=tuple(fields),
    )


def _raw_field_text(raw: bytes, field: DBFField, encoding: str) -> str | None:
    if field.field_type.upper() in {"I", "B", "Y", "T", "@"}:
        return raw.hex()
    try:
        value = raw.decode(encoding, errors="strict")
    except UnicodeDecodeError as error:
        raise ParcelShapefileError(
            "shapefile_dbf_value_decode_failed",
            "Shapefile DBF value is invalid for its declared encoding",
            details={"field": field.name, "encoding": encoding},
        ) from error
    normalized = value.replace("\x00", "").strip()
    return normalized or None


def _decode_dbf_value(
    raw: bytes,
    field: DBFField,
    *,
    encoding: str,
) -> Any:
    field_type = field.field_type.upper()
    if field_type in {"C", "M"}:
        return _raw_field_text(raw, field, encoding)
    if field_type in {"I"}:
        if len(raw) != 4:
            return {"binary_hex": raw.hex()}
        return struct.unpack("<i", raw)[0]
    if field_type in {"B"}:
        if len(raw) != 8:
            return {"binary_hex": raw.hex()}
        value = struct.unpack("<d", raw)[0]
        return value if math.isfinite(value) else {"binary_hex": raw.hex()}
    if field_type in {"Y"}:
        if len(raw) != 8:
            return {"binary_hex": raw.hex()}
        scaled = struct.unpack("<q", raw)[0]
        sign = "-" if scaled < 0 else ""
        absolute = abs(scaled)
        return f"{sign}{absolute // 10_000}.{absolute % 10_000:04d}"
    if field_type in {"T", "@"}:
        return {"binary_hex": raw.hex()}

    text = raw.decode("ascii", errors="replace").strip()
    if not text or set(text) <= {"*"}:
        return None
    if field_type in {"N", "F"}:
        try:
            return float(text) if field.decimal_count else int(text)
        except ValueError:
            return text
    if field_type == "L":
        marker = text[:1].upper()
        if marker in {"T", "Y"}:
            return True
        if marker in {"F", "N"}:
            return False
        return None
    if field_type == "D" and re.fullmatch(r"\d{8}", text):
        try:
            return date(
                int(text[0:4]),
                int(text[4:6]),
                int(text[6:8]),
            ).isoformat()
        except ValueError:
            return text
    return text


def _iter_dbf_records(
    stream: BinaryIO,
    schema: DBFSchema,
    *,
    start_record: int = 0,
) -> Iterator[DBFRecord]:
    if start_record < 0 or start_record > schema.record_count:
        raise ValueError("start_record is outside the DBF record table")
    _position_stream(
        stream,
        schema.header_length + start_record * schema.record_length,
        code="shapefile_dbf_header_truncated",
        message="Could not position the DBF stream at the requested record",
        details={"member": schema.member_name},
    )
    for record_index in range(start_record, schema.record_count):
        raw_record = _read_exact(
            stream,
            schema.record_length,
            code="shapefile_dbf_record_truncated",
            message="Shapefile DBF record table ended unexpectedly",
            details={
                "member": schema.member_name,
                "record_index": record_index,
            },
        )
        marker = raw_record[:1]
        if marker not in {b" ", b"*"}:
            raise ParcelShapefileError(
                "shapefile_dbf_record_marker_invalid",
                "Shapefile DBF record has an unknown deletion marker",
                details={
                    "member": schema.member_name,
                    "record_index": record_index,
                    "marker": marker.hex(),
                },
            )
        attributes: dict[str, Any] = {}
        raw_text: dict[str, str | None] = {}
        offset = 1
        for field in schema.fields:
            value = raw_record[offset : offset + field.length]
            offset += field.length
            attributes[field.name] = _decode_dbf_value(
                value,
                field,
                encoding=schema.encoding,
            )
            raw_text[field.name] = _raw_field_text(
                value,
                field,
                schema.encoding,
            )
        yield DBFRecord(
            record_index=record_index,
            deleted=marker == b"*",
            attributes=attributes,
            raw_text=raw_text,
            trailing_bytes_hex=(
                raw_record[offset:].hex() if offset < len(raw_record) else None
            ),
        )


def _parse_shape_header(
    data: bytes,
    *,
    member_name: str,
    member_size: int,
) -> ShapeHeader:
    if len(data) != 100:
        raise ParcelShapefileError(
            "shapefile_header_truncated",
            "SHP or SHX header is truncated",
            details={
                "member": member_name,
                "expected_bytes": 100,
                "observed_bytes": len(data),
            },
        )
    file_code = struct.unpack_from(">i", data, 0)[0]
    file_length_words = struct.unpack_from(">i", data, 24)[0]
    version = struct.unpack_from("<i", data, 28)[0]
    shape_type = struct.unpack_from("<i", data, 32)[0]
    file_length_bytes = file_length_words * 2
    if file_code != 9994 or version != 1000:
        raise ParcelShapefileError(
            "shapefile_header_invalid",
            "SHP or SHX header is not an Esri shapefile header",
            details={
                "member": member_name,
                "file_code": file_code,
                "version": version,
            },
        )
    if shape_type not in SHAPE_TYPE_NAMES:
        raise ParcelShapefileError(
            "shapefile_shape_type_unsupported",
            "Shapefile declares a shape type not decoded by this module",
            details={
                "member": member_name,
                "shape_type": shape_type,
            },
        )
    if file_length_bytes < 100 or file_length_bytes != member_size:
        raise ParcelShapefileError(
            "shapefile_declared_length_mismatch",
            "SHP or SHX declared byte length differs from its member size",
            details={
                "member": member_name,
                "declared_length_bytes": file_length_bytes,
                "member_size": member_size,
            },
        )
    raw_bounds = struct.unpack_from("<4d", data, 36)
    if any(not math.isfinite(value) for value in raw_bounds):
        raise ParcelShapefileError(
            "shapefile_header_bounds_invalid",
            "SHP or SHX header contains non-finite XY bounds",
            details={"member": member_name, "bounds": list(raw_bounds)},
        )
    bounds = raw_bounds
    z_range = struct.unpack_from("<2d", data, 68)
    m_range = struct.unpack_from("<2d", data, 84)
    return ShapeHeader(
        member_name=member_name,
        member_size=member_size,
        file_length_bytes=file_length_bytes,
        version=version,
        shape_type=shape_type,
        bounds=tuple(float(value) for value in bounds),
        z_range=tuple(float(value) for value in z_range),
        m_range=tuple(float(value) for value in m_range),
    )


def _shape_header(
    artifact: LocalShapefileArtifact,
    member_name: str,
) -> ShapeHeader:
    metadata = artifact.member_metadata(member_name)
    member_size = int(metadata["size"])
    with artifact.open_member(member_name) as stream:
        header = _read_exact(
            stream,
            100,
            code="shapefile_header_truncated",
            message="SHP or SHX header is truncated",
            details={"member": member_name},
        )
    return _parse_shape_header(
        header,
        member_name=member_name,
        member_size=member_size,
    )


def _shape_index_header(
    artifact: LocalShapefileArtifact,
    members: DatasetMembers,
) -> ShapeIndexHeader:
    header = _shape_header(artifact, members.shx)
    entry_bytes = header.file_length_bytes - 100
    if entry_bytes % 8:
        raise ParcelShapefileError(
            "shapefile_shx_length_invalid",
            "SHX record table length is not divisible by eight bytes",
            details={
                "member": members.shx,
                "record_table_bytes": entry_bytes,
            },
        )
    return ShapeIndexHeader(
        shape_header=header,
        record_count=entry_bytes // 8,
    )


def _iter_shape_index_entries(
    stream: BinaryIO,
    header: ShapeIndexHeader,
    *,
    start_feature_ordinal: int = 0,
) -> Iterator[ShapeIndexEntry]:
    if (
        start_feature_ordinal < 0
        or start_feature_ordinal > header.record_count
    ):
        raise ValueError("start_feature_ordinal is outside the SHX table")
    position_ordinal = max(0, start_feature_ordinal - 1)
    _position_stream(
        stream,
        100 + position_ordinal * 8,
        code="shapefile_shx_header_truncated",
        message="Could not position the SHX stream at the requested feature",
        details={"member": header.shape_header.member_name},
    )
    previous_offset = 100
    if start_feature_ordinal:
        prior = _read_exact(
            stream,
            8,
            code="shapefile_shx_entry_truncated",
            message="Prior SHX index entry is truncated",
            details={
                "member": header.shape_header.member_name,
                "feature_ordinal": start_feature_ordinal - 1,
            },
        )
        prior_offset_words, prior_length_words = struct.unpack(">2i", prior)
        prior_offset_bytes = prior_offset_words * 2
        prior_length_bytes = prior_length_words * 2
        if prior_offset_bytes < 100 or prior_length_bytes < 4:
            raise ParcelShapefileError(
                "shapefile_shx_entry_invalid",
                "Prior SHX entry has an invalid offset or content length",
                details={
                    "member": header.shape_header.member_name,
                    "feature_ordinal": start_feature_ordinal - 1,
                    "offset_bytes": prior_offset_bytes,
                    "content_length_bytes": prior_length_bytes,
                },
            )
        previous_offset = (
            prior_offset_bytes + 8 + prior_length_bytes
        )
    for feature_ordinal in range(
        start_feature_ordinal,
        header.record_count,
    ):
        raw = _read_exact(
            stream,
            8,
            code="shapefile_shx_entry_truncated",
            message="SHX index entry is truncated",
            details={
                "member": header.shape_header.member_name,
                "feature_ordinal": feature_ordinal,
            },
        )
        offset_words, length_words = struct.unpack(">2i", raw)
        offset_bytes = offset_words * 2
        content_length_bytes = length_words * 2
        if (
            offset_bytes < 100
            or offset_bytes != previous_offset
            or content_length_bytes < 4
        ):
            raise ParcelShapefileError(
                "shapefile_shx_entry_invalid",
                "SHX index entry has an invalid offset or content length",
                details={
                    "member": header.shape_header.member_name,
                    "feature_ordinal": feature_ordinal,
                    "offset_bytes": offset_bytes,
                    "content_length_bytes": content_length_bytes,
                },
            )
        previous_offset = offset_bytes + 8 + content_length_bytes
        yield ShapeIndexEntry(
            feature_ordinal=feature_ordinal,
            offset_bytes=offset_bytes,
            content_length_bytes=content_length_bytes,
        )


def _crs_authorities(wkt: str) -> tuple[str, ...]:
    candidates: list[str] = []
    patterns = (
        r"""(?i)\bAUTHORITY\s*\[\s*["']([^"']+)["']\s*,\s*["']?([0-9A-Za-z_.:-]+)["']?\s*\]""",
        r"""(?i)\bID\s*\[\s*["']([^"']+)["']\s*,\s*["']?([0-9A-Za-z_.:-]+)["']?\s*\]""",
    )
    for pattern in patterns:
        for authority, code in re.findall(pattern, wkt):
            value = f"{authority.upper()}:{code}"
            if value not in candidates:
                candidates.append(value)
    return tuple(candidates)


def _crs_metadata(
    artifact: LocalShapefileArtifact,
    members: DatasetMembers,
) -> CRSMetadata:
    if members.prj is None:
        return CRSMetadata(
            state="not_published_with_dataset",
            member_name=None,
            encoding=None,
            wkt=None,
            byte_sha256=None,
            authority_candidates=(),
        )
    raw = artifact.read_member(members.prj, max_bytes=1024 * 1024)
    encoding = "utf-8-sig"
    try:
        wkt = raw.decode(encoding, errors="strict")
    except UnicodeDecodeError:
        encoding = "cp1252"
        wkt = raw.decode(encoding, errors="strict")
    wkt = wkt.strip()
    if not wkt:
        return CRSMetadata(
            state="published_member_blank",
            member_name=members.prj,
            encoding=encoding,
            wkt=None,
            byte_sha256=_sha256_bytes(raw),
            authority_candidates=(),
        )
    return CRSMetadata(
        state="published_wkt_preserved",
        member_name=members.prj,
        encoding=encoding,
        wkt=wkt,
        byte_sha256=_sha256_bytes(raw),
        authority_candidates=_crs_authorities(wkt),
    )


def _resolve_fields(
    schema: DBFSchema,
    requested: Sequence[str] | None,
    *,
    role: str,
) -> tuple[str, ...]:
    lookup = schema.field_lookup
    if requested is None:
        if role == "parcel_join":
            names = [
                lookup[name.casefold()]
                for name in CONSERVATIVE_PARCEL_FIELDS
                if name.casefold() in lookup
            ]
        else:
            names = list(schema.field_names)
    else:
        names = []
        missing = []
        for value in requested:
            normalized = _text(value)
            observed = (
                lookup.get(normalized.casefold()) if normalized else None
            )
            if observed is None:
                missing.append(str(value))
            elif observed not in names:
                names.append(observed)
        if missing:
            raise ParcelShapefileError(
                "shapefile_dbf_field_not_found",
                "Requested DBF fields are not present",
                details={
                    "role": role,
                    "missing_fields": missing,
                    "available_fields": list(schema.field_names),
                },
            )
    return tuple(names)


def _inspect_artifact(
    artifact: LocalShapefileArtifact,
    *,
    dataset_member: str | None = None,
    source_id: str = DEFAULT_SOURCE_ID,
    release_id: str | None = None,
    parcel_fields: Sequence[str] | None = None,
) -> ShapefileDatasetInspection:
    normalized_source = _text(source_id)
    if normalized_source is None:
        raise ValueError("source_id must not be blank")
    members = artifact.select_dataset(dataset_member)
    shp = _shape_header(artifact, members.shp)
    shx = _shape_index_header(artifact, members)
    dbf = _parse_dbf_schema(artifact, members)
    crs = _crs_metadata(artifact, members)
    if shp.shape_type != shx.shape_header.shape_type:
        raise ParcelShapefileError(
            "shapefile_shp_shx_type_mismatch",
            "SHP and SHX headers declare different shape types",
            details={
                "shp_member": members.shp,
                "shp_shape_type": shp.shape_type,
                "shx_member": members.shx,
                "shx_shape_type": shx.shape_header.shape_type,
            },
        )
    if shp.bounds != shx.shape_header.bounds:
        raise ParcelShapefileError(
            "shapefile_shp_shx_bounds_mismatch",
            "SHP and SHX headers declare different XY bounds",
            details={
                "shp_member": members.shp,
                "shp_bounds": list(shp.bounds),
                "shx_member": members.shx,
                "shx_bounds": list(shx.shape_header.bounds),
            },
        )
    counts = {
        "shx_feature_count": shx.record_count,
        "dbf_record_count": dbf.record_count,
    }
    if shx.record_count != dbf.record_count:
        raise ParcelShapefileError(
            "shapefile_feature_table_count_mismatch",
            "SHX feature count and DBF record count differ",
            details=counts,
        )
    resolved_parcel_fields = _resolve_fields(
        dbf,
        parcel_fields,
        role="parcel_join",
    )
    member_identity = artifact.member_identity(members)
    effective_release = _text(release_id)
    release_state = "caller_supplied"
    if effective_release is None:
        effective_release = f"artifact:{artifact.artifact_sha256}"
        release_state = "derived_from_artifact_for_local_decode"
    schema_payload = {
        "format": SCHEMA_VERSION,
        "members": members.to_dict(),
        "shape_type": shp.shape_type,
        "dbf_schema_fingerprint": dbf.schema_fingerprint,
        "feature_count": shx.record_count,
        "crs_byte_sha256": crs.byte_sha256,
        "parcel_join_fields": list(resolved_parcel_fields),
    }
    return ShapefileDatasetInspection(
        path=str(artifact.path),
        container=artifact.container,
        artifact_sha256=artifact.artifact_sha256,
        artifact_identity_kind=artifact.artifact_identity_kind,
        archive=artifact.archive_dict,
        source_id=normalized_source,
        release_id=effective_release,
        release_identity_state=release_state,
        members=members,
        member_identity_sha256=member_identity,
        shp=shp,
        shx=shx,
        dbf=dbf,
        crs=crs,
        parcel_join_fields=resolved_parcel_fields,
        feature_count=shx.record_count,
        alignment_state="shp_shx_dbf_counts_aligned",
        schema_fingerprint=sha256_fingerprint(schema_payload),
    )


def inspect_shapefile_dataset(
    path: Path | str,
    *,
    dataset_member: str | None = None,
    source_id: str = DEFAULT_SOURCE_ID,
    release_id: str | None = None,
    parcel_fields: Sequence[str] | None = None,
    policy: ArchiveSafetyPolicy | None = None,
) -> ShapefileDatasetInspection:
    artifact = LocalShapefileArtifact(path, policy=policy)
    return _inspect_artifact(
        artifact,
        dataset_member=dataset_member,
        source_id=source_id,
        release_id=release_id,
        parcel_fields=parcel_fields,
    )


class _ShapeBuffer:
    def __init__(
        self,
        data: bytes,
        *,
        member_name: str,
        feature_ordinal: int,
    ) -> None:
        self.data = data
        self.offset = 0
        self.details = {
            "member": member_name,
            "feature_ordinal": feature_ordinal,
        }

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def take(self, length: int, label: str) -> bytes:
        end = self.offset + length
        if length < 0 or end > len(self.data):
            raise ParcelShapefileError(
                "shapefile_record_content_truncated",
                f"Shapefile record ended while reading {label}",
                details={
                    **self.details,
                    "record_bytes": len(self.data),
                    "offset": self.offset,
                    "requested_bytes": length,
                },
            )
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def int32(self, label: str) -> int:
        return struct.unpack("<i", self.take(4, label))[0]

    def doubles(self, count: int, label: str) -> tuple[float, ...]:
        if count < 0:
            raise ParcelShapefileError(
                "shapefile_record_count_invalid",
                f"Shapefile {label} count is negative",
                details={**self.details, "count": count},
            )
        if count == 0:
            return ()
        return tuple(
            float(value)
            for value in struct.unpack(
                f"<{count}d",
                self.take(count * 8, label),
            )
        )

    def int32s(self, count: int, label: str) -> tuple[int, ...]:
        if count < 0:
            raise ParcelShapefileError(
                "shapefile_record_count_invalid",
                f"Shapefile {label} count is negative",
                details={**self.details, "count": count},
            )
        if count == 0:
            return ()
        return tuple(
            int(value)
            for value in struct.unpack(
                f"<{count}i",
                self.take(count * 4, label),
            )
        )

    def finish(self) -> None:
        if self.remaining:
            raise ParcelShapefileError(
                "shapefile_record_content_extra",
                "Shapefile record contains unparsed trailing bytes",
                details={
                    **self.details,
                    "trailing_bytes": self.remaining,
                },
            )


def _native_bounds(
    values: Sequence[float],
    *,
    details: Mapping[str, Any],
) -> dict[str, float]:
    xmin, ymin, xmax, ymax = values
    return {
        "xmin": _finite(xmin, label="xmin", details=details),
        "ymin": _finite(ymin, label="ymin", details=details),
        "xmax": _finite(xmax, label="xmax", details=details),
        "ymax": _finite(ymax, label="ymax", details=details),
    }


def _native_points(
    values: Sequence[float],
    *,
    details: Mapping[str, Any],
) -> list[list[float]]:
    points: list[list[float]] = []
    for index in range(0, len(values), 2):
        points.append(
            [
                _finite(
                    values[index],
                    label="x coordinate",
                    details={**details, "point_index": index // 2},
                ),
                _finite(
                    values[index + 1],
                    label="y coordinate",
                    details={**details, "point_index": index // 2},
                ),
            ]
        )
    return points


def _measure(value: float) -> float | None:
    if not math.isfinite(value) or value < -1.0e38:
        return None
    return value


def _measure_range(values: Sequence[float]) -> dict[str, float | None]:
    return {
        "minimum": _measure(float(values[0])),
        "maximum": _measure(float(values[1])),
    }


def _parse_optional_measures(
    buffer: _ShapeBuffer,
    *,
    point_count: int,
) -> tuple[dict[str, float | None] | None, list[float | None] | None]:
    if buffer.remaining == 0:
        return None, None
    expected = 16 + point_count * 8
    if buffer.remaining != expected:
        raise ParcelShapefileError(
            "shapefile_measure_array_length_invalid",
            "Shapefile optional measure section has an unexpected length",
            details={
                **buffer.details,
                "remaining_bytes": buffer.remaining,
                "expected_bytes": expected,
            },
        )
    measure_range = _measure_range(buffer.doubles(2, "measure range"))
    measures = [
        _measure(value)
        for value in buffer.doubles(point_count, "measure array")
    ]
    return measure_range, measures


def _ring_orientation(points: Sequence[Sequence[float]]) -> str | None:
    if len(points) < 3:
        return None
    area_twice = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area_twice += point[0] * next_point[1]
        area_twice -= next_point[0] * point[1]
    if area_twice < 0:
        return "clockwise"
    if area_twice > 0:
        return "counterclockwise"
    return "degenerate"


def _geometry_record(
    content: bytes,
    *,
    expected_shape_type: int,
    member_name: str,
    feature_ordinal: int,
) -> dict[str, Any] | None:
    buffer = _ShapeBuffer(
        content,
        member_name=member_name,
        feature_ordinal=feature_ordinal,
    )
    shape_type = buffer.int32("shape type")
    if shape_type == 0:
        buffer.finish()
        return None
    if shape_type != expected_shape_type:
        raise ParcelShapefileError(
            "shapefile_record_shape_type_mismatch",
            "Shapefile feature type differs from the dataset header",
            details={
                **buffer.details,
                "record_shape_type": shape_type,
                "header_shape_type": expected_shape_type,
            },
        )
    details = {**buffer.details, "shape_type": shape_type}
    base: dict[str, Any] = {
        "shape_type": shape_type,
        "shape_type_name": SHAPE_TYPE_NAMES[shape_type],
        "coordinates": "published_native_crs",
        "transformed": False,
    }

    if shape_type in POINT_TYPES:
        x, y = buffer.doubles(2, "point coordinates")
        coordinate = [
            _finite(x, label="x coordinate", details=details),
            _finite(y, label="y coordinate", details=details),
        ]
        dimensions = ["x", "y"]
        measure: float | None = None
        if shape_type in Z_TYPES:
            z = buffer.doubles(1, "point Z coordinate")[0]
            coordinate.append(
                _finite(z, label="z coordinate", details=details)
            )
            dimensions.append("z")
            if buffer.remaining:
                if buffer.remaining != 8:
                    raise ParcelShapefileError(
                        "shapefile_point_measure_length_invalid",
                        "PointZ optional measure has an unexpected length",
                        details={
                            **details,
                            "remaining_bytes": buffer.remaining,
                        },
                    )
                measure = _measure(
                    buffer.doubles(1, "point measure")[0]
                )
        elif shape_type in M_TYPES:
            measure = _measure(buffer.doubles(1, "point measure")[0])
        buffer.finish()
        base.update(
            {
                "geometry_type": "point",
                "coordinate_dimensions": dimensions,
                "coordinates_native": coordinate,
                "measure": measure,
            }
        )
        return base

    if shape_type in MULTIPOINT_TYPES:
        bounds = _native_bounds(
            buffer.doubles(4, "multipoint bounds"),
            details=details,
        )
        point_count = buffer.int32("point count")
        points = _native_points(
            buffer.doubles(point_count * 2, "point coordinates"),
            details=details,
        )
        z_range: dict[str, float] | None = None
        z_values: list[float] | None = None
        measure_range: dict[str, float | None] | None = None
        measures: list[float | None] | None = None
        dimensions = ["x", "y"]
        if shape_type in Z_TYPES:
            z_min, z_max = buffer.doubles(2, "Z range")
            z_range = {
                "minimum": _finite(z_min, label="zmin", details=details),
                "maximum": _finite(z_max, label="zmax", details=details),
            }
            z_values = [
                _finite(
                    value,
                    label="z coordinate",
                    details={**details, "point_index": index},
                )
                for index, value in enumerate(
                    buffer.doubles(point_count, "Z array")
                )
            ]
            dimensions.append("z")
            for index, point in enumerate(points):
                point.append(z_values[index])
            measure_range, measures = _parse_optional_measures(
                buffer,
                point_count=point_count,
            )
        elif shape_type in M_TYPES:
            measure_range, measures = _parse_optional_measures(
                buffer,
                point_count=point_count,
            )
        buffer.finish()
        base.update(
            {
                "geometry_type": "multipoint",
                "coordinate_dimensions": dimensions,
                "bounds": bounds,
                "point_count": point_count,
                "coordinates_native": points,
                "z_range": z_range,
                "measure_range": measure_range,
                "measures": measures,
            }
        )
        return base

    if shape_type in POLYLINE_TYPES | POLYGON_TYPES:
        bounds = _native_bounds(
            buffer.doubles(4, "part bounds"),
            details=details,
        )
        part_count = buffer.int32("part count")
        point_count = buffer.int32("point count")
        part_offsets = buffer.int32s(part_count, "part offsets")
        if point_count == 0 and part_count != 0:
            raise ParcelShapefileError(
                "shapefile_part_index_invalid",
                "Shapefile has parts but no points",
                details={
                    **details,
                    "part_count": part_count,
                    "point_count": point_count,
                },
            )
        if point_count > 0:
            if not part_offsets or part_offsets[0] != 0:
                raise ParcelShapefileError(
                    "shapefile_part_index_invalid",
                    "First shapefile part does not begin at point zero",
                    details={
                        **details,
                        "part_offsets": list(part_offsets),
                        "point_count": point_count,
                    },
                )
            if (
                any(value < 0 or value >= point_count for value in part_offsets)
                or any(
                    part_offsets[index] >= part_offsets[index + 1]
                    for index in range(len(part_offsets) - 1)
                )
            ):
                raise ParcelShapefileError(
                    "shapefile_part_index_invalid",
                    "Shapefile part offsets are outside or out of order",
                    details={
                        **details,
                        "part_offsets": list(part_offsets),
                        "point_count": point_count,
                    },
                )
        points = _native_points(
            buffer.doubles(point_count * 2, "part coordinates"),
            details=details,
        )
        dimensions = ["x", "y"]
        z_range: dict[str, float] | None = None
        z_values: list[float] | None = None
        measure_range: dict[str, float | None] | None = None
        measures: list[float | None] | None = None
        if shape_type in Z_TYPES:
            z_min, z_max = buffer.doubles(2, "Z range")
            z_range = {
                "minimum": _finite(z_min, label="zmin", details=details),
                "maximum": _finite(z_max, label="zmax", details=details),
            }
            z_values = [
                _finite(
                    value,
                    label="z coordinate",
                    details={**details, "point_index": index},
                )
                for index, value in enumerate(
                    buffer.doubles(point_count, "Z array")
                )
            ]
            dimensions.append("z")
            for index, point in enumerate(points):
                point.append(z_values[index])
            measure_range, measures = _parse_optional_measures(
                buffer,
                point_count=point_count,
            )
        elif shape_type in M_TYPES:
            measure_range, measures = _parse_optional_measures(
                buffer,
                point_count=point_count,
            )
        buffer.finish()
        parts = []
        for part_index, start in enumerate(part_offsets):
            end = (
                part_offsets[part_index + 1]
                if part_index + 1 < len(part_offsets)
                else point_count
            )
            part_points = points[start:end]
            part: dict[str, Any] = {
                "part_index": part_index,
                "start_point_index": start,
                "end_point_index_exclusive": end,
                "coordinates_native": part_points,
            }
            if measures is not None:
                part["measures"] = measures[start:end]
            if shape_type in POLYGON_TYPES:
                part["ring_orientation"] = _ring_orientation(part_points)
                part["ring_topology"] = (
                    "source_part_preserved_without_exterior_hole_inference"
                )
            parts.append(part)
        base.update(
            {
                "geometry_type": (
                    "polygon_parts"
                    if shape_type in POLYGON_TYPES
                    else "polyline_parts"
                ),
                "coordinate_dimensions": dimensions,
                "bounds": bounds,
                "part_count": part_count,
                "point_count": point_count,
                "multipart": part_count > 1,
                "parts": parts,
                "z_range": z_range,
                "measure_range": measure_range,
            }
        )
        return base

    raise ParcelShapefileError(
        "shapefile_shape_type_unsupported",
        "Shapefile record type is not decoded by this module",
        details=details,
    )


def _parcel_join(
    record: DBFRecord,
    *,
    fields: Sequence[str],
) -> dict[str, Any]:
    candidates = []
    values: list[str] = []
    for field_name in fields:
        raw_value = record.raw_text.get(field_name)
        value = _text(raw_value)
        state = "published_value" if value is not None else "blank_in_source"
        candidates.append(
            {
                "field": field_name,
                "raw_value": raw_value,
                "value": value,
                "state": state,
            }
        )
        if value is not None and value not in values:
            values.append(value)
    selected: dict[str, Any] | None = None
    if not fields:
        state = "no_conservative_join_field"
    elif not values:
        state = "source_join_key_blank"
    elif len(values) == 1:
        state = "join_candidate_present"
        selected = {
            "value": values[0],
            "fields": [
                candidate["field"]
                for candidate in candidates
                if candidate["value"] == values[0]
            ],
        }
    else:
        state = "multiple_distinct_join_candidates"
    return {
        "state": state,
        "selected": selected,
        "distinct_nonblank_values": values,
        "candidates": candidates,
        "normalization": "whitespace_trim_only",
        "feature_identity_uses_join_value": False,
    }


def _feature_occurrence(
    *,
    inspection: ShapefileDatasetInspection,
    feature_ordinal: int,
    source_record_number: int,
    index_entry: ShapeIndexEntry,
    dbf_record: DBFRecord,
    geometry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    occurrence_payload = {
        "source_id": inspection.source_id,
        "release_id": inspection.release_id,
        "artifact_sha256": inspection.artifact_sha256,
        "member_identity_sha256": inspection.member_identity_sha256,
        "shp_member": inspection.members.shp,
        "feature_ordinal": feature_ordinal,
        "source_record_number": source_record_number,
        "dbf_member": inspection.members.dbf,
        "dbf_record_index": dbf_record.record_index,
    }
    occurrence_id = sha256_fingerprint(occurrence_payload)
    return {
        "canonical_ref": f"SHAPEFILE-FEATURE:{occurrence_id}",
        "evidence_ref": (
            f"SHAPEFILE:{inspection.artifact_sha256}:"
            f"{inspection.member_identity_sha256}:{feature_ordinal}"
        ),
        "source_id": inspection.source_id,
        "release_id": inspection.release_id,
        "record_kind": "parcel_shapefile_feature_occurrence",
        "feature_occurrence": {
            "occurrence_id": occurrence_id,
            "feature_ordinal": feature_ordinal,
            "source_record_number": source_record_number,
            "dbf_record_index": dbf_record.record_index,
            "shx_offset_bytes": index_entry.offset_bytes,
            "shape_content_length_bytes": index_entry.content_length_bytes,
            "identity_fields": [
                "source_id",
                "release_id",
                "artifact_sha256",
                "member_identity_sha256",
                "shp_member",
                "feature_ordinal",
                "source_record_number",
                "dbf_member",
                "dbf_record_index",
            ],
        },
        "parcel_join": _parcel_join(
            dbf_record,
            fields=inspection.parcel_join_fields,
        ),
        "dbf_record": {
            "record_index": dbf_record.record_index,
            "deleted": dbf_record.deleted,
            "attributes": dict(dbf_record.attributes),
            "raw_text": dict(dbf_record.raw_text),
            "trailing_bytes_hex": dbf_record.trailing_bytes_hex,
        },
        "geometry": dict(geometry) if geometry is not None else None,
        "geometry_state": (
            "decoded_native_crs" if geometry is not None else "null_shape"
        ),
        "crs": inspection.crs.to_dict(),
        "source_lineage": {
            "artifact_path": inspection.path,
            "container": inspection.container,
            "artifact_sha256": inspection.artifact_sha256,
            "artifact_identity_kind": inspection.artifact_identity_kind,
            "release_id": inspection.release_id,
            "dataset_member": inspection.members.shp,
            "members": inspection.members.to_dict(),
            "member_identity_sha256": inspection.member_identity_sha256,
            "schema_fingerprint": inspection.schema_fingerprint,
        },
    }


def iter_shapefile_features(
    path: Path | str,
    *,
    dataset_member: str | None = None,
    source_id: str = DEFAULT_SOURCE_ID,
    release_id: str | None = None,
    parcel_fields: Sequence[str] | None = None,
    policy: ArchiveSafetyPolicy | None = None,
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    inspection: ShapefileDatasetInspection | None = None,
    _artifact: LocalShapefileArtifact | None = None,
    start_feature_ordinal: int = 0,
) -> Iterator[dict[str, Any]]:
    _positive(max_record_bytes, "max_record_bytes")
    artifact = _artifact or LocalShapefileArtifact(path, policy=policy)
    if artifact.path != Path(path).expanduser().resolve():
        raise ValueError("_artifact does not belong to path")
    current = inspection or _inspect_artifact(
        artifact,
        dataset_member=dataset_member,
        source_id=source_id,
        release_id=release_id,
        parcel_fields=parcel_fields,
    )
    selected = artifact.select_dataset(current.members.shp)
    if (
        isinstance(start_feature_ordinal, bool)
        or not isinstance(start_feature_ordinal, int)
        or start_feature_ordinal < 0
        or start_feature_ordinal > current.feature_count
    ):
        raise ValueError(
            "start_feature_ordinal must be within the feature table"
        )
    if (
        artifact.artifact_sha256 != current.artifact_sha256
        or artifact.member_identity(selected) != current.member_identity_sha256
    ):
        raise ParcelShapefileError(
            "shapefile_artifact_changed_during_decode",
            "Local shapefile artifact changed after inspection",
            details={
                "inspected_artifact_sha256": current.artifact_sha256,
                "observed_artifact_sha256": artifact.artifact_sha256,
            },
        )

    with (
        artifact.open_member(selected.shp) as shp_stream,
        artifact.open_member(selected.shx) as shx_stream,
        artifact.open_member(selected.dbf) as dbf_stream,
    ):
        index_entries = _iter_shape_index_entries(
            shx_stream,
            current.shx,
            start_feature_ordinal=start_feature_ordinal,
        )
        dbf_records = _iter_dbf_records(
            dbf_stream,
            current.dbf,
            start_record=start_feature_ordinal,
        )
        expected_shp_offset: int | None = None
        for feature_ordinal in range(
            start_feature_ordinal,
            current.feature_count,
        ):
            try:
                index_entry = next(index_entries)
                dbf_record = next(dbf_records)
            except StopIteration as error:
                raise ParcelShapefileError(
                    "shapefile_aligned_stream_ended_early",
                    "SHP sidecar streams ended before their declared count",
                    details={"feature_ordinal": feature_ordinal},
                ) from error
            if expected_shp_offset is None:
                expected_shp_offset = index_entry.offset_bytes
                _position_stream(
                    shp_stream,
                    expected_shp_offset,
                    code="shapefile_shp_position_failed",
                    message=(
                        "Could not position the SHP stream at the requested "
                        "feature"
                    ),
                    details={
                        "member": selected.shp,
                        "feature_ordinal": feature_ordinal,
                    },
                )
            record_header = _read_exact(
                shp_stream,
                8,
                code="shapefile_record_header_truncated",
                message="SHP feature record header is truncated",
                details={
                    "member": selected.shp,
                    "feature_ordinal": feature_ordinal,
                },
            )
            source_record_number, length_words = struct.unpack(
                ">2i",
                record_header,
            )
            content_length_bytes = length_words * 2
            if source_record_number <= 0 or content_length_bytes < 4:
                raise ParcelShapefileError(
                    "shapefile_record_header_invalid",
                    "SHP feature record has an invalid number or length",
                    details={
                        "member": selected.shp,
                        "feature_ordinal": feature_ordinal,
                        "source_record_number": source_record_number,
                        "content_length_bytes": content_length_bytes,
                    },
                )
            if (
                index_entry.feature_ordinal != feature_ordinal
                or index_entry.offset_bytes != expected_shp_offset
                or index_entry.content_length_bytes != content_length_bytes
            ):
                raise ParcelShapefileError(
                    "shapefile_shx_alignment_mismatch",
                    "SHX entry does not describe the aligned SHP feature",
                    details={
                        "feature_ordinal": feature_ordinal,
                        "expected_shp_offset": expected_shp_offset,
                        "shx_offset_bytes": index_entry.offset_bytes,
                        "shp_content_length_bytes": content_length_bytes,
                        "shx_content_length_bytes": (
                            index_entry.content_length_bytes
                        ),
                    },
                )
            if dbf_record.record_index != feature_ordinal:
                raise ParcelShapefileError(
                    "shapefile_dbf_alignment_mismatch",
                    "DBF record index does not align with the SHP feature",
                    details={
                        "feature_ordinal": feature_ordinal,
                        "dbf_record_index": dbf_record.record_index,
                    },
                )
            if content_length_bytes > max_record_bytes:
                raise ParcelShapefileError(
                    "shapefile_record_exceeds_bound",
                    "SHP feature record exceeds the requested decode bound",
                    details={
                        "feature_ordinal": feature_ordinal,
                        "content_length_bytes": content_length_bytes,
                        "max_record_bytes": max_record_bytes,
                    },
                )
            content = _read_exact(
                shp_stream,
                content_length_bytes,
                code="shapefile_record_content_truncated",
                message="SHP feature record content is truncated",
                details={
                    "member": selected.shp,
                    "feature_ordinal": feature_ordinal,
                },
            )
            geometry = _geometry_record(
                content,
                expected_shape_type=current.shp.shape_type,
                member_name=selected.shp,
                feature_ordinal=feature_ordinal,
            )
            yield _feature_occurrence(
                inspection=current,
                feature_ordinal=feature_ordinal,
                source_record_number=source_record_number,
                index_entry=index_entry,
                dbf_record=dbf_record,
                geometry=geometry,
            )
            expected_shp_offset += 8 + content_length_bytes
        if (
            start_feature_ordinal < current.feature_count
            and expected_shp_offset != current.shp.file_length_bytes
        ):
            raise ParcelShapefileError(
                "shapefile_shp_record_table_length_mismatch",
                "Decoded SHP records do not reach the declared file length",
                details={
                    "decoded_length_bytes": expected_shp_offset,
                    "declared_length_bytes": current.shp.file_length_bytes,
                },
            )


def _cursor_encode(
    *,
    inspection: ShapefileDatasetInspection,
    query_fingerprint: str,
    next_feature_ordinal: int,
) -> str:
    payload = canonical_json(
        {
            "version": 1,
            "artifact_sha256": inspection.artifact_sha256,
            "dataset_member": inspection.members.shp,
            "member_identity_sha256": inspection.member_identity_sha256,
            "schema_fingerprint": inspection.schema_fingerprint,
            "query_fingerprint": query_fingerprint,
            "next_feature_ordinal": next_feature_ordinal,
        }
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _cursor_decode(
    cursor: str | None,
    *,
    inspection: ShapefileDatasetInspection,
    query_fingerprint: str,
) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise ParcelShapefileError(
            "shapefile_cursor_invalid",
            "Shapefile cursor has an invalid prefix",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        payload_bytes = base64.urlsafe_b64decode(
            token + "=" * (-len(token) % 4)
        )
        payload = json.loads(payload_bytes)
    except (
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as error:
        raise ParcelShapefileError(
            "shapefile_cursor_invalid",
            "Shapefile cursor is malformed",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("version") != 1:
        raise ParcelShapefileError(
            "shapefile_cursor_invalid",
            "Shapefile cursor payload or version is invalid",
        )
    expected = {
        "artifact_sha256": inspection.artifact_sha256,
        "dataset_member": inspection.members.shp,
        "member_identity_sha256": inspection.member_identity_sha256,
        "schema_fingerprint": inspection.schema_fingerprint,
        "query_fingerprint": query_fingerprint,
    }
    mismatches = {
        key: {
            "cursor": payload.get(key),
            "current": value,
        }
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if mismatches:
        raise ParcelShapefileError(
            "shapefile_cursor_context_changed",
            "Shapefile cursor does not match the artifact, member, schema, or query",
            details={"mismatches": mismatches},
        )
    ordinal = payload.get("next_feature_ordinal")
    if (
        isinstance(ordinal, bool)
        or not isinstance(ordinal, int)
        or ordinal < 0
        or ordinal > inspection.feature_count
    ):
        raise ParcelShapefileError(
            "shapefile_cursor_ordinal_invalid",
            "Shapefile cursor feature ordinal is invalid",
            details={
                "next_feature_ordinal": ordinal,
                "feature_count": inspection.feature_count,
            },
        )
    return ordinal


def _match_values(record: Mapping[str, Any], fields: Sequence[str]) -> list[str]:
    dbf_record = record.get("dbf_record")
    if not isinstance(dbf_record, Mapping):
        return []
    attributes = dbf_record.get("attributes")
    raw_text = dbf_record.get("raw_text")
    if not isinstance(attributes, Mapping) or not isinstance(raw_text, Mapping):
        return []
    values: list[str] = []
    for field_name in fields:
        for candidate in (
            raw_text.get(field_name),
            attributes.get(field_name),
        ):
            value = _text(candidate)
            if value is not None and value not in values:
                values.append(value)
    return values


def _record_matches(
    record: Mapping[str, Any],
    *,
    query: str | None,
    fields: Sequence[str],
    match: str,
) -> bool:
    if query is None:
        return True
    normalized_query = _text(query)
    if normalized_query is None:
        raise ValueError("query must not be blank")
    needle = normalized_query.casefold()
    for value in _match_values(record, fields):
        candidate = value.casefold()
        if match == "exact" and candidate == needle:
            return True
        if match == "prefix" and candidate.startswith(needle):
            return True
        if match == "contains" and needle in candidate:
            return True
    return False


def search_shapefile_dataset(
    path: Path | str,
    query: str | None = None,
    *,
    dataset_member: str | None = None,
    source_id: str = DEFAULT_SOURCE_ID,
    release_id: str | None = None,
    parcel_fields: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
    match: str = "contains",
    limit: int = DEFAULT_RESULT_LIMIT,
    scan_limit: int = DEFAULT_SCAN_LIMIT,
    cursor: str | None = None,
    policy: ArchiveSafetyPolicy | None = None,
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
) -> FeaturePage:
    _positive(limit, "limit")
    _positive(scan_limit, "scan_limit")
    _positive(max_record_bytes, "max_record_bytes")
    if match not in {"exact", "prefix", "contains"}:
        raise ValueError("match must be exact, prefix, or contains")
    if query is not None and _text(query) is None:
        raise ValueError("query must not be blank")
    artifact = LocalShapefileArtifact(path, policy=policy)
    inspection = _inspect_artifact(
        artifact,
        dataset_member=dataset_member,
        source_id=source_id,
        release_id=release_id,
        parcel_fields=parcel_fields,
    )
    resolved_fields = _resolve_fields(
        inspection.dbf,
        fields,
        role="search",
    )
    query_payload = {
        "operation": "features" if query is None else "search",
        "query": _text(query).casefold() if query is not None else None,
        "fields": list(resolved_fields),
        "match": match,
        "parcel_join_fields": list(inspection.parcel_join_fields),
        "source_id": inspection.source_id,
        "release_id": inspection.release_id,
    }
    query_fingerprint = sha256_fingerprint(query_payload)
    start_ordinal = _cursor_decode(
        cursor,
        inspection=inspection,
        query_fingerprint=query_fingerprint,
    )
    records: list[Mapping[str, Any]] = []
    scanned_count = 0
    next_ordinal: int | None = None
    stop_reason = "end_of_dataset"
    exhausted = True

    for record in iter_shapefile_features(
        path,
        dataset_member=inspection.members.shp,
        source_id=inspection.source_id,
        release_id=inspection.release_id,
        parcel_fields=inspection.parcel_join_fields,
        policy=policy,
        max_record_bytes=max_record_bytes,
        inspection=inspection,
        _artifact=artifact,
        start_feature_ordinal=start_ordinal,
    ):
        occurrence = record["feature_occurrence"]
        ordinal = int(occurrence["feature_ordinal"])
        scanned_count += 1
        matched = _record_matches(
            record,
            query=query,
            fields=resolved_fields,
            match=match,
        )
        if matched:
            records.append(record)
        has_remaining_features = ordinal + 1 < inspection.feature_count
        if len(records) >= limit and has_remaining_features:
            next_ordinal = ordinal + 1
            stop_reason = "result_limit"
            exhausted = False
            break
        if scanned_count >= scan_limit and has_remaining_features:
            next_ordinal = ordinal + 1
            stop_reason = "scan_limit"
            exhausted = False
            break

    next_cursor = (
        _cursor_encode(
            inspection=inspection,
            query_fingerprint=query_fingerprint,
            next_feature_ordinal=next_ordinal,
        )
        if next_ordinal is not None
        else None
    )
    return FeaturePage(
        inspection=inspection,
        records=tuple(records),
        query_contract=query_payload,
        query_fingerprint=query_fingerprint,
        start_feature_ordinal=start_ordinal,
        result_limit=limit,
        scan_limit=scan_limit,
        scanned_count=scanned_count,
        next_cursor=next_cursor,
        exhausted=exhausted,
        stop_reason=stop_reason,
    )


def _archive_policy(args: argparse.Namespace) -> ArchiveSafetyPolicy:
    return ArchiveSafetyPolicy(
        max_members=args.max_archive_members,
        max_total_uncompressed_bytes=args.max_archive_uncompressed_bytes,
        max_member_uncompressed_bytes=args.max_member_uncompressed_bytes,
        max_compression_ratio=args.max_compression_ratio,
    )


def _add_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dataset-member",
        help="SHP member path or same-stem dataset name when an archive has several",
    )
    parser.add_argument(
        "--source-id",
        default=DEFAULT_SOURCE_ID,
        help="Publishing source identifier retained in feature lineage",
    )
    parser.add_argument(
        "--release-id",
        help="Publisher release identity; otherwise the local artifact digest is used",
    )
    parser.add_argument(
        "--parcel-field",
        action="append",
        dest="parcel_fields",
        help=(
            "DBF field to retain as a parcel join candidate; repeat for "
            "multiple published keys"
        ),
    )


def _add_archive_policy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-archive-members", type=int)
    parser.add_argument("--max-archive-uncompressed-bytes", type=int)
    parser.add_argument("--max-member-uncompressed-bytes", type=int)
    parser.add_argument("--max-compression-ratio", type=float)


def _add_page_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=DEFAULT_RESULT_LIMIT)
    parser.add_argument(
        "--scan-limit",
        type=int,
        default=DEFAULT_SCAN_LIMIT,
        help="Maximum feature occurrences examined in this invocation",
    )
    parser.add_argument("--cursor")
    parser.add_argument(
        "--max-record-bytes",
        type=int,
        default=DEFAULT_MAX_RECORD_BYTES,
        help="Maximum uncompressed bytes decoded for one SHP feature",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect and stream local official parcel shapefile occurrences"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect aligned SHP/SHX/DBF headers and CRS metadata",
    )
    inspect_parser.add_argument("artifact", type=Path)
    _add_identity_args(inspect_parser)
    _add_archive_policy_args(inspect_parser)
    add_output_args(inspect_parser)

    features_parser = subparsers.add_parser(
        "features",
        help="Return a bounded page of feature occurrences",
    )
    features_parser.add_argument("artifact", type=Path)
    _add_identity_args(features_parser)
    _add_archive_policy_args(features_parser)
    _add_page_args(features_parser)
    add_output_args(features_parser)

    search_parser = subparsers.add_parser(
        "search",
        help="Search DBF attributes and return aligned feature occurrences",
    )
    search_parser.add_argument("artifact", type=Path)
    search_parser.add_argument("query")
    _add_identity_args(search_parser)
    _add_archive_policy_args(search_parser)
    _add_page_args(search_parser)
    search_parser.add_argument(
        "--field",
        action="append",
        dest="fields",
        help="DBF field to search; repeat to search several fields",
    )
    search_parser.add_argument(
        "--match",
        choices=("exact", "prefix", "contains"),
        default="contains",
    )
    add_output_args(search_parser)
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    policy = _archive_policy(args)
    common = {
        "dataset_member": args.dataset_member,
        "source_id": args.source_id,
        "release_id": args.release_id,
        "parcel_fields": args.parcel_fields,
        "policy": policy,
    }
    if args.command == "inspect":
        inspection = inspect_shapefile_dataset(args.artifact, **common)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "operation": "inspect",
            "identity": inspection.identity_dict(),
            "records": [
                {
                    "record_kind": "parcel_shapefile_dataset_inspection",
                    "inspection": inspection.to_dict(),
                }
            ],
            "next_cursor": None,
            "raw_artifact_refs": [inspection.path],
        }
    page = search_shapefile_dataset(
        args.artifact,
        args.query if args.command == "search" else None,
        fields=args.fields if args.command == "search" else None,
        match=args.match if args.command == "search" else "contains",
        limit=args.limit,
        scan_limit=args.scan_limit,
        cursor=args.cursor,
        max_record_bytes=args.max_record_bytes,
        **common,
    )
    return page.to_dict(operation=args.command)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = execute(args)
    except ParcelShapefileError as error:
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "operation": args.command,
            "records": [],
            "next_cursor": None,
            "raw_artifact_refs": [str(args.artifact)],
            "error": error.to_dict(),
        }
    summary = f"parcel shapefile {args.command}"
    if write_output(result, args, summary=summary):
        return
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
