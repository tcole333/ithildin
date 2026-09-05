#!/usr/bin/env python3
"""Query Deschutes County CDD documents in Laserfiche WebLink.

The official DIAL account page is the anonymous discovery index for this
repository.  It links a Deschutes property account and map/taxlot to one or
more Laserfiche entry IDs.  WebLink then provides document/template metadata,
parent-folder metadata, and two source-native document representations:

* recent electronic files through ``ElectronicFile.aspx``; and
* older imaged documents through WebLink's PDF generation workflow.

Property-account and taxlot values are joins.  The Laserfiche entry ID remains
the native document identity.

Examples:
    uv run python tools/query_deschutes_laserfiche.py sources
    uv run python tools/query_deschutes_laserfiche.py account 135278 \
        --output /tmp/deschutes-cdd-documents.json
    uv run python tools/query_deschutes_laserfiche.py document 1383062 \
        --account 135278 --output /tmp/deschutes-cdd-document.json
    uv run python tools/query_deschutes_laserfiche.py folder 1378494 \
        --output /tmp/deschutes-cdd-folder.json
    uv run python tools/query_deschutes_laserfiche.py download 333623 \
        --account 135278 --destination /tmp/deschutes-cdd-333623.pdf \
        --output /tmp/deschutes-cdd-download.json
    uv run python tools/query_deschutes_laserfiche.py probe \
        --output /tmp/deschutes-cdd-probe.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

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
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
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
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-or-deschutes-cdd-weblink"
SOURCE_NAME = "Deschutes County CDD Laserfiche WebLink"
PUBLISHER = "Deschutes County Community Development Department"
COUNTY_NAME = "Deschutes County, Oregon"
COUNTY_GEOID = "41017"
STATE_CODE = "OR"
STATE_FIPS = "41"

DIAL_SOURCE_ID = "us-or-deschutes-dial-property"
TAXLOT_SOURCE_ID = "us-or-deschutes-county-taxlots"
OREGON_EPERMITTING_COMPLEMENT_KEY = "official_oregon_epermitting_portal"

DIAL_BASE_URL = "http://dial.deschutes.org"
DIAL_DOCUMENT_ROUTE = "/Real/DevelopmentDocs/{account_id}"
BASE_URL = "https://weblink.deschutes.org/CDD/"
VIEWER_URL = f"{BASE_URL}DocView.aspx"
MY_WEBLINK_URL = f"{BASE_URL}MyWebLink.aspx"
DOCUMENT_INFO_URL = f"{BASE_URL}DocumentService.aspx/GetBasicDocumentInfo"
FOLDER_METADATA_URL = f"{BASE_URL}FolderListingService.aspx/GetMetaData"
GENERATE_PDF_URL = f"{BASE_URL}GeneratePDF10.aspx"
PDF_PROGRESS_URL = f"{BASE_URL}DocumentService.aspx/PDFTransition"

REPOSITORY_NAME = "LFCDD"
DATABASE_ID = 0
CURSOR_PREFIX = "deschutes-cdd-weblink:v1:"
CURSOR_VERSION = 1
ACCOUNT_SORT = "date_uploaded_desc_document_type_asc_document_id_asc"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.3
DEFAULT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_DOCUMENT_BYTES = 256 * 1024 * 1024
DEFAULT_LIMIT = 100
DEFAULT_POLL_ATTEMPTS = 60
DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_USER_AGENT = "IthildinOSINT/1.0 (public-record research)"

PROBE_ACCOUNT_ID = "135278"
PROBE_TAXLOT = "141031B000700"
PROBE_ELECTRONIC_DOCUMENT_ID = "1383062"
PROBE_IMAGED_DOCUMENT_ID = "333623"
PROBE_PARENT_FOLDER_ID = "1378494"

ACCOUNT_HEADERS = (
    "date_uploaded",
    "document_type",
    "description",
    "file_number",
    "",
)
WEBLINK_TIMEZONE = ZoneInfo("America/Los_Angeles")
OFFICIAL_HOSTS = {
    "dial.deschutes.org": frozenset({"http", "https"}),
    "weblink.deschutes.org": frozenset({"https"}),
}


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role=(
        "official_county_planning_permit_septic_zoning_and_development_documents"
    ),
    base_url=BASE_URL,
    dataset_id="deschutes-cdd-laserfiche-lfcdd",
    metadata={
        "publisher": PUBLISHER,
        "county_geoid": COUNTY_GEOID,
        "platform_family": "laserfiche_weblink_11",
        "repository_name": REPOSITORY_NAME,
        "database_id": DATABASE_ID,
        "native_identity_key": "laserfiche_entry_id",
        "property_join_keys": ["deschutes_dial_account_id", "map_taxlot"],
        "access_observation": {
            "account_discovery": "anonymous_dial_html_table",
            "document_metadata": "anonymous_cookie_session_json",
            "folder_metadata": "anonymous_cookie_session_json",
            "electronic_files": "anonymous_cookie_session_native_file",
            "imaged_documents": "anonymous_cookie_session_generated_pdf",
            "repository_search": "not_granted_to_public_weblink_identity",
            "repository_browse": "not_exposed_by_viewer",
            "observed_at": "2026-07-29",
        },
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Deschutes County",
    metadata={"state_fips": STATE_FIPS},
)


@dataclass(frozen=True)
class FetchedBody:
    body: bytes
    source_url: str
    media_type: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class ViewerContract:
    source_url: str
    repository_name: str
    virtual_directory: str
    has_search_rights: bool
    has_export_rights: bool
    has_print_rights_hint: bool
    show_browse_link: bool
    show_search_link: bool
    raw_capabilities: Mapping[str, Any]
    schema_fingerprint: str


@dataclass(frozen=True)
class AccountDocumentPage:
    account_id: str
    map_taxlot: str | None
    mailing_name: str | None
    situs_address: str | None
    tax_status: str | None
    records: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str
    snapshot_fingerprint: str


@dataclass(frozen=True)
class BinaryArtifact:
    content: bytes
    source_url: str
    media_type: str
    filename: str | None
    retrieval_mode: str
    generation_token: str | None
    etag: str | None
    last_modified: str | None


class WebLinkSelectionError(ValueError):
    """A selector or continuation does not match this source contract."""

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
            category="selection",
            details=self.details,
        )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "get_text"):
        value = value.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    return text or None


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (_clean(value) or "").casefold()).strip("_")


def _integer(value: Any) -> int | None:
    text = _clean(value)
    if text is None or not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def _document_id(value: Any) -> str:
    text = _clean(value)
    if text is None or not re.fullmatch(r"[1-9]\d*", text):
        raise WebLinkSelectionError(
            "invalid_document_id",
            "Laserfiche document ID must be a positive decimal entry ID",
        )
    return text


def _folder_id(value: Any) -> str:
    text = _clean(value)
    if text is None or not re.fullmatch(r"[1-9]\d*", text):
        raise WebLinkSelectionError(
            "invalid_folder_id",
            "Laserfiche folder ID must be a positive decimal entry ID",
        )
    return text


def _account_id(value: Any) -> str:
    text = _clean(value)
    if text is None or not re.fullmatch(r"[A-Za-z0-9._-]+", text):
        raise WebLinkSelectionError(
            "invalid_account_id",
            "DIAL account ID contains unsupported path characters",
        )
    return text


def _normalize_taxlot(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    return normalized or None


def _source_date(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    for source_format in ("%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(text, source_format).date().isoformat()
        except ValueError:
            continue
    return None


def _source_datetime(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    for source_format in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, source_format).replace(
                tzinfo=WEBLINK_TIMEZONE
            )
            return parsed.isoformat()
        except ValueError:
            continue
    return None


def _official_url(path_or_url: str, *, base_url: str = BASE_URL) -> str:
    absolute = urljoin(base_url, path_or_url)
    parsed = urlparse(absolute)
    schemes = OFFICIAL_HOSTS.get((parsed.hostname or "").casefold())
    port_matches_scheme = (
        parsed.port in {None, 443}
        if parsed.scheme.casefold() == "https"
        else parsed.port in {None, 80}
    )
    if (
        schemes is None
        or parsed.scheme.casefold() not in schemes
        or parsed.username is not None
        or parsed.password is not None
        or not port_matches_scheme
    ):
        raise WebLinkSelectionError(
            "unexpected_source_url",
            "Deschutes document request left the verified official hosts",
            details={"url": absolute},
        )
    return absolute


def _viewer_url(document_id: str) -> str:
    return f"{VIEWER_URL}?id={quote(_document_id(document_id), safe='')}"


def _dial_account_url(account_id: str) -> str:
    return urljoin(
        DIAL_BASE_URL,
        DIAL_DOCUMENT_ROUTE.format(
            account_id=quote(_account_id(account_id), safe="._-")
        ),
    )


def _response_url(response: Any, fallback: str) -> str:
    return str(getattr(response, "url", None) or fallback)


def _response_headers(response: Any) -> dict[str, str]:
    headers = getattr(response, "headers", {}) or {}
    return {str(key): str(value) for key, value in dict(headers).items()}


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    target = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == target:
            return _clean(value)
    return None


def _retry_after(response: Any) -> float | None:
    value = _header(_response_headers(response), "retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _bounded_response(
    response: Any,
    *,
    maximum_bytes: int,
    request_url: str,
) -> FetchedBody:
    if maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be positive")
    headers = _response_headers(response)
    source_url = _official_url(_response_url(response, request_url))
    declared_length = _integer(_header(headers, "content-length"))
    if declared_length is not None and declared_length > maximum_bytes:
        response.close()
        raise SourceResponseError(
            "Deschutes WebLink response exceeds the requested byte bound",
            url=source_url,
            details={
                "content_length": declared_length,
                "maximum_bytes": maximum_bytes,
            },
        )
    chunks: list[bytes] = []
    observed_bytes = 0
    try:
        iterator = getattr(response, "iter_content", None)
        if callable(iterator):
            for chunk in iterator(chunk_size=64 * 1024):
                if not chunk:
                    continue
                value = bytes(chunk)
                observed_bytes += len(value)
                if observed_bytes > maximum_bytes:
                    raise SourceResponseError(
                        "Deschutes WebLink response exceeded the requested byte bound",
                        url=source_url,
                        details={
                            "observed_bytes": observed_bytes,
                            "maximum_bytes": maximum_bytes,
                        },
                    )
                chunks.append(value)
            body = b"".join(chunks)
        else:
            value = getattr(response, "content", b"")
            if isinstance(value, str):
                body = value.encode("utf-8")
            else:
                body = bytes(value)
            if len(body) > maximum_bytes:
                raise SourceResponseError(
                    "Deschutes WebLink response exceeded the requested byte bound",
                    url=source_url,
                    details={
                        "observed_bytes": len(body),
                        "maximum_bytes": maximum_bytes,
                    },
                )
    finally:
        response.close()
    media_type = (_header(headers, "content-type") or "").split(";", 1)[0].strip()
    return FetchedBody(
        body=body,
        source_url=source_url,
        media_type=media_type,
        headers=headers,
    )


def _decode_text(body: FetchedBody) -> str:
    charset_match = re.search(
        r"charset\s*=\s*([A-Za-z0-9._-]+)",
        _header(body.headers, "content-type") or "",
        flags=re.I,
    )
    encoding = charset_match.group(1) if charset_match else "utf-8"
    return body.body.decode(encoding, errors="replace")


def _json_body(body: FetchedBody, *, representation: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(_decode_text(body))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SourceSchemaError(
            f"Deschutes WebLink {representation} response is not JSON",
            url=body.source_url,
            details={"content_type": body.media_type},
        ) from error
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            f"Deschutes WebLink {representation} response is not an object",
            url=body.source_url,
        )
    source_error = payload.get("error")
    if source_error:
        raise SourceResponseError(
            f"Deschutes WebLink {representation} returned a source error",
            url=body.source_url,
            details={"source_error": source_error},
        )
    return payload


def _labeled_values(block: Tag) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for strong in block.find_all("strong"):
        label = _slug(strong)
        parts: list[str] = []
        for sibling in strong.next_siblings:
            if isinstance(sibling, Tag) and sibling.name.casefold() == "br":
                break
            if isinstance(sibling, (Tag, NavigableString)):
                text = _clean(sibling)
                if text:
                    parts.append(text)
        values[label] = _clean(" ".join(parts))
    return values


def _document_sort_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    date_value = str(record.get("date_uploaded") or "0000-00-00")
    date_number = int(date_value.replace("-", "")) if date_value[:4].isdigit() else 0
    document_id = _integer(record.get("laserfiche_entry_id")) or 0
    return (
        -date_number,
        str(record.get("document_type") or "").casefold(),
        document_id,
    )


def parse_account_documents_page(
    html: str,
    source_url: str,
    *,
    expected_account_id: str | None = None,
) -> AccountDocumentPage:
    """Parse the DIAL account-level discovery table into WebLink references."""

    official_source_url = _official_url(source_url, base_url=DIAL_BASE_URL)
    soup = BeautifulSoup(html, "lxml")
    account_block = soup.select_one(".uxAccountInformation")
    if not isinstance(account_block, Tag):
        raise SourceSchemaError(
            "Deschutes DIAL account information is missing",
            url=official_source_url,
        )
    fields = _labeled_values(account_block)
    account_id = _clean(fields.get("account"))
    if account_id is None:
        raise SourceSchemaError(
            "Deschutes DIAL development-documents page has no account ID",
            url=official_source_url,
        )
    if expected_account_id is not None and account_id != _account_id(
        expected_account_id
    ):
        raise SourceSchemaError(
            "Deschutes DIAL returned a different property account",
            url=official_source_url,
            details={
                "expected_account_id": expected_account_id,
                "observed_account_id": account_id,
            },
        )
    map_taxlot = _normalize_taxlot(fields.get("map_and_taxlot"))

    table: Tag | None = None
    header_slugs: tuple[str, ...] = ()
    for candidate in soup.find_all("table"):
        observed = tuple(
            _slug(cell) for cell in candidate.select("thead th")
        )
        if observed == ACCOUNT_HEADERS:
            table = candidate
            header_slugs = observed
            break
    if table is None:
        raise SourceSchemaError(
            "Deschutes DIAL development-document table schema changed",
            url=official_source_url,
            details={
                "observed_tables": [
                    [_slug(cell) for cell in candidate.select("thead th")]
                    for candidate in soup.find_all("table")
                ]
            },
        )

    by_document: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(table.select("tr"), start=1):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != 5:
            raise SourceSchemaError(
                "Deschutes DIAL development-document row width changed",
                url=official_source_url,
                details={"row_index": row_index, "cell_count": len(cells)},
            )
        link = cells[4].find("a", href=True)
        if not isinstance(link, Tag):
            raise SourceSchemaError(
                "Deschutes DIAL development-document link is missing",
                url=official_source_url,
                details={"row_index": row_index},
            )
        viewer_url = _official_url(
            str(link.get("href")),
            base_url=official_source_url,
        )
        parsed = urlparse(viewer_url)
        query = parse_qs(parsed.query)
        if (
            parsed.hostname != "weblink.deschutes.org"
            or parsed.path.casefold() != "/cdd/docview.aspx"
            or len(query.get("id", [])) != 1
        ):
            raise SourceSchemaError(
                "Deschutes DIAL development-document viewer route changed",
                url=official_source_url,
                details={"viewer_url": viewer_url, "row_index": row_index},
            )
        document_id = _document_id(query["id"][0])
        occurrence = {
            "date_uploaded": _source_date(cells[0]),
            "date_uploaded_raw": _clean(cells[0]),
            "document_type": _clean(cells[1]),
            "description": _clean(cells[2]),
            "file_number": _clean(cells[3]),
            "source_row": row_index,
        }
        existing = by_document.get(document_id)
        if existing is not None:
            existing["dial_index_occurrences"].append(occurrence)
            continue
        canonical_ref = canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "document",
            document_id,
        )
        by_document[document_id] = {
            "source_id": SOURCE_ID,
            "source_name": SOURCE_NAME,
            "source_url": viewer_url,
            "record_kind": "development_document_reference",
            "canonical_ref": canonical_ref,
            "evidence_ref": canonical_ref,
            "access_state": "public_anonymous_cookie_session",
            "native_document_id": document_id,
            "laserfiche_entry_id": document_id,
            "viewer_url": viewer_url,
            "metadata_endpoint": DOCUMENT_INFO_URL,
            "deschutes_dial_account_id": account_id,
            "map_taxlot": map_taxlot,
            "property_identifiers": {
                "deschutes_dial_account_id": account_id,
                "map_taxlot": map_taxlot,
            },
            "document_identifiers": {
                "laserfiche_entry_id": document_id,
            },
            **occurrence,
            "dial_index_occurrences": [occurrence],
            "discovery_source_id": DIAL_SOURCE_ID,
            "discovery_source_url": official_source_url,
            "retrieval_state": "viewer_and_metadata_route_available",
            "join_candidates": {
                DIAL_SOURCE_ID: {
                    "account_id": account_id,
                    "map_taxlot": map_taxlot,
                    "relationship": "account_document_index",
                },
                TAXLOT_SOURCE_ID: {
                    "map_taxlot": map_taxlot,
                    "relationship": "parcel_geometry_and_assessment_complement",
                },
            },
            "provenance": [
                {
                    "component": "dial_account_document_index",
                    "source_id": DIAL_SOURCE_ID,
                    "source_url": official_source_url,
                },
                {
                    "component": "laserfiche_document_viewer",
                    "source_id": SOURCE_ID,
                    "source_url": viewer_url,
                },
            ],
        }

    for record in by_document.values():
        occurrences = sorted(
            record["dial_index_occurrences"],
            key=lambda occurrence: (
                -int(
                    str(occurrence.get("date_uploaded") or "0000-00-00").replace(
                        "-", ""
                    )
                ),
                str(occurrence.get("document_type") or "").casefold(),
                str(occurrence.get("description") or "").casefold(),
                str(occurrence.get("file_number") or "").casefold(),
                int(occurrence.get("source_row") or 0),
            ),
        )
        record["dial_index_occurrences"] = occurrences
        for key in (
            "date_uploaded",
            "date_uploaded_raw",
            "document_type",
            "description",
            "file_number",
            "source_row",
        ):
            record[key] = occurrences[0].get(key)
    records = tuple(sorted(by_document.values(), key=_document_sort_key))
    shape = {
        "headers": header_slugs,
        "account_labels": sorted(fields),
        "viewer_host": "weblink.deschutes.org",
        "viewer_path": "/cdd/docview.aspx",
    }
    snapshot = [
        {
            "laserfiche_entry_id": record["laserfiche_entry_id"],
            "date_uploaded": record["date_uploaded"],
            "document_type": record["document_type"],
            "description": record["description"],
            "file_number": record["file_number"],
            "occurrences": record["dial_index_occurrences"],
        }
        for record in records
    ]
    return AccountDocumentPage(
        account_id=account_id,
        map_taxlot=map_taxlot,
        mailing_name=_clean(fields.get("mailing_name")),
        situs_address=_clean(fields.get("situs_address")),
        tax_status=_clean(fields.get("tax_status")),
        records=records,
        source_url=official_source_url,
        schema_fingerprint=schema_fingerprint(shape),
        snapshot_fingerprint=sha256_fingerprint(snapshot),
    )


def parse_viewer_contract(html: str, source_url: str) -> ViewerContract:
    official_source_url = _official_url(source_url)
    if "Cookies are not enabled for this website" in html:
        raise SourceSchemaError(
            "Deschutes WebLink cookie handshake did not complete",
            url=official_source_url,
        )
    if "<doc-viewer-app" not in html:
        raise SourceSchemaError(
            "Deschutes WebLink document viewer shell changed",
            url=official_source_url,
        )
    match = re.search(r"run\(\{\s*str_json\s*:\s*", html, flags=re.DOTALL)
    if match is None:
        raise SourceSchemaError(
            "Deschutes WebLink viewer capabilities are missing",
            url=official_source_url,
        )
    try:
        capabilities, _ = json.JSONDecoder().raw_decode(html[match.end() :])
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise SourceSchemaError(
            "Deschutes WebLink viewer capabilities are not JSON",
            url=official_source_url,
        ) from error
    if not isinstance(capabilities, Mapping):
        raise SourceSchemaError(
            "Deschutes WebLink viewer capabilities changed type",
            url=official_source_url,
        )
    repository_name = _clean(capabilities.get("repoName"))
    virtual_directory = _clean(capabilities.get("vdirName"))
    if repository_name != REPOSITORY_NAME or (
        virtual_directory or ""
    ).casefold() != "cdd":
        raise SourceSchemaError(
            "Deschutes WebLink viewer repository identity changed",
            url=official_source_url,
            details={
                "repository_name": repository_name,
                "virtual_directory": virtual_directory,
            },
        )
    shape = {
        "capability_keys": sorted(str(key) for key in capabilities),
        "repository_name": repository_name,
        "virtual_directory": virtual_directory,
    }
    return ViewerContract(
        source_url=official_source_url,
        repository_name=repository_name,
        virtual_directory=virtual_directory or "CDD",
        has_search_rights=bool(capabilities.get("hasSearchRights")),
        has_export_rights=bool(capabilities.get("hasExportRights")),
        has_print_rights_hint=bool(capabilities.get("hasPrintRights", True)),
        show_browse_link=bool(capabilities.get("showBrowseLink")),
        show_search_link=bool(capabilities.get("showSearchLink")),
        raw_capabilities=dict(capabilities),
        schema_fingerprint=schema_fingerprint(shape),
    )


def _template_fields(
    metadata: Mapping[str, Any],
    *,
    source_url: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_fields = metadata.get("fInfo")
    if raw_fields is None:
        raw_fields = []
    if not isinstance(raw_fields, list):
        raise SourceSchemaError(
            "Deschutes WebLink template fields changed type",
            url=source_url,
        )
    fields: list[dict[str, Any]] = []
    values_by_name: dict[str, Any] = {}
    for index, raw in enumerate(raw_fields):
        if not isinstance(raw, Mapping):
            raise SourceSchemaError(
                "Deschutes WebLink template field is not an object",
                url=source_url,
                details={"field_index": index},
            )
        name = _clean(raw.get("name"))
        values = raw.get("values")
        if name is None or not isinstance(values, list):
            raise SourceSchemaError(
                "Deschutes WebLink template field schema changed",
                url=source_url,
                details={"field_index": index},
            )
        clean_values = [
            cleaned
            for value in values
            if (cleaned := _clean(value)) is not None
        ]
        field = {
            "name": name,
            "values": clean_values,
            "is_multi_value_group": bool(raw.get("isMvfg")),
        }
        fields.append(field)
        if name in values_by_name:
            previous = values_by_name[name]
            if not isinstance(previous, list):
                previous = [previous]
            values_by_name[name] = [*previous, *clean_values]
        elif len(clean_values) == 1:
            values_by_name[name] = clean_values[0]
        else:
            values_by_name[name] = clean_values
    return fields, values_by_name


def _field_value(values: Mapping[str, Any], name: str) -> str | None:
    value = values.get(name)
    if isinstance(value, list):
        return _clean(value[0]) if value else None
    return _clean(value)


def _metadata_common(
    metadata: Mapping[str, Any],
    *,
    source_url: str,
) -> dict[str, Any]:
    fields, values = _template_fields(metadata, source_url=source_url)
    return {
        "template_name": _clean(metadata.get("templateName")),
        "created_at": _source_datetime(metadata.get("created")),
        "created_at_raw": _clean(metadata.get("created")),
        "modified_at": _source_datetime(metadata.get("modified")),
        "modified_at_raw": _clean(metadata.get("modified")),
        "laserfiche_path": _clean(metadata.get("path")),
        "tag_ids": list(metadata.get("tagIds") or []),
        "template_fields": fields,
        "template_field_values": values,
        "link_group": metadata.get("linkGroup"),
        "document_relationships": list(metadata.get("documentRelationships") or []),
    }


def parse_document_info(
    payload: Mapping[str, Any],
    source_url: str,
    *,
    expected_document_id: str,
    viewer_contract: ViewerContract | None = None,
) -> dict[str, Any]:
    """Normalize one WebLink ``GetBasicDocumentInfo`` response."""

    official_source_url = _official_url(source_url)
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise SourceSchemaError(
            "Deschutes WebLink document metadata has no data object",
            url=official_source_url,
        )
    document_id = _document_id(data.get("id"))
    expected_id = _document_id(expected_document_id)
    if document_id != expected_id:
        raise SourceSchemaError(
            "Deschutes WebLink returned a different document entry",
            url=official_source_url,
            details={
                "expected_document_id": expected_id,
                "observed_document_id": document_id,
            },
        )
    metadata = data.get("metadata")
    if not isinstance(metadata, Mapping):
        raise SourceSchemaError(
            "Deschutes WebLink document metadata object is missing",
            url=official_source_url,
        )
    metadata_error = metadata.get("err")
    if metadata_error:
        raise SourceResponseError(
            "Deschutes WebLink document metadata reports an error",
            url=official_source_url,
            details={"source_error": metadata_error},
        )
    common = _metadata_common(metadata, source_url=official_source_url)
    page_count = _integer(data.get("pageCount"))
    if page_count is None or page_count < 0:
        raise SourceSchemaError(
            "Deschutes WebLink document page count changed type",
            url=official_source_url,
        )
    parent_folder_id = _folder_id(data.get("parentId"))
    edoc_url_raw = _clean(data.get("edocUrl"))
    electronic_file_url: str | None = None
    if edoc_url_raw:
        electronic_file_url = _official_url(edoc_url_raw)
        parsed_edoc = urlparse(electronic_file_url)
        edoc_query = parse_qs(parsed_edoc.query)
        if (
            parsed_edoc.path.casefold() != "/cdd/electronicfile.aspx"
            or (edoc_query.get("docid") or [None])[0] != document_id
        ):
            raise SourceSchemaError(
                "Deschutes WebLink electronic-file route changed",
                url=official_source_url,
                details={"electronic_file_url": electronic_file_url},
            )
    has_imaged_pages = bool(data.get("hasImagedPages"))
    if electronic_file_url:
        retrieval_mode = "electronic_file"
        retrieval_state = "document_download_available"
    elif page_count > 0 and has_imaged_pages:
        retrieval_mode = "generated_pdf_from_imaged_pages"
        retrieval_state = "document_download_available"
    elif page_count > 0:
        retrieval_mode = "generated_pdf_from_pages"
        retrieval_state = "document_download_available"
    else:
        retrieval_mode = "metadata_only"
        retrieval_state = "no_document_representation_observed"

    field_values = common["template_field_values"]
    taxlot = _normalize_taxlot(_field_value(field_values, "Tax Lot"))
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "document",
        document_id,
    )
    viewer_url = _viewer_url(document_id)
    shape = {
        "data_keys": sorted(str(key) for key in data),
        "metadata_keys": sorted(str(key) for key in metadata),
        "template_field_names": [
            field["name"] for field in common["template_fields"]
        ],
        "representation": {
            "has_edoc_url": bool(electronic_file_url),
            "has_imaged_pages": has_imaged_pages,
            "page_count_positive": page_count > 0,
        },
    }
    viewer = None
    if viewer_contract is not None:
        viewer = {
            "source_url": viewer_contract.source_url,
            "repository_name": viewer_contract.repository_name,
            "virtual_directory": viewer_contract.virtual_directory,
            "has_search_rights": viewer_contract.has_search_rights,
            "has_export_rights": viewer_contract.has_export_rights,
            "has_print_rights_hint": viewer_contract.has_print_rights_hint,
            "show_browse_link": viewer_contract.show_browse_link,
            "show_search_link": viewer_contract.show_search_link,
            "schema_fingerprint": viewer_contract.schema_fingerprint,
        }
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": viewer_url,
        "record_kind": "laserfiche_development_document",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "access_state": "public_anonymous_cookie_session",
        "native_document_id": document_id,
        "laserfiche_entry_id": document_id,
        "document_identifiers": {"laserfiche_entry_id": document_id},
        "name": _clean(data.get("name")),
        "extension": _clean(data.get("extension")),
        "page_count": page_count,
        "has_imaged_pages": has_imaged_pages,
        "parent_folder_id": parent_folder_id,
        "target_type": data.get("targetType"),
        "link_to_entry_id": data.get("linkTo"),
        "icon_class": _clean(data.get("iconClass")),
        **common,
        "map_taxlot": taxlot,
        "property_identifiers": {"map_taxlot": taxlot},
        "description": _field_value(field_values, "Description"),
        "document_category": _field_value(field_values, "Document Category"),
        "case_number": _field_value(field_values, "Case Number"),
        "group": _field_value(field_values, "Group"),
        "barcode": _field_value(field_values, "Barcode"),
        "division": _field_value(field_values, "Division"),
        "accela_document_id": _field_value(field_values, "Accela Doc ID"),
        "accela_upload_at": _source_datetime(
            _field_value(field_values, "Accela Upload Date")
        ),
        "accela_upload_at_raw": _field_value(field_values, "Accela Upload Date"),
        "accela_file_name": _field_value(field_values, "Accela File Name"),
        "viewer_url": viewer_url,
        "metadata_endpoint": official_source_url,
        "electronic_file_url": electronic_file_url,
        "generated_pdf_route": (
            f"{BASE_URL}PDF10/{{generation_token}}/{document_id}"
            if page_count > 0
            else None
        ),
        "retrieval_mode": retrieval_mode,
        "retrieval_state": retrieval_state,
        "viewer_contract": viewer,
        "source_response_schema_fingerprint": schema_fingerprint(shape),
        "source_data_fingerprint": sha256_fingerprint(data),
        "join_candidates": {
            DIAL_SOURCE_ID: {
                "map_taxlot": taxlot,
                "relationship": "account_document_discovery_and_property_context",
            },
            TAXLOT_SOURCE_ID: {
                "map_taxlot": taxlot,
                "relationship": "parcel_geometry_and_assessment_complement",
            },
            OREGON_EPERMITTING_COMPLEMENT_KEY: {
                "record_id": _field_value(field_values, "Case Number"),
                "accela_document_id": _field_value(field_values, "Accela Doc ID"),
                "relationship": "current_permit_status_and_applicant_document_complement",
            },
        },
        "provenance": [
            {
                "component": "laserfiche_document_viewer",
                "source_id": SOURCE_ID,
                "source_url": viewer_url,
            },
            {
                "component": "laserfiche_document_service",
                "source_id": SOURCE_ID,
                "source_url": official_source_url,
            },
        ],
    }


def parse_folder_metadata(
    payload: Mapping[str, Any],
    source_url: str,
    *,
    folder_id: str,
) -> dict[str, Any]:
    official_source_url = _official_url(source_url)
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise SourceSchemaError(
            "Deschutes WebLink folder metadata has no data object",
            url=official_source_url,
        )
    if data.get("err"):
        raise SourceResponseError(
            "Deschutes WebLink folder metadata reports an error",
            url=official_source_url,
            details={"source_error": data.get("err")},
        )
    normalized_folder_id = _folder_id(folder_id)
    common = _metadata_common(data, source_url=official_source_url)
    folder_path = _clean(common.get("laserfiche_path"))
    if folder_path is None:
        raise SourceSchemaError(
            "Deschutes WebLink folder path is missing",
            url=official_source_url,
        )
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "folder",
        normalized_folder_id,
    )
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": official_source_url,
        "record_kind": "laserfiche_folder_metadata",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "access_state": "public_anonymous_cookie_session",
        "native_folder_id": normalized_folder_id,
        "laserfiche_folder_id": normalized_folder_id,
        "folder_name": folder_path.rstrip("\\").rsplit("\\", 1)[-1],
        **common,
        "metadata_endpoint": official_source_url,
        "source_response_schema_fingerprint": schema_fingerprint(
            {
                "metadata_keys": sorted(str(key) for key in data),
                "template_field_names": [
                    field["name"] for field in common["template_fields"]
                ],
            }
        ),
        "source_data_fingerprint": sha256_fingerprint(data),
    }


def _filename_from_headers(headers: Mapping[str, Any]) -> str | None:
    disposition = _header(headers, "content-disposition")
    if disposition is None:
        return None
    encoded = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", disposition, flags=re.I)
    if encoded:
        return _clean(unquote(encoded.group(1)))
    plain = re.search(r'filename\s*=\s*"([^"]+)"', disposition, flags=re.I)
    if plain:
        return _clean(plain.group(1))
    plain = re.search(r"filename\s*=\s*([^;]+)", disposition, flags=re.I)
    return _clean(plain.group(1)) if plain else None


class DeschutesWebLinkClient:
    """Bounded, retrying client that preserves the anonymous WebLink session."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: MinimumIntervalRateLimiter | Any | None = None,
        maximum_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if maximum_response_bytes <= 0:
            raise ValueError("maximum_response_bytes must be positive")
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.rate_limiter = rate_limiter or MinimumIntervalRateLimiter(
            DEFAULT_MINIMUM_INTERVAL,
            sleeper=sleeper,
        )
        self.maximum_response_bytes = maximum_response_bytes
        self.sleeper = sleeper
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.8",
        }
        self._session_warmed = False
        self._viewer_contracts: dict[str, ViewerContract] = {}

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        accept: str,
    ) -> Any:
        official_url = _official_url(url)
        request_headers = {**self.headers, "Accept": accept}
        if json_body is not None:
            request_headers.update(
                {
                    "Content-Type": "application/json",
                    "X-Lf-Suppress-Login-Redirect": "1",
                }
            )
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    official_url,
                    params=dict(params or {}),
                    json=dict(json_body) if json_body is not None else None,
                    headers=request_headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True,
                )
            except (requests.RequestException, OSError, RuntimeError) as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                break
            for redirect in [*getattr(response, "history", ()), response]:
                _official_url(_response_url(redirect, official_url))
            status = int(getattr(response, "status_code", 0))
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                retry_after = _retry_after(response)
                response.close()
                self.sleeper(self.retry_policy.delay(attempt, retry_after))
                continue
            if status == 429:
                response.close()
                raise RateLimitedHTTPError(status, url=official_url)
            if status in {401, 403}:
                response.close()
                raise RestrictedHTTPError(status, url=official_url)
            if status in {404, 410}:
                response.close()
                raise SourceChangedHTTPError(status, url=official_url)
            if status < 200 or status >= 300:
                response_body = _bounded_response(
                    response,
                    maximum_bytes=min(self.maximum_response_bytes, 64 * 1024),
                    request_url=official_url,
                )
                raise HTTPStatusError(
                    status,
                    url=response_body.source_url,
                    response_text=_decode_text(response_body),
                )
            return response
        raise TransportError(
            "Deschutes CDD WebLink request failed",
            url=official_url,
            details={"error": str(last_error or "retry attempts exhausted")},
        )

    def _get_text(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[str, FetchedBody]:
        response = self._request(
            "GET",
            url,
            params=params,
            accept="text/html,application/xhtml+xml",
        )
        body = _bounded_response(
            response,
            maximum_bytes=self.maximum_response_bytes,
            request_url=url,
        )
        if body.media_type and "html" not in body.media_type.casefold():
            raise SourceSchemaError(
                "Deschutes document index returned non-HTML content",
                url=body.source_url,
                details={"content_type": body.media_type},
            )
        return _decode_text(body), body

    def _post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        *,
        representation: str,
    ) -> tuple[Mapping[str, Any], FetchedBody]:
        response = self._request(
            "POST",
            url,
            json_body=payload,
            accept="application/json,text/json,*/*;q=0.8",
        )
        body = _bounded_response(
            response,
            maximum_bytes=self.maximum_response_bytes,
            request_url=url,
        )
        return _json_body(body, representation=representation), body

    def account_page(self, account_id: str) -> AccountDocumentPage:
        normalized_account = _account_id(account_id)
        source_url = _dial_account_url(normalized_account)
        html, body = self._get_text(source_url)
        return parse_account_documents_page(
            html,
            body.source_url,
            expected_account_id=normalized_account,
        )

    def warm_session(self) -> None:
        if self._session_warmed:
            return
        html, body = self._get_text(
            MY_WEBLINK_URL,
            params={"dbid": DATABASE_ID, "repo": REPOSITORY_NAME},
        )
        if (
            "Powered by Laserfiche" not in html
            or "Cookies are not enabled for this website" in html
        ):
            raise SourceSchemaError(
                "Deschutes WebLink session page changed",
                url=body.source_url,
            )
        self._session_warmed = True

    def viewer_contract(self, document_id: str) -> ViewerContract:
        normalized_id = _document_id(document_id)
        cached = self._viewer_contracts.get(normalized_id)
        if cached is not None:
            return cached
        html, body = self._get_text(_viewer_url(normalized_id))
        contract = parse_viewer_contract(html, body.source_url)
        self._session_warmed = True
        self._viewer_contracts[normalized_id] = contract
        return contract

    def document_info(self, document_id: str) -> dict[str, Any]:
        normalized_id = _document_id(document_id)
        viewer = self.viewer_contract(normalized_id)
        payload, body = self._post_json(
            DOCUMENT_INFO_URL,
            {
                "repoName": REPOSITORY_NAME,
                "entryId": int(normalized_id),
            },
            representation="document metadata",
        )
        return parse_document_info(
            payload,
            body.source_url,
            expected_document_id=normalized_id,
            viewer_contract=viewer,
        )

    def folder_metadata(self, folder_id: str) -> dict[str, Any]:
        normalized_id = _folder_id(folder_id)
        self.warm_session()
        payload, body = self._post_json(
            FOLDER_METADATA_URL,
            {
                "repoName": REPOSITORY_NAME,
                "entryId": int(normalized_id),
            },
            representation="folder metadata",
        )
        return parse_folder_metadata(
            payload,
            body.source_url,
            folder_id=normalized_id,
        )

    def _read_artifact(
        self,
        response: Any,
        *,
        request_url: str,
        maximum_bytes: int,
        retrieval_mode: str,
        expected_extension: str | None = None,
        generation_token: str | None = None,
    ) -> BinaryArtifact:
        body = _bounded_response(
            response,
            maximum_bytes=maximum_bytes,
            request_url=request_url,
        )
        content_type = body.media_type.casefold()
        if not body.body:
            raise SourceSchemaError(
                "Deschutes WebLink returned an empty document representation",
                url=body.source_url,
            )
        stripped_prefix = body.body[:256].lstrip().lower()
        if (
            "html" in content_type
            or "json" in content_type
            or stripped_prefix.startswith(b"<!doctype html")
            or stripped_prefix.startswith(b"<html")
        ):
            raise SourceSchemaError(
                "Deschutes WebLink document route returned a non-document page",
                url=body.source_url,
                details={
                    "content_type": body.media_type,
                    "body_prefix_hex": body.body[:16].hex(),
                },
            )
        expects_pdf = (
            "pdf" in content_type
            or (expected_extension or "").casefold().lstrip(".") == "pdf"
            or retrieval_mode == "generated_pdf_from_imaged_pages"
        )
        if expects_pdf and not body.body.startswith(b"%PDF-"):
            raise SourceSchemaError(
                "Deschutes WebLink PDF response has invalid bytes",
                url=body.source_url,
                details={"body_prefix_hex": body.body[:16].hex()},
            )
        return BinaryArtifact(
            content=body.body,
            source_url=body.source_url,
            media_type=body.media_type or "application/octet-stream",
            filename=_filename_from_headers(body.headers),
            retrieval_mode=retrieval_mode,
            generation_token=generation_token,
            etag=_header(body.headers, "etag"),
            last_modified=_header(body.headers, "last-modified"),
        )

    def download_document(
        self,
        document: Mapping[str, Any],
        *,
        maximum_bytes: int,
        poll_attempts: int,
        poll_interval: float,
    ) -> BinaryArtifact:
        document_id = _document_id(document.get("laserfiche_entry_id"))
        retrieval_mode = _clean(document.get("retrieval_mode"))
        if retrieval_mode == "electronic_file":
            source_url = _clean(document.get("electronic_file_url"))
            if source_url is None:
                raise SourceSchemaError(
                    "Deschutes WebLink electronic-file metadata is incomplete",
                    url=DOCUMENT_INFO_URL,
                )
            response = self._request(
                "GET",
                source_url,
                accept="application/pdf,application/octet-stream,*/*;q=0.8",
            )
            return self._read_artifact(
                response,
                request_url=source_url,
                maximum_bytes=maximum_bytes,
                retrieval_mode="electronic_file",
                expected_extension=_clean(document.get("extension")),
            )
        if retrieval_mode not in {
            "generated_pdf_from_imaged_pages",
            "generated_pdf_from_pages",
        }:
            raise SourceSchemaError(
                "Deschutes WebLink exposes metadata but no downloadable representation",
                url=_viewer_url(document_id),
                details={
                    "document_id": document_id,
                    "retrieval_mode": retrieval_mode,
                },
            )
        page_count = _integer(document.get("page_count"))
        if page_count is None or page_count <= 0:
            raise SourceSchemaError(
                "Deschutes WebLink generated-PDF page count is invalid",
                url=_viewer_url(document_id),
            )
        response = self._request(
            "POST",
            GENERATE_PDF_URL,
            params={
                "key": document_id,
                "PageRange": f"1 - {page_count}",
                "Watermark": 0,
                "repo": REPOSITORY_NAME,
            },
            json_body={},
            accept="text/plain,text/html,*/*;q=0.8",
        )
        initiation = _bounded_response(
            response,
            maximum_bytes=min(self.maximum_response_bytes, 64 * 1024),
            request_url=GENERATE_PDF_URL,
        )
        first_line = _decode_text(initiation).splitlines()[0].strip()
        if not re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            first_line,
            flags=re.I,
        ):
            raise SourceSchemaError(
                "Deschutes WebLink PDF generator did not return a job token",
                url=initiation.source_url,
                details={"response_prefix": _decode_text(initiation)[:200]},
            )
        token = first_line
        for poll_index in range(1, poll_attempts + 1):
            payload, progress_body = self._post_json(
                PDF_PROGRESS_URL,
                {"Key": token},
                representation="PDF generation progress",
            )
            progress = payload.get("data")
            if not isinstance(progress, Mapping):
                raise SourceSchemaError(
                    "Deschutes WebLink PDF progress data is missing",
                    url=progress_body.source_url,
                )
            if bool(progress.get("finished")):
                if not bool(progress.get("success")):
                    raise SourceResponseError(
                        "Deschutes WebLink could not generate the document PDF",
                        url=progress_body.source_url,
                        details={
                            "document_id": document_id,
                            "generation_token": token,
                            "source_error": progress.get("errMsg"),
                        },
                    )
                generated_url = _official_url(
                    f"PDF10/{quote(token, safe='-')}/{quote(document_id, safe='')}"
                )
                generated_response = self._request(
                    "GET",
                    generated_url,
                    accept="application/pdf,*/*;q=0.8",
                )
                return self._read_artifact(
                    generated_response,
                    request_url=generated_url,
                    maximum_bytes=maximum_bytes,
                    retrieval_mode="generated_pdf_from_imaged_pages",
                    expected_extension="pdf",
                    generation_token=token,
                )
            if poll_index < poll_attempts:
                self.sleeper(poll_interval)
        raise TransportError(
            "Deschutes WebLink PDF generation did not finish within the poll bound",
            url=PDF_PROGRESS_URL,
            details={
                "document_id": document_id,
                "generation_token": token,
                "poll_attempts": poll_attempts,
            },
        )


