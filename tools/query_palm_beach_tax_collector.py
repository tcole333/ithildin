#!/usr/bin/env python3
"""Query Palm Beach County's public Aumentum property-tax account portal.

The Constitutional Tax Collector publishes a DNN/PublicAccessNow application
backed by source-specific JSON modules.  This adapter keeps the source's
identities separate:

* the 17-digit Property Control Number (PCN) is the cross-source parcel join;
* ``AlternateKey`` is the Tax Collector's account locator;
* bill ID, bill number, installment, receipt number, and payment occurrence
  remain distinct source identifiers.

The QuickSearch configuration currently publishes a 300-record maximum.  A
query that reaches that value is returned as ``partial`` because the portal
does not expose whether additional matching accounts exist.  The value is a
publisher boundary, not an adapter-selected result cap.

Examples:
    uv run python tools/query_palm_beach_tax_collector.py search SMITH
    uv run python tools/query_palm_beach_tax_collector.py owner "SMITH JOHN"
    uv run python tools/query_palm_beach_tax_collector.py parcel \
        04-36-43-25-00-000-5040
    uv run python tools/query_palm_beach_tax_collector.py account \
        04-36-43-25-00-000-5040
    uv run python tools/query_palm_beach_tax_collector.py bills \
        04-36-43-25-00-000-5040
    uv run python tools/query_palm_beach_tax_collector.py payments \
        04-36-43-25-00-000-5040
    uv run python tools/query_palm_beach_tax_collector.py discovery
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlencode, urljoin

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
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
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_property_ref
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
        sha256_fingerprint,
    )
    from public_records_http import (
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-fl-palm-beach-tax-collector"
COUNTY_GEOID = "12099"
STATE_FIPS = "12"
STATE_CODE = "FL"
COUNTY_NAME = "Palm Beach County"

OFFICIAL_GUIDANCE_URL = "https://www.pbctax.gov/propertytax/"
PORTAL_ROOT = "https://pbctax.publicaccessnow.com/"
SEARCH_PAGE_URL = f"{PORTAL_ROOT}PropertyTax.aspx"
QUICK_SEARCH_URL = (
    f"{PORTAL_ROOT}DesktopModules/QuickSearch/API/Module/GetData"
)
QUICK_SETTINGS_URL = (
    f"{PORTAL_ROOT}DesktopModules/QuickSearch/API/Settings/GetSettings"
)
PROCESSING_URL = f"{PORTAL_ROOT}PropertyTax/Processing.aspx"
ACCOUNT_URL = f"{PORTAL_ROOT}PropertyTax/Account.aspx"
ACCOUNT_SUMMARY_URL = (
    f"{PORTAL_ROOT}API/AccountSummary/AccountSummary/GetData"
)
BILLS_URL = f"{PORTAL_ROOT}API/PaymentBill/Bill/GetData"
PAYMENT_SETTINGS_URL = (
    f"{PORTAL_ROOT}API/DataDisplay/DataSources/GetViewSettings"
)
PAYMENT_DATA_URL = f"{PORTAL_ROOT}API/DataDisplay/DataSources/GetData"
BILL_DETAIL_URL = f"{PORTAL_ROOT}PropertyTax/Account/BillDetail.aspx"
REFRESH_URL = f"{PORTAL_ROOT}API/AumentumSync/AumentumSync/FetchData"
SYNC_STATUS_URL = (
    f"{PORTAL_ROOT}API/AumentumSync/AumentumSync/GetAumentumSyncStatus"
)

QUICK_SEARCH_MODULE_ID = 449
QUICK_SEARCH_TAB_ID = 47
PROCESSING_TAB_ID = 48
REFRESH_MODULE_ID = 461
ACCOUNT_MODULE_IDS = (462, 465)
BILLS_MODULE_ID = 652
PAYMENT_HISTORY_MODULE_ID = 663
OBSERVED_PAYMENT_PAGE_SIZE = 18
DEFAULT_TIMEOUT = 45.0
DEFAULT_RETRY_ATTEMPTS = 3
SEARCH_CURSOR_PREFIX = "pbc-tax-search:v1:"
PAYMENT_CURSOR_PREFIX = "pbc-tax-payments:v1:"
CURSOR_VERSION = 1
SENTINEL_PCN = "04364325000005040"

PROPERTY_APPRAISER_SOURCE_ID = "us-fl-palm-beach-property-appraiser"
OFFICIAL_RECORDS_SOURCE_ID = "us-fl-palm-beach-official-records"
TAX_DEEDS_SOURCE_ID = "us-fl-palm-beach-tax-deeds"
FL_DOR_SOURCE_ID = "us-fl-dor-property-roll"

FIELD_QUALIFIERS = {
    "owner": "Owner",
    "owners": "Owners",
    "parcel": "ParcelID",
    "pcn": "ParcelID",
    "situs": "Situs",
    "address": "Situs",
    "postal": "PostalStreetName",
    "postal-street-number": "PostalStreetNumber",
    "postal-street-name": "PostalStreetName",
    "situs-street-number": "SitusStreetNumber",
    "situs-street-name": "SitusStreetName",
    "paid-status": "PaidStatus",
    "delivery": "Delivery",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Palm Beach County Constitutional Tax Collector Property Tax",
    source_role=(
        "county_property_tax_account_bill_installment_payment_history"
    ),
    base_url=OFFICIAL_GUIDANCE_URL,
    dataset_id="AUMENTUMTAX/QuickSearch+AccountSummary+Bill+PaymentHistory",
    metadata={
        "authority": "Palm Beach County Constitutional Tax Collector",
        "operator": "Aumentum Technologies PublicAccessNow",
        "county_geoid": COUNTY_GEOID,
        "portal_root": PORTAL_ROOT,
        "parcel_join": "17-digit Property Control Number",
        "account_locator": "AlternateKey",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=f"{COUNTY_NAME}, Florida",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    metadata={"state_fips": STATE_FIPS, "county_fips_3": "099"},
)
SOURCE_WARNINGS = (
    "Tax Collector owner labels are tax-account observations, not recorded "
    "title or beneficial-ownership conclusions.",
    "PCN is the parcel join. AlternateKey, bill ID, bill number, installment, "
    "receipt number, and payment occurrence retain separate source roles.",
    "Confidential flags and publisher-masked values are preserved without "
    "attempting to reconstruct withheld names or addresses.",
    "Current balances, delinquency labels, payment capability, and source "
    "last-updated values are retrieved-state observations; due dates and "
    "effective payment dates remain separate published dates.",
    "Payment-history payer is the source-observed payer and is not promoted "
    "to owner or title holder.",
)


class PalmBeachTaxError(ValueError):
    """Structured query-selection or source-state error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "query_selection",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=False,
            details=self.details,
        )


@dataclass(frozen=True)
class SearchSettings:
    records_per_page: int
    maximum_records: int
    data_source: str
    selected_view: str
    auto_forward: str
    advanced_fields: tuple[str, ...]
    confidentiality_published: bool
    response_schema_fingerprint: str
    raw: Mapping[str, Any]

    @property
    def contract_fingerprint(self) -> str:
        return sha256_fingerprint(self.stable_contract())

    def stable_contract(self) -> dict[str, Any]:
        return {
            "module_id": QUICK_SEARCH_MODULE_ID,
            "tab_id": QUICK_SEARCH_TAB_ID,
            "records_per_page": self.records_per_page,
            "maximum_records": self.maximum_records,
            "data_source": self.data_source,
            "selected_view": self.selected_view,
            "auto_forward": self.auto_forward,
            "advanced_fields": list(self.advanced_fields),
            "confidentiality_published": self.confidentiality_published,
            "response_schema_fingerprint": self.response_schema_fingerprint,
        }


@dataclass(frozen=True)
class SearchCursor:
    criteria_fingerprint: str
    settings_fingerprint: str
    next_offset: int
    source_reported_total: int
    source_effective_total: int


@dataclass(frozen=True)
class SearchFetch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    source_reported_total: int
    source_effective_total: int
    source_ceiling_reached: bool
    pages_fetched: int
    requests_made: int
    settings: SearchSettings


@dataclass(frozen=True)
class PaymentFetch:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    source_reported_total: int | None
    pages_fetched: int
    requests_made: int
    settings_schema_fingerprint: str
    native_page_size: int


def _label_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split())
    return normalized or None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = _text(value)
    if normalized is None:
        return None
    if normalized.casefold() in {"true", "yes", "y", "1"}:
        return True
    if normalized.casefold() in {"false", "no", "n", "0"}:
        return False
    return None


def _positive_int(value: Any, field_name: str = "value") -> int:
    if isinstance(value, bool):
        raise argparse.ArgumentTypeError(f"{field_name} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            f"{field_name} must be a positive integer"
        ) from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"{field_name} must be a positive integer")
    return parsed


