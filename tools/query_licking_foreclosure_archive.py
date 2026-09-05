#!/usr/bin/env python3
"""Query the official Licking County Sheriff foreclosure archive.

The archive is distinct from the county's RealAuction tenant. Its native
identity is the court case number, and its county-maintained records add terms,
sale type, deed-as, purchaser contact/address, and purchase price fields.

The official API returns a complete JSON array for a selected archive year.
Omitting ``--limit`` therefore returns the complete selected and filtered
result set. An explicit limit is applied after full enumeration and returns a
query- and ordered-case-membership-bound cursor. Mutable record fields are
refreshed when a continuation is used.

Examples:
    .venv/bin/python tools/query_licking_foreclosure_archive.py years --json
    .venv/bin/python tools/query_licking_foreclosure_archive.py year \
        --year 2026 --output /tmp/licking-foreclosures-2026.json
    .venv/bin/python tools/query_licking_foreclosure_archive.py case \
        --case-number 25CV01926 --json
    .venv/bin/python tools/query_licking_foreclosure_archive.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

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
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-oh-licking-sheriff-foreclosure-archive"
SOURCE_NAME = "Licking County Sheriff Foreclosure Archive"
BASE_URL = "https://apps.lickingcounty.gov/sheriff/foreclosures"
API_BASE_URL = f"{BASE_URL}/api"
YEARS_URL = f"{API_BASE_URL}/saleyears/"
FORECLOSURES_URL = f"{API_BASE_URL}/foreclosures/"
DETAIL_URL_BASE = f"{API_BASE_URL}/foreclosures"
OFFICIAL_INFO_URL = f"{BASE_URL}/"
EXPECTED_HOST = "apps.lickingcounty.gov"
COUNTY_GEOID = "39089"
COUNTY_NAME = "Licking County, Ohio"
STATE_CODE = "OH"
OBSERVED_AT = "2026-07-30"
PROBE_YEAR = 2026
PROBE_CASE_NUMBER = "25CV01926"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_RETRIES = 2
CURSOR_PREFIX = "licking-foreclosure-archive:v1:"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

EXPECTED_FIELDS = (
    "SaleDate",
    "CaseNumber",
    "Address",
    "City",
    "Zip",
    "AdvertiseDate",
    "AppraisalValue",
    "Terms",
    "SaleType",
    "RequiredDepositAmmount",
    "Status",
    "Parcels",
    "DeedAs",
    "PurchaserName",
    "PurchaserAddress",
    "PurchasePrice",
)
SCHEMA_FINGERPRINT = hashlib.sha256(
    canonical_json(
        {
            "source_id": SOURCE_ID,
            "fields": EXPECTED_FIELDS,
            "native_identity": "case_number",
        }
    ).encode("utf-8")
).hexdigest()

OBSERVED_YEAR_COUNTS = {
    2026: 65,
    2025: 80,
    2024: 61,
    2023: 64,
    2022: 87,
    2021: 82,
    2020: 77,
    2019: 156,
    2018: 175,
    2017: 299,
    2016: 446,
    2015: 554,
    2014: 710,
    2013: 1016,
    2012: 1010,
    2011: 997,
    2010: 1334,
    2009: 1200,
    2008: 1047,
    2007: 972,
    2006: 865,
    2005: 822,
    2004: 663,
    2003: 655,
    2002: 356,
    2001: 300,
    2000: 182,
}

SOURCE_WARNINGS = (
    "The year=0 route is the portal's rolling current subset, not a complete "
    "year. The year operation uses an explicit inventory year and retrieves "
    "the source's complete JSON array for that year.",
    "Join this archive to RealAuction by case number, parcel, and sale date. "
    "A matching outcome ordinarily describes the same underlying auction "
    "event and is not automatically independent corroboration.",
    "A reported sale or purchase price does not establish completed title "
    "transfer; the court confirmation and recorded sheriff's deed supply that "
    "separate evidence.",
)


class LickingArchiveError(RuntimeError):
    """Base class for verified archive query failures."""


class LickingArchiveSelectionError(LickingArchiveError):
    """A caller selector or continuation cursor is invalid."""

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


class LickingArchiveTransportError(LickingArchiveError):
    """The official API was unreachable after bounded retries."""


class LickingArchiveHTTPError(LickingArchiveError):
    """The official API returned a non-success HTTP response."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(
            f"Licking foreclosure archive returned HTTP {status_code} for {url}"
        )


class LickingArchiveRateLimited(LickingArchiveError):
    """The official API returned HTTP 429."""


class LickingArchiveSourceChanged(LickingArchiveError):
    """A verified endpoint, resolved host, or response schema changed."""


