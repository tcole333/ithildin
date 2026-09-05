#!/usr/bin/env python3
"""Extract local FileGDB feature occurrences through GDAL OpenFileGDB.

The Esri File Geodatabase table format is not decoded directly here.  A mature
GDAL build is the byte-format backend; this module supplies the source-neutral
identity, pagination, join-candidate, and native-geometry contracts around it.

The repository does not bundle GDAL.  ``backend`` and ``container`` remain
useful without it, while dataset inspection and feature extraction report the
missing dependency explicitly.  A suitable installation provides both
``ogrinfo`` and ``ogr2ogr`` with the built-in ``OpenFileGDB`` driver.

Feature pages are selected with OGRSQL and materialized to a temporary
GeoPackage.  No source or destination SRS override is supplied.  Geometry is
returned as OGC WKB in the published native CRS, alongside the source and
materialized CRS metadata.  The wrapper does not claim source-byte identity:
GDAL performs the FileGDB-to-OGC geometry serialization.

Examples:
    uv run python tools/public_records_filegdb.py backend
    uv run python tools/public_records_filegdb.py container Parcels.zip
    uv run python tools/public_records_filegdb.py inspect Parcels.zip \
        --source-id us-tx-hcad-parcel-gis --release-id 2026-current
    uv run python tools/public_records_filegdb.py features Parcels.zip \
        --source-id us-tx-hcad-parcel-gis --release-id 2026-current \
        --layer Parcels --parcel-field HCAD_NUM --limit 100 \
        --output /tmp/hcad-filegdb-page.json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        ArchiveSafetyError,
        ArchiveSafetyPolicy,
        file_sha256,
        inspect_zip,
    )
    from tools.public_records_contract import canonical_json, sha256_fingerprint
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        ArchiveSafetyError,
        ArchiveSafetyPolicy,
        file_sha256,
        inspect_zip,
    )
    from public_records_contract import canonical_json, sha256_fingerprint


SCHEMA_VERSION = "public-records-filegdb/1.0"
CURSOR_PREFIX = "parcel-filegdb:v1:"
DEFAULT_SOURCE_ID = "local-parcel-filegdb"
DEFAULT_RESULT_LIMIT = 100
DEFAULT_BACKEND_TIMEOUT = 300
PAGE_TABLE = "__ithildin_filegdb_page__"
SOURCE_FID_ALIAS = "__ithildin_source_fid__"

GDAL_OPENFILEGDB_DOC = (
    "https://gdal.org/en/stable/drivers/vector/openfilegdb.html"
)
GDAL_OGRINFO_DOC = "https://gdal.org/en/stable/programs/ogrinfo.html"

# Conservative parcel keys only.  OBJECTID/FID/GLOBALID identify source
# occurrences and therefore are deliberately not treated as parcel joins.
CONSERVATIVE_PARCEL_FIELDS = (
    "HCAD_NUM",
    "ACCTID",
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
    "PARID",
)

# These geometry families round-trip through the ordinary OGC geometry model
# used by GeoPackage/WKB.  Curves, TIN, polyhedral surfaces, and other extended
# families are left to a future backend with explicit fixture coverage.
SUPPORTED_GEOMETRY_TYPES = frozenset(
    {
        "GEOMETRY",
        "POINT",
        "LINESTRING",
        "POLYGON",
        "MULTIPOINT",
        "MULTILINESTRING",
        "MULTIPOLYGON",
        "GEOMETRYCOLLECTION",
    }
)


class FileGDBError(ValueError):
    """A FileGDB container or decode contract cannot be satisfied."""

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


class FileGDBDependencyError(FileGDBError):
    """The explicit GDAL/OpenFileGDB backend is unavailable."""


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).replace("\x00", "").strip()
    return normalized or None


def _positive(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _nonnegative(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _gdal_version_pair(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    match = re.search(r"\bGDAL\s+(\d+)\.(\d+)", value, re.I)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def _gdal_driver_capabilities(
    formats_output: str,
    driver_name: str,
) -> str | None:
    match = re.search(
        rf"(?im)^\s*{re.escape(driver_name)}\b[^\r\n]*?\(([^)]*)\)",
        formats_output,
    )
    return match.group(1).casefold() if match is not None else None


def _json_value(value: Any) -> Any:
    """Detach a value through the repository's canonical JSON contract."""

    return json.loads(canonical_json(value))


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_sqlite_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _gdb_roots(paths: Sequence[str]) -> tuple[str, ...]:
    roots: set[str] = set()
    for raw_path in paths:
        path = PurePosixPath(raw_path)
        for index, part in enumerate(path.parts):
            if part.casefold().endswith(".gdb"):
                roots.add("/".join(path.parts[: index + 1]))
                break
    return tuple(sorted(roots, key=str.casefold))


def _stream_sha256(stream: Any) -> tuple[str, int]:
    digest = hashlib.sha256()
    observed_size = 0
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
        observed_size += len(chunk)
    return digest.hexdigest(), observed_size


def _gdb_logical_identity(
    gdb_member: str,
    members: Sequence[Mapping[str, Any]],
) -> str:
    logical_members = []
    for member in members:
        relative_path = str(member.get("relative_path") or "")
        kind = str(member.get("kind") or "")
        if kind != "file":
            continue
        logical_members.append(
            {
                "relative_path": relative_path,
                "size": member.get("size"),
                "content_sha256": member.get("content_sha256"),
            }
        )
    logical_members.sort(
        key=lambda member: str(member["relative_path"]).casefold()
    )
    return sha256_fingerprint(
        {
            "format": "filegdb-logical-member/1.0",
            "gdb_name": PurePosixPath(gdb_member).name,
            "members": logical_members,
        }
    )


def _select_gdb_root(
    roots: Sequence[str],
    requested: str | None,
) -> str:
    if requested is None:
        if len(roots) != 1:
            raise FileGDBError(
                "filegdb_member_selection_required",
                "Select one FileGDB member from this container",
                details={"available_gdb_members": list(roots)},
            )
        return roots[0]
    normalized = str(PurePosixPath(requested))
    matches = [root for root in roots if root.casefold() == normalized.casefold()]
    if len(matches) != 1:
        raise FileGDBError(
            "filegdb_member_not_found",
            "Requested FileGDB member is not present in this container",
            details={
                "requested_gdb_member": requested,
                "available_gdb_members": list(roots),
            },
        )
    return matches[0]


@dataclass(frozen=True)
class FileGDBContainerInspection:
    path: str
    container: str
    artifact_sha256: str
    artifact_identity_kind: str
    artifact_size: int | None
    available_gdb_members: tuple[str, ...]
    gdb_member: str
    gdb_member_identity_sha256: str
    gdb_members: tuple[Mapping[str, Any], ...]
    gdal_datasource: str
    archive: Mapping[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "path": self.path,
            "container": self.container,
            "artifact_sha256": self.artifact_sha256,
            "artifact_identity_kind": self.artifact_identity_kind,
            "artifact_size": self.artifact_size,
            "available_gdb_members": list(self.available_gdb_members),
            "gdb_member": self.gdb_member,
            "gdb_member_identity_sha256": (
                self.gdb_member_identity_sha256
            ),
            "gdb_members": [_json_value(member) for member in self.gdb_members],
            "gdal_datasource": self.gdal_datasource,
            "archive": (
                _json_value(self.archive) if self.archive is not None else None
            ),
        }


def _inspect_gdb_directory(
    path: Path,
    *,
    gdb_member: str | None,
) -> FileGDBContainerInspection:
    if not path.name.casefold().endswith(".gdb"):
        raise FileGDBError(
            "filegdb_directory_suffix_invalid",
            "A directory input must itself be a .gdb directory",
            details={"path": str(path)},
        )
    selected = _select_gdb_root((path.name,), gdb_member)
    members: list[dict[str, Any]] = []
    for child in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if child.is_symlink():
            raise FileGDBError(
                "filegdb_directory_link_unsupported",
                "FileGDB directory contains a symbolic link",
                details={"path": str(child)},
            )
        if child.is_dir():
            continue
        if not child.is_file():
            raise FileGDBError(
                "filegdb_directory_special_member",
                "FileGDB directory contains a non-regular member",
                details={"path": str(child)},
            )
        relative = child.relative_to(path).as_posix()
        before = child.stat()
        content_sha256 = file_sha256(child)
        after = child.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or getattr(before, "st_ino", None) != getattr(after, "st_ino", None)
        ):
            raise FileGDBError(
                "filegdb_artifact_changed_during_inspection",
                "FileGDB directory changed while it was being fingerprinted",
                details={"path": str(child)},
            )
        members.append(
            {
                "path": f"{selected}/{relative}",
                "relative_path": relative,
                "kind": "file",
                "size": after.st_size,
                "content_sha256": content_sha256,
            }
        )
    if not members:
        raise FileGDBError(
            "filegdb_directory_empty",
            "FileGDB directory contains no regular files",
            details={"path": str(path)},
        )
    digest = _gdb_logical_identity(selected, members)
    return FileGDBContainerInspection(
        path=str(path),
        container="directory",
        artifact_sha256=digest,
        artifact_identity_kind="directory_member_manifest_sha256",
        artifact_size=sum(int(member["size"]) for member in members),
        available_gdb_members=(path.name,),
        gdb_member=selected,
        gdb_member_identity_sha256=digest,
        gdb_members=tuple(members),
        gdal_datasource=str(path),
        archive=None,
    )