def _nonnegative_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            "minimum interval must be a non-negative number"
        ) from error
    if parsed < 0:
        raise argparse.ArgumentTypeError(
            "minimum interval must be a non-negative number"
        )
    return parsed


def normalize_pcn(value: Any, *, required: bool = True) -> str | None:
    """Return the evidenced 17-digit cross-source PCN representation."""

    text = _text(value)
    if text is None:
        if required:
            raise PalmBeachTaxError("pcn_required", "PCN is required")
        return None
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) != 17:
        raise PalmBeachTaxError(
            "invalid_pcn",
            "Palm Beach Property Control Number must contain exactly 17 digits",
            details={"value": text},
        )
    return digits


def format_pcn(value: Any) -> str | None:
    digits = normalize_pcn(value, required=False)
    if digits is None:
        return None
    return (
        f"{digits[0:2]}-{digits[2:4]}-{digits[4:6]}-{digits[6:8]}-"
        f"{digits[8:10]}-{digits[10:13]}-{digits[13:17]}"
    )


def _money(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    negative = text.startswith("(") and text.endswith(")")
    normalized = text.strip("()").replace("$", "").replace(",", "").strip()
    if normalized in {"", "-", "—"}:
        return None
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
        return text
    if negative and not normalized.startswith("-"):
        normalized = f"-{normalized}"
    return normalized


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def _mapping_values(value: Mapping[str, Any]) -> dict[str, Any]:
    return {_label_key(key): item for key, item in value.items()}


def _direct_value(
    value: Mapping[str, Any],
    *aliases: str,
) -> Any:
    indexed = _mapping_values(value)
    for alias in aliases:
        key = _label_key(alias)
        if key in indexed and indexed[key] not in (None, ""):
            return indexed[key]
    return None


def _find_value(value: Any, *aliases: str) -> Any:
    alias_keys = {_label_key(alias) for alias in aliases}
    for _path, item in _walk(value):
        if not isinstance(item, Mapping):
            continue
        indexed = _mapping_values(item)
        for alias in alias_keys:
            if alias in indexed and indexed[alias] not in (None, ""):
                return indexed[alias]
        label = _text(
            _direct_value(item, "label", "name", "title", "displayName")
        )
        if label and _label_key(label) in alias_keys:
            candidate = _direct_value(
                item,
                "value",
                "displayValue",
                "text",
                "content",
            )
            if candidate not in (None, ""):
                return candidate
    return None


def _find_values(value: Any, *aliases: str) -> list[Any]:
    alias_keys = {_label_key(alias) for alias in aliases}
    found: list[Any] = []
    for _path, item in _walk(value):
        if not isinstance(item, Mapping):
            continue
        indexed = _mapping_values(item)
        for alias in alias_keys:
            candidate = indexed.get(alias)
            if candidate not in (None, "") and candidate not in found:
                found.append(candidate)
        label = _text(
            _direct_value(item, "label", "name", "title", "displayName")
        )
        if label and _label_key(label) in alias_keys:
            candidate = _direct_value(
                item,
                "value",
                "displayValue",
                "text",
                "content",
            )
            if candidate not in (None, "") and candidate not in found:
                found.append(candidate)
    return found


def _object_candidates(
    payload: Any,
    *,
    required_keys: Sequence[str],
    minimum_matches: int,
) -> list[tuple[str, Mapping[str, Any]]]:
    keys = {_label_key(key) for key in required_keys}
    candidates: list[tuple[str, Mapping[str, Any]]] = []
    seen: set[str] = set()
    for path, item in _walk(payload):
        if not isinstance(item, Mapping):
            continue
        item_keys = {_label_key(key) for key in item}
        if len(item_keys & keys) < minimum_matches:
            continue
        fingerprint = sha256_fingerprint(item)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        candidates.append((path, item))
    return candidates


def _response_schema(payload: Any) -> str:
    records = [item for _path, item in _walk(payload) if isinstance(item, Mapping)]
    return schema_fingerprint(inferred_schema(records or [{}]))


def _settings_int(payload: Any, *aliases: str) -> int:
    raw = _find_value(payload, *aliases)
    if isinstance(raw, bool):
        raise SourceSchemaError(
            f"Palm Beach Tax Collector setting {aliases[0]} is not an integer",
            url=QUICK_SETTINGS_URL,
            details={"value": raw},
        )
    try:
        parsed = int(raw)
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            f"Palm Beach Tax Collector setting {aliases[0]} is unavailable",
            url=QUICK_SETTINGS_URL,
            details={"value": raw},
        ) from error
    if parsed <= 0:
        raise SourceSchemaError(
            f"Palm Beach Tax Collector setting {aliases[0]} is not positive",
            url=QUICK_SETTINGS_URL,
            details={"value": raw},
        )
    return parsed


def parse_search_settings(payload: Any) -> SearchSettings:
    if not isinstance(payload, (Mapping, list)):
        raise SourceSchemaError(
            "Palm Beach QuickSearch settings response is not structured JSON",
            url=QUICK_SETTINGS_URL,
        )
    records_per_page = _settings_int(
        payload,
        "recordsPerPage",
        "pageSize",
        "itemsPerPage",
    )
    maximum_records = _settings_int(
        payload,
        "maximumRecords",
        "maxRecords",
    )
    data_source = _text(_find_value(payload, "dataSource")) or ""
    selected_view = _text(
        _find_value(payload, "selectedDataSourceView", "dataSourceView")
    ) or ""
    auto_forward = _text(
        _find_value(payload, "autoForward", "autoForwardUrl", "forwardUrl")
    ) or ""
    if data_source.casefold() != "aumentumtax":
        raise SourceSchemaError(
            "Palm Beach QuickSearch data source is no longer AUMENTUMTAX",
            url=QUICK_SETTINGS_URL,
            details={"data_source": data_source},
        )
    if selected_view.casefold() != "quicksearch":
        raise SourceSchemaError(
            "Palm Beach QuickSearch selected view changed",
            url=QUICK_SETTINGS_URL,
            details={"selected_view": selected_view},
        )
    if "processing.aspx" not in auto_forward.casefold():
        raise SourceSchemaError(
            "Palm Beach QuickSearch account-forward route changed",
            url=QUICK_SETTINGS_URL,
            details={"auto_forward": auto_forward},
        )

    advanced_fields: list[str] = []
    for _path, item in _walk(payload):
        if isinstance(item, Mapping):
            candidate = _text(
                _direct_value(
                    item,
                    "columnName",
                    "fieldName",
                    "dataField",
                    "name",
                )
            )
            if candidate and _label_key(candidate) in {
                _label_key(value) for value in FIELD_QUALIFIERS.values()
            }:
                if candidate not in advanced_fields:
                    advanced_fields.append(candidate)
        elif isinstance(item, str):
            candidate_key = _label_key(item)
            if candidate_key in {
                _label_key(value) for value in FIELD_QUALIFIERS.values()
            } and item not in advanced_fields:
                advanced_fields.append(item)
    confidentiality_published = any(
        "confidential" in _label_key(path) or "confidential" in _label_key(item)
        for path, item in _walk(payload)
        if isinstance(item, (str, bool, int))
    )
    return SearchSettings(
        records_per_page=records_per_page,
        maximum_records=maximum_records,
        data_source=data_source,
        selected_view=selected_view,
        auto_forward=auto_forward,
        advanced_fields=tuple(sorted(advanced_fields, key=str.casefold)),
        confidentiality_published=confidentiality_published,
        response_schema_fingerprint=_response_schema(payload),
        raw=dict(payload) if isinstance(payload, Mapping) else {"items": payload},
    )


def _reported_total(payload: Any) -> int | None:
    raw = _find_value(
        payload,
        "TotalItems",
        "TotalRecords",
        "RecordCount",
        "TotalCount",
        "total",
    )
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def parse_search_page(
    payload: Any,
) -> tuple[tuple[Mapping[str, Any], ...], int]:
    if isinstance(payload, Mapping) and payload.get("error"):
        raise SourceResponseError(
            "Palm Beach QuickSearch returned an error payload",
            url=QUICK_SEARCH_URL,
            details={"response": dict(payload)},
        )
    candidates = _object_candidates(
        payload,
        required_keys=(
            "PrimaryKey",
            "AlternateKey",
            "ParcelID",
            "Owner",
            "Situs",
        ),
        minimum_matches=2,
    )
    records = tuple(item for _path, item in candidates)
    total = _reported_total(payload)
    if total is None:
        total = 0 if not records else len(records)
    if total < len(records):
        raise SourceSchemaError(
            "Palm Beach QuickSearch total is smaller than the returned page",
            url=QUICK_SEARCH_URL,
            details={"reported_total": total, "page_rows": len(records)},
        )
    return records, total