@dataclass(frozen=True)
class YearInventory:
    years: tuple[int, ...]
    records: tuple[dict[str, Any], ...]
    source_url: str

    @property
    def current_archive_year(self) -> int:
        return max(self.years)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = (
        value.get_text(" ", strip=True)
        if hasattr(value, "get_text")
        else str(value)
    )
    return re.sub(r"\s+", " ", text).strip()


def _nonblank(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise argparse.ArgumentTypeError("value must not be blank")
    return candidate


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("limit must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("limit must be positive")
    return parsed


def _year_value(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("year must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("year must be positive")
    return parsed


def _money_amount(value: Any, *, field_name: str) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", raw)
    if not cleaned:
        raise LickingArchiveSourceChanged(
            f"{field_name} is no longer a recognizable money value"
        )
    try:
        return format(Decimal(cleaned), "f")
    except InvalidOperation as error:
        raise LickingArchiveSourceChanged(
            f"{field_name} is no longer a recognizable money value"
        ) from error


def _source_date(value: Any, *, field_name: str, required: bool) -> str | None:
    raw = _clean(value)
    if not raw:
        if required:
            raise LickingArchiveSourceChanged(f"{field_name} is missing")
        return None
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise LickingArchiveSourceChanged(
            f"{field_name} date format changed"
        ) from error


def _status(value: Any) -> str:
    raw = _clean(value)
    if not raw:
        return "not_reported"
    return re.sub(r"[^a-z0-9]+", "_", raw.casefold()).strip("_")


def _parcel_values(value: Any) -> tuple[list[str], list[str]]:
    raw = _clean(value)
    if not raw:
        return [], []
    soup = BeautifulSoup(str(value), "html.parser")
    anchors = soup.find_all("a")
    if not anchors:
        raise LickingArchiveSourceChanged(
            "non-empty parcel field no longer contains linked parcel values"
        )
    parcel_ids: list[str] = []
    parcel_links: list[str] = []
    for anchor in anchors:
        parcel_id = _clean(anchor)
        if not parcel_id:
            raise LickingArchiveSourceChanged(
                "parcel link is missing its parcel identifier"
            )
        parcel_ids.append(parcel_id)
        href = _clean(anchor.get("href"))
        if href:
            parcel_links.append(href)
    return parcel_ids, parcel_links


def _html_text(value: Any) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    return _clean(BeautifulSoup(str(value), "html.parser"))


def _source_metadata() -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_ID,
        name=SOURCE_NAME,
        source_role=(
            "official_county_sheriff_foreclosure_archive_and_sale_outcomes"
        ),
        base_url=BASE_URL,
        dataset_id="licking-county-sheriff-foreclosure-archive",
        metadata={
            "publisher": "Licking County Sheriff",
            "authentication": "none",
            "native_identity_key": "case_number",
            "api_response_pagination": "none",
            "rolling_current_selector": 0,
            "observed_at": OBSERVED_AT,
        },
    )


def _jurisdiction() -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=COUNTY_GEOID,
        name=COUNTY_NAME,
        state_code=STATE_CODE,
        county_fips=COUNTY_GEOID,
        locality="Licking County",
    )


def _query(
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=_source_metadata(),
        jurisdiction=_jurisdiction(),
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "source_returns_complete_selected_array": True,
                "default_result_cap": None,
            },
        ),
    )


