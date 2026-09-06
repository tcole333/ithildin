#!/usr/bin/env python3
"""Query official Pennsylvania appellate opinion and order postings.

The public Pennsylvania Courts pages use an anonymous JSON endpoint for
Supreme, Superior, and Commonwealth Court posting metadata. This adapter
exhausts native pagination by default and keeps the resulting opinion/order
corpus distinct from UJS docket sheets and AOPC bulk case-record access.

Examples:
    uv run python tools/query_pa_opinions.py list --court supreme \
        --date-from 2026-07-28 --date-to 2026-07-28 --json
    uv run python tools/query_pa_opinions.py list --court superior \
        --year 2026 --month 7 --author "Olson" --output opinions.json
    uv run python tools/query_pa_opinions.py docket "69 WAL 2026" \
        --court supreme --json
    uv run python tools/query_pa_opinions.py download \
        "https://www.pacourts.us/assets/opinions/Supreme/out/example.pdf?cb=1" \
        /tmp/pa-opinion.pdf --output /tmp/pa-opinion-receipt.json
    uv run python tools/query_pa_opinions.py probe --json
    uv run python tools/query_pa_opinions.py sentinel --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, unquote, urlsplit

import requests

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


SOURCE_ID = "us-pa-appellate-opinions-postings"
STATE_CODE = "PA"
STATE_GEOID = "42"
BASE_URL = "https://www.pacourts.us"
API_URL = f"{BASE_URL}/api/opinion"
SITE_SEARCH_URL = f"{BASE_URL}/site-search"
UJS_DOCKET_URL = "https://ujsportal.pacourts.us/CaseSearch"
AOPC_RECORDS_URL = f"{BASE_URL}/public-records/public-records-forms"
COURTLISTENER_URL = "https://www.courtlistener.com/"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
SENTINEL_DOCKET = "69 WAL 2026"
SENTINEL_YEAR = 2026
SENTINEL_OPINION_ID = 85654
SENTINEL_POSTING_ID = 94487

COURTS: dict[str, dict[str, Any]] = {
    "supreme": {
        "api_value": "SUPREME",
        "enum_value": 3,
        "asset_directory": "Supreme",
        "court_id": "pa-supreme-court",
        "name": "Supreme Court of Pennsylvania",
        "page_url": f"{BASE_URL}/courts/supreme-court/court-opinions",
        "rss_url": f"{BASE_URL}/Rss/Opinions/Supreme/",
    },
    "superior": {
        "api_value": "SUPERIOR",
        "enum_value": 2,
        "asset_directory": "Superior",
        "court_id": "pa-superior-court",
        "name": "Superior Court of Pennsylvania",
        "page_url": f"{BASE_URL}/courts/superior-court/court-opinions",
        "rss_url": f"{BASE_URL}/Rss/Opinions/Superior/",
    },
    "commonwealth": {
        "api_value": "COMMONWEALTH",
        "enum_value": 0,
        "asset_directory": "Commonwealth",
        "court_id": "pa-commonwealth-court",
        "name": "Commonwealth Court of Pennsylvania",
        "page_url": f"{BASE_URL}/courts/commonwealth-court/court-opinions",
        "rss_url": f"{BASE_URL}/Rss/Opinions/Commonwealth/",
    },
}
COURT_BY_API_VALUE = {
    str(spec["api_value"]): key for key, spec in COURTS.items()
}
COURT_BY_ASSET_DIRECTORY = {
    str(spec["asset_directory"]): key for key, spec in COURTS.items()
}

_REQUIRED_PAGE_FIELDS = frozenset(
    {
        "HasNext",
        "HasPrevious",
        "Items",
        "PageNumber",
        "PageSize",
        "TotalItems",
        "TotalPages",
    }
)
_DOCKET_RE = re.compile(
    r"\b("
    r"\d+(?:-\d+)*(?:\s*(?:&|,)\s*\d+(?:-\d+)*)?"
    r"\s+(?:WAL|MAL|EAL|WAP|MAP|EAP|WM|MM|EM|EDA|MDA|WDA|"
    r"C\.?\s*D\.?|M\.?\s*D\.?)\s+\d{4}"
    r")\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_PDF_PATH_RE = re.compile(
    r"^/assets/opinions/(Supreme|Superior|Commonwealth)/out/([^/]+\.pdf)$",
    re.IGNORECASE,
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Pennsylvania Appellate Opinions and Postings",
    source_role="official_appellate_opinion_order_posting_corpus",
    base_url=API_URL,
    dataset_id="pacourts-appellate-opinions",
    metadata={
        "authority": "Unified Judicial System of Pennsylvania",
        "operator": "Administrative Office of Pennsylvania Courts",
        "state_code": STATE_CODE,
        "authentication": "none",
        "api_endpoint": API_URL,
        "native_pagination": "page_number",
        "observed_native_page_size": 20,
        "court_types": [
            spec["api_value"] for spec in COURTS.values()
        ],
        "evidentiary_role": "official_opinion_and_order_publication",
    },
)

SOURCE_WARNINGS = (
    "This source is an official appellate opinion/order posting corpus, not "
    "a complete docket or a repository of the parties' underlying filings.",
    "Use the UJS docket source for case chronology and docket-sheet metadata; "
    "use the applicable prothonotary for an official certified copy.",
)


class PAOpinionsError(RuntimeError):
    """Source, transport, or selection error with envelope semantics."""

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


class PAOpinionsSelectionError(PAOpinionsError):
    """The caller supplied an unsupported source-native selection."""

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


class PAOpinionsSourceChangedError(PAOpinionsError):
    """The official source no longer matches its verified contract."""

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


class PAOpinionsPaginationError(PAOpinionsError):
    """Native pagination changed or became incomplete during traversal."""

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
class PAOpinionsPage:
    """One verified page from the official opinions API."""

    items: tuple[Mapping[str, Any], ...]
    page_number: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class PAOpinionsCollection:
    """An exhaustive or explicitly partial native-page traversal."""

    items: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    page_size: int
    total_items: int
    total_pages: int
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: PAOpinionsError | None = None


@dataclass(frozen=True)
class PAOpinionPDF:
    """Validated official PDF bytes and integrity metadata."""

    content: bytes
    source_url: str
    media_type: str
    sha256: str
    court_key: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise PAOpinionsSourceChangedError(
            "required_field_missing",
            f"Pennsylvania opinions response lacks {field_name}",
            details={"field": field_name},
        )
    return normalized


def _required_int(
    value: Any,
    field_name: str,
    *,
    minimum: int,
) -> int:
    if isinstance(value, bool):
        raise PAOpinionsSourceChangedError(
            "integer_field_changed",
            f"Pennsylvania opinions {field_name} is not an integer",
            details={"field": field_name, "value": value},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise PAOpinionsSourceChangedError(
            "integer_field_changed",
            f"Pennsylvania opinions {field_name} is not an integer",
            details={"field": field_name, "value": value},
        ) from error
    if parsed < minimum:
        raise PAOpinionsSourceChangedError(
            "integer_field_out_of_range",
            f"Pennsylvania opinions {field_name} is out of range",
            details={
                "field": field_name,
                "value": parsed,
                "minimum": minimum,
            },
        )
    return parsed


def _required_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise PAOpinionsSourceChangedError(
            "boolean_field_changed",
            f"Pennsylvania opinions {field_name} is not boolean",
            details={"field": field_name, "value": value},
        )
    return value


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PAOpinionsSourceChangedError(
            "object_field_changed",
            f"Pennsylvania opinions {field_name} is not an object",
            details={"field": field_name},
        )
    return value


def _schema_fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _selection_date(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise PAOpinionsSelectionError(
            "date_required",
            f"{field_name} is required",
            details={"field": field_name},
        )
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as error:
        raise PAOpinionsSelectionError(
            "date_invalid",
            f"{field_name} must use YYYY-MM-DD: {normalized}",
            details={"field": field_name, "value": normalized},
        ) from error


def _source_datetime(value: Any, field_name: str) -> tuple[str | None, str | None]:
    raw = _text(value)
    if raw is None or raw.startswith("0001-01-01"):
        return raw, None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise PAOpinionsSourceChangedError(
            "date_field_changed",
            f"Pennsylvania opinions returned an invalid {field_name}",
            details={"field": field_name, "value": raw},
        ) from error
    return raw, parsed.isoformat()


def _source_date(value: Any, field_name: str) -> tuple[str | None, str | None]:
    raw, normalized = _source_datetime(value, field_name)
    return raw, normalized[:10] if normalized else None


def _docket_key(value: str) -> str:
    return " ".join(value.upper().replace(".", "").split())


def extract_docket_numbers(caption: str) -> list[str]:
    """Extract common Pennsylvania appellate docket formats from a caption."""

    values: list[str] = []
    seen: set[str] = set()
    for match in _DOCKET_RE.finditer(caption):
        value = " ".join(match.group(1).split())
        key = _docket_key(value)
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
    return values


def _infer_year(docket_number: str) -> int:
    years = _YEAR_RE.findall(docket_number)
    if not years:
        raise PAOpinionsSelectionError(
            "docket_year_required",
            "The official endpoint requires a date/year partition; pass "
            "--year when the docket text does not contain one.",
            details={"docket_number": docket_number},
        )
    return int(years[-1])


def parse_page(
    payload: Any,
    *,
    source_url: str = API_URL,
) -> PAOpinionsPage:
    """Validate one native API page without silently accepting schema drift."""

    if not isinstance(payload, Mapping):
        raise PAOpinionsSourceChangedError(
            "response_root_changed",
            "Pennsylvania opinions response is not a JSON object",
        )
    missing = sorted(_REQUIRED_PAGE_FIELDS.difference(payload))
    if missing:
        raise PAOpinionsSourceChangedError(
            "pagination_fields_changed",
            "Pennsylvania opinions response lacks pagination fields",
            details={"missing": missing, "observed": sorted(payload)},
        )

    raw_items = payload["Items"]
    if not isinstance(raw_items, list):
        raise PAOpinionsSourceChangedError(
            "items_field_changed",
            "Pennsylvania opinions Items is not an array",
        )
    page_number = _required_int(payload["PageNumber"], "PageNumber", minimum=1)
    page_size = _required_int(payload["PageSize"], "PageSize", minimum=1)
    total_items = _required_int(payload["TotalItems"], "TotalItems", minimum=0)
    total_pages = _required_int(payload["TotalPages"], "TotalPages", minimum=1)
    has_next = _required_bool(payload["HasNext"], "HasNext")
    has_previous = _required_bool(payload["HasPrevious"], "HasPrevious")

    expected_pages = max(1, math.ceil(total_items / page_size))
    if total_pages != expected_pages:
        raise PAOpinionsSourceChangedError(
            "pagination_math_changed",
            "Pennsylvania opinions pagination totals are inconsistent",
            details={
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "expected_total_pages": expected_pages,
            },
        )
    if page_number > total_pages:
        raise PAOpinionsSourceChangedError(
            "page_number_out_of_range",
            "Pennsylvania opinions page number exceeds total pages",
            details={
                "page_number": page_number,
                "total_pages": total_pages,
            },
        )
    if has_next != (page_number < total_pages) or has_previous != (
        page_number > 1
    ):
        raise PAOpinionsSourceChangedError(
            "pagination_flags_changed",
            "Pennsylvania opinions pagination flags are inconsistent",
            details={
                "page_number": page_number,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
            },
        )
    if len(raw_items) > page_size:
        raise PAOpinionsSourceChangedError(
            "page_size_exceeded",
            "Pennsylvania opinions returned more items than PageSize",
            details={"items": len(raw_items), "page_size": page_size},
        )
    if total_items == 0 and raw_items:
        raise PAOpinionsSourceChangedError(
            "empty_total_has_items",
            "Pennsylvania opinions returned items with TotalItems zero",
        )

    items: list[Mapping[str, Any]] = []
    item_keys: set[str] = set()
    posting_keys: set[str] = set()
    for item_index, value in enumerate(raw_items):
        item = _mapping(value, f"Items[{item_index}]")
        _required_int(item.get("Id"), f"Items[{item_index}].Id", minimum=1)
        _required_int(
            item.get("CourtType"),
            f"Items[{item_index}].CourtType",
            minimum=0,
        )
        _required_text(
            item.get("Caption"),
            f"Items[{item_index}].Caption",
        )
        postings = item.get("Postings")
        if not isinstance(postings, list):
            raise PAOpinionsSourceChangedError(
                "postings_field_changed",
                "Pennsylvania opinions Postings is not an array",
                details={"item_index": item_index},
            )
        for posting_index, posting_value in enumerate(postings):
            posting = _mapping(
                posting_value,
                f"Items[{item_index}].Postings[{posting_index}]",
            )
            _required_int(
                posting.get("OpinionId"),
                f"Items[{item_index}].Postings[{posting_index}].OpinionId",
                minimum=1,
            )
            _required_text(
                posting.get("FileName"),
                f"Items[{item_index}].Postings[{posting_index}].FileName",
            )
            posting_keys.update(str(key) for key in posting)
        item_keys.update(str(key) for key in item)
        items.append(item)

    contract = {
        "root_keys": sorted(str(key) for key in payload),
        "item_keys": sorted(item_keys),
        "posting_keys": sorted(posting_keys),
        "native_pagination": "page_number",
    }
    return PAOpinionsPage(
        items=tuple(items),
        page_number=page_number,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
        schema_fingerprint=_schema_fingerprint(contract),
        source_url=source_url,
    )


def _court_payload(court_key: str) -> dict[str, Any]:
    spec = COURTS[court_key]
    return {
        "court_id": spec["court_id"],
        "native_court_id": spec["api_value"],
        "name": spec["name"],
        "state_code": STATE_CODE,
        "court_level": "appellate",
        "official_url": spec["page_url"],
    }


def _posting_identity(
    opinion_id: int,
    posting_index: int,
    posting: Mapping[str, Any],
) -> str:
    raw_id = posting.get("Id")
    if not isinstance(raw_id, bool):
        try:
            posting_id = int(raw_id)
        except (TypeError, ValueError):
            posting_id = 0
        if posting_id > 0:
            return str(posting_id)
    fingerprint_input = {
        "file_name": _text(posting.get("FileName")),
        "opinion_id": opinion_id,
        "posting_index": posting_index,
        "posting_type_id": _text(posting.get("PostingTypeId")),
    }
    digest = hashlib.sha256(
        canonical_json(fingerprint_input).encode("utf-8")
    ).hexdigest()[:20]
    return f"{opinion_id}:posting:{digest}"


def _pdf_url(court_key: str, posting: Mapping[str, Any]) -> str:
    spec = COURTS[court_key]
    file_name = _required_text(posting.get("FileName"), "posting.FileName")
    if "/" in file_name or "\\" in file_name:
        raise PAOpinionsSourceChangedError(
            "opinion_filename_changed",
            "Pennsylvania opinions returned a filename containing a path",
            details={"file_name": file_name},
        )
    file_version = _required_int(
        posting.get("FileVersion", 1),
        "posting.FileVersion",
        minimum=1,
    )
    return (
        f"{BASE_URL}/assets/opinions/{spec['asset_directory']}/out/"
        f"{quote(file_name, safe='')}?cb={file_version}"
    )


def _posting_type(posting: Mapping[str, Any]) -> tuple[str | None, str | None]:
    code = _text(posting.get("PostingTypeId"))
    post_type = posting.get("PostType")
    if not isinstance(post_type, Mapping):
        return code, None
    candidates = (
        _text(post_type.get("PostingTypeId")),
        _text(post_type.get("PostingTypeCode")),
    )
    label = next(
        (
            candidate
            for candidate in candidates
            if candidate is not None and candidate.casefold() != (code or "").casefold()
        ),
        candidates[0] or candidates[1],
    )
    return code, label


def _publication_type(posting: Mapping[str, Any]) -> str | None:
    publication = posting.get("PublicationType")
    if isinstance(publication, Mapping):
        return _text(publication.get("Description"))
    return None


def _posting_author(
    item: Mapping[str, Any],
    posting: Mapping[str, Any],
) -> str | None:
    author = posting.get("Author")
    if isinstance(author, Mapping):
        named = _text(author.get("AuthorName"))
        if named:
            return named
    author_id = _text(posting.get("AuthorId"))
    if author_id and not author_id.isdigit():
        return author_id
    return _text(item.get("Author"))


def _canonical_ref(
    court_key: str,
    opinion_id: int,
    native_posting_id: str,
) -> str:
    values = (SOURCE_ID, court_key, str(opinion_id), native_posting_id)
    encoded = "/".join(quote(value, safe=".-_") for value in values)
    return f"PAOPINION:{encoded}"


def normalize_collection(
    collection: PAOpinionsCollection,
    *,
    court_key: str,
    selection: Mapping[str, str],
    exact_docket: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Flatten API opinions into one stable record per downloadable posting."""

    spec = COURTS[court_key]
    records: list[dict[str, Any]] = []
    for item_index, item in enumerate(collection.items):
        opinion_id = _required_int(
            item.get("Id"),
            f"items[{item_index}].Id",
            minimum=1,
        )
        observed_court_type = _required_int(
            item.get("CourtType"),
            f"items[{item_index}].CourtType",
            minimum=0,
        )
        if observed_court_type != spec["enum_value"]:
            raise PAOpinionsSourceChangedError(
                "court_type_mismatch",
                "Pennsylvania opinions returned a record for another court",
                details={
                    "expected": spec["enum_value"],
                    "observed": observed_court_type,
                    "opinion_id": opinion_id,
                },
            )
        caption = _required_text(
            item.get("Caption"),
            f"items[{item_index}].Caption",
        )
        docket_numbers = extract_docket_numbers(caption)
        if exact_docket:
            target = _docket_key(exact_docket)
            docket_matches = target in {
                _docket_key(value) for value in docket_numbers
            }
            caption_matches = f" {target} " in f" {_docket_key(caption)} "
            if not docket_matches and not caption_matches:
                continue

        disposition_date_raw, disposition_date = _source_date(
            item.get("DispositionDate"),
            "DispositionDate",
        )
        upload_date_raw, upload_date = _source_date(
            item.get("UploadDate"),
            "UploadDate",
        )
        postings = item.get("Postings")
        assert isinstance(postings, list)
        for posting_index, posting_value in enumerate(postings):
            posting = _mapping(
                posting_value,
                f"items[{item_index}].Postings[{posting_index}]",
            )
            posting_opinion_id = _required_int(
                posting.get("OpinionId"),
                "posting.OpinionId",
                minimum=1,
            )
            if posting_opinion_id != opinion_id:
                raise PAOpinionsSourceChangedError(
                    "posting_opinion_id_mismatch",
                    "Pennsylvania posting references another opinion",
                    details={
                        "opinion_id": opinion_id,
                        "posting_opinion_id": posting_opinion_id,
                    },
                )
            native_posting_id = _posting_identity(
                opinion_id,
                posting_index,
                posting,
            )
            posted_at_raw, posted_at = _source_datetime(
                posting.get("PostedDateDisplay"),
                "PostedDateDisplay",
            )
            rendered_date_raw, rendered_date = _source_date(
                posting.get("RenderedDate"),
                "RenderedDate",
            )
            processed_at_raw, processed_at = _source_datetime(
                posting.get("ProcessedDate"),
                "ProcessedDate",
            )
            posting_type_code, posting_type = _posting_type(posting)
            pdf_url = _pdf_url(court_key, posting)
            records.append(
                {
                    "record_kind": "appellate_opinion_posting",
                    "source_id": SOURCE_ID,
                    "native_opinion_id": str(opinion_id),
                    "native_posting_id": native_posting_id,
                    "native_posting_id_raw": posting.get("Id"),
                    "native_document_id": native_posting_id,
                    "canonical_ref": _canonical_ref(
                        court_key,
                        opinion_id,
                        native_posting_id,
                    ),
                    "court": _court_payload(court_key),
                    "caption": caption,
                    "title": caption,
                    "docket_number": (
                        docket_numbers[0] if docket_numbers else None
                    ),
                    "docket_numbers": docket_numbers,
                    "decision_date_raw": disposition_date_raw,
                    "decision_date": disposition_date,
                    "upload_date_raw": upload_date_raw,
                    "upload_date": upload_date,
                    "posted_at_raw": posted_at_raw,
                    "posted_at": posted_at,
                    "posted_date": posted_at[:10] if posted_at else None,
                    "rendered_date_raw": rendered_date_raw,
                    "rendered_date": rendered_date,
                    "processed_at_raw": processed_at_raw,
                    "processed_at": processed_at,
                    "author": _posting_author(item, posting),
                    "posted_by": _text(item.get("UserIdentifier")),
                    "posting_type_code": posting_type_code,
                    "posting_type": posting_type,
                    "publication_type": _publication_type(posting),
                    "keywords": _text(item.get("Keywords")),
                    "file_name": _required_text(
                        posting.get("FileName"),
                        "posting.FileName",
                    ),
                    "file_version": _required_int(
                        posting.get("FileVersion", 1),
                        "posting.FileVersion",
                        minimum=1,
                    ),
                    "pdf_url": pdf_url,
                    "source_url": pdf_url,
                    "media_type": "application/pdf",
                    "access_state": "public",
                    "certified_record": False,
                    "evidentiary_role": (
                        "official_appellate_opinion_or_order_posting"
                    ),
                    "source_scope": {
                        "complete_docket": False,
                        "underlying_party_filings": False,
                        "native_pagination_exhausted": (
                            collection.incomplete_error is None
                        ),
                    },
                    "search_metadata": {
                        "selection": dict(selection),
                        "source_total_opinions": collection.total_items,
                        "source_total_pages": collection.total_pages,
                        "source_pages_fetched": collection.pages_fetched,
                        "native_page_size": collection.page_size,
                        "native_pagination": "page_number",
                    },
                    "raw": {
                        "opinion": dict(item),
                        "posting": dict(posting),
                    },
                }
            )
    if limit is not None:
        records = records[:limit]
    return records


