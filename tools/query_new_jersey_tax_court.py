#!/usr/bin/env python3
"""Search New Jersey Tax Court local-property docket snapshots.

The New Jersey Judiciary publishes current local-property cases docketed and
currently open as XLSX/PDF pairs.  The human landing page is protected by an
edge challenge, but the Judiciary's public S3 bucket exposes an anonymous
ListObjectsV2 manifest and the report artifacts themselves.

The XLSX reports contain one row per docket/property occurrence.  A docket can
therefore appear on multiple rows, and exact duplicate source rows occur in the
live workbooks.  This adapter preserves every occurrence with workbook row and
artifact provenance while giving all occurrences of the same docket a stable
case reference.

Examples:
    uv run python tools/query_new_jersey_tax_court.py manifest --json
    uv run python tools/query_new_jersey_tax_court.py search "ACME LLC"
    uv run python tools/query_new_jersey_tax_court.py search \
        --dataset open --county Bergen --block 100 --lot 2
    uv run python tools/query_new_jersey_tax_court.py search \
        --docket 003855-2026 --include-raw-row
    uv run python tools/query_new_jersey_tax_court.py validate --dataset both
    uv run python tools/query_new_jersey_tax_court.py alternatives --json
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import posixpath
import re
import sys
import tempfile
import time
import zipfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        ArtifactProbe,
        BulkArtifact,
        BulkSourceError,
        BulkTransferClient,
        DownloadResult,
        file_sha256,
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
    from tools.public_records_store import canonical_court_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        ArtifactProbe,
        BulkArtifact,
        BulkSourceError,
        BulkTransferClient,
        DownloadResult,
        file_sha256,
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
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-nj-tax-court-property-cases"
COURT_ID = "nj-tax-court"
LANDING_URL = "https://www.njcourts.gov/courts/tax/docketed-cases"
S3_BASE_URL = "https://njj-aocmedia-prod-general-purpose.s3.amazonaws.com"
S3_PREFIX = "tax-reports/"
S3_LIST_URL = f"{S3_BASE_URL}/?list-type=2&prefix={S3_PREFIX}"
DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_CACHE_DIR = (
    Path(tempfile.gettempdir()) / "ithildin-new-jersey-tax-court"
)
CURSOR_PREFIX = "nj-tax-court:v1:"
CURSOR_VERSION = 1

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOCUMENT_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

SEMANTIC_HEADERS = (
    "docket_number",
    "case_title",
    "entered_date",
    "block",
    "lot",
    "unit",
    "assessment_year",
    "county",
)
DOCKETED_HEADERS = (
    "Docket Number",
    "Case Title",
    "Entered Date",
    "Block Number",
    "Lot Number",
    "Unit Number",
    "Assessment Year",
    "County",
)
OPEN_HEADERS_WITH_ANOMALY = (*DOCKETED_HEADERS[:-1], "Year")

COUNTIES = {
    "Atlantic": "34001",
    "Bergen": "34003",
    "Burlington": "34005",
    "Camden": "34007",
    "Cape May": "34009",
    "Cumberland": "34011",
    "Essex": "34013",
    "Gloucester": "34015",
    "Hudson": "34017",
    "Hunterdon": "34019",
    "Mercer": "34021",
    "Middlesex": "34023",
    "Monmouth": "34025",
    "Morris": "34027",
    "Ocean": "34029",
    "Passaic": "34031",
    "Salem": "34033",
    "Somerset": "34035",
    "Sussex": "34037",
    "Union": "34039",
    "Warren": "34041",
}
COUNTY_ALIASES = {
    re.sub(r"[^a-z0-9]", "", name.casefold()): name
    for name in COUNTIES
}

SOURCE_WARNINGS = (
    (
        "The docketed and open files are replaceable Judiciary snapshots. "
        "A row appearing in both files is the same source lineage, not "
        "independent corroboration."
    ),
    (
        "Each source row describes a docket/property occurrence. Multiple "
        "rows, including exact duplicate rows, are preserved because one "
        "docket can cover multiple properties."
    ),
    (
        "The open-cases workbook has been observed with a final header named "
        "'Year' whose values are county names. The adapter records that raw "
        "header and normalizes the column as county."
    ),
)

ACCESS_STATE = {
    "current_reports": {
        "machine_enumerable": True,
        "manifest": "S3 ListObjectsV2",
        "artifacts": [
            "docketed XLSX",
            "docketed PDF",
            "open XLSX",
            "open PDF",
        ],
    },
    "current_key_versions": {
        "machine_enumerable": True,
        "manifest": "S3 ListObjectVersions",
        "scope": (
            "prior versions of the replaceable current-report keys; these "
            "are not the named monthly judgment archive"
        ),
    },
    "historical_judgment_files": {
        "machine_enumerable": False,
        "discovery": "Judiciary browser archive and public search index",
        "direct_non_browser_http": "edge_challenge",
    },
}
JOIN_GUIDANCE = {
    "stable_case_key": "docket number",
    "available_candidate_parcel_fields": [
        "county",
        "block",
        "lot",
        "unit",
        "assessment year",
    ],
    "missing_for_deterministic_njgin_sr1a_parcel_join": [
        "municipality",
    ],
    "caption_semantics": (
        "Case title is preserved as a raw caption. Party names can seed "
        "candidate pivots but do not establish property ownership."
    ),
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="New Jersey Tax Court local-property case reports",
    source_role="official court bulk docket reports",
    base_url=LANDING_URL,
    dataset_id="local-property-tax-cases",
    metadata={
        "machine_manifest_url": S3_LIST_URL,
        "publisher": "New Jersey Judiciary",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-nj",
    name="New Jersey",
    state_code="NJ",
)


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    label: str
    xlsx_key: str
    pdf_key: str
    sheet_name: str
    scope: str

    @property
    def accepted_headers(self) -> tuple[tuple[str, ...], ...]:
        if self.dataset_id == "open":
            return (OPEN_HEADERS_WITH_ANOMALY, DOCKETED_HEADERS)
        return (DOCKETED_HEADERS,)


DATASET_SPECS = {
    "docketed": DatasetSpec(
        dataset_id="docketed",
        label="Local Property Tax Cases Docketed",
        xlsx_key="tax-reports/localtaxcases.xlsx",
        pdf_key="tax-reports/localtaxcases.pdf",
        sheet_name="Local Property Docketed",
        scope="cases docketed in the current reporting year",
    ),
    "open": DatasetSpec(
        dataset_id="open",
        label="Open Local Property Tax Cases",
        xlsx_key="tax-reports/localtaxcasesall.xlsx",
        pdf_key="tax-reports/localtaxcasesall.pdf",
        sheet_name="Local Property Open",
        scope="cases currently reported open across filing years",
    ),
}
KEY_INDEX = {
    key: (spec, file_format)
    for spec in DATASET_SPECS.values()
    for key, file_format in (
        (spec.xlsx_key, "xlsx"),
        (spec.pdf_key, "pdf"),
    )
}


class NewJerseyTaxCourtError(Exception):
    """Structured source-specific failure."""

    code = "nj_tax_court_error"
    status = ResultStatus.SOURCE_CHANGED
    category = "source"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class ManifestTransportError(NewJerseyTaxCourtError):
    code = "nj_tax_court_manifest_unavailable"
    status = ResultStatus.UNAVAILABLE
    category = "transport"
    retryable = True


class ManifestContractError(NewJerseyTaxCourtError):
    code = "nj_tax_court_manifest_changed"


class WorkbookContractError(NewJerseyTaxCourtError):
    code = "nj_tax_court_workbook_changed"


class CursorError(NewJerseyTaxCourtError):
    code = "nj_tax_court_cursor_invalid"


@dataclass(frozen=True)
class S3Object:
    key: str
    last_modified: str
    etag: str
    size: int
    storage_class: str | None = None

    @property
    def url(self) -> str:
        return f"{S3_BASE_URL}/{quote(self.key, safe='/')}"

    @property
    def dataset(self) -> DatasetSpec:
        return KEY_INDEX[self.key][0]

    @property
    def file_format(self) -> str:
        return KEY_INDEX[self.key][1]

    def artifact(self) -> BulkArtifact:
        media_type = {
            "xlsx": (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            "pdf": "application/pdf",
        }[self.file_format]
        return BulkArtifact(
            artifact_id=f"{self.dataset.dataset_id}-{self.file_format}",
            url=self.url,
            filename=Path(self.key).name,
            media_type=media_type,
            archive_format="zip" if self.file_format == "xlsx" else None,
            expected_size=self.size,
            etag=self.etag,
            last_modified=self.last_modified,
            metadata={
                "dataset": self.dataset.dataset_id,
                "s3_key": self.key,
                "source_manifest": S3_LIST_URL,
            },
        )

    def to_record(self, manifest_fingerprint: str) -> dict[str, Any]:
        return {
            "record_type": "artifact_manifest",
            "artifact_id": f"{self.dataset.dataset_id}-{self.file_format}",
            "dataset": {
                "id": self.dataset.dataset_id,
                "label": self.dataset.label,
                "scope": self.dataset.scope,
            },
            "format": self.file_format,
            "key": self.key,
            "url": self.url,
            "size": self.size,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "storage_class": self.storage_class,
            "manifest_url": S3_LIST_URL,
            "manifest_fingerprint": manifest_fingerprint,
            "access_state": ACCESS_STATE,
            "join_guidance": JOIN_GUIDANCE,
        }


@dataclass(frozen=True)
class ManifestSnapshot:
    objects: tuple[S3Object, ...]

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            [
                {
                    "key": item.key,
                    "last_modified": item.last_modified,
                    "etag": item.etag,
                    "size": item.size,
                }
                for item in self.objects
            ]
        )

    def object_for(self, dataset_id: str, file_format: str) -> S3Object:
        for item in self.objects:
            if (
                item.dataset.dataset_id == dataset_id
                and item.file_format == file_format
            ):
                return item
        raise ManifestContractError(
            "Official manifest omitted a selected Tax Court artifact",
            details={"dataset": dataset_id, "format": file_format},
        )


def parse_manifest_xml(data: bytes | str) -> ManifestSnapshot:
    """Parse and validate the official S3 ListObjectsV2 response."""
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise ManifestContractError(
            f"Official object manifest is not valid XML: {error}"
        ) from error
    namespace = root.tag.partition("}")[0].removeprefix("{")
    prefix = f"{{{namespace}}}" if namespace else ""
    truncated = root.findtext(f"{prefix}IsTruncated", default="false")
    if truncated.strip().casefold() == "true":
        raise ManifestContractError(
            "Official object manifest was unexpectedly paginated",
            details={"url": S3_LIST_URL},
        )
    objects: list[S3Object] = []
    for content in root.findall(f"{prefix}Contents"):
        key = content.findtext(f"{prefix}Key", default="").strip()
        if key not in KEY_INDEX:
            continue
        modified = content.findtext(
            f"{prefix}LastModified",
            default="",
        ).strip()
        etag = content.findtext(f"{prefix}ETag", default="").strip().strip('"')
        size_text = content.findtext(f"{prefix}Size", default="").strip()
        storage_class = content.findtext(f"{prefix}StorageClass")
        try:
            size = int(size_text)
        except ValueError as error:
            raise ManifestContractError(
                "Official object manifest contains an invalid artifact size",
                details={"key": key, "size": size_text},
            ) from error
        if not modified or not etag or size <= 0:
            raise ManifestContractError(
                "Official object manifest contains incomplete artifact metadata",
                details={
                    "key": key,
                    "last_modified": modified,
                    "etag": etag,
                    "size": size,
                },
            )
        objects.append(
            S3Object(
                key=key,
                last_modified=modified,
                etag=etag,
                size=size,
                storage_class=(
                    storage_class.strip()
                    if storage_class and storage_class.strip()
                    else None
                ),
            )
        )
    missing = sorted(set(KEY_INDEX) - {item.key for item in objects})
    if missing:
        raise ManifestContractError(
            "Official object manifest omitted expected Tax Court reports",
            details={"missing_keys": missing},
        )
    return ManifestSnapshot(
        objects=tuple(
            sorted(
                objects,
                key=lambda item: (
                    item.dataset.dataset_id,
                    item.file_format,
                ),
            )
        )
    )


def _response_status(response: Any) -> int:
    return int(getattr(response, "status", getattr(response, "status_code", 200)))


def fetch_manifest(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    opener: Callable[..., Any] = urlopen,
) -> ManifestSnapshot:
    """Fetch the public, anonymous official object manifest."""
    request = Request(
        S3_LIST_URL,
        headers={
            "User-Agent": "Ithildin-Public-Records/1.0",
            "Accept": "application/xml,text/xml",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, retry_attempts + 1):
        try:
            with opener(request, timeout=timeout) as response:
                status = _response_status(response)
                if status < 200 or status >= 300:
                    raise ManifestTransportError(
                        f"Official object manifest returned HTTP {status}",
                        details={"url": S3_LIST_URL, "http_status": status},
                    )
                return parse_manifest_xml(response.read())
        except HTTPError as error:
            last_error = error
            retryable = error.code in {429, 500, 502, 503, 504}
            if not retryable or attempt >= retry_attempts:
                raise ManifestTransportError(
                    f"Official object manifest returned HTTP {error.code}",
                    details={
                        "url": S3_LIST_URL,
                        "http_status": error.code,
                    },
                ) from error
        except (URLError, TimeoutError, ConnectionError, OSError) as error:
            last_error = error
            if attempt >= retry_attempts:
                raise ManifestTransportError(
                    f"Could not fetch the official object manifest: {error}",
                    details={"url": S3_LIST_URL},
                ) from error
        if attempt < retry_attempts:
            time.sleep(min(0.25 * (2 ** (attempt - 1)), 2.0))
    assert last_error is not None
    raise ManifestTransportError(str(last_error))


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    if not cursor.startswith(CURSOR_PREFIX):
        raise CursorError(
            "Cursor does not belong to the New Jersey Tax Court source"
        )
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CursorError("Cursor payload is not valid") from error
    if (
        not isinstance(payload, dict)
        or payload.get("version") != CURSOR_VERSION
    ):
        raise CursorError("Cursor version is not supported")
    return payload


def _selected_dataset_ids(value: str) -> tuple[str, ...]:
    if value == "both":
        return ("docketed", "open")
    return (value,)


def _selected_manifest_objects(
    args: argparse.Namespace,
    snapshot: ManifestSnapshot,
) -> tuple[S3Object, ...]:
    dataset_value = getattr(args, "dataset", "both")
    format_value = getattr(args, "format", "all")
    datasets = set(_selected_dataset_ids(dataset_value))
    return tuple(
        item
        for item in snapshot.objects
        if item.dataset.dataset_id in datasets
        and (format_value == "all" or item.file_format == format_value)
    )


def paginate_manifest(
    snapshot: ManifestSnapshot,
    objects: Sequence[S3Object],
    *,
    limit: int | None,
    cursor: str | None,
) -> tuple[tuple[S3Object, ...], str | None]:
    selection = sha256_fingerprint([item.key for item in objects])
    offset = 0
    if cursor:
        payload = _decode_cursor(cursor)
        if payload.get("kind") != "manifest":
            raise CursorError("Cursor is not a manifest cursor")
        if payload.get("manifest_fingerprint") != snapshot.fingerprint:
            raise CursorError(
                "Tax Court artifact manifest changed after cursor issuance"
            )
        if payload.get("selection_fingerprint") != selection:
            raise CursorError(
                "Tax Court manifest cursor does not match the selectors"
            )
        offset = payload.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise CursorError("Manifest cursor offset is invalid")
    end = len(objects) if limit is None else min(len(objects), offset + limit)
    selected = tuple(objects[offset:end])
    next_cursor = None
    if end < len(objects):
        next_cursor = _encode_cursor(
            {
                "version": CURSOR_VERSION,
                "kind": "manifest",
                "manifest_fingerprint": snapshot.fingerprint,
                "selection_fingerprint": selection,
                "offset": end,
            }
        )
    return selected, next_cursor


def _safe_member_path(base: str, target: str) -> str:
    candidate = target.lstrip("/")
    if not target.startswith("/"):
        candidate = posixpath.join(posixpath.dirname(base), target)
    normalized = posixpath.normpath(candidate)
    if normalized.startswith("../") or normalized == "..":
        raise WorkbookContractError(
            "Workbook relationship points outside the XLSX archive",
            details={"base": base, "target": target},
        )
    return normalized


def _validate_zip_members(archive: zipfile.ZipFile) -> None:
    for member in archive.infolist():
        normalized = posixpath.normpath(member.filename)
        if (
            member.filename.startswith("/")
            or normalized == ".."
            or normalized.startswith("../")
        ):
            raise WorkbookContractError(
                "Workbook contains an unsafe archive member path",
                details={"member": member.filename},
            )
        if member.flag_bits & 0x1:
            raise WorkbookContractError(
                "Workbook unexpectedly contains an encrypted member",
                details={"member": member.filename},
            )


def _shared_strings(
    archive: zipfile.ZipFile,
) -> tuple[str, ...]:
    member = "xl/sharedStrings.xml"
    if member not in archive.namelist():
        return ()
    values: list[str] = []
    try:
        with archive.open(member) as source:
            for _event, element in ElementTree.iterparse(
                source,
                events=("end",),
            ):
                if element.tag == f"{{{MAIN_NS}}}si":
                    values.append(
                        "".join(
                            node.text or ""
                            for node in element.iter(f"{{{MAIN_NS}}}t")
                        )
                    )
                    element.clear()
    except ElementTree.ParseError as error:
        raise WorkbookContractError(
            f"Workbook shared-string table is invalid XML: {error}"
        ) from error
    return tuple(values)


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    if not letters:
        raise WorkbookContractError(
            "Workbook cell is missing a column reference",
            details={"reference": reference},
        )
    value = 0
    for character in letters.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _cell_value(
    cell: ElementTree.Element,
    shared_strings: Sequence[str],
) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            node.text or ""
            for node in cell.iter(f"{{{MAIN_NS}}}t")
        )
    value = cell.find(f"{{{MAIN_NS}}}v")
    if value is None or value.text is None:
        return ""
    raw = value.text
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError) as error:
            raise WorkbookContractError(
                "Workbook cell references an invalid shared string",
                details={
                    "cell": cell.attrib.get("r"),
                    "shared_string_index": raw,
                },
            ) from error
    return raw


def _iter_sheet_rows(
    archive: zipfile.ZipFile,
    sheet_member: str,
    shared_strings: Sequence[str],
) -> Iterator[tuple[int, tuple[str, ...]]]:
    try:
        with archive.open(sheet_member) as source:
            for _event, element in ElementTree.iterparse(
                source,
                events=("end",),
            ):
                if element.tag != f"{{{MAIN_NS}}}row":
                    continue
                row_number_text = element.attrib.get("r", "")
                try:
                    row_number = int(row_number_text)
                except ValueError as error:
                    raise WorkbookContractError(
                        "Workbook row has an invalid row number",
                        details={"row_number": row_number_text},
                    ) from error
                cells: dict[int, str] = {}
                for cell in element.findall(f"{{{MAIN_NS}}}c"):
                    index = _column_index(cell.attrib.get("r", ""))
                    value = _cell_value(cell, shared_strings)
                    if index >= len(SEMANTIC_HEADERS) and value.strip():
                        raise WorkbookContractError(
                            "Workbook contains unexpected populated columns",
                            details={
                                "row_number": row_number,
                                "column_index": index + 1,
                                "value": value,
                            },
                        )
                    if index < len(SEMANTIC_HEADERS):
                        cells[index] = value
                yield row_number, tuple(
                    cells.get(index, "")
                    for index in range(len(SEMANTIC_HEADERS))
                )
                element.clear()
    except KeyError as error:
        raise WorkbookContractError(
            "Workbook is missing its selected worksheet member",
            details={"sheet_member": sheet_member},
        ) from error
    except ElementTree.ParseError as error:
        raise WorkbookContractError(
            f"Workbook worksheet is invalid XML: {error}",
            details={"sheet_member": sheet_member},
        ) from error


@dataclass(frozen=True)
class WorkbookDescriptor:
    sheet_name: str
    sheet_member: str
    raw_headers: tuple[str, ...]
    semantic_headers: tuple[str, ...]
    record_count: int
    shared_string_count: int
    dimension: str | None
    header_aliases: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheet_name": self.sheet_name,
            "sheet_member": self.sheet_member,
            "raw_headers": list(self.raw_headers),
            "semantic_headers": list(self.semantic_headers),
            "record_count": self.record_count,
            "shared_string_count": self.shared_string_count,
            "dimension": self.dimension,
            "header_aliases": dict(self.header_aliases),
        }


def _worksheet_member(
    archive: zipfile.ZipFile,
    sheet_name: str,
) -> str:
    try:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
    except KeyError as error:
        raise WorkbookContractError(
            "XLSX package is missing workbook relationship metadata"
        ) from error
    except ElementTree.ParseError as error:
        raise WorkbookContractError(
            f"XLSX workbook metadata is invalid XML: {error}"
        ) from error
    relationship_targets = {
        node.attrib.get("Id"): node.attrib.get("Target")
        for node in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
    }
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        if sheet.attrib.get("name") != sheet_name:
            continue
        relationship_id = sheet.attrib.get(f"{{{DOCUMENT_REL_NS}}}id")
        target = relationship_targets.get(relationship_id)
        if not target:
            raise WorkbookContractError(
                "Selected worksheet has no package relationship",
                details={"sheet_name": sheet_name},
            )
        member = _safe_member_path("xl/workbook.xml", target)
        if member not in archive.namelist():
            raise WorkbookContractError(
                "Selected worksheet member is absent from the XLSX package",
                details={"sheet_name": sheet_name, "sheet_member": member},
            )
        return member
    raise WorkbookContractError(
        "Workbook no longer contains the expected worksheet",
        details={"expected_sheet_name": sheet_name},
    )


def describe_workbook(
    path: Path | str,
    dataset: DatasetSpec,
) -> WorkbookDescriptor:
    """Validate the XLSX package and return source schema metadata."""
    workbook_path = Path(path)
    try:
        with zipfile.ZipFile(workbook_path) as archive:
            _validate_zip_members(archive)
            sheet_member = _worksheet_member(archive, dataset.sheet_name)
            strings = _shared_strings(archive)
            dimension: str | None = None
            try:
                worksheet_root = ElementTree.fromstring(
                    archive.read(sheet_member)
                )
                dimension_node = worksheet_root.find(
                    f"{{{MAIN_NS}}}dimension"
                )
                if dimension_node is not None:
                    dimension = dimension_node.attrib.get("ref")
            except ElementTree.ParseError as error:
                raise WorkbookContractError(
                    f"Workbook worksheet is invalid XML: {error}",
                    details={"sheet_member": sheet_member},
                ) from error
            row_iterator = _iter_sheet_rows(archive, sheet_member, strings)
            try:
                header_row_number, headers = next(row_iterator)
            except StopIteration as error:
                raise WorkbookContractError(
                    "Workbook worksheet is empty",
                    details={"sheet_name": dataset.sheet_name},
                ) from error
            if header_row_number != 1 or headers not in dataset.accepted_headers:
                raise WorkbookContractError(
                    "Workbook headers no longer match the observed schema",
                    details={
                        "dataset": dataset.dataset_id,
                        "header_row_number": header_row_number,
                        "actual_headers": list(headers),
                        "accepted_headers": [
                            list(item) for item in dataset.accepted_headers
                        ],
                    },
                )
            record_count = sum(1 for _item in row_iterator)
    except (OSError, zipfile.BadZipFile) as error:
        raise WorkbookContractError(
            f"Tax Court artifact is not a readable XLSX workbook: {error}",
            details={"path": str(workbook_path)},
        ) from error
    aliases = (
        {"Year": "county"}
        if dataset.dataset_id == "open"
        and headers == OPEN_HEADERS_WITH_ANOMALY
        else {}
    )
    return WorkbookDescriptor(
        sheet_name=dataset.sheet_name,
        sheet_member=sheet_member,
        raw_headers=headers,
        semantic_headers=SEMANTIC_HEADERS,
        record_count=record_count,
        shared_string_count=len(strings),
        dimension=dimension,
        header_aliases=aliases,
    )


@dataclass(frozen=True)
class LocalWorkbook:
    dataset: DatasetSpec
    source_object: S3Object
    path: Path
    size: int
    sha256: str
    descriptor: WorkbookDescriptor
    manifest_fingerprint: str
    etag: str | None = None
    last_modified: str | None = None
    version_id: str | None = None

    @property
    def binding(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset.dataset_id,
            "s3_key": self.source_object.key,
            "url": self.source_object.url,
            "size": self.size,
            "sha256": self.sha256,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "version_id": self.version_id,
            "sheet_name": self.descriptor.sheet_name,
            "sheet_member": self.descriptor.sheet_member,
            "raw_headers": list(self.descriptor.raw_headers),
            "record_count": self.descriptor.record_count,
            "manifest_fingerprint": self.manifest_fingerprint,
        }


def _local_workbook_from_path(
    dataset: DatasetSpec,
    source_object: S3Object,
    path: Path | str,
    *,
    manifest_fingerprint: str,
    etag: str | None = None,
    last_modified: str | None = None,
    version_id: str | None = None,
    known_sha256: str | None = None,
) -> LocalWorkbook:
    workbook_path = Path(path)
    descriptor = describe_workbook(workbook_path, dataset)
    return LocalWorkbook(
        dataset=dataset,
        source_object=source_object,
        path=workbook_path,
        size=workbook_path.stat().st_size,
        sha256=known_sha256 or file_sha256(workbook_path),
        descriptor=descriptor,
        manifest_fingerprint=manifest_fingerprint,
        etag=(etag or source_object.etag).strip('"'),
        last_modified=last_modified or source_object.last_modified,
        version_id=version_id,
    )


@contextmanager
def _artifact_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _cache_destination(
    source_object: S3Object,
    probe: ArtifactProbe,
    cache_dir: Path,
) -> Path:
    validator = sha256_fingerprint(
        {
            "url": source_object.url,
            "etag": probe.etag,
            "last_modified": probe.last_modified,
            "content_length": probe.content_length,
            "version_id": probe.headers.get("x-amz-version-id"),
        }
    )[:16]
    source_name = Path(source_object.key).name
    return cache_dir / f"{Path(source_name).stem}.{validator}.xlsx"


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=args.chunk_size,
    )


def resolve_local_workbooks(
    args: argparse.Namespace,
    snapshot: ManifestSnapshot,
    dataset_ids: Sequence[str],
    *,
    transfer_client: BulkTransferClient,
    workbook_paths: Mapping[str, Path | str] | None = None,
) -> tuple[LocalWorkbook, ...]:
    """Resolve selected datasets to hash-bound local XLSX snapshots."""
    if workbook_paths is not None:
        missing = [
            dataset_id
            for dataset_id in dataset_ids
            if dataset_id not in workbook_paths
        ]
        if missing:
            raise WorkbookContractError(
                "Local workbook mapping omitted selected datasets",
                details={"missing_datasets": missing},
            )
    resolved: list[LocalWorkbook] = []
    for dataset_id in dataset_ids:
        dataset = DATASET_SPECS[dataset_id]
        source_object = snapshot.object_for(dataset_id, "xlsx")
        if workbook_paths is not None:
            resolved.append(
                _local_workbook_from_path(
                    dataset,
                    source_object,
                    workbook_paths[dataset_id],
                    manifest_fingerprint=snapshot.fingerprint,
                )
            )
            continue
        artifact = source_object.artifact()
        probe = transfer_client.probe(artifact, sample_bytes=16)
        if probe.format_hint != "zip":
            raise WorkbookContractError(
                "Tax Court XLSX artifact no longer has a ZIP signature",
                details={
                    "dataset": dataset_id,
                    "url": artifact.url,
                    "signature_hex": probe.signature_hex,
                    "media_type": probe.media_type,
                },
            )
        destination = _cache_destination(
            source_object,
            probe,
            Path(args.cache_dir),
        )
        with _artifact_lock(destination.with_suffix(".lock")):
            download = transfer_client.download(
                BulkArtifact(
                    artifact_id=artifact.artifact_id,
                    url=artifact.url,
                    filename=artifact.filename,
                    media_type=artifact.media_type,
                    archive_format=artifact.archive_format,
                    expected_size=probe.content_length,
                    etag=probe.etag,
                    last_modified=probe.last_modified,
                    metadata=artifact.metadata,
                ),
                destination,
                resume=True,
                max_bytes=args.max_download_bytes,
            )
        resolved.append(
            _local_workbook_from_path(
                dataset,
                source_object,
                download.path,
                manifest_fingerprint=snapshot.fingerprint,
                etag=download.etag or probe.etag,
                last_modified=download.last_modified or probe.last_modified,
                version_id=probe.headers.get("x-amz-version-id"),
                known_sha256=download.sha256,
            )
        )
    return tuple(resolved)


def iter_workbook_rows(
    local: LocalWorkbook,
    *,
    start_position: int = 0,
) -> Iterator[tuple[int, int, tuple[str, ...]]]:
    """Yield data-row position, Excel row number, and raw source values."""
    if (
        start_position < 0
        or start_position > local.descriptor.record_count
    ):
        raise CursorError(
            "Cursor row position is outside the selected workbook",
            details={
                "dataset": local.dataset.dataset_id,
                "row_position": start_position,
                "record_count": local.descriptor.record_count,
            },
        )
    try:
        with zipfile.ZipFile(local.path) as archive:
            strings = _shared_strings(archive)
            rows = _iter_sheet_rows(
                archive,
                local.descriptor.sheet_member,
                strings,
            )
            try:
                next(rows)
            except StopIteration as error:
                raise WorkbookContractError(
                    "Workbook worksheet became empty during traversal"
                ) from error
            observed = 0
            for position, (row_number, values) in enumerate(rows):
                observed = position + 1
                if position >= start_position:
                    yield position, row_number, values
    except (OSError, zipfile.BadZipFile) as error:
        raise WorkbookContractError(
            f"Could not traverse Tax Court workbook: {error}",
            details={"path": str(local.path)},
        ) from error
    if observed != local.descriptor.record_count:
        raise WorkbookContractError(
            "Workbook row count changed between validation and traversal",
            details={
                "dataset": local.dataset.dataset_id,
                "expected_rows": local.descriptor.record_count,
                "actual_rows": observed,
            },
        )


def _clean(value: str | None) -> str | None:
    normalized = " ".join((value or "").strip().split())
    return normalized or None


def _text_key(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _identifier_key(value: str | None) -> str:
    compact = re.sub(r"\s+", "", (value or "").strip().upper())
    if re.fullmatch(r"\d+(?:\.\d+)?", compact):
        integer, dot, fraction = compact.partition(".")
        integer = integer.lstrip("0") or "0"
        fraction = fraction.rstrip("0")
        return integer + (f".{fraction}" if dot and fraction else "")
    return compact


def _docket_raw(value: str | None) -> str | None:
    compact = re.sub(r"[^0-9]", "", value or "")
    if re.fullmatch(r"\d{10}", compact):
        if "-" in (value or ""):
            first, second = (value or "").strip().split("-", 1)
            if len(first) == 6 and len(second) == 4:
                return second + first
        return compact
    return _clean(value)


def _docket_display(raw: str | None) -> str | None:
    if raw and re.fullmatch(r"\d{10}", raw):
        return f"{raw[4:]}-{raw[:4]}"
    return raw


def _source_date(value: str | None) -> dict[str, Any]:
    raw = _clean(value)
    normalized: str | None = None
    if raw:
        try:
            normalized = datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
        except ValueError:
            pass
    return {
        "raw": raw,
        "source_format": "MM/DD/YYYY",
        "iso": normalized,
    }


def _assessment_year(value: str | None) -> int | None:
    raw = _clean(value)
    if raw and re.fullmatch(r"\d{4}", raw):
        year = int(raw)
        if 1900 <= year <= 2100:
            return year
    return None


def _county_name(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    alias = re.sub(r"[^a-z0-9]", "", cleaned.casefold())
    if alias.endswith("county"):
        alias = alias.removesuffix("county")
    return COUNTY_ALIASES.get(alias, cleaned)


def _row_fields(values: Sequence[str]) -> dict[str, str]:
    if len(values) != len(SEMANTIC_HEADERS):
        raise WorkbookContractError(
            "Workbook row width does not match the validated schema",
            details={
                "expected_columns": len(SEMANTIC_HEADERS),
                "actual_columns": len(values),
            },
        )
    return dict(zip(SEMANTIC_HEADERS, values, strict=True))


def _normalization_issues(fields: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    docket = _clean(fields["docket_number"])
    if not docket or not re.fullmatch(r"\d{10}", docket):
        issues.append(f"docket_number:unexpected_format:{docket}")
    entered = _source_date(fields["entered_date"])
    if entered["raw"] and entered["iso"] is None:
        issues.append(f"entered_date:unparsed:{entered['raw']}")
    year_raw = _clean(fields["assessment_year"])
    if year_raw and _assessment_year(year_raw) is None:
        issues.append(f"assessment_year:unparsed_or_out_of_range:{year_raw}")
    county = _county_name(fields["county"])
    if county and county not in COUNTIES:
        issues.append(f"county:unrecognized:{county}")
    return issues


def normalize_row(
    values: Sequence[str],
    *,
    local: LocalWorkbook,
    position: int,
    row_number: int,
    include_raw_row: bool = False,
) -> dict[str, Any]:
    """Normalize one docket/property occurrence with artifact provenance."""
    fields = _row_fields(values)
    cleaned = {name: _clean(value) for name, value in fields.items()}
    docket_raw = _docket_raw(cleaned["docket_number"])
    if not docket_raw:
        raise WorkbookContractError(
            "Workbook row has no docket number",
            details={
                "dataset": local.dataset.dataset_id,
                "row_number": row_number,
            },
        )
    docket_display = _docket_display(docket_raw)
    assert docket_display is not None
    entered = _source_date(cleaned["entered_date"])
    assessment_year = _assessment_year(cleaned["assessment_year"])
    county_name = _county_name(cleaned["county"])
    county_fips = COUNTIES.get(county_name or "")
    row_payload = {
        name: cleaned[name]
        for name in SEMANTIC_HEADERS
    }
    row_sha256 = hashlib.sha256(
        canonical_json(row_payload).encode("utf-8")
    ).hexdigest()
    source_occurrence_id = sha256_fingerprint(
        {
            "artifact_sha256": local.sha256,
            "sheet_member": local.descriptor.sheet_member,
            "row_number": row_number,
            "row_sha256": row_sha256,
        }
    )
    case_ref = canonical_court_ref(
        SOURCE_ID,
        COURT_ID,
        docket_raw,
        "case",
    )
    record: dict[str, Any] = {
        "record_type": "tax_court_property_case_parcel_row",
        "native_record_id": source_occurrence_id,
        "source_occurrence_id": source_occurrence_id,
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            docket_raw,
            "property-case-parcel-row",
            native_id=source_occurrence_id,
        ),
        "case_canonical_ref": case_ref,
        "case": {
            "docket_number_raw": docket_raw,
            "docket_number": docket_display,
            "filing_year": (
                int(docket_raw[:4])
                if re.fullmatch(r"\d{10}", docket_raw)
                else None
            ),
            "title": cleaned["case_title"],
            "entered_date": entered,
        },
        "property": {
            "county_name": county_name,
            "county_fips": county_fips,
            "block": cleaned["block"],
            "lot": cleaned["lot"],
            "unit": cleaned["unit"],
            "assessment_year_raw": cleaned["assessment_year"],
            "assessment_year": assessment_year,
        },
        "dataset": {
            "id": local.dataset.dataset_id,
            "label": local.dataset.label,
            "scope": local.dataset.scope,
        },
        "jurisdiction": {
            "state_code": "NJ",
            "state_fips": "34",
            "county_name": county_name,
            "county_fips": county_fips,
        },
        "normalization_issues": _normalization_issues(fields),
        "source_record": {
            "publisher": "New Jersey Judiciary",
            "landing_url": LANDING_URL,
            "manifest_url": S3_LIST_URL,
            "artifact_url": local.source_object.url,
            "s3_key": local.source_object.key,
            "artifact_size": local.size,
            "artifact_sha256": local.sha256,
            "etag": local.etag,
            "last_modified": local.last_modified,
            "version_id": local.version_id,
            "workbook_sheet": local.descriptor.sheet_name,
            "worksheet_member": local.descriptor.sheet_member,
            "raw_headers": list(local.descriptor.raw_headers),
            "header_aliases": dict(local.descriptor.header_aliases),
            "row_position": position,
            "row_number": row_number,
            "row_sha256": row_sha256,
        },
    }
    if include_raw_row:
        record["source_record"]["raw_row"] = row_payload
    return record


@dataclass(frozen=True)
class SearchSelection:
    query: str | None
    field: str
    docket: str | None
    county: str | None
    block: str | None
    lot: str | None
    unit: str | None
    assessment_year: int | None
    entered_from: str | None
    entered_to: str | None
    dataset_ids: tuple[str, ...]
    include_raw_row: bool

    @property
    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "field": self.field,
            "docket": self.docket,
            "county": self.county,
            "block": self.block,
            "lot": self.lot,
            "unit": self.unit,
            "assessment_year": self.assessment_year,
            "entered_from": self.entered_from,
            "entered_to": self.entered_to,
            "dataset_ids": list(self.dataset_ids),
            "include_raw_row": self.include_raw_row,
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.fingerprint_payload)


def build_selection(args: argparse.Namespace) -> SearchSelection:
    entered_from = getattr(args, "entered_from", None)
    entered_to = getattr(args, "entered_to", None)
    if entered_from and entered_to and entered_from > entered_to:
        raise ValueError("entered-from must not be after entered-to")
    county = getattr(args, "county", None)
    if county:
        normalized_county = _county_name(county)
        if normalized_county not in COUNTIES:
            raise ValueError(f"Unknown New Jersey county: {county}")
        county = normalized_county
    docket = _docket_raw(getattr(args, "docket", None))
    return SearchSelection(
        query=_clean(getattr(args, "query", None)),
        field=args.field,
        docket=docket,
        county=county,
        block=_clean(getattr(args, "block", None)),
        lot=_clean(getattr(args, "lot", None)),
        unit=_clean(getattr(args, "unit", None)),
        assessment_year=getattr(args, "assessment_year", None),
        entered_from=entered_from,
        entered_to=entered_to,
        dataset_ids=_selected_dataset_ids(args.dataset),
        include_raw_row=args.include_raw_row,
    )


def _query_haystack(
    fields: Mapping[str, str],
    field: str,
) -> str:
    if field == "docket":
        raw = _docket_raw(fields["docket_number"])
        values = (raw or "", _docket_display(raw) or "")
    elif field == "case-title":
        values = (fields["case_title"],)
    elif field == "parcel":
        values = (fields["block"], fields["lot"], fields["unit"])
    elif field == "county":
        values = (fields["county"],)
    else:
        raw = _docket_raw(fields["docket_number"])
        values = (
            raw or "",
            _docket_display(raw) or "",
            fields["case_title"],
            fields["entered_date"],
            fields["block"],
            fields["lot"],
            fields["unit"],
            fields["assessment_year"],
            fields["county"],
        )
    return _text_key(" ".join(values))


def row_matches(
    values: Sequence[str],
    selection: SearchSelection,
) -> bool:
    fields = _row_fields(values)
    if selection.query and _text_key(selection.query) not in _query_haystack(
        fields,
        selection.field,
    ):
        return False
    if (
        selection.docket
        and _docket_raw(fields["docket_number"]) != selection.docket
    ):
        return False
    if (
        selection.county
        and _county_name(fields["county"]) != selection.county
    ):
        return False
    for selected, field_name in (
        (selection.block, "block"),
        (selection.lot, "lot"),
        (selection.unit, "unit"),
    ):
        if selected and _identifier_key(fields[field_name]) != _identifier_key(
            selected
        ):
            return False
    if (
        selection.assessment_year is not None
        and _assessment_year(fields["assessment_year"])
        != selection.assessment_year
    ):
        return False
    entered = _source_date(fields["entered_date"])["iso"]
    if selection.entered_from and (
        entered is None or entered < selection.entered_from
    ):
        return False
    if selection.entered_to and (
        entered is None or entered > selection.entered_to
    ):
        return False
    return True


def _workbook_fingerprint(locals_: Sequence[LocalWorkbook]) -> str:
    return sha256_fingerprint([local.binding for local in locals_])


def search_local_workbooks(
    *,
    selection: SearchSelection,
    locals_: Sequence[LocalWorkbook],
    limit: int | None,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Search in source order with query- and snapshot-bound continuation."""
    artifact_fingerprint = _workbook_fingerprint(locals_)
    start_dataset = 0
    start_position = 0
    if cursor:
        payload = _decode_cursor(cursor)
        if payload.get("kind") != "search":
            raise CursorError("Cursor is not a search cursor")
        if payload.get("selection_fingerprint") != selection.fingerprint:
            raise CursorError(
                "Tax Court cursor selection fingerprint does not match query"
            )
        if payload.get("artifact_fingerprint") != artifact_fingerprint:
            raise CursorError(
                "Tax Court cursor artifact binding no longer matches source"
            )
        start_dataset = payload.get("dataset_index")
        start_position = payload.get("row_position")
        if (
            isinstance(start_dataset, bool)
            or not isinstance(start_dataset, int)
            or start_dataset < 0
            or start_dataset >= len(locals_)
            or isinstance(start_position, bool)
            or not isinstance(start_position, int)
            or start_position < 0
        ):
            raise CursorError("Search cursor position is invalid")
    records: list[dict[str, Any]] = []
    next_cursor = None
    for dataset_index, local in enumerate(locals_):
        if dataset_index < start_dataset:
            continue
        row_start = start_position if dataset_index == start_dataset else 0
        for position, row_number, values in iter_workbook_rows(
            local,
            start_position=row_start,
        ):
            if not row_matches(values, selection):
                continue
            if limit is not None and len(records) >= limit:
                next_cursor = _encode_cursor(
                    {
                        "version": CURSOR_VERSION,
                        "kind": "search",
                        "selection_fingerprint": selection.fingerprint,
                        "artifact_fingerprint": artifact_fingerprint,
                        "dataset_index": dataset_index,
                        "row_position": position,
                    }
                )
                return records, next_cursor
            records.append(
                normalize_row(
                    values,
                    local=local,
                    position=position,
                    row_number=row_number,
                    include_raw_row=selection.include_raw_row,
                )
            )
    return records, next_cursor