def _source_record() -> dict[str, Any]:
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "source-contract",
            "licking-foreclosure-archive-v1",
        ),
        "source_id": SOURCE_ID,
        "record_kind": "source_contract",
        "publisher": "Licking County Sheriff",
        "official_info_url": OFFICIAL_INFO_URL,
        "observed_at": OBSERVED_AT,
        "access": {
            "authentication": "none",
            "years": "anonymous_json",
            "year_enumeration": "anonymous_json",
            "exact_case": "anonymous_json",
            "not_found_behavior": "HTTP 200 with JSON null",
            "resolved_host": EXPECTED_HOST,
        },
        "endpoints": {
            "year_inventory": YEARS_URL,
            "full_year": f"{FORECLOSURES_URL}?year={{year}}",
            "rolling_current_subset": f"{FORECLOSURES_URL}?year=0",
            "exact_case": f"{DETAIL_URL_BASE}/{{case_number}}",
        },
        "native_identity": {
            "key": "case_number",
            "observed_unique_across_inventory": True,
            "observed_rows_checked": sum(OBSERVED_YEAR_COUNTS.values()),
        },
        "inventory_observation": {
            "years": list(range(2026, 1999, -1)),
            "year_counts": {
                str(year): count
                for year, count in OBSERVED_YEAR_COUNTS.items()
            },
            "total_records": sum(OBSERVED_YEAR_COUNTS.values()),
            "schema_keyset_count": 1,
            "records_missing_case_number": 0,
        },
        "temporal_views": {
            "year_0": {
                "kind": "rolling_current_subset",
                "complete_year": False,
                "listed_in_year_inventory": False,
            },
            "maximum_inventory_year": {
                "kind": "current_year_archive",
                "complete_at_retrieval": True,
                "mutable": True,
            },
            "earlier_inventory_years": {
                "kind": "historical_archive_year",
                "complete_at_retrieval": True,
                "mutable": "source_corrections_remain_possible",
            },
        },
        "public_fields": [
            "sale_date",
            "case_number",
            "address",
            "city",
            "postal_code",
            "advertise_date",
            "appraisal_value",
            "terms",
            "sale_type",
            "required_deposit",
            "status",
            "parcel_ids",
            "deed_as",
            "purchaser_contact_name",
            "purchaser_address",
            "purchase_price",
        ],
        "observed_field_notes": {
            "AdvertiseDate": "present but null in all 14,275 observed rows",
            "RequiredDepositAmmount": (
                "source key preserves the publisher's spelling; normalized "
                "field uses required_deposit"
            ),
            "historical_coverage": (
                "older rows frequently omit parcel, sale type, and deposit "
                "fields while retaining case, date, address, and outcomes"
            ),
        },
        "public_field_gaps": [
            "plaintiff",
            "defendant",
            "court_docket_events",
            "court_filing_documents",
            "judgment_and_confirmation_orders",
            "auction_aid",
            "bid_history",
            "full_legal_description",
            "recorded_sheriff_deed",
            "title_status",
        ],
        "official_complements": [
            {
                "source_id": "us-oh-licking-sheriff-realauction",
                "relationship": "current_auction_listing_and_bid_status",
                "join_keys": ["case_number", "parcel_id", "sale_date"],
                "matched_outcome_evidence": (
                    "same_underlying_event_unless_separate_assertion_is_shown"
                ),
            },
            {
                "name": "Licking County Common Pleas records search",
                "url": (
                    "https://lickingcounty.gov/depts/clerk/"
                    "records_search.htm"
                ),
                "relationship": "case_number_to_docket_and_pleadings",
            },
        ],
        "schema_fingerprint": SCHEMA_FINGERPRINT,
    }


def parse_year_inventory(
    payload: Any,
    *,
    source_url: str,
) -> YearInventory:
    """Parse the official descending year inventory."""

    if not isinstance(payload, list) or not payload:
        raise LickingArchiveSourceChanged(
            "sale-year inventory is no longer a non-empty JSON list"
        )
    years: list[int] = []
    for value in payload:
        if isinstance(value, bool) or not isinstance(value, int):
            raise LickingArchiveSourceChanged(
                "sale-year inventory contains a non-integer"
            )
        years.append(value)
    if len(set(years)) != len(years):
        raise LickingArchiveSourceChanged(
            "sale-year inventory contains duplicate years"
        )
    current = max(years)
    records = tuple(
        {
            "canonical_ref": canonical_property_ref(
                SOURCE_ID,
                COUNTY_GEOID,
                "foreclosure-archive-year",
                str(year),
            ),
            "evidence_ref": canonical_property_ref(
                SOURCE_ID,
                COUNTY_GEOID,
                "foreclosure-archive-year",
                str(year),
            ),
            "source_id": SOURCE_ID,
            "record_kind": "foreclosure_archive_year",
            "county_geoid": COUNTY_GEOID,
            "year": year,
            "temporal_view": (
                "current_year_archive"
                if year == current
                else "historical_archive_year"
            ),
            "source_url": source_url,
            "access_state": "anonymous",
            "observed_at": OBSERVED_AT,
        }
        for year in years
    )
    return YearInventory(tuple(years), records, source_url)


def _validate_record_schema(raw: Mapping[str, Any]) -> None:
    missing = [field for field in EXPECTED_FIELDS if field not in raw]
    if missing:
        raise LickingArchiveSourceChanged(
            "foreclosure archive fields changed; missing "
            + ", ".join(missing)
        )