def _inspect_gdb_zip(
    path: Path,
    *,
    gdb_member: str | None,
    policy: ArchiveSafetyPolicy | None,
) -> FileGDBContainerInspection:
    try:
        archive = inspect_zip(path, policy=policy)
    except ArchiveSafetyError as error:
        raise FileGDBError(
            "filegdb_archive_unsafe",
            "FileGDB ZIP failed archive safety inspection",
            details=getattr(error, "details", {"error": str(error)}),
        ) from error
    archive_dict = archive.to_dict()
    paths = [str(member["path"]) for member in archive.members]
    roots = _gdb_roots(paths)
    if not roots:
        raise FileGDBError(
            "filegdb_member_missing",
            "ZIP archive contains no .gdb directory",
            details={"path": str(path)},
        )
    selected = _select_gdb_root(roots, gdb_member)
    prefix = f"{selected}/"
    selected_parts = PurePosixPath(selected).parts
    selected_ancestors = {
        "/".join(selected_parts[:index])
        for index in range(1, len(selected_parts) + 1)
    }
    file_paths = {
        str(member["path"])
        for member in archive.members
        if member.get("kind") == "file"
    }
    ancestor_file_collisions = sorted(file_paths & selected_ancestors)
    selected_namespace_paths = {
        str(member["path"])
        for member in archive.members
        if (
            str(member["path"]) == selected
            or str(member["path"]).startswith(prefix)
        )
    }
    descendant_file_collisions = sorted(
        file_path
        for file_path in file_paths
        if file_path.startswith(prefix)
        and any(
            candidate.startswith(f"{file_path}/")
            for candidate in selected_namespace_paths
        )
    )
    if ancestor_file_collisions or descendant_file_collisions:
        raise FileGDBError(
            "filegdb_member_namespace_collision",
            "Selected .gdb path collides with a regular ZIP member",
            details={
                "gdb_member": selected,
                "ancestor_file_collisions": ancestor_file_collisions,
                "descendant_file_collisions": descendant_file_collisions,
            },
        )
    selected_archive_members = tuple(
        _json_value(member)
        for member in archive.members
        if (
            str(member["path"]) == selected
            or str(member["path"]).startswith(prefix)
        )
    )
    if not any(
        member.get("kind") == "file"
        and str(member.get("path") or "").startswith(prefix)
        for member in selected_archive_members
    ):
        raise FileGDBError(
            "filegdb_member_empty",
            "Selected .gdb member contains no descendant regular files",
            details={"gdb_member": selected},
        )
    try:
        with zipfile.ZipFile(path) as source:
            info_by_path: dict[str, zipfile.ZipInfo] = {}
            for info in source.infolist():
                normalized = "/".join(
                    part
                    for part in PurePosixPath(info.filename).parts
                    if part not in {"", "."}
                )
                info_by_path[normalized] = info
            members: list[dict[str, Any]] = []
            for archive_member in selected_archive_members:
                member = dict(archive_member)
                member_path = str(member["path"])
                member["relative_path"] = (
                    member_path[len(prefix) :]
                    if member_path.startswith(prefix)
                    else ""
                )
                if member.get("kind") == "file":
                    info = info_by_path.get(member_path)
                    if info is None:
                        raise FileGDBError(
                            "filegdb_archive_changed_during_inspection",
                            "Selected FileGDB member disappeared during hashing",
                            details={"member": member_path},
                        )
                    with source.open(info, "r") as stream:
                        content_sha256, observed_size = _stream_sha256(
                            stream
                        )
                    if observed_size != int(member["size"]):
                        raise FileGDBError(
                            "filegdb_archive_changed_during_inspection",
                            "Selected FileGDB member size changed during hashing",
                            details={
                                "member": member_path,
                                "inspected_size": member["size"],
                                "observed_size": observed_size,
                            },
                        )
                    member["content_sha256"] = content_sha256
                members.append(member)
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise FileGDBError(
            "filegdb_archive_changed_during_inspection",
            "FileGDB ZIP changed or became unreadable during hashing",
            details={"path": str(path), "error": str(error)},
        ) from error
    try:
        observed_archive_sha256 = file_sha256(path)
    except OSError as error:
        raise FileGDBError(
            "filegdb_archive_changed_during_inspection",
            "FileGDB ZIP changed or became unreadable during hashing",
            details={"path": str(path), "error": str(error)},
        ) from error
    if observed_archive_sha256 != archive.archive_sha256:
        raise FileGDBError(
            "filegdb_archive_changed_during_inspection",
            "FileGDB ZIP changed while it was being fingerprinted",
            details={
                "inspected_artifact_sha256": archive.archive_sha256,
                "observed_artifact_sha256": observed_archive_sha256,
            },
        )
    member_identity = _gdb_logical_identity(selected, members)
    # /vsizip/ followed by an absolute POSIX path intentionally has a double
    # slash after the prefix, e.g. /vsizip//Users/.../Parcels.zip/Parcels.gdb.
    datasource = f"/vsizip/{path.as_posix()}/{selected}"
    return FileGDBContainerInspection(
        path=str(path),
        container="zip",
        artifact_sha256=archive.archive_sha256,
        artifact_identity_kind="archive_sha256",
        artifact_size=archive.archive_size,
        available_gdb_members=tuple(roots),
        gdb_member=selected,
        gdb_member_identity_sha256=member_identity,
        gdb_members=tuple(members),
        gdal_datasource=datasource,
        archive=archive_dict,
    )


def inspect_filegdb_container(
    path: Path | str,
    *,
    gdb_member: str | None = None,
    policy: ArchiveSafetyPolicy | None = None,
) -> FileGDBContainerInspection:
    """Inspect a .gdb directory or safe ZIP member without invoking GDAL."""

    artifact_path = Path(path).expanduser().resolve()
    if artifact_path.is_dir():
        return _inspect_gdb_directory(
            artifact_path,
            gdb_member=gdb_member,
        )
    if not artifact_path.is_file():
        raise FileGDBError(
            "filegdb_artifact_missing",
            "FileGDB artifact does not exist",
            details={"path": str(artifact_path)},
        )
    if not zipfile.is_zipfile(artifact_path):
        raise FileGDBError(
            "filegdb_container_unsupported",
            "FileGDB file input must be a ZIP archive",
            details={"path": str(artifact_path)},
        )
    return _inspect_gdb_zip(
        artifact_path,
        gdb_member=gdb_member,
        policy=policy,
    )


def _container_identity(
    inspection: FileGDBContainerInspection,
) -> dict[str, Any]:
    return {
        "container": inspection.container,
        "artifact_sha256": inspection.artifact_sha256,
        "gdb_member": inspection.gdb_member,
        "gdb_member_identity_sha256": (
            inspection.gdb_member_identity_sha256
        ),
    }


def _assert_container_unchanged(
    expected: FileGDBContainerInspection,
    *,
    policy: ArchiveSafetyPolicy | None,
    operation: str,
) -> FileGDBContainerInspection:
    try:
        observed = inspect_filegdb_container(
            expected.path,
            gdb_member=expected.gdb_member,
            policy=policy,
        )
    except FileGDBError as error:
        raise FileGDBError(
            "filegdb_artifact_changed_during_decode",
            f"FileGDB artifact changed during {operation}",
            details={
                "operation": operation,
                "expected": _container_identity(expected),
                "reinspection_error": error.to_dict(),
            },
        ) from error
    expected_identity = _container_identity(expected)
    observed_identity = _container_identity(observed)
    if observed_identity != expected_identity:
        raise FileGDBError(
            "filegdb_artifact_changed_during_decode",
            f"FileGDB artifact changed during {operation}",
            details={
                "operation": operation,
                "expected": expected_identity,
                "observed": observed_identity,
            },
        )
    return observed


@dataclass(frozen=True)
class BackendStatus:
    available: bool
    backend: str
    ogrinfo_path: str | None
    ogr2ogr_path: str | None
    gdal_version: str | None
    openfilegdb_driver: bool
    reason: str | None
    inspection_available: bool
    extraction_available: bool
    ogr2ogr_version: str | None
    ogr2ogr_openfilegdb_driver: bool
    gpkg_write_driver: bool
    inspection_reason: str | None
    extraction_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "inspection_available": self.inspection_available,
            "extraction_available": self.extraction_available,
            "backend": self.backend,
            "ogrinfo_path": self.ogrinfo_path,
            "ogr2ogr_path": self.ogr2ogr_path,
            "gdal_version": self.gdal_version,
            "ogr2ogr_version": self.ogr2ogr_version,
            "openfilegdb_driver": self.openfilegdb_driver,
            "ogr2ogr_openfilegdb_driver": (
                self.ogr2ogr_openfilegdb_driver
            ),
            "gpkg_write_driver": self.gpkg_write_driver,
            "reason": self.reason,
            "inspection_reason": self.inspection_reason,
            "extraction_reason": self.extraction_reason,
            "dependency": {
                "requirement": (
                    "ogrinfo from GDAL 3.7+ with OpenFileGDB for inspection; "
                    "ogr2ogr from GDAL 3.7+ with OpenFileGDB read and GPKG "
                    "write support for extraction"
                ),
                "openfilegdb_documentation": GDAL_OPENFILEGDB_DOC,
                "ogrinfo_documentation": GDAL_OGRINFO_DOC,
            },
        }


@dataclass(frozen=True)
class ExtractedFeature:
    native_fid: int
    attributes: Mapping[str, Any]
    geometry: Mapping[str, Any] | None
    materialized_ordinal: int


@dataclass(frozen=True)
class BackendFeaturePage:
    features: tuple[ExtractedFeature, ...]
    requested_offset: int
    requested_limit: int
    materialized_schema: Mapping[str, Any]
    backend: Mapping[str, Any]


class FileGDBBackend(Protocol):
    def status(self) -> BackendStatus:
        """Return backend availability and implementation identity."""

    def inspect(
        self,
        container: FileGDBContainerInspection,
    ) -> Mapping[str, Any]:
        """Return an ogrinfo-compatible dataset metadata mapping."""

    def extract_page(
        self,
        container: FileGDBContainerInspection,
        layer: "FileGDBLayerInspection",
        *,
        offset: int,
        limit: int,
        include_geometry: bool,
    ) -> BackendFeaturePage:
        """Return at most *limit* source features from one layer."""