def _encode_cursor(state: Mapping[str, Any]) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "source_id": SOURCE_ID,
        "operation": "account",
        **dict(state),
    }
    token = base64.urlsafe_b64encode(canonical_json(payload).encode()).decode()
    return CURSOR_PREFIX + token.rstrip("=")


def _decode_cursor(value: str) -> Mapping[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise WebLinkSelectionError(
            "invalid_cursor",
            "Continuation is not a Deschutes CDD WebLink cursor",
        )
    token = value[len(CURSOR_PREFIX) :]
    try:
        decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        state = json.loads(decoded)
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise WebLinkSelectionError(
            "invalid_cursor",
            "Deschutes CDD WebLink cursor is malformed",
        ) from error
    if (
        not isinstance(state, Mapping)
        or state.get("version") != CURSOR_VERSION
        or state.get("source_id") != SOURCE_ID
        or state.get("operation") != "account"
        or not isinstance(state.get("offset"), int)
        or state.get("offset") < 0
        or not isinstance(state.get("account_id"), str)
        or not isinstance(state.get("criteria"), str)
        or not isinstance(state.get("snapshot"), str)
        or not isinstance(state.get("schema"), str)
    ):
        raise WebLinkSelectionError(
            "invalid_cursor",
            "Deschutes CDD WebLink cursor fields are invalid",
        )
    return state


def _basic_query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    requested_limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _verify_document_link(
    client: DeschutesWebLinkClient | Any,
    document: Mapping[str, Any],
    *,
    account_id: str | None,
    expected_taxlot: str | None,
) -> Mapping[str, Any] | None:
    document_id = _document_id(document.get("laserfiche_entry_id"))
    metadata_taxlot = _normalize_taxlot(document.get("map_taxlot"))
    expected_normalized = _normalize_taxlot(expected_taxlot)
    if expected_normalized and metadata_taxlot != expected_normalized:
        return None
    if account_id is None:
        return {
            "deschutes_dial_account_id": None,
            "map_taxlot": metadata_taxlot,
            "verification": (
                "weblink_template_taxlot"
                if expected_normalized
                else "not_requested"
            ),
        }
    page = client.account_page(_account_id(account_id))
    linked = next(
        (
            record
            for record in page.records
            if record.get("laserfiche_entry_id") == document_id
        ),
        None,
    )
    if linked is None:
        return None
    if expected_normalized and page.map_taxlot != expected_normalized:
        return None
    if metadata_taxlot and page.map_taxlot and metadata_taxlot != page.map_taxlot:
        raise SourceSchemaError(
            "Deschutes DIAL and WebLink disagree on the document taxlot",
            url=str(linked.get("source_url")),
            details={
                "document_id": document_id,
                "dial_taxlot": page.map_taxlot,
                "weblink_taxlot": metadata_taxlot,
            },
        )
    return {
        "deschutes_dial_account_id": page.account_id,
        "map_taxlot": page.map_taxlot or metadata_taxlot,
        "verification": "dial_account_document_index",
        "discovery_source_url": page.source_url,
        "dial_index_record": dict(linked),
    }


def execute_account(
    args: argparse.Namespace,
    *,
    client: DeschutesWebLinkClient | Any,
) -> PublicRecordsResult:
    account_id = _account_id(args.account_id)
    criteria = {
        "account_id": account_id,
        "sort": ACCOUNT_SORT,
        "hydrate": bool(args.hydrate),
    }
    criteria_fingerprint = sha256_fingerprint(criteria)
    query = _basic_query(
        "account",
        criteria,
        requested_limit=args.limit,
        cursor=args.cursor,
    )
    page = client.account_page(account_id)
    cursor_state = _decode_cursor(args.cursor) if args.cursor else None
    offset = 0
    if cursor_state:
        if (
            cursor_state["account_id"] != account_id
            or cursor_state["criteria"] != criteria_fingerprint
        ):
            raise WebLinkSelectionError(
                "cursor_query_mismatch",
                "Continuation belongs to a different Deschutes account query",
            )
        if (
            cursor_state["snapshot"] != page.snapshot_fingerprint
            or cursor_state["schema"] != page.schema_fingerprint
        ):
            raise WebLinkSelectionError(
                "cursor_snapshot_changed",
                "Deschutes account document index changed since the continuation",
                details={"account_id": account_id},
            )
        offset = cursor_state["offset"]
    if offset > len(page.records):
        raise WebLinkSelectionError(
            "cursor_offset_changed",
            "Deschutes account continuation exceeds the current document index",
        )
    selected = [dict(record) for record in page.records[offset : offset + args.limit]]
    if args.hydrate:
        for record in selected:
            record["weblink_metadata"] = client.document_info(
                str(record["laserfiche_entry_id"])
            )
    next_offset = offset + len(selected)
    next_cursor = None
    if next_offset < len(page.records):
        next_cursor = _encode_cursor(
            {
                "account_id": account_id,
                "criteria": criteria_fingerprint,
                "offset": next_offset,
                "snapshot": page.snapshot_fingerprint,
                "schema": page.schema_fingerprint,
            }
        )
    for record in selected:
        record["account_index"] = {
            "mailing_name": page.mailing_name,
            "situs_address": page.situs_address,
            "tax_status": page.tax_status,
            "total_unique_documents": len(page.records),
            "schema_fingerprint": page.schema_fingerprint,
            "snapshot_fingerprint": page.snapshot_fingerprint,
        }
    return PublicRecordsResult.success(
        query,
        selected,
        next_cursor=next_cursor,
    )


def execute_document(
    args: argparse.Namespace,
    *,
    client: DeschutesWebLinkClient | Any,
) -> PublicRecordsResult:
    document_id = _document_id(args.document_id)
    query = _basic_query(
        "document",
        {
            "laserfiche_entry_id": document_id,
            "deschutes_dial_account_id": args.account,
            "expected_taxlot": _normalize_taxlot(args.taxlot),
        },
    )
    document = client.document_info(document_id)
    link = _verify_document_link(
        client,
        document,
        account_id=args.account,
        expected_taxlot=args.taxlot,
    )
    if link is None:
        return PublicRecordsResult.success(query, [])
    document["verified_property_link"] = dict(link)
    if args.account:
        document["property_identifiers"] = {
            **dict(document.get("property_identifiers") or {}),
            "deschutes_dial_account_id": _account_id(args.account),
        }
        document["provenance"] = [
            *list(document.get("provenance") or []),
            {
                "component": "dial_account_document_index",
                "source_id": DIAL_SOURCE_ID,
                "source_url": link.get("discovery_source_url"),
            },
        ]
    return PublicRecordsResult.success(query, [document])


def execute_folder(
    args: argparse.Namespace,
    *,
    client: DeschutesWebLinkClient | Any,
) -> PublicRecordsResult:
    folder_id = _folder_id(args.folder_id)
    query = _basic_query(
        "folder",
        {"laserfiche_folder_id": folder_id},
    )
    return PublicRecordsResult.success(
        query,
        [client.folder_metadata(folder_id)],
    )


def _atomic_binary_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def execute_download(
    args: argparse.Namespace,
    *,
    client: DeschutesWebLinkClient | Any,
) -> PublicRecordsResult:
    document_id = _document_id(args.document_id)
    query = _basic_query(
        "download",
        {
            "laserfiche_entry_id": document_id,
            "deschutes_dial_account_id": args.account,
            "expected_taxlot": _normalize_taxlot(args.taxlot),
            "maximum_bytes": args.max_bytes,
            "poll_attempts": args.poll_attempts,
        },
    )
    document = client.document_info(document_id)
    link = _verify_document_link(
        client,
        document,
        account_id=args.account,
        expected_taxlot=args.taxlot,
    )
    if link is None:
        return PublicRecordsResult.success(query, [])
    artifact = client.download_document(
        document,
        maximum_bytes=args.max_bytes,
        poll_attempts=args.poll_attempts,
        poll_interval=args.poll_interval,
    )
    destination = Path(args.destination).expanduser().resolve()
    _atomic_binary_write(destination, artifact.content)
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "document",
        document_id,
    )
    record = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": artifact.source_url,
        "record_kind": "laserfiche_document_artifact",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "access_state": "public_anonymous_cookie_session",
        "native_document_id": document_id,
        "laserfiche_entry_id": document_id,
        "deschutes_dial_account_id": (
            _account_id(args.account) if args.account else None
        ),
        "map_taxlot": link.get("map_taxlot"),
        "verified_property_link": dict(link),
        "retrieval_state": "retrieved",
        "retrieval_mode": artifact.retrieval_mode,
        "generation_token": artifact.generation_token,
        "media_type": artifact.media_type,
        "filename": artifact.filename,
        "size_bytes": len(artifact.content),
        "sha256": hashlib.sha256(artifact.content).hexdigest(),
        "etag": artifact.etag,
        "last_modified": artifact.last_modified,
        "local_path": str(destination),
        "document_metadata": document,
        "provenance": [
            {
                "component": "laserfiche_document_metadata",
                "source_id": SOURCE_ID,
                "source_url": document["metadata_endpoint"],
            },
            {
                "component": artifact.retrieval_mode,
                "source_id": SOURCE_ID,
                "source_url": artifact.source_url,
            },
        ],
    }
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[str(destination)],
    )