def normalize_foreclosure(
    raw: Mapping[str, Any],
    *,
    source_url: str,
    source_view: str,
    current_archive_year: int,
    expected_year: int | None = None,
) -> dict[str, Any]:
    """Normalize one official archive row without conflating RealAuction."""

    _validate_record_schema(raw)
    case_number = _clean(raw["CaseNumber"])
    if not case_number:
        raise LickingArchiveSourceChanged(
            "foreclosure archive record is missing CaseNumber"
        )
    sale_date = _source_date(
        raw["SaleDate"],
        field_name="SaleDate",
        required=True,
    )
    assert sale_date is not None
    archive_year = int(sale_date[:4])
    if expected_year is not None and archive_year != expected_year:
        raise LickingArchiveSourceChanged(
            "foreclosure archive row falls outside the requested year"
        )
    parcel_ids, parcel_links = _parcel_values(raw["Parcels"])
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "foreclosure-case",
        case_number,
    )
    status_raw = _clean(raw["Status"])
    purchaser_address_raw = _clean(raw["PurchaserAddress"]) or None
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "record_kind": "sheriff_foreclosure_archive_record",
        "record_scope": "county_foreclosure_archive_and_sale_outcome",
        "county_geoid": COUNTY_GEOID,
        "native_case_number": case_number,
        "identity_kind": "county_archive_case_number",
        "archive_year": archive_year,
        "temporal_view": (
            "current_year_archive_mutable"
            if archive_year == current_archive_year
            else "historical_archive_year"
        ),
        "source_view": source_view,
        "sale_date_raw": _clean(raw["SaleDate"]),
        "sale_date": sale_date,
        "case_number": case_number,
        "property_address": _clean(raw["Address"]) or None,
        "city": _clean(raw["City"]) or None,
        "state_code": STATE_CODE,
        "postal_code_raw": _clean(raw["Zip"]) or None,
        "advertise_date_raw": _clean(raw["AdvertiseDate"]) or None,
        "advertise_date": _source_date(
            raw["AdvertiseDate"],
            field_name="AdvertiseDate",
            required=False,
        ),
        "appraised_value_raw": _clean(raw["AppraisalValue"]) or None,
        "appraised_value_amount": _money_amount(
            raw["AppraisalValue"],
            field_name="AppraisalValue",
        ),
        "terms": _clean(raw["Terms"]) or None,
        "sale_type": _clean(raw["SaleType"]) or None,
        "required_deposit_raw": (
            _clean(raw["RequiredDepositAmmount"]) or None
        ),
        "required_deposit_amount": _money_amount(
            raw["RequiredDepositAmmount"],
            field_name="RequiredDepositAmmount",
        ),
        "status_raw": status_raw or None,
        "status": _status(raw["Status"]),
        "status_is_reported": bool(status_raw),
        "parcel_html_raw": _clean(raw["Parcels"]) or None,
        "parcel_ids": parcel_ids,
        "parcel_links": parcel_links,
        "deed_as": _clean(raw["DeedAs"]) or None,
        "purchaser_contact_name": _clean(raw["PurchaserName"]) or None,
        "purchaser_address_raw": purchaser_address_raw,
        "purchaser_address_text": _html_text(raw["PurchaserAddress"]),
        "purchase_price_raw": _clean(raw["PurchasePrice"]) or None,
        "purchase_price_amount": _money_amount(
            raw["PurchasePrice"],
            field_name="PurchasePrice",
        ),
        "realauction_join": {
            "keys": {
                "case_number": case_number,
                "parcel_ids": parcel_ids,
                "sale_date": sale_date,
            },
            "matched_outcome_evidence": (
                "same_underlying_event_unless_separate_assertion_is_shown"
            ),
        },
        "source_url": source_url,
        "access_state": "anonymous",
        "schema_fingerprint": SCHEMA_FINGERPRINT,
        "raw_record": dict(raw),
    }


def parse_year_payload(
    payload: Any,
    *,
    source_url: str,
    year: int,
    current_archive_year: int,
) -> tuple[dict[str, Any], ...]:
    """Parse the complete JSON array for one explicit archive year."""

    if not isinstance(payload, list):
        raise LickingArchiveSourceChanged(
            "full-year endpoint no longer returns a JSON list"
        )
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in payload:
        if not isinstance(value, Mapping):
            raise LickingArchiveSourceChanged(
                "full-year endpoint contains a non-object row"
            )
        record = normalize_foreclosure(
            value,
            source_url=source_url,
            source_view="explicit_full_year",
            current_archive_year=current_archive_year,
            expected_year=year,
        )
        case_number = str(record["native_case_number"])
        if case_number in seen:
            raise LickingArchiveSourceChanged(
                f"full-year endpoint repeated case number {case_number}"
            )
        seen.add(case_number)
        records.append(record)
    return tuple(records)