class GDALCLIBackend:
    """GDAL command-line backend using OpenFileGDB and temporary GeoPackage."""

    def __init__(
        self,
        *,
        ogrinfo: str | None = None,
        ogr2ogr: str | None = None,
        timeout: int = DEFAULT_BACKEND_TIMEOUT,
    ) -> None:
        self.ogrinfo = ogrinfo
        self.ogr2ogr = ogr2ogr
        self.timeout = _positive(timeout, "timeout")
        self._status: BackendStatus | None = None

    def _run(
        self,
        command: Sequence[str],
        *,
        operation: str,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                list(command),
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise FileGDBDependencyError(
                "filegdb_backend_invocation_failed",
                f"GDAL backend failed during {operation}",
                details={
                    "operation": operation,
                    "error": str(error),
                    "command": list(command[:2]),
                },
            ) from error
        if result.returncode != 0:
            raise FileGDBError(
                "filegdb_backend_command_failed",
                f"GDAL backend rejected the FileGDB during {operation}",
                details={
                    "operation": operation,
                    "returncode": result.returncode,
                    "stderr": result.stderr[-8000:],
                },
            )
        return result

    def status(self) -> BackendStatus:
        if self._status is not None:
            return self._status
        ogrinfo_path = self.ogrinfo or shutil.which("ogrinfo")
        ogr2ogr_path = self.ogr2ogr or shutil.which("ogr2ogr")
        ogrinfo_version: str | None = None
        ogr2ogr_version: str | None = None
        ogrinfo_openfilegdb = False
        ogr2ogr_openfilegdb = False
        gpkg_write = False
        inspection_reason: str | None = None
        extraction_reason: str | None = None

        if not ogrinfo_path:
            inspection_reason = "ogrinfo is required for FileGDB inspection"
        else:
            try:
                version_result = self._run(
                    (ogrinfo_path, "--version"),
                    operation="ogrinfo version check",
                )
                formats_result = self._run(
                    (ogrinfo_path, "--formats"),
                    operation="ogrinfo driver check",
                )
            except FileGDBError as error:
                inspection_reason = str(error)
            else:
                ogrinfo_version = _text(version_result.stdout)
                version_pair = _gdal_version_pair(ogrinfo_version)
                openfilegdb_capabilities = _gdal_driver_capabilities(
                    formats_result.stdout,
                    "OpenFileGDB",
                )
                ogrinfo_openfilegdb = bool(
                    openfilegdb_capabilities
                    and "r" in openfilegdb_capabilities
                )
                if not ogrinfo_openfilegdb:
                    inspection_reason = (
                        "OpenFileGDB read driver is not available to ogrinfo"
                    )
                elif version_pair is None:
                    inspection_reason = "GDAL version could not be verified"
                elif version_pair < (3, 7):
                    inspection_reason = (
                        "ogrinfo JSON metadata requires GDAL 3.7 or newer"
                    )

        inspection_available = inspection_reason is None
        if not inspection_available:
            extraction_reason = (
                "FileGDB inspection capability is unavailable: "
                f"{inspection_reason}"
            )
        elif not ogr2ogr_path:
            extraction_reason = "ogr2ogr is required for feature extraction"
        else:
            try:
                ogr2ogr_version_result = self._run(
                    (ogr2ogr_path, "--version"),
                    operation="ogr2ogr version check",
                )
                ogr2ogr_formats_result = self._run(
                    (ogr2ogr_path, "--formats"),
                    operation="ogr2ogr driver check",
                )
            except FileGDBError as error:
                extraction_reason = str(error)
            else:
                ogr2ogr_version = _text(ogr2ogr_version_result.stdout)
                ogr2ogr_version_pair = _gdal_version_pair(ogr2ogr_version)
                ogr2ogr_openfilegdb_capabilities = (
                    _gdal_driver_capabilities(
                        ogr2ogr_formats_result.stdout,
                        "OpenFileGDB",
                    )
                )
                gpkg_capabilities = _gdal_driver_capabilities(
                    ogr2ogr_formats_result.stdout,
                    "GPKG",
                )
                ogr2ogr_openfilegdb = bool(
                    ogr2ogr_openfilegdb_capabilities
                    and "r" in ogr2ogr_openfilegdb_capabilities
                )
                gpkg_write = bool(
                    gpkg_capabilities and "w" in gpkg_capabilities
                )
                if ogr2ogr_version_pair is None:
                    extraction_reason = (
                        "ogr2ogr GDAL version could not be verified"
                    )
                elif ogr2ogr_version_pair < (3, 7):
                    extraction_reason = (
                        "FileGDB extraction requires ogr2ogr from GDAL 3.7 "
                        "or newer"
                    )
                elif not ogr2ogr_openfilegdb:
                    extraction_reason = (
                        "OpenFileGDB read driver is not available to ogr2ogr"
                    )
                elif not gpkg_write:
                    extraction_reason = (
                        "GPKG write driver is not available to ogr2ogr"
                    )

        extraction_available = extraction_reason is None
        reason = inspection_reason or extraction_reason
        self._status = BackendStatus(
            available=extraction_available,
            backend="gdal-openfilegdb-cli",
            ogrinfo_path=ogrinfo_path,
            ogr2ogr_path=ogr2ogr_path,
            gdal_version=ogrinfo_version,
            openfilegdb_driver=ogrinfo_openfilegdb,
            reason=reason,
            inspection_available=inspection_available,
            extraction_available=extraction_available,
            ogr2ogr_version=ogr2ogr_version,
            ogr2ogr_openfilegdb_driver=ogr2ogr_openfilegdb,
            gpkg_write_driver=gpkg_write,
            inspection_reason=inspection_reason,
            extraction_reason=extraction_reason,
        )
        return self._status

    def _require_status(self, *, extraction: bool) -> BackendStatus:
        status = self.status()
        capability_available = (
            status.extraction_available
            if extraction
            else status.inspection_available
        )
        if not capability_available:
            raise FileGDBDependencyError(
                "filegdb_backend_unavailable",
                "GDAL OpenFileGDB backend is unavailable",
                details=status.to_dict(),
            )
        return status

    def inspect(
        self,
        container: FileGDBContainerInspection,
    ) -> Mapping[str, Any]:
        status = self._require_status(extraction=False)
        if status.ogrinfo_path is None:
            raise FileGDBDependencyError(
                "filegdb_backend_unavailable",
                "GDAL backend status omitted the ogrinfo executable",
                details=status.to_dict(),
            )
        result = self._run(
            (
                status.ogrinfo_path,
                "-json",
                "-ro",
                "-if",
                "OpenFileGDB",
                container.gdal_datasource,
            ),
            operation="dataset inspection",
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise FileGDBError(
                "filegdb_backend_metadata_invalid",
                "ogrinfo returned invalid JSON metadata",
                details={"error": str(error)},
            ) from error
        if not isinstance(payload, Mapping):
            raise FileGDBError(
                "filegdb_backend_metadata_invalid",
                "ogrinfo metadata root is not an object",
            )
        return payload

    def extract_page(
        self,
        container: FileGDBContainerInspection,
        layer: "FileGDBLayerInspection",
        *,
        offset: int,
        limit: int,
        include_geometry: bool,
    ) -> BackendFeaturePage:
        status = self._require_status(extraction=True)
        if status.ogr2ogr_path is None:
            raise FileGDBDependencyError(
                "filegdb_backend_unavailable",
                "GDAL backend status omitted the ogr2ogr executable",
                details=status.to_dict(),
            )
        _nonnegative(offset, "offset")
        _positive(limit, "limit")
        if SOURCE_FID_ALIAS.casefold() in {
            field["name"].casefold() for field in layer.fields
        }:
            raise FileGDBError(
                "filegdb_reserved_field_collision",
                "Source layer contains the reserved FID projection field",
                details={
                    "layer": layer.name,
                    "field": SOURCE_FID_ALIAS,
                },
            )
        _require_supported_geometry(layer)
        sql = (
            f"SELECT FID AS {_quote_identifier(SOURCE_FID_ALIAS)}, * "
            f"FROM {_quote_identifier(layer.name)} "
            f"ORDER BY FID LIMIT {limit} OFFSET {offset}"
        )
        with tempfile.TemporaryDirectory(
            prefix="ithildin-filegdb-"
        ) as workdir:
            destination = Path(workdir) / "page.gpkg"
            command = (
                status.ogr2ogr_path,
                "-f",
                "GPKG",
                "-overwrite",
                "-if",
                "OpenFileGDB",
                "-nln",
                PAGE_TABLE,
                "-dialect",
                "OGRSQL",
                "-sql",
                sql,
                str(destination),
                container.gdal_datasource,
            )
            self._run(command, operation="feature page extraction")
            features, schema = _read_geopackage_page(
                destination,
                source_layer=layer,
                include_geometry=include_geometry,
            )
        return BackendFeaturePage(
            features=tuple(features),
            requested_offset=offset,
            requested_limit=limit,
            materialized_schema=schema,
            backend=status.to_dict(),
        )


def _normalize_field(field: Mapping[str, Any]) -> dict[str, Any]:
    name = _text(field.get("name"))
    field_type = _text(field.get("type"))
    if name is None or field_type is None:
        raise FileGDBError(
            "filegdb_layer_schema_invalid",
            "FileGDB field metadata lacks a name or type",
            details={"field": _json_value(field)},
        )
    normalized = {
        key: _json_value(value)
        for key, value in field.items()
        if key
        in {
            "name",
            "type",
            "subType",
            "width",
            "precision",
            "nullable",
            "uniqueConstraint",
            "defaultValue",
            "alias",
            "domainName",
            "comment",
            "timezone",
        }
    }
    normalized["name"] = name
    normalized["type"] = field_type
    return normalized


def _normalize_geometry_field(field: Mapping[str, Any]) -> dict[str, Any]:
    geometry_type = _text(field.get("type"))
    if geometry_type is None:
        raise FileGDBError(
            "filegdb_layer_schema_invalid",
            "FileGDB geometry metadata lacks a type",
            details={"geometry_field": _json_value(field)},
        )
    normalized = _json_value(field)
    normalized["name"] = _text(field.get("name")) or ""
    normalized["type"] = geometry_type
    return normalized


def _feature_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise FileGDBError(
            "filegdb_layer_schema_invalid",
            "FileGDB feature count is not numeric",
            details={"feature_count": value},
        )
    if isinstance(value, (int, float)) and float(value).is_integer():
        count = int(value)
        if count >= 0:
            return count
    raise FileGDBError(
        "filegdb_layer_schema_invalid",
        "FileGDB feature count is invalid",
        details={"feature_count": value},
    )


def _resolve_parcel_fields(
    fields: Sequence[Mapping[str, Any]],
    requested: Sequence[str] | None,
    *,
    require_all: bool = True,
) -> tuple[str, ...]:
    lookup = {str(field["name"]).casefold(): str(field["name"]) for field in fields}
    if requested is None:
        return tuple(
            lookup[name.casefold()]
            for name in CONSERVATIVE_PARCEL_FIELDS
            if name.casefold() in lookup
        )
    resolved: list[str] = []
    missing: list[str] = []
    for raw in requested:
        name = _text(raw)
        observed = lookup.get(name.casefold()) if name else None
        if observed is None:
            missing.append(str(raw))
        elif observed not in resolved:
            resolved.append(observed)
    if missing and require_all:
        raise FileGDBError(
            "filegdb_parcel_field_missing",
            "Requested parcel join field is absent from the source layer",
            details={
                "missing_fields": missing,
                "available_fields": [field["name"] for field in fields],
            },
        )
    return tuple(resolved)


@dataclass(frozen=True)
class FileGDBLayerInspection:
    name: str
    feature_count: int | None
    fid_column_name: str | None
    fields: tuple[Mapping[str, Any], ...]
    geometry_fields: tuple[Mapping[str, Any], ...]
    parcel_join_fields: tuple[str, ...]
    metadata: Mapping[str, Any]
    schema_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "feature_count": self.feature_count,
            "fid_column_name": self.fid_column_name,
            "fields": [_json_value(field) for field in self.fields],
            "geometry_fields": [
                _json_value(field) for field in self.geometry_fields
            ],
            "parcel_join_fields": list(self.parcel_join_fields),
            "metadata": _json_value(self.metadata),
            "schema_fingerprint": self.schema_fingerprint,
            "feature_identity": {
                "source_occurrence": (
                    "native OGR FID within artifact, geodatabase member, "
                    "and layer"
                ),
                "parcel_fields_are_joins": True,
            },
        }


@dataclass(frozen=True)
class FileGDBDatasetInspection:
    container: FileGDBContainerInspection
    source_id: str
    release_id: str
    release_identity_state: str
    backend: BackendStatus
    driver_short_name: str
    driver_long_name: str | None
    layers: tuple[FileGDBLayerInspection, ...]
    metadata: Mapping[str, Any]
    dataset_schema_fingerprint: str

    def layer(self, name: str) -> FileGDBLayerInspection:
        matches = [
            layer for layer in self.layers if layer.name.casefold() == name.casefold()
        ]
        if len(matches) != 1:
            raise FileGDBError(
                "filegdb_layer_not_found",
                "Requested FileGDB layer is not present",
                details={
                    "requested_layer": name,
                    "available_layers": [layer.name for layer in self.layers],
                },
            )
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_id": self.source_id,
            "release_id": self.release_id,
            "release_identity_state": self.release_identity_state,
            "container": self.container.to_dict(),
            "backend": self.backend.to_dict(),
            "driver_short_name": self.driver_short_name,
            "driver_long_name": self.driver_long_name,
            "layers": [layer.to_dict() for layer in self.layers],
            "metadata": _json_value(self.metadata),
            "dataset_schema_fingerprint": self.dataset_schema_fingerprint,
        }


