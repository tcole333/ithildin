#!/usr/bin/env python3
"""Query Colorado appellate opinions and current release surfaces.

The adapter keeps two official source components distinct:

* ``research.coloradojudicial.gov`` provides the historical Colorado-branded
  case-law index, document metadata, full text, and rendered PDFs.
* ``coloradojudicial.gov`` provides the current Supreme Court opinion release
  page and Court of Appeals announcement packets.  An announcement packet is
  an index/freshness artifact, not itself an opinion.

Examples:
    uv run python tools/query_colorado_opinions.py search 25997 \
        --court supreme --json
    uv run python tools/query_colorado_opinions.py docket 25CA0631 \
        --court appeals --output colorado-opinion.json
    uv run python tools/query_colorado_opinions.py releases \
        --court appeals --year 2026 --json
    uv run python tools/query_colorado_opinions.py document 887202075 \
        --output calvaresi.json
    uv run python tools/query_colorado_opinions.py download 887202075 \
        /tmp/calvaresi.pdf --output /tmp/calvaresi-receipt.json
    uv run python tools/query_colorado_opinions.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import acquisition_result_status
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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import acquisition_result_status
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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )


SOURCE_ID = "us-co-appellate-case-law-search"
RELEASE_SOURCE_ID = "us-co-judicial-appellate-opinion-releases"
ADAPTER_FAMILY = "colorado_appellate_opinions"
STATE_CODE = "CO"
STATE_GEOID = "08"

CASE_LAW_BASE_URL = "https://research.coloradojudicial.gov"
SEARCH_URL = f"{CASE_LAW_BASE_URL}/search.json"
COUNT_URL = f"{CASE_LAW_BASE_URL}/search/count.json"
JUDICIAL_BASE_URL = "https://www.coloradojudicial.gov"
SUPREME_RELEASE_URL = (
    f"{JUDICIAL_BASE_URL}/supreme-court/opinions?topic=78&wrapped=true"
)
APPEALS_RELEASE_URL = (
    f"{JUDICIAL_BASE_URL}/court-appeals/"
    "court-appeals-case-announcements"
)

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
NATIVE_PAGE_SIZE = 20
CURSOR_VERSION = "v2"
SENTINEL_DOCUMENT_ID = 887202075
SENTINEL_QUERY = "25997"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

COURTS: dict[str, dict[str, str]] = {
    "supreme": {
        "native_id": "14024_01",
        "name": "Colorado Supreme Court",
        "court_id": "co-supreme-court",
        "release_url": SUPREME_RELEASE_URL,
    },
    "appeals": {
        "native_id": "14024_02",
        "name": "Colorado Court of Appeals",
        "court_id": "co-court-of-appeals",
        "release_url": APPEALS_RELEASE_URL,
    },
}
COURT_BY_NATIVE_ID = {
    value["native_id"]: key for key, value in COURTS.items()
}
COURT_BY_NAME = {
    value["name"].casefold(): key for key, value in COURTS.items()
}

SEARCH_CURSOR_PATTERN = re.compile(
    r"^colorado-opinions:v2:query:(?P<query>[0-9a-f]{64}):"
    r"page:(?P<page>\d+):row:(?P<row>\d+):seen:(?P<seen>\d+):"
    r"anchor:(?P<anchor>\d+)$"
)
RELEASE_CURSOR_PATTERN = re.compile(
    r"^colorado-opinion-releases:v2:query:(?P<query>[0-9a-f]{64}):"
    r"offset:(?P<offset>\d+):anchor:(?P<anchor>[0-9a-f]{64})$"
)
APPELLATE_DOCKET_RE = re.compile(
    r"\b\d{2}(?:SC|SA|CA)\d{3,5}\b",
    re.IGNORECASE,
)
SUPREME_CITATION_RE = re.compile(r"^\d{2,4}\s+CO\s+\d+[A-Za-z]?$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CASE_LAW_WARNINGS = (
    "The Colorado Case Law Search is the historical searchable opinion "
    "component; the Judicial Branch release pages are a separate freshness "
    "component and may lead the historical index.",
    "The case-law index is not a complete appellate docket and does not expose "
    "the parties' underlying briefs or trial-court filings.",
    "Publication status is left null when the case-law index does not state it; "
    "the adapter does not infer publication from citation presence.",
)
RELEASE_WARNINGS = (
    "Court of Appeals announcement PDFs are release packets containing opinion "
    "lists and related notices; they are not normalized as opinions.",
    "Current release records remain separate from historical case-law records "
    "even when both components refer to the same case.",
)

CASE_LAW_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Colorado Appellate Case Law Search",
    source_role="official_colorado_branded_historical_case_law_search",
    base_url=CASE_LAW_BASE_URL,
    dataset_id="colorado-appellate-case-law-search",
    metadata={
        "authority": "Colorado Judicial Branch",
        "operator": "vLex",
        "state_code": STATE_CODE,
        "authentication": "none",
        "adapter_family": ADAPTER_FAMILY,
        "native_pagination": "page_number_with_count",
        "native_page_size": NATIVE_PAGE_SIZE,
        "components": [SOURCE_ID, RELEASE_SOURCE_ID],
    },
)
RELEASE_METADATA = SourceMetadata(
    source_id=RELEASE_SOURCE_ID,
    name="Colorado Judicial Appellate Opinion Releases",
    source_role="official_current_appellate_release_surfaces",
    base_url=JUDICIAL_BASE_URL,
    dataset_id="colorado-judicial-appellate-opinion-releases",
    metadata={
        "authority": "Colorado Judicial Branch",
        "state_code": STATE_CODE,
        "authentication": "none",
        "adapter_family": ADAPTER_FAMILY,
        "supreme_release_url": SUPREME_RELEASE_URL,
        "appeals_release_url": APPEALS_RELEASE_URL,
        "components": [SOURCE_ID, RELEASE_SOURCE_ID],
    },
)
SOURCE_METADATA = CASE_LAW_METADATA


class ColoradoOpinionsError(RuntimeError):
    """Source, transport, selection, or pagination failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "source",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.retryable = retryable
        self.details = dict(details or {})


class ColoradoOpinionsSelectionError(ColoradoOpinionsError):
    """A caller selection or cursor is invalid."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="query_selection",
            details=details,
        )


class ColoradoOpinionsSourceChangedError(ColoradoOpinionsError):
    """The live source no longer matches its verified contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