def _owner_values(record: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for raw in (
        _direct_value(record, "Owner"),
        _direct_value(record, "Owners"),
    ):
        candidates = raw if isinstance(raw, (list, tuple)) else [raw]
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                candidate = _direct_value(
                    candidate,
                    "Owner",
                    "Name",
                    "DisplayName",
                    "Value",
                )
            value = _text(candidate)
            if value and value not in values:
                values.append(value)
    return values


def _publisher_masked(value: Any) -> bool:
    if isinstance(value, Mapping):
        candidates = [
            item
            for item in value.values()
            if item not in (None, "")
        ]
        return bool(candidates) and all(
            _publisher_masked(item) for item in candidates
        )
    if isinstance(value, (list, tuple)):
        candidates = [item for item in value if item not in (None, "")]
        return bool(candidates) and all(
            _publisher_masked(item) for item in candidates
        )
    text = _text(value)
    return bool(text) and set(text) <= {"*"}


def _account_urls(pcn: str, alternate_key: str) -> dict[str, str]:
    parameters = urlencode({"p": pcn, "a": alternate_key})
    return {
        "processing": f"{PROCESSING_URL}?{parameters}",
        "account": f"{ACCOUNT_URL}?{parameters}",
    }


def normalize_search_result(
    record: Mapping[str, Any],
    *,
    criteria: str,
    native_page: int,
    native_row: int,
    settings: SearchSettings,
    source_reported_total: int,
) -> dict[str, Any]:
    primary_key = _text(
        _direct_value(record, "PrimaryKey", "PCN", "PropertyControlNumber")
    )
    parcel_id = _text(_direct_value(record, "ParcelID", "ParcelNumber"))
    pcn = normalize_pcn(primary_key or parcel_id)
    alternate_key = _text(_direct_value(record, "AlternateKey"))
    if not alternate_key:
        raise SourceSchemaError(
            "Palm Beach QuickSearch row lacks AlternateKey",
            url=QUICK_SEARCH_URL,
            details={"record": dict(record)},
        )
    confidential = _bool(_direct_value(record, "Confidential"))
    owners = _owner_values(record)
    masked_fields = [
        field
        for field, value in (
            ("owner", _direct_value(record, "Owner")),
            ("owners", _direct_value(record, "Owners")),
            ("delivery", _direct_value(record, "Delivery")),
            ("situs", _direct_value(record, "Situs")),
        )
        if _publisher_masked(value)
    ]
    occurrence_id = f"{pcn}:{alternate_key}"
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "tax-account-search-result",
            occurrence_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "tax_account_search_result",
        "source_occurrence_id": occurrence_id,
        "native_parcel_id": pcn,
        "formatted_pcn": format_pcn(pcn),
        "native_account_id": alternate_key,
        "parcel_join": {
            "field": "Property Control Number",
            "value": pcn,
            "normalization": "17_digits",
            "county_geoid": COUNTY_GEOID,
        },
        "account_locator": {
            "field": "AlternateKey",
            "value": alternate_key,
            "cross_source_parcel_identity": False,
        },
        "owners": [
            {
                "raw_name": value,
                "role": "tax_account_publisher_label",
                "masked": _publisher_masked(value),
            }
            for value in owners
        ],
        "situs_address": {
            "raw": _text(_direct_value(record, "Situs")),
            "city": _text(_direct_value(record, "City")),
            "state": _text(_direct_value(record, "State")),
            "postal_code": _text(_direct_value(record, "Zip")),
        },
        "mailing_address": {
            "raw": _text(_direct_value(record, "Delivery")),
            "city": _text(_direct_value(record, "City")),
            "state": _text(_direct_value(record, "State")),
            "postal_code": _text(_direct_value(record, "Zip")),
        },
        "paid_status": _text(_direct_value(record, "PaidStatus")),
        "publisher_redaction_state": {
            "confidential": confidential,
            "masked_fields": masked_fields,
            "masked_values_reconstructed": False,
        },
        "source_result_position": {
            "criteria": criteria,
            "native_page": native_page,
            "native_row": native_row,
            "records_per_page": settings.records_per_page,
            "source_reported_total": source_reported_total,
        },
        "source_urls": _account_urls(pcn, alternate_key),
        "source_url": SEARCH_PAGE_URL,
        "response_schema_fingerprint": schema_fingerprint(
            inferred_schema([record])
        ),
        "raw": dict(record),
    }