def _court_key_from_pdf_url(source_url: str) -> str:
    parsed = urlsplit(source_url)
    if (
        parsed.scheme.casefold() != "https"
        or parsed.netloc.casefold() != urlsplit(BASE_URL).netloc.casefold()
    ):
        raise PAOpinionsSelectionError(
            "pdf_url_invalid",
            "PDF URL is not on the official Pennsylvania Courts origin",
            details={"url": source_url},
        )
    decoded_path = unquote(parsed.path)
    match = _PDF_PATH_RE.fullmatch(decoded_path)
    if match is None:
        raise PAOpinionsSelectionError(
            "pdf_url_invalid",
            "PDF URL is not an official Pennsylvania appellate opinion route",
            details={"url": source_url},
        )
    asset_directory = match.group(1)
    court_key = next(
        (
            key
            for directory, key in COURT_BY_ASSET_DIRECTORY.items()
            if directory.casefold() == asset_directory.casefold()
        ),
        None,
    )
    if court_key is None:
        raise PAOpinionsSelectionError(
            "pdf_court_unknown",
            "PDF URL identifies an unsupported Pennsylvania court",
            details={"url": source_url},
        )
    return court_key


class PAOpinionsClient:
    """HTTP client for the official public metadata and PDF routes."""

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
            "Referer": COURTS["supreme"]["page_url"],
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
                    raise PAOpinionsError(
                        "transport_error",
                        "Pennsylvania opinions request failed after "
                        f"{attempt} attempts: {error}",
                        category="transport",
                        retryable=True,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                retry_after: float | None = None
                raw_retry_after = response.headers.get("Retry-After")
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
                raise PAOpinionsError(
                    "rate_limited" if status_code == 429 else "http_status_error",
                    f"Pennsylvania opinions returned HTTP {status_code}",
                    status=(
                        ResultStatus.RATE_LIMITED
                        if status_code == 429
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=(
                        "rate_limit" if status_code == 429 else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code},
                )
            if status_code in {401, 403}:
                raise PAOpinionsError(
                    "source_access_failed",
                    f"Pennsylvania opinions returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code},
                )
            if status_code in {404, 410}:
                raise PAOpinionsSourceChangedError(
                    "source_route_missing",
                    f"Pennsylvania opinions route returned HTTP {status_code}",
                    details={"status_code": status_code, "url": url},
                )
            if status_code < 200 or status_code >= 300:
                raise PAOpinionsError(
                    "http_status_error",
                    f"Pennsylvania opinions returned HTTP {status_code}",
                    category="transport",
                    details={"status_code": status_code},
                )
            return response
        raise PAOpinionsError(
            "transport_error",
            f"Pennsylvania opinions request failed: {last_error}",
            category="transport",
            retryable=True,
        )

    def fetch_page(
        self,
        selection: Mapping[str, str],
        *,
        page_number: int = 1,
    ) -> PAOpinionsPage:
        if page_number <= 0:
            raise ValueError("page_number must be positive")
        params: dict[str, Any] = dict(selection)
        if page_number > 1:
            params["pageNumber"] = page_number
        response = self._request(
            API_URL,
            params=params,
            accept="application/json",
        )
        media_type = (
            str(response.headers.get("Content-Type", ""))
            .split(";", 1)[0]
            .strip()
            .casefold()
        )
        if media_type != "application/json":
            raise PAOpinionsSourceChangedError(
                "api_media_type_changed",
                "Pennsylvania opinions API did not return JSON",
                details={"content_type": media_type},
            )
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise PAOpinionsSourceChangedError(
                "api_json_invalid",
                "Pennsylvania opinions API returned invalid JSON",
            ) from error
        page = parse_page(payload, source_url=str(response.url))
        if page.page_number != page_number:
            raise PAOpinionsSourceChangedError(
                "api_page_number_mismatch",
                "Pennsylvania opinions returned another page number",
                details={
                    "requested": page_number,
                    "observed": page.page_number,
                },
            )
        return page

    def fetch_all(
        self,
        selection: Mapping[str, str],
    ) -> PAOpinionsCollection:
        first = self.fetch_page(selection, page_number=1)
        pages = [first]
        incomplete_error: PAOpinionsError | None = None
        for page_number in range(2, first.total_pages + 1):
            try:
                page = self.fetch_page(selection, page_number=page_number)
            except PAOpinionsError as error:
                incomplete_error = error
                break
            if (
                page.page_size != first.page_size
                or page.total_items != first.total_items
                or page.total_pages != first.total_pages
            ):
                incomplete_error = PAOpinionsPaginationError(
                    "Pennsylvania opinions pagination totals changed during "
                    "the traversal",
                    details={
                        "first_page": {
                            "page_size": first.page_size,
                            "total_items": first.total_items,
                            "total_pages": first.total_pages,
                        },
                        "observed_page": {
                            "page_number": page.page_number,
                            "page_size": page.page_size,
                            "total_items": page.total_items,
                            "total_pages": page.total_pages,
                        },
                    },
                )
                break
            pages.append(page)

        items: list[Mapping[str, Any]] = []
        seen_ids: set[int] = set()
        for page in pages:
            for item in page.items:
                opinion_id = _required_int(
                    item.get("Id"),
                    "item.Id",
                    minimum=1,
                )
                if opinion_id in seen_ids:
                    if incomplete_error is None:
                        incomplete_error = PAOpinionsPaginationError(
                            "Pennsylvania opinions repeated an opinion across "
                            "native pages",
                            details={"opinion_id": opinion_id},
                        )
                    continue
                seen_ids.add(opinion_id)
                items.append(item)
        if (
            incomplete_error is None
            and len(items) != first.total_items
        ):
            incomplete_error = PAOpinionsPaginationError(
                "Pennsylvania opinions traversal did not yield TotalItems",
                details={
                    "expected": first.total_items,
                    "observed": len(items),
                },
            )

        return PAOpinionsCollection(
            items=tuple(items),
            pages_fetched=len(pages),
            page_size=first.page_size,
            total_items=first.total_items,
            total_pages=first.total_pages,
            source_urls=tuple(page.source_url for page in pages),
            schema_fingerprints=tuple(
                page.schema_fingerprint for page in pages
            ),
            incomplete_error=incomplete_error,
        )

    def fetch_pdf(self, source_url: str) -> PAOpinionPDF:
        court_key = _court_key_from_pdf_url(source_url)
        response = self._request(
            source_url,
            accept="application/pdf",
        )
        final_url = str(response.url)
        final_court_key = _court_key_from_pdf_url(final_url)
        if final_court_key != court_key:
            raise PAOpinionsSourceChangedError(
                "pdf_redirect_changed_court",
                "Pennsylvania opinion PDF redirected to another court",
                details={"requested_url": source_url, "final_url": final_url},
            )
        media_type = (
            str(response.headers.get("Content-Type", ""))
            .split(";", 1)[0]
            .strip()
            .casefold()
        )
        content = bytes(response.content)
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise PAOpinionsSourceChangedError(
                "pdf_response_invalid",
                "Pennsylvania opinion route did not return a PDF",
                details={
                    "content_type": media_type,
                    "magic_hex": content[:8].hex(),
                    "url": final_url,
                },
            )
        return PAOpinionPDF(
            content=content,
            source_url=final_url,
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
            court_key=court_key,
        )


def _date_partition(args: argparse.Namespace) -> dict[str, str]:
    raw_year = getattr(args, "year", None)
    raw_month = getattr(args, "month", None)
    raw_start = _text(getattr(args, "date_from", None))
    raw_end = _text(getattr(args, "date_to", None))
    if raw_year is not None:
        if raw_start is not None or raw_end is not None:
            raise PAOpinionsSelectionError(
                "date_partition_conflict",
                "Use either --year/--month or --date-from/--date-to",
            )
        return {
            "year": str(raw_year),
            "month": str(raw_month) if raw_month is not None else "",
        }
    if raw_month is not None:
        raise PAOpinionsSelectionError(
            "month_requires_year",
            "--month requires --year",
        )
    if (raw_start is None) != (raw_end is None):
        raise PAOpinionsSelectionError(
            "date_pair_required",
            "--date-from and --date-to must be supplied together",
        )
    if raw_start is None:
        raise PAOpinionsSelectionError(
            "date_partition_required",
            "The official endpoint requires --year or a date range",
        )
    start = _selection_date(raw_start, "date_from")
    end = _selection_date(raw_end, "date_to")
    if end < start:
        raise PAOpinionsSelectionError(
            "date_range_reversed",
            "date_to must be on or after date_from",
            details={"date_from": start, "date_to": end},
        )
    return {"startDate": start, "endDate": end}


def native_selection(args: argparse.Namespace) -> dict[str, str]:
    """Translate CLI operations to verified native API fields."""

    if args.command == "list":
        selection = {
            **_date_partition(args),
            "courtType": COURTS[args.court]["api_value"],
        }
        optional = {
            "captionText": args.caption,
            "authorName": args.author,
            "publicationType": args.publication_type,
        }
        selection.update(
            {
                key: value
                for key, raw in optional.items()
                if (value := _text(raw)) is not None
            }
        )
        post_types = [
            value
            for raw in args.post_type
            if (value := _text(raw)) is not None
        ]
        if post_types:
            selection["postTypes"] = ",".join(post_types)
        selection["sortDirection"] = "-1" if args.sort == "newest" else "1"
        return selection
    if args.command in {"docket", "sentinel", "probe"}:
        docket_number = (
            SENTINEL_DOCKET
            if args.command in {"sentinel", "probe"}
            else _text(args.docket_number)
        )
        assert docket_number is not None
        court_key = "supreme" if args.command in {"sentinel", "probe"} else args.court
        year = (
            SENTINEL_YEAR
            if args.command in {"sentinel", "probe"}
            else args.year or _infer_year(docket_number)
        )
        return {
            "year": str(year),
            "month": "",
            "courtType": COURTS[court_key]["api_value"],
            "captionText": docket_number,
            "sortDirection": "-1",
        }
    if args.command == "download":
        return {"source_url": args.source_url}
    return {}


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    requested_limit = getattr(args, "limit", None)
    try:
        parameters = native_selection(args)
    except PAOpinionsError:
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
    if args.command == "download":
        parameters = {
            **parameters,
            "destination": str(args.destination),
        }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=STATE_GEOID,
            name="Pennsylvania",
            state_code=STATE_CODE,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
        ),
    )