class ColoradoOpinionsPaginationError(ColoradoOpinionsError):
    """Native pagination could not be completed without guessing."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "native_pagination_incomplete",
            message,
            status=ResultStatus.PARTIAL,
            category="source_pagination",
            details=details,
        )


@dataclass(frozen=True)
class CaseLawCount:
    count: int
    restricted: bool
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class CaseLawPage:
    results: tuple[Mapping[str, Any], ...]
    count: int
    partial_results: bool
    page_number: int
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class CaseLawBatch:
    results: tuple[Mapping[str, Any], ...]
    total_count: int
    pages_fetched: int
    next_cursor: str | None
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: ColoradoOpinionsError | None = None


@dataclass(frozen=True)
class ReleasePage:
    records: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str
    next_page_url: str | None = None


@dataclass(frozen=True)
class ReleaseCollection:
    records: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    next_cursor: str | None
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: ColoradoOpinionsError | None = None


@dataclass(frozen=True)
class CaseLawDocument:
    metadata: Mapping[str, Any]
    content_html: str | None
    metadata_url: str
    content_url: str | None
    metadata_schema_fingerprint: str
    content_sha256: str | None


@dataclass(frozen=True)
class PDFArtifact:
    content: bytes
    source_url: str
    media_type: str
    sha256: str
    file_name: str | None
    component_source_id: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _required_text(value: Any, field: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise ColoradoOpinionsSourceChangedError(
            "required_field_missing",
            f"Colorado opinions response lacks {field}",
            details={"field": field},
        )
    return normalized


def _required_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise ColoradoOpinionsSourceChangedError(
            "integer_field_changed",
            f"Colorado opinions {field} is not an integer",
            details={"field": field, "value": value},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ColoradoOpinionsSourceChangedError(
            "integer_field_changed",
            f"Colorado opinions {field} is not an integer",
            details={"field": field, "value": value},
        ) from error
    if parsed < minimum:
        raise ColoradoOpinionsSourceChangedError(
            "integer_field_out_of_range",
            f"Colorado opinions {field} is out of range",
            details={"field": field, "value": parsed, "minimum": minimum},
        )
    return parsed


def _required_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ColoradoOpinionsSourceChangedError(
            "boolean_field_changed",
            f"Colorado opinions {field} is not boolean",
            details={"field": field, "value": value},
        )
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ColoradoOpinionsSourceChangedError(
            "object_field_changed",
            f"Colorado opinions {field} is not an object",
            details={"field": field},
        )
    return value


def _schema_fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _iso_date(value: Any, field: str) -> str:
    normalized = _required_text(value, field)
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as error:
        raise ColoradoOpinionsSourceChangedError(
            "date_field_changed",
            f"Colorado opinions returned an invalid {field}",
            details={"field": field, "value": normalized},
        ) from error


def _response_url(response: Any, fallback: str) -> str:
    return str(getattr(response, "url", "") or fallback)


def _media_type(response: Any) -> str:
    headers = getattr(response, "headers", {})
    return (
        str(headers.get("Content-Type", headers.get("content-type", "")))
        .split(";", 1)[0]
        .strip()
        .casefold()
    )


def _property_values(
    result: Mapping[str, Any],
    label: str,
) -> list[str]:
    values: list[str] = []
    raw_properties = result.get("properties", [])
    if not isinstance(raw_properties, list):
        raise ColoradoOpinionsSourceChangedError(
            "properties_field_changed",
            "Colorado case-law result properties is not an array",
        )
    for index, raw_property in enumerate(raw_properties):
        item = _mapping(raw_property, f"properties[{index}]")
        descriptor = _mapping(
            item.get("property"),
            f"properties[{index}].property",
        )
        observed_label = _text(descriptor.get("label"))
        raw_values = item.get("values")
        if not isinstance(raw_values, list):
            raise ColoradoOpinionsSourceChangedError(
                "property_values_changed",
                "Colorado case-law property values is not an array",
                details={"property_index": index},
            )
        if observed_label and observed_label.casefold() == label.casefold():
            values.extend(
                value
                for raw in raw_values
                if (value := _text(raw)) is not None
            )
    return values


def parse_count(
    payload: Any,
    *,
    source_url: str = COUNT_URL,
) -> CaseLawCount:
    """Validate the native count response used to drive traversal."""

    root = _mapping(payload, "count response")
    missing = sorted({"count", "restricted"}.difference(root))
    if missing:
        raise ColoradoOpinionsSourceChangedError(
            "count_fields_changed",
            "Colorado case-law count response lacks required fields",
            details={"missing": missing, "observed": sorted(root)},
        )
    count = _required_int(root["count"], "count", minimum=0)
    restricted = _required_bool(root["restricted"], "restricted")
    contract = {
        "root_keys": sorted(str(key) for key in root),
        "count_type": type(root["count"]).__name__,
        "restricted_type": type(root["restricted"]).__name__,
    }
    return CaseLawCount(
        count=count,
        restricted=restricted,
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(contract),
    )


def parse_search_page(
    payload: Any,
    *,
    page_number: int,
    source_url: str = SEARCH_URL,
) -> CaseLawPage:
    """Validate a short-page-safe native search page."""

    if page_number <= 0:
        raise ValueError("page_number must be positive")
    root = _mapping(payload, "search response")
    required = {"count", "debug", "results", "partial_results"}
    missing = sorted(required.difference(root))
    if missing:
        raise ColoradoOpinionsSourceChangedError(
            "search_fields_changed",
            "Colorado case-law search response lacks required fields",
            details={"missing": missing, "observed": sorted(root)},
        )
    count = _required_int(root["count"], "count", minimum=0)
    _required_bool(root["debug"], "debug")
    partial_results = _required_bool(
        root["partial_results"],
        "partial_results",
    )
    raw_results = root["results"]
    if not isinstance(raw_results, list):
        raise ColoradoOpinionsSourceChangedError(
            "results_field_changed",
            "Colorado case-law results is not an array",
        )
    if len(raw_results) > NATIVE_PAGE_SIZE:
        raise ColoradoOpinionsSourceChangedError(
            "native_page_size_changed",
            "Colorado case-law page exceeds the verified native page size",
            details={
                "observed": len(raw_results),
                "verified_page_size": NATIVE_PAGE_SIZE,
            },
        )
    if count == 0 and raw_results:
        raise ColoradoOpinionsSourceChangedError(
            "empty_count_has_results",
            "Colorado case-law returned results with count zero",
        )

    results: list[Mapping[str, Any]] = []
    result_keys: set[str] = set()
    property_labels: set[str] = set()
    for index, raw_result in enumerate(raw_results):
        result = _mapping(raw_result, f"results[{index}]")
        _required_int(result.get("id"), f"results[{index}].id", minimum=1)
        _required_text(result.get("title"), f"results[{index}].title")
        result_type = _required_text(
            result.get("type"),
            f"results[{index}].type",
        )
        if result_type != "document":
            raise ColoradoOpinionsSourceChangedError(
                "result_type_changed",
                "Colorado case-law search returned a non-document result",
                details={"index": index, "type": result_type},
            )
        _iso_date(
            result.get("document_date"),
            f"results[{index}].document_date",
        )
        parent = _mapping(
            result.get("parent"),
            f"results[{index}].parent",
        )
        _required_text(
            parent.get("title"),
            f"results[{index}].parent.title",
        )
        raw_properties = result.get("properties")
        if not isinstance(raw_properties, list):
            raise ColoradoOpinionsSourceChangedError(
                "properties_field_changed",
                "Colorado case-law expanded properties is not an array",
                details={"index": index},
            )
        for property_index, raw_property in enumerate(raw_properties):
            item = _mapping(
                raw_property,
                f"results[{index}].properties[{property_index}]",
            )
            descriptor = _mapping(
                item.get("property"),
                (
                    f"results[{index}].properties[{property_index}]"
                    ".property"
                ),
            )
            label = _required_text(
                descriptor.get("label"),
                (
                    f"results[{index}].properties[{property_index}]"
                    ".property.label"
                ),
            )
            if not isinstance(item.get("values"), list):
                raise ColoradoOpinionsSourceChangedError(
                    "property_values_changed",
                    "Colorado case-law property values is not an array",
                    details={
                        "result_index": index,
                        "property_index": property_index,
                    },
                )
            property_labels.add(label)
        result_keys.update(str(key) for key in result)
        results.append(result)

    contract = {
        "root_keys": sorted(str(key) for key in root),
        "result_keys": sorted(result_keys),
        "property_labels": sorted(property_labels),
        "native_page_size": NATIVE_PAGE_SIZE,
        "short_pages_may_precede_exhaustion": True,
    }
    return CaseLawPage(
        results=tuple(results),
        count=count,
        partial_results=partial_results,
        page_number=page_number,
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(contract),
    )


def _court_payload(court_key: str) -> dict[str, Any]:
    spec = COURTS[court_key]
    return {
        "court_id": spec["court_id"],
        "native_court_id": spec["native_id"],
        "name": spec["name"],
        "state_code": STATE_CODE,
        "court_level": "appellate",
        "official_url": spec["release_url"],
    }


def _canonical_case_law_ref(court_key: str, document_id: int) -> str:
    values = (SOURCE_ID, court_key, str(document_id))
    encoded = "/".join(quote(value, safe=".-_") for value in values)
    return f"COOPINION:{encoded}"


def normalize_search_results(
    results: Sequence[Mapping[str, Any]],
    *,
    court_key: str,
    total_count: int,
) -> list[dict[str, Any]]:
    """Normalize stable case-law identities without publication inference."""

    spec = COURTS[court_key]
    normalized: list[dict[str, Any]] = []
    for index, result in enumerate(results):
        document_id = _required_int(
            result.get("id"),
            f"results[{index}].id",
            minimum=1,
        )
        title = _required_text(
            result.get("title"),
            f"results[{index}].title",
        )
        parent = _mapping(result.get("parent"), f"results[{index}].parent")
        observed_court = _required_text(
            parent.get("title"),
            f"results[{index}].parent.title",
        )
        if observed_court.casefold() != spec["name"].casefold():
            raise ColoradoOpinionsSourceChangedError(
                "court_filter_leaked",
                "Colorado case-law result belongs to another court",
                details={
                    "expected": spec["name"],
                    "observed": observed_court,
                    "document_id": document_id,
                },
            )
        docket_numbers = _property_values(result, "Docket Number")
        citations = _property_values(result, "Citation")
        property_dates = _property_values(result, "Decision Date")
        decision_date = _iso_date(
            result.get("document_date"),
            f"results[{index}].document_date",
        )
        iceberg = result.get("iceberg_record_info")
        iceberg_record_id = None
        if isinstance(iceberg, Mapping):
            iceberg_record_id = _text(iceberg.get("iceberg_record_id"))
        normalized.append(
            {
                "record_kind": "appellate_opinion_index",
                "source_id": SOURCE_ID,
                "component_source_id": SOURCE_ID,
                "adapter_family": ADAPTER_FAMILY,
                "canonical_ref": _canonical_case_law_ref(
                    court_key,
                    document_id,
                ),
                "native_document_id": str(document_id),
                "iceberg_record_id": iceberg_record_id,
                "title": title,
                "court": _court_payload(court_key),
                "docket_number": docket_numbers[0] if docket_numbers else None,
                "docket_numbers": docket_numbers,
                "decision_date": decision_date,
                "source_decision_date_values": property_dates,
                "citations": citations,
                "publication_status": None,
                "publication_status_available": False,
                "publication_note": (
                    "The historical index result does not state publication "
                    "status."
                ),
                "is_authorized": result.get("is_authorized"),
                "document_url": f"{CASE_LAW_BASE_URL}/vid/{document_id}",
                "metadata_url": (
                    f"{CASE_LAW_BASE_URL}/vid/{document_id}.json"
                ),
                "full_text_url": (
                    f"{CASE_LAW_BASE_URL}/vid/{document_id}/content"
                ),
                "pdf_url": f"{CASE_LAW_BASE_URL}/pdf/{document_id}",
                "source_url": f"{CASE_LAW_BASE_URL}/vid/{document_id}",
                "source_role": "historical_searchable_case_law_index",
                "current_release_freshness": False,
                "search_context": {"source_total_count": total_count},
            }
        )
    return normalized


def _parse_release_date(value: str, field: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise ColoradoOpinionsSourceChangedError(
            "release_date_missing",
            f"Colorado release page lacks {field}",
        )
    for pattern in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(normalized, pattern).date().isoformat()
        except ValueError:
            pass
    raise ColoradoOpinionsSourceChangedError(
        "release_date_changed",
        f"Colorado release page returned an invalid {field}",
        details={"field": field, "value": normalized},
    )


def _release_ref(court_key: str, *identity: str) -> str:
    values = (RELEASE_SOURCE_ID, court_key, *identity)
    encoded = "/".join(quote(value, safe=".-_") for value in values)
    return f"COOPINION-RELEASE:{encoded}"


def parse_supreme_releases(
    html: str,
    *,
    source_url: str = SUPREME_RELEASE_URL,
) -> ReleasePage:
    """Parse the Supreme Court's current fiscal-year opinion release index."""

    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select(".field--name-field-text")
    body = next(
        (
            candidate
            for candidate in candidates
            if "Below are the Supreme Court Case Opinions"
            in candidate.get_text(" ", strip=True)
        ),
        None,
    )
    if body is None:
        raise ColoradoOpinionsSourceChangedError(
            "supreme_release_container_changed",
            "Colorado Supreme Court release-page container was not found",
        )

    current_date: str | None = None
    records: list[dict[str, Any]] = []
    for paragraph in body.find_all("p"):
        paragraph_text = _text(paragraph.get_text(" ", strip=True))
        if paragraph_text is None:
            continue
        try:
            current_date = _parse_release_date(
                paragraph_text,
                "release date",
            )
            continue
        except ColoradoOpinionsSourceChangedError:
            pass
        link = paragraph.find(
            "a",
            href=re.compile(r"(?:^|https://www\.coloradojudicial\.gov)/node/\d+"),
        )
        if link is None:
            continue
        if current_date is None:
            raise ColoradoOpinionsSourceChangedError(
                "supreme_release_date_missing",
                "Colorado Supreme Court opinion precedes its release date",
            )
        href = _required_text(link.get("href"), "supreme opinion node URL")
        node_match = re.search(r"/node/(\d+)", href)
        if node_match is None:
            raise ColoradoOpinionsSourceChangedError(
                "supreme_node_identity_changed",
                "Colorado Supreme Court opinion link lacks a node identity",
                details={"href": href},
            )
        docket_match = APPELLATE_DOCKET_RE.search(paragraph_text)
        docket_number = docket_match.group(0).upper() if docket_match else None
        title = (
            _text(paragraph_text[docket_match.end() :].lstrip(" ,;:-"))
            if docket_match
            else paragraph_text
        )
        citation = _text(link.get_text(" ", strip=True))
        if citation and not SUPREME_CITATION_RE.fullmatch(citation):
            citation = None
        node_id = node_match.group(1)
        records.append(
            {
                "record_kind": "current_supreme_opinion_release",
                "source_id": RELEASE_SOURCE_ID,
                "component_source_id": RELEASE_SOURCE_ID,
                "adapter_family": ADAPTER_FAMILY,
                "canonical_ref": _release_ref(
                    "supreme",
                    node_id,
                    docket_number or citation or "undocketed",
                ),
                "native_release_id": node_id,
                "title": title,
                "court": _court_payload("supreme"),
                "docket_number": docket_number,
                "decision_date": current_date,
                "release_date": current_date,
                "citation": citation,
                "publication_status": "published",
                "publication_stage": "slip_opinion",
                "is_opinion": True,
                "source_url": urljoin(JUDICIAL_BASE_URL, href),
                "download_source": urljoin(JUDICIAL_BASE_URL, href),
                "pdf_resolution": "follow_verified_release_node",
                "release_page_url": source_url,
                "historical_complement_source_id": SOURCE_ID,
                "source_role": "current_supreme_opinion_release_index",
                "current_release_freshness": True,
            }
        )

    if not records and "Case Opinions" not in body.get_text(" ", strip=True):
        raise ColoradoOpinionsSourceChangedError(
            "supreme_release_records_changed",
            "Colorado Supreme Court release page lacks its opinion marker",
        )
    contract = {
        "container_class": "field--name-field-text",
        "node_link_pattern": "/node/<id>",
        "record_fields": [
            "citation",
            "decision_date",
            "docket_number",
            "native_release_id",
            "source_url",
            "title",
        ],
        "record_kind": "current_supreme_opinion_release",
    }
    return ReleasePage(
        records=tuple(records),
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(contract),
    )