def _normalize_dataset_metadata(
    payload: Mapping[str, Any],
    *,
    container: FileGDBContainerInspection,
    source_id: str,
    release_id: str | None,
    parcel_fields: Sequence[str] | None,
    backend_status: BackendStatus,
) -> FileGDBDatasetInspection:
    driver = _text(payload.get("driverShortName"))
    if driver != "OpenFileGDB":
        raise FileGDBError(
            "filegdb_backend_driver_mismatch",
            "GDAL did not open the dataset with OpenFileGDB",
            details={"driver_short_name": driver},
        )
    raw_layers = payload.get("layers")
    if not isinstance(raw_layers, Sequence) or isinstance(
        raw_layers, (str, bytes)
    ):
        raise FileGDBError(
            "filegdb_backend_metadata_invalid",
            "ogrinfo metadata has no layer list",
        )
    layers: list[FileGDBLayerInspection] = []
    for raw_layer in raw_layers:
        if not isinstance(raw_layer, Mapping):
            raise FileGDBError(
                "filegdb_layer_schema_invalid",
                "FileGDB layer metadata is not an object",
            )
        name = _text(raw_layer.get("name"))
        if name is None:
            raise FileGDBError(
                "filegdb_layer_schema_invalid",
                "FileGDB layer metadata lacks a name",
            )
        raw_fields = raw_layer.get("fields") or []
        raw_geometry = raw_layer.get("geometryFields") or []
        if (
            not isinstance(raw_fields, Sequence)
            or isinstance(raw_fields, (str, bytes))
            or not isinstance(raw_geometry, Sequence)
            or isinstance(raw_geometry, (str, bytes))
        ):
            raise FileGDBError(
                "filegdb_layer_schema_invalid",
                "FileGDB layer fields are not arrays",
                details={"layer": name},
            )
        fields = tuple(
            _normalize_field(field)
            for field in raw_fields
            if isinstance(field, Mapping)
        )
        geometry_fields = tuple(
            _normalize_geometry_field(field)
            for field in raw_geometry
            if isinstance(field, Mapping)
        )
        if len(fields) != len(raw_fields) or len(geometry_fields) != len(
            raw_geometry
        ):
            raise FileGDBError(
                "filegdb_layer_schema_invalid",
                "FileGDB layer contains invalid field metadata",
                details={"layer": name},
            )
        folded = [str(field["name"]).casefold() for field in fields]
        if len(set(folded)) != len(folded):
            raise FileGDBError(
                "filegdb_layer_fields_duplicated",
                "FileGDB layer field names collide case-insensitively",
                details={"layer": name},
            )
        resolved_joins = _resolve_parcel_fields(
            fields,
            parcel_fields,
            require_all=False,
        )
        layer_schema_payload = {
            "name": name,
            "fid_column_name": _text(raw_layer.get("fidColumnName")),
            "fields": list(fields),
            "geometry_fields": list(geometry_fields),
        }
        observed_feature_count = _feature_count(
            raw_layer.get("featureCount")
        )
        observed_fid_column = _text(raw_layer.get("fidColumnName"))
        layers.append(
            FileGDBLayerInspection(
                name=name,
                feature_count=observed_feature_count,
                fid_column_name=observed_fid_column,
                fields=fields,
                geometry_fields=geometry_fields,
                parcel_join_fields=resolved_joins,
                metadata=_json_value(raw_layer.get("metadata") or {}),
                schema_fingerprint=sha256_fingerprint(
                    layer_schema_payload
                ),
            )
        )
    if not layers:
        raise FileGDBError(
            "filegdb_layers_empty",
            "OpenFileGDB reported no user-visible layers",
        )
    folded_layers = [layer.name.casefold() for layer in layers]
    if len(set(folded_layers)) != len(folded_layers):
        raise FileGDBError(
            "filegdb_layers_duplicated",
            "FileGDB layer names collide case-insensitively",
            details={"layers": [layer.name for layer in layers]},
        )
    normalized_source = _text(source_id)
    if normalized_source is None:
        raise ValueError("source_id must not be blank")
    normalized_release = _text(release_id)
    release_state = "caller_supplied"
    if normalized_release is None:
        normalized_release = f"artifact:{container.artifact_sha256}"
        release_state = "derived_from_artifact_for_local_decode"
    schema_payload = {
        "format": SCHEMA_VERSION,
        "layers": [
            {
                "name": layer.name,
                "schema_fingerprint": layer.schema_fingerprint,
            }
            for layer in layers
        ],
    }
    return FileGDBDatasetInspection(
        container=container,
        source_id=normalized_source,
        release_id=normalized_release,
        release_identity_state=release_state,
        backend=backend_status,
        driver_short_name=driver,
        driver_long_name=_text(payload.get("driverLongName")),
        layers=tuple(layers),
        metadata={
            key: _json_value(payload.get(key))
            for key in ("metadata", "domains", "relationships", "groups")
            if payload.get(key) is not None
        },
        dataset_schema_fingerprint=sha256_fingerprint(schema_payload),
    )


def inspect_filegdb_dataset(
    path: Path | str,
    *,
    gdb_member: str | None = None,
    source_id: str = DEFAULT_SOURCE_ID,
    release_id: str | None = None,
    parcel_fields: Sequence[str] | None = None,
    policy: ArchiveSafetyPolicy | None = None,
    backend: FileGDBBackend | None = None,
) -> FileGDBDatasetInspection:
    """Inspect FileGDB layers and schemas through an explicit backend."""

    container = inspect_filegdb_container(
        path,
        gdb_member=gdb_member,
        policy=policy,
    )
    active_backend = backend or GDALCLIBackend()
    status = active_backend.status()
    if not status.inspection_available:
        raise FileGDBDependencyError(
            "filegdb_backend_unavailable",
            "GDAL OpenFileGDB backend is unavailable",
            details=status.to_dict(),
        )
    try:
        payload = active_backend.inspect(container)
    except Exception:
        _assert_container_unchanged(
            container,
            policy=policy,
            operation="backend inspection",
        )
        raise
    _assert_container_unchanged(
        container,
        policy=policy,
        operation="backend inspection",
    )
    return _normalize_dataset_metadata(
        payload,
        container=container,
        source_id=source_id,
        release_id=release_id,
        parcel_fields=parcel_fields,
        backend_status=status,
    )


def _base_geometry_type(value: str) -> str:
    normalized = re.sub(r"[\s_-]+", "", value).upper()
    return re.sub(r"(ZM|Z|M)$", "", normalized)


def _require_supported_geometry(layer: FileGDBLayerInspection) -> None:
    if len(layer.geometry_fields) > 1:
        raise FileGDBError(
            "filegdb_multiple_geometry_fields_unsupported",
            "This extraction backend covers layers with at most one geometry field",
            details={
                "layer": layer.name,
                "geometry_fields": [
                    field.get("name") for field in layer.geometry_fields
                ],
            },
        )
    if not layer.geometry_fields:
        return
    geometry_type = str(layer.geometry_fields[0]["type"])
    if _base_geometry_type(geometry_type) not in SUPPORTED_GEOMETRY_TYPES:
        raise FileGDBError(
            "filegdb_geometry_family_unsupported",
            "Layer geometry family lacks a verified GeoPackage/WKB extraction contract",
            details={
                "layer": layer.name,
                "geometry_type": geometry_type,
                "supported_geometry_families": sorted(
                    SUPPORTED_GEOMETRY_TYPES
                ),
            },
        )


def _sqlite_table_info(
    connection: sqlite3.Connection,
    table: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        f"PRAGMA table_info({_quote_sqlite_identifier(table)})"
    ).fetchall()
    return [
        {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "primary_key_order": row[5],
        }
        for row in rows
    ]