def execute_probe(
    args: argparse.Namespace,
    *,
    client: DeschutesWebLinkClient | Any,
) -> PublicRecordsResult:
    query = _basic_query(
        "probe",
        {
            "account_id": PROBE_ACCOUNT_ID,
            "electronic_document_id": PROBE_ELECTRONIC_DOCUMENT_ID,
            "imaged_document_id": PROBE_IMAGED_DOCUMENT_ID,
            "with_download": bool(args.with_download),
        },
    )
    page = client.account_page(PROBE_ACCOUNT_ID)
    linked_ids = {
        str(record.get("laserfiche_entry_id")) for record in page.records
    }
    missing = {
        PROBE_ELECTRONIC_DOCUMENT_ID,
        PROBE_IMAGED_DOCUMENT_ID,
    } - linked_ids
    if missing:
        raise SourceSchemaError(
            "Deschutes DIAL no longer links the WebLink sentinels",
            url=page.source_url,
            details={"missing_document_ids": sorted(missing)},
        )
    electronic = client.document_info(PROBE_ELECTRONIC_DOCUMENT_ID)
    imaged = client.document_info(PROBE_IMAGED_DOCUMENT_ID)
    if electronic.get("retrieval_mode") != "electronic_file":
        raise SourceSchemaError(
            "Deschutes recent WebLink sentinel changed storage mode",
            url=str(electronic.get("source_url")),
        )
    if str(electronic.get("parent_folder_id")) != PROBE_PARENT_FOLDER_ID:
        raise SourceSchemaError(
            "Deschutes recent WebLink sentinel parent folder changed",
            url=str(electronic.get("source_url")),
            details={
                "expected_parent_folder_id": PROBE_PARENT_FOLDER_ID,
                "observed_parent_folder_id": electronic.get("parent_folder_id"),
            },
        )
    if imaged.get("retrieval_mode") not in {
        "generated_pdf_from_imaged_pages",
        "generated_pdf_from_pages",
    }:
        raise SourceSchemaError(
            "Deschutes historical WebLink sentinel changed storage mode",
            url=str(imaged.get("source_url")),
        )
    if (
        _normalize_taxlot(electronic.get("map_taxlot")) != PROBE_TAXLOT
        or _normalize_taxlot(imaged.get("map_taxlot")) != PROBE_TAXLOT
        or page.map_taxlot != PROBE_TAXLOT
    ):
        raise SourceSchemaError(
            "Deschutes WebLink sentinel taxlot join changed",
            url=page.source_url,
        )
    folder = client.folder_metadata(str(electronic["parent_folder_id"]))
    downloads: list[dict[str, Any]] = []
    if args.with_download:
        for document in (electronic, imaged):
            artifact = client.download_document(
                document,
                maximum_bytes=args.max_bytes,
                poll_attempts=args.poll_attempts,
                poll_interval=args.poll_interval,
            )
            downloads.append(
                {
                    "laserfiche_entry_id": document["laserfiche_entry_id"],
                    "source_url": artifact.source_url,
                    "retrieval_mode": artifact.retrieval_mode,
                    "media_type": artifact.media_type,
                    "size_bytes": len(artifact.content),
                    "sha256": hashlib.sha256(artifact.content).hexdigest(),
                }
            )
    record = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": BASE_URL,
        "record_kind": "source_probe",
        "access_state": "public_anonymous_cookie_session",
        "account_discovery": {
            "source_url": page.source_url,
            "account_id": page.account_id,
            "map_taxlot": page.map_taxlot,
            "unique_document_count": len(page.records),
            "schema_fingerprint": page.schema_fingerprint,
            "snapshot_fingerprint": page.snapshot_fingerprint,
        },
        "electronic_document": {
            "laserfiche_entry_id": electronic["laserfiche_entry_id"],
            "parent_folder_id": electronic["parent_folder_id"],
            "retrieval_mode": electronic["retrieval_mode"],
            "source_data_fingerprint": electronic["source_data_fingerprint"],
        },
        "imaged_document": {
            "laserfiche_entry_id": imaged["laserfiche_entry_id"],
            "parent_folder_id": imaged["parent_folder_id"],
            "page_count": imaged["page_count"],
            "retrieval_mode": imaged["retrieval_mode"],
            "source_data_fingerprint": imaged["source_data_fingerprint"],
        },
        "parent_folder": {
            "laserfiche_folder_id": folder["laserfiche_folder_id"],
            "laserfiche_path": folder["laserfiche_path"],
            "source_data_fingerprint": folder["source_data_fingerprint"],
        },
        "viewer_access": electronic.get("viewer_contract"),
        "downloads": downloads,
    }
    return PublicRecordsResult.success(query, [record])


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": "deschutes-cdd-weblink-sources/1.0",
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "observed_contract": {
            "account_discovery": {
                "source_id": DIAL_SOURCE_ID,
                "route": f"{DIAL_BASE_URL}{DIAL_DOCUMENT_ROUTE}",
                "method": "GET",
                "representation": "complete_server_rendered_html_table",
                "native_identity": "deschutes_dial_account_id",
                "join_key": "map_taxlot",
                "canonical_order": ACCOUNT_SORT,
                "continuation": "query_and_snapshot_bound_client_cursor",
            },
            "viewer": {
                "url": f"{VIEWER_URL}?id={{laserfiche_entry_id}}",
                "repository": REPOSITORY_NAME,
                "cookie_handshake": True,
                "public_capabilities_observed": {
                    "document_open": True,
                    "document_export": True,
                    "document_print": True,
                    "repository_search": False,
                    "repository_browse_link": False,
                },
            },
            "document_metadata": {
                "url": DOCUMENT_INFO_URL,
                "method": "POST_JSON",
                "parameters": {
                    "repoName": REPOSITORY_NAME,
                    "entryId": "laserfiche_entry_id",
                },
            },
            "folder_metadata": {
                "url": FOLDER_METADATA_URL,
                "method": "POST_JSON",
                "parameters": {
                    "repoName": REPOSITORY_NAME,
                    "entryId": "laserfiche_folder_id",
                },
            },
            "document_representations": {
                "electronic_file": (
                    f"{BASE_URL}ElectronicFile.aspx?docid={{entry_id}}"
                    f"&dbid={DATABASE_ID}&repo={REPOSITORY_NAME}"
                ),
                "imaged_pages": {
                    "start": GENERATE_PDF_URL,
                    "poll": PDF_PROGRESS_URL,
                    "retrieve": (
                        f"{BASE_URL}PDF10/{{generation_token}}/{{entry_id}}"
                    ),
                },
            },
        },
        "identity_model": {
            "document_identity": "laserfiche_entry_id",
            "folder_identity": "laserfiche_folder_id",
            "property_join_identifiers": [
                "deschutes_dial_account_id",
                "map_taxlot",
            ],
            "permit_join_identifiers": [
                "case_number",
                "accela_document_id",
            ],
        },
        "complements": [
            {
                "source_id": DIAL_SOURCE_ID,
                "url": DIAL_BASE_URL,
                "relationship": (
                    "anonymous_account_search_property_context_permits_and_"
                    "account_to_document_discovery"
                ),
                "join_keys": ["deschutes_dial_account_id", "map_taxlot"],
            },
            {
                "source_id": TAXLOT_SOURCE_ID,
                "url": (
                    "https://maps.deschutes.org/arcgis/rest/services/"
                    "Taxlots/FeatureServer"
                ),
                "relationship": "parcel_geometry_assessment_and_relationship_graph",
                "join_keys": ["map_taxlot", "deschutes_dial_account_id"],
            },
            {
                "kind": OREGON_EPERMITTING_COMPLEMENT_KEY,
                "url": "https://aca-oregon.accela.com/oregon/",
                "relationship": (
                    "current_permit_status_and_applicant_scoped_approved_documents"
                ),
                "join_keys": ["case_number", "accela_document_id"],
                "coverage_difference": (
                    "current ePermitting records; some approved construction "
                    "documents are available only to the original applicant"
                ),
            },
            {
                "kind": "official_public_records_request",
                "url": (
                    "https://www.deschutes.org/administration/page/"
                    "deschutes-county-public-records-requests"
                ),
                "relationship": (
                    "request route for CDD records absent from the account-linked "
                    "repository or unavailable as document bytes"
                ),
            },
        ],
    }


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
    except Exception:
        return


