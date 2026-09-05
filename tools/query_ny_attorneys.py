#!/usr/bin/env python3
"""New York attorney registrations from the official OCA open dataset.

The Unified Court System's interactive Attorney Directory uses a browser
challenge. The same public registration data is published by the New York
Office of Court Administration through NY Open Data as Socrata dataset
``eqw2-r5nb``. This adapter uses that supported API and keeps the interactive
directory, written-request process, public discipline decisions, and NYSCEF
case filings visible as complementary routes.

Usage:
    uv run python tools/query_ny_attorneys.py search "Brad Karp"
    uv run python tools/query_ny_attorneys.py search --company "KIRKLAND & ELLIS LLP"
    uv run python tools/query_ny_attorneys.py registration 2064509
    uv run python tools/query_ny_attorneys.py probe --output /tmp/ny-attorneys.json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

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
        PaginatedFetch,
        PublicRecordsHTTPError,
        RetryPolicy,
        SocrataSODAClient,
        SourceSchemaError,
        failure_result,
    )
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
        PaginatedFetch,
        PublicRecordsHTTPError,
        RetryPolicy,
        SocrataSODAClient,
        SourceSchemaError,
        failure_result,
    )


SOURCE_ID = "us-ny-oca-attorney-registrations"
DATASET_ID = "eqw2-r5nb"
BASE_URL = "https://data.ny.gov/resource"
QUERY_URL = f"{BASE_URL}/{DATASET_ID}.json"
METADATA_URL = f"https://data.ny.gov/api/views/{DATASET_ID}"
DATASET_URL = f"https://data.ny.gov/d/{DATASET_ID}"
INTERACTIVE_DIRECTORY_URL = (
    "https://iapps.courts.state.ny.us/attorneyservices/search"
)
PUBLIC_ACCESS_RULE_URL = (
    "https://www.nycourts.gov/rules/rule/"
    "section-1182-public-access-attorney-registration-information"
)
NYSCEF_URL = "https://iapps.courts.state.ny.us/nyscef/HomePage"
AD1_REGISTRATION_URL = (
    "https://nycourts.gov/courts/ad1/Committees%26Programs/CFC/"
    "delinquent-registration.shtml"
)
AD2_ATTORNEY_MATTERS_URL = (
    "https://www.nycourts.gov/courts/ad2/attorneymatters_ada.shtml"
)
AD3_DISCIPLINE_URL = "https://www.nycourts.gov/ad3/agc/"
AD4_DISCIPLINE_URL = (
    "https://www.nycourts.gov/courts/ad4/clerk/attymttrs/"
    "atty-discip.html"
)
AD4_DECISIONS_URL = (
    "https://www.nycourts.gov/courts/ad4/clerk/decisions/2025/"
    "disciplinary.shtm"
)

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_PAGE_SIZE = 1_000
CURSOR_PREFIX = "ny-oca-attorneys:v2:"
CURSOR_VERSION = 2
ORDERING = "registration_number ASC"
PROBE_REGISTRATION_NUMBER = "2064509"

EXPECTED_FIELDS = (
    "registration_number",
    "first_name",
    "middle_name",
    "last_name",
    "suffix",
    "company_name",
    "street_1",
    "street_2",
    "city",
    "state",
    "zip",
    "zip_plus_four",
    "country",
    "county",
    "phone_number",
    "year_admitted",
    "judicial_department_of_admission",
    "law_school",
    "status",
    "next_registration",
)

TEXT_FIELDS = {
    "first-name": "first_name",
    "middle-name": "middle_name",
    "last-name": "last_name",
    "company": "company_name",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "country": "country",
    "county": "county",
    "law-school": "law_school",
    "status": "status",
}

STRUCTURED_FILTERS = {
    "first": "first_name",
    "middle": "middle_name",
    "last": "last_name",
    "company": "company_name",
    "city": "city",
    "state": "state",
    "postal_code": "zip",
    "country": "country",
    "county": "county",
    "law_school": "law_school",
    "status": "status",
}

DEPARTMENT_LABELS = {
    "1": "First Judicial Department",
    "2": "Second Judicial Department",
    "3": "Third Judicial Department",
    "4": "Fourth Judicial Department",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="NYS Attorney Registrations",
    source_role="state_attorney_registration",
    base_url=BASE_URL,
    dataset_id=DATASET_ID,
    metadata={
        "authority": "New York State Unified Court System",
        "publisher": "New York State Office of Court Administration",
        "coverage": (
            "All attorneys admitted in New York, resident or nonresident, "
            "active, retired, or otherwise registered"
        ),
        "posting_frequency": "quarterly",
        "dataset_url": DATASET_URL,
        "metadata_url": METADATA_URL,
        "interactive_directory_url": INTERACTIVE_DIRECTORY_URL,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="36",
    name="New York State",
    state_code="NY",
    metadata={
        "court_system": "New York State Unified Court System",
        "registration_authority": "Office of Court Administration",
    },
)

WARNINGS = (
    "The API is a quarterly public-registration snapshot; the interactive "
    "directory may reflect changes made after the dataset refresh.",
    "Public discipline decisions and case appearances are separate sources "
    "linked in each record's complementary_routes.",
)


class SelectionError(RuntimeError):
    """A caller selection or continuation does not fit this source contract."""

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
            retryable=False,
            details=self.details,
        )


class NYAttorneyClient(SocrataSODAClient):
    """Socrata client with OCA dataset metadata and count helpers."""

    def dataset_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(METADATA_URL, params={})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "NYS attorney dataset metadata is not an object",
                url=METADATA_URL,
            )
        return payload

    def count(self, where: str) -> int:
        payload = self._request_json(
            self.query_url,
            params={"$select": "count(*) as count", "$where": where},
            headers=(
                {"X-App-Token": self.app_token} if self.app_token else {}
            ),
        )
        if (
            not isinstance(payload, list)
            or len(payload) != 1
            or not isinstance(payload[0], Mapping)
        ):
            raise SourceSchemaError(
                "NYS attorney count response is not a one-row array",
                url=self.query_url,
            )
        try:
            count = int(str(payload[0]["count"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceSchemaError(
                "NYS attorney count response has no integer count",
                url=self.query_url,
                details={"response": payload},
            ) from exc
        if count < 0:
            raise SourceSchemaError(
                "NYS attorney count response is negative",
                url=self.query_url,
                details={"count": count},
            )
        return count


def _new_client(args: argparse.Namespace) -> NYAttorneyClient:
    return NYAttorneyClient(
        BASE_URL,
        DATASET_ID,
        app_token=os.environ.get("NY_OPEN_DATA_APP_TOKEN"),
        page_size=args.page_size,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )


def _clean(value: Any) -> str | None:
    text = " ".join(str(value or "").replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any) -> str:
    text = _clean(value)
    if not text:
        raise ValueError("query values must not be blank")
    return text.replace("'", "''").upper()


def _registration_number(value: Any) -> str:
    text = _clean(value)
    if not text or not text.isdigit():
        raise ValueError("registration number must contain digits only")
    return text


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _next_registration(value: Any) -> dict[str, Any]:
    raw = _clean(value)
    normalized = None
    if raw:
        try:
            normalized = datetime.strptime(raw, "%b %Y").strftime("%Y-%m")
        except ValueError:
            normalized = None
    return {
        "raw": raw,
        "year_month": normalized,
        "precision": "month" if normalized else None,
    }


def _match_clause(field: str, value: Any, match: str) -> str:
    literal = _sql_text(value)
    if match == "exact":
        pattern = literal
        operator = "="
    elif match == "prefix":
        pattern = f"{literal}%"
        operator = "LIKE"
    elif match == "contains":
        pattern = f"%{literal}%"
        operator = "LIKE"
    else:
        raise ValueError(f"unsupported match mode: {match}")
    return f"upper({field}) {operator} '{pattern}'"


def _name_clause(value: Any, match: str) -> str:
    tokens = (_clean(value) or "").split()
    if not tokens:
        raise ValueError("name query must not be blank")
    clauses = []
    for token in tokens:
        candidates = [
            _match_clause(field, token, match)
            for field in ("first_name", "middle_name", "last_name")
        ]
        clauses.append(f"({' OR '.join(candidates)})")
    return " AND ".join(clauses)


def _search_where(args: argparse.Namespace) -> str:
    clauses: list[str] = []
    query = _clean(args.query)
    if query:
        if args.field == "name":
            clauses.append(_name_clause(query, args.match))
        else:
            clauses.append(
                _match_clause(TEXT_FIELDS[args.field], query, args.match)
            )
    for argument, field in STRUCTURED_FILTERS.items():
        value = getattr(args, argument, None)
        if _clean(value):
            clauses.append(_match_clause(field, value, "exact"))
    if args.year_admitted is not None:
        clauses.append(f"year_admitted={int(args.year_admitted)}")
    if args.department is not None:
        clauses.append(
            f"judicial_department_of_admission={int(args.department)}"
        )
    return " AND ".join(f"({clause})" for clause in clauses) or "1=1"


def _metadata_contract(
    metadata: Mapping[str, Any],
) -> tuple[str, int, str, tuple[dict[str, Any], ...]]:
    if metadata.get("id") != DATASET_ID:
        raise SourceSchemaError(
            "NYS attorney metadata identifies a different dataset",
            url=METADATA_URL,
            details={"dataset_id": metadata.get("id")},
        )
    columns = metadata.get("columns")
    if not isinstance(columns, list) or not all(
        isinstance(column, Mapping) for column in columns
    ):
        raise SourceSchemaError(
            "NYS attorney metadata has no column declarations",
            url=METADATA_URL,
        )
    declared = tuple(
        {
            key: column.get(key)
            for key in ("fieldName", "dataTypeName", "description")
        }
        for column in columns
    )
    published = {
        str(column.get("fieldName"))
        for column in columns
        if column.get("fieldName")
    }
    missing = sorted(set(EXPECTED_FIELDS) - published)
    if missing:
        raise SourceSchemaError(
            "NYS attorney dataset no longer publishes expected fields",
            url=METADATA_URL,
            details={"missing_fields": missing},
        )
    rows_updated_at = metadata.get("rowsUpdatedAt")
    if isinstance(rows_updated_at, bool) or not isinstance(
        rows_updated_at, int
    ):
        raise SourceSchemaError(
            "NYS attorney metadata has no integer rowsUpdatedAt",
            url=METADATA_URL,
            details={"rowsUpdatedAt": rows_updated_at},
        )
    rows_updated_iso = (
        datetime.fromtimestamp(rows_updated_at, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    fingerprint = sha256_fingerprint(
        {
            "dataset_id": DATASET_ID,
            "columns": sorted(declared, key=lambda item: str(item["fieldName"])),
        }
    )
    return fingerprint, rows_updated_at, rows_updated_iso, declared


def _cursor_encode(payload: Mapping[str, Any]) -> str:
    cursor_payload = dict(payload)
    cursor_payload["check"] = sha256_fingerprint(cursor_payload)[:16]
    encoded = base64.urlsafe_b64encode(
        canonical_json(cursor_payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def _cursor_decode(cursor: str | None) -> Mapping[str, Any] | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise SelectionError(
            "cursor_invalid",
            "cursor does not belong to the NY attorney adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        decoded = json.loads(
            base64.urlsafe_b64decode(
                token + "=" * (-len(token) % 4)
            ).decode("utf-8")
        )
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise SelectionError(
            "cursor_invalid",
            "cursor payload is malformed",
        ) from exc
    if not isinstance(decoded, Mapping):
        raise SelectionError(
            "cursor_invalid",
            "cursor payload is incomplete",
        )
    payload = dict(decoded)
    supplied_check = payload.pop("check", None)
    expected_check = sha256_fingerprint(payload)[:16]
    required = {
        "version": int,
        "criteria": str,
        "schema": str,
        "rows_updated_at": int,
        "total": int,
        "offset": int,
    }
    if any(
        not isinstance(payload.get(key), value_type)
        for key, value_type in required.items()
    ) or any(
        isinstance(payload.get(key), bool)
        for key in ("version", "rows_updated_at", "total", "offset")
    ):
        raise SelectionError(
            "cursor_invalid",
            "cursor payload is incomplete",
        )
    if (
        supplied_check != expected_check
        or payload["version"] != CURSOR_VERSION
        or payload["rows_updated_at"] < 0
        or payload["total"] < 0
        or payload["offset"] < 0
        or len(payload["criteria"]) != 64
        or len(payload["schema"]) != 64
        or any(
            character not in "0123456789abcdef"
            for value in (payload["criteria"], payload["schema"])
            for character in value
        )
    ):
        raise SelectionError(
            "cursor_invalid",
            "cursor integrity or snapshot values are invalid",
        )
    return payload


def _query_contract(
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
    where: str,
    criteria: str,
    page_size: int,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=dict(parameters),
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "dataset_id": DATASET_ID,
                "where": where,
                "ordering": ORDERING,
                "criteria_fingerprint": criteria,
                "transport_page_size": page_size,
                "server_page_ceiling": (
                    "not observed; current endpoint accepted a page limit "
                    "above 50,000"
                ),
            },
        ),
    )


def _complementary_routes(registration_number: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "Unified Court System interactive Attorney Directory",
            "url": INTERACTIVE_DIRECTORY_URL,
            "adds": [
                "current interactive registration detail",
                "directory discipline-history links when published",
            ],
            "lookup": {
                "registration_number": registration_number,
                "mode": "interactive_name_search",
            },
        },
        {
            "name": "22 NYCRR 118.2 written-request registration data",
            "url": PUBLIC_ACCESS_RULE_URL,
            "adds": [
                "single-name registration inquiry",
                "geographic registration lists",
                "all-registered-attorney list",
            ],
        },
        {
            "name": "Appellate Division public discipline sources",
            "urls": {
                "first_department_registration_notices": AD1_REGISTRATION_URL,
                "second_department_attorney_matters": AD2_ATTORNEY_MATTERS_URL,
                "third_department_grievance_committee": AD3_DISCIPLINE_URL,
                "fourth_department_discipline": AD4_DISCIPLINE_URL,
                "fourth_department_decisions": AD4_DECISIONS_URL,
            },
            "adds": [
                "public discipline decisions",
                "registration suspension and reinstatement notices",
            ],
        },
        {
            "name": "NYSCEF civil case filings",
            "url": NYSCEF_URL,
            "adapter": "tools/query_nyscef.py",
            "adds": [
                "case appearances",
                "filed documents carrying attorney registration numbers",
            ],
        },
    ]


def _normalize_record(
    row: Mapping[str, Any],
    *,
    declared_schema_fingerprint: str,
    response_schema_fingerprint: str,
    rows_updated_at: int,
    rows_updated_iso: str,
) -> dict[str, Any]:
    raw = dict(row)
    registration_number = _registration_number(
        raw.get("registration_number")
    )
    first = _clean(raw.get("first_name"))
    middle = _clean(raw.get("middle_name"))
    last = _clean(raw.get("last_name"))
    suffix = _clean(raw.get("suffix"))
    if not first or not last:
        raise SourceSchemaError(
            "NYS attorney row lacks a first or last name",
            url=QUERY_URL,
            details={"registration_number": registration_number},
        )
    display_name = " ".join(
        value for value in (first, middle, last, suffix) if value
    )
    department = _clean(raw.get("judicial_department_of_admission"))
    return {
        "record_kind": "attorney_registration",
        "source_id": SOURCE_ID,
        "dataset_id": DATASET_ID,
        "source_record_id": registration_number,
        "canonical_ref": f"{SOURCE_ID}:registration:{registration_number}",
        "native_ids": {
            "registration_number": registration_number,
        },
        "name": {
            "display": display_name,
            "first": first,
            "middle": middle,
            "last": last,
            "suffix": suffix,
        },
        "registration": {
            "status": _clean(raw.get("status")),
            "year_admitted": _integer(raw.get("year_admitted")),
            "judicial_department_of_admission": department,
            "judicial_department_label": DEPARTMENT_LABELS.get(
                department or ""
            ),
            "next_registration": _next_registration(
                raw.get("next_registration")
            ),
        },
        "organization": {
            "name": _clean(raw.get("company_name")),
            "relationship": "registered_office_or_employer",
        },
        "education": {
            "law_school": _clean(raw.get("law_school")),
        },
        "office": {
            "street_1": _clean(raw.get("street_1")),
            "street_2": _clean(raw.get("street_2")),
            "city": _clean(raw.get("city")),
            "state": _clean(raw.get("state")),
            "postal_code": _clean(raw.get("zip")),
            "postal_code_plus_four": _clean(raw.get("zip_plus_four")),
            "country": _clean(raw.get("country")),
            "new_york_county_or_out_of_state": _clean(raw.get("county")),
            "business_phone": _clean(raw.get("phone_number")),
        },
        "source_snapshot": {
            "posting_frequency": "quarterly",
            "rows_updated_at_epoch": rows_updated_at,
            "rows_updated_at": rows_updated_iso,
            "declared_schema_fingerprint": declared_schema_fingerprint,
            "response_schema_fingerprint": response_schema_fingerprint,
        },
        "source_urls": {
            "dataset": DATASET_URL,
            "api": QUERY_URL,
            "metadata": METADATA_URL,
            "interactive_directory": INTERACTIVE_DIRECTORY_URL,
        },
        "complementary_routes": _complementary_routes(
            registration_number
        ),
        "raw_record": raw,
    }


def _selection_failure(
    query: PublicRecordsQuery,
    error: SelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=WARNINGS,
    )


def _normalization_failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.SOURCE_CHANGED,
        [
            PublicRecordsError(
                code="normalization_failed",
                message=str(error),
                category="source_schema",
                retryable=False,
                details={"dataset_url": DATASET_URL},
            )
        ],
        warnings=WARNINGS,
    )


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
    except Exception as exc:
        print(f"Warning: search log was not updated: {exc}", file=sys.stderr)


def _execute_collection(
    args: argparse.Namespace,
    client: Any,
    *,
    operation: str,
    where: str,
    parameters: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
    exact_one: bool = False,
    probe: bool = False,
) -> PublicRecordsResult:
    criteria = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "operation": operation,
            "where": where,
            "order": ORDERING,
        }
    )
    query = _query_contract(
        operation,
        parameters=parameters,
        limit=limit,
        cursor=cursor,
        where=where,
        criteria=criteria,
        page_size=args.page_size,
    )
    try:
        metadata = client.dataset_metadata()
        (
            declared_schema,
            rows_updated_at,
            rows_updated_iso,
            declared_columns,
        ) = _metadata_contract(metadata)
        total = client.count(where)
        state = _cursor_decode(cursor)
        offset = 0
        if state is not None:
            expected = {
                "criteria": criteria,
                "schema": declared_schema,
                "rows_updated_at": rows_updated_at,
                "total": total,
            }
            for key, value in expected.items():
                if state.get(key) != value:
                    raise SelectionError(
                        "cursor_snapshot_changed",
                        "cursor does not match the current query snapshot",
                        details={
                            "field": key,
                            "cursor_value": state.get(key),
                            "current_value": value,
                        },
                    )
            offset = int(state["offset"])
            if offset > total:
                raise SelectionError(
                    "cursor_invalid",
                    "cursor offset exceeds the matching result count",
                    details={"offset": offset, "total": total},
                )
        fetch: PaginatedFetch = client.query(
            {
                "$where": where,
                "$order": ORDERING,
                "$offset": offset,
            },
            requested_limit=limit,
        )
        final_metadata = client.dataset_metadata()
        (
            final_schema,
            final_rows_updated_at,
            _final_rows_updated_iso,
            _final_declared_columns,
        ) = _metadata_contract(final_metadata)
        if (
            final_schema != declared_schema
            or final_rows_updated_at != rows_updated_at
        ):
            raise SelectionError(
                "dataset_snapshot_changed",
                "dataset changed while the query was being traversed",
                details={
                    "initial_rows_updated_at": rows_updated_at,
                    "final_rows_updated_at": final_rows_updated_at,
                },
            )
        raw_records = list(fetch.records)
        remaining = total - offset
        expected_count = remaining if limit is None else min(limit, remaining)
        if len(raw_records) != expected_count:
            raise SourceSchemaError(
                "NYS attorney traversal did not return the expected row count",
                url=QUERY_URL,
                details={
                    "offset": offset,
                    "total": total,
                    "requested_limit": limit,
                    "expected_records": expected_count,
                    "returned_records": len(raw_records),
                },
            )
        if exact_one and len(raw_records) > 1:
            raise SourceSchemaError(
                "exact registration lookup returned multiple rows",
                url=QUERY_URL,
                details={"returned_records": len(raw_records)},
            )
        records = [
            _normalize_record(
                row,
                declared_schema_fingerprint=declared_schema,
                response_schema_fingerprint=fetch.schema_fingerprint,
                rows_updated_at=rows_updated_at,
                rows_updated_iso=rows_updated_iso,
            )
            for row in raw_records
        ]
        next_cursor = None
        next_offset = offset + len(records)
        if limit is not None and next_offset < total:
            next_cursor = _cursor_encode(
                {
                    "version": CURSOR_VERSION,
                    "criteria": criteria,
                    "schema": declared_schema,
                    "rows_updated_at": rows_updated_at,
                    "total": total,
                    "offset": next_offset,
                }
            )
        if probe:
            if len(records) != 1:
                raise SourceSchemaError(
                    "NYS attorney probe sentinel did not resolve uniquely",
                    url=QUERY_URL,
                    details={
                        "registration_number": PROBE_REGISTRATION_NUMBER,
                        "returned_records": len(records),
                    },
                )
            request_breakdown = {
                "initial_metadata": 1,
                "matching_count": 1,
                "sentinel_query": fetch.requests_made,
                "final_metadata": 1,
                "total_count": 1,
            }
            probe_record = {
                "record_kind": "source_probe",
                "source_id": SOURCE_ID,
                "dataset_id": DATASET_ID,
                "dataset_name": metadata.get("name"),
                "attribution": metadata.get("attribution"),
                "provenance": metadata.get("provenance"),
                "total_registration_rows": client.count("1=1"),
                "declared_field_count": len(declared_columns),
                "declared_fields": [
                    item["fieldName"] for item in declared_columns
                ],
                "declared_schema_fingerprint": declared_schema,
                "rows_updated_at_epoch": rows_updated_at,
                "rows_updated_at": rows_updated_iso,
                "transport_page_size": args.page_size,
                "server_page_ceiling": (
                    "not observed; current endpoint accepted a page limit "
                    "above 50,000"
                ),
                "requests_made": sum(request_breakdown.values()),
                "request_breakdown": request_breakdown,
                "sentinel": records[0],
            }
            return PublicRecordsResult.success(
                query,
                [probe_record],
                warnings=WARNINGS,
                raw_artifact_refs=[METADATA_URL, QUERY_URL],
            )
        return PublicRecordsResult.success(
            query,
            records,
            next_cursor=next_cursor,
            warnings=WARNINGS,
            raw_artifact_refs=[METADATA_URL, QUERY_URL],
        )
    except SelectionError as exc:
        return _selection_failure(query, exc)
    except PublicRecordsHTTPError as exc:
        return failure_result(query, exc, warnings=WARNINGS)
    except (TypeError, ValueError) as exc:
        return _normalization_failure(query, exc)


def source_manifest() -> dict[str, Any]:
    return {
        "schema_version": "ny-oca-attorney-sources/1.0",
        "primary_source": SOURCE_METADATA.to_dict(),
        "coverage": {
            "scope": (
                "All attorneys admitted in New York, including resident and "
                "nonresident, active, retired, delinquent, suspended, "
                "resigned, disbarred, deceased, and incapacitated statuses"
            ),
            "posting_frequency": "quarterly",
            "published_fields": list(EXPECTED_FIELDS),
            "identity_key": "registration_number",
        },
        "pagination": {
            "caller_bound": (
                "optional --limit; omitted search bounds traverse all matches"
            ),
            "transport_batch_size": DEFAULT_PAGE_SIZE,
            "server_page_ceiling": (
                "not observed; current endpoint accepted a page limit "
                "above 50,000"
            ),
            "bounded_probe_records": 2,
            "ordering": ORDERING,
        },
        "capabilities": [
            {
                "name": "NY Open Data Socrata API",
                "url": QUERY_URL,
                "access": "anonymous API; optional app token",
                "adds": [
                    "all public registration rows",
                    "office and organization",
                    "status and admission",
                    "law school and next registration month",
                ],
                "adapter_commands": ["search", "registration", "probe"],
            },
            {
                "name": "Unified Court System interactive directory",
                "url": INTERACTIVE_DIRECTORY_URL,
                "access": "interactive browser with hCaptcha",
                "adds": [
                    "interactive current detail",
                    "discipline-history links when published",
                ],
            },
            {
                "name": "22 NYCRR 118.2 written request",
                "url": PUBLIC_ACCESS_RULE_URL,
                "access": "written request to OCA Attorney Registration Unit",
                "adds": [
                    "single-name inquiry",
                    "geographic list",
                    "all-registered-attorney list",
                ],
                "published_fee_schedule": {
                    "first_individual_name": "$0",
                    "each_additional_name": "$2.50",
                    "geographic_100_or_fewer": "$25",
                    "each_additional_geographic_100": "$1",
                    "all_registered_attorneys": "$100",
                },
            },
            {
                "name": "Appellate Division discipline sources",
                "urls": {
                    "department_1": AD1_REGISTRATION_URL,
                    "department_2": AD2_ATTORNEY_MATTERS_URL,
                    "department_3": AD3_DISCIPLINE_URL,
                    "department_4": AD4_DISCIPLINE_URL,
                },
                "adds": [
                    "public discipline decisions",
                    "suspension and reinstatement notices",
                ],
            },
            {
                "name": "NYSCEF case filings",
                "url": NYSCEF_URL,
                "adapter": "tools/query_nyscef.py",
                "adds": [
                    "case appearances",
                    "registration numbers in filed documents",
                    "counsel-to-party relationships",
                ],
            },
        ],
        "field_gaps": {
            "socrata_dataset": [
                "discipline decision text",
                "case appearances",
                "registration history between quarterly snapshots",
            ],
            "interactive_directory": [
                "bulk machine traversal",
                "case appearances",
            ],
            "nyscef": [
                "statewide registration status",
                "attorneys without an observed public case filing",
            ],
        },
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    if args.command == "sources":
        return source_manifest()
    active_client = client or _new_client(args)
    if args.command == "search":
        where = _search_where(args)
        parameters = {
            "query": _clean(args.query),
            "field": args.field,
            "match": args.match,
            "filters": {
                key: getattr(args, key, None)
                for key in (*STRUCTURED_FILTERS, "year_admitted", "department")
                if getattr(args, key, None) is not None
            },
        }
        result = _execute_collection(
            args,
            active_client,
            operation="search",
            where=where,
            parameters=parameters,
            limit=args.limit,
            cursor=args.cursor,
        )
    elif args.command == "registration":
        registration_number = _registration_number(args.registration_number)
        result = _execute_collection(
            args,
            active_client,
            operation="registration",
            where=f"registration_number={int(registration_number)}",
            parameters={"registration_number": registration_number},
            limit=2,
            cursor=None,
            exact_one=True,
        )
    elif args.command == "probe":
        result = _execute_collection(
            args,
            active_client,
            operation="probe",
            where=f"registration_number={int(PROBE_REGISTRATION_NUMBER)}",
            parameters={
                "sentinel_registration_number": PROBE_REGISTRATION_NUMBER
            },
            limit=2,
            cursor=None,
            exact_one=True,
            probe=True,
        )
    else:
        raise ValueError(f"unsupported command: {args.command}")
    if log_results:
        _best_effort_log(result.query, result)
    return result


def _add_transport(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the official NYS OCA attorney-registration dataset and "
            "describe complementary court sources"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="Describe primary coverage, alternatives, and field gaps",
    )
    add_output_args(sources)

    search = subparsers.add_parser(
        "search",
        help="Search public attorney-registration rows",
    )
    search.add_argument("query", nargs="?")
    search.add_argument(
        "--field",
        choices=("name", *TEXT_FIELDS),
        default="name",
    )
    search.add_argument(
        "--match",
        choices=("exact", "prefix", "contains"),
        default="contains",
    )
    search.add_argument("--first")
    search.add_argument("--middle")
    search.add_argument("--last")
    search.add_argument("--company")
    search.add_argument("--city")
    search.add_argument("--state")
    search.add_argument("--postal-code")
    search.add_argument("--country")
    search.add_argument("--county")
    search.add_argument("--law-school")
    search.add_argument("--status")
    search.add_argument("--year-admitted", type=int)
    search.add_argument("--department", type=int, choices=(1, 2, 3, 4))
    search.add_argument(
        "--limit",
        type=int,
        help="Return at most this many records; omitted traverses all matches",
    )
    search.add_argument(
        "--cursor",
        help="Continuation from the same query and dataset snapshot",
    )
    _add_transport(search)

    registration = subparsers.add_parser(
        "registration",
        help="Fetch one attorney by unique OCA registration number",
    )
    registration.add_argument("registration_number")
    _add_transport(registration)

    probe = subparsers.add_parser(
        "probe",
        help="Run bounded metadata, count, and exact-sentinel checks",
    )
    _add_transport(probe)
    return parser


def _validate_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    limit = getattr(args, "limit", None)
    if limit is not None and limit <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "page_size", 1) <= 0:
        parser.error("--page-size must be positive")
    if getattr(args, "timeout", 1.0) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0.0) < 0:
        parser.error("--minimum-interval cannot be negative")
    if getattr(args, "retry_attempts", 1) < 1:
        parser.error("--retry-attempts must be at least 1")
    if getattr(args, "year_admitted", 1) is not None and getattr(
        args, "year_admitted", 1
    ) <= 0:
        parser.error("--year-admitted must be positive")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(args, parser)
    result = execute(args)
    payload = (
        result.to_dict()
        if isinstance(result, PublicRecordsResult)
        else dict(result)
    )
    summary = (
        f"NYS attorney {args.command}"
        if args.command != "search"
        else f"NYS attorney search {args.query or '(structured filters)'}"
    )
    if write_output(payload, args, summary=summary):
        return
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