def validate_local_workbook(local: LocalWorkbook) -> dict[str, Any]:
    """Fully traverse one workbook and summarize observed source semantics."""
    docket_counts: Counter[str] = Counter()
    county_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    row_counts: Counter[str] = Counter()
    parsed_dates: list[str] = []
    for position, row_number, values in iter_workbook_rows(local):
        fields = _row_fields(values)
        docket = _clean(fields["docket_number"]) or ""
        docket_counts[docket] += 1
        county_counts[_clean(fields["county"]) or ""] += 1
        year_counts[_clean(fields["assessment_year"]) or ""] += 1
        row_hash = hashlib.sha256(
            canonical_json(
                {
                    name: _clean(fields[name])
                    for name in SEMANTIC_HEADERS
                }
            ).encode("utf-8")
        ).hexdigest()
        row_counts[row_hash] += 1
        parsed = _source_date(fields["entered_date"])["iso"]
        if parsed:
            parsed_dates.append(parsed)
        for issue in _normalization_issues(fields):
            issue_counts[issue.split(":", 1)[0]] += 1
        if position + 1 > local.descriptor.record_count:
            raise WorkbookContractError(
                "Workbook traversal exceeded validated row count",
                details={"row_number": row_number},
            )
    return {
        "record_type": "workbook_validation",
        "dataset": {
            "id": local.dataset.dataset_id,
            "label": local.dataset.label,
            "scope": local.dataset.scope,
        },
        "artifact": local.binding,
        "workbook": local.descriptor.to_dict(),
        "validation": {
            "complete_workbook_traversal": True,
            "records_traversed": local.descriptor.record_count,
            "unique_dockets": len(docket_counts),
            "duplicate_docket_rows": sum(
                count - 1 for count in docket_counts.values()
            ),
            "maximum_rows_per_docket": max(docket_counts.values(), default=0),
            "exact_duplicate_rows": sum(
                count - 1 for count in row_counts.values()
            ),
            "county_counts": dict(sorted(county_counts.items())),
            "assessment_year_counts": dict(sorted(year_counts.items())),
            "entered_date_min": min(parsed_dates, default=None),
            "entered_date_max": max(parsed_dates, default=None),
            "normalization_issue_counts_by_field": dict(
                sorted(issue_counts.items())
            ),
        },
    }