def _client(args: argparse.Namespace) -> DeschutesWebLinkClient:
    return DeschutesWebLinkClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
        rate_limiter=MinimumIntervalRateLimiter(args.minimum_interval),
        maximum_response_bytes=args.max_response_bytes,
    )


def _fallback_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {"error_context": "source_request"}
    for name in (
        "account_id",
        "document_id",
        "folder_id",
        "account",
        "taxlot",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = value
    return _basic_query(
        args.command,
        parameters,
        requested_limit=getattr(args, "limit", None),
        cursor=getattr(args, "cursor", None),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: DeschutesWebLinkClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute a source listing, account, document, folder, download, or probe."""

    if args.command == "sources":
        return _sources_payload()
    active_client = client or _client(args)
    owns_client = client is None
    try:
        if args.command == "account":
            result = execute_account(args, client=active_client)
        elif args.command == "document":
            result = execute_document(args, client=active_client)
        elif args.command == "folder":
            result = execute_folder(args, client=active_client)
        elif args.command == "download":
            result = execute_download(args, client=active_client)
        else:
            result = execute_probe(args, client=active_client)
    except WebLinkSelectionError as error:
        query = _fallback_query(args)
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        query = _fallback_query(args)
        result = failure_result(query, error)
    except (KeyError, TypeError, ValueError) as error:
        query = _fallback_query(args)
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    finally:
        if owns_client:
            active_client.close()
    if log_results:
        _best_effort_log(result.query, result)
    return result


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=DEFAULT_MAX_RESPONSE_BYTES,
        help="Maximum bytes to read from an HTML or JSON response",
    )
    add_output_args(parser)


def _add_property_link_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--account",
        help="Optionally verify that DIAL account links this document",
    )
    parser.add_argument(
        "--taxlot",
        help="Optionally require this map/taxlot in WebLink metadata",
    )


def _add_download_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_DOCUMENT_BYTES,
        help="Maximum document bytes to read",
    )
    parser.add_argument(
        "--poll-attempts",
        type=int,
        default=DEFAULT_POLL_ATTEMPTS,
        help="Maximum progress checks for an imaged-document PDF job",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help="Seconds between imaged-document PDF progress checks",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Deschutes County CDD development documents in "
            "Laserfiche WebLink"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Describe verified discovery, metadata, download, and complement routes",
    )
    add_output_args(sources)

    account = sub.add_parser(
        "account",
        help="Discover WebLink document IDs linked from one DIAL property account",
    )
    account.add_argument("account_id")
    account.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    account.add_argument(
        "--cursor",
        help="Query- and snapshot-bound continuation from an earlier account query",
    )
    account.add_argument(
        "--hydrate",
        action="store_true",
        help="Also fetch WebLink metadata for each returned document",
    )
    _add_transport_arguments(account)

    document = sub.add_parser(
        "document",
        help="Fetch one WebLink document and template-metadata record",
    )
    document.add_argument("document_id")
    _add_property_link_arguments(document)
    _add_transport_arguments(document)

    folder = sub.add_parser(
        "folder",
        help="Fetch metadata for one source-native Laserfiche parent folder",
    )
    folder.add_argument("folder_id")
    _add_transport_arguments(folder)

    download = sub.add_parser(
        "download",
        help="Retrieve an electronic file or generate a PDF from imaged pages",
    )
    download.add_argument("document_id")
    download.add_argument("--destination", required=True)
    _add_property_link_arguments(download)
    _add_download_arguments(download)
    _add_transport_arguments(download)

    probe = sub.add_parser(
        "probe",
        help="Verify account discovery, both storage modes, and parent-folder metadata",
    )
    probe.add_argument(
        "--with-download",
        action="store_true",
        help="Also retrieve both the electronic and imaged-document sentinels",
    )
    _add_download_arguments(probe)
    _add_transport_arguments(probe)
    return parser


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
    count = len(records) if isinstance(records, list) else 1
    if write_output(
        payload,
        args,
        summary=f"Deschutes CDD WebLink {args.command}",
        result_count=count,
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command == "sources":
        print(
            f"{SOURCE_NAME}: account discovery, metadata, folders, and two "
            "document download modes"
        )
        return
    print(
        f"Deschutes CDD WebLink {args.command}: "
        f"{payload.get('status')} ({count} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for field in (
        "timeout",
        "retry_attempts",
        "max_response_bytes",
        "limit",
        "max_bytes",
        "poll_attempts",
    ):
        if hasattr(args, field) and getattr(args, field) <= 0:
            parser.error(f"--{field.replace('_', '-')} must be positive")
    for field in ("minimum_interval", "poll_interval"):
        if hasattr(args, field) and getattr(args, field) < 0:
            parser.error(f"--{field.replace('_', '-')} must not be negative")
    value = execute(args)
    _emit(value, args)
    if isinstance(value, PublicRecordsResult) and value.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
