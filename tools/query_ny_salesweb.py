#!/usr/bin/env python3
"""Search New York ORPTS SalesWeb real-property transfer records.

SalesWeb publishes a rolling ten-year index of RP-5217 real-property transfer
reports for New York State outside New York City.  The current Municipal Data
Portal exposes public JSON search and detail services plus a CSV export.  The
source is updated weekly and may be corrected after initial publication.

The ORPTS ``saleTranNmbr`` is retained as the sale identity.  Parcel identity is
kept separately: ``swisCd`` plus ``printKey`` forms the exact
``SWIS_PRINT_KEY_ID`` used by the NY Statewide Parcel Map adapter.

Examples:
    uv run python tools/query_ny_salesweb.py search \
        --county Albany --seller CROSIER --limit 25 \
        --output /tmp/ny-sales.json
    uv run python tools/query_ny_salesweb.py search \
        --municipality 012000 --sale-from 2025-01-01 --all \
        --output /tmp/berne-sales.json
    uv run python tools/query_ny_salesweb.py detail 2047101021 --json
    uv run python tools/query_ny_salesweb.py export \
        --municipality 012000 --limit 100 --csv-output /tmp/sales.csv \
        --output /tmp/sales-export.json
    uv run python tools/query_ny_salesweb.py references --json
    uv run python tools/query_ny_salesweb.py alternatives --json
    uv run python tools/query_ny_salesweb.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import requests

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
        PaginationError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
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
        PaginationError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-ny-orpts-sales-web"
STATE_CODE = "NY"
STATE_FIPS = "36"
LANDING_URL = "https://www.tax.ny.gov/research/property/assess/sales/salesweb.htm"
MUNICIPAL_PORTAL_URL = "https://www.tax.ny.gov/pit/property/munidataportal.htm"
APP_URL = "https://pad.tax.ny.gov"
API_ROOT = f"{APP_URL}/api/nimu-pad-sales-web/SALESWEBUC"
COMMON_API_URL = f"{APP_URL}/api/nimu-pad-common/PADCOMMONUC"
TRANSFER_INFO_URL = (
    "https://www.tax.ny.gov/pit/property/new-homebuyers/transfer-reporting.htm"
)
TRANSFER_STATUTES_URL = (
    "https://www.tax.ny.gov/research/property/assess/sales/salesstatutes.htm"
)
ACRIS_URL = "https://www.nyc.gov/site/finance/property/acris.page"
ACRIS_SEARCH_URL = "https://a836-acris.nyc.gov/DS/DocumentSearch/Index"
RICHMOND_CLERK_URL = "https://richmondcountyclerk.com/Search/SearchIndex"
NYC_PROPERTY_PORTAL_URL = "https://propertyinformationportal.nyc.gov/"
STATEWIDE_PARCELS_URL = "https://gis.ny.gov/parcels"

DEFAULT_TIMEOUT = 45.0
DEFAULT_PAGE_SIZE = 100
DEFAULT_LIMIT = 100
DEFAULT_MINIMUM_INTERVAL = 0.1
CURSOR_PREFIX = "ny-salesweb:v1:"
CURSOR_VERSION = 1

SEARCH_ACTION = "fetchSalesWebData"
DETAIL_ACTION = "fetchSalesWebRowData"
REFERENCE_ACTION = "getRefTbls"
EXPORT_ACTION = "downloadResults"

SEARCH_REQUIRED_FIELDS = frozenset(
    {
        "saleTranNmbr",
        "swisCd",
        "printKey",
        "saleDt",
        "salePriceAmt",
        "buyerLastName",
        "sellerLastName",
    }
)
DETAIL_REQUIRED_FIELDS = SEARCH_REQUIRED_FIELDS | {
    "bookNmbr",
    "pageNmbr",
    "parcelId",
    "rollYr",
}
REFERENCE_REQUIRED_FIELDS = {
    "muniRef": frozenset({"muniCd", "muniType", "name", "countyName"}),
    "schlRef": frozenset({"code", "name"}),
    "propRef": frozenset({"propClass", "propClassDescrip"}),
    "saleConRef": frozenset(),
}

SORT_FIELDS = {
    "buyer": "buyerLastNm",
    "book": "book",
    "page": "page",
    "class-on-roll": "classOnRoll",
    "class-at-sale": "classOnSaleRoll",
    "sale-date": "saleDt",
    "sale-price": "salePrice",
    "school": "schoolCd",
    "seller": "sellerLastName",
    "street": "streetName",
    "swis": "swisCd",
    "tax-map": "taxMapId",
}

# ORPTS SWIS county prefixes are sequential administrative codes, not FIPS.
COUNTY_GEOID_BY_NAME = {
    "Albany": "36001",
    "Allegany": "36003",
    "Broome": "36007",
    "Cattaraugus": "36009",
    "Cayuga": "36011",
    "Chautauqua": "36013",
    "Chemung": "36015",
    "Chenango": "36017",
    "Clinton": "36019",
    "Columbia": "36021",
    "Cortland": "36023",
    "Delaware": "36025",
    "Dutchess": "36027",
    "Erie": "36029",
    "Essex": "36031",
    "Franklin": "36033",
    "Fulton": "36035",
    "Genesee": "36037",
    "Greene": "36039",
    "Hamilton": "36041",
    "Herkimer": "36043",
    "Jefferson": "36045",
    "Lewis": "36049",
    "Livingston": "36051",
    "Madison": "36053",
    "Monroe": "36055",
    "Montgomery": "36057",
    "Nassau": "36059",
    "Niagara": "36063",
    "Oneida": "36065",
    "Onondaga": "36067",
    "Ontario": "36069",
    "Orange": "36071",
    "Orleans": "36073",
    "Oswego": "36075",
    "Otsego": "36077",
    "Putnam": "36079",
    "Rensselaer": "36083",
    "Rockland": "36087",
    "St Lawrence": "36089",
    "St. Lawrence": "36089",
    "Saratoga": "36091",
    "Schenectady": "36093",
    "Schoharie": "36095",
    "Schuyler": "36097",
    "Seneca": "36099",
    "Steuben": "36101",
    "Suffolk": "36103",
    "Sullivan": "36105",
    "Tioga": "36107",
    "Tompkins": "36109",
    "Ulster": "36111",
    "Warren": "36113",
    "Washington": "36115",
    "Wayne": "36117",
    "Westchester": "36119",
    "Wyoming": "36121",
    "Yates": "36123",
}

SOURCE_WARNINGS = (
    (
        "SalesWeb is a rolling ten-year RP-5217 transfer index outside New "
        "York City; older transfers remain with the county recording office."
    ),
    (
        "ORPTS updates the source weekly, and recent transfers may arrive "
        "weeks or months after the sale date."
    ),
    (
        "Local assessors and county directors can submit corrections, so "
        "repeated observations from SalesWeb are one mutable source lineage."
    ),
    (
        "RP-5217 is not required for every real-property interest event; "
        "recorded instruments remain the complementary source for omitted "
        "transfer types and document images."
    ),
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="New York ORPTS SalesWeb",
    source_role="statewide_property_transfer_index_outside_new_york_city",
    base_url=LANDING_URL,
    dataset_id="ORPTS-SalesWeb",
    metadata={
        "authority": (
            "New York State Department of Taxation and Finance, "
            "Office of Real Property Tax Services"
        ),
        "application_url": APP_URL,
        "coverage": (
            "rolling ten years of New York real-property transfers outside "
            "New York City"
        ),
        "update_frequency": "weekly",
        "source_form": "RP-5217 Real Property Transfer Report",
        "sale_identity_field": "saleTranNmbr",
        "parcel_join_fields": ["swisCd", "printKey"],
        "api_actions": {
            "references": REFERENCE_ACTION,
            "search": SEARCH_ACTION,
            "detail": DETAIL_ACTION,
            "export": EXPORT_ACTION,
        },
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-ny",
    name="New York",
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS, "excludes": "New York City"},
)


@dataclass(frozen=True)
class SearchPage:
    """One source-native search page."""

    records: tuple[Mapping[str, Any], ...]
    full_length: int
    schema_fingerprint: str | None


@dataclass(frozen=True)
class CursorState:
    """Continuation state bound to one normalized SalesWeb query."""

    criteria_fingerprint: str
    offset: int
    full_length: int
    schema_fingerprint: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CURSOR_VERSION,
            "criteria_fingerprint": self.criteria_fingerprint,
            "offset": self.offset,
            "full_length": self.full_length,
            "schema_fingerprint": self.schema_fingerprint,
        }


class NYSalesWebError(PublicRecordsHTTPError):
    """Source-specific error with explicit result semantics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        category: str = "source_schema",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
        url: str = APP_URL,
    ) -> None:
        super().__init__(message, url=url, details=details)
        self.code = code
        self.result_status = status
        self.category = category
        self.retryable = retryable