def source_manifest_record() -> dict[str, Any]:
    """Return a stable, network-free source and route description."""
    return {
        "record_type": "source_family_manifest",
        "schema_version": "public-record-source-family/1.0",
        "family_id": SOURCE_ID,
        "canonical_ref": "NJTAXCOURT:SOURCE:LOCAL-PROPERTY-REPORTS",
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "datasets": [
            {
                "dataset_id": spec.dataset_id,
                "label": spec.label,
                "scope": spec.scope,
                "xlsx_key": spec.xlsx_key,
                "pdf_key": spec.pdf_key,
                "worksheet": spec.sheet_name,
            }
            for spec in DATASET_SPECS.values()
        ],
        "operations": {
            "manifest": "official_s3_list_objects_v2",
            "probe": "official_artifact_head_and_bounded_range",
            "download": "official_artifact_transfer",
            "validate": "complete_xlsx_traversal",
            "search": "complete_or_cursor_bounded_xlsx_traversal",
            "alternatives": "network_free_complementary_route_inventory",
        },
        "access_state": ACCESS_STATE,
        "join_guidance": JOIN_GUIDANCE,
        "complementary_routes": [
            {
                "source_id": route["source_id"],
                "name": route["name"],
                "url": route["url"],
            }
            for route in _alternative_routes()
        ],
    }