def parse_current_payload(
    payload: Any,
    *,
    source_url: str,
    current_archive_year: int,
) -> tuple[dict[str, Any], ...]:
    """Parse the portal's rolling, non-exhaustive ``year=0`` view."""

    if not isinstance(payload, list):
        raise LickingArchiveSourceChanged(
            "rolling-current endpoint no longer returns a JSON list"
        )
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in payload:
        if not isinstance(value, Mapping):
            raise LickingArchiveSourceChanged(
                "rolling-current endpoint contains a non-object row"
            )
        record = normalize_foreclosure(
            value,
            source_url=source_url,
            source_view="rolling_current_subset",
            current_archive_year=current_archive_year,
        )
        case_number = str(record["native_case_number"])
        if case_number in seen:
            raise LickingArchiveSourceChanged(
                f"rolling-current endpoint repeated case number {case_number}"
            )
        seen.add(case_number)
        records.append(record)
    return tuple(records)


def parse_case_payload(
    payload: Any,
    *,
    source_url: str,
    requested_case_number: str,
    current_archive_year: int,
) -> tuple[dict[str, Any], ...]:
    """Parse an exact case response; JSON null is authoritative no-results."""

    if payload is None:
        return ()
    if not isinstance(payload, Mapping):
        raise LickingArchiveSourceChanged(
            "exact-case endpoint no longer returns an object or null"
        )
    record = normalize_foreclosure(
        payload,
        source_url=source_url,
        source_view="exact_case_detail",
        current_archive_year=current_archive_year,
    )
    if str(record["native_case_number"]).casefold() != (
        requested_case_number.casefold()
    ):
        raise LickingArchiveSourceChanged(
            "exact-case endpoint returned a different case number"
        )
    return (record,)