def _encode_cursor(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return f"{prefix}{encoded.rstrip('=')}"


def _decode_cursor(prefix: str, value: str) -> Mapping[str, Any]:
    if not value.startswith(prefix):
        raise PalmBeachTaxError(
            "cursor_invalid",
            "Continuation cursor belongs to another operation or source",
        )
    encoded = value[len(prefix) :]
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = json.loads(
            base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise PalmBeachTaxError(
            "cursor_invalid",
            "Continuation cursor is malformed",
        ) from error
    if not isinstance(decoded, Mapping) or decoded.get("version") != CURSOR_VERSION:
        raise PalmBeachTaxError(
            "cursor_invalid",
            "Continuation cursor version is unsupported",
        )
    return decoded


def _search_cursor(
    *,
    criteria_fingerprint: str,
    settings_fingerprint: str,
    next_offset: int,
    source_reported_total: int,
    source_effective_total: int,
) -> str:
    return _encode_cursor(
        SEARCH_CURSOR_PREFIX,
        {
            "version": CURSOR_VERSION,
            "criteria_fingerprint": criteria_fingerprint,
            "settings_fingerprint": settings_fingerprint,
            "next_offset": next_offset,
            "source_reported_total": source_reported_total,
            "source_effective_total": source_effective_total,
        },
    )


def _parse_search_cursor(
    value: str | None,
    *,
    criteria_fingerprint: str,
    settings_fingerprint: str,
) -> SearchCursor | None:
    if value is None:
        return None
    decoded = _decode_cursor(SEARCH_CURSOR_PREFIX, value)
    if decoded.get("criteria_fingerprint") != criteria_fingerprint:
        raise PalmBeachTaxError(
            "cursor_query_mismatch",
            "Continuation cursor was issued for different search criteria",
        )
    if decoded.get("settings_fingerprint") != settings_fingerprint:
        raise PalmBeachTaxError(
            "cursor_source_changed",
            "QuickSearch settings changed since the cursor was issued",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    try:
        parsed = SearchCursor(
            criteria_fingerprint=criteria_fingerprint,
            settings_fingerprint=settings_fingerprint,
            next_offset=int(decoded["next_offset"]),
            source_reported_total=int(decoded["source_reported_total"]),
            source_effective_total=int(decoded["source_effective_total"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PalmBeachTaxError(
            "cursor_invalid",
            "Continuation cursor lacks required search state",
        ) from error
    if parsed.next_offset < 0 or parsed.source_reported_total < 0:
        raise PalmBeachTaxError(
            "cursor_invalid",
            "Continuation cursor has invalid search offsets",
        )
    return parsed


class PalmBeachTaxClient(_BaseJSONClient):
    """Transport-injectable client for the verified Palm Beach tenant modules."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = 0.0,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        **kwargs: Any,
    ) -> None:
        if "transport" not in kwargs and "session" not in kwargs:
            kwargs["session"] = system_trust_session()
        super().__init__(
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
            **kwargs,
        )

    @staticmethod
    def _module_headers(
        module_id: int,
        *,
        tab_id: int = QUICK_SEARCH_TAB_ID,
    ) -> dict[str, str]:
        return {
            "moduleid": str(module_id),
            "tabid": str(tab_id),
            "Referer": SEARCH_PAGE_URL,
        }

    def fetch_search_settings(self) -> Any:
        return self._request_json(
            QUICK_SETTINGS_URL,
            params={"_m": QUICK_SEARCH_MODULE_ID},
            headers=self._module_headers(QUICK_SEARCH_MODULE_ID),
        )

    def fetch_search_page(self, criteria: str, page: int) -> Any:
        return self._request_json(
            QUICK_SEARCH_URL,
            params={
                "keywords": criteria,
                "page": page,
                "_m": QUICK_SEARCH_MODULE_ID,
            },
            headers=self._module_headers(QUICK_SEARCH_MODULE_ID),
        )

    def fetch_refresh(self, alternate_key: str) -> Any:
        return self._request_json(
            REFRESH_URL,
            params={"RevObjId": alternate_key, "_m": REFRESH_MODULE_ID},
            headers=self._module_headers(
                REFRESH_MODULE_ID,
                tab_id=PROCESSING_TAB_ID,
            ),
        )

    def fetch_sync_status(self) -> Any:
        return self._request_json(
            SYNC_STATUS_URL,
            params={"_m": REFRESH_MODULE_ID},
            headers=self._module_headers(
                REFRESH_MODULE_ID,
                tab_id=PROCESSING_TAB_ID,
            ),
        )

    def fetch_account_section(
        self,
        pcn: str,
        alternate_key: str,
        module_id: int,
    ) -> Any:
        if module_id not in ACCOUNT_MODULE_IDS:
            raise ValueError(f"unsupported account-summary module {module_id}")
        return self._request_json(
            ACCOUNT_SUMMARY_URL,
            params={"p": pcn, "a": alternate_key, "_m": module_id},
            headers=self._module_headers(module_id),
        )

    def fetch_bills(self, pcn: str, alternate_key: str) -> Any:
        return self._request_json(
            BILLS_URL,
            params={
                "p": pcn,
                "a": alternate_key,
                "_m": BILLS_MODULE_ID,
            },
            headers=self._module_headers(BILLS_MODULE_ID),
        )

    def fetch_payment_settings(self) -> Any:
        return self._request_json(
            PAYMENT_SETTINGS_URL,
            params={"_m": PAYMENT_HISTORY_MODULE_ID},
            headers=self._module_headers(PAYMENT_HISTORY_MODULE_ID),
        )

    def fetch_payment_page(
        self,
        pcn: str,
        alternate_key: str,
        *,
        items_per_page: int,
        page: int,
    ) -> Any:
        return self._request_json(
            PAYMENT_DATA_URL,
            params={
                "p": pcn,
                "a": alternate_key,
                "itemsPerPage": items_per_page,
                "page": page,
                "_m": PAYMENT_HISTORY_MODULE_ID,
            },
            headers=self._module_headers(PAYMENT_HISTORY_MODULE_ID),
        )

    def fetch_bill_detail_html(
        self,
        *,
        pcn: str,
        alternate_key: str,
        bill_id: str,
        tax_year: str,
        bill_type: str,
        bill_number: str,
    ) -> tuple[str, str]:
        parameters = {
            "p": pcn,
            "a": alternate_key,
            "b": bill_id,
            "y": tax_year,
            "t": bill_type,
            "n": bill_number,
        }
        url = f"{BILL_DETAIL_URL}?{urlencode(parameters)}"
        self._rate_limiter.wait()
        self.request_count += 1
        response = self.transport.request(
            "GET",
            url,
            params=None,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": self.user_agent,
                "Referer": ACCOUNT_URL,
            },
            timeout=self.timeout,
        )
        status_code = int(
            getattr(response, "status_code", getattr(response, "status", 0))
        )
        text = getattr(response, "text", "")
        body = text if isinstance(text, str) else str(text)
        if status_code == 429:
            raise RateLimitedHTTPError(
                status_code,
                url=url,
                response_text=body,
            )
        if status_code in {401, 403}:
            raise RestrictedHTTPError(
                status_code,
                url=url,
                response_text=body,
            )
        if status_code == 451:
            raise TermsBlockedHTTPError(
                status_code,
                url=url,
                response_text=body,
            )
        if status_code in {404, 410}:
            raise SourceChangedHTTPError(
                status_code,
                url=url,
                response_text=body,
            )
        if status_code < 200 or status_code >= 300:
            raise HTTPStatusError(
                status_code,
                url=url,
                response_text=body,
            )
        return body, url


def _qualified_criteria(query: str, field: str) -> str:
    value = _text(query)
    if not value:
        raise PalmBeachTaxError(
            "search_criteria_required",
            "Search criteria must not be blank",
        )
    if field == "simple":
        return value
    try:
        qualifier = FIELD_QUALIFIERS[field]
    except KeyError as error:
        raise PalmBeachTaxError(
            "search_field_unsupported",
            f"Unsupported Palm Beach Tax Collector search field: {field}",
        ) from error
    return f"{qualifier}:{value}"


def fetch_search_records(
    client: PalmBeachTaxClient,
    *,
    criteria: str,
    limit: int | None,
    cursor: str | None,
) -> SearchFetch:
    start_requests = client.request_count
    settings = parse_search_settings(client.fetch_search_settings())
    criteria_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "operation": "quick_search",
            "criteria": criteria,
        }
    )
    state = _parse_search_cursor(
        cursor,
        criteria_fingerprint=criteria_fingerprint,
        settings_fingerprint=settings.contract_fingerprint,
    )
    offset = state.next_offset if state else 0
    initial_total = state.source_reported_total if state else None
    effective_total = state.source_effective_total if state else None
    records: list[Mapping[str, Any]] = []
    pages_fetched = 0
    seen_pages: set[str] = set()

    while effective_total is None or offset < effective_total:
        page = offset // settings.records_per_page + 1
        within_page = offset % settings.records_per_page
        payload = client.fetch_search_page(criteria, page)
        pages_fetched += 1
        rows, reported_total = parse_search_page(payload)
        page_fingerprint = sha256_fingerprint(
            {"rows": list(rows), "total": reported_total}
        )
        if page_fingerprint in seen_pages:
            raise SourceSchemaError(
                "Palm Beach QuickSearch repeated a page during traversal",
                url=QUICK_SEARCH_URL,
                details={"page": page},
            )
        seen_pages.add(page_fingerprint)
        if initial_total is None:
            initial_total = reported_total
            effective_total = min(reported_total, settings.maximum_records)
        elif reported_total != initial_total:
            raise SourceSchemaError(
                "Palm Beach QuickSearch total changed during continuation",
                url=QUICK_SEARCH_URL,
                details={
                    "cursor_total": initial_total,
                    "observed_total": reported_total,
                },
            )
        if not rows:
            if offset < (effective_total or 0):
                raise SourceSchemaError(
                    "Palm Beach QuickSearch returned an empty page before its "
                    "reported boundary",
                    url=QUICK_SEARCH_URL,
                    details={"page": page, "offset": offset},
                )
            break
        if within_page >= len(rows):
            raise SourceSchemaError(
                "Palm Beach QuickSearch cursor points beyond a native page",
                url=QUICK_SEARCH_URL,
                details={
                    "page": page,
                    "within_page": within_page,
                    "page_rows": len(rows),
                },
            )
        for row_index, row in enumerate(rows[within_page:], start=within_page):
            if offset >= (effective_total or 0):
                break
            records.append(
                normalize_search_result(
                    row,
                    criteria=criteria,
                    native_page=page,
                    native_row=row_index + 1,
                    settings=settings,
                    source_reported_total=initial_total,
                )
            )
            offset += 1
            if limit is not None and len(records) >= limit:
                break
        if limit is not None and len(records) >= limit:
            break
        if len(rows) < settings.records_per_page:
            if offset < (effective_total or 0):
                raise SourceSchemaError(
                    "Palm Beach QuickSearch returned a short page before its "
                    "reported boundary",
                    url=QUICK_SEARCH_URL,
                    details={
                        "page": page,
                        "page_rows": len(rows),
                        "records_per_page": settings.records_per_page,
                        "offset": offset,
                        "effective_total": effective_total,
                    },
                )
            break

    source_reported_total = int(initial_total or 0)
    source_effective_total = int(effective_total or 0)
    next_cursor = None
    if offset < source_effective_total:
        next_cursor = _search_cursor(
            criteria_fingerprint=criteria_fingerprint,
            settings_fingerprint=settings.contract_fingerprint,
            next_offset=offset,
            source_reported_total=source_reported_total,
            source_effective_total=source_effective_total,
        )
    return SearchFetch(
        records=tuple(records),
        next_cursor=next_cursor,
        source_reported_total=source_reported_total,
        source_effective_total=source_effective_total,
        source_ceiling_reached=(
            source_reported_total >= settings.maximum_records
        ),
        pages_fetched=pages_fetched,
        requests_made=client.request_count - start_requests,
        settings=settings,
    )


def _resolve_account(
    client: PalmBeachTaxClient,
    *,
    pcn: str,
    alternate_key: str | None,
) -> tuple[str, str] | None:
    normalized_pcn = normalize_pcn(pcn)
    normalized_alternate = _text(alternate_key)
    if normalized_alternate:
        return normalized_pcn, normalized_alternate
    fetched = fetch_search_records(
        client,
        criteria=normalized_pcn,
        limit=None,
        cursor=None,
    )
    matches = {
        (
            _text(record.get("native_parcel_id")),
            _text(record.get("native_account_id")),
        )
        for record in fetched.records
        if _text(record.get("native_parcel_id")) == normalized_pcn
        and _text(record.get("native_account_id"))
    }
    if not matches:
        return None
    if len(matches) != 1:
        raise PalmBeachTaxError(
            "account_locator_ambiguous",
            "Exact PCN resolved to more than one Tax Collector account locator; "
            "provide --alternate-key",
            status=ResultStatus.HUMAN_REQUIRED,
            details={
                "pcn": normalized_pcn,
                "alternate_keys": sorted(
                    value for _pcn, value in matches if value
                ),
            },
        )
    resolved_pcn, resolved_alternate = next(iter(matches))
    return str(resolved_pcn), str(resolved_alternate)


def normalize_account(
    *,
    pcn: str,
    alternate_key: str,
    sections: Mapping[int, Any],
) -> dict[str, Any]:
    combined = {"modules": {str(key): value for key, value in sections.items()}}
    published_pcn = _find_value(
        combined,
        "PCN",
        "PropertyControlNumber",
        "PrimaryKey",
        "ParcelID",
    )
    if published_pcn:
        normalized_published = normalize_pcn(published_pcn)
        if normalized_published != pcn:
            raise SourceSchemaError(
                "Palm Beach account summary returned another PCN",
                url=ACCOUNT_SUMMARY_URL,
                details={"requested": pcn, "returned": normalized_published},
            )
    owner = _text(
        _find_value(
            combined,
            "OwnerOfRecord",
            "Owner",
            "PropertyOwner",
        )
    )
    second_owner = _text(
        _find_value(
            combined,
            "SecondOwner",
            "Owner2",
            "AdditionalOwner",
        )
    )
    confidential = _bool(_find_value(combined, "Confidential"))
    source_last_updated = _text(
        _find_value(combined, "lastUpdated", "sourceLastUpdated")
    )
    occurrence_id = f"{pcn}:{alternate_key}"
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "tax-account",
            occurrence_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "property_tax_account_snapshot",
        "source_occurrence_id": occurrence_id,
        "native_parcel_id": pcn,
        "formatted_pcn": format_pcn(pcn),
        "native_account_id": alternate_key,
        "parcel_join": {
            "field": "Property Control Number",
            "value": pcn,
            "normalization": "17_digits",
            "county_geoid": COUNTY_GEOID,
        },
        "account_locator": {
            "field": "AlternateKey",
            "value": alternate_key,
            "cross_source_parcel_identity": False,
        },
        "owners": [
            {
                "raw_name": value,
                "role": "tax_account_publisher_label",
                "masked": _publisher_masked(value),
            }
            for value in (owner, second_owner)
            if value
        ],
        "property_type": _text(_find_value(combined, "PropertyType")),
        "property_address": {
            "raw": _text(
                _find_value(
                    combined,
                    "PropertyAddress",
                    "Situs",
                    "SitusAddress",
                )
            )
        },
        "mailing_address": {
            "raw": _text(_find_value(combined, "MailingAddress", "Delivery")),
            "city": _text(_find_value(combined, "MailingCity", "City")),
            "state": _text(_find_value(combined, "MailingState", "State")),
            "postal_code": _text(
                _find_value(combined, "MailingZip", "Zip", "PostalCode")
            ),
        },
        "account_status": _text(
            _find_value(combined, "Status", "AccountStatus", "PaidStatus")
        ),
        "legal_description": _text(
            _find_value(combined, "LegalDescription", "Legal")
        ),
        "source_last_updated": source_last_updated,
        "snapshot_semantics": {
            "retrieved_state_observation": True,
            "last_updated_is_source_freshness": bool(source_last_updated),
            "last_updated_is_property_event_date": False,
        },
        "publisher_redaction_state": {
            "confidential": confidential,
            "masked_values_reconstructed": False,
        },
        "source_urls": _account_urls(pcn, alternate_key),
        "source_url": _account_urls(pcn, alternate_key)["account"],
        "response_schema_fingerprint": _response_schema(combined),
        "raw_sections": combined["modules"],
    }


def _bill_candidates(payload: Any) -> list[tuple[str, Mapping[str, Any]]]:
    return _object_candidates(
        payload,
        required_keys=(
            "TaxYear",
            "BillId",
            "BillNumber",
            "BillType",
            "Installment",
            "DueDate",
            "AmountDue",
            "PaidAmount",
        ),
        minimum_matches=2,
    )


def _publisher_messages(record: Mapping[str, Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for path, value in _walk(record):
        if not isinstance(value, str):
            continue
        final_key = _label_key(path.rsplit(".", 1)[-1])
        if any(
            token in final_key
            for token in ("message", "flag", "warning", "notice")
        ):
            text = _text(value)
            if text and {"path": path, "text": text} not in messages:
                messages.append({"path": path, "text": text})
    return messages


def _payment_capability(record: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in record.items():
        normalized = _label_key(key)
        if any(
            token in normalized
            for token in ("pay", "online", "selectable", "disabled")
        ):
            values[str(key)] = value
    return values


def normalize_bill(
    record: Mapping[str, Any],
    *,
    pcn: str,
    alternate_key: str,
    source_path: str,
    ordinal: int,
) -> dict[str, Any]:
    tax_year = _text(_direct_value(record, "TaxYear", "Year"))
    bill_id = _text(
        _direct_value(record, "BillId", "BillID", "InternalBillId")
    )
    bill_number = _text(_direct_value(record, "BillNumber", "BillNo"))
    installment = _text(
        _direct_value(record, "Installment", "InstallmentNumber")
    )
    bill_type = _text(_direct_value(record, "BillType", "Type"))
    roll = _text(_direct_value(record, "Roll", "RollType"))
    if bill_id:
        occurrence_id = f"{pcn}:bill-id:{bill_id}"
    else:
        occurrence_id = (
            f"{pcn}:bill:{tax_year or ''}:{bill_number or ''}:"
            f"{installment or ''}:{ordinal}:{sha256_fingerprint(record)[:12]}"
        )
    bill_detail = _text(
        _direct_value(
            record,
            "BillDetailUrl",
            "BillDetailURL",
            "DetailUrl",
            "Url",
        )
    )
    if bill_detail:
        bill_detail = urljoin(PORTAL_ROOT, bill_detail)
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "tax-bill",
            occurrence_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "property_tax_bill_snapshot",
        "source_occurrence_id": occurrence_id,
        "native_parcel_id": pcn,
        "formatted_pcn": format_pcn(pcn),
        "native_account_id": alternate_key,
        "native_ids": {
            "bill_id": bill_id,
            "bill_number": bill_number,
            "installment": installment,
            "tax_year": tax_year,
        },
        "tax_year": tax_year,
        "bill_number": bill_number,
        "bill_id": bill_id,
        "bill_type": bill_type,
        "roll": roll,
        "installment": installment,
        "due_date": _text(_direct_value(record, "DueDate")),
        "amount_due_as_of": _text(
            _direct_value(record, "AmountDueDate", "DueAsOfDate", "AsOfDate")
        ),
        "amounts": {
            "net_tax": _money(_direct_value(record, "NetTax")),
            "interest": _money(_direct_value(record, "Interest")),
            "penalty": _money(_direct_value(record, "Penalty")),
            "fees": _money(_direct_value(record, "Fees", "Fee")),
            "discount": _money(
                _direct_value(record, "Discount", "Discounts")
            ),
            "amount_due": _money(
                _direct_value(record, "AmountDue", "TotalDue")
            ),
            "paid_amount": _money(
                _direct_value(record, "PaidAmount", "AmountPaid")
            ),
        },
        "status": _text(
            _direct_value(record, "Status", "BillStatus", "PaidStatus")
        ),
        "payment_capability": _payment_capability(record),
        "publisher_messages": _publisher_messages(record),
        "snapshot_semantics": {
            "amounts_are_retrieved_state": True,
            "due_date_is_publisher_date": True,
            "amount_due_as_of_is_publisher_label": True,
            "online_payment_operation_implemented": False,
        },
        "bill_detail_url": bill_detail,
        "source_path": source_path,
        "source_url": _account_urls(pcn, alternate_key)["account"],
        "response_schema_fingerprint": schema_fingerprint(
            inferred_schema([record])
        ),
        "raw": dict(record),
    }


def normalize_bills(
    payload: Any,
    *,
    pcn: str,
    alternate_key: str,
    tax_year: str | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for ordinal, (path, record) in enumerate(_bill_candidates(payload), start=1):
        value = normalize_bill(
            record,
            pcn=pcn,
            alternate_key=alternate_key,
            source_path=path,
            ordinal=ordinal,
        )
        if tax_year and value.get("tax_year") != tax_year:
            continue
        normalized.append(value)
    return normalized


def _payment_rows(payload: Any) -> list[tuple[str, Mapping[str, Any]]]:
    return _object_candidates(
        payload,
        required_keys=(
            "TaxYear",
            "BillNumber",
            "EffPayDate",
            "PaidByNameConf",
            "ReceiptNumber",
            "ReceiptAmount",
        ),
        minimum_matches=3,
    )


def normalize_payment(
    record: Mapping[str, Any],
    *,
    pcn: str,
    alternate_key: str,
    native_page: int,
    native_row: int,
) -> dict[str, Any]:
    tax_year = _text(_direct_value(record, "TaxYear"))
    bill_number = _text(_direct_value(record, "BillNumber", "BillNo"))
    effective_date = _text(
        _direct_value(record, "EffPayDate", "EffectivePaymentDate")
    )
    receipt_number = _text(
        _direct_value(record, "ReceiptNumber", "ReceiptNo")
    )
    payer = _text(
        _direct_value(record, "PaidByNameConf", "PaidBy", "Payer")
    )
    occurrence_id = (
        f"{pcn}:payment:{receipt_number or ''}:{bill_number or ''}:"
        f"{effective_date or ''}:{sha256_fingerprint(record)[:12]}"
    )
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "tax-payment",
            occurrence_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "property_tax_payment",
        "source_occurrence_id": occurrence_id,
        "native_parcel_id": pcn,
        "formatted_pcn": format_pcn(pcn),
        "native_account_id": alternate_key,
        "native_ids": {
            "receipt_number": receipt_number,
            "bill_number": bill_number,
            "tax_year": tax_year,
        },
        "tax_year": tax_year,
        "bill_number": bill_number,
        "effective_payment_date": effective_date,
        "receipt_number": receipt_number,
        "receipt_amount": _money(
            _direct_value(record, "ReceiptAmount", "Amount")
        ),
        "payer_observation": {
            "raw_name": payer,
            "role": "source_observed_payer",
            "owner_or_title_role": False,
            "masked": _publisher_masked(payer),
        },
        "source_result_position": {
            "native_page": native_page,
            "native_row": native_row,
        },
        "source_url": _account_urls(pcn, alternate_key)["account"],
        "response_schema_fingerprint": schema_fingerprint(
            inferred_schema([record])
        ),
        "raw": dict(record),
    }


def _payment_page_size(settings: Any) -> int:
    raw = _find_value(settings, "itemsPerPage", "recordsPerPage", "pageSize")
    if raw is not None and not isinstance(raw, bool):
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            parsed = 0
        if parsed > 0:
            return parsed
    return OBSERVED_PAYMENT_PAGE_SIZE


def _payment_cursor(
    *,
    criteria_fingerprint: str,
    settings_fingerprint: str,
    next_offset: int,
    source_reported_total: int | None,
) -> str:
    return _encode_cursor(
        PAYMENT_CURSOR_PREFIX,
        {
            "version": CURSOR_VERSION,
            "criteria_fingerprint": criteria_fingerprint,
            "settings_fingerprint": settings_fingerprint,
            "next_offset": next_offset,
            "source_reported_total": source_reported_total,
        },
    )


def fetch_payment_records(
    client: PalmBeachTaxClient,
    *,
    pcn: str,
    alternate_key: str,
    tax_year: str | None,
    limit: int | None,
    cursor: str | None,
) -> PaymentFetch:
    start_requests = client.request_count
    settings = client.fetch_payment_settings()
    settings_schema_fingerprint = _response_schema(settings)
    native_page_size = _payment_page_size(settings)
    criteria_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "operation": "payment_history",
            "pcn": pcn,
            "alternate_key": alternate_key,
            "tax_year": tax_year,
        }
    )
    offset = 0
    cursor_total: int | None = None
    if cursor:
        decoded = _decode_cursor(PAYMENT_CURSOR_PREFIX, cursor)
        if decoded.get("criteria_fingerprint") != criteria_fingerprint:
            raise PalmBeachTaxError(
                "cursor_query_mismatch",
                "Payment cursor was issued for different account criteria",
            )
        if decoded.get("settings_fingerprint") != settings_schema_fingerprint:
            raise PalmBeachTaxError(
                "cursor_source_changed",
                "Payment-history settings changed since the cursor was issued",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
            )
        try:
            offset = int(decoded["next_offset"])
            cursor_total_raw = decoded.get("source_reported_total")
            cursor_total = (
                int(cursor_total_raw) if cursor_total_raw is not None else None
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PalmBeachTaxError(
                "cursor_invalid",
                "Payment cursor lacks required traversal state",
            ) from error
        if offset < 0:
            raise PalmBeachTaxError(
                "cursor_invalid",
                "Payment cursor has an invalid offset",
            )

    records: list[Mapping[str, Any]] = []
    pages_fetched = 0
    total = cursor_total
    source_has_more = True
    seen_pages: set[str] = set()
    while source_has_more and (total is None or offset < total):
        page = offset // native_page_size + 1
        within_page = offset % native_page_size
        payload = client.fetch_payment_page(
            pcn,
            alternate_key,
            items_per_page=native_page_size,
            page=page,
        )
        pages_fetched += 1
        rows_with_paths = _payment_rows(payload)
        rows = [record for _path, record in rows_with_paths]
        observed_total = _reported_total(payload)
        page_fingerprint = sha256_fingerprint(
            {"rows": rows, "total": observed_total}
        )
        if page_fingerprint in seen_pages:
            raise SourceSchemaError(
                "Palm Beach payment history repeated a native page",
                url=PAYMENT_DATA_URL,
                details={"page": page},
            )
        seen_pages.add(page_fingerprint)
        if observed_total is not None:
            if total is None:
                total = observed_total
            elif total != observed_total:
                raise SourceSchemaError(
                    "Palm Beach payment-history total changed during continuation",
                    url=PAYMENT_DATA_URL,
                    details={
                        "cursor_total": total,
                        "observed_total": observed_total,
                    },
                )
        if not rows:
            if total is not None and offset < total:
                raise SourceSchemaError(
                    "Palm Beach payment history returned an empty page before "
                    "its reported total",
                    url=PAYMENT_DATA_URL,
                    details={"page": page, "offset": offset, "total": total},
                )
            source_has_more = False
            break
        if within_page >= len(rows):
            raise SourceSchemaError(
                "Palm Beach payment cursor points beyond a native page",
                url=PAYMENT_DATA_URL,
                details={
                    "page": page,
                    "within_page": within_page,
                    "page_rows": len(rows),
                },
            )
        for row_index, row in enumerate(rows[within_page:], start=within_page):
            payment = normalize_payment(
                row,
                pcn=pcn,
                alternate_key=alternate_key,
                native_page=page,
                native_row=row_index + 1,
            )
            offset += 1
            if tax_year and payment.get("tax_year") != tax_year:
                continue
            records.append(payment)
            if limit is not None and len(records) >= limit:
                break
        source_has_more = (
            (total is not None and offset < total)
            or (total is None and len(rows) >= native_page_size)
        )
        if limit is not None and len(records) >= limit:
            break
        if total is None and len(rows) < native_page_size:
            source_has_more = False

    next_cursor = None
    if source_has_more:
        next_cursor = _payment_cursor(
            criteria_fingerprint=criteria_fingerprint,
            settings_fingerprint=settings_schema_fingerprint,
            next_offset=offset,
            source_reported_total=total,
        )
    return PaymentFetch(
        records=tuple(records),
        next_cursor=next_cursor,
        source_reported_total=total,
        pages_fetched=pages_fetched,
        requests_made=client.request_count - start_requests,
        settings_schema_fingerprint=settings_schema_fingerprint,
        native_page_size=native_page_size,
    )


class _BillDetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.links: list[dict[str, str | None]] = []
        self._in_title = False
        self._in_heading = False
        self._anchor: dict[str, str | None] | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized = tag.casefold()
        attributes = {key.casefold(): value for key, value in attrs}
        if normalized == "title":
            self._in_title = True
        elif normalized in {"h1", "h2"} and not self.heading_parts:
            self._in_heading = True
        elif normalized == "a" and attributes.get("href"):
            self._anchor = {
                "href": attributes.get("href"),
                "title": attributes.get("title"),
            }
            self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized == "title":
            self._in_title = False
        elif normalized in {"h1", "h2"}:
            self._in_heading = False
        elif normalized == "a" and self._anchor is not None:
            self._anchor["text"] = _text(" ".join(self._anchor_text))
            self.links.append(self._anchor)
            self._anchor = None
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_heading:
            self.heading_parts.append(data)
        if self._anchor is not None:
            self._anchor_text.append(data)


def parse_bill_detail_html(
    html: str,
    *,
    url: str,
    pcn: str,
    alternate_key: str,
    bill_id: str,
    tax_year: str,
    bill_number: str,
) -> dict[str, Any]:
    parser = _BillDetailParser()
    parser.feed(html)
    module_ids = sorted(
        {
            int(value)
            for pattern in (
                r"(?:moduleId|moduleid|data-module-id|_m)[=:'\"\s]+(\d+)",
                r"dnn_ctr(\d+)_",
            )
            for value in re.findall(pattern, html, flags=re.I)
        }
    )
    documents: list[dict[str, Any]] = []
    for link in parser.links:
        href = _text(link.get("href"))
        if not href:
            continue
        resolved = urljoin(url, href)
        label = _text(link.get("text") or link.get("title"))
        searchable = f"{href} {label or ''}".casefold()
        if not any(
            token in searchable
            for token in ("download", ".pdf", "print", "tax bill", "billdetail")
        ):
            continue
        entry = {
            "url": resolved,
            "label": label,
            "media_type": (
                "application/pdf"
                if ".pdf" in resolved.casefold()
                else "source_managed"
            ),
            "availability": "linked_by_bill_detail_page",
        }
        if entry not in documents:
            documents.append(entry)
    occurrence_id = f"{pcn}:bill-id:{bill_id}"
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "tax-bill-detail",
            occurrence_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "property_tax_bill_detail_metadata",
        "source_occurrence_id": occurrence_id,
        "native_parcel_id": pcn,
        "native_account_id": alternate_key,
        "native_ids": {
            "bill_id": bill_id,
            "bill_number": bill_number,
            "tax_year": tax_year,
        },
        "page_title": _text(" ".join(parser.title_parts)),
        "page_heading": _text(" ".join(parser.heading_parts)),
        "published_module_ids": module_ids,
        "documents": documents,
        "source_url": url,
        "page_sha256": sha256_fingerprint({"html": html}),
        "bill_detail_semantics": {
            "module_ids_discovered_from_page": True,
            "module_ids_are_tenant_page_configuration": True,
            "module_ids_are_universal_aumentum_constants": False,
            "payment_submission_implemented": False,
        },
    }


def source_routes() -> dict[str, Any]:
    """Return official field-specific complements without merging provenance."""

    return {
        "record_kind": "source_routes",
        "source_id": SOURCE_ID,
        "primary": {
            "official_guidance": OFFICIAL_GUIDANCE_URL,
            "portal": SEARCH_PAGE_URL,
            "adds": [
                "tax_account",
                "bill_and_installment_state",
                "delinquency_and_source_flags",
                "payment_history",
            ],
        },
        "complementary_routes": [
            {
                "source_id": PROPERTY_APPRAISER_SOURCE_ID,
                "url": (
                    "https://gis.pbcgov.org/arcgis/rest/services/"
                    "Parcels/PARCEL_INFO/FeatureServer/4"
                ),
                "adds": [
                    "assessment_roll_names",
                    "situs_and_mailing_addresses",
                    "assessed_and_market_values",
                    "legal_description",
                    "parcel_geometry",
                ],
                "does_not_replace": [
                    "tax_balance",
                    "bill",
                    "payment_history",
                    "recorded_title",
                ],
                "join_keys": ["17_digit_pcn"],
            },
            {
                "source_id": OFFICIAL_RECORDS_SOURCE_ID,
                "url": "https://erec.mypalmbeachclerk.com/",
                "adds": [
                    "recorded_instrument_index",
                    "deed_and_mortgage_parties",
                    "recorded_document_representation",
                ],
                "does_not_replace": ["current_tax_account_state"],
                "join_keys": ["pcn", "book_page", "party_name"],
            },
            {
                "source_id": TAX_DEEDS_SOURCE_ID,
                "url": "https://taxdeed.mypalmbeachclerk.com/",
                "adds": [
                    "tax_certificate",
                    "tax_deed_case",
                    "auction_event_and_status",
                    "opening_and_high_bid",
                    "legal_notices_and_case_documents",
                ],
                "does_not_replace": [
                    "ordinary_tax_bill",
                    "recorded_title_conclusion",
                ],
                "join_keys": [
                    "17_digit_pcn",
                    "tax_deed_case_number",
                    "certificate_number",
                ],
            },
            {
                "source_id": FL_DOR_SOURCE_ID,
                "adds": ["statewide_property_roll_bulk"],
                "does_not_replace": [
                    "live_tax_account_balance",
                    "payment_history",
                    "recorded_instrument",
                ],
                "join_keys": ["county", "parcel_number"],
            },
        ],
    }


def _settings_record(settings: SearchSettings) -> dict[str, Any]:
    return {
        "record_kind": "source_settings",
        "source_id": SOURCE_ID,
        "stable_contract": settings.stable_contract(),
        "source_search_boundary": {
            "maximum_records": settings.maximum_records,
            "meaning": (
                "publisher-configured maximum matching records returned by "
                "QuickSearch"
            ),
            "authoritative_population_total_when_equal": False,
            "adapter_selected_cap": False,
        },
        "raw": dict(settings.raw),
    }


def _sync_status_record(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "Palm Beach Aumentum sync-status response is not an object",
            url=SYNC_STATUS_URL,
            details={"response_type": type(payload).__name__},
        )
    filter_value = payload.get("filter")
    if not isinstance(filter_value, Mapping):
        raise SourceSchemaError(
            "Palm Beach Aumentum sync-status response lacks its filter contract",
            url=SYNC_STATUS_URL,
        )
    field_name = _text(_direct_value(filter_value, "fieldName"))
    parameter_name = _text(_direct_value(filter_value, "paramName"))
    navigate_to_url = _text(_direct_value(payload, "navigateToUrl"))
    if (
        field_name != "RevObjId"
        or parameter_name != "a"
        or not navigate_to_url
        or "account.aspx" not in navigate_to_url.casefold()
    ):
        raise SourceSchemaError(
            "Palm Beach Aumentum account-refresh routing contract changed",
            url=SYNC_STATUS_URL,
            details={
                "field_name": field_name,
                "parameter_name": parameter_name,
                "navigate_to_url": navigate_to_url,
            },
        )
    return {
        "record_kind": "account_refresh_contract",
        "source_id": SOURCE_ID,
        "module_id": REFRESH_MODULE_ID,
        "tab_id": PROCESSING_TAB_ID,
        "active": _bool(_direct_value(payload, "isActive")),
        "administrator_context": _bool(_direct_value(payload, "isAdmin")),
        "navigate_to_url": urljoin(PORTAL_ROOT, navigate_to_url),
        "loading_message": _text(_direct_value(payload, "loadingMessage")),
        "refresh_selector": {
            "field_name": field_name,
            "parameter_name": parameter_name,
        },
        "semantics": {
            "settings_and_routing_metadata": True,
            "per_account_completion_poll": False,
            "refresh_operation": "one_shot_FetchData_by_AlternateKey",
        },
        "source_url": SYNC_STATUS_URL,
        "response_schema_fingerprint": _response_schema(payload),
        "raw": dict(payload),
    }


def _probe_record(
    client: PalmBeachTaxClient,
    settings: SearchSettings,
    sync_status: Mapping[str, Any],
) -> dict[str, Any]:
    payload = client.fetch_search_page(SENTINEL_PCN, 1)
    rows, total = parse_search_page(payload)
    samples = [
        normalize_search_result(
            row,
            criteria=SENTINEL_PCN,
            native_page=1,
            native_row=index,
            settings=settings,
            source_reported_total=total,
        )
        for index, row in enumerate(rows[:1], start=1)
    ]
    return {
        "record_kind": "source_probe",
        "source_id": SOURCE_ID,
        "stable_contract": {
            **settings.stable_contract(),
            "quick_search_url": QUICK_SEARCH_URL,
            "account_summary_modules": list(ACCOUNT_MODULE_IDS),
            "bill_module": BILLS_MODULE_ID,
            "payment_history_module": PAYMENT_HISTORY_MODULE_ID,
            "account_refresh_contract": {
                "module_id": sync_status.get("module_id"),
                "tab_id": sync_status.get("tab_id"),
                "navigate_to_url": sync_status.get("navigate_to_url"),
                "refresh_selector": sync_status.get("refresh_selector"),
                "per_account_completion_poll": False,
            },
            "identity": {
                "parcel_join": "17_digit_pcn",
                "account_locator": "AlternateKey",
                "bill_and_payment_identities_separate": True,
            },
        },
        "rolling_observation": {
            "sentinel_pcn": SENTINEL_PCN,
            "source_reported_total": total,
            "sample": samples[0] if samples else None,
        },
        "source_ceiling_semantics": {
            "maximum_records": settings.maximum_records,
            "equal_total_means_partial_boundary": True,
        },
        "routes": source_routes(),
    }


def _access_contract(args: argparse.Namespace) -> Mapping[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> PalmBeachTaxClient:
    limits = access_contract.get("limits") or {}
    minimum_interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return PalmBeachTaxClient(
        timeout=args.timeout,
        minimum_interval=minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "catalog_db",
        "catalog_config",
        "output",
        "json_out",
        "timeout",
        "minimum_interval",
        "retry_attempts",
    }
    return {
        key: value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _partial_search_result(
    query: PublicRecordsQuery,
    fetched: SearchFetch,
) -> PublicRecordsResult:
    error = PublicRecordsError(
        code="source_search_ceiling_reached",
        message=(
            "Palm Beach QuickSearch reached its publisher-configured "
            f"{fetched.settings.maximum_records}-record boundary; additional "
            "matching accounts may exist"
        ),
        category="source_completeness",
        retryable=False,
        details={
            "source_reported_total": fetched.source_reported_total,
            "source_effective_total": fetched.source_effective_total,
            "publisher_maximum_records": fetched.settings.maximum_records,
            "adapter_selected_cap": False,
        },
    )
    return PublicRecordsResult.failure(
        query,
        ResultStatus.PARTIAL,
        [error],
        records=fetched.records,
        next_cursor=fetched.next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    client: PalmBeachTaxClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one catalog-aware Palm Beach Tax Collector query."""

    query = build_query(args)
    try:
        decision = (
            access_contract if access_contract is not None else _access_contract(args)
        )
        active_client = client or _client(args, decision)
        if args.command in {"settings", "sync-status", "discovery", "probe"}:
            settings = parse_search_settings(
                active_client.fetch_search_settings()
            )
            if args.command == "settings":
                records = [_settings_record(settings)]
            elif args.command == "sync-status":
                records = [
                    _sync_status_record(active_client.fetch_sync_status())
                ]
            elif args.command == "discovery":
                records = [
                    _settings_record(settings),
                    _sync_status_record(active_client.fetch_sync_status()),
                    source_routes(),
                ]
            else:
                records = [
                    _probe_record(
                        active_client,
                        settings,
                        _sync_status_record(active_client.fetch_sync_status()),
                    )
                ]
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command in {"search", "owner", "address", "parcel"}:
            if args.command == "parcel":
                criteria = normalize_pcn(args.query)
            else:
                field = (
                    "owner"
                    if args.command == "owner"
                    else "situs"
                    if args.command == "address"
                    else args.field
                )
                criteria = _qualified_criteria(args.query, field)
            fetched = fetch_search_records(
                active_client,
                criteria=criteria,
                limit=args.limit,
                cursor=args.cursor,
            )
            if fetched.source_ceiling_reached:
                result = _partial_search_result(query, fetched)
            else:
                result = PublicRecordsResult.success(
                    query,
                    fetched.records,
                    next_cursor=fetched.next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
        else:
            resolved = _resolve_account(
                active_client,
                pcn=args.pcn,
                alternate_key=args.alternate_key,
            )
            if resolved is None:
                result = PublicRecordsResult.success(
                    query,
                    [],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                pcn, alternate_key = resolved
                if args.command == "refresh":
                    payload = active_client.fetch_refresh(alternate_key)
                    records = [
                        {
                            "record_kind": "tax_account_refresh_state",
                            "source_id": SOURCE_ID,
                            "native_parcel_id": pcn,
                            "native_account_id": alternate_key,
                            "publisher_status": _text(
                                _find_value(
                                    payload,
                                    "Status",
                                    "State",
                                    "Message",
                                )
                            ),
                            "source_url": (
                                f"{REFRESH_URL}?"
                                + urlencode(
                                    {
                                        "RevObjId": alternate_key,
                                        "_m": REFRESH_MODULE_ID,
                                    }
                                )
                            ),
                            "response_schema_fingerprint": _response_schema(
                                payload
                            ),
                            "raw": payload,
                        }
                    ]
                elif args.command == "account":
                    sections = {
                        module_id: active_client.fetch_account_section(
                            pcn,
                            alternate_key,
                            module_id,
                        )
                        for module_id in ACCOUNT_MODULE_IDS
                    }
                    records = [
                        normalize_account(
                            pcn=pcn,
                            alternate_key=alternate_key,
                            sections=sections,
                        )
                    ]
                elif args.command == "bills":
                    payload = active_client.fetch_bills(pcn, alternate_key)
                    records = normalize_bills(
                        payload,
                        pcn=pcn,
                        alternate_key=alternate_key,
                        tax_year=(
                            str(args.tax_year) if args.tax_year is not None else None
                        ),
                    )
                elif args.command == "payments":
                    fetched_payments = fetch_payment_records(
                        active_client,
                        pcn=pcn,
                        alternate_key=alternate_key,
                        tax_year=(
                            str(args.tax_year) if args.tax_year is not None else None
                        ),
                        limit=args.limit,
                        cursor=args.cursor,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        fetched_payments.records,
                        next_cursor=fetched_payments.next_cursor,
                        warnings=SOURCE_WARNINGS,
                    )
                    records = None
                elif args.command == "bill-detail":
                    html, url = active_client.fetch_bill_detail_html(
                        pcn=pcn,
                        alternate_key=alternate_key,
                        bill_id=args.bill_id,
                        tax_year=str(args.tax_year),
                        bill_type=args.bill_type,
                        bill_number=args.bill_number,
                    )
                    records = [
                        parse_bill_detail_html(
                            html,
                            url=url,
                            pcn=pcn,
                            alternate_key=alternate_key,
                            bill_id=args.bill_id,
                            tax_year=str(args.tax_year),
                            bill_number=args.bill_number,
                        )
                    ]
                else:
                    raise PalmBeachTaxError(
                        "operation_unsupported",
                        f"Unsupported Palm Beach Tax Collector operation: "
                        f"{args.command}",
                    )
                if records is not None:
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        warnings=SOURCE_WARNINGS,
                    )
    except AcquisitionUnavailableError as error:
        decision = error.decision
        result = PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code")
                        or "machine_acquisition_denied"
                    ),
                    message=str(error),
                    category="access_policy",
                    retryable=False,
                    details=decision,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    except PalmBeachTaxError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="palm_beach_tax_normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )

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
        try:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
        except Exception as error:  # pragma: no cover - external logging
            print(f"WARNING: search logging failed: {error}", file=sys.stderr)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Palm Beach Tax Collector {args.command} ({result.status.value})",
    ):
        return
    print(
        f"Palm Beach Tax Collector {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("formatted_pcn")
            or record.get("source_occurrence_id")
            or record.get("record_kind")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime_arguments(
    parser: argparse.ArgumentParser,
    *,
    paginated: bool = False,
) -> None:
    if paginated:
        parser.add_argument(
            "--limit",
            type=_positive_int,
            help=(
                "Optional caller-selected return bound; omitted traverses the "
                "source-published result window"
            ),
        )
        parser.add_argument(
            "--cursor",
            help="Query- and settings-bound continuation cursor",
        )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=0.0,
        help="Optional caller-selected minimum seconds between requests",
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    parser.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB_PATH))
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
    )
    add_output_args(parser)


def _add_account_selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pcn", help="17-digit Property Control Number")
    parser.add_argument(
        "--alternate-key",
        help=(
            "Exact Tax Collector AlternateKey; omitted resolves it through "
            "an exact PCN QuickSearch"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Palm Beach County Constitutional Tax Collector property-tax "
            "accounts, bills, and payment history"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("settings", "sync-status", "discovery", "probe"):
        command_parser = subparsers.add_parser(command)
        _add_runtime_arguments(command_parser)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument(
        "--field",
        choices=("simple", *FIELD_QUALIFIERS),
        default="simple",
    )
    _add_runtime_arguments(search_parser, paginated=True)

    for command in ("owner", "address", "parcel"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("query")
        _add_runtime_arguments(command_parser, paginated=True)

    for command in ("account", "refresh", "bills"):
        command_parser = subparsers.add_parser(command)
        _add_account_selector(command_parser)
        if command == "bills":
            command_parser.add_argument("--tax-year", type=_positive_int)
        _add_runtime_arguments(command_parser)

    payments_parser = subparsers.add_parser("payments")
    _add_account_selector(payments_parser)
    payments_parser.add_argument("--tax-year", type=_positive_int)
    _add_runtime_arguments(payments_parser, paginated=True)

    detail_parser = subparsers.add_parser("bill-detail")
    _add_account_selector(detail_parser)
    detail_parser.add_argument("bill_id")
    detail_parser.add_argument("--tax-year", type=_positive_int, required=True)
    detail_parser.add_argument("--bill-number", required=True)
    detail_parser.add_argument("--bill-type", default="Real Property")
    _add_runtime_arguments(detail_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