def parse_appeals_releases(
    html: str,
    *,
    source_url: str = APPEALS_RELEASE_URL,
) -> ReleasePage:
    """Parse one Court of Appeals announcement-packet listing page."""

    soup = BeautifulSoup(html, "html.parser")
    view = soup.select_one(".view-case-announcements-search-api")
    if view is None:
        raise ColoradoOpinionsSourceChangedError(
            "appeals_release_container_changed",
            "Colorado Court of Appeals announcement view was not found",
        )
    records: list[dict[str, Any]] = []
    for article in view.select("article.node--type-case-announcement"):
        native_id = _text(article.get("data-history-node-id"))
        if native_id is None or not native_id.isdigit():
            raise ColoradoOpinionsSourceChangedError(
                "announcement_identity_changed",
                "Colorado Court of Appeals announcement lacks a node ID",
            )
        date_node = article.select_one(".field--name-title")
        if date_node is None:
            raise ColoradoOpinionsSourceChangedError(
                "announcement_date_missing",
                "Colorado Court of Appeals announcement lacks a date",
                details={"native_release_id": native_id},
            )
        release_date = _parse_release_date(
            date_node.get_text(" ", strip=True),
            "announcement date",
        )
        node_link = article.find("a", href=re.compile(r"/node/\d+"))
        pdf_link = article.find("a", href=re.compile(r"\.pdf(?:$|\?)", re.I))
        if node_link is None or pdf_link is None:
            raise ColoradoOpinionsSourceChangedError(
                "announcement_links_changed",
                "Colorado Court of Appeals announcement lacks node or PDF link",
                details={"native_release_id": native_id},
            )
        node_url = urljoin(
            JUDICIAL_BASE_URL,
            _required_text(node_link.get("href"), "announcement node URL"),
        )
        pdf_url = urljoin(
            JUDICIAL_BASE_URL,
            _required_text(pdf_link.get("href"), "announcement PDF URL"),
        )
        records.append(
            {
                "record_kind": "appellate_release_announcement_packet",
                "source_id": RELEASE_SOURCE_ID,
                "component_source_id": RELEASE_SOURCE_ID,
                "adapter_family": ADAPTER_FAMILY,
                "canonical_ref": _release_ref("appeals", native_id),
                "native_release_id": native_id,
                "title": (
                    "Colorado Court of Appeals announcements — "
                    f"{release_date}"
                ),
                "court": _court_payload("appeals"),
                "docket_number": None,
                "decision_date": None,
                "release_date": release_date,
                "publication_status": None,
                "publication_scope": ["published", "unpublished"],
                "is_opinion": False,
                "packet_role": (
                    "announcement index containing published and unpublished "
                    "opinion listings"
                ),
                "source_url": node_url,
                "download_source": pdf_url,
                "pdf_url": pdf_url,
                "release_page_url": source_url,
                "historical_complement_source_id": SOURCE_ID,
                "source_role": "current_appeals_announcement_packet",
                "current_release_freshness": True,
            }
        )

    empty = view.select_one(".view-empty")
    if not records and empty is None:
        raise ColoradoOpinionsSourceChangedError(
            "appeals_release_records_changed",
            "Colorado Court of Appeals announcement view has no records or "
            "authoritative empty marker",
        )
    next_link = view.find("a", rel=lambda value: value and "next" in value)
    next_page_url = None
    if next_link is not None:
        next_page_url = urljoin(
            source_url,
            _required_text(next_link.get("href"), "announcement next page"),
        )
    contract = {
        "container_class": "view-case-announcements-search-api",
        "article_class": "node--type-case-announcement",
        "record_fields": [
            "native_release_id",
            "pdf_url",
            "release_date",
            "source_url",
        ],
        "record_kind": "appellate_release_announcement_packet",
        "next_link": "rel=next",
    }
    return ReleasePage(
        records=tuple(records),
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(contract),
        next_page_url=next_page_url,
    )