def _alternative_routes() -> list[dict[str, Any]]:
    """Return official and complementary routes for missing report detail."""
    return [
        {
            "source_id": "us-nj-tax-court-current-object-versions",
            "name": "New Jersey Tax Court current-report object versions",
            "url": (
                f"{S3_BASE_URL}/?versions&prefix="
                "tax-reports/localtaxcases"
            ),
            "authority": "New Jersey Judiciary public S3 bucket",
            "coverage": (
                "Prior versions of the replaceable current docketed/open "
                "report keys. The listing is machine-readable but does not "
                "enumerate the named monthly judgment archive."
            ),
            "access": "Public anonymous S3 ListObjectVersions XML.",
            "join_fields": ["artifact key", "ETag", "version ID", "modified time"],
        },
        {
            "source_id": "us-nj-tax-court-judgment-archives",
            "name": "New Jersey Tax Court docket and judgment archives",
            "url": LANDING_URL,
            "authority": "New Jersey Judiciary",
            "coverage": (
                "Annual docket lists and monthly local-property judgment "
                "lists in XLS/PDF, with archive years shown from 2008 onward."
            ),
            "access": (
                "The archive is usable in a browser and indexed by public "
                "search engines; direct non-browser HTTP currently receives "
                "the site's edge challenge."
            ),
            "verified_artifacts": [
                {
                    "period": "2025-01",
                    "format": "xls",
                    "url": (
                        "https://www.njcourts.gov/sites/default/files/"
                        "tax/docket/01_25%20judgments.xls"
                    ),
                },
                {
                    "period": "2025-01",
                    "format": "pdf",
                    "url": (
                        "https://www.njcourts.gov/sites/default/files/"
                        "tax/docket/01_25%20judgments.pdf"
                    ),
                },
                {
                    "period": "2025-05",
                    "format": "pdf",
                    "url": (
                        "https://www.njcourts.gov/sites/default/files/"
                        "tax/docket/05_25%20judgments.pdf"
                    ),
                },
            ],
            "join_fields": [
                "docket number",
                "case title",
                "county",
                "municipality",
                "block",
                "lot",
                "assessment year",
                "judgment date",
            ],
        },
        {
            "source_id": "us-nj-govconnect-tax-notices",
            "name": "New Jersey GovConnect Tax Collector notices",
            "url": "https://www.nj.gov/govconnect/news/tax/",
            "authority": (
                "New Jersey Department of Community Affairs, Division of "
                "Local Government Services"
            ),
            "coverage": (
                "Recent monthly Tax Court judgment-list notices, publication "
                "dates, corrected-judgment page locations, and operational "
                "context supplied to municipal tax collectors."
            ),
            "access": "Public HTML; notice attachments are not exposed as hrefs.",
            "join_fields": ["report month", "publication date"],
        },
        {
            "source_id": "us-nj-tax-case-public-access",
            "name": "New Jersey Tax Court Case Jacket public access",
            "url": "https://www.njcourts.gov/public/get-help/tax-case-public-access",
            "authority": "New Jersey Judiciary",
            "coverage": (
                "Case lookup by party, docket, or block/lot and available "
                "case-jacket details such as properties and proceedings."
            ),
            "access": "Interactive registration and browser workflow.",
            "join_fields": [
                "party",
                "docket number",
                "block",
                "lot",
            ],
        },
        {
            "source_id": "us-nj-tax-court-opinions",
            "name": "Published and unpublished New Jersey Tax Court opinions",
            "url": "https://www.njcourts.gov/attorneys/opinions/published-tax",
            "additional_url": (
                "https://www.njcourts.gov/attorneys/opinions/unpublished-tax"
            ),
            "authority": "New Jersey Judiciary",
            "coverage": (
                "Written decisions that add reasoning, valuation evidence, "
                "party representation, and disposition context."
            ),
            "join_fields": ["party", "docket number", "decision date"],
        },
        {
            "source_id": "us-nj-property-tax-appeals",
            "name": "New Jersey Treasury property-tax appeal statistics",
            "url": (
                "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml"
            ),
            "authority": "New Jersey Division of Taxation",
            "coverage": (
                "Annual property-tax appeal statistics plus MOD-IV assessment "
                "files for parcel and assessed-value context."
            ),
            "join_fields": [
                "county",
                "municipality",
                "block",
                "lot",
                "assessment year",
            ],
        },
        {
            "source_id": "us-nj-county-tax-boards",
            "name": "County boards of taxation and local assessors",
            "url": (
                "https://www.nj.gov/treasury/taxation/pdf/lpt/"
                "CountyBoardsofTaxation.pdf"
            ),
            "additional_url": (
                "https://www.nj.gov/treasury/taxation/pdf/lpt/"
                "assessor/statewidebycounty.pdf"
            ),
            "authority": "New Jersey Division of Taxation",
            "coverage": (
                "County-level appeal records, judgments, local assessment "
                "records, and contacts for records not present in the "
                "statewide report."
            ),
            "join_fields": [
                "county",
                "municipality",
                "block",
                "lot",
                "assessment year",
            ],
        },
        {
            "source_id": "us-nj-treasury-sr1a-sales",
            "name": "New Jersey SR1A property-sale releases",
            "url": (
                "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml"
            ),
            "local_tool": "tools/query_new_jersey_sr1a.py",
            "authority": "New Jersey Division of Taxation",
            "coverage": (
                "Grantor, grantee, deed, sale price, assessment value, "
                "property location, and parcel details."
            ),
            "join_fields": [
                "county",
                "municipality",
                "block",
                "lot",
                "assessment year",
                "party",
            ],
        },
    ]


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return number