class SalesWebClient:
    """Bounded HTTP client for the public Municipal Data Portal services."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if minimum_interval < 0:
            raise ValueError("minimum_interval must not be negative")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = RetryPolicy(max_attempts=retry_attempts)
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper
        self.request_count = 0
        self._references: Mapping[str, Any] | None = None

    def _post(
        self,
        action: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        url = f"{API_ROOT}/{action}"
        body = {"data": dict(payload)} if payload else {}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": APP_URL,
            "Referer": f"{APP_URL}/",
            "User-Agent": "Ithildin-OSINT/1.0 public-records research",
        }
        last_error: PublicRecordsHTTPError | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = TransportError(
                    f"SalesWeb transport failed: {exc}",
                    url=url,
                    details={"attempt": attempt},
                )
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise last_error from exc

            status_code = int(response.status_code)
            response_text = getattr(response, "text", "")
            if status_code == 429:
                last_error = RateLimitedHTTPError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            elif status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            elif status_code in {404, 410}:
                raise SourceChangedHTTPError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            elif status_code >= 400:
                last_error = HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=response_text,
                )
            else:
                try:
                    decoded = response.json()
                except (TypeError, ValueError) as exc:
                    raise SourceResponseError(
                        "SalesWeb returned a non-JSON response",
                        url=url,
                        details={"response_text": response_text[:500]},
                    ) from exc
                if not isinstance(decoded, Mapping):
                    raise SourceSchemaError(
                        "SalesWeb response root is not an object",
                        url=url,
                    )
                return dict(decoded)

            if last_error.retryable and attempt < self.retry_policy.max_attempts:
                retry_after = _retry_after_seconds(
                    getattr(response, "headers", {}).get("Retry-After")
                )
                self.sleeper(self.retry_policy.delay(attempt, retry_after))
                continue
            raise last_error
        assert last_error is not None
        raise last_error

    def fetch_references(self, *, refresh: bool = False) -> Mapping[str, Any]:
        if self._references is not None and not refresh:
            return self._references
        payload = self._post(REFERENCE_ACTION)
        data = _app_data(payload, action=REFERENCE_ACTION)
        _validate_reference_tables(data)
        self._references = data
        return data

    def search(self, request: Mapping[str, Any]) -> SearchPage:
        payload = self._post(SEARCH_ACTION, request)
        data = _app_data(payload, action=SEARCH_ACTION)
        service = data.get("oServiceResponse")
        if not isinstance(service, Mapping):
            raise SourceSchemaError(
                "SalesWeb search response lacks oServiceResponse",
                url=f"{API_ROOT}/{SEARCH_ACTION}",
            )
        status = service.get("status")
        if status != "SUCCESS":
            raise SourceResponseError(
                f"SalesWeb search returned service status {status!r}",
                url=f"{API_ROOT}/{SEARCH_ACTION}",
                details={"service_status": status},
            )
        records = service.get("salesWebList")
        full_length = service.get("fullLength")
        if not isinstance(records, list) or not all(
            isinstance(record, Mapping) for record in records
        ):
            raise SourceSchemaError(
                "SalesWeb search response has an invalid salesWebList",
                url=f"{API_ROOT}/{SEARCH_ACTION}",
            )
        if (
            isinstance(full_length, bool)
            or not isinstance(full_length, int)
            or full_length < 0
        ):
            raise SourceSchemaError(
                "SalesWeb search response has an invalid fullLength",
                url=f"{API_ROOT}/{SEARCH_ACTION}",
                details={"fullLength": full_length},
            )
        for record in records:
            _require_fields(
                record,
                SEARCH_REQUIRED_FIELDS,
                context="SalesWeb search row",
                url=f"{API_ROOT}/{SEARCH_ACTION}",
            )
        schema = _record_schema_fingerprint(records)
        return SearchPage(tuple(records), full_length, schema)

    def detail(
        self,
        sale_transaction_number: int,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        payload = self._post(
            DETAIL_ACTION,
            {"saleTranNmbr": sale_transaction_number},
        )
        data = _app_data(payload, action=DETAIL_ACTION)
        service = data.get("oServiceResponse")
        reference_response = data.get("aRefTblResponse")
        if not isinstance(service, Mapping):
            raise SourceSchemaError(
                "SalesWeb detail response lacks oServiceResponse",
                url=f"{API_ROOT}/{DETAIL_ACTION}",
            )
        service_data = service.get("data")
        row = (
            service_data.get("salesWebRow")
            if isinstance(service_data, Mapping)
            else None
        )
        if not isinstance(row, Mapping):
            raise SourceResponseError(
                "SalesWeb did not return a detail row for that transaction",
                url=f"{API_ROOT}/{DETAIL_ACTION}",
                details={"saleTranNmbr": sale_transaction_number},
            )
        _require_fields(
            row,
            DETAIL_REQUIRED_FIELDS,
            context="SalesWeb detail row",
            url=f"{API_ROOT}/{DETAIL_ACTION}",
        )
        refs = (
            reference_response.get("data")
            if isinstance(reference_response, Mapping)
            else None
        )
        if not isinstance(refs, Mapping):
            refs = self.fetch_references()
        else:
            _validate_reference_tables(refs)
        return dict(row), refs

    def download(self, request: Mapping[str, Any]) -> bytes:
        payload = self._post(EXPORT_ACTION, request)
        file_data = payload.get("fileData")
        values = file_data.get("data") if isinstance(file_data, Mapping) else None
        if not isinstance(values, list) or not all(
            isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 255
            for value in values
        ):
            raise SourceSchemaError(
                "SalesWeb export response lacks a valid byte buffer",
                url=f"{API_ROOT}/{EXPORT_ACTION}",
            )
        return bytes(values)


def _retry_after_seconds(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _app_data(payload: Mapping[str, Any], *, action: str) -> Mapping[str, Any]:
    if payload.get("status") != "success":
        raise SourceResponseError(
            f"SalesWeb {action} returned application status {payload.get('status')!r}",
            url=f"{API_ROOT}/{action}",
            details={"application_status": payload.get("status")},
        )
    app = payload.get("app")
    data = app.get("data") if isinstance(app, Mapping) else None
    if not isinstance(data, Mapping):
        raise SourceSchemaError(
            f"SalesWeb {action} response lacks app.data",
            url=f"{API_ROOT}/{action}",
        )
    return dict(data)


def _require_fields(
    record: Mapping[str, Any],
    required: frozenset[str],
    *,
    context: str,
    url: str,
) -> None:
    missing = sorted(required - set(record))
    if missing:
        raise SourceSchemaError(
            f"{context} is missing required fields",
            url=url,
            details={"missing_fields": missing},
        )


def _validate_reference_tables(data: Mapping[str, Any]) -> None:
    for table_name, required_fields in REFERENCE_REQUIRED_FIELDS.items():
        rows = data.get(table_name)
        if not isinstance(rows, list) or not all(
            isinstance(row, Mapping) for row in rows
        ):
            raise SourceSchemaError(
                f"SalesWeb reference response lacks valid {table_name}",
                url=f"{API_ROOT}/{REFERENCE_ACTION}",
            )
        for row in rows:
            _require_fields(
                row,
                required_fields,
                context=f"SalesWeb {table_name} row",
                url=f"{API_ROOT}/{REFERENCE_ACTION}",
            )


def _record_schema_fingerprint(
    records: Sequence[Mapping[str, Any]],
) -> str | None:
    if not records:
        return None
    return sha256_fingerprint(
        {
            "kind": "salesweb-observed-fields",
            "field_sets": sorted(
                {tuple(sorted(str(key) for key in record)) for record in records}
            ),
        }
    )


def _encode_cursor(state: CursorState) -> str:
    encoded = base64.urlsafe_b64encode(
        canonical_json(state.to_dict()).encode("utf-8")
    ).decode("ascii")
    return f"{CURSOR_PREFIX}{encoded.rstrip('=')}"


def _decode_cursor(value: str | None) -> CursorState | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise NYSalesWebError(
            "invalid_cursor",
            "cursor does not belong to the NY SalesWeb adapter",
        )
    token = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NYSalesWebError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from exc
    if not isinstance(decoded, Mapping) or decoded.get("version") != CURSOR_VERSION:
        raise NYSalesWebError(
            "invalid_cursor",
            "cursor version is missing or unsupported",
        )
    try:
        state = CursorState(
            criteria_fingerprint=str(decoded["criteria_fingerprint"]),
            offset=int(decoded["offset"]),
            full_length=int(decoded["full_length"]),
            schema_fingerprint=(
                str(decoded["schema_fingerprint"])
                if decoded.get("schema_fingerprint") is not None
                else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise NYSalesWebError(
            "invalid_cursor",
            "cursor fields are invalid",
        ) from exc
    if state.offset < 0 or state.full_length < 0:
        raise NYSalesWebError(
            "invalid_cursor",
            "cursor offsets must not be negative",
        )
    return state


def _name_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _parse_date(value: str, field_name: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD") from exc


def _source_date(value: Any) -> dict[str, Any]:
    raw = _clean(value)
    if raw is None:
        return {"raw": None, "iso": None}
    candidate = str(raw).removesuffix("[UTC]")
    try:
        iso = date.fromisoformat(candidate[:10]).isoformat()
    except ValueError:
        iso = None
    return {"raw": raw, "iso": iso}


def _integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decimal_number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _indicator(value: Any) -> dict[str, Any]:
    normalized = str(value).strip().upper() if value is not None else ""
    if normalized in {"1", "Y", "YES", "TRUE"}:
        boolean = True
    elif normalized in {"0", "N", "NO", "FALSE"}:
        boolean = False
    else:
        boolean = None
    return {"source_value": _clean(value), "boolean": boolean}


def _party(first: Any, last: Any, second_last: Any = None) -> dict[str, Any]:
    first_value = _clean(first)
    last_value = _clean(last)
    second_value = _clean(second_last)
    name_parts = [value for value in (last_value, first_value) if value]
    result: dict[str, Any] = {
        "name": ", ".join(str(value) for value in name_parts) or None,
        "first_name": first_value,
        "last_name": last_value,
    }
    if second_value is not None:
        result["second_last_name"] = second_value
    return result


def _reference_schema(data: Mapping[str, Any]) -> dict[str, Any]:
    schemas = {}
    for name in REFERENCE_REQUIRED_FIELDS:
        rows = data.get(name, [])
        schemas[name] = sorted(
            {key for row in rows if isinstance(row, Mapping) for key in row}
        )
    return schemas


class ReferenceIndex:
    """Resolve human-readable counties, municipalities, and schools."""

    def __init__(self, references: Mapping[str, Any]) -> None:
        _validate_reference_tables(references)
        self.references = references
        self.municipalities = [dict(row) for row in references["muniRef"]]
        self.schools = [dict(row) for row in references["schlRef"]]
        self.properties = {
            str(row["propClass"]): _clean(row.get("propClassDescrip"))
            for row in references["propRef"]
        }
        self.counties = [
            row
            for row in self.municipalities
            if _name_key(row.get("muniType")) == "county"
        ]
        self.muni_by_code = {str(row["muniCd"]): row for row in self.municipalities}
        self.school_by_code = {str(row["code"]): row for row in self.schools}

    def resolve_counties(self, values: Sequence[str]) -> list[str]:
        return [
            self._resolve_one(
                f"{value.strip()}0000"
                if re.fullmatch(r"\d{2}", value.strip())
                else value,
                self.counties,
                code_field="muniCd",
                name_field="name",
                kind="county",
            )
            for value in values
        ]

    def resolve_municipalities(
        self,
        values: Sequence[str],
        county_codes: Sequence[str],
    ) -> list[str]:
        rows = [
            row
            for row in self.municipalities
            if _name_key(row.get("muniType")) != "county"
        ]
        if county_codes:
            county_names = {
                str(self.muni_by_code[code].get("name"))
                for code in county_codes
                if code in self.muni_by_code
            }
            rows = [row for row in rows if str(row.get("countyName")) in county_names]
        return [
            self._resolve_one(
                value,
                rows,
                code_field="muniCd",
                name_field="name",
                kind="municipality",
            )
            for value in values
        ]

    def resolve_schools(self, values: Sequence[str]) -> list[str]:
        return [
            self._resolve_one(
                value,
                self.schools,
                code_field="code",
                name_field="name",
                kind="school district",
            )
            for value in values
        ]

    @staticmethod
    def _resolve_one(
        value: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        code_field: str,
        name_field: str,
        kind: str,
    ) -> str:
        requested = value.strip()
        code_matches = [
            row for row in rows if str(row.get(code_field, "")) == requested
        ]
        matches = code_matches or [
            row
            for row in rows
            if _name_key(row.get(name_field)) == _name_key(requested)
        ]
        if len(matches) == 1:
            return str(matches[0][code_field])
        choices = [
            {
                "code": row.get(code_field),
                "name": row.get(name_field),
                "type": row.get("muniType"),
                "county": row.get("countyName"),
            }
            for row in matches[:20]
        ]
        if not matches:
            raise NYSalesWebError(
                "reference_not_found",
                f"SalesWeb has no {kind} matching {requested!r}",
                details={"kind": kind, "value": requested},
            )
        raise NYSalesWebError(
            "ambiguous_reference",
            f"SalesWeb has multiple {kind} records matching {requested!r}; "
            "use the source code",
            details={"kind": kind, "value": requested, "choices": choices},
        )

    def municipality_context(self, swis_code: Any) -> dict[str, Any]:
        code = str(swis_code or "")
        row = self.muni_by_code.get(code, {})
        county_name = _clean(row.get("countyName"))
        if county_name is None and len(code) >= 2:
            county_row = self.muni_by_code.get(f"{code[:2]}0000", {})
            county_name = _clean(county_row.get("name"))
        county_geoid = COUNTY_GEOID_BY_NAME.get(str(county_name))
        return {
            "county_name": county_name,
            "county_geoid": county_geoid,
            "municipality": _clean(row.get("name")),
            "municipality_type": _clean(row.get("muniType")),
        }


def _flatten(values: Sequence[str] | None) -> list[str]:
    flattened: list[str] = []
    for value in values or ():
        flattened.extend(part.strip() for part in value.split(",") if part.strip())
    return flattened


def _criteria(args: argparse.Namespace) -> list[dict[str, Any]]:
    criteria: list[dict[str, Any]] = []
    if args.arms_length:
        criteria.append(
            {
                "fieldName": "armsLength",
                "value": {"yes": "Y", "no": "N", "other": "X"}[args.arms_length],
            }
        )
    if args.cod_usable:
        criteria.append(
            {
                "fieldName": "codUsable",
                "value": "Y" if args.cod_usable == "yes" else "N",
            }
        )
    if args.rar_usable:
        criteria.append(
            {
                "fieldName": "rarUsable",
                "value": {
                    "yes": "Y",
                    "no": "N",
                    "not-applicable": "NA",
                }[args.rar_usable],
            }
        )
    if args.address_number or args.street:
        item: dict[str, Any] = {"fieldName": "streetAdr"}
        if args.address_number:
            item["streetNmbr"] = args.address_number
        if args.street:
            item["streetName"] = args.street
        criteria.append(item)
    if args.book or args.page:
        item = {"fieldName": "bookPage"}
        if args.book:
            item["book"] = args.book
        if args.page:
            item["page"] = args.page
        criteria.append(item)
    if args.buyer:
        criteria.append({"fieldName": "buyer", "value": args.buyer})
    if args.seller:
        criteria.append({"fieldName": "seller", "value": args.seller})
    if args.price_min is not None or args.price_max is not None:
        criteria.append(
            {
                "fieldName": "salePriceRange",
                "rangeFrom": str(args.price_min or 0),
                "rangeTo": str(
                    args.price_max if args.price_max is not None else 999_999_999
                ),
            }
        )
    if args.sale_from or args.sale_to:
        sale_to = (
            _parse_date(args.sale_to, "sale-to")
            if args.sale_to
            else date.today().isoformat()
        )
        if args.sale_from:
            sale_from = _parse_date(args.sale_from, "sale-from")
        else:
            end = date.fromisoformat(sale_to)
            try:
                sale_from = end.replace(year=end.year - 10).isoformat()
            except ValueError:
                sale_from = end.replace(year=end.year - 10, day=28).isoformat()
        if sale_from > sale_to:
            raise ValueError("sale-from must not be later than sale-to")
        criteria.append(
            {
                "fieldName": "saleDateRange",
                "saleFromDt": sale_from,
                "saleToDt": sale_to,
            }
        )
    if args.tax_map:
        criteria.append(
            {
                "fieldName": "taxMapId",
                "operator": (
                    "INCLUDES" if args.tax_map_mode == "includes" else "BEGIN_WITH"
                ),
                "value": args.tax_map,
            }
        )
    property_classes = _flatten(args.property_class)
    if property_classes:
        criteria.append(
            {
                "fieldName": "propertyClass",
                "propClassOnRoll": "Y" if args.class_on_roll else "N",
                "propClassAtSale": "Y" if args.class_at_sale else "N",
                "values": property_classes,
            }
        )
    return criteria


def _sorts(args: argparse.Namespace) -> list[dict[str, str]]:
    values = _flatten(args.sort)
    if not values:
        values = [
            "sale-date:descending",
            "swis:ascending",
            "book:ascending",
            "page:ascending",
            "tax-map:ascending",
        ]
    output = []
    for value in values:
        field, separator, direction = value.partition(":")
        if field not in SORT_FIELDS:
            raise ValueError(
                f"unknown sort field {field!r}; choose from "
                f"{', '.join(sorted(SORT_FIELDS))}"
            )
        direction = direction if separator else "ascending"
        if direction not in {"ascending", "descending"}:
            raise ValueError("sort direction must be ascending or descending")
        output.append({"fieldName": SORT_FIELDS[field], "value": direction})
    return output


def build_search_request(
    args: argparse.Namespace,
    references: Mapping[str, Any],
    *,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    """Translate CLI criteria to the request shape used by the official SPA."""
    index = ReferenceIndex(references)
    county_codes = index.resolve_counties(_flatten(args.county))
    municipality_codes = index.resolve_municipalities(
        _flatten(args.municipality),
        county_codes,
    )
    school_codes = index.resolve_schools(_flatten(args.school))
    return {
        "counties": county_codes,
        "munis": municipality_codes,
        "schools": school_codes,
        "criterias": _criteria(args),
        "sortBy": _sorts(args),
        "offset": offset,
        "limit": limit,
    }


def _criteria_payload(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: request[key]
        for key in ("counties", "munis", "schools", "criterias", "sortBy")
    }


def _normalize_record(
    row: Mapping[str, Any],
    references: Mapping[str, Any],
    *,
    detail: bool,
    include_raw: bool,
    source_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    index = ReferenceIndex(references)
    sale_transaction_number = _integer(row.get("saleTranNmbr"))
    if sale_transaction_number is None:
        raise SourceSchemaError(
            "SalesWeb row has an invalid saleTranNmbr",
            url=f"{API_ROOT}/{DETAIL_ACTION if detail else SEARCH_ACTION}",
        )
    swis = str(_clean(row.get("swisCd")) or "")
    print_key = str(_clean(row.get("printKey")) or "")
    context = index.municipality_context(swis)
    county_geoid = context["county_geoid"] or STATE_FIPS
    swis_print_key_id = f"{swis}{print_key}" if swis and print_key else None
    parcel_native_id = swis_print_key_id or str(_clean(row.get("parcelId")) or "")
    school_code = _clean(row.get("schoolCd"))
    school_row = index.school_by_code.get(str(school_code), {})
    class_on_roll = str(
        _clean(row.get("prpClsLstRollCd")) or _clean(row.get("prpClsLstRoll1Cd")) or ""
    )
    class_at_sale = str(
        _clean(row.get("prpClsAtSaleCd")) or _clean(row.get("prpClsAtSale1Cd")) or ""
    )
    seller = _party(row.get("sellerFirstName"), row.get("sellerLastName"))
    buyer = _party(
        row.get("buyerFirstName"),
        row.get("buyerLastName"),
        row.get("buyerLastName2"),
    )
    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            county_geoid,
            "property_sale",
            str(sale_transaction_number),
        ),
        "source_id": SOURCE_ID,
        "record_type": "property_sale",
        "native_record_id": str(sale_transaction_number),
        "sale_record_id": str(sale_transaction_number),
        "record_identity": {
            "scope": "ORPTS SalesWeb source-native transaction",
            "source_native_key": "saleTranNmbr",
            "source_native_value": sale_transaction_number,
        },
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": context["county_name"],
            "county_geoid": context["county_geoid"],
            "municipality": context["municipality"],
            "municipality_type": context["municipality_type"],
            "swis_code": swis or None,
            "school_code": school_code,
            "school_district": _clean(school_row.get("name")),
        },
        "transaction": {
            "sale_date": _source_date(row.get("saleDt")),
            "sale_price_dollars": _decimal_number(row.get("salePriceAmt")),
            "deed": {
                "book": _clean(row.get("bookNmbr")),
                "page": _clean(row.get("pageNmbr")),
                "document_number": _clean(row.get("docNmbr")),
                "deed_date": _source_date(row.get("deedDt")),
            },
            "contract_date": _source_date(row.get("contractDt")),
            "personal_property_dollars": _decimal_number(row.get("personalPropAmt")),
            "report_type_code": _clean(row.get("rptTypeCd")),
            "review": {
                "assessor_reviewed": _indicator(row.get("assrRevdInd")),
                "roll_matched": _indicator(row.get("rollmatchInd")),
            },
        },
        "parties": {
            "seller": seller,
            "buyer": buyer,
        },
        "property": {
            "address": {
                "street_number": _clean(row.get("stNmbr")),
                "street": _clean(row.get("stName")),
                "postal_code": _clean(row.get("zipCd")),
                "state": STATE_CODE,
            },
            "parcel_identifiers": {
                "salesweb_parcel_id": _clean(row.get("parcelId")),
                "swis": swis or None,
                "print_key": print_key or None,
                "village_print_key": _clean(row.get("vlgPrintKey")),
                "swis_print_key_id": swis_print_key_id,
                "second_swis": _clean(row.get("secondSwisCd")),
                "sbl_text": _clean(row.get("sblText")),
            },
            "parcel_join": {
                "canonical_ref": (
                    canonical_property_ref(
                        SOURCE_ID,
                        county_geoid,
                        "parcel_join",
                        parcel_native_id,
                    )
                    if parcel_native_id
                    else None
                ),
                "exact_join_fields": (
                    {
                        "SWIS": swis,
                        "PRINT_KEY": print_key,
                        "SWIS_PRINT_KEY_ID": swis_print_key_id,
                    }
                    if swis_print_key_id
                    else None
                ),
                "statewide_parcel_query": (
                    {
                        "tool": "tools/query_ny_statewide_parcels.py",
                        "arguments": [
                            "parcel",
                            swis_print_key_id,
                            "--id-type",
                            "swis-print-key",
                        ],
                    }
                    if swis_print_key_id
                    else None
                ),
            },
            "roll_year": _integer(row.get("rollYr")),
            "property_class": {
                "on_last_roll": {
                    "code": class_on_roll or None,
                    "description": index.properties.get(class_on_roll),
                },
                "at_sale": {
                    "code": class_at_sale or None,
                    "description": index.properties.get(class_at_sale),
                },
            },
            "assessed_value_dollars": {
                "total": _decimal_number(row.get("totalAvAmt")),
                "village_total": _decimal_number(row.get("vlgTotalAvAmt")),
            },
        },
        "source_snapshot": dict(source_snapshot),
        "source_record": {
            "application_url": APP_URL,
            "endpoint": f"{API_ROOT}/{DETAIL_ACTION if detail else SEARCH_ACTION}",
            "field_names": sorted(row),
            "field_schema_fingerprint": sha256_fingerprint(sorted(row)),
        },
    }

    if detail:
        result["parties"]["buyer"]["mailing_address"] = {
            "street_number": _clean(row.get("buyerStNmbr")),
            "street": _clean(row.get("buyerStName")),
            "city": _clean(row.get("buyerCityName")),
            "state": _clean(row.get("buyerState")),
            "postal_code": _clean(row.get("buyerZip")),
        }
        result["related_professionals"] = {
            "attorney": {
                **_party(row.get("attyFirstName"), row.get("attyLastName")),
                "phone": _clean(row.get("attyPhoneNmbr")),
            }
        }
        result["transaction"].update(
            {
                "usability": {
                    "arms_length": _indicator(row.get("armsLngthInd")),
                    "cod_usable": _indicator(row.get("codUsableInd")),
                    "rar_usable": _indicator(row.get("rarUsableInd")),
                    "village_rar_usable": _indicator(row.get("vlgRarUsableInd")),
                },
                "condition_flags": {
                    key.removeprefix("cond").removesuffix("Ind"): _indicator(
                        row.get(key)
                    )
                    for key in sorted(row)
                    if key.startswith("cond") and key.endswith("Ind")
                },
                "condition_memo": _clean(row.get("condMemoDesc")),
            }
        )
        result["property"].update(
            {
                "sale_acres": _decimal_number(row.get("ttlSaleAcresNmbr")),
                "number_of_parcels": _integer(row.get("parcelCnt")),
                "dimensions": {
                    "front": _decimal_number(row.get("frontNmbr")),
                    "depth": _decimal_number(row.get("depthNmbr")),
                },
                "grid_coordinates": {
                    "east": _decimal_number(row.get("gridEastNmbr")),
                    "north": _decimal_number(row.get("gridNorthNmbr")),
                },
                "attributes": {
                    "part_of_parcel": _indicator(row.get("prtlCnstrInd")),
                    "condominium": _indicator(row.get("condoInd")),
                    "new_construction": _indicator(row.get("newCnstrInd")),
                    "ownership_code": _clean(row.get("ownershipCd")),
                },
            }
        )
        result["source_processing"] = {
            "form_received": _indicator(row.get("frmRcvdInd")),
            "rps_updated": _indicator(row.get("rpsUpdateInd")),
            "paper_corrected": _indicator(row.get("corUpdateInd")),
            "other_update": _indicator(row.get("otherUpdtInd")),
            "load_date": _source_date(row.get("loadDt")),
            "last_form_date": _source_date(row.get("lastFmDt")),
            "version_timestamp": _clean(row.get("versionTs")),
            "control_number": _clean(row.get("cntrlNmbr")),
        }
    if include_raw:
        result["raw_source_record"] = dict(row)
    return result


def _alternative_routes() -> list[dict[str, Any]]:
    return [
        {
            "route_id": "nyc-acris-recorded-documents",
            "name": "NYC ACRIS",
            "url": ACRIS_URL,
            "search_url": ACRIS_SEARCH_URL,
            "authority": "New York City Department of Finance",
            "coverage": (
                "recorded deeds and other property documents for Manhattan, "
                "Bronx, Brooklyn, and Queens from 1966 to present"
            ),
            "record_role": "official recorded-instrument index and document images",
            "join_keys": ["borough", "block", "lot", "party", "document_id"],
        },
        {
            "route_id": "richmond-county-land-documents",
            "name": "Richmond County Clerk Land Documents Search",
            "url": RICHMOND_CLERK_URL,
            "authority": "Office of the Richmond County Clerk",
            "coverage": "Staten Island recorded land documents",
            "record_role": (
                "official Staten Island deed and land-document index and images"
            ),
            "search_modes": [
                "document number",
                "party or company",
                "date range",
                "block and lot",
                "book and page",
            ],
            "join_keys": ["block", "lot", "book", "page", "party"],
        },
        {
            "route_id": "county-clerk-recorded-instruments",
            "name": "County recording office",
            "url": LANDING_URL,
            "authority": "County clerk for the county where the deed was filed",
            "coverage": "older transfers and source recorded instruments",
            "record_role": (
                "deeds, document images, and transfers older than the "
                "SalesWeb rolling window"
            ),
            "routing": (
                "Resolve the county from SalesWeb SWIS or the Municipal Data "
                "Portal, then use that county clerk's land-record system."
            ),
            "join_keys": ["county", "book", "page", "party", "tax_map_id"],
        },
        {
            "route_id": "ny-statewide-parcel-map",
            "name": "New York Statewide Parcel Map Program",
            "url": STATEWIDE_PARCELS_URL,
            "authority": "New York State ITS Geospatial Services",
            "coverage": (
                "all-county parcel centroids and assessment attributes, "
                "participating-county public parcel polygons"
            ),
            "record_role": (
                "current parcel, assessment, ownership, and geometry context"
            ),
            "adapter": "tools/query_ny_statewide_parcels.py",
            "exact_join": {
                "SalesWeb": ["swisCd", "printKey"],
                "parcel_map": ["SWIS", "PRINT_KEY", "SWIS_PRINT_KEY_ID"],
            },
        },
        {
            "route_id": "nyc-property-information-portal",
            "name": "NYC Property Information Portal",
            "url": NYC_PROPERTY_PORTAL_URL,
            "authority": "New York City Department of Finance",
            "coverage": "New York City parcels, including Staten Island",
            "record_role": (
                "parcel, owner, assessment, and recent recorded-document context"
            ),
            "join_keys": ["borough", "block", "lot", "address"],
        },
    ]


def alternative_routes() -> list[dict[str, Any]]:
    """Return official parcel, recorder, and NYC substitute routes."""

    return _alternative_routes()


def _reference_record(references: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "record_type": "source_reference_tables",
        "counts": {name: len(references[name]) for name in REFERENCE_REQUIRED_FIELDS},
        "schema": _reference_schema(references),
        "schema_fingerprint": sha256_fingerprint(_reference_schema(references)),
        "county_count": sum(
            1
            for row in references["muniRef"]
            if _name_key(row.get("muniType")) == "county"
        ),
        "application_url": APP_URL,
        "endpoint": f"{API_ROOT}/{REFERENCE_ACTION}",
    }


def _search(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    references = client.fetch_references()
    cursor = _decode_cursor(args.cursor)
    page_size = args.page_size
    first_request = build_search_request(
        args,
        references,
        offset=cursor.offset if cursor else 0,
        limit=page_size,
    )
    criteria_fingerprint = sha256_fingerprint(_criteria_payload(first_request))
    if cursor and cursor.criteria_fingerprint != criteria_fingerprint:
        raise NYSalesWebError(
            "stale_cursor",
            "query criteria changed since the cursor was issued",
            details={
                "cursor_criteria_fingerprint": cursor.criteria_fingerprint,
                "current_criteria_fingerprint": criteria_fingerprint,
            },
        )

    offset = cursor.offset if cursor else 0
    requested_limit = None if args.all_records else args.limit
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    pages_fetched = 0
    source_full_length: int | None = None
    schema_fingerprint = cursor.schema_fingerprint if cursor else None

    while requested_limit is None or len(records) < requested_limit:
        request_limit = page_size
        if requested_limit is not None:
            request_limit = min(page_size, requested_limit - len(records))
        request = {
            **_criteria_payload(first_request),
            "offset": offset,
            "limit": request_limit,
        }
        page = client.search(request)
        pages_fetched += 1
        if source_full_length is None:
            source_full_length = page.full_length
            if cursor and cursor.full_length != source_full_length:
                raise NYSalesWebError(
                    "stale_cursor",
                    "SalesWeb result count changed since the cursor was issued",
                    details={
                        "cursor_full_length": cursor.full_length,
                        "current_full_length": source_full_length,
                    },
                )
        elif page.full_length != source_full_length:
            raise NYSalesWebError(
                "source_changed_during_pagination",
                "SalesWeb result count changed during pagination",
                details={
                    "initial_full_length": source_full_length,
                    "current_full_length": page.full_length,
                },
            )
        if page.schema_fingerprint is not None:
            if (
                schema_fingerprint is not None
                and page.schema_fingerprint != schema_fingerprint
            ):
                raise SourceSchemaError(
                    "SalesWeb search row fields changed during pagination",
                    url=f"{API_ROOT}/{SEARCH_ACTION}",
                    details={
                        "initial_schema_fingerprint": schema_fingerprint,
                        "current_schema_fingerprint": page.schema_fingerprint,
                    },
                )
            schema_fingerprint = page.schema_fingerprint
        if not page.records:
            if offset < page.full_length:
                raise PaginationError(
                    "SalesWeb returned an empty page before fullLength",
                    url=f"{API_ROOT}/{SEARCH_ACTION}",
                    details={
                        "offset": offset,
                        "full_length": page.full_length,
                    },
                )
            break
        source_snapshot = {
            "reported_total_matches": page.full_length,
            "page_offset": offset,
            "pages_fetched": pages_fetched,
            "schema_fingerprint": schema_fingerprint,
            "reference_schema_fingerprint": sha256_fingerprint(
                _reference_schema(references)
            ),
        }
        for row in page.records:
            native_id = str(row["saleTranNmbr"])
            if native_id in seen_ids:
                raise PaginationError(
                    "SalesWeb pagination repeated a sale transaction",
                    url=f"{API_ROOT}/{SEARCH_ACTION}",
                    details={"saleTranNmbr": native_id, "offset": offset},
                )
            seen_ids.add(native_id)
            records.append(
                _normalize_record(
                    row,
                    references,
                    detail=False,
                    include_raw=args.include_raw,
                    source_snapshot=source_snapshot,
                )
            )
        offset += len(page.records)
        if offset >= page.full_length:
            break

    full_length = source_full_length or 0
    next_cursor = None
    if offset < full_length:
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria_fingerprint,
                offset=offset,
                full_length=full_length,
                schema_fingerprint=schema_fingerprint,
            )
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _detail(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    row, references = client.detail(args.sale_transaction_number)
    record = _normalize_record(
        row,
        references,
        detail=True,
        include_raw=args.include_raw,
        source_snapshot={
            "schema_fingerprint": sha256_fingerprint(sorted(row)),
            "reference_schema_fingerprint": sha256_fingerprint(
                _reference_schema(references)
            ),
        },
    )
    return PublicRecordsResult.success(
        query,
        [record],
        warnings=SOURCE_WARNINGS,
    )


def _export(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    references = client.fetch_references()
    probe_request = build_search_request(
        args,
        references,
        offset=0,
        limit=1,
    )
    page = client.search(probe_request)
    if page.full_length == 0:
        return PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    export_count = (
        min(args.limit, page.full_length)
        if args.limit is not None
        else page.full_length
    )
    export_request = {
        **_criteria_payload(probe_request),
        "offset": 0,
        "limit": export_count,
        "orderInd": 1,
    }
    content = client.download(export_request)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceSchemaError(
            "SalesWeb export is not UTF-8 CSV",
            url=f"{API_ROOT}/{EXPORT_ACTION}",
        ) from exc
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise SourceSchemaError(
            "SalesWeb export is empty",
            url=f"{API_ROOT}/{EXPORT_ACTION}",
        )
    headers = rows[0]
    required_headers = {"swis_cd", "print_key", "seller_last_nam", "sale_dte"}
    missing = sorted(required_headers - set(headers))
    if missing:
        raise SourceSchemaError(
            "SalesWeb export header changed",
            url=f"{API_ROOT}/{EXPORT_ACTION}",
            details={"missing_headers": missing, "headers": headers},
        )
    destination = Path(args.csv_output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    record_count = max(0, len(rows) - 1)
    record = {
        "source_id": SOURCE_ID,
        "record_type": "salesweb_csv_export",
        "artifact_path": str(destination),
        "artifact_sha256": hashlib.sha256(content).hexdigest(),
        "artifact_size_bytes": len(content),
        "reported_total_matches": page.full_length,
        "requested_export_rows": export_count,
        "csv_record_count": record_count,
        "csv_headers": headers,
        "csv_schema_fingerprint": sha256_fingerprint(headers),
        "sale_identity_note": (
            "The CSV omits saleTranNmbr; use the JSON search/detail service "
            "when a source-native sale identity is required."
        ),
        "query_request": export_request,
        "endpoint": f"{API_ROOT}/{EXPORT_ACTION}",
    }
    warnings = (
        *SOURCE_WARNINGS,
        (
            "The official CSV export does not contain saleTranNmbr. It is "
            "retained as a raw source artifact, while normalized sale records "
            "come from the JSON search/detail service."
        ),
    )
    return PublicRecordsResult.success(
        query,
        [record],
        raw_artifact_refs=[str(destination)],
        warnings=warnings,
    )


def _probe(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    references = client.fetch_references(refresh=True)
    probe_args = argparse.Namespace(
        county=[],
        municipality=["012000"],
        school=[],
        arms_length=None,
        cod_usable=None,
        rar_usable=None,
        address_number=None,
        street=None,
        book=None,
        page=None,
        buyer=None,
        seller=None,
        price_min=None,
        price_max=None,
        sale_from=None,
        sale_to=None,
        tax_map=None,
        tax_map_mode="includes",
        property_class=[],
        class_on_roll=True,
        class_at_sale=True,
        sort=["sale-date:descending"],
    )
    request = build_search_request(
        probe_args,
        references,
        offset=0,
        limit=1,
    )
    page = client.search(request)
    detail_schema_fingerprint = None
    native_identity_present = False
    parcel_join_present = False
    native_sale_transaction_number = None
    if page.records:
        native_sale_transaction_number = int(
            page.records[0]["saleTranNmbr"]
        )
        row, detail_refs = client.detail(native_sale_transaction_number)
        detail_schema_fingerprint = sha256_fingerprint(sorted(row))
        native_identity_present = row.get("saleTranNmbr") is not None
        parcel_join_present = bool(row.get("swisCd") and row.get("printKey"))
        _validate_reference_tables(detail_refs)
    record = {
        "source_id": SOURCE_ID,
        "record_type": "source_probe",
        "application_url": APP_URL,
        "api_root": API_ROOT,
        "reference_tables": _reference_record(references),
        "bounded_search": {
            "municipality_code": "012000",
            "reported_total_matches": page.full_length,
            "returned_rows": len(page.records),
            "schema_fingerprint": page.schema_fingerprint,
        },
        "detail": {
            "checked": bool(page.records),
            "native_sale_transaction_number": (
                native_sale_transaction_number
            ),
            "schema_fingerprint": detail_schema_fingerprint,
            "sale_transaction_identity_present": native_identity_present,
            "swis_print_key_join_present": parcel_join_present,
        },
        "requests_made": getattr(client, "request_count", None),
    }
    return PublicRecordsResult.success(
        query,
        [record],
        warnings=SOURCE_WARNINGS,
    )


def _raw_query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    excluded = {
        "command",
        "output",
        "json_out",
        "timeout",
        "minimum_interval",
        "retry_attempts",
        "include_raw",
        "cursor",
        "page_size",
        "all_records",
        "csv_output",
    }
    return {
        key: value
        for key, value in vars(args).items()
        if key not in excluded and value not in (None, [], False)
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    requested_limit = getattr(args, "limit", None)
    if getattr(args, "all_records", False):
        requested_limit = None
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_raw_query_parameters(args),
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
            metadata={
                "sale_identity": "saleTranNmbr",
                "parcel_join": "swisCd + printKey -> SWIS_PRINT_KEY_ID",
            },
        ),
    )


def _client_from_args(args: argparse.Namespace) -> SalesWebClient:
    return SalesWebClient(
        timeout=getattr(args, "timeout", DEFAULT_TIMEOUT),
        minimum_interval=getattr(
            args,
            "minimum_interval",
            DEFAULT_MINIMUM_INTERVAL,
        ),
        retry_attempts=getattr(args, "retry_attempts", 3),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
) -> PublicRecordsResult:
    query = build_query(args)
    selected_client = client
    try:
        if args.command in {"alternatives", "routes"}:
            result = PublicRecordsResult.success(
                query,
                _alternative_routes(),
                warnings=SOURCE_WARNINGS,
            )
        else:
            selected_client = selected_client or _client_from_args(args)
            if args.command == "search":
                result = _search(args, selected_client, query)
            elif args.command == "detail":
                result = _detail(args, selected_client, query)
            elif args.command == "export":
                result = _export(args, selected_client, query)
            elif args.command == "references":
                references = selected_client.fetch_references(refresh=True)
                result = PublicRecordsResult.success(
                    query,
                    [_reference_record(references)],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                result = _probe(args, selected_client, query)
            else:
                raise ValueError(f"unsupported operation {args.command!r}")
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError, OSError) as error:
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

    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=_positive_int, default=3)
    add_output_args(parser)


def _add_criteria_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--county",
        action="append",
        default=[],
        help="County name, two-digit SWIS prefix, or six-digit county code; repeatable",
    )
    parser.add_argument(
        "--municipality",
        action="append",
        default=[],
        help="Municipality name or six-digit SWIS code; repeatable",
    )
    parser.add_argument(
        "--school",
        action="append",
        default=[],
        help="School district name or six-digit ORPTS code; repeatable",
    )
    parser.add_argument("--buyer", help="Buyer last name includes")
    parser.add_argument("--seller", help="Seller last name includes")
    parser.add_argument("--address-number")
    parser.add_argument("--street")
    parser.add_argument("--book")
    parser.add_argument("--page")
    parser.add_argument("--tax-map")
    parser.add_argument(
        "--tax-map-mode",
        choices=("includes", "begins"),
        default="includes",
    )
    parser.add_argument("--sale-from")
    parser.add_argument("--sale-to")
    parser.add_argument("--price-min", type=_nonnegative_int)
    parser.add_argument("--price-max", type=_nonnegative_int)
    parser.add_argument(
        "--arms-length",
        choices=("yes", "no", "other"),
    )
    parser.add_argument("--cod-usable", choices=("yes", "no"))
    parser.add_argument(
        "--rar-usable",
        choices=("yes", "no", "not-applicable"),
    )
    parser.add_argument(
        "--property-class",
        action="append",
        default=[],
        help="ORPTS property class code; repeatable or comma-separated",
    )
    class_group = parser.add_argument_group("property class matching")
    class_group.add_argument(
        "--no-class-on-roll",
        action="store_false",
        dest="class_on_roll",
        default=True,
    )
    class_group.add_argument(
        "--no-class-at-sale",
        action="store_false",
        dest="class_at_sale",
        default=True,
    )
    parser.add_argument(
        "--sort",
        action="append",
        default=[],
        metavar="FIELD[:DIRECTION]",
        help=(
            "Repeatable sort; fields include sale-date, sale-price, buyer, "
            "seller, book, page, tax-map, street, swis, school"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search ORPTS real-property transfers",
    )
    _add_criteria_args(search)
    limit_group = search.add_mutually_exclusive_group()
    limit_group.add_argument("--limit", type=_positive_int, default=DEFAULT_LIMIT)
    limit_group.add_argument(
        "--all",
        action="store_true",
        dest="all_records",
        help="Retrieve all native matches",
    )
    search.add_argument("--page-size", type=_positive_int, default=DEFAULT_PAGE_SIZE)
    search.add_argument("--cursor")
    search.add_argument("--include-raw", action="store_true")
    _add_network_args(search)

    detail = subparsers.add_parser(
        "detail",
        help="Fetch one sale by its source-native saleTranNmbr",
    )
    detail.add_argument("sale_transaction_number", type=_positive_int)
    detail.add_argument("--include-raw", action="store_true")
    _add_network_args(detail)

    export = subparsers.add_parser(
        "export",
        help="Save the official CSV export for a SalesWeb search",
    )
    _add_criteria_args(export)
    export.add_argument("--limit", type=_positive_int)
    export.add_argument("--csv-output", required=True)
    _add_network_args(export)

    references = subparsers.add_parser(
        "references",
        help="Inspect live municipality, school, class, and condition references",
    )
    _add_network_args(references)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded reference, search, and detail health check",
    )
    _add_network_args(probe)

    for command in ("alternatives", "routes"):
        routes = subparsers.add_parser(
            command,
            help="List official complementary and fallback property-record routes",
        )
        add_output_args(routes)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"New York ORPTS SalesWeb {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"New York ORPTS SalesWeb {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command in {"alternatives", "routes"}:
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "search":
            transaction = record["transaction"]
            print(
                f"  {record['sale_record_id']} | "
                f"{transaction['sale_date']['iso']} | "
                f"{transaction['sale_price_dollars']} | "
                f"{record['property']['address']['street_number'] or ''} "
                f"{record['property']['address']['street'] or ''}"
            )
        elif args.command == "detail":
            print(f"  saleTranNmbr {record['sale_record_id']}")
        elif args.command == "export":
            print(
                f"  {record['csv_record_count']} CSV rows | {record['artifact_path']}"
            )
        elif args.command == "references":
            print(f"  {record['counts']}")
        elif args.command == "probe":
            print(
                "  references/search/detail verified | "
                f"{record['requests_made']} requests"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "timeout", DEFAULT_TIMEOUT) <= 0:
        parser.error("timeout must be positive")
    if getattr(args, "minimum_interval", DEFAULT_MINIMUM_INTERVAL) < 0:
        parser.error("minimum-interval must not be negative")
    if hasattr(args, "price_min") and hasattr(args, "price_max"):
        if (
            args.price_min is not None
            and args.price_max is not None
            and args.price_min > args.price_max
        ):
            parser.error("price-min must not exceed price-max")
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS} else 1


if __name__ == "__main__":
    raise SystemExit(main())