class LickingForeclosureArchiveClient:
    """Requests-compatible client for the verified official JSON endpoints."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json, text/plain, */*",
                }
            )
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_retries = max_retries
        self._sleeper = sleeper
        self._clock = clock
        self._last_request_at = 0.0
        self.request_count = 0

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _json(
        self,
        url: str,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> tuple[Any, str]:
        for attempt in range(self.max_retries + 1):
            elapsed = self._clock() - self._last_request_at
            if elapsed < self.minimum_interval:
                self._sleeper(self.minimum_interval - elapsed)
            try:
                self._last_request_at = self._clock()
                self.request_count += 1
                response = self.session.request(
                    "GET",
                    url,
                    params=dict(parameters or {}),
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                raise LickingArchiveTransportError(
                    f"Licking foreclosure archive request failed: {error}"
                ) from error

            response_url = str(getattr(response, "url", url))
            response_host = (
                urlparse(response_url).hostname or ""
            ).casefold()
            if response_host != EXPECTED_HOST:
                raise LickingArchiveSourceChanged(
                    "Licking archive response resolved outside the official "
                    f"archive host: {response_host or '<missing>'}"
                )
            status_code = int(response.status_code)
            if (status_code == 429 or status_code >= 500) and (
                attempt < self.max_retries
            ):
                self._sleeper(0.5 * (2**attempt))
                continue
            if status_code == 429:
                raise LickingArchiveRateLimited(
                    "Licking foreclosure archive returned HTTP 429"
                )
            if status_code < 200 or status_code >= 300:
                raise LickingArchiveHTTPError(status_code, response_url)
            try:
                payload = json.loads(str(response.text))
            except json.JSONDecodeError as error:
                raise LickingArchiveSourceChanged(
                    "Licking archive endpoint returned non-JSON content"
                ) from error
            return payload, response_url
        raise LickingArchiveTransportError(
            "Licking foreclosure archive request exhausted retries"
        )

    def years(self) -> YearInventory:
        payload, source_url = self._json(YEARS_URL)
        return parse_year_inventory(payload, source_url=source_url)

    def year(
        self,
        year: int,
        *,
        current_archive_year: int,
    ) -> tuple[dict[str, Any], ...]:
        payload, source_url = self._json(
            FORECLOSURES_URL,
            parameters={"year": year},
        )
        return parse_year_payload(
            payload,
            source_url=source_url,
            year=year,
            current_archive_year=current_archive_year,
        )

    def current(
        self,
        *,
        current_archive_year: int,
    ) -> tuple[dict[str, Any], ...]:
        payload, source_url = self._json(
            FORECLOSURES_URL,
            parameters={"year": 0},
        )
        return parse_current_payload(
            payload,
            source_url=source_url,
            current_archive_year=current_archive_year,
        )

    def case(
        self,
        case_number: str,
        *,
        current_archive_year: int,
    ) -> tuple[dict[str, Any], ...]:
        encoded = quote(case_number, safe="")
        payload, source_url = self._json(f"{DETAIL_URL_BASE}/{encoded}")
        return parse_case_payload(
            payload,
            source_url=source_url,
            requested_case_number=case_number,
            current_archive_year=current_archive_year,
        )


def _selection_payload(
    *,
    year: int,
    case_number: str | None,
    parcel: str | None,
    address: str | None,
    status: str | None,
    sale_type: str | None,
    purchaser: str | None,
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "operation": "year",
        "year": year,
        "case_number": case_number,
        "parcel": parcel,
        "address": address,
        "status": status,
        "sale_type": sale_type,
        "purchaser": purchaser,
        "schema_fingerprint": SCHEMA_FINGERPRINT,
    }


def _membership_fingerprint(records: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        canonical_json(
            [str(record["native_case_number"]) for record in records]
        ).encode("utf-8")
    ).hexdigest()


def _cursor_encode(payload: Mapping[str, Any]) -> str:
    token = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _cursor_decode(value: str) -> Mapping[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise LickingArchiveSelectionError(
            "invalid_cursor",
            "cursor is not a Licking foreclosure archive continuation",
        )
    token = value.removeprefix(CURSOR_PREFIX)
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as error:
        raise LickingArchiveSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(payload, Mapping):
        raise LickingArchiveSelectionError(
            "invalid_cursor",
            "cursor payload changed type",
        )
    return payload


def _window_records(
    records: Sequence[Mapping[str, Any]],
    *,
    selection: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    membership = _membership_fingerprint(records)
    selection_fingerprint = hashlib.sha256(
        canonical_json(selection).encode("utf-8")
    ).hexdigest()
    offset = 0
    if cursor:
        payload = _cursor_decode(cursor)
        if payload.get("source_id") != SOURCE_ID:
            raise LickingArchiveSelectionError(
                "cursor_source_mismatch",
                "cursor belongs to a different source",
            )
        if payload.get("selection_fingerprint") != selection_fingerprint:
            raise LickingArchiveSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to a different year or filter selection",
            )
        if (
            payload.get("membership_fingerprint") != membership
            or payload.get("total") != len(records)
        ):
            raise LickingArchiveSelectionError(
                "cursor_membership_changed",
                "ordered case membership changed since the cursor was issued",
            )
        try:
            offset = int(payload["offset"])
        except (KeyError, TypeError, ValueError) as error:
            raise LickingArchiveSelectionError(
                "invalid_cursor",
                "cursor offset is invalid",
            ) from error
        if offset < 0 or offset > len(records):
            raise LickingArchiveSelectionError(
                "invalid_cursor",
                "cursor offset is outside the result set",
            )
        expected_anchor = (
            str(records[offset - 1]["native_case_number"])
            if offset > 0
            else None
        )
        if payload.get("anchor_before") != expected_anchor:
            raise LickingArchiveSelectionError(
                "cursor_boundary_changed",
                "cursor boundary case changed",
            )

    end = len(records) if limit is None else min(offset + limit, len(records))
    selected = [dict(record) for record in records[offset:end]]
    next_cursor = None
    if end < len(records):
        next_cursor = _cursor_encode(
            {
                "source_id": SOURCE_ID,
                "selection_fingerprint": selection_fingerprint,
                "membership_fingerprint": membership,
                "offset": end,
                "anchor_before": str(
                    records[end - 1]["native_case_number"]
                ),
                "total": len(records),
            }
        )
    return selected, next_cursor


def _contains(haystack: Any, needle: str | None) -> bool:
    return not needle or needle.casefold() in str(haystack or "").casefold()


def _matches(
    record: Mapping[str, Any],
    *,
    case_number: str | None,
    parcel: str | None,
    address: str | None,
    status: str | None,
    sale_type: str | None,
    purchaser: str | None,
) -> bool:
    return all(
        (
            _contains(record.get("case_number"), case_number),
            _contains(" ".join(record.get("parcel_ids") or ()), parcel),
            _contains(
                " ".join(
                    [
                        str(record.get("property_address") or ""),
                        str(record.get("city") or ""),
                        str(record.get("postal_code_raw") or ""),
                    ]
                ),
                address,
            ),
            _contains(record.get("status_raw"), status),
            _contains(record.get("sale_type"), sale_type),
            _contains(
                " ".join(
                    [
                        str(record.get("deed_as") or ""),
                        str(record.get("purchaser_contact_name") or ""),
                        str(record.get("purchaser_address_text") or ""),
                    ]
                ),
                purchaser,
            ),
        )
    )


def _source_failure(
    query: PublicRecordsQuery,
    error: LickingArchiveError,
) -> PublicRecordsResult:
    if isinstance(error, LickingArchiveRateLimited):
        status = ResultStatus.RATE_LIMITED
        code = "rate_limited"
        category = "rate_limit"
        retryable = True
        details: dict[str, Any] = {}
    elif isinstance(error, LickingArchiveHTTPError):
        status = (
            ResultStatus.RESTRICTED
            if error.status_code in {401, 403}
            else ResultStatus.UNAVAILABLE
        )
        code = f"http_{error.status_code}"
        category = "http"
        retryable = error.status_code >= 500
        details = {
            "status_code": error.status_code,
            "url": error.url,
            "access_characterization": "observed_response_not_policy",
        }
    elif isinstance(error, LickingArchiveTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "transport_error"
        category = "transport"
        retryable = True
        details = {}
    elif isinstance(error, LickingArchiveSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_or_provenance_changed"
        category = "source_schema"
        retryable = False
        details = {}
    elif isinstance(error, LickingArchiveSelectionError):
        status = ResultStatus.UNAVAILABLE
        code = error.code
        category = "query"
        retryable = False
        details = dict(error.details)
    else:
        status = ResultStatus.UNAVAILABLE
        code = "source_error"
        category = "source"
        retryable = False
        details = {}
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category=category,
                retryable=retryable,
                details=details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: LickingForeclosureArchiveClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one standalone archive operation."""

    operation = args.command
    limit = getattr(args, "limit", None)
    cursor = getattr(args, "cursor", None)
    parameters: dict[str, Any] = {}
    if operation == "year":
        parameters = {
            "year": args.year,
            "case_number": args.case_number,
            "parcel": args.parcel,
            "address": args.address,
            "status": args.status,
            "sale_type": args.sale_type,
            "purchaser": args.purchaser,
            "completeness": (
                "complete_selected_official_array"
                if limit is None
                else "caller_window_after_complete_selected_official_array"
            ),
        }
    elif operation == "case":
        parameters = {"case_number": args.case_number}
    elif operation == "probe":
        parameters = {
            "probe_year": PROBE_YEAR,
            "probe_case_number": args.case_number,
            "routes": [
                "year_inventory",
                "explicit_full_year",
                "rolling_current_subset",
                "exact_case",
            ],
        }
    query = _query(
        operation,
        parameters=parameters,
        limit=limit,
        cursor=cursor,
    )
    source_client = client or LickingForeclosureArchiveClient(
        timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
        minimum_interval=float(
            getattr(args, "minimum_interval", DEFAULT_MINIMUM_INTERVAL)
        ),
        max_retries=int(getattr(args, "retry_attempts", DEFAULT_MAX_RETRIES)),
    )

    try:
        if operation == "source":
            result = PublicRecordsResult.success(
                query,
                [_source_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif operation == "years":
            inventory = source_client.years()
            result = PublicRecordsResult.success(
                query,
                inventory.records,
                warnings=SOURCE_WARNINGS,
            )
        elif operation == "year":
            inventory = source_client.years()
            if args.year not in inventory.years:
                raise LickingArchiveSelectionError(
                    "year_not_in_inventory",
                    (
                        f"{args.year} is not listed in the official sale-year "
                        "inventory"
                    ),
                    details={
                        "available_years": list(inventory.years),
                    },
                )
            records = source_client.year(
                args.year,
                current_archive_year=inventory.current_archive_year,
            )
            filtered = [
                dict(record)
                for record in records
                if _matches(
                    record,
                    case_number=args.case_number,
                    parcel=args.parcel,
                    address=args.address,
                    status=args.status,
                    sale_type=args.sale_type,
                    purchaser=args.purchaser,
                )
            ]
            selection = _selection_payload(
                year=args.year,
                case_number=args.case_number,
                parcel=args.parcel,
                address=args.address,
                status=args.status,
                sale_type=args.sale_type,
                purchaser=args.purchaser,
            )
            window, next_cursor = _window_records(
                filtered,
                selection=selection,
                limit=limit,
                cursor=cursor,
            )
            for record in window:
                record["retrieval"] = {
                    "official_year_record_count": len(records),
                    "matching_record_count": len(filtered),
                    "source_response_pagination": "none",
                    "complete_selected_array_fetched": True,
                    "adapter_truncated": next_cursor is not None,
                }
            result = PublicRecordsResult.success(
                query,
                window,
                next_cursor=next_cursor,
                warnings=SOURCE_WARNINGS,
            )
        elif operation == "case":
            inventory = source_client.years()
            records = source_client.case(
                args.case_number,
                current_archive_year=inventory.current_archive_year,
            )
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=SOURCE_WARNINGS,
            )
        else:
            inventory = source_client.years()
            full_year = source_client.year(
                PROBE_YEAR,
                current_archive_year=inventory.current_archive_year,
            )
            rolling = source_client.current(
                current_archive_year=inventory.current_archive_year,
            )
            detail = source_client.case(
                args.case_number,
                current_archive_year=inventory.current_archive_year,
            )
            if PROBE_YEAR not in inventory.years:
                raise LickingArchiveSourceChanged(
                    "verified probe year disappeared from the inventory"
                )
            if not detail:
                raise LickingArchiveSourceChanged(
                    "verified exact-case sentinel returned JSON null"
                )
            if not any(
                str(record["case_number"]).casefold()
                == args.case_number.casefold()
                for record in full_year
            ):
                raise LickingArchiveSourceChanged(
                    "exact-case sentinel is absent from its full-year array"
                )
            probe = _source_record()
            probe["record_kind"] = "source_probe"
            probe["probe"] = {
                "status": "available",
                "routes_exercised": [
                    "year_inventory",
                    "explicit_full_year",
                    "rolling_current_subset",
                    "exact_case",
                ],
                "inventory_first_year": min(inventory.years),
                "inventory_latest_year": max(inventory.years),
                "inventory_year_count": len(inventory.years),
                "probe_year": PROBE_YEAR,
                "probe_year_record_count": len(full_year),
                "rolling_current_record_count": len(rolling),
                "sentinel_case_number": args.case_number,
                "sentinel_status": detail[0]["status"],
                "sentinel_sale_date": detail[0]["sale_date"],
                "sentinel_purchase_price_amount": detail[0][
                    "purchase_price_amount"
                ],
            }
            result = PublicRecordsResult.success(
                query,
                [probe],
                warnings=SOURCE_WARNINGS,
            )
    except LickingArchiveError as error:
        result = _source_failure(query, error)

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        _log(query, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Licking foreclosure archive {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Licking foreclosure archive {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "foreclosure_archive_year":
            print(f"- {record['year']} | {record['temporal_view']}")
        elif record.get("record_kind") == (
            "sheriff_foreclosure_archive_record"
        ):
            print(
                f"- {record['case_number']} | {record['sale_date']} | "
                f"{record.get('property_address') or '?'} | "
                f"{record['status']}"
            )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the official Licking County Sheriff foreclosure archive"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show the verified archive contract, fields, gaps, and joins",
    )
    add_output_args(source)

    years = subparsers.add_parser(
        "years",
        help="Return the complete official sale-year inventory",
    )
    add_output_args(years)

    year = subparsers.add_parser(
        "year",
        help="Enumerate one complete official archive year",
    )
    year.add_argument("--year", required=True, type=_year_value)
    year.add_argument(
        "--case-number",
        help="Keep rows whose case number contains this text",
    )
    year.add_argument(
        "--parcel",
        help="Keep rows whose parsed parcel identifiers contain this text",
    )
    year.add_argument(
        "--address",
        help="Keep rows whose address, city, or postal text contains this text",
    )
    year.add_argument(
        "--status",
        help="Keep rows whose source status contains this text",
    )
    year.add_argument(
        "--sale-type",
        help="Keep rows whose source sale type contains this text",
    )
    year.add_argument(
        "--purchaser",
        help="Keep rows whose deed-as, contact, or purchaser address matches",
    )
    year.add_argument(
        "--limit",
        type=_positive_int,
        help="Return this many rows and a continuation cursor if more remain",
    )
    year.add_argument("--cursor", help="Resume a prior bounded year query")
    add_output_args(year)

    case = subparsers.add_parser(
        "case",
        help="Fetch one exact archive case number",
    )
    case.add_argument("--case-number", required=True, type=_nonblank)
    add_output_args(case)

    probe = subparsers.add_parser(
        "probe",
        help=(
            "Probe inventory, full-year, rolling-current, and exact-case routes"
        ),
    )
    probe.add_argument(
        "--case-number",
        type=_nonblank,
        default=PROBE_CASE_NUMBER,
        help="Known case in the verified 2026 probe year",
    )
    add_output_args(probe)
    for command in subparsers.choices.values():
        command.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
        command.add_argument(
            "--minimum-interval",
            type=float,
            default=DEFAULT_MINIMUM_INTERVAL,
        )
        command.add_argument(
            "--retry-attempts",
            type=int,
            default=DEFAULT_MAX_RETRIES,
        )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