def _positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "date must use YYYY-MM-DD"
        ) from error


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in (
        "query",
        "field",
        "dataset",
        "format",
        "docket",
        "county",
        "block",
        "lot",
        "unit",
        "assessment_year",
        "entered_from",
        "entered_to",
        "include_raw_row",
        "range_bytes",
        "destination",
        "max_download_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = str(value) if isinstance(value, Path) else value
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


def _download_record(
    source_object: S3Object,
    snapshot: ManifestSnapshot,
    download: DownloadResult,
) -> dict[str, Any]:
    record = source_object.to_record(snapshot.fingerprint)
    record["download"] = download.to_dict()
    if source_object.file_format == "xlsx":
        record["workbook"] = describe_workbook(
            download.path,
            source_object.dataset,
        ).to_dict()
    return record


def execute(
    args: argparse.Namespace,
    *,
    manifest_snapshot: ManifestSnapshot | None = None,
    transfer_client: BulkTransferClient | None = None,
    workbook_paths: Mapping[str, Path | str] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute a command and return the shared public-record envelope."""
    query = build_query(args)
    try:
        if args.command == "alternatives":
            result = PublicRecordsResult.success(query, _alternative_routes())
        else:
            snapshot = manifest_snapshot or fetch_manifest(
                timeout=args.timeout,
                retry_attempts=args.retry_attempts,
            )
            if args.command == "manifest":
                objects = _selected_manifest_objects(args, snapshot)
                selected, next_cursor = paginate_manifest(
                    snapshot,
                    objects,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        item.to_record(snapshot.fingerprint)
                        for item in selected
                    ],
                    next_cursor=next_cursor,
                )
            elif args.command in {"probe", "download"}:
                source_object = snapshot.object_for(
                    args.dataset,
                    args.format,
                )
                transfer = transfer_client or _bulk_client(args)
                if args.command == "probe":
                    probe = transfer.probe(
                        source_object.artifact(),
                        sample_bytes=args.range_bytes,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        [
                            {
                                **source_object.to_record(
                                    snapshot.fingerprint
                                ),
                                "probe": probe.to_dict(),
                            }
                        ],
                    )
                else:
                    download = transfer.download(
                        source_object.artifact(),
                        args.destination,
                        resume=True,
                        max_bytes=args.max_download_bytes,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        [
                            _download_record(
                                source_object,
                                snapshot,
                                download,
                            )
                        ],
                        raw_artifact_refs=(download.path,),
                    )
            else:
                dataset_ids = _selected_dataset_ids(args.dataset)
                transfer = transfer_client or _bulk_client(args)
                locals_ = resolve_local_workbooks(
                    args,
                    snapshot,
                    dataset_ids,
                    transfer_client=transfer,
                    workbook_paths=workbook_paths,
                )
                if args.command == "validate":
                    result = PublicRecordsResult.success(
                        query,
                        [
                            validate_local_workbook(local)
                            for local in locals_
                        ],
                        raw_artifact_refs=tuple(
                            str(local.path) for local in locals_
                        ),
                        warnings=SOURCE_WARNINGS,
                    )
                else:
                    selection = build_selection(args)
                    records, next_cursor = search_local_workbooks(
                        selection=selection,
                        locals_=locals_,
                        limit=args.limit,
                        cursor=args.cursor,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        next_cursor=next_cursor,
                        raw_artifact_refs=tuple(
                            str(local.path) for local in locals_
                        ),
                        warnings=SOURCE_WARNINGS,
                    )
    except NewJerseyTaxCourtError as error:
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
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="nj_tax_court_operation_failed",
                    message=str(error),
                    category="source_or_query",
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
        summary=(
            f"New Jersey Tax Court {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"New Jersey Tax Court {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command == "manifest":
            print(
                f"  {record['artifact_id']} | "
                f"{record['last_modified']} | {record['url']}"
            )
        elif args.command == "alternatives":
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "search":
            print(
                f"  {record['case']['docket_number']} | "
                f"{record['case']['title'] or '?'} | "
                f"{record['property']['county_name'] or '?'} "
                f"B{record['property']['block'] or '?'} "
                f"L{record['property']['lot'] or '?'}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    parser.add_argument(
        "--chunk-size",
        type=_positive_int,
        default=DEFAULT_CHUNK_SIZE,
    )


def _add_dataset_arg(
    parser: argparse.ArgumentParser,
    *,
    default: str = "both",
    include_both: bool = True,
) -> None:
    choices = ("docketed", "open", "both") if include_both else (
        "docketed",
        "open",
    )
    parser.add_argument("--dataset", choices=choices, default=default)


def _add_local_workbook_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
    )
    parser.add_argument("--max-download-bytes", type=_positive_int)
    _add_network_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover, download, validate, and search New Jersey Tax Court "
            "local-property case reports"
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    manifest = subparsers.add_parser(
        "manifest",
        help="List current report artifacts from the official S3 manifest",
    )
    _add_dataset_arg(manifest)
    manifest.add_argument(
        "--format",
        choices=("xlsx", "pdf", "all"),
        default="all",
    )
    manifest.add_argument("--limit", type=_positive_int)
    manifest.add_argument("--cursor")
    _add_network_args(manifest)
    add_output_args(manifest)

    probe = subparsers.add_parser(
        "probe",
        help="Probe one current official XLSX or PDF artifact",
    )
    _add_dataset_arg(probe, default="docketed", include_both=False)
    probe.add_argument("--format", choices=("xlsx", "pdf"), default="xlsx")
    probe.add_argument("--range-bytes", type=_nonnegative_int, default=64)
    _add_network_args(probe)
    add_output_args(probe)

    download = subparsers.add_parser(
        "download",
        help="Download and validate one current official artifact",
    )
    _add_dataset_arg(download, default="docketed", include_both=False)
    download.add_argument("--format", choices=("xlsx", "pdf"), default="xlsx")
    download.add_argument("destination", type=Path)
    download.add_argument("--max-download-bytes", type=_positive_int)
    _add_network_args(download)
    add_output_args(download)

    validate = subparsers.add_parser(
        "validate",
        help="Fully traverse selected XLSX reports and summarize source shape",
    )
    _add_dataset_arg(validate)
    _add_local_workbook_args(validate)
    add_output_args(validate)

    search = subparsers.add_parser(
        "search",
        help=(
            "Search selected XLSX reports; without a query or filters, "
            "return the complete selected corpus"
        ),
    )
    search.add_argument("query", nargs="?")
    search.add_argument(
        "--field",
        choices=("any", "docket", "case-title", "parcel", "county"),
        default="any",
    )
    _add_dataset_arg(search)
    search.add_argument("--docket")
    search.add_argument("--county")
    search.add_argument("--block")
    search.add_argument("--lot")
    search.add_argument("--unit")
    search.add_argument("--assessment-year", type=_positive_int)
    search.add_argument("--entered-from", type=_iso_date)
    search.add_argument("--entered-to", type=_iso_date)
    search.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional match bound; omitted traverses every match",
    )
    search.add_argument(
        "--cursor",
        help="Query- and artifact-bound continuation cursor",
    )
    search.add_argument(
        "--include-raw-row",
        action="store_true",
        help="Include the source row keyed by normalized column name",
    )
    _add_local_workbook_args(search)
    add_output_args(search)

    alternatives = subparsers.add_parser(
        "alternatives",
        help=(
            "List official archives and complementary routes for judgments, "
            "case jackets, opinions, assessments, and deeds"
        ),
    )
    add_output_args(alternatives)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
