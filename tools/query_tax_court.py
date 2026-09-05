#!/usr/bin/env python3
"""Query the U.S. Tax Court's public DAWSON API.

DAWSON exposes anonymous case-name search, case detail, native docket
pagination, order/opinion full-text search, current releases, trial sessions,
and public PDF downloads.  Search responses are returned with their native
fields intact; the envelope adds only provenance, schema, and ceiling
metadata.

Examples:
    uv run python tools/query_tax_court.py cases Hagee --json
    uv run python tools/query_tax_court.py case 455-22S --json
    uv run python tools/query_tax_court.py docket 455-22S --output docket.json
    uv run python tools/query_tax_court.py orders --docket 455-22 --json
    uv run python tools/query_tax_court.py opinions \
        --keyword '"innocent spouse"' --limit 25 --json
    uv run python tools/query_tax_court.py download \
        455-22 8fbd790c-3af0-43fb-9059-9754310faa24 /tmp/order.pdf
    uv run python tools/query_tax_court.py docket-pdf \
        455-22 /tmp/docket.pdf
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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, quote, urlparse

import requests

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )


SOURCE_ID = "us-tax-court-dawson"
SOURCE_NAME = "U.S. Tax Court DAWSON"
PORTAL_URL = "https://dawson.ustaxcourt.gov"
API_ROOT = "https://public-api.dawson.ustaxcourt.gov"
OFFICIAL_SITE_URL = "https://www.ustaxcourt.gov"

CASE_SEARCH_URL = f"{API_ROOT}/public-api/search"
CASE_RESULT_CEILING = 5_000
DOCUMENT_SEARCH_RESULT_CEILING = 5_000
TODAYS_OPINIONS_RESULT_CEILING = 200
DOCKET_PAGE_SIZE = 1_000
DOCKET_MAX_PAGE = 20
TODAYS_ORDERS_PAGE_SIZE = 100
DEFAULT_DOWNLOAD_URL_TTL_SECONDS = 120
DEFAULT_DOCKET_PDF_POLL_SECONDS = 2.0
DEFAULT_DOCKET_PDF_TIMEOUT_SECONDS = 16 * 60.0

OPINION_TYPES = {
    "tc": "TCOP",
    "t.c.": "TCOP",
    "tcop": "TCOP",
    "memorandum": "MOP",
    "memo": "MOP",
    "mop": "MOP",
    "summary": "SOP",
    "sop": "SOP",
    "bench": "OST",
    "ost": "OST",
}
ALL_OPINION_TYPES = ("TCOP", "MOP", "SOP", "OST")
TODAYS_ORDERS_SORTS = {
    "filing-date-asc": "FILING_DATE_ASC",
    "filing-date-desc": "FILING_DATE_DESC",
    "page-count-asc": "NUMBER_OF_PAGES_ASC",
    "page-count-desc": "NUMBER_OF_PAGES_DESC",
    "filingdate|asc": "FILING_DATE_ASC",
    "filingdate|desc": "FILING_DATE_DESC",
}
TODAYS_ORDERS_NATIVE_SORTS = frozenset(TODAYS_ORDERS_SORTS.values())
DOCKET_BASE_RE = re.compile(
    r"^(?P<base>\d+-\d{2})(?:SL|[DLPRSWX])?$",
    flags=re.IGNORECASE,
)

SOURCE_METADATA = {
    "source_id": SOURCE_ID,
    "name": SOURCE_NAME,
    "authority": "United States Tax Court",
    "portal_url": PORTAL_URL,
    "api_root": API_ROOT,
    "authentication": "none",
    "coverage": {
        "case_search_result_ceiling": CASE_RESULT_CEILING,
        "document_search_result_ceiling": DOCUMENT_SEARCH_RESULT_CEILING,
        "todays_opinions_result_ceiling": (
            TODAYS_OPINIONS_RESULT_CEILING
        ),
        "docket_page_size": DOCKET_PAGE_SIZE,
        "docket_pages": {
            "first": 0,
            "last": DOCKET_MAX_PAGE,
        },
        "todays_orders_page_size": TODAYS_ORDERS_PAGE_SIZE,
    },
}


class TaxCourtQueryError(ValueError):
    """A DAWSON query cannot be represented by the source contract."""


class TaxCourtNotFoundError(RuntimeError):
    """DAWSON returned an expected resource-level 404."""

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url


class TaxCourtJobError(RuntimeError):
    """DAWSON reported that an asynchronous export job failed."""


@dataclass(frozen=True)
class TaxCourtDownload:
    """One validated PDF fetched through a short-lived DAWSON URL."""

    content: bytes
    public_request_url: str
    signed_url_issued_at: str | None
    signed_url_expires_seconds: int | None
    job_id: str | None = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    def metadata(self, destination: Path) -> dict[str, Any]:
        return {
            "source_id": SOURCE_ID,
            "path": str(destination),
            "bytes": len(self.content),
            "sha256": self.sha256,
            "media_type": "application/pdf",
            "public_request_url": self.public_request_url,
            "signed_url_issued_at": self.signed_url_issued_at,
            "signed_url_expires_seconds": self.signed_url_expires_seconds,
            "job_id": self.job_id,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required(value: str | None, label: str) -> str:
    normalized = " ".join((value or "").split()).strip()
    if not normalized:
        raise TaxCourtQueryError(f"{label} is required")
    return normalized


def canonical_docket_number(value: str) -> str:
    """Return the suffixless identifier used by public document/PDF jobs."""

    normalized = _required(value, "docket number").upper().replace(" ", "")
    match = DOCKET_BASE_RE.fullmatch(normalized)
    return match.group("base") if match else normalized


def tax_court_evidence_ref(
    docket_number: str,
    docket_entry_id: str | None = None,
) -> str:
    """Return the stable citation ref for a case or docket entry."""

    reference = f"TAXCOURT:{canonical_docket_number(docket_number)}"
    if docket_entry_id is not None:
        reference += f":{_required(docket_entry_id, 'docket entry ID')}"
    return reference


def _search_date(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _required(value, "date")
    try:
        return date.fromisoformat(normalized).strftime("%m/%d/%Y")
    except ValueError:
        return normalized


def _positive_limit(value: int | None, ceiling: int) -> int:
    if value is None:
        return ceiling
    if isinstance(value, bool) or value <= 0:
        raise TaxCourtQueryError("limit must be a positive integer")
    if value > ceiling:
        raise TaxCourtQueryError(
            f"DAWSON limits this search to {ceiling:,} results"
        )
    return value


def normalize_todays_orders_sort(value: str) -> str:
    """Return one of DAWSON's deployed Today's Orders sort tokens."""
    normalized = _required(value, "sort")
    native = normalized.upper()
    if native in TODAYS_ORDERS_NATIVE_SORTS:
        return native
    try:
        return TODAYS_ORDERS_SORTS[normalized.casefold()]
    except KeyError as error:
        raise TaxCourtQueryError(
            "Today's Orders sort must be filing-date-asc, "
            "filing-date-desc, page-count-asc, or page-count-desc"
        ) from error


def _records_schema(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    schema = inferred_schema(records)
    return {
        "schema": schema,
        "schema_fingerprint": schema_fingerprint(schema),
    }


def _resource_schema(resource: Mapping[str, Any]) -> dict[str, Any]:
    return _records_schema([resource])


def _records_evidence_refs(
    records: Sequence[Mapping[str, Any]],
) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for record in records:
        docket = (
            record.get("docketNumber")
            or record.get("docketNumberWithSuffix")
        )
        if not isinstance(docket, str) or not docket.strip():
            continue
        entry_id = record.get("docketEntryId")
        reference = tax_court_evidence_ref(
            docket,
            entry_id if isinstance(entry_id, str) else None,
        )
        if reference not in seen:
            refs.append(reference)
            seen.add(reference)
    return refs


def _envelope(
    command: str,
    query: Mapping[str, Any],
    *,
    records: Sequence[Mapping[str, Any]] | None = None,
    resource: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    warnings: Sequence[str] = (),
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source": SOURCE_METADATA,
        "command": command,
        "query": dict(query),
        "retrieved_at": _now_iso(),
        "warnings": list(warnings),
    }
    if records is not None:
        native_records = [dict(record) for record in records]
        evidence_refs = _records_evidence_refs(native_records)
        result["records"] = native_records
        result["metadata"] = {
            "returned_count": len(native_records),
            **_records_schema(native_records),
            **({"evidence_refs": evidence_refs} if evidence_refs else {}),
            **dict(metadata or {}),
        }
    elif resource is not None:
        native_resource = dict(resource)
        result["resource"] = native_resource
        result["metadata"] = {
            **_resource_schema(native_resource),
            **dict(metadata or {}),
        }
    else:
        result["metadata"] = dict(metadata or {})
    return result


def _retry_after_seconds(headers: Mapping[str, Any]) -> float | None:
    for key, value in headers.items():
        if str(key).casefold() != "retry-after":
            continue
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None
    return None


def _response_text(response: Any) -> str:
    value = getattr(response, "text", "")
    return value if isinstance(value, str) else str(value)


def _header(response: Any, name: str) -> str | None:
    for key, value in getattr(response, "headers", {}).items():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


class TaxCourtClient:
    """Transport-injectable client for DAWSON's anonymous public API."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = 30.0,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        user_agent: str = "Ithildin-Public-Records/1.0",
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._clock = clock
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            clock=clock,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        accept: str = "application/json",
    ) -> Any:
        headers = {
            "Accept": accept,
            "User-Agent": self.user_agent,
        }
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    params=dict(params or {}),
                    json=dict(json_body) if json_body is not None else None,
                    headers=headers,
                    timeout=self.timeout,
                )
            except (
                requests.RequestException,
                TimeoutError,
                ConnectionError,
            ) as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        f"DAWSON request failed after {attempt} attempts: "
                        f"{error}",
                        url=url,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(getattr(response, "status_code", 0))
            if status_code in self.retry_policy.retry_statuses:
                retry_after = _retry_after_seconds(
                    getattr(response, "headers", {})
                )
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                if status_code == 429:
                    raise RateLimitedHTTPError(
                        status_code,
                        url=url,
                        response_text=_response_text(response),
                    )
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code == 451:
                raise TermsBlockedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code in {404, 410}:
                raise TaxCourtNotFoundError(
                    _response_text(response)
                    or f"DAWSON resource returned HTTP {status_code}",
                    url=url,
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            return response

        raise TransportError(
            f"DAWSON request failed: {last_error}",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )

    def _json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        response = self._request(
            method,
            url,
            params=params,
            json_body=json_body,
        )
        try:
            return response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SourceSchemaError(
                "DAWSON returned invalid JSON",
                url=url,
                details={"response_text": _response_text(response)[:500]},
            ) from error

    @staticmethod
    def _object(payload: Any, url: str) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "DAWSON response must be an object",
                url=url,
                details={"response_type": type(payload).__name__},
            )
        return payload

    @staticmethod
    def _list(payload: Any, url: str) -> list[Mapping[str, Any]]:
        if not isinstance(payload, list) or any(
            not isinstance(record, Mapping) for record in payload
        ):
            raise SourceSchemaError(
                "DAWSON response must be an array of objects",
                url=url,
                details={"response_type": type(payload).__name__},
            )
        return list(payload)

    @classmethod
    def _results(
        cls,
        payload: Any,
        url: str,
    ) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
        wrapper = cls._object(payload, url)
        records = wrapper.get("results")
        if not isinstance(records, list) or any(
            not isinstance(record, Mapping) for record in records
        ):
            raise SourceSchemaError(
                "DAWSON result wrapper is missing an object-array 'results'",
                url=url,
            )
        return list(records), wrapper

    def health(self) -> dict[str, Any]:
        url = f"{API_ROOT}/public-api/health"
        start_requests = self.request_count
        payload = self._object(self._json("GET", url), url)
        return _envelope(
            "probe",
            {},
            resource=payload,
            metadata={
                "requests_made": self.request_count - start_requests,
                "contracts": {
                    "case_search_result_ceiling": CASE_RESULT_CEILING,
                    "document_search_result_ceiling": (
                        DOCUMENT_SEARCH_RESULT_CEILING
                    ),
                    "todays_opinions_result_ceiling": (
                        TODAYS_OPINIONS_RESULT_CEILING
                    ),
                    "docket_page_size": DOCKET_PAGE_SIZE,
                    "docket_max_page": DOCKET_MAX_PAGE,
                    "todays_orders_page_size": TODAYS_ORDERS_PAGE_SIZE,
                    "download_url_ttl_seconds": (
                        DEFAULT_DOWNLOAD_URL_TTL_SECONDS
                    ),
                },
            },
        )

    def search_cases(
        self,
        petitioner_name: str | None = None,
        *,
        country_type: str | None = None,
        petitioner_state: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        case_types: Sequence[str] = (),
        procedure_type: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        start_requests = self.request_count
        if limit is not None:
            _positive_limit(limit, CASE_RESULT_CEILING)
        params: dict[str, Any] = {}
        optional = {
            "petitionerName": petitioner_name,
            "countryType": country_type,
            "petitionerState": petitioner_state,
            "startDate": _search_date(filed_after),
            "endDate": _search_date(filed_before),
            "procedureType": procedure_type,
        }
        params.update(
            {
                key: value
                for key, value in optional.items()
                if value is not None and str(value).strip()
            }
        )
        if case_types:
            # DAWSON's public API requires array query-string semantics even
            # when the caller supplies a single case type.
            params["caseTypes[]"] = list(case_types)
        payload = self._json("GET", CASE_SEARCH_URL, params=params)
        records, wrapper = self._results(payload, CASE_SEARCH_URL)
        source_returned = len(records)
        if limit is not None:
            records = records[:limit]
        return _envelope(
            "cases",
            params,
            records=records,
            metadata={
                "requests_made": self.request_count - start_requests,
                "source_returned_count": source_returned,
                "source_result_ceiling": CASE_RESULT_CEILING,
                "source_ceiling_reached": (
                    source_returned == CASE_RESULT_CEILING
                ),
                "caller_limit": limit,
                "truncated_by_caller": (
                    limit is not None and source_returned > limit
                ),
                "native_wrapper_metadata": {
                    key: value
                    for key, value in wrapper.items()
                    if key != "results"
                },
            },
        )

    def get_case(self, docket_number: str) -> dict[str, Any]:
        docket = _required(docket_number, "docket number")
        url = (
            f"{API_ROOT}/public-api/cases/"
            f"{quote(docket, safe='-')}?"
            "excludeDocketEntries=true"
        )
        start_requests = self.request_count
        payload = self._object(self._json("GET", url), url)
        native_base_docket = payload.get("docketNumber")
        case_link_docket = (
            _required(native_base_docket, "response docket number")
            if isinstance(native_base_docket, str)
            else canonical_docket_number(docket)
        )
        return _envelope(
            "case",
            {"docket_number": docket},
            resource=payload,
            metadata={
                "requests_made": self.request_count - start_requests,
                "evidence_ref": tax_court_evidence_ref(case_link_docket),
                "case_record_url": (
                    f"{PORTAL_URL}/case-detail/"
                    f"{quote(case_link_docket, safe='-')}"
                ),
            },
        )

    def _docket_page(
        self,
        docket_number: str,
        page: int,
    ) -> tuple[list[Mapping[str, Any]], Mapping[str, Any], str]:
        if isinstance(page, bool) or page < 0 or page > DOCKET_MAX_PAGE:
            raise TaxCourtQueryError(
                f"DAWSON docket pages run from 0 through {DOCKET_MAX_PAGE}"
            )
        url = (
            f"{API_ROOT}/public-api/cases/"
            f"{quote(docket_number, safe='-')}/docket-entries"
        )
        payload = self._object(
            self._json("GET", url, params={"page": page}),
            url,
        )
        records = payload.get("docketEntries")
        if not isinstance(records, list) or any(
            not isinstance(record, Mapping) for record in records
        ):
            raise SourceSchemaError(
                "DAWSON docket page is missing object-array docketEntries",
                url=url,
            )
        for field in ("page", "pageSize", "totalCount"):
            if not isinstance(payload.get(field), int):
                raise SourceSchemaError(
                    f"DAWSON docket page is missing integer {field}",
                    url=url,
                )
        return list(records), payload, url

    def docket_entries(
        self,
        docket_number: str,
        *,
        page: int | None = None,
    ) -> dict[str, Any]:
        docket = _required(docket_number, "docket number")
        start_requests = self.request_count
        first_page_number = 0 if page is None else page
        records, first_payload, url = self._docket_page(
            docket,
            first_page_number,
        )
        page_metadata = [
            {
                key: value
                for key, value in first_payload.items()
                if key != "docketEntries"
            }
        ]
        warnings: list[str] = []

        total_count = int(first_payload["totalCount"])
        page_size = int(first_payload["pageSize"])
        total_pages = (
            math.ceil(total_count / page_size) if page_size > 0 else 0
        )
        source_page_ceiling_reached = total_pages > DOCKET_MAX_PAGE + 1

        if page is None:
            last_page = min(total_pages - 1, DOCKET_MAX_PAGE)
            for page_number in range(1, last_page + 1):
                page_records, payload, _ = self._docket_page(
                    docket,
                    page_number,
                )
                if (
                    payload["pageSize"] != page_size
                    or payload["totalCount"] != total_count
                ):
                    raise SourceSchemaError(
                        "DAWSON docket pagination metadata changed mid-fetch",
                        url=url,
                    )
                records.extend(page_records)
                page_metadata.append(
                    {
                        key: value
                        for key, value in payload.items()
                        if key != "docketEntries"
                    }
                )
            if source_page_ceiling_reached:
                warnings.append(
                    "The docket exceeds DAWSON's last accepted page "
                    f"({DOCKET_MAX_PAGE}); returned every source-accessible "
                    "page."
                )

        return _envelope(
            "docket",
            {"docket_number": docket, "page": page},
            records=records,
            metadata={
                "requests_made": self.request_count - start_requests,
                "native_pages": page_metadata,
                "native_page_size": page_size,
                "native_total_count": total_count,
                "native_total_pages": total_pages,
                "source_max_page": DOCKET_MAX_PAGE,
                "source_page_ceiling_reached": source_page_ceiling_reached,
                "complete": (
                    page is None
                    and not source_page_ceiling_reached
                    and len(records) >= total_count
                ),
            },
            warnings=warnings,
        )

    @staticmethod
    def _document_search_params(
        *,
        keyword: str | None,
        docket_number: str | None,
        case_title_or_petitioner: str | None,
        judge: str | None,
        filed_after: str | None,
        filed_before: str | None,
        limit: int | None,
    ) -> dict[str, Any]:
        if filed_before and not filed_after:
            raise TaxCourtQueryError(
                "DAWSON requires a start date when an end date is supplied"
            )
        effective_limit = _positive_limit(
            limit,
            DOCUMENT_SEARCH_RESULT_CEILING,
        )
        params: dict[str, Any] = {
            "dateRange": (
                "customDates"
                if filed_after or filed_before
                else "allDates"
            ),
            "limit": effective_limit,
        }
        optional = {
            "keyword": keyword,
            "docketNumber": (
                canonical_docket_number(docket_number)
                if docket_number
                else None
            ),
            "caseTitleOrPetitioner": case_title_or_petitioner,
            "judge": judge,
            "startDate": _search_date(filed_after),
            "endDate": _search_date(filed_before),
        }
        params.update(
            {
                key: value
                for key, value in optional.items()
                if value is not None and str(value).strip()
            }
        )
        return params

    def _document_search(
        self,
        command: str,
        url: str,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        start_requests = self.request_count
        payload = self._json("GET", url, params=params)
        records, wrapper = self._results(payload, url)
        requested_limit = int(params["limit"])
        return _envelope(
            command,
            params,
            records=records,
            metadata={
                "requests_made": self.request_count - start_requests,
                "requested_limit": requested_limit,
                "requested_limit_reached": len(records) == requested_limit,
                "source_result_ceiling": DOCUMENT_SEARCH_RESULT_CEILING,
                "source_ceiling_reached": (
                    requested_limit == DOCUMENT_SEARCH_RESULT_CEILING
                    and len(records) == DOCUMENT_SEARCH_RESULT_CEILING
                ),
                "native_wrapper_metadata": {
                    key: value
                    for key, value in wrapper.items()
                    if key != "results"
                },
            },
        )

    def search_orders(
        self,
        *,
        keyword: str | None = None,
        docket_number: str | None = None,
        case_title_or_petitioner: str | None = None,
        judge: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        params = self._document_search_params(
            keyword=keyword,
            docket_number=docket_number,
            case_title_or_petitioner=case_title_or_petitioner,
            judge=judge,
            filed_after=filed_after,
            filed_before=filed_before,
            limit=limit,
        )
        return self._document_search(
            "orders",
            f"{API_ROOT}/public-api/order-search",
            params,
        )

    def search_opinions(
        self,
        *,
        keyword: str | None = None,
        docket_number: str | None = None,
        case_title_or_petitioner: str | None = None,
        judge: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
        opinion_types: Sequence[str] = (),
        limit: int | None = None,
    ) -> dict[str, Any]:
        params = self._document_search_params(
            keyword=keyword,
            docket_number=docket_number,
            case_title_or_petitioner=case_title_or_petitioner,
            judge=judge,
            filed_after=filed_after,
            filed_before=filed_before,
            limit=limit,
        )
        normalized_types = [
            OPINION_TYPES.get(value.casefold(), value.upper())
            for value in opinion_types
        ]
        params["opinionTypes"] = ",".join(
            normalized_types or ALL_OPINION_TYPES
        )
        return self._document_search(
            "opinions",
            f"{API_ROOT}/public-api/opinion-search",
            params,
        )

    def todays_opinions(self) -> dict[str, Any]:
        url = f"{API_ROOT}/public-api/todays-opinions"
        start_requests = self.request_count
        records = self._list(self._json("GET", url), url)
        return _envelope(
            "today-opinions",
            {},
            records=records,
            metadata={
                "requests_made": self.request_count - start_requests,
                "source_result_ceiling": TODAYS_OPINIONS_RESULT_CEILING,
                "source_ceiling_reached": (
                    len(records) == TODAYS_OPINIONS_RESULT_CEILING
                ),
            },
        )

    def _todays_orders_page(
        self,
        page: int,
        sort: str,
    ) -> tuple[list[Mapping[str, Any]], Mapping[str, Any], str]:
        if isinstance(page, bool) or page < 1:
            raise TaxCourtQueryError(
                "DAWSON Today's Orders pages are one-based"
            )
        normalized_sort = normalize_todays_orders_sort(sort)
        url = (
            f"{API_ROOT}/public-api/todays-orders/{page}/"
            f"{quote(normalized_sort, safe='')}"
        )
        payload = self._object(self._json("GET", url), url)
        records = payload.get("results")
        if not isinstance(records, list) or any(
            not isinstance(record, Mapping) for record in records
        ):
            raise SourceSchemaError(
                "DAWSON Today's Orders response is missing results",
                url=url,
            )
        if not isinstance(payload.get("totalCount"), int):
            raise SourceSchemaError(
                "DAWSON Today's Orders response is missing totalCount",
                url=url,
            )
        return list(records), payload, url

    def todays_orders(
        self,
        *,
        page: int | None = None,
        sort: str = "filing-date-desc",
    ) -> dict[str, Any]:
        start_requests = self.request_count
        native_sort = normalize_todays_orders_sort(sort)
        first_page = 1 if page is None else page
        records, payload, url = self._todays_orders_page(
            first_page,
            native_sort,
        )
        total_count = int(payload["totalCount"])
        page_metadata = [
            {
                "page": first_page,
                **{
                    key: value
                    for key, value in payload.items()
                    if key != "results"
                },
            }
        ]
        warnings: list[str] = []
        if page is None:
            total_pages = math.ceil(
                total_count / TODAYS_ORDERS_PAGE_SIZE
            )
            for page_number in range(2, total_pages + 1):
                page_records, page_payload, _ = self._todays_orders_page(
                    page_number,
                    native_sort,
                )
                if page_payload["totalCount"] != total_count:
                    raise SourceSchemaError(
                        "DAWSON Today's Orders total changed mid-fetch",
                        url=url,
                    )
                if not page_records:
                    warnings.append(
                        "DAWSON returned an empty page before its reported "
                        "total was reached."
                    )
                    break
                records.extend(page_records)
                page_metadata.append(
                    {
                        "page": page_number,
                        **{
                            key: value
                            for key, value in page_payload.items()
                            if key != "results"
                        },
                    }
                )
        return _envelope(
            "today-orders",
            {
                "page": page,
                "sort": sort,
                "native_sort": native_sort,
            },
            records=records,
            metadata={
                "requests_made": self.request_count - start_requests,
                "native_total_count": total_count,
                "native_page_size": TODAYS_ORDERS_PAGE_SIZE,
                "native_pages": page_metadata,
                "complete": (
                    page is None and len(records) >= total_count
                ),
            },
            warnings=warnings,
        )

    def judges(self) -> dict[str, Any]:
        url = f"{API_ROOT}/public-api/judges"
        start_requests = self.request_count
        records = self._list(self._json("GET", url), url)
        return _envelope(
            "judges",
            {},
            records=records,
            metadata={
                "requests_made": self.request_count - start_requests,
            },
        )

    def trial_sessions(self) -> dict[str, Any]:
        url = f"{API_ROOT}/public-api/trial-sessions"
        start_requests = self.request_count
        records = self._list(self._json("GET", url), url)
        return _envelope(
            "trial-sessions",
            {},
            records=records,
            metadata={
                "requests_made": self.request_count - start_requests,
            },
        )

    def trial_session(self, trial_session_id: str) -> dict[str, Any]:
        identifier = _required(trial_session_id, "trial session ID")
        url = (
            f"{API_ROOT}/public-api/trial-sessions/"
            f"{quote(identifier, safe='-')}"
        )
        start_requests = self.request_count
        resource = self._object(self._json("GET", url), url)
        return _envelope(
            "trial-session",
            {"trial_session_id": identifier},
            resource=resource,
            metadata={
                "requests_made": self.request_count - start_requests,
                "calendared_case_count": len(
                    resource.get("calendaredCases", [])
                )
                if isinstance(resource.get("calendaredCases"), list)
                else None,
            },
        )

    @staticmethod
    def _signed_url_metadata(url: str) -> tuple[str | None, int | None]:
        query = parse_qs(urlparse(url).query)
        issued_at = (query.get("X-Amz-Date") or [None])[0]
        expires_raw = (query.get("X-Amz-Expires") or [None])[0]
        try:
            expires = int(expires_raw) if expires_raw is not None else None
        except ValueError:
            expires = None
        return issued_at, expires

    def _download_signed_pdf(
        self,
        signed_url: str,
        *,
        public_request_url: str,
        job_id: str | None = None,
    ) -> TaxCourtDownload:
        response = self._request(
            "GET",
            _required(signed_url, "signed download URL"),
            accept="application/pdf",
        )
        content = getattr(response, "content", None)
        if not isinstance(content, bytes):
            content = _response_text(response).encode()
        content_type = (_header(response, "Content-Type") or "").casefold()
        if not content.startswith(b"%PDF-"):
            raise SourceSchemaError(
                "DAWSON public document response is not a PDF",
                url=public_request_url,
                details={
                    "content_type": content_type,
                    "content_prefix": content[:16].hex(),
                },
            )
        issued_at, expires = self._signed_url_metadata(signed_url)
        return TaxCourtDownload(
            content=content,
            public_request_url=public_request_url,
            signed_url_issued_at=issued_at,
            signed_url_expires_seconds=expires,
            job_id=job_id,
        )

    def download_document(
        self,
        docket_number: str,
        docket_entry_id: str,
    ) -> TaxCourtDownload:
        docket = canonical_docket_number(docket_number)
        entry_id = _required(docket_entry_id, "docket entry ID")
        url = (
            f"{API_ROOT}/public-api/{quote(docket, safe='-')}/"
            f"{quote(entry_id, safe='-')}/public-document-download-url"
        )
        payload = self._object(self._json("GET", url), url)
        signed_url = payload.get("url")
        if not isinstance(signed_url, str) or not signed_url:
            raise SourceSchemaError(
                "DAWSON document-link response is missing url",
                url=url,
            )
        return self._download_signed_pdf(
            signed_url,
            public_request_url=url,
        )

    def generate_docket_pdf(
        self,
        docket_number: str,
        *,
        sort_field: str = "index",
        sort_order: str = "asc",
        poll_interval: float = DEFAULT_DOCKET_PDF_POLL_SECONDS,
        poll_timeout: float = DEFAULT_DOCKET_PDF_TIMEOUT_SECONDS,
    ) -> TaxCourtDownload:
        if poll_interval < 0:
            raise TaxCourtQueryError("poll interval must not be negative")
        if poll_timeout <= 0:
            raise TaxCourtQueryError("poll timeout must be positive")
        docket = canonical_docket_number(docket_number)
        start_url = (
            f"{API_ROOT}/public-api/cases/{quote(docket, safe='-')}/"
            "generate-docket-record"
        )
        job_payload = self._object(
            self._json(
                "POST",
                start_url,
                json_body={
                    "docketNumber": docket,
                    "docketRecordTableSort": {
                        "sortField": _required(sort_field, "sort field"),
                        "sortOrder": _required(sort_order, "sort order"),
                    },
                },
            ),
            start_url,
        )
        job_id = job_payload.get("jobId")
        if not isinstance(job_id, str) or not job_id:
            raise SourceSchemaError(
                "DAWSON printable-docket response is missing jobId",
                url=start_url,
            )

        status_url = (
            f"{API_ROOT}/public-api/docket-record-status/"
            f"{quote(job_id, safe='-')}"
        )
        deadline = self._clock() + poll_timeout
        while self._clock() < deadline:
            status = self._object(self._json("GET", status_url), status_url)
            state = status.get("status")
            if state == "ready":
                signed_url = status.get("url")
                if not isinstance(signed_url, str) or not signed_url:
                    raise SourceSchemaError(
                        "DAWSON ready docket job is missing url",
                        url=status_url,
                    )
                return self._download_signed_pdf(
                    signed_url,
                    public_request_url=start_url,
                    job_id=job_id,
                )
            if state == "error":
                message = str(
                    status.get("message")
                    or "DAWSON failed to generate the docket PDF"
                )
                status_code = status.get("statusCode")
                if status_code == 404:
                    raise TaxCourtNotFoundError(message, url=start_url)
                raise TaxCourtJobError(message)
            if state != "pending":
                raise SourceSchemaError(
                    "DAWSON docket job returned an unknown status",
                    url=status_url,
                    details={"status": status},
                )
            self._sleeper(poll_interval)
        raise TimeoutError(
            "Timed out waiting for DAWSON printable docket PDF"
        )


def _add_document_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--keyword", help="Full-text keyword or phrase query")
    parser.add_argument("--docket", help="Docket number")
    parser.add_argument(
        "--case-title",
        help="Case title or petitioner name",
    )
    parser.add_argument("--judge", help="Judge name")
    parser.add_argument(
        "--filed-after",
        help="Start date (YYYY-MM-DD or source-native MM/DD/YYYY)",
    )
    parser.add_argument(
        "--filed-before",
        help="End date (YYYY-MM-DD or source-native MM/DD/YYYY)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "Result count requested from DAWSON "
            f"(source ceiling {DOCUMENT_SEARCH_RESULT_CEILING:,})"
        ),
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the U.S. Tax Court DAWSON public API",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser(
        "probe",
        help="Check the deployed public API and show verified contracts",
    )
    add_output_args(probe)

    cases = subparsers.add_parser(
        "cases",
        help="Search cases by petitioner, date, state, type, or procedure",
    )
    cases.add_argument(
        "petitioner_name",
        nargs="?",
        help="Optional petitioner's full or last name",
    )
    cases.add_argument("--country-type")
    cases.add_argument("--state", dest="petitioner_state")
    cases.add_argument("--filed-after")
    cases.add_argument("--filed-before")
    cases.add_argument(
        "--case-type",
        action="append",
        default=[],
        dest="case_types",
        help=(
            "Exact DAWSON case-type label (for example, Deficiency or "
            "CDP (Lien/Levy)); repeat for more than one"
        ),
    )
    cases.add_argument("--procedure-type")
    cases.add_argument(
        "--limit",
        type=int,
        help="Optional caller-side slice after DAWSON returns its results",
    )
    add_output_args(cases)

    case = subparsers.add_parser("case", help="Fetch public case metadata")
    case.add_argument("docket_number")
    add_output_args(case)

    docket = subparsers.add_parser(
        "docket",
        help="Fetch all source-accessible docket pages or one native page",
    )
    docket.add_argument("docket_number")
    docket.add_argument(
        "--page",
        type=int,
        help=f"Native zero-based page (0 through {DOCKET_MAX_PAGE})",
    )
    add_output_args(docket)

    orders = subparsers.add_parser(
        "orders",
        help="Search public Tax Court orders",
    )
    _add_document_search_args(orders)

    opinions = subparsers.add_parser(
        "opinions",
        help="Search public Tax Court opinions",
    )
    _add_document_search_args(opinions)
    opinions.add_argument(
        "--opinion-type",
        action="append",
        default=[],
        dest="opinion_types",
        help=(
            "Opinion type or native event code; repeat as needed "
            "(defaults to all types)"
        ),
    )

    today_orders = subparsers.add_parser(
        "today-orders",
        help="Fetch today's public orders",
    )
    today_orders.add_argument(
        "--page",
        type=int,
        help="Fetch one native one-based page instead of all pages",
    )
    today_orders.add_argument(
        "--sort",
        default="filing-date-desc",
        help=(
            "filing-date-asc, filing-date-desc, page-count-asc, or "
            "page-count-desc (default: filing-date-desc)"
        ),
    )
    add_output_args(today_orders)

    today_opinions = subparsers.add_parser(
        "today-opinions",
        help="Fetch today's public opinions",
    )
    add_output_args(today_opinions)

    judges = subparsers.add_parser(
        "judges",
        help="Fetch the public judge directory used by search filters",
    )
    add_output_args(judges)

    trial_sessions = subparsers.add_parser(
        "trial-sessions",
        help="Fetch open public trial sessions",
    )
    add_output_args(trial_sessions)

    trial_session = subparsers.add_parser(
        "trial-session",
        help="Fetch a public trial session and its calendared cases",
    )
    trial_session.add_argument("trial_session_id")
    add_output_args(trial_session)

    download = subparsers.add_parser(
        "download",
        help="Download a public docket-entry PDF",
    )
    download.add_argument("docket_number")
    download.add_argument("docket_entry_id")
    download.add_argument("destination", type=Path)
    add_output_args(download)

    docket_pdf = subparsers.add_parser(
        "docket-pdf",
        help="Generate and download the official printable docket record",
    )
    docket_pdf.add_argument("docket_number")
    docket_pdf.add_argument("destination", type=Path)
    docket_pdf.add_argument("--sort-field", default="index")
    docket_pdf.add_argument("--sort-order", default="asc")
    docket_pdf.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_DOCKET_PDF_POLL_SECONDS,
    )
    docket_pdf.add_argument(
        "--poll-timeout",
        type=float,
        default=DEFAULT_DOCKET_PDF_TIMEOUT_SECONDS,
    )
    add_output_args(docket_pdf)
    return parser


def execute(
    args: argparse.Namespace,
    *,
    client: TaxCourtClient | None = None,
    log_results: bool = True,
) -> dict[str, Any]:
    client = client or TaxCourtClient()
    if args.command == "probe":
        result = client.health()
    elif args.command == "cases":
        result = client.search_cases(
            args.petitioner_name,
            country_type=args.country_type,
            petitioner_state=args.petitioner_state,
            filed_after=args.filed_after,
            filed_before=args.filed_before,
            case_types=args.case_types,
            procedure_type=args.procedure_type,
            limit=args.limit,
        )
    elif args.command == "case":
        result = client.get_case(args.docket_number)
    elif args.command == "docket":
        result = client.docket_entries(
            args.docket_number,
            page=args.page,
        )
    elif args.command == "orders":
        result = client.search_orders(
            keyword=args.keyword,
            docket_number=args.docket,
            case_title_or_petitioner=args.case_title,
            judge=args.judge,
            filed_after=args.filed_after,
            filed_before=args.filed_before,
            limit=args.limit,
        )
    elif args.command == "opinions":
        result = client.search_opinions(
            keyword=args.keyword,
            docket_number=args.docket,
            case_title_or_petitioner=args.case_title,
            judge=args.judge,
            filed_after=args.filed_after,
            filed_before=args.filed_before,
            opinion_types=args.opinion_types,
            limit=args.limit,
        )
    elif args.command == "today-orders":
        result = client.todays_orders(page=args.page, sort=args.sort)
    elif args.command == "today-opinions":
        result = client.todays_opinions()
    elif args.command == "judges":
        result = client.judges()
    elif args.command == "trial-sessions":
        result = client.trial_sessions()
    elif args.command == "trial-session":
        result = client.trial_session(args.trial_session_id)
    elif args.command == "download":
        download = client.download_document(
            args.docket_number,
            args.docket_entry_id,
        )
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        args.destination.write_bytes(download.content)
        result = {
            **_envelope(
                "download",
                {
                    "docket_number": canonical_docket_number(
                        args.docket_number
                    ),
                    "docket_entry_id": args.docket_entry_id,
                },
            ),
            **download.metadata(args.destination),
            "docket_number": canonical_docket_number(args.docket_number),
            "docket_entry_id": args.docket_entry_id,
            "evidence_ref": tax_court_evidence_ref(
                args.docket_number,
                args.docket_entry_id,
            ),
        }
    elif args.command == "docket-pdf":
        download = client.generate_docket_pdf(
            args.docket_number,
            sort_field=args.sort_field,
            sort_order=args.sort_order,
            poll_interval=args.poll_interval,
            poll_timeout=args.poll_timeout,
        )
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        args.destination.write_bytes(download.content)
        result = {
            **_envelope(
                "docket-pdf",
                {
                    "docket_number": canonical_docket_number(
                        args.docket_number
                    ),
                    "sort_field": args.sort_field,
                    "sort_order": args.sort_order,
                },
            ),
            **download.metadata(args.destination),
            "docket_number": canonical_docket_number(args.docket_number),
            "evidence_ref": tax_court_evidence_ref(args.docket_number),
            "sort_field": args.sort_field,
            "sort_order": args.sort_order,
        }
    else:
        raise TaxCourtQueryError(f"unsupported command: {args.command}")

    if log_results:
        record_count: int | None
        if isinstance(result.get("records"), list):
            record_count = len(result["records"])
        elif result.get("resource") is not None:
            record_count = 1
        elif result.get("sha256"):
            record_count = 1
        else:
            record_count = None
        log_search(
            json.dumps(
                {
                    "command": args.command,
                    "query": result.get("query", {}),
                },
                sort_keys=True,
            ),
            SOURCE_ID,
            record_count,
        )
    return result


def _print_human(result: Mapping[str, Any]) -> None:
    if isinstance(result.get("records"), list):
        print(
            f"{SOURCE_NAME}: {len(result['records']):,} "
            f"{result.get('command', 'records')}"
        )
        for record in result["records"]:
            docket = record.get("docketNumberWithSuffix") or record.get(
                "docketNumber"
            )
            title = (
                record.get("caseCaption")
                or record.get("documentTitle")
                or record.get("judgeFullName")
                or record.get("trialLocation")
                or record.get("name")
            )
            print(" | ".join(str(value) for value in (docket, title) if value))
        return
    if isinstance(result.get("resource"), Mapping):
        print(json.dumps(result["resource"], indent=2, default=str))
        return
    print(json.dumps(result, indent=2, default=str))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = execute(args)
    except (
        TaxCourtQueryError,
        TaxCourtNotFoundError,
        TaxCourtJobError,
        HTTPStatusError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        TimeoutError,
    ) as error:
        print(f"Tax Court query failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    summary = f"{SOURCE_NAME} {args.command}"
    result_count = (
        len(result["records"])
        if isinstance(result.get("records"), list)
        else 1
    )
    if not write_output(
        result,
        args,
        summary=summary,
        result_count=result_count,
    ):
        _print_human(result)


if __name__ == "__main__":
    main()