def _json_attribute(value: Any) -> Any:
    if isinstance(value, bytes):
        return {
            "encoding": "base64",
            "data": base64.b64encode(value).decode("ascii"),
            "byte_length": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    if isinstance(value, float) and not math.isfinite(value):
        return {
            "encoding": "non_finite_float",
            "value": repr(value),
        }
    return value


WKB_LINEAR_FAMILIES = {
    1: "Point",
    2: "LineString",
    3: "Polygon",
    4: "MultiPoint",
    5: "MultiLineString",
    6: "MultiPolygon",
    7: "GeometryCollection",
}
WKB_COLLECTION_MEMBERS = {
    4: 1,
    5: 2,
    6: 3,
}
MAX_WKB_NESTING = 256


class _WKBReader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def take(self, length: int, label: str) -> bytes:
        if length < 0 or length > self.remaining:
            raise FileGDBError(
                "filegdb_wkb_truncated",
                f"Materialized WKB ended while reading {label}",
                details={
                    "offset": self.offset,
                    "requested_bytes": length,
                    "remaining_bytes": self.remaining,
                },
            )
        end = self.offset + length
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def byte(self, label: str) -> int:
        return self.take(1, label)[0]

    def uint32(self, endian: str, label: str) -> int:
        return struct.unpack(f"{endian}I", self.take(4, label))[0]


def _wkb_type_contract(
    raw_type: int,
) -> tuple[int, bool, bool, bool]:
    ewkb_z = bool(raw_type & 0x80000000)
    ewkb_m = bool(raw_type & 0x40000000)
    ewkb_srid = bool(raw_type & 0x20000000)
    normalized = raw_type & 0x1FFFFFFF
    iso_z = False
    iso_m = False
    if 3000 <= normalized < 4000:
        normalized -= 3000
        iso_z = True
        iso_m = True
    elif 2000 <= normalized < 3000:
        normalized -= 2000
        iso_m = True
    elif 1000 <= normalized < 2000:
        normalized -= 1000
        iso_z = True
    if (ewkb_z or ewkb_m) and (iso_z or iso_m):
        raise FileGDBError(
            "filegdb_wkb_dimensional_encoding_invalid",
            "Materialized WKB mixes EWKB and ISO dimensional type encodings",
            details={"raw_type_code": raw_type},
        )
    if normalized in range(8, 18):
        raise FileGDBError(
            "filegdb_wkb_geometry_family_unsupported",
            "Materialized WKB contains a nonlinear or extended geometry family",
            details={
                "raw_type_code": raw_type,
                "base_type_code": normalized,
            },
        )
    if normalized not in WKB_LINEAR_FAMILIES:
        raise FileGDBError(
            "filegdb_wkb_type_unsupported",
            "Materialized WKB contains an unknown geometry type",
            details={
                "raw_type_code": raw_type,
                "base_type_code": normalized,
            },
        )
    return normalized, ewkb_z or iso_z, ewkb_m or iso_m, ewkb_srid


def _wkb_dimensions(has_z: bool, has_m: bool) -> tuple[int, str]:
    if has_z and has_m:
        return 4, "XYZM"
    if has_z:
        return 3, "XYZ"
    if has_m:
        return 3, "XYM"
    return 2, "XY"


def _validate_wkb_geometry(
    reader: _WKBReader,
    *,
    depth: int,
    expected_base_type: int | None,
    state: dict[str, Any],
) -> int:
    if depth > MAX_WKB_NESTING:
        raise FileGDBError(
            "filegdb_wkb_nesting_exceeded",
            "Materialized WKB geometry nesting is excessive",
            details={"max_nesting": MAX_WKB_NESTING},
        )
    byte_order = reader.byte("geometry byte order")
    if byte_order not in {0, 1}:
        raise FileGDBError(
            "filegdb_wkb_byte_order_invalid",
            "Materialized WKB has an invalid byte-order marker",
            details={"byte_order": byte_order},
        )
    endian = "<" if byte_order == 1 else ">"
    raw_type = reader.uint32(endian, "geometry type")
    base_type, has_z, has_m, has_srid = _wkb_type_contract(raw_type)
    if expected_base_type is not None and base_type != expected_base_type:
        raise FileGDBError(
            "filegdb_wkb_collection_member_invalid",
            "Materialized WKB collection contains the wrong member family",
            details={
                "expected_base_type": expected_base_type,
                "observed_base_type": base_type,
                "raw_type_code": raw_type,
            },
        )
    if has_srid:
        embedded_srid = reader.uint32(endian, "EWKB SRID")
        raise FileGDBError(
            "filegdb_wkb_embedded_srid_unsupported",
            "GeoPackage WKB must not override the GeoPackage header SRS",
            details={
                "raw_type_code": raw_type,
                "embedded_srid": embedded_srid,
                "depth": depth,
            },
        )
    dimensions, dimension_name = _wkb_dimensions(has_z, has_m)
    family = WKB_LINEAR_FAMILIES[base_type]
    state["geometry_count"] += 1
    state["max_depth"] = max(state["max_depth"], depth)
    if family not in state["families"]:
        state["families"].append(family)
    if dimension_name not in state["coordinate_dimensions"]:
        state["coordinate_dimensions"].append(dimension_name)
    state["geometry_dimensions"].append(
        {
            "depth": depth,
            "family": family,
            "has_z": has_z,
            "has_m": has_m,
            "coordinate_dimension": dimension_name,
        }
    )
    if depth == 0:
        state["top_level_raw_type_code"] = raw_type
        state["top_level_family"] = family
        state["top_level_byte_order"] = (
            "little" if byte_order == 1 else "big"
        )

    if base_type == 1:
        reader.take(dimensions * 8, "point coordinates")
        return base_type
    if base_type == 2:
        point_count = reader.uint32(endian, "line point count")
        reader.take(
            point_count * dimensions * 8,
            "line coordinates",
        )
        return base_type
    if base_type == 3:
        ring_count = reader.uint32(endian, "polygon ring count")
        if ring_count > reader.remaining // 4:
            raise FileGDBError(
                "filegdb_wkb_count_invalid",
                "Materialized WKB polygon ring count exceeds its bytes",
                details={
                    "ring_count": ring_count,
                    "remaining_bytes": reader.remaining,
                },
            )
        for _ in range(ring_count):
            point_count = reader.uint32(endian, "ring point count")
            reader.take(
                point_count * dimensions * 8,
                "ring coordinates",
            )
        return base_type

    geometry_count = reader.uint32(endian, "collection geometry count")
    if geometry_count > reader.remaining // 5:
        raise FileGDBError(
            "filegdb_wkb_count_invalid",
            "Materialized WKB collection count exceeds its bytes",
            details={
                "geometry_count": geometry_count,
                "remaining_bytes": reader.remaining,
            },
        )
    expected_child = WKB_COLLECTION_MEMBERS.get(base_type)
    for _ in range(geometry_count):
        _validate_wkb_geometry(
            reader,
            depth=depth + 1,
            expected_base_type=expected_child,
            state=state,
        )
    return base_type


def _validate_linear_wkb(wkb: bytes) -> dict[str, Any]:
    if len(wkb) < 5:
        raise FileGDBError(
            "filegdb_wkb_truncated",
            "Materialized geometry has no complete WKB header",
        )
    reader = _WKBReader(wkb)
    state: dict[str, Any] = {
        "geometry_count": 0,
        "max_depth": 0,
        "families": [],
        "coordinate_dimensions": [],
        "geometry_dimensions": [],
        "top_level_raw_type_code": None,
        "top_level_family": None,
        "top_level_byte_order": None,
    }
    _validate_wkb_geometry(
        reader,
        depth=0,
        expected_base_type=None,
        state=state,
    )
    if reader.remaining:
        raise FileGDBError(
            "filegdb_wkb_trailing_bytes",
            "Materialized WKB contains trailing bytes",
            details={"trailing_bytes": reader.remaining},
        )
    return state


def _parse_geopackage_geometry(blob: bytes) -> dict[str, Any]:
    if len(blob) < 8 or blob[:2] != b"GP":
        raise FileGDBError(
            "filegdb_materialized_geometry_invalid",
            "Materialized geometry is not a GeoPackage geometry blob",
        )
    version = blob[2]
    flags = blob[3]
    if flags & 0x20:
        raise FileGDBError(
            "filegdb_gpkg_extended_geometry_unsupported",
            "GeoPackage page contains an extended geometry encoding",
        )
    little_endian = bool(flags & 0x01)
    endian = "<" if little_endian else ">"
    envelope_code = (flags >> 1) & 0x07
    envelope_lengths = {
        0: 0,
        1: 4,
        2: 6,
        3: 6,
        4: 8,
    }
    if version != 0 or envelope_code not in envelope_lengths:
        raise FileGDBError(
            "filegdb_materialized_geometry_invalid",
            "GeoPackage geometry header is unsupported",
            details={
                "version": version,
                "envelope_code": envelope_code,
            },
        )
    srs_id = struct.unpack(f"{endian}i", blob[4:8])[0]
    envelope_count = envelope_lengths[envelope_code]
    header_length = 8 + envelope_count * 8
    if len(blob) < header_length:
        raise FileGDBError(
            "filegdb_materialized_geometry_invalid",
            "GeoPackage geometry envelope is truncated",
        )
    envelope = (
        list(
            struct.unpack(
                f"{endian}{envelope_count}d",
                blob[8:header_length],
            )
        )
        if envelope_count
        else []
    )
    wkb = blob[header_length:]
    empty = bool(flags & 0x10)
    validation = _validate_linear_wkb(wkb)
    return {
        "encoding": "ogc_wkb",
        "wkb_base64": base64.b64encode(wkb).decode("ascii"),
        "wkb_byte_length": len(wkb),
        "wkb_sha256": hashlib.sha256(wkb).hexdigest(),
        "wkb_byte_order": validation["top_level_byte_order"],
        "wkb_type_code": validation["top_level_raw_type_code"],
        "wkb_validation": validation,
        "gpkg_header": {
            "version": version,
            "byte_order": "little" if little_endian else "big",
            "srs_id": srs_id,
            "envelope_code": envelope_code,
            "envelope": envelope,
            "empty": empty,
            "extended_geometry": bool(flags & 0x20),
        },
        "coordinates": "published_native_crs",
        "transformed": False,
        "source_byte_identity": False,
        "serialization": (
            "GDAL OpenFileGDB read followed by GeoPackage/OGC WKB"
        ),
    }


def _validate_geopackage_dimensions(
    geometry_metadata: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> None:
    dimension_rows = validation.get("geometry_dimensions")
    if not isinstance(dimension_rows, Sequence) or isinstance(
        dimension_rows,
        (str, bytes),
    ):
        raise FileGDBError(
            "filegdb_materialized_geometry_dimension_invalid",
            "Validated WKB omitted its coordinate-dimension contract",
        )
    for axis, key in (("Z", "has_z"), ("M", "has_m")):
        raw_constraint = geometry_metadata.get(axis.casefold())
        if (
            isinstance(raw_constraint, bool)
            or not isinstance(raw_constraint, int)
            or raw_constraint not in {0, 1, 2}
        ):
            raise FileGDBError(
                "filegdb_materialized_geometry_dimension_invalid",
                "GeoPackage geometry column has an invalid dimension constraint",
                details={
                    "axis": axis,
                    "constraint": raw_constraint,
                },
            )
        observed = [
            bool(row.get(key))
            for row in dimension_rows
            if isinstance(row, Mapping)
        ]
        if len(observed) != len(dimension_rows):
            raise FileGDBError(
                "filegdb_materialized_geometry_dimension_invalid",
                "Validated WKB has an invalid dimension observation",
                details={"axis": axis},
            )
        violates_prohibited = raw_constraint == 0 and any(observed)
        violates_mandatory = raw_constraint == 1 and (
            not observed or not all(observed)
        )
        if violates_prohibited or violates_mandatory:
            raise FileGDBError(
                "filegdb_materialized_geometry_dimension_mismatch",
                "GeoPackage column and WKB coordinate dimensions differ",
                details={
                    "axis": axis,
                    "constraint": raw_constraint,
                    "observed": observed,
                },
            )


def _authority_from_source_geometry(
    geometry_field: Mapping[str, Any],
) -> tuple[str, str] | None:
    coordinate_system = geometry_field.get("coordinateSystem")
    if not isinstance(coordinate_system, Mapping):
        return None
    projjson = coordinate_system.get("projjson")
    if not isinstance(projjson, Mapping):
        return None
    identifier = projjson.get("id")
    if not isinstance(identifier, Mapping):
        return None
    authority = _text(identifier.get("authority"))
    code = _text(identifier.get("code"))
    if authority and code:
        return authority.upper(), code
    return None


def _read_geopackage_page(
    path: Path,
    *,
    source_layer: FileGDBLayerInspection,
    include_geometry: bool,
) -> tuple[list[ExtractedFeature], dict[str, Any]]:
    uri = f"file:{path.as_posix()}?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as error:
        raise FileGDBError(
            "filegdb_materialized_page_invalid",
            "Could not open GDAL's materialized GeoPackage page",
            details={"error": str(error)},
        ) from error
    connection.row_factory = sqlite3.Row
    try:
        table_info = _sqlite_table_info(connection, PAGE_TABLE)
        if not table_info:
            raise FileGDBError(
                "filegdb_materialized_page_missing",
                "GDAL did not create the requested GeoPackage page layer",
            )
        names = {str(column["name"]).casefold(): column for column in table_info}
        fid_alias_column = names.get(SOURCE_FID_ALIAS.casefold())
        if fid_alias_column is None:
            raise FileGDBError(
                "filegdb_materialized_fid_missing",
                "GDAL page omitted the explicitly selected source FID",
            )
        primary_keys = sorted(
            (
                column
                for column in table_info
                if int(column["primary_key_order"]) > 0
            ),
            key=lambda column: int(column["primary_key_order"]),
        )
        if len(primary_keys) != 1:
            raise FileGDBError(
                "filegdb_materialized_schema_invalid",
                "GeoPackage page does not have one occurrence-order key",
                details={"primary_keys": primary_keys},
            )
        output_fid = str(primary_keys[0]["name"])

        geometry_rows = connection.execute(
            """
            SELECT column_name, geometry_type_name, srs_id, z, m
            FROM gpkg_geometry_columns
            WHERE table_name = ?
            """,
            (PAGE_TABLE,),
        ).fetchall()
        if len(geometry_rows) > 1:
            raise FileGDBError(
                "filegdb_materialized_schema_invalid",
                "GeoPackage page has multiple geometry columns",
            )
        geometry_column: str | None = None
        geometry_metadata: dict[str, Any] | None = None
        materialized_srs: dict[str, Any] | None = None
        if geometry_rows:
            geometry_column = str(geometry_rows[0]["column_name"])
            geometry_metadata = {
                "column_name": geometry_column,
                "geometry_type_name": geometry_rows[0]["geometry_type_name"],
                "srs_id": geometry_rows[0]["srs_id"],
                "z": geometry_rows[0]["z"],
                "m": geometry_rows[0]["m"],
            }
            srs_row = connection.execute(
                """
                SELECT srs_name, srs_id, organization,
                       organization_coordsys_id, definition, description
                FROM gpkg_spatial_ref_sys
                WHERE srs_id = ?
                """,
                (geometry_rows[0]["srs_id"],),
            ).fetchone()
            if srs_row is None:
                raise FileGDBError(
                    "filegdb_materialized_crs_missing",
                    "GeoPackage page geometry references an absent CRS row",
                )
            materialized_srs = dict(srs_row)
        if bool(source_layer.geometry_fields) != bool(geometry_rows):
            raise FileGDBError(
                "filegdb_materialized_geometry_schema_changed",
                "Source and materialized layers disagree about geometry presence",
                details={
                    "source_geometry_fields": [
                        field.get("name")
                        for field in source_layer.geometry_fields
                    ],
                    "materialized_geometry_column": geometry_column,
                },
            )
        if source_layer.geometry_fields and geometry_metadata is not None:
            source_type = _base_geometry_type(
                str(source_layer.geometry_fields[0]["type"])
            )
            output_type = _base_geometry_type(
                str(geometry_metadata["geometry_type_name"])
            )
            if output_type not in SUPPORTED_GEOMETRY_TYPES:
                raise FileGDBError(
                    "filegdb_materialized_geometry_family_unsupported",
                    "Materialized GeoPackage geometry family is unsupported",
                    details={
                        "source_geometry_type": source_type,
                        "materialized_geometry_type": output_type,
                        "supported_geometry_families": sorted(
                            SUPPORTED_GEOMETRY_TYPES
                        ),
                    },
                )
            if source_type != "GEOMETRY" and source_type != output_type:
                raise FileGDBError(
                    "filegdb_materialized_geometry_type_changed",
                    "Source and materialized geometry families differ",
                    details={
                        "source_geometry_type": source_type,
                        "materialized_geometry_type": output_type,
                    },
                )
            authority = _authority_from_source_geometry(
                source_layer.geometry_fields[0]
            )
            if authority and materialized_srs is not None:
                observed = (
                    _text(materialized_srs.get("organization")),
                    _text(
                        materialized_srs.get(
                            "organization_coordsys_id"
                        )
                    ),
                )
                if (
                    observed[0]
                    and observed[1]
                    and (observed[0].upper(), observed[1]) != authority
                ):
                    raise FileGDBError(
                        "filegdb_materialized_crs_changed",
                        "Source and materialized CRS authorities differ",
                        details={
                            "source_authority": list(authority),
                            "materialized_authority": list(observed),
                        },
                    )

        source_fid_name = (
            source_layer.fid_column_name.casefold()
            if source_layer.fid_column_name
            else None
        )
        expected_attribute_names = {
            str(field["name"]).casefold(): str(field["name"])
            for field in source_layer.fields
            if str(field["name"]).casefold() != source_fid_name
        }
        excluded_columns = {
            output_fid.casefold(),
            SOURCE_FID_ALIAS.casefold(),
        }
        if geometry_column is not None:
            excluded_columns.add(geometry_column.casefold())
        if source_fid_name is not None:
            excluded_columns.add(source_fid_name)
        observed_attribute_names = {
            str(column["name"]).casefold(): str(column["name"])
            for column in table_info
            if str(column["name"]).casefold() not in excluded_columns
        }
        if set(expected_attribute_names) != set(observed_attribute_names):
            raise FileGDBError(
                "filegdb_materialized_attribute_schema_changed",
                "Source and materialized attribute field names differ",
                details={
                    "source_fields": sorted(expected_attribute_names.values()),
                    "materialized_fields": sorted(
                        observed_attribute_names.values()
                    ),
                    "source_fid_column": source_layer.fid_column_name,
                },
            )
        attribute_columns = {
            observed_name: expected_attribute_names[folded]
            for folded, observed_name in observed_attribute_names.items()
        }

        query = (
            f"SELECT * FROM {_quote_sqlite_identifier(PAGE_TABLE)} "
            f"ORDER BY {_quote_sqlite_identifier(output_fid)}"
        )
        rows = connection.execute(query).fetchall()
        features: list[ExtractedFeature] = []
        seen_fids: set[int] = set()
        previous_native_fid: int | None = None
        for ordinal, row in enumerate(rows):
            native_fid = row[SOURCE_FID_ALIAS]
            if (
                isinstance(native_fid, bool)
                or not isinstance(native_fid, int)
                or native_fid < 0
            ):
                raise FileGDBError(
                    "filegdb_native_fid_invalid",
                    "Source feature has no usable non-negative integer FID",
                    details={"native_fid": native_fid},
                )
            if native_fid in seen_fids:
                raise FileGDBError(
                    "filegdb_native_fid_duplicated",
                    "Source FID repeats within one materialized page",
                    details={"native_fid": native_fid},
                )
            if (
                previous_native_fid is not None
                and native_fid <= previous_native_fid
            ):
                raise FileGDBError(
                    "filegdb_native_fid_order_invalid",
                    "Materialized source FIDs are not strictly increasing",
                    details={
                        "previous_native_fid": previous_native_fid,
                        "native_fid": native_fid,
                    },
                )
            seen_fids.add(native_fid)
            previous_native_fid = native_fid
            attributes = {
                source_name: _json_attribute(row[observed_name])
                for observed_name, source_name in attribute_columns.items()
            }
            geometry: dict[str, Any] | None = None
            if geometry_column is not None and row[geometry_column] is not None:
                raw_geometry = row[geometry_column]
                if not isinstance(raw_geometry, bytes):
                    raise FileGDBError(
                        "filegdb_materialized_geometry_invalid",
                        "GeoPackage geometry column is not binary",
                    )
                parsed = _parse_geopackage_geometry(raw_geometry)
                _validate_geopackage_dimensions(
                    geometry_metadata,
                    parsed["wkb_validation"],
                )
                materialized_family = _base_geometry_type(
                    str(geometry_metadata["geometry_type_name"])
                )
                wkb_family = _base_geometry_type(
                    str(
                        parsed["wkb_validation"][
                            "top_level_family"
                        ]
                    )
                )
                if (
                    materialized_family != "GEOMETRY"
                    and materialized_family != wkb_family
                ):
                    raise FileGDBError(
                        "filegdb_materialized_geometry_type_changed",
                        "GeoPackage layer and WKB geometry families differ",
                        details={
                            "materialized_geometry_type": (
                                materialized_family
                            ),
                            "wkb_geometry_type": wkb_family,
                        },
                    )
                expected_srs = int(geometry_metadata["srs_id"])
                observed_srs = int(parsed["gpkg_header"]["srs_id"])
                if expected_srs != observed_srs:
                    raise FileGDBError(
                        "filegdb_materialized_crs_changed",
                        "Geometry header and layer CRS identifiers differ",
                        details={
                            "geometry_srs_id": observed_srs,
                            "layer_srs_id": expected_srs,
                        },
                    )
                if include_geometry:
                    parsed["source_geometry_field"] = _json_value(
                        source_layer.geometry_fields[0]
                    )
                    parsed["materialized_geometry_field"] = geometry_metadata
                    parsed["materialized_srs"] = materialized_srs
                    geometry = parsed
            features.append(
                ExtractedFeature(
                    native_fid=native_fid,
                    attributes=attributes,
                    geometry=geometry,
                    materialized_ordinal=ordinal,
                )
            )
        schema = {
            "page_table": PAGE_TABLE,
            "columns": table_info,
            "source_fid_alias": SOURCE_FID_ALIAS,
            "source_fid_column": source_layer.fid_column_name,
            "output_fid_column": output_fid,
            "geometry_field": geometry_metadata,
            "materialized_srs": materialized_srs,
            "geometry_included": include_geometry,
        }
        schema["schema_fingerprint"] = sha256_fingerprint(schema)
        return features, schema
    except sqlite3.Error as error:
        raise FileGDBError(
            "filegdb_materialized_page_invalid",
            "Could not read GDAL's materialized GeoPackage page",
            details={"error": str(error)},
        ) from error
    finally:
        connection.close()


def _parcel_join(
    attributes: Mapping[str, Any],
    fields: Sequence[str],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    values: list[str] = []
    for field_name in fields:
        raw_value = attributes.get(field_name)
        scalar = not isinstance(raw_value, (Mapping, list, tuple))
        normalized = _text(raw_value) if scalar else None
        if not scalar:
            state = "non_scalar_in_source"
        elif raw_value is None:
            state = "null_in_source"
        elif normalized is None:
            state = "blank_in_source"
        else:
            state = "published_value"
            if normalized not in values:
                values.append(normalized)
        candidates.append(
            {
                "field": field_name,
                "raw_value": raw_value,
                "value": normalized,
                "state": state,
            }
        )
    selected: dict[str, Any] | None = None
    if not fields:
        state = "no_conservative_join_field"
    elif not values:
        state = "source_join_key_blank_or_null"
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
        "normalization": "outer_whitespace_trim_only",
        "feature_identity_uses_join_value": False,
    }


def _feature_occurrence(
    feature: ExtractedFeature,
    *,
    inspection: FileGDBDatasetInspection,
    layer: FileGDBLayerInspection,
    source_ordinal: int,
    geometry_requested: bool,
) -> dict[str, Any]:
    occurrence_payload = {
        "source_id": inspection.source_id,
        "release_id": inspection.release_id,
        "artifact_sha256": inspection.container.artifact_sha256,
        "gdb_member_identity_sha256": (
            inspection.container.gdb_member_identity_sha256
        ),
        "gdb_member": inspection.container.gdb_member,
        "layer": layer.name,
        "layer_schema_fingerprint": layer.schema_fingerprint,
        "native_fid": feature.native_fid,
    }
    occurrence_id = sha256_fingerprint(occurrence_payload)
    if not layer.geometry_fields:
        geometry_state = "nonspatial_table"
    elif not geometry_requested:
        geometry_state = "omitted_by_query"
    elif feature.geometry is None:
        geometry_state = "null_geometry"
    else:
        geometry_state = "extracted_native_crs_wkb"
    return {
        "canonical_ref": f"FILEGDB-FEATURE:{occurrence_id}",
        "evidence_ref": (
            f"FILEGDB:{inspection.container.artifact_sha256}:"
            f"{inspection.container.gdb_member_identity_sha256}:"
            f"{layer.schema_fingerprint}:{feature.native_fid}"
        ),
        "source_id": inspection.source_id,
        "release_id": inspection.release_id,
        "record_kind": "filegdb_feature_occurrence",
        "feature_occurrence": {
            "occurrence_id": occurrence_id,
            "native_fid": feature.native_fid,
            "source_ordinal": source_ordinal,
            "native_fid_column": layer.fid_column_name,
            "identity_fields": [
                "source_id",
                "release_id",
                "artifact_sha256",
                "gdb_member_identity_sha256",
                "gdb_member",
                "layer",
                "layer_schema_fingerprint",
                "native_fid",
            ],
        },
        "parcel_join": _parcel_join(
            feature.attributes,
            layer.parcel_join_fields,
        ),
        "attributes": _json_value(feature.attributes),
        "geometry": (
            _json_value(feature.geometry)
            if feature.geometry is not None
            else None
        ),
        "geometry_state": geometry_state,
        "source_lineage": {
            "artifact_path": inspection.container.path,
            "container": inspection.container.container,
            "artifact_sha256": inspection.container.artifact_sha256,
            "artifact_identity_kind": (
                inspection.container.artifact_identity_kind
            ),
            "gdb_member": inspection.container.gdb_member,
            "gdb_member_identity_sha256": (
                inspection.container.gdb_member_identity_sha256
            ),
            "layer": layer.name,
            "layer_schema_fingerprint": layer.schema_fingerprint,
            "dataset_schema_fingerprint": (
                inspection.dataset_schema_fingerprint
            ),
            "backend": inspection.backend.to_dict(),
        },
    }


def _validate_backend_fid_sequence(
    features: Sequence[ExtractedFeature],
    *,
    previous_last_fid: int | None,
) -> None:
    preceding = previous_last_fid
    seen: set[int] = set()
    for page_index, feature in enumerate(features):
        native_fid = feature.native_fid
        if (
            isinstance(native_fid, bool)
            or not isinstance(native_fid, int)
            or native_fid < 0
        ):
            raise FileGDBError(
                "filegdb_native_fid_invalid",
                "Backend feature has no usable non-negative integer FID",
                details={
                    "page_index": page_index,
                    "native_fid": native_fid,
                },
            )
        if native_fid in seen:
            raise FileGDBError(
                "filegdb_native_fid_duplicated",
                "Backend source FID repeats within one page",
                details={
                    "page_index": page_index,
                    "native_fid": native_fid,
                },
            )
        if preceding is not None and native_fid <= preceding:
            raise FileGDBError(
                "filegdb_native_fid_order_invalid",
                "Backend source FIDs are not strictly increasing",
                details={
                    "page_index": page_index,
                    "previous_native_fid": preceding,
                    "native_fid": native_fid,
                    "cross_page_boundary": page_index == 0
                    and previous_last_fid is not None,
                },
            )
        seen.add(native_fid)
        preceding = native_fid


def _cursor_encode(
    *,
    inspection: FileGDBDatasetInspection,
    layer: FileGDBLayerInspection,
    query_fingerprint: str,
    next_offset: int,
    last_native_fid: int,
) -> str:
    payload = canonical_json(
        {
            "version": 1,
            "source_id": inspection.source_id,
            "release_id": inspection.release_id,
            "artifact_sha256": inspection.container.artifact_sha256,
            "gdb_member": inspection.container.gdb_member,
            "gdb_member_identity_sha256": (
                inspection.container.gdb_member_identity_sha256
            ),
            "layer": layer.name,
            "layer_schema_fingerprint": layer.schema_fingerprint,
            "dataset_schema_fingerprint": (
                inspection.dataset_schema_fingerprint
            ),
            "query_fingerprint": query_fingerprint,
            "next_offset": next_offset,
            "last_native_fid": last_native_fid,
        }
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _cursor_decode(
    cursor: str | None,
    *,
    inspection: FileGDBDatasetInspection,
    layer: FileGDBLayerInspection,
    query_fingerprint: str,
) -> tuple[int, int | None]:
    if cursor is None:
        return 0, None
    if not cursor.startswith(CURSOR_PREFIX):
        raise FileGDBError(
            "filegdb_cursor_invalid",
            "FileGDB cursor has an invalid prefix",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(
                token + "=" * (-len(token) % 4)
            )
        )
    except (
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as error:
        raise FileGDBError(
            "filegdb_cursor_invalid",
            "FileGDB cursor is malformed",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("version") != 1:
        raise FileGDBError(
            "filegdb_cursor_invalid",
            "FileGDB cursor payload or version is invalid",
        )
    expected = {
        "source_id": inspection.source_id,
        "release_id": inspection.release_id,
        "artifact_sha256": inspection.container.artifact_sha256,
        "gdb_member": inspection.container.gdb_member,
        "gdb_member_identity_sha256": (
            inspection.container.gdb_member_identity_sha256
        ),
        "layer": layer.name,
        "layer_schema_fingerprint": layer.schema_fingerprint,
        "dataset_schema_fingerprint": (
            inspection.dataset_schema_fingerprint
        ),
        "query_fingerprint": query_fingerprint,
    }
    mismatches = {
        key: {"cursor": payload.get(key), "current": value}
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if mismatches:
        raise FileGDBError(
            "filegdb_cursor_context_changed",
            (
                "FileGDB cursor does not match the source, release, artifact, "
                "layer, schema, or query"
            ),
            details={"mismatches": mismatches},
        )
    offset = payload.get("next_offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise FileGDBError(
            "filegdb_cursor_offset_invalid",
            "FileGDB cursor offset is invalid",
            details={"next_offset": offset},
        )
    if layer.feature_count is not None and offset > layer.feature_count:
        raise FileGDBError(
            "filegdb_cursor_offset_invalid",
            "FileGDB cursor offset exceeds the inspected feature count",
            details={
                "next_offset": offset,
                "feature_count": layer.feature_count,
            },
        )
    last_native_fid = payload.get("last_native_fid")
    if (
        isinstance(last_native_fid, bool)
        or not isinstance(last_native_fid, int)
        or last_native_fid < 0
    ):
        raise FileGDBError(
            "filegdb_cursor_fid_boundary_invalid",
            "FileGDB cursor has an invalid native-FID boundary",
            details={"last_native_fid": last_native_fid},
        )
    if offset == 0:
        raise FileGDBError(
            "filegdb_cursor_fid_boundary_invalid",
            "A continued FileGDB cursor cannot have a zero offset",
            details={
                "next_offset": offset,
                "last_native_fid": last_native_fid,
            },
        )
    return offset, last_native_fid


@dataclass(frozen=True)
class FileGDBFeaturePage:
    inspection: FileGDBDatasetInspection
    layer: FileGDBLayerInspection
    records: tuple[Mapping[str, Any], ...]
    start_offset: int
    result_limit: int
    next_cursor: str | None
    exhausted: bool
    query_fingerprint: str
    materialized_schema: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_id": self.inspection.source_id,
            "release_id": self.inspection.release_id,
            "operation": "features",
            "layer": self.layer.to_dict(),
            "records": [_json_value(record) for record in self.records],
            "pagination": {
                "start_offset": self.start_offset,
                "result_limit": self.result_limit,
                "returned_count": len(self.records),
                "next_cursor": self.next_cursor,
                "exhausted": self.exhausted,
                "query_fingerprint": self.query_fingerprint,
            },
            "materialized_schema": _json_value(self.materialized_schema),
            "container": self.inspection.container.to_dict(),
            "backend": self.inspection.backend.to_dict(),
        }


def read_filegdb_features(
    path: Path | str,
    *,
    layer: str,
    gdb_member: str | None = None,
    source_id: str = DEFAULT_SOURCE_ID,
    release_id: str | None = None,
    parcel_fields: Sequence[str] | None = None,
    limit: int = DEFAULT_RESULT_LIMIT,
    cursor: str | None = None,
    include_geometry: bool = True,
    policy: ArchiveSafetyPolicy | None = None,
    backend: FileGDBBackend | None = None,
) -> FileGDBFeaturePage:
    """Read one cursor-bound page without conflating parcel and feature IDs."""

    _positive(limit, "limit")
    active_backend = backend or GDALCLIBackend()
    inspection = inspect_filegdb_dataset(
        path,
        gdb_member=gdb_member,
        source_id=source_id,
        release_id=release_id,
        parcel_fields=parcel_fields,
        policy=policy,
        backend=active_backend,
    )
    selected = inspection.layer(layer)
    _require_supported_geometry(selected)
    if parcel_fields is not None:
        selected_joins = _resolve_parcel_fields(
            selected.fields,
            parcel_fields,
        )
        if selected_joins != selected.parcel_join_fields:
            raise FileGDBError(
                "filegdb_parcel_field_contract_changed",
                "Selected layer parcel join fields changed after inspection",
                details={
                    "inspected_fields": list(selected.parcel_join_fields),
                    "selected_fields": list(selected_joins),
                },
            )
    query_payload = {
        "operation": "features",
        "source_id": inspection.source_id,
        "release_id": inspection.release_id,
        "layer": selected.name,
        "parcel_join_fields": list(selected.parcel_join_fields),
        "include_geometry": bool(include_geometry),
    }
    query_fingerprint = sha256_fingerprint(query_payload)
    offset, previous_last_fid = _cursor_decode(
        cursor,
        inspection=inspection,
        layer=selected,
        query_fingerprint=query_fingerprint,
    )
    try:
        backend_page = active_backend.extract_page(
            inspection.container,
            selected,
            offset=offset,
            limit=limit + 1,
            include_geometry=include_geometry,
        )
    except Exception:
        _assert_container_unchanged(
            inspection.container,
            policy=policy,
            operation="feature page extraction",
        )
        raise
    _assert_container_unchanged(
        inspection.container,
        policy=policy,
        operation="feature page extraction",
    )
    if (
        backend_page.requested_offset != offset
        or backend_page.requested_limit != limit + 1
    ):
        raise FileGDBError(
            "filegdb_backend_page_contract_invalid",
            "FileGDB backend returned a page for a different request",
        )
    raw_features = list(backend_page.features)
    if len(raw_features) > limit + 1:
        raise FileGDBError(
            "filegdb_backend_page_contract_invalid",
            "FileGDB backend returned more features than requested",
            details={
                "requested_limit": limit + 1,
                "returned_count": len(raw_features),
            },
        )
    _validate_backend_fid_sequence(
        raw_features,
        previous_last_fid=previous_last_fid,
    )
    misaligned = [
        {
            "page_index": index,
            "materialized_ordinal": feature.materialized_ordinal,
        }
        for index, feature in enumerate(raw_features)
        if feature.materialized_ordinal != index
    ]
    if misaligned:
        raise FileGDBError(
            "filegdb_backend_page_contract_invalid",
            "FileGDB backend feature order is not aligned to its page",
            details={"misaligned_features": misaligned},
        )
    has_more = len(raw_features) > limit
    selected_features = raw_features[:limit]
    records = tuple(
        _feature_occurrence(
            feature,
            inspection=inspection,
            layer=selected,
            source_ordinal=offset + index,
            geometry_requested=include_geometry,
        )
        for index, feature in enumerate(selected_features)
    )
    next_offset = offset + len(selected_features)
    next_cursor = (
        _cursor_encode(
            inspection=inspection,
            layer=selected,
            query_fingerprint=query_fingerprint,
            next_offset=next_offset,
            last_native_fid=selected_features[-1].native_fid,
        )
        if has_more
        else None
    )
    return FileGDBFeaturePage(
        inspection=inspection,
        layer=selected,
        records=records,
        start_offset=offset,
        result_limit=limit,
        next_cursor=next_cursor,
        exhausted=not has_more,
        query_fingerprint=query_fingerprint,
        materialized_schema=backend_page.materialized_schema,
    )


def _archive_policy(args: argparse.Namespace) -> ArchiveSafetyPolicy:
    return ArchiveSafetyPolicy(
        max_members=args.max_archive_members,
        max_total_uncompressed_bytes=args.max_archive_uncompressed_bytes,
        max_member_uncompressed_bytes=args.max_member_uncompressed_bytes,
        max_compression_ratio=args.max_compression_ratio,
    )


def _add_archive_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--gdb-member")
    parser.add_argument("--max-archive-members", type=int)
    parser.add_argument("--max-archive-uncompressed-bytes", type=int)
    parser.add_argument("--max-member-uncompressed-bytes", type=int)
    parser.add_argument("--max-compression-ratio", type=float)


def _add_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    parser.add_argument("--release-id")
    parser.add_argument(
        "--parcel-field",
        action="append",
        dest="parcel_fields",
        help="Published parcel join candidate; repeat for multiple fields",
    )


def _backend_from_args(args: argparse.Namespace) -> GDALCLIBackend:
    return GDALCLIBackend(
        ogrinfo=getattr(args, "ogrinfo", None),
        ogr2ogr=getattr(args, "ogr2ogr", None),
        timeout=getattr(
            args,
            "backend_timeout",
            DEFAULT_BACKEND_TIMEOUT,
        ),
    )


def _add_backend_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ogrinfo")
    parser.add_argument("--ogr2ogr")
    parser.add_argument(
        "--backend-timeout",
        type=int,
        default=DEFAULT_BACKEND_TIMEOUT,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Source-neutral local FileGDB extraction interface"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backend_parser = subparsers.add_parser(
        "backend",
        help="Report GDAL/OpenFileGDB availability",
    )
    _add_backend_args(backend_parser)
    add_output_args(backend_parser)

    container_parser = subparsers.add_parser(
        "container",
        help="Inspect .gdb directory or ZIP lineage without decoding",
    )
    container_parser.add_argument("path")
    _add_archive_args(container_parser)
    add_output_args(container_parser)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect FileGDB layers and source schemas",
    )
    inspect_parser.add_argument("path")
    _add_archive_args(inspect_parser)
    _add_identity_args(inspect_parser)
    _add_backend_args(inspect_parser)
    add_output_args(inspect_parser)

    features_parser = subparsers.add_parser(
        "features",
        help="Extract one cursor-bound source feature page",
    )
    features_parser.add_argument("path")
    features_parser.add_argument("--layer", required=True)
    features_parser.add_argument("--limit", type=int, default=DEFAULT_RESULT_LIMIT)
    features_parser.add_argument("--cursor")
    features_parser.add_argument(
        "--no-geometry",
        action="store_true",
        help="Return attributes and occurrence identity without WKB payloads",
    )
    _add_archive_args(features_parser)
    _add_identity_args(features_parser)
    _add_backend_args(features_parser)
    add_output_args(features_parser)
    return parser


def _emit(data: Mapping[str, Any], args: argparse.Namespace, summary: str) -> None:
    if not write_output(data, args, summary=summary):
        print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "backend":
            data = _backend_from_args(args).status().to_dict()
            _emit(data, args, "FileGDB backend")
            return 0
        if args.command == "container":
            data = inspect_filegdb_container(
                args.path,
                gdb_member=args.gdb_member,
                policy=_archive_policy(args),
            ).to_dict()
            _emit(data, args, "FileGDB container")
            return 0
        backend = _backend_from_args(args)
        if args.command == "inspect":
            data = inspect_filegdb_dataset(
                args.path,
                gdb_member=args.gdb_member,
                source_id=args.source_id,
                release_id=args.release_id,
                parcel_fields=args.parcel_fields,
                policy=_archive_policy(args),
                backend=backend,
            ).to_dict()
            _emit(data, args, "FileGDB dataset")
            return 0
        if args.command == "features":
            page = read_filegdb_features(
                args.path,
                layer=args.layer,
                gdb_member=args.gdb_member,
                source_id=args.source_id,
                release_id=args.release_id,
                parcel_fields=args.parcel_fields,
                limit=args.limit,
                cursor=args.cursor,
                include_geometry=not args.no_geometry,
                policy=_archive_policy(args),
                backend=backend,
            )
            _emit(page.to_dict(), args, "FileGDB feature page")
            return 0
    except FileGDBError as error:
        failure = {
            "status": "unavailable",
            "error": error.to_dict(),
        }
        _emit(failure, args, "FileGDB operation unavailable")
        return 2
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