def _make_client(args: argparse.Namespace) -> PAOpinionsClient:
    return PAOpinionsClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _public_error(error: PAOpinionsError) -> PublicRecordsError:
    return PublicRecordsError(
        code=error.code,
        message=str(error),
        category=error.category,
        retryable=error.retryable,
        details=error.details,
    )


def _error_result(
    query: PublicRecordsQuery,
    error: PAOpinionsError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [_public_error(error)],
        warnings=SOURCE_WARNINGS,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
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
        warnings=SOURCE_WARNINGS,
    )


def _collection_result(
    query: PublicRecordsQuery,
    collection: PAOpinionsCollection,
    *,
    court_key: str,
    selection: Mapping[str, str],
    exact_docket: str | None,
    limit: int | None,
) -> PublicRecordsResult:
    all_records = normalize_collection(
        collection,
        court_key=court_key,
        selection=selection,
        exact_docket=exact_docket,
    )
    records = all_records if limit is None else all_records[:limit]
    warnings = list(SOURCE_WARNINGS)
    if limit is not None and len(records) < len(all_records):
        warnings.append(
            f"Caller limit returned {len(records)} of "
            f"{len(all_records)} normalized postings after native pagination."
        )
    if collection.incomplete_error is not None:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [_public_error(collection.incomplete_error)],
            records=records,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        warnings=warnings,
    )