def parse_supreme_release_node_pdf(
    html: str,
    *,
    source_url: str,
) -> str:
    """Resolve one Supreme Court release node to its exact opinion PDF."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    heading = soup.find("h1")
    heading_text = _text(heading.get_text(" ", strip=True)) if heading else None
    if (
        "Case Opinion PDF" not in page_text
        or heading_text is None
        or APPELLATE_DOCKET_RE.fullmatch(heading_text) is None
    ):
        raise ColoradoOpinionsSelectionError(
            "release_node_not_opinion",
            "Colorado Judicial node is not a Supreme Court opinion release",
            details={"source_url": source_url, "heading": heading_text},
        )
    candidates: list[str] = []
    for link in soup.find_all("a", href=True):
        href = _required_text(link.get("href"), "release-node PDF URL")
        if re.search(r"\.pdf(?:$|[?#])", href, flags=re.IGNORECASE) is None:
            continue
        candidate = urljoin(source_url, href)
        try:
            component_source_id, validated_url = _validated_pdf_source(
                candidate
            )
        except ColoradoOpinionsError:
            continue
        if component_source_id == RELEASE_SOURCE_ID:
            candidates.append(validated_url)
    unique_candidates = list(dict.fromkeys(candidates))
    if len(unique_candidates) != 1:
        raise ColoradoOpinionsSourceChangedError(
            "release_node_pdf_changed",
            "Colorado Supreme Court opinion node did not expose one opinion "
            "PDF",
            details={
                "source_url": source_url,
                "candidate_count": len(unique_candidates),
            },
        )
    return unique_candidates[0]


def _search_selection(query_text: str, court_key: str) -> dict[str, str]:
    query_value = _text(query_text)
    if query_value is None:
        raise ColoradoOpinionsSelectionError(
            "query_required",
            "Colorado case-law search requires a non-empty query",
        )
    return {
        "include_local_exclusive": "true",
        "hide_ct6": "true",
        "q": query_value,
        "type": "document",
        "jurisdiction": "US",
        "content_type": "2",
        "court": COURTS[court_key]["native_id"],
        "per_page": str(NATIVE_PAGE_SIZE),
        "include": "parent,abstract,properties_with_ids",
    }


def _query_fingerprint(parameters: Mapping[str, str]) -> str:
    return hashlib.sha256(
        canonical_json(dict(parameters)).encode("utf-8")
    ).hexdigest()


def _search_cursor(
    *,
    parameters: Mapping[str, str],
    page: int,
    row: int,
    seen: int,
    anchor: int,
) -> str:
    return (
        f"colorado-opinions:{CURSOR_VERSION}:query:"
        f"{_query_fingerprint(parameters)}:page:{page}:row:{row}:seen:{seen}:"
        f"anchor:{anchor}"
    )


def _search_cursor_position(
    cursor: str | None,
    *,
    parameters: Mapping[str, str],
) -> tuple[int, int, int, int | None]:
    if cursor is None:
        return 1, 0, 0, None
    match = SEARCH_CURSOR_PATTERN.fullmatch(cursor)
    if match is None:
        raise ColoradoOpinionsSelectionError(
            "invalid_cursor",
            "cursor must be a Colorado case-law continuation returned by a "
            "prior search",
            details={"cursor": cursor},
        )
    expected = _query_fingerprint(parameters)
    observed = match.group("query")
    if observed != expected:
        raise ColoradoOpinionsSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different Colorado case-law search parameters",
            details={
                "cursor_query_fingerprint": observed,
                "search_query_fingerprint": expected,
            },
        )
    page = int(match.group("page"))
    row = int(match.group("row"))
    seen = int(match.group("seen"))
    if page <= 0:
        raise ColoradoOpinionsSelectionError(
            "invalid_cursor",
            "cursor page must be positive",
        )
    return page, row, seen, int(match.group("anchor"))


def _release_parameters(args: argparse.Namespace) -> dict[str, str]:
    return {
        "court": args.court,
        "year": str(args.year) if args.year is not None else "",
        "query": _text(args.query_text) or "",
    }


def _release_cursor(
    *,
    parameters: Mapping[str, str],
    offset: int,
    anchor: str,
) -> str:
    return (
        f"colorado-opinion-releases:{CURSOR_VERSION}:query:"
        f"{_query_fingerprint(parameters)}:offset:{offset}:anchor:{anchor}"
    )


def _release_cursor_offset(
    cursor: str | None,
    *,
    parameters: Mapping[str, str],
) -> tuple[int, str | None]:
    if cursor is None:
        return 0, None
    match = RELEASE_CURSOR_PATTERN.fullmatch(cursor)
    if match is None:
        raise ColoradoOpinionsSelectionError(
            "invalid_cursor",
            "cursor must be a Colorado release continuation returned by a "
            "prior releases query",
            details={"cursor": cursor},
        )
    expected = _query_fingerprint(parameters)
    observed = match.group("query")
    if observed != expected:
        raise ColoradoOpinionsSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different Colorado release parameters",
            details={
                "cursor_query_fingerprint": observed,
                "release_query_fingerprint": expected,
            },
        )
    return int(match.group("offset")), match.group("anchor")


def _canonical_ref_anchor(record: Mapping[str, Any]) -> str:
    canonical_ref = _required_text(
        record.get("canonical_ref"),
        "record canonical reference",
    )
    return hashlib.sha256(canonical_ref.encode("utf-8")).hexdigest()


def _document_court_key(metadata: Mapping[str, Any]) -> str:
    parent = _mapping(metadata.get("parent"), "document.parent")
    alternative_key = _text(parent.get("alternative_key"))
    if alternative_key:
        native_suffix = alternative_key.rsplit("_", 1)[-1]
        native_id = f"14024_{native_suffix}"
        court_key = COURT_BY_NATIVE_ID.get(native_id)
        if court_key:
            return court_key
    title = _text(parent.get("title"))
    if title:
        court_key = COURT_BY_NAME.get(title.casefold())
        if court_key:
            return court_key
    raise ColoradoOpinionsSourceChangedError(
        "document_court_changed",
        "Colorado case-law document belongs to an unknown court",
        details={"parent_title": title, "alternative_key": alternative_key},
    )


def _content_metadata(content_html: str) -> dict[str, Any]:
    soup = BeautifulSoup(content_html, "html.parser")
    if soup.select_one(".ldml-decision") is None:
        raise ColoradoOpinionsSourceChangedError(
            "document_content_changed",
            "Colorado case-law full-text response lacks its decision container",
        )
    docket_numbers: list[str] = []
    citations: list[str] = []
    seen_dockets: set[str] = set()
    seen_citations: set[str] = set()
    for node in soup.select(".ldml-cite"):
        value = _text(node.get_text(" ", strip=True))
        if value is None:
            continue
        docket_match = APPELLATE_DOCKET_RE.search(value)
        if value.casefold().startswith("no.") or docket_match:
            docket = (
                docket_match.group(0).upper()
                if docket_match
                else value.removeprefix("No.").strip().rstrip(".")
            )
            if docket and docket.casefold() not in seen_dockets:
                seen_dockets.add(docket.casefold())
                docket_numbers.append(docket)
            continue
        if value.casefold() not in seen_citations:
            seen_citations.add(value.casefold())
            citations.append(value)
    court_node = soup.select_one(".ldml-court")
    source_court = (
        _text(court_node.get_text(" ", strip=True))
        if court_node is not None
        else None
    )
    plain_text = _text(soup.get_text(" ", strip=True)) or ""
    return {
        "docket_numbers": docket_numbers,
        "citations": citations,
        "source_court_text": source_court,
        "full_text": plain_text,
    }


def normalize_document(document: CaseLawDocument) -> dict[str, Any]:
    metadata = document.metadata
    document_id = _required_int(
        metadata.get("id"),
        "document.id",
        minimum=1,
    )
    court_key = _document_court_key(metadata)
    title = _required_text(metadata.get("title"), "document.title")
    doc_date = _iso_date(metadata.get("doc_date"), "document.doc_date")
    content_fields: dict[str, Any] = {
        "docket_numbers": [],
        "citations": [],
        "source_court_text": None,
        "full_text": None,
    }
    if document.content_html is not None:
        content_fields = _content_metadata(document.content_html)
    docket_numbers = content_fields["docket_numbers"]
    return {
        "record_kind": "appellate_opinion_document",
        "source_id": SOURCE_ID,
        "component_source_id": SOURCE_ID,
        "adapter_family": ADAPTER_FAMILY,
        "canonical_ref": _canonical_case_law_ref(court_key, document_id),
        "native_document_id": str(document_id),
        "title": title,
        "court": _court_payload(court_key),
        "docket_number": docket_numbers[0] if docket_numbers else None,
        "docket_numbers": docket_numbers,
        "decision_date": doc_date,
        "citations": content_fields["citations"],
        "publication_status": None,
        "publication_status_available": False,
        "published_at": _text(metadata.get("published_at")),
        "document_url": f"{CASE_LAW_BASE_URL}/vid/{document_id}",
        "metadata_url": document.metadata_url,
        "full_text_url": document.content_url,
        "pdf_url": f"{CASE_LAW_BASE_URL}/pdf/{document_id}",
        "source_url": f"{CASE_LAW_BASE_URL}/vid/{document_id}",
        "source_court_text": content_fields["source_court_text"],
        "full_text": content_fields["full_text"],
        "full_text_format": (
            "text/plain derived from source HTML"
            if document.content_html is not None
            else None
        ),
        "full_text_html": document.content_html,
        "full_text_sha256": document.content_sha256,
        "metadata_schema_fingerprint": (
            document.metadata_schema_fingerprint
        ),
        "source_role": "historical_case_law_document",
        "current_release_freshness": False,
    }


def _validated_pdf_source(source: str) -> tuple[str, str]:
    normalized = _required_text(source, "PDF source")
    if normalized.isdigit():
        document_id = int(normalized)
        if document_id <= 0:
            raise ColoradoOpinionsSelectionError(
                "document_id_invalid",
                "document ID must be positive",
            )
        return SOURCE_ID, f"{CASE_LAW_BASE_URL}/pdf/{document_id}"

    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").casefold()
    path = unquote(parsed.path)
    if (
        parsed.scheme == "https"
        and host == "research.coloradojudicial.gov"
        and re.fullmatch(r"/pdf/\d+", path)
    ):
        return SOURCE_ID, normalized
    if (
        parsed.scheme == "https"
        and host == "www.coloradojudicial.gov"
        and re.fullmatch(r"/node/\d+", path)
    ):
        return RELEASE_SOURCE_ID, normalized
    if (
        parsed.scheme == "https"
        and host == "www.coloradojudicial.gov"
        and (
            re.fullmatch(
                r"/system/files/opinions-\d{4}-\d{2}/"
                r"[A-Za-z0-9._-]+\.pdf",
                path,
                flags=re.IGNORECASE,
            )
            or re.fullmatch(
                r"/sites/default/files/\d{4}-\d{2}/"
                r"\d{2}-\d{2}-\d{2}\.pdf",
                path,
                flags=re.IGNORECASE,
            )
        )
    ):
        return RELEASE_SOURCE_ID, normalized
    raise ColoradoOpinionsSelectionError(
        "pdf_source_unknown",
        "PDF source is not a verified Colorado appellate artifact route",
        details={"source": normalized},
    )


class ColoradoOpinionsClient:
    """Retrying anonymous client for both Colorado appellate components."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        sleeper: Any = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0
        self._verified_document_ids: set[int] = set()

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        accept: str,
    ) -> Any:
        headers = {
            "Accept": accept,
            "User-Agent": self.user_agent,
            "Referer": (
                CASE_LAW_BASE_URL
                if url.startswith(CASE_LAW_BASE_URL)
                else JUDICIAL_BASE_URL
            ),
        }
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise ColoradoOpinionsError(
                        "transport_error",
                        "Colorado opinions request failed after "
                        f"{attempt} attempts: {error}",
                        category="transport",
                        retryable=True,
                        details={"attempts": attempt, "url": url},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(getattr(response, "status_code", 0))
            if status_code in self.retry_policy.retry_statuses:
                retry_after: float | None = None
                raw_retry_after = getattr(response, "headers", {}).get(
                    "Retry-After"
                )
                if raw_retry_after:
                    try:
                        retry_after = max(0.0, float(raw_retry_after))
                    except ValueError:
                        retry_after = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                raise ColoradoOpinionsError(
                    (
                        "rate_limited"
                        if status_code == 429
                        else "http_status_error"
                    ),
                    f"Colorado opinions returned HTTP {status_code}",
                    status=(
                        ResultStatus.RATE_LIMITED
                        if status_code == 429
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=(
                        "rate_limit"
                        if status_code == 429
                        else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code, "url": url},
                )
            if status_code in {401, 403}:
                raise ColoradoOpinionsError(
                    "source_access_failed",
                    f"Colorado opinions returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code, "url": url},
                )
            if status_code in {404, 410}:
                raise ColoradoOpinionsSourceChangedError(
                    "source_route_missing",
                    f"Colorado opinions route returned HTTP {status_code}",
                    details={"status_code": status_code, "url": url},
                )
            if status_code < 200 or status_code >= 300:
                raise ColoradoOpinionsError(
                    "http_status_error",
                    f"Colorado opinions returned HTTP {status_code}",
                    category="transport",
                    details={"status_code": status_code, "url": url},
                )
            return response
        raise ColoradoOpinionsError(
            "transport_error",
            f"Colorado opinions request failed: {last_error}",
            category="transport",
            retryable=True,
        )

    def _json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[Any, str]:
        response = self._request(
            url,
            params=params,
            accept="application/json",
        )
        media_type = _media_type(response)
        if media_type and media_type != "application/json":
            raise ColoradoOpinionsSourceChangedError(
                "json_media_type_changed",
                "Colorado opinions JSON route returned another media type",
                details={"content_type": media_type, "url": url},
            )
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise ColoradoOpinionsSourceChangedError(
                "json_response_invalid",
                "Colorado opinions route returned invalid JSON",
                details={"url": url},
            ) from error
        return payload, _response_url(response, url)

    def fetch_count(
        self,
        selection: Mapping[str, str],
    ) -> CaseLawCount:
        payload, source_url = self._json(
            COUNT_URL,
            params={**selection, "page": "1", "g": "2"},
        )
        return parse_count(payload, source_url=source_url)

    def fetch_search_page(
        self,
        selection: Mapping[str, str],
        *,
        page_number: int,
    ) -> CaseLawPage:
        payload, source_url = self._json(
            SEARCH_URL,
            params={**selection, "page": str(page_number)},
        )
        return parse_search_page(
            payload,
            page_number=page_number,
            source_url=source_url,
        )

    def search(
        self,
        selection: Mapping[str, str],
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> CaseLawBatch:
        (
            page_number,
            row_offset,
            seen_before_page,
            cursor_anchor,
        ) = _search_cursor_position(cursor, parameters=selection)
        count = self.fetch_count(selection)

        collected: list[Mapping[str, Any]] = []
        pages: list[CaseLawPage] = []
        seen_ids: set[int] = set()
        next_cursor: str | None = None
        incomplete_error: ColoradoOpinionsError | None = None
        source_consumed = seen_before_page + row_offset
        target_count = count.count

        while source_consumed < target_count or not pages:
            page = self.fetch_search_page(
                selection,
                page_number=page_number,
            )
            pages.append(page)
            if len(pages) == 1 and page.count != count.count:
                target_count = page.count
                incomplete_error = ColoradoOpinionsPaginationError(
                    "Colorado case-law count endpoint and search page "
                    "disagreed; traversal followed the search-page count",
                    details={
                        "count_endpoint": count.count,
                        "search_page_count": page.count,
                        "page": page_number,
                    },
                )
            elif len(pages) > 1 and page.count != target_count:
                incomplete_error = ColoradoOpinionsPaginationError(
                    "Colorado case-law search-page count changed during "
                    "traversal; traversal retained its initial snapshot count",
                    details={
                        "snapshot_count": target_count,
                        "observed_search_page_count": page.count,
                        "page": page_number,
                    },
                )
            if source_consumed > target_count:
                incomplete_error = ColoradoOpinionsPaginationError(
                    "Colorado case-law cursor position exceeds the current "
                    "reported result count",
                    details={
                        "cursor_position": source_consumed,
                        "source_total_count": target_count,
                    },
                )
            if page.partial_results or count.restricted:
                incomplete_error = ColoradoOpinionsError(
                    "source_returned_partial_results",
                    "Colorado case-law source marked the result set partial "
                    "or restricted",
                    status=ResultStatus.PARTIAL,
                    category="access",
                    details={
                        "partial_results": page.partial_results,
                        "restricted": count.restricted,
                    },
                )
            if row_offset > len(page.results):
                raise ColoradoOpinionsSelectionError(
                    "cursor_out_of_range",
                    "cursor row exceeds the native Colorado result page",
                    details={
                        "page": page_number,
                        "row": row_offset,
                        "page_rows": len(page.results),
                    },
                )
            if cursor_anchor is not None:
                if row_offset <= 0:
                    raise ColoradoOpinionsSelectionError(
                        "invalid_cursor",
                        "continuation cursor lacks a consumed-page boundary",
                    )
                observed_anchor = _required_int(
                    page.results[row_offset - 1].get("id"),
                    "cursor boundary result.id",
                    minimum=1,
                )
                if observed_anchor != cursor_anchor:
                    raise ColoradoOpinionsSelectionError(
                        "cursor_snapshot_changed",
                        "Colorado case-law results changed at the continuation "
                        "boundary",
                        details={
                            "expected_document_id": cursor_anchor,
                            "observed_document_id": observed_anchor,
                            "page": page_number,
                            "row": row_offset,
                        },
                    )
                cursor_anchor = None
            if not page.results:
                if target_count == 0 and page_number == 1 and row_offset == 0:
                    break
                incomplete_error = ColoradoOpinionsPaginationError(
                    "Colorado case-law returned an empty page before its "
                    "reported count was reached",
                    details={
                        "page": page_number,
                        "source_total_count": target_count,
                        "source_rows_consumed": source_consumed,
                    },
                )
                break

            duplicate_found = False
            for raw_result in page.results:
                document_id = _required_int(
                    raw_result.get("id"),
                    "result.id",
                    minimum=1,
                )
                if document_id in seen_ids:
                    incomplete_error = ColoradoOpinionsPaginationError(
                        "Colorado case-law repeated a document across native "
                        "pages",
                        details={
                            "document_id": document_id,
                            "page": page_number,
                        },
                    )
                    duplicate_found = True
                    break
                seen_ids.add(document_id)
            if duplicate_found:
                break

            available = list(page.results[row_offset:])
            if source_consumed + len(available) > target_count:
                incomplete_error = ColoradoOpinionsPaginationError(
                    "Colorado case-law returned more rows than its snapshot "
                    "count",
                    details={
                        "page": page_number,
                        "snapshot_count": target_count,
                        "rows_through_page": source_consumed + len(available),
                    },
                )
            remaining = (
                None if limit is None else limit - len(collected)
            )
            if remaining is not None and remaining < len(available):
                collected.extend(available[:remaining])
                next_cursor = _search_cursor(
                    parameters=selection,
                    page=page_number,
                    row=row_offset + remaining,
                    seen=seen_before_page,
                    anchor=_required_int(
                        available[remaining - 1].get("id"),
                        "cursor boundary result.id",
                        minimum=1,
                    ),
                )
                source_consumed += remaining
                break

            collected.extend(available)
            source_consumed += len(available)
            next_seen = seen_before_page + len(page.results)
            if remaining is not None and remaining == len(available):
                if source_consumed < target_count:
                    next_cursor = _search_cursor(
                        parameters=selection,
                        page=page_number,
                        row=row_offset + remaining,
                        seen=seen_before_page,
                        anchor=_required_int(
                            available[-1].get("id"),
                            "cursor boundary result.id",
                            minimum=1,
                        ),
                    )
                break
            if page.partial_results:
                break
            if source_consumed >= target_count:
                break
            page_number += 1
            row_offset = 0
            seen_before_page = next_seen

        return CaseLawBatch(
            results=tuple(collected),
            total_count=target_count,
            pages_fetched=len(pages),
            next_cursor=next_cursor,
            source_urls=(count.source_url,)
            + tuple(page.source_url for page in pages),
            schema_fingerprints=(count.schema_fingerprint,)
            + tuple(page.schema_fingerprint for page in pages),
            incomplete_error=incomplete_error,
        )

    def fetch_document(
        self,
        document_id: int,
        *,
        include_content: bool = True,
    ) -> CaseLawDocument:
        if document_id <= 0:
            raise ColoradoOpinionsSelectionError(
                "document_id_invalid",
                "document ID must be positive",
            )
        metadata_url = f"{CASE_LAW_BASE_URL}/vid/{document_id}.json"
        payload, resolved_metadata_url = self._json(metadata_url)
        metadata = _mapping(payload, "document metadata")
        observed_id = _required_int(
            metadata.get("id"),
            "document.id",
            minimum=1,
        )
        if observed_id != document_id:
            raise ColoradoOpinionsSourceChangedError(
                "document_identity_mismatch",
                "Colorado case-law metadata returned another document",
                details={
                    "requested": document_id,
                    "observed": observed_id,
                },
            )
        _document_court_key(metadata)
        self._verified_document_ids.add(document_id)
        content_html: str | None = None
        content_url: str | None = None
        content_sha256: str | None = None
        if include_content:
            requested_content_url = (
                f"{CASE_LAW_BASE_URL}/vid/{document_id}/content"
            )
            response = self._request(
                requested_content_url,
                accept="text/html",
            )
            media_type = _media_type(response)
            if media_type and media_type != "text/html":
                raise ColoradoOpinionsSourceChangedError(
                    "content_media_type_changed",
                    "Colorado case-law content route returned another media "
                    "type",
                    details={"content_type": media_type},
                )
            content_html = str(getattr(response, "text", ""))
            _content_metadata(content_html)
            content_url = _response_url(response, requested_content_url)
            content_sha256 = hashlib.sha256(
                content_html.encode("utf-8")
            ).hexdigest()
        contract = {
            "root_keys": sorted(str(key) for key in metadata),
            "parent_keys": sorted(
                str(key)
                for key in _mapping(
                    metadata.get("parent"),
                    "document.parent",
                )
            ),
        }
        return CaseLawDocument(
            metadata=metadata,
            content_html=content_html,
            metadata_url=resolved_metadata_url,
            content_url=content_url,
            metadata_schema_fingerprint=_schema_fingerprint(contract),
            content_sha256=content_sha256,
        )

    def fetch_pdf(self, source: str) -> PDFArtifact:
        component_source_id, source_url = _validated_pdf_source(source)
        parsed_source = urlsplit(source_url)
        if component_source_id == SOURCE_ID:
            document_match = re.fullmatch(
                r"/pdf/(\d+)",
                unquote(parsed_source.path),
            )
            if document_match is None:
                raise ColoradoOpinionsSelectionError(
                    "pdf_source_unknown",
                    "Colorado case-law PDF lacks a document identity",
                )
            document_id = int(document_match.group(1))
            if document_id not in self._verified_document_ids:
                self.fetch_document(document_id, include_content=False)
        elif re.fullmatch(r"/node/\d+", unquote(parsed_source.path)):
            html, resolved_node_url = self._html(source_url)
            source_url = parse_supreme_release_node_pdf(
                html,
                source_url=resolved_node_url,
            )
        response = self._request(
            source_url,
            accept="application/pdf",
        )
        resolved_url = _response_url(response, source_url)
        resolved_component, _ = _validated_pdf_source(resolved_url)
        if resolved_component != component_source_id:
            raise ColoradoOpinionsSourceChangedError(
                "pdf_redirect_changed_component",
                "Colorado appellate PDF redirected to another component",
                details={
                    "requested_url": source_url,
                    "resolved_url": resolved_url,
                },
            )
        media_type = _media_type(response)
        content = bytes(getattr(response, "content", b""))
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise ColoradoOpinionsSourceChangedError(
                "pdf_response_invalid",
                "Colorado appellate artifact route did not return a PDF",
                details={
                    "content_type": media_type,
                    "magic_hex": content[:8].hex(),
                    "url": resolved_url,
                },
            )
        disposition = str(
            getattr(response, "headers", {}).get(
                "Content-Disposition",
                getattr(response, "headers", {}).get(
                    "content-disposition",
                    "",
                ),
            )
        )
        filename_match = re.search(
            r"""filename\*?=(?:UTF-8''|")?([^";]+)""",
            disposition,
            flags=re.IGNORECASE,
        )
        return PDFArtifact(
            content=content,
            source_url=resolved_url,
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
            file_name=(
                unquote(filename_match.group(1).strip())
                if filename_match
                else Path(urlsplit(resolved_url).path).name or None
            ),
            component_source_id=component_source_id,
        )

    def _html(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[str, str]:
        response = self._request(
            url,
            params=params,
            accept="text/html,application/xhtml+xml",
        )
        media_type = _media_type(response)
        if media_type and media_type not in {
            "text/html",
            "application/xhtml+xml",
        }:
            raise ColoradoOpinionsSourceChangedError(
                "release_media_type_changed",
                "Colorado release page returned another media type",
                details={"content_type": media_type, "url": url},
            )
        return (
            str(getattr(response, "text", "")),
            _response_url(response, url),
        )

    def fetch_supreme_release_page(self) -> ReleasePage:
        html, source_url = self._html(SUPREME_RELEASE_URL)
        return parse_supreme_releases(html, source_url=source_url)

    def fetch_appeals_release_page(
        self,
        *,
        page_number: int = 0,
        year: int | None = None,
        query_text: str | None = None,
    ) -> ReleasePage:
        if page_number < 0:
            raise ValueError("page_number must not be negative")
        params: dict[str, str] = {"page": str(page_number)}
        if year is not None:
            params["f[0]"] = f"case_announcement_coa_year:{year}"
        query_value = _text(query_text)
        if query_value:
            params["search_api_fulltext"] = query_value
        html, source_url = self._html(
            APPEALS_RELEASE_URL,
            params=params,
        )
        return parse_appeals_releases(html, source_url=source_url)

    def fetch_releases(
        self,
        *,
        court_key: str,
        year: int | None,
        query_text: str | None,
        limit: int | None,
        cursor: str | None,
    ) -> ReleaseCollection:
        parameters = {
            "court": court_key,
            "year": str(year) if year is not None else "",
            "query": _text(query_text) or "",
        }
        offset, cursor_anchor = _release_cursor_offset(
            cursor,
            parameters=parameters,
        )
        pages: list[ReleasePage] = []
        incomplete_error: ColoradoOpinionsError | None = None
        if court_key == "supreme":
            page = self.fetch_supreme_release_page()
            pages.append(page)
            records = list(page.records)
            if year is not None:
                records = [
                    record
                    for record in records
                    if str(record["release_date"]).startswith(f"{year:04d}-")
                ]
            query_value = _text(query_text)
            if query_value:
                folded = query_value.casefold()
                records = [
                    record
                    for record in records
                    if folded
                    in canonical_json(record).casefold()
                ]
        else:
            records = []
            page_number = 0
            seen_pages: set[int] = set()
            seen_page_signatures: set[str] = set()
            seen_record_refs: set[str] = set()
            while True:
                if page_number in seen_pages:
                    raise ColoradoOpinionsPaginationError(
                        "Colorado Court of Appeals release pagination stalled",
                        details={"page": page_number},
                    )
                seen_pages.add(page_number)
                page = self.fetch_appeals_release_page(
                    page_number=page_number,
                    year=year,
                    query_text=query_text,
                )
                pages.append(page)
                page_refs = [
                    _required_text(
                        record.get("canonical_ref"),
                        "release canonical reference",
                    )
                    for record in page.records
                ]
                page_signature = hashlib.sha256(
                    canonical_json(page_refs).encode("utf-8")
                ).hexdigest()
                new_records = [
                    record
                    for record, canonical_ref in zip(
                        page.records,
                        page_refs,
                        strict=True,
                    )
                    if canonical_ref not in seen_record_refs
                ]
                if (
                    page_signature in seen_page_signatures
                    or (page.records and not new_records)
                ):
                    incomplete_error = ColoradoOpinionsPaginationError(
                        "Colorado Court of Appeals release pagination "
                        "repeated content without identity progress",
                        details={
                            "page": page_number,
                            "record_count": len(page.records),
                        },
                    )
                    break
                seen_page_signatures.add(page_signature)
                seen_record_refs.update(page_refs)
                records.extend(new_records)
                if page.next_page_url is None:
                    break
                if not new_records:
                    incomplete_error = ColoradoOpinionsPaginationError(
                        "Colorado Court of Appeals release pagination "
                        "advertised another page without identity progress",
                        details={"page": page_number},
                    )
                    break
                next_values = parse_qs(
                    urlsplit(page.next_page_url).query
                ).get("page", [])
                if not next_values or not next_values[-1].isdigit():
                    raise ColoradoOpinionsSourceChangedError(
                        "release_next_page_changed",
                        "Colorado Court of Appeals next link lacks a page "
                        "number",
                        details={"next_page_url": page.next_page_url},
                    )
                next_page = int(next_values[-1])
                if next_page <= page_number:
                    raise ColoradoOpinionsPaginationError(
                        "Colorado Court of Appeals release pagination did not "
                        "advance",
                        details={
                            "page": page_number,
                            "next_page": next_page,
                        },
                    )
                page_number = next_page

        if offset > len(records):
            raise ColoradoOpinionsSelectionError(
                "cursor_out_of_range",
                "release cursor points beyond available records",
                details={"offset": offset, "records": len(records)},
            )
        if cursor_anchor is not None:
            if offset <= 0:
                raise ColoradoOpinionsSelectionError(
                    "invalid_cursor",
                    "release continuation lacks a consumed-record boundary",
                )
            observed_anchor = _canonical_ref_anchor(records[offset - 1])
            if observed_anchor != cursor_anchor:
                raise ColoradoOpinionsSelectionError(
                    "cursor_snapshot_changed",
                    "Colorado release records changed at the continuation "
                    "boundary",
                    details={
                        "offset": offset,
                        "expected_anchor": cursor_anchor,
                        "observed_anchor": observed_anchor,
                    },
                )
        remaining = records[offset:]
        selected = remaining if limit is None else remaining[:limit]
        next_cursor = None
        next_offset = offset + len(selected)
        if next_offset < len(records):
            next_cursor = _release_cursor(
                parameters=parameters,
                offset=next_offset,
                anchor=_canonical_ref_anchor(selected[-1]),
            )
        return ReleaseCollection(
            records=tuple(selected),
            pages_fetched=len(pages),
            next_cursor=next_cursor,
            source_urls=tuple(page.source_url for page in pages),
            schema_fingerprints=tuple(
                page.schema_fingerprint for page in pages
            ),
            incomplete_error=incomplete_error,
        )


def _selection_for_args(args: argparse.Namespace) -> dict[str, str]:
    if args.command == "search":
        return _search_selection(args.query_text, args.court)
    if args.command == "docket":
        return _search_selection(args.docket_number, args.court)
    if args.command == "probe":
        return _search_selection(SENTINEL_QUERY, "supreme")
    return {}


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    if args.command == "releases":
        source = RELEASE_METADATA
        parameters: Mapping[str, Any] = _release_parameters(args)
    elif (
        args.command == "probe"
        and getattr(args, "component", "all") == "releases"
    ):
        source = RELEASE_METADATA
        parameters = {"component": "releases"}
    elif args.command == "download":
        try:
            component_source_id, _source_url = _validated_pdf_source(
                args.source
            )
        except ColoradoOpinionsError:
            component_source_id = SOURCE_ID
        source = (
            RELEASE_METADATA
            if component_source_id == RELEASE_SOURCE_ID
            else CASE_LAW_METADATA
        )
        parameters = {
            "source": args.source,
            "destination": str(args.destination),
        }
    elif args.command == "document":
        source = CASE_LAW_METADATA
        parameters = {
            "document_id": args.document_id,
            "include_content": not args.metadata_only,
        }
    else:
        source = CASE_LAW_METADATA
        try:
            parameters = _selection_for_args(args)
        except ColoradoOpinionsError:
            parameters = {
                key: str(value) if isinstance(value, Path) else value
                for key, value in vars(args).items()
                if key
                not in {
                    "json_out",
                    "max_attempts",
                    "minimum_interval",
                    "output",
                    "timeout",
                }
            }
    return PublicRecordsQuery(
        source=source,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Colorado",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _make_client(args: argparse.Namespace) -> ColoradoOpinionsClient:
    return ColoradoOpinionsClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _public_error(error: ColoradoOpinionsError) -> PublicRecordsError:
    return PublicRecordsError(
        code=error.code,
        message=str(error),
        category=error.category,
        retryable=error.retryable,
        details=error.details,
    )


def _error_result(
    query: PublicRecordsQuery,
    error: ColoradoOpinionsError,
    *,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [_public_error(error)],
        warnings=warnings,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
    *,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=warnings,
    )


def _search_result(
    query: PublicRecordsQuery,
    batch: CaseLawBatch,
    *,
    court_key: str,
) -> PublicRecordsResult:
    records = normalize_search_results(
        batch.results,
        court_key=court_key,
        total_count=batch.total_count,
    )
    if batch.incomplete_error is not None:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [_public_error(batch.incomplete_error)],
            records=records,
            next_cursor=batch.next_cursor,
            warnings=CASE_LAW_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=CASE_LAW_WARNINGS,
    )


def _execute_command(
    args: argparse.Namespace,
    client: ColoradoOpinionsClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command in {"search", "docket"}:
        selection = _selection_for_args(args)
        batch = client.search(
            selection,
            limit=args.limit,
            cursor=args.cursor,
        )
        return _search_result(
            query,
            batch,
            court_key=args.court,
        )

    if args.command == "releases":
        collection = client.fetch_releases(
            court_key=args.court,
            year=args.year,
            query_text=args.query_text,
            limit=args.limit,
            cursor=args.cursor,
        )
        if collection.incomplete_error is not None:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                [_public_error(collection.incomplete_error)],
                records=list(collection.records),
                next_cursor=collection.next_cursor,
                warnings=RELEASE_WARNINGS,
            )
        return PublicRecordsResult.success(
            query,
            list(collection.records),
            next_cursor=collection.next_cursor,
            warnings=RELEASE_WARNINGS,
        )

    if args.command == "document":
        document = client.fetch_document(
            args.document_id,
            include_content=not args.metadata_only,
        )
        return PublicRecordsResult.success(
            query,
            [normalize_document(document)],
            warnings=CASE_LAW_WARNINGS,
        )

    if args.command == "download":
        artifact = client.fetch_pdf(args.source)
        destination = Path(args.destination)
        if destination.exists() and not args.overwrite:
            raise ColoradoOpinionsSelectionError(
                "destination_exists",
                f"destination exists; pass --overwrite: {destination}",
                details={"destination": str(destination)},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.name}.",
                suffix=".part",
                dir=destination.parent,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(artifact.content)
                handle.flush()
            temporary_path.replace(destination)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        record_kind = (
            "appellate_opinion_pdf_artifact"
            if artifact.component_source_id == SOURCE_ID
            else "appellate_release_pdf_artifact"
        )
        record = {
            "record_kind": record_kind,
            "source_id": artifact.component_source_id,
            "component_source_id": artifact.component_source_id,
            "adapter_family": ADAPTER_FAMILY,
            "canonical_ref": (
                "COOPINION-ARTIFACT:"
                f"{artifact.component_source_id}:{artifact.sha256}"
            ),
            "source_url": artifact.source_url,
            "artifact_path": str(destination),
            "file_name": artifact.file_name,
            "media_type": artifact.media_type,
            "byte_length": len(artifact.content),
            "sha256": artifact.sha256,
            "access_state": "public",
            "certified_record": False,
        }
        warnings = (
            CASE_LAW_WARNINGS
            if artifact.component_source_id == SOURCE_ID
            else RELEASE_WARNINGS
        )
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[str(destination)],
            warnings=warnings,
        )

    if args.command == "probe":
        component = getattr(args, "component", "all")
        component_sources: list[dict[str, Any]] = []
        probe_error: ColoradoOpinionsError | None = None
        if component in {"archive", "all"}:
            selection = _selection_for_args(args)
            count = client.fetch_count(selection)
            page = client.fetch_search_page(selection, page_number=1)
            sentinel = next(
                (
                    result
                    for result in page.results
                    if int(result.get("id", 0)) == SENTINEL_DOCUMENT_ID
                ),
                None,
            )
            if sentinel is None:
                raise ColoradoOpinionsSourceChangedError(
                    "sentinel_missing",
                    "Colorado case-law sentinel is missing from its exact "
                    "query",
                    details={
                        "query": SENTINEL_QUERY,
                        "document_id": SENTINEL_DOCUMENT_ID,
                    },
                )
            if count.restricted or page.partial_results:
                probe_error = ColoradoOpinionsError(
                    "source_returned_partial_results",
                    "Colorado case-law probe was marked partial or restricted",
                    status=ResultStatus.PARTIAL,
                    category="access",
                    details={
                        "count_restricted": count.restricted,
                        "page_partial_results": page.partial_results,
                    },
                )
            elif page.count != count.count:
                probe_error = ColoradoOpinionsPaginationError(
                    "Colorado case-law probe count endpoints disagreed",
                    details={
                        "count_endpoint": count.count,
                        "search_page_count": page.count,
                    },
                )
            document = client.fetch_document(
                SENTINEL_DOCUMENT_ID,
                include_content=True,
            )
            artifact = client.fetch_pdf(str(SENTINEL_DOCUMENT_ID))
            component_sources.append(
                {
                    "source_id": SOURCE_ID,
                    "role": "historical_search_full_text_and_pdf",
                    "base_url": CASE_LAW_BASE_URL,
                    "search_url": SEARCH_URL,
                    "count_url": COUNT_URL,
                    "sentinel_query": SENTINEL_QUERY,
                    "sentinel_result_count": count.count,
                    "sentinel_document_id": str(SENTINEL_DOCUMENT_ID),
                    "search_schema_fingerprint": page.schema_fingerprint,
                    "count_schema_fingerprint": count.schema_fingerprint,
                    "metadata_schema_fingerprint": (
                        document.metadata_schema_fingerprint
                    ),
                    "full_text_byte_length": len(
                        (document.content_html or "").encode("utf-8")
                    ),
                    "full_text_sha256": document.content_sha256,
                    "pdf_byte_length": len(artifact.content),
                    "pdf_media_type": artifact.media_type,
                    "pdf_sha256": artifact.sha256,
                }
            )
        if component in {"releases", "all"}:
            supreme_page = client.fetch_supreme_release_page()
            appeals_page = client.fetch_appeals_release_page(page_number=0)
            component_sources.append(
                {
                    "source_id": RELEASE_SOURCE_ID,
                    "role": "current_release_freshness",
                    "supreme_url": SUPREME_RELEASE_URL,
                    "appeals_url": APPEALS_RELEASE_URL,
                    "supreme_current_page_records": len(
                        supreme_page.records
                    ),
                    "appeals_current_page_packets": len(
                        appeals_page.records
                    ),
                    "supreme_schema_fingerprint": (
                        supreme_page.schema_fingerprint
                    ),
                    "appeals_schema_fingerprint": (
                        appeals_page.schema_fingerprint
                    ),
                    "appeals_records_are_opinions": False,
                }
            )
        records: list[dict[str, Any]] = []
        for component_record in component_sources:
            component_source_id = str(component_record["source_id"])
            component_name = (
                "archive"
                if component_source_id == SOURCE_ID
                else "releases"
            )
            if component_name == "archive":
                schema_payload = {
                    key: component_record.get(key)
                    for key in (
                        "search_schema_fingerprint",
                        "count_schema_fingerprint",
                        "metadata_schema_fingerprint",
                    )
                }
                artifact_payload = {
                    key: component_record.get(key)
                    for key in (
                        "sentinel_document_id",
                        "sentinel_result_count",
                        "full_text_sha256",
                        "pdf_byte_length",
                        "pdf_media_type",
                    )
                }
                result_count = component_record["sentinel_result_count"]
                source_url = CASE_LAW_BASE_URL
                native_pagination: Mapping[str, Any] = {
                    "kind": "page_number_with_count",
                    "page_size": NATIVE_PAGE_SIZE,
                    "short_page_is_not_exhaustion": True,
                    "cursor": (
                        "query-bound page, row, consumed-row, and boundary "
                        "continuation"
                    ),
                }
            else:
                schema_payload = {
                    key: component_record.get(key)
                    for key in (
                        "supreme_schema_fingerprint",
                        "appeals_schema_fingerprint",
                    )
                }
                artifact_payload = {
                    key: component_record.get(key)
                    for key in (
                        "supreme_current_page_records",
                        "appeals_current_page_packets",
                        "appeals_records_are_opinions",
                    )
                }
                result_count = (
                    int(component_record["supreme_current_page_records"])
                    + int(component_record["appeals_current_page_packets"])
                )
                source_url = JUDICIAL_BASE_URL
                native_pagination = {
                    "supreme": "single_current_release_page",
                    "court_of_appeals": (
                        "zero_based_next_links_with_identity_progress"
                    ),
                }
            records.append(
                {
                    "record_kind": "source_health_check",
                    "source_id": component_source_id,
                    "component_source_id": component_source_id,
                    "adapter_family": ADAPTER_FAMILY,
                    "canonical_ref": (
                        f"STATECOURT:{component_source_id}/source-health/"
                        f"probe-{component_name}"
                    ),
                    "source_url": source_url,
                    "status": "ok",
                    "checked_at": datetime.now()
                    .astimezone()
                    .isoformat(timespec="seconds"),
                    "authentication": "none",
                    "probe_component": component_name,
                    "result_count": result_count,
                    "schema_fingerprint": _schema_fingerprint(
                        schema_payload
                    ),
                    "artifact_identity": _schema_fingerprint(
                        artifact_payload
                    ),
                    "component_sources": [component_record],
                    "native_pagination": native_pagination,
                    "source_roles_kept_distinct": True,
                }
            )
        if probe_error is not None:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                [_public_error(probe_error)],
                records=records,
                warnings=CASE_LAW_WARNINGS + RELEASE_WARNINGS,
            )
        return PublicRecordsResult.success(
            query,
            records,
            warnings=CASE_LAW_WARNINGS + RELEASE_WARNINGS,
        )

    raise ColoradoOpinionsSelectionError(
        "unsupported_command",
        f"unsupported Colorado opinions command: {args.command}",
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: ColoradoOpinionsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Colorado appellate opinion or release operation."""

    query = build_query(args)
    warnings = (
        RELEASE_WARNINGS
        if args.command == "releases"
        or (
            args.command == "probe"
            and getattr(args, "component", "all") == "releases"
        )
        else CASE_LAW_WARNINGS
    )
    if (
        access_decision is not None
        and access_decision.get("source_id") is not None
        and access_decision.get("source_id") != query.source.source_id
    ):
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_decision_source_mismatch",
                    message=(
                        "Catalog decision belongs to another source component"
                    ),
                    category="access",
                    retryable=False,
                    details={
                        "decision_source_id": access_decision.get("source_id"),
                        "query_source_id": query.source.source_id,
                    },
                )
            ],
            warnings=warnings,
        )
        if log_results:
            _log(query, None)
        return result
    if access_decision is not None and not access_decision.get(
        "allowed", False
    ):
        result = _decision_failure(
            query,
            access_decision,
            warnings=warnings,
        )
        if log_results:
            _log(query, None)
        return result

    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except ColoradoOpinionsError as error:
        result = _error_result(query, error, warnings=warnings)
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
            warnings=warnings,
        )
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=warnings,
        )
    finally:
        if owns_client:
            source_client.close()

    if log_results:
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
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            count,
        )
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Colorado opinions {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Colorado opinions {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        print(
            f"  {record.get('docket_number') or '?'} | "
            f"{record.get('record_kind')} | "
            f"{record.get('title') or record.get('file_name') or '?'}"
        )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _year(value: str) -> int:
    parsed = int(value)
    if parsed < 1800 or parsed > 9999:
        raise argparse.ArgumentTypeError("year is out of range")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between source requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="Maximum attempts for transient source failures",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Colorado appellate case law and current release surfaces"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search the historical Colorado case-law index",
    )
    search.add_argument("query_text")
    search.add_argument("--court", choices=tuple(COURTS), required=True)
    search.add_argument("--limit", type=_positive_int)
    search.add_argument("--cursor")
    _add_runtime_and_output(search)

    docket = subparsers.add_parser(
        "docket",
        help="Search the historical index by appellate docket text",
    )
    docket.add_argument("docket_number")
    docket.add_argument("--court", choices=tuple(COURTS), required=True)
    docket.add_argument("--limit", type=_positive_int)
    docket.add_argument("--cursor")
    _add_runtime_and_output(docket)

    releases = subparsers.add_parser(
        "releases",
        help="List current Judicial Branch release records or packets",
    )
    releases.add_argument("--court", choices=tuple(COURTS), required=True)
    releases.add_argument("--year", type=_year)
    releases.add_argument("--query", dest="query_text")
    releases.add_argument("--limit", type=_positive_int)
    releases.add_argument("--cursor")
    _add_runtime_and_output(releases)

    document = subparsers.add_parser(
        "document",
        help="Retrieve case-law metadata and full text",
    )
    document.add_argument("document_id", type=_positive_int)
    document.add_argument(
        "--metadata-only",
        action="store_true",
        help="Retrieve metadata without the full-text route",
    )
    _add_runtime_and_output(document)

    download = subparsers.add_parser(
        "download",
        help="Download a verified opinion or release PDF",
    )
    download.add_argument(
        "source",
        help=(
            "Case-law document ID, Supreme Court release-node URL, or "
            "verified Colorado appellate PDF URL"
        ),
    )
    download.add_argument("destination", type=Path)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify both official source components and their distinct roles",
    )
    probe.add_argument(
        "--component",
        choices=("archive", "releases", "all"),
        default="all",
        help="Probe one source component or both",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> int:
    args = build_parser().parse_args()
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
