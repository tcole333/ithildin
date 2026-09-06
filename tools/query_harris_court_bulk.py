#!/usr/bin/env python3
"""Discover and retrieve Harris District Clerk public bulk datasets.

The District Clerk publishes an anonymous, unpaginated ASP.NET catalog. Each
download must be selected from that live catalog: a fresh GET supplies cookies
and hidden fields, then a POST to the same page submits the exact catalog
locator through ``hiddenDownloadFile``.

Examples:
    uv run python tools/query_harris_court_bulk.py list --section Civil \
        --output /tmp/harris-court-catalog.json
    uv run python tools/query_harris_court_bulk.py inspect \
        "Civil\\2024-08-15 FIELD_CODES.xlsx" \
        --output /tmp/harris-court-inspect.json
    uv run python tools/query_harris_court_bulk.py download \
        "Civil\\2024-08-15 FIELD_CODES.xlsx" \
        --destination /tmp/FIELD_CODES.xlsx \
        --output /tmp/harris-court-download.json
    uv run python tools/query_harris_court_bulk.py sentinel --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
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
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
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
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-tx-harris-district-clerk-public-datasets"
SOURCE = SOURCE_ID
CATALOG_URL = (
    "https://www.hcdistrictclerk.com/Common/e-services/PublicDatasets.aspx"
)
DOWNLOAD_LOCATOR_FIELD = "hiddenDownloadFile"
DOWNLOAD_BUTTON_FIELD = (
    "ctl00$ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolder2$"
    "ContentPlaceHolder2$buttonDownload"
)
TIMEOUT = 45.0
REQUEST_DELAY = 0.2
MAX_RETRIES = 2
DEFAULT_SAMPLE_BYTES = 4096
USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

SENTINEL_LOCATOR = r"Civil\2024-08-15 FIELD_CODES.xlsx"
SENTINEL_FILENAME = "FIELD_CODES.xlsx"
SENTINEL_PUBLISHED_DATE = "2024-08-15"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE,
    name="Harris County District Clerk Public Datasets",
    source_role="civil_and_criminal_court_bulk_dataset_catalog",
    base_url=CATALOG_URL,
    dataset_id="PublicDatasets",
    metadata={
        "authority": "Harris County District Clerk",
        "jurisdiction_geoid": "48201",
        "catalog_transport": "aspnet_exact_member_postback",
        "catalog_pagination": "unpaginated",
        "evidence_scope": "bulk_extract_catalog_and_artifacts",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="48201",
    name="Harris County, Texas",
    state_code="TX",
    county_fips="48201",
    locality="Harris County",
)
SOURCE_WARNINGS = (
    (
        "Bulk catalog metadata and downloaded extracts are distinct from "
        "individual filing images in the District Clerk eDocs portal."
    ),
)

_DOWNLOAD_RE = re.compile(
    r"""DownloadDoc\(\s*'((?:\\.|[^'])+)'\s*\)""",
    re.IGNORECASE,
)
_DISPOSITION_FILENAME_RE = re.compile(
    r"""filename\s*=\s*(?:"([^"]+)"|([^;]+))""",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_RANGE_RE = re.compile(r"(?<!\d)(20\d{2})[-_](20\d{2})(?!\d)")


class HarrisCourtBulkError(RuntimeError):
    """Base error for the official public-dataset source."""


class HarrisCourtBulkSourceChanged(HarrisCourtBulkError):
    """The catalog or download response no longer matches the verified shape."""


class HarrisCourtBulkNotFound(HarrisCourtBulkError):
    """A requested artifact is not an exact member of the live catalog."""


class HarrisCourtBulkAmbiguous(HarrisCourtBulkError):
    """A shorthand selector matches multiple live catalog members."""


class HarrisCourtBulkTransportError(HarrisCourtBulkError):
    """The source was unreachable after bounded retries."""


class HarrisCourtBulkRateLimited(HarrisCourtBulkError):
    """The source returned HTTP 429 after bounded retries."""


class HarrisCourtBulkHTTPError(HarrisCourtBulkError):
    """The source returned a non-success HTTP response."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(
            f"Harris District Clerk returned HTTP {status_code}"
        )


@dataclass(frozen=True)
class DatasetArtifact:
    """One exact member of the District Clerk's live catalog."""

    index: int
    section: str
    published_date: str
    filename: str
    native_locator: str

    @property
    def artifact_id(self) -> str:
        return hashlib.sha256(
            self.native_locator.encode("utf-8")
        ).hexdigest()[:20]

    @property
    def native_filename(self) -> str:
        return self.native_locator.rsplit("\\", 1)[-1]

    @property
    def format(self) -> str:
        suffix = Path(self.native_filename).suffix.lower().lstrip(".")
        return suffix or "unknown"

    @property
    def family(self) -> str:
        return _dataset_family(self.filename)

    @property
    def cadence(self) -> str:
        return _dataset_cadence(self.filename)

    def to_record(self) -> dict[str, Any]:
        encoded = quote(self.native_locator, safe=".-_")
        return {
            "source_id": SOURCE,
            "record_kind": "bulk_dataset_artifact",
            "record_scope": "court_bulk_catalog_member",
            "canonical_ref": f"COURT-BULK:{SOURCE}/{encoded}",
            "evidence_ref": f"COURT-BULK:{SOURCE}/{encoded}",
            "artifact_id": self.artifact_id,
            "native_document_id": self.native_locator,
            "native_locator": self.native_locator,
            "section": self.section,
            "published_date": self.published_date,
            "filename": self.filename,
            "native_filename": self.native_filename,
            "format": self.format,
            "dataset_family": self.family,
            "cadence": self.cadence,
            "coverage": _coverage_from_filename(self.filename),
            "source_url": CATALOG_URL,
            "download_contract": {
                "method": "POST",
                "form_url": CATALOG_URL,
                "locator_field": DOWNLOAD_LOCATOR_FIELD,
                "selection": "exact_live_catalog_member",
            },
            "projection": {
                "projectable_as_case": False,
                "scope": "bulk_artifact_manifest",
                "reason": "the artifact must be parsed before case projection",
            },
        }


@dataclass(frozen=True)
class CatalogPage:
    artifacts: tuple[DatasetArtifact, ...]
    hidden_fields: Mapping[str, str]


@dataclass(frozen=True)
class ProbeReceipt:
    artifact: DatasetArtifact
    response_url: str
    content_type: str | None
    content_length: int | None
    content_disposition: str | None
    response_filename: str | None
    sample: bytes
    catalog_artifacts: tuple[DatasetArtifact, ...] = ()

    def to_record(self) -> dict[str, Any]:
        record = self.artifact.to_record()
        record["inspection"] = {
            "response_url": self.response_url,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "content_disposition": self.content_disposition,
            "response_filename": self.response_filename,
            "sample_bytes": len(self.sample),
            "sample_sha256": hashlib.sha256(self.sample).hexdigest(),
            "signature_hex": self.sample[:16].hex(),
            "format_valid": True,
            "transfer_complete": (
                self.content_length is not None
                and len(self.sample) >= self.content_length
            ),
        }
        if self.catalog_artifacts:
            record["catalog_summary"] = _catalog_summary(
                self.catalog_artifacts
            )
        return record


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = (
        value.get_text(" ", strip=True)
        if hasattr(value, "get_text")
        else str(value)
    )
    return re.sub(r"\s+", " ", text).strip()


def _unescape_js_locator(value: str) -> str:
    return value.replace(r"\\", "\\").replace(r"\'", "'")


def _validate_locator(locator: str, section: str) -> None:
    if (
        not locator
        or "\r" in locator
        or "\n" in locator
        or "/" in locator
        or ".." in locator.split("\\")
        or "\\" not in locator
    ):
        raise HarrisCourtBulkSourceChanged(
            f"catalog contains an invalid native locator: {locator!r}"
        )
    prefix = locator.split("\\", 1)[0]
    if prefix.casefold() != section.casefold():
        raise HarrisCourtBulkSourceChanged(
            "catalog row section and download locator disagree"
        )


def _dataset_family(filename: str) -> str:
    folded = filename.casefold()
    if (
        "field_codes" in folded
        or "recordlayoutsandfieldnames" in folded
        or "data dict" in folded
        or "data_dict" in folded
    ):
        return "schema_reference"
    if "overview" in folded:
        return "overview"
    if "filingswithfuturesettings" in folded:
        return "future_settings"
    if "dispos" in folded:
        return "dispositions"
    if "filing" in folded:
        return "filings"
    if "casesummary" in folded:
        return "case_summary"
    if "casesetting" in folded:
        return "case_setting"
    if "activity" in folded or "actmods" in folded:
        return "activity"
    if "party" in folded or "parties" in folded:
        return "party"
    if "service" in folded:
        return "service"
    if "tdi" in folded:
        return "tdi"
    if "bond" in folded:
        return "bond"
    if "misfel" in folded:
        return "misdemeanor_felony_case_index"
    if "historicaldaily" in folded:
        return "historical_daily"
    if "historical" in folded:
        return "historical_snapshot"
    return "other"


def _dataset_cadence(filename: str) -> str:
    folded = filename.casefold()
    if "daily" in folded:
        return "daily"
    if "weekly" in folded:
        return "weekly"
    if "monthly" in folded:
        return "monthly"
    if "historicalcurrent" in folded:
        return "current_historical_segment"
    if _RANGE_RE.search(filename):
        return "historical_segment"
    if "historical" in folded:
        return "historical_snapshot"
    if _dataset_family(filename) in {"overview", "schema_reference"}:
        return "reference"
    return "published_extract"


def _coverage_from_filename(filename: str) -> dict[str, Any]:
    """Return source-name coverage hints without inventing missing dates."""
    match = _RANGE_RE.search(filename)
    if match:
        return {
            "basis": "filename_range",
            "start_year": int(match.group(1)),
            "end_year": int(match.group(2)),
            "raw": match.group(0),
        }
    if "currenttodate" in filename.casefold():
        return {"basis": "filename_label", "raw": "CurrentToDate"}
    if "prevmonth" in filename.casefold():
        return {"basis": "filename_label", "raw": "PrevMonth"}
    return {"basis": "catalog_only"}


def parse_catalog(html: str) -> CatalogPage:
    """Parse every artifact and the ASP.NET state from one catalog response."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblPublicDatasets")
    if table is None:
        raise HarrisCourtBulkSourceChanged(
            "public-dataset catalog table is missing"
        )

    hidden_fields = {
        str(node.get("name")): str(node.get("value") or "")
        for node in soup.select("input[type='hidden'][name]")
    }
    if "__VIEWSTATE" not in hidden_fields:
        raise HarrisCourtBulkSourceChanged(
            "public-dataset form lacks ASP.NET view state"
        )
    if soup.select_one(f"[name='{DOWNLOAD_BUTTON_FIELD}']") is None:
        raise HarrisCourtBulkSourceChanged(
            "public-dataset form lacks the download button"
        )

    artifacts: list[DatasetArtifact] = []
    section: str | None = None
    for row in table.select("tr"):
        if "trPublicReportsSubHeader" in (row.get("class") or []):
            section = _clean_text(row)
            continue
        date_node = row.select_one("th[scope='row']")
        cells = row.select("td")
        link = row.select_one("[onclick*='DownloadDoc']")
        if link is None:
            if date_node is not None and cells and _clean_text(cells[0]):
                raise HarrisCourtBulkSourceChanged(
                    "dataset row lacks its download action"
                )
            continue
        if not section:
            raise HarrisCourtBulkSourceChanged(
                "dataset row appears before a section header"
            )
        action = str(link.get("onclick") or "")
        match = _DOWNLOAD_RE.search(action)
        if not match:
            raise HarrisCourtBulkSourceChanged(
                "dataset download action no longer matches DownloadDoc"
            )
        locator = _unescape_js_locator(match.group(1))
        _validate_locator(locator, section)
        if date_node is None or not cells:
            raise HarrisCourtBulkSourceChanged(
                "dataset row lacks its date or filename"
            )
        date_match = _DATE_RE.search(_clean_text(date_node))
        filename = _clean_text(cells[0])
        if date_match is None or not filename:
            raise HarrisCourtBulkSourceChanged(
                "dataset row has an invalid date or blank filename"
            )
        artifacts.append(
            DatasetArtifact(
                index=len(artifacts),
                section=section,
                published_date=date_match.group(1),
                filename=filename,
                native_locator=locator,
            )
        )
    if not artifacts:
        raise HarrisCourtBulkSourceChanged(
            "public-dataset catalog contains no artifacts"
        )
    return CatalogPage(tuple(artifacts), hidden_fields)


def _catalog_summary(
    artifacts: Sequence[DatasetArtifact],
) -> dict[str, Any]:
    section_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    publication_dates: dict[str, dict[str, str]] = {}
    identities: list[dict[str, str]] = []
    for artifact in artifacts:
        section_counts[artifact.section] = (
            section_counts.get(artifact.section, 0) + 1
        )
        family_counts[artifact.family] = (
            family_counts.get(artifact.family, 0) + 1
        )
        bounds = publication_dates.setdefault(
            artifact.section,
            {
                "earliest": artifact.published_date,
                "latest": artifact.published_date,
            },
        )
        bounds["earliest"] = min(
            bounds["earliest"],
            artifact.published_date,
        )
        bounds["latest"] = max(
            bounds["latest"],
            artifact.published_date,
        )
        identities.append(
            {
                "native_locator": artifact.native_locator,
                "published_date": artifact.published_date,
                "family": artifact.family,
            }
        )
    return {
        "artifact_count": len(artifacts),
        "section_counts": dict(sorted(section_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "publication_dates": dict(sorted(publication_dates.items())),
        "artifact_fingerprint": hashlib.sha256(
            canonical_json(identities).encode("utf-8")
        ).hexdigest(),
    }


def resolve_artifact(
    artifacts: Sequence[DatasetArtifact],
    selector: str,
) -> DatasetArtifact:
    """Resolve only an exact live locator, artifact ID, or unique filename."""
    value = selector.strip()
    matches = [
        item
        for item in artifacts
        if value
        in {
            item.native_locator,
            item.artifact_id,
            item.filename,
            item.native_filename,
        }
    ]
    if not matches:
        raise HarrisCourtBulkNotFound(
            f"no exact live catalog member matches {selector!r}"
        )
    if len(matches) > 1:
        locators = ", ".join(item.native_locator for item in matches)
        raise HarrisCourtBulkAmbiguous(
            f"selector {selector!r} matches multiple members: {locators}"
        )
    return matches[0]


def _response_filename(value: str | None) -> str | None:
    match = _DISPOSITION_FILENAME_RE.search(value or "")
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip()


def _expected_magic(artifact: DatasetArtifact, sample: bytes) -> bool:
    suffix = artifact.format
    if suffix in {"zip", "xlsx"}:
        return sample.startswith(b"PK\x03\x04")
    if suffix == "pdf":
        return sample.startswith(b"%PDF-")
    if suffix == "txt":
        stripped = sample.lstrip().lower()
        return bool(sample) and not stripped.startswith(
            (b"<!doctype html", b"<html")
        )
    return bool(sample)


def _validate_download_response(
    artifact: DatasetArtifact,
    *,
    content_disposition: str | None,
    sample: bytes,
) -> str:
    filename = _response_filename(content_disposition)
    if filename != artifact.native_filename:
        raise HarrisCourtBulkSourceChanged(
            "download response filename differs from the selected catalog "
            f"member: {filename!r}"
        )
    if not _expected_magic(artifact, sample):
        raise HarrisCourtBulkSourceChanged(
            f"download response does not match {artifact.format} magic"
        )
    return filename


class HarrisCourtBulkClient:
    """Requests-compatible client for the exact-member ASP.NET catalog."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = TIMEOUT,
        minimum_interval: float = REQUEST_DELAY,
        max_retries: int = MAX_RETRIES,
        sleeper=time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,application/zip,"
                    "application/octet-stream,*/*"
                ),
                "Accept-Language": "en-US,en;q=0.8",
            })
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_retries = max_retries
        self._sleeper = sleeper
        self._last_request_at = 0.0

    def _request(self, method: str, **kwargs: Any) -> Any:
        parsed = urlparse(CATALOG_URL)
        if parsed.scheme != "https" or parsed.hostname != "www.hcdistrictclerk.com":
            raise HarrisCourtBulkError("catalog URL is not the official HTTPS host")
        for attempt in range(self.max_retries + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.minimum_interval:
                self._sleeper(self.minimum_interval - elapsed)
            try:
                self._last_request_at = time.monotonic()
                response = self.session.request(
                    method,
                    CATALOG_URL,
                    timeout=self.timeout,
                    allow_redirects=True,
                    **kwargs,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                raise HarrisCourtBulkTransportError(
                    f"Harris District Clerk request failed: {exc}"
                ) from exc
            status = int(response.status_code)
            if status == 429 or status >= 500:
                if attempt < self.max_retries:
                    if hasattr(response, "close"):
                        response.close()
                    self._sleeper(0.5 * (2**attempt))
                    continue
                if status == 429:
                    raise HarrisCourtBulkRateLimited(
                        "Harris District Clerk rate limited the request"
                    )
            if status < 200 or status >= 300:
                raise HarrisCourtBulkHTTPError(status)
            return response
        raise AssertionError("bounded request loop exhausted")

    def catalog(self) -> CatalogPage:
        response = self._request("GET")
        try:
            return parse_catalog(response.text)
        finally:
            if hasattr(response, "close"):
                response.close()

    def list_artifacts(
        self,
        *,
        section: str | None = None,
        family: str | None = None,
    ) -> list[DatasetArtifact]:
        artifacts = list(self.catalog().artifacts)
        if section:
            artifacts = [
                item
                for item in artifacts
                if item.section.casefold() == section.casefold()
            ]
        if family:
            artifacts = [
                item
                for item in artifacts
                if item.family.casefold() == family.casefold()
            ]
        return artifacts

    def _open_selected(
        self,
        selector: str,
    ) -> tuple[DatasetArtifact, Any, CatalogPage]:
        page = self.catalog()
        artifact = resolve_artifact(page.artifacts, selector)
        data = dict(page.hidden_fields)
        data[DOWNLOAD_LOCATOR_FIELD] = artifact.native_locator
        data[DOWNLOAD_BUTTON_FIELD] = ""
        response = self._request(
            "POST",
            data=data,
            stream=True,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return artifact, response, page

    def inspect(
        self,
        selector: str,
        *,
        sample_bytes: int = DEFAULT_SAMPLE_BYTES,
    ) -> ProbeReceipt:
        if sample_bytes < 4:
            raise HarrisCourtBulkError("--sample-bytes must be at least 4")
        artifact, response, page = self._open_selected(selector)
        sample = bytearray()
        try:
            for chunk in response.iter_content(min(sample_bytes, 64 * 1024)):
                if not chunk:
                    continue
                remaining = sample_bytes - len(sample)
                sample.extend(chunk[:remaining])
                if len(sample) >= sample_bytes:
                    break
            content_disposition = response.headers.get(
                "Content-Disposition"
            )
            response_filename = _validate_download_response(
                artifact,
                content_disposition=content_disposition,
                sample=bytes(sample),
            )
            raw_length = response.headers.get("Content-Length")
            content_length = (
                int(raw_length)
                if raw_length and raw_length.isdigit()
                else None
            )
            return ProbeReceipt(
                artifact=artifact,
                response_url=str(getattr(response, "url", CATALOG_URL)),
                content_type=response.headers.get("Content-Type"),
                content_length=content_length,
                content_disposition=content_disposition,
                response_filename=response_filename,
                sample=bytes(sample),
                catalog_artifacts=page.artifacts,
            )
        finally:
            if hasattr(response, "close"):
                response.close()

    def download(
        self,
        selector: str,
        destination: str | Path,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        artifact, response, _page = self._open_selected(selector)
        destination_path = Path(destination).expanduser()
        if destination_path.exists() and destination_path.is_dir():
            destination_path = destination_path / artifact.native_filename
        elif str(destination).endswith(os.sep):
            destination_path = destination_path / artifact.native_filename
        if destination_path.exists() and not overwrite:
            if hasattr(response, "close"):
                response.close()
            raise OSError(
                f"destination exists; pass --overwrite: {destination_path}"
            )
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        byte_count = 0
        sample = bytearray()
        temporary_path: Path | None = None
        content_disposition = response.headers.get("Content-Disposition")
        content_encoding = response.headers.get("Content-Encoding")
        raw_length = response.headers.get("Content-Length")
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination_path.name}.",
                suffix=".part",
                dir=destination_path.parent,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                for chunk in response.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    if len(sample) < DEFAULT_SAMPLE_BYTES:
                        remaining = DEFAULT_SAMPLE_BYTES - len(sample)
                        sample.extend(chunk[:remaining])
                    handle.write(chunk)
                    digest.update(chunk)
                    byte_count += len(chunk)
            response_filename = _validate_download_response(
                artifact,
                content_disposition=content_disposition,
                sample=bytes(sample),
            )
            if (
                raw_length
                and raw_length.isdigit()
                and (content_encoding or "identity").casefold() == "identity"
                and int(raw_length) != byte_count
            ):
                raise HarrisCourtBulkSourceChanged(
                    "download byte count differs from Content-Length"
                )
            temporary_path.replace(destination_path)
            temporary_path = None
        finally:
            if hasattr(response, "close"):
                response.close()
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return {
            "artifact": artifact,
            "artifact_receipt": {
                "path": str(destination_path.resolve()),
                "size": byte_count,
                "sha256": digest.hexdigest(),
                "content_type": response.headers.get("Content-Type"),
                "content_encoding": content_encoding,
                "content_length_header": (
                    int(raw_length)
                    if raw_length and raw_length.isdigit()
                    else None
                ),
                "content_disposition": content_disposition,
                "response_filename": response_filename,
                "source_url": CATALOG_URL,
            },
        }


def run_sentinel(
    client: HarrisCourtBulkClient | Any | None = None,
) -> dict[str, Any]:
    source_client = client or HarrisCourtBulkClient()
    receipt = source_client.inspect(
        SENTINEL_LOCATOR,
        sample_bytes=DEFAULT_SAMPLE_BYTES,
    )
    artifact = receipt.artifact
    if (
        artifact.filename != SENTINEL_FILENAME
        or artifact.published_date != SENTINEL_PUBLISHED_DATE
        or artifact.section != "Civil"
        or not receipt.sample.startswith(b"PK\x03\x04")
    ):
        raise HarrisCourtBulkSourceChanged(
            "stable field-code sentinel changed"
        )
    if not receipt.catalog_artifacts:
        raise HarrisCourtBulkSourceChanged(
            "sentinel inspection lacks the parsed live catalog"
        )
    return {
        "source": SOURCE,
        "status": "ok",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "catalog_url": CATALOG_URL,
        "sentinel": {
            "native_locator": artifact.native_locator,
            "filename": artifact.filename,
            "published_date": artifact.published_date,
            "format": artifact.format,
            "sample_bytes": len(receipt.sample),
            "signature_hex": receipt.sample[:4].hex(),
            "response_filename": receipt.response_filename,
        },
        "catalog": _catalog_summary(receipt.catalog_artifacts),
    }


def _selector_parameters(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "list":
        text_filter = getattr(args, "text_filter", None) or getattr(
            args,
            "text",
            None,
        )
        published_after = getattr(args, "published_after", None) or getattr(
            args,
            "after",
            None,
        )
        published_before = getattr(args, "published_before", None) or getattr(
            args,
            "before",
            None,
        )
        return {
            key: value
            for key, value in {
                "section": args.section,
                "family": args.family,
                "text_filter": text_filter,
                "published_after": published_after,
                "published_before": published_before,
            }.items()
            if value is not None
        }
    if args.command == "inspect":
        return {
            "artifact": args.artifact,
            "sample_bytes": args.sample_bytes,
        }
    if args.command == "download":
        return {
            "artifact": args.artifact,
            "destination": str(args.destination),
        }
    return {"artifact": SENTINEL_LOCATOR}


def build_query(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    requested_limit = None
    if args.command == "list":
        requested_limit = getattr(args, "result_limit", None)
        if requested_limit is None:
            requested_limit = getattr(args, "limit", None)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_selector_parameters(args),
            requested_limit=requested_limit,
            metadata={"access_decision": dict(access_decision or {})},
        ),
    )


def _filter_list_artifacts(
    artifacts: Sequence[DatasetArtifact],
    args: argparse.Namespace,
) -> list[DatasetArtifact]:
    """Apply equivalent local catalog filters for direct and shared callers."""

    records = list(artifacts)
    text_filter = getattr(args, "text_filter", None) or getattr(
        args,
        "text",
        None,
    )
    if text_filter:
        folded = str(text_filter).casefold()
        records = [
            artifact
            for artifact in records
            if folded
            in " ".join(
                (
                    artifact.filename,
                    artifact.native_locator,
                    artifact.family,
                    artifact.cadence,
                )
            ).casefold()
        ]
    published_after = getattr(args, "published_after", None) or getattr(
        args,
        "after",
        None,
    )
    published_before = getattr(args, "published_before", None) or getattr(
        args,
        "before",
        None,
    )
    if published_after:
        records = [
            artifact
            for artifact in records
            if artifact.published_date >= published_after
        ]
    if published_before:
        records = [
            artifact
            for artifact in records
            if artifact.published_date <= published_before
        ]
    result_limit = getattr(args, "result_limit", None)
    if result_limit is None:
        result_limit = getattr(args, "limit", None)
    if result_limit is not None:
        records = records[: int(result_limit)]
    return records


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE)


def _access_failure(
    args: argparse.Namespace,
    error: AcquisitionUnavailableError | CatalogError | OSError | ValueError,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = dict(error.decision)
        status = ResultStatus(acquisition_result_status(decision))
        code = str(
            decision.get("reason_code") or "machine_acquisition_unavailable"
        )
        message = str(decision.get("reason") or error)
    else:
        decision = {}
        status = ResultStatus.UNAVAILABLE
        code = "catalog_unavailable"
        message = str(error)
    return PublicRecordsResult.failure(
        build_query(args, access_decision=decision),
        status,
        [
            PublicRecordsError(
                code=code,
                message=message,
                category="source_access",
                retryable=False,
                details={"access_decision": decision},
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _source_failure(
    query: PublicRecordsQuery,
    error: HarrisCourtBulkError,
) -> PublicRecordsResult:
    if isinstance(error, HarrisCourtBulkSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_changed"
        category = "source_schema"
        retryable = False
    elif isinstance(error, HarrisCourtBulkRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "source_rate_limited"
        category = "rate_limit"
        retryable = True
    elif isinstance(error, HarrisCourtBulkTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "source_transport_failed"
        category = "transport"
        retryable = True
    elif isinstance(error, HarrisCourtBulkHTTPError):
        status = (
            ResultStatus.SOURCE_CHANGED
            if error.status_code in {404, 410}
            else ResultStatus.UNAVAILABLE
        )
        code = f"source_http_{error.status_code}"
        category = "http"
        retryable = error.status_code >= 500
    else:
        status = ResultStatus.UNAVAILABLE
        code = "invalid_or_rejected_query"
        category = "source_query"
        retryable = False
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category=category,
                retryable=retryable,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: HarrisCourtBulkClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one bulk-catalog operation through the shared result contract."""
    try:
        decision = (
            dict(access_decision)
            if access_decision is not None
            else _access_contract(args)
        )
    except (
        AcquisitionUnavailableError,
        CatalogError,
        OSError,
        ValueError,
    ) as error:
        result = _access_failure(args, error)
        _log(result.query, None)
        return result
    if not decision.get("allowed", False):
        result = _access_failure(
            args,
            AcquisitionUnavailableError(decision),
        )
        _log(result.query, None)
        return result

    query = build_query(args, access_decision=decision)
    source_client = client or HarrisCourtBulkClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
    )
    raw_refs: tuple[str, ...] = ()
    try:
        if args.command == "list":
            artifacts = source_client.list_artifacts(
                section=args.section,
                family=args.family,
            )
            artifacts = _filter_list_artifacts(artifacts, args)
            result = PublicRecordsResult.success(
                query,
                [item.to_record() for item in artifacts],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "inspect":
            receipt = source_client.inspect(
                args.artifact,
                sample_bytes=args.sample_bytes,
            )
            result = PublicRecordsResult.success(
                query,
                [receipt.to_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "download":
            payload = source_client.download(
                args.artifact,
                args.destination,
                overwrite=args.overwrite,
            )
            artifact = payload["artifact"]
            record = artifact.to_record()
            record["artifact_receipt"] = payload["artifact_receipt"]
            raw_refs = (payload["artifact_receipt"]["path"],)
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=raw_refs,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "sentinel":
            sentinel = run_sentinel(source_client)
            result = PublicRecordsResult.success(
                query,
                [{
                    **sentinel,
                    "source_id": SOURCE,
                    "record_kind": "source_health_check",
                    "native_document_id": "live-sentinel",
                }],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise HarrisCourtBulkError(
                f"unsupported command: {args.command}"
            )
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_write_failed",
                    message=str(error),
                    category="local_io",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    except HarrisCourtBulkError as error:
        result = _source_failure(query, error)

    count = (
        len(result.records)
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else None
    )
    _log(query, count)
    return result


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE, count)
    except Exception as exc:
        print(f"Warning: could not log search: {exc}", file=sys.stderr)


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Harris court bulk {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Harris court bulk {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "bulk_dataset_artifact":
            print(
                f"- {record['section']} | {record['published_date']} | "
                f"{record['filename']} | {record['native_locator']}"
            )
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=REQUEST_DELAY,
    )
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
    )
    add_output_args(parser)


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"expected YYYY-MM-DD, got {value!r}"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover and retrieve Harris District Clerk bulk datasets"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list")
    listing.add_argument("--section", choices=("Civil", "Criminal"))
    listing.add_argument("--family")
    listing.add_argument(
        "--text",
        "--text-filter",
        dest="text",
        help="Filter filename, catalog path, family, or cadence locally",
    )
    listing.add_argument(
        "--after",
        "--published-after",
        dest="after",
        type=_iso_date,
        help="Keep artifacts published on or after YYYY-MM-DD",
    )
    listing.add_argument(
        "--before",
        "--published-before",
        dest="before",
        type=_iso_date,
        help="Keep artifacts published on or before YYYY-MM-DD",
    )
    listing.add_argument(
        "--limit",
        "--result-limit",
        dest="limit",
        type=int,
        help="Optional caller-selected result limit after full catalog parse",
    )
    _add_runtime_args(listing)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("artifact")
    inspect.add_argument(
        "--sample-bytes",
        type=int,
        default=DEFAULT_SAMPLE_BYTES,
    )
    _add_runtime_args(inspect)

    download = subparsers.add_parser("download")
    download.add_argument("artifact")
    download.add_argument("--destination", type=Path, required=True)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_args(download)

    sentinel = subparsers.add_parser("sentinel")
    _add_runtime_args(sentinel)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0 or args.minimum_interval < 0:
        parser.error(
            "--timeout must be positive and --minimum-interval non-negative"
        )
    if getattr(args, "sample_bytes", DEFAULT_SAMPLE_BYTES) < 4:
        parser.error("--sample-bytes must be at least 4")
    if args.command == "list":
        if args.limit is not None and args.limit <= 0:
            parser.error("--limit must be positive")
        if args.after and args.before and args.after > args.before:
            parser.error("--after must not be later than --before")
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