def _execute_command(
    args: argparse.Namespace,
    client: PAOpinionsClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command in {"list", "docket"}:
        selection = native_selection(args)
        collection = client.fetch_all(selection)
        return _collection_result(
            query,
            collection,
            court_key=args.court,
            selection=selection,
            exact_docket=(
                args.docket_number if args.command == "docket" else None
            ),
            limit=getattr(args, "limit", None),
        )

    if args.command == "download":
        pdf = client.fetch_pdf(args.source_url)
        destination = Path(args.destination)
        if destination.exists() and not args.overwrite:
            raise PAOpinionsSelectionError(
                "destination_exists",
                f"destination exists; pass --overwrite: {destination}",
                details={"destination": str(destination)},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(pdf.content)
        record = {
            "record_kind": "appellate_opinion_artifact",
            "source_id": SOURCE_ID,
            "canonical_ref": (
                f"PAOPINION-ARTIFACT:{pdf.court_key}:{pdf.sha256}"
            ),
            "court": _court_payload(pdf.court_key),
            "source_url": pdf.source_url,
            "artifact_path": str(destination),
            "file_name": Path(unquote(urlsplit(pdf.source_url).path)).name,
            "media_type": pdf.media_type,
            "byte_length": len(pdf.content),
            "sha256": pdf.sha256,
            "access_state": "public",
            "certified_record": False,
            "evidentiary_role": "official_appellate_opinion_or_order_pdf",
        }
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[str(destination)],
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "probe":
        selection = native_selection(args)
        page = client.fetch_page(selection, page_number=1)
        record = {
            "record_kind": "source_probe",
            "source_id": SOURCE_ID,
            "source_url": page.source_url,
            "api_url": API_URL,
            "authentication": "none",
            "court_types": list(COURT_BY_API_VALUE),
            "native_query_fields": [
                "startDate",
                "endDate",
                "year",
                "month",
                "courtType",
                "captionText",
                "authorName",
                "postTypes",
                "publicationType",
                "sortDirection",
                "pageNumber",
            ],
            "native_pagination": {
                "kind": "page_number",
                "page_size": page.page_size,
                "total_items_for_probe": page.total_items,
                "total_pages_for_probe": page.total_pages,
            },
            "schema_fingerprint": page.schema_fingerprint,
            "evidentiary_role": (
                "official_appellate_opinion_order_posting_corpus"
            ),
            "complementary_routes": [
                {
                    "role": "case_chronology_and_docket_sheet_metadata",
                    "url": UJS_DOCKET_URL,
                },
                {
                    "role": "bulk_case_metadata_and_record_requests",
                    "url": AOPC_RECORDS_URL,
                },
                {
                    "role": "official_copy_or_certification",
                    "route": "applicable appellate court prothonotary",
                },
                {
                    "role": "secondary_full_text_citation_and_docket_discovery",
                    "url": COURTLISTENER_URL,
                },
                {
                    "role": "official_site_full_text_search",
                    "url": SITE_SEARCH_URL,
                },
            ],
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "sentinel":
        selection = native_selection(args)
        collection = client.fetch_all(selection)
        records = normalize_collection(
            collection,
            court_key="supreme",
            selection=selection,
            exact_docket=SENTINEL_DOCKET,
        )
        record = next(
            (
                value
                for value in records
                if value["native_opinion_id"] == str(SENTINEL_OPINION_ID)
                and value["native_posting_id"] == str(SENTINEL_POSTING_ID)
            ),
            None,
        )
        if record is None:
            raise PAOpinionsSourceChangedError(
                "sentinel_missing",
                "Pennsylvania Supreme Court opinion sentinel is missing",
                details={
                    "docket_number": SENTINEL_DOCKET,
                    "opinion_id": SENTINEL_OPINION_ID,
                    "posting_id": SENTINEL_POSTING_ID,
                },
            )
        pdf = client.fetch_pdf(record["pdf_url"])
        record = {
            **record,
            "sentinel": True,
            "sentinel_pdf_sha256": pdf.sha256,
            "sentinel_pdf_byte_length": len(pdf.content),
            "sentinel_pdf_media_type": pdf.media_type,
        }
        if collection.incomplete_error is not None:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                [_public_error(collection.incomplete_error)],
                records=[record],
                warnings=SOURCE_WARNINGS,
            )
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )

    raise PAOpinionsSelectionError(
        "unsupported_command",
        f"unsupported Pennsylvania opinions command: {args.command}",
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: PAOpinionsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one official Pennsylvania appellate opinion operation."""

    query = build_query(args)
    if access_decision is not None and not access_decision.get(
        "allowed", False
    ):
        result = _decision_failure(query, access_decision)
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except PAOpinionsError as error:
        result = _error_result(query, error)
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
            warnings=SOURCE_WARNINGS,
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
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Pennsylvania opinions {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Pennsylvania opinions {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        print(
            f"  {record.get('docket_number') or '?'} | "
            f"{record.get('posting_type') or record.get('record_kind')} | "
            f"{record.get('caption') or record.get('file_name') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _month(value: str) -> int:
    parsed = int(value)
    if parsed < 1 or parsed > 12:
        raise argparse.ArgumentTypeError("month must be between 1 and 12")
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
        description="Query official Pennsylvania appellate opinion postings",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser(
        "list",
        help="List/filter postings and exhaust native pages",
    )
    listing.add_argument("--court", choices=tuple(COURTS), required=True)
    partition = listing.add_mutually_exclusive_group(required=True)
    partition.add_argument("--year", type=_positive_int)
    partition.add_argument("--date-from", help="Inclusive ISO start date")
    listing.add_argument("--date-to", help="Inclusive ISO end date")
    listing.add_argument("--month", type=_month)
    listing.add_argument("--caption")
    listing.add_argument("--author")
    listing.add_argument(
        "--post-type",
        action="append",
        default=[],
        help="Repeatable source-native posting type code or identifier",
    )
    listing.add_argument("--publication-type")
    listing.add_argument(
        "--sort",
        choices=("newest", "oldest"),
        default="newest",
    )
    listing.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-side slice after all native pages are fetched",
    )
    _add_runtime_and_output(listing)

    docket = subparsers.add_parser(
        "docket",
        help="Find postings for an exact appellate docket",
    )
    docket.add_argument("docket_number")
    docket.add_argument("--court", choices=tuple(COURTS), required=True)
    docket.add_argument(
        "--year",
        type=_positive_int,
        help="Date partition override when the docket lacks a year",
    )
    docket.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional caller-side slice after all native pages are fetched",
    )
    _add_runtime_and_output(docket)

    download = subparsers.add_parser(
        "download",
        help="Download an official posting PDF with an integrity receipt",
    )
    download.add_argument("source_url")
    download.add_argument("destination", type=Path)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the public API and describe its source role",
    )
    _add_runtime_and_output(probe)

    sentinel = subparsers.add_parser(
        "sentinel",
        help="Verify a stable Supreme Court posting and its PDF",
    )
    _add_runtime_and_output(sentinel)
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
