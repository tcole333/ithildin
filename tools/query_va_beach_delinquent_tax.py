#!/usr/bin/env python3
"""Query Virginia Beach's daily delinquent real-estate tax table.

The City Treasurer publishes one row per delinquent bill installment through a
public ArcGIS FeatureServer table. Records include the primary published owner,
mailing and situs addresses, GPIN, legal description, tax year, bill number,
installment, and the tax, penalty, interest, fee, and total balances.

Virginia tax collection is administered by local treasurers. This adapter
covers Virginia Beach and exposes related official routes for assessment,
detailed account history, land records and judgments, court cases, and tax-sale
notices.

Examples:
    uv run python tools/query_va_beach_delinquent_tax.py owner "EXAMPLE LLC"
    uv run python tools/query_va_beach_delinquent_tax.py parcel 14469645070000
    uv run python tools/query_va_beach_delinquent_tax.py address "SHERRY AVE"
    uv run python tools/query_va_beach_delinquent_tax.py bill 1125000027
    uv run python tools/query_va_beach_delinquent_tax.py search \
        --tax-year 2025 --min-total-due 1000
    uv run python tools/query_va_beach_delinquent_tax.py probe \
        --output /tmp/va-beach-tax-probe.json
    uv run python tools/query_va_beach_delinquent_tax.py routes --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

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
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        ArcGISRESTClient,
        PaginationError,
        PublicRecordsHTTPError,
        SourceResponseError,
        SourceSchemaError,
        arcgis_declared_schema,
        failure_result,
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
        sha256_fingerprint,
    )
    from public_records_http import (
        ArcGISRESTClient,
        PaginationError,
        PublicRecordsHTTPError,
        SourceResponseError,
        SourceSchemaError,
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-va-virginia-beach-delinquent-real-estate-taxes"
VIRGINIA_BEACH_GEOID = "51810"
STATE_CODE = "VA"
ARCGIS_ITEM_ID = "1b2d03addfaa41bb83c17f9237e1504c"
ARCGIS_ORG_ID = "CyVvlIiUfRBmMQuu"
LAYER_ID = 0

OPEN_DATA_URL = (
    "https://data.virginiabeach.gov/datasets/"
    f"{ARCGIS_ITEM_ID}_{LAYER_ID}/explore"
)
ITEM_API_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{ARCGIS_ITEM_ID}"
)
FEATURE_SERVICE_URL = (
    f"https://services2.arcgis.com/{ARCGIS_ORG_ID}/arcgis/rest/services/"
    "Delinquent_Real_Estate_Taxes_view/FeatureServer"
)
LAYER_URL = f"{FEATURE_SERVICE_URL}/{LAYER_ID}"
QUERY_URL = f"{LAYER_URL}/query"

TREASURER_PAGE_URL = (
    "https://treasurer.virginiabeach.gov/taxes-licenses-collections/"
    "real-estate"
)
DETAILED_TAX_SEARCH_URL = "https://cvb.manatron.com/Default.aspx"
ASSESSOR_SEARCH_URL = "https://propertysearch.virginiabeach.gov/"
LAND_RECORDS_URL = (
    "https://courts.virginiabeach.gov/circuit-court-clerks-office/"
    "real-estate-records"
)
CIRCUIT_CASE_SEARCH_URL = (
    "https://eapps.courts.state.va.us/CJISWeb/circuit.jsp?hl=en-US"
)
GENERAL_DISTRICT_CASE_SEARCH_URL = (
    "https://eapps.courts.state.va.us/gdcourts/landing.do?landing=landing"
)

DEFAULT_PAGE_SIZE = 1_000
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.0
CURSOR_PREFIX = "va-beach-delinquent-tax:v1:"
CURSOR_VERSION = 1
NORMALIZATION_VERSION = 1

OUT_FIELDS = (
    "OBJECTID",
    "Owner_Name",
    "Mailing_Address",
    "City_State_Zip",
    "GPIN",
    "Situs_Address",
    "Property_Description",
    "District",
    "Tax_Year",
    "Bill_Number",
    "Installment",
    "Tax_Due",
    "Penalty_Due",
    "Interest_Due",
    "Fee_Due",
    "Total_Delinquent_Amount_Due",
)

EXPECTED_FIELD_TYPES: Mapping[str, frozenset[str]] = {
    "OBJECTID": frozenset({"esriFieldTypeOID"}),
    "Owner_Name": frozenset({"esriFieldTypeString"}),
    "Mailing_Address": frozenset({"esriFieldTypeString"}),
    "City_State_Zip": frozenset({"esriFieldTypeString"}),
    "GPIN": frozenset({"esriFieldTypeString"}),
    "Situs_Address": frozenset({"esriFieldTypeString"}),
    "Property_Description": frozenset({"esriFieldTypeString"}),
    "District": frozenset({"esriFieldTypeString"}),
    "Tax_Year": frozenset({"esriFieldTypeString", "esriFieldTypeInteger"}),
    "Bill_Number": frozenset({"esriFieldTypeString"}),
    "Installment": frozenset({"esriFieldTypeString", "esriFieldTypeInteger"}),
    "Tax_Due": frozenset(
        {
            "esriFieldTypeSingle",
            "esriFieldTypeDouble",
            "esriFieldTypeInteger",
        }
    ),
    "Penalty_Due": frozenset(
        {
            "esriFieldTypeSingle",
            "esriFieldTypeDouble",
            "esriFieldTypeInteger",
        }
    ),
    "Interest_Due": frozenset(
        {
            "esriFieldTypeSingle",
            "esriFieldTypeDouble",
            "esriFieldTypeInteger",
        }
    ),
    "Fee_Due": frozenset(
        {
            "esriFieldTypeSingle",
            "esriFieldTypeDouble",
            "esriFieldTypeInteger",
        }
    ),
    "Total_Delinquent_Amount_Due": frozenset(
        {
            "esriFieldTypeSingle",
            "esriFieldTypeDouble",
            "esriFieldTypeInteger",
        }
    ),
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Virginia Beach Delinquent Real Estate Taxes",
    source_role="local_property_tax_delinquency_current_extract",
    base_url=OPEN_DATA_URL,
    dataset_id=f"{ARCGIS_ITEM_ID}/{LAYER_ID}",
    metadata={
        "authority": "City of Virginia Beach Treasurer's Office",
        "operator": "City of Virginia Beach Open Data",
        "coverage": "City of Virginia Beach, Virginia",
        "update_frequency": "daily",
        "platform_family": "arcgis_feature_service_table",
        "arcgis_item_id": ARCGIS_ITEM_ID,
        "arcgis_org_id": ARCGIS_ORG_ID,
        "stable_key_fields": [
            "bill_number",
            "installment",
            "gpin",
            "tax_year",
        ],
        "join_key_fields": [
            "gpin",
            "owner_name",
            "mailing_address",
            "situs_address",
            "bill_number",
            "tax_year",
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=VIRGINIA_BEACH_GEOID,
    name="City of Virginia Beach, Virginia",
    state_code=STATE_CODE,
    county_fips=VIRGINIA_BEACH_GEOID,
    locality="Virginia Beach",
)

SOURCE_WARNINGS = (
    "The table is a current daily extract; balances and membership can change "
    "when the Treasurer refreshes it.",
    "The publisher identifies Owner Name as the primary owner and notes that "
    "additional owners may not be listed.",
    "Published owner and mailing fields are tax-account observations, not a "
    "substitute for the Circuit Court Clerk's recorded deed.",
    "This source covers Virginia Beach; Virginia tax collection is administered "
    "by local treasurers rather than one statewide delinquency system.",
)

RELATED_ROUTES = (
    {
        "role": "delinquency_extract",
        "source_id": SOURCE_ID,
        "url": OPEN_DATA_URL,
        "access": "public_arcgis_api",
        "join_keys": ["GPIN", "bill_number", "installment", "tax_year"],
        "information": [
            "published primary owner",
            "mailing and situs addresses",
            "legal description",
            "tax, penalty, interest, fee, and total due",
        ],
    },
    {
        "role": "current_tax_account_detail_and_payment_history",
        "url": DETAILED_TAX_SEARCH_URL,
        "access": "public_web_inquiry",
        "join_keys": [
            "GPIN",
            "bill_number",
            "owner_name",
            "situs_address",
        ],
        "information": [
            "original due date",
            "current component balances",
            "limited payment history",
        ],
    },
    {
        "role": "assessment_and_current_owner_context",
        "url": ASSESSOR_SEARCH_URL,
        "access": "public_web_search",
        "join_keys": ["GPIN", "owner_name", "situs_address"],
        "information": [
            "assessment",
            "parcel characteristics",
            "current assessor ownership observation",
        ],
    },
    {
        "role": "recorded_deeds_judgments_and_ucc",
        "url": LAND_RECORDS_URL,
        "access": "clerk_land_records_route",
        "join_keys": [
            "GPIN",
            "owner_name",
            "legal_description",
            "situs_address",
        ],
        "information": [
            "deeds",
            "deeds of trust",
            "certificates of satisfaction",
            "judgments",
            "UCC financing statements",
        ],
    },
    {
        "role": "circuit_court_case_index",
        "source_id": "us-va-circuit-court-case-information",
        "url": CIRCUIT_CASE_SEARCH_URL,
        "access": "public_web_search",
        "join_keys": ["owner_name", "case_number"],
        "information": [
            "participating circuit court civil and criminal case index",
        ],
    },
    {
        "role": "general_district_court_case_index",
        "source_id": "us-va-general-district-court-case-information",
        "url": GENERAL_DISTRICT_CASE_SEARCH_URL,
        "access": "public_web_search",
        "join_keys": ["owner_name", "case_number"],
        "information": [
            "general district civil, criminal, and traffic case index",
        ],
    },
    {
        "role": "tax_sale_notices_and_auction_links",
        "url": TREASURER_PAGE_URL,
        "access": "official_publication_page",
        "join_keys": [
            "GPIN",
            "owner_name",
            "situs_address",
            "legal_description",
        ],
        "information": [
            "legal advertisements",
            "judicial and non-judicial auction flyers",
        ],
    },
)

ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "source_id": SOURCE_ID,
        "normalization_version": NORMALIZATION_VERSION,
        "fields": OUT_FIELDS,
        "stable_key_fields": [
            "Bill_Number",
            "Installment",
            "GPIN",
            "Tax_Year",
        ],
        "ordering": "OBJECTID ASC",
    }
)


class VirginiaBeachTaxQueryError(PublicRecordsHTTPError):
    """A caller selection or continuation cursor is invalid."""

    result_status = ResultStatus.UNAVAILABLE
    category = "query"
    retryable = False
    code = "invalid_query"


class VirginiaBeachTaxCursorError(VirginiaBeachTaxQueryError):
    """A continuation cursor is malformed or belongs to another query."""

    code = "invalid_cursor"


class VirginiaBeachTaxCursorMismatch(VirginiaBeachTaxCursorError):
    """A continuation cursor was paired with different search criteria."""

    code = "cursor_criteria_mismatch"


class VirginiaBeachTaxSnapshotChanged(VirginiaBeachTaxQueryError):
    """The daily table changed while or between pages of one traversal."""

    retryable = True
    code = "cursor_snapshot_changed"


class VirginiaBeachTaxSourceChanged(SourceSchemaError):
    """The official ArcGIS representation no longer matches this adapter."""

    code = "virginia_beach_tax_source_changed"


@dataclass(frozen=True)
class LayerSnapshot:
    schema: Mapping[str, Any]
    schema_fingerprint: str
    query_schema_fingerprint: str
    data_last_edit_ms: int
    data_last_edit_iso: str
    max_record_count: int


@dataclass(frozen=True)
class CursorState:
    criteria_fingerprint: str
    schema_fingerprint: str
    data_last_edit_ms: int
    last_object_id: int
    emitted_count: int
    total_count: int


@dataclass(frozen=True)
class SearchCriteria:
    query: str | None = None
    owner: str | None = None
    address: str | None = None
    gpin: str | None = None
    bill_number: str | None = None
    tax_year: int | None = None
    installment: str | None = None
    district: str | None = None
    min_total_due: Decimal | None = None
    max_total_due: Decimal | None = None

    def parameters(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "owner": self.owner,
            "address": self.address,
            "gpin": self.gpin,
            "bill_number": self.bill_number,
            "tax_year": self.tax_year,
            "installment": self.installment,
            "district": self.district,
            "min_total_due": (
                str(self.min_total_due)
                if self.min_total_due is not None
                else None
            ),
            "max_total_due": (
                str(self.max_total_due)
                if self.max_total_due is not None
                else None
            ),
        }


class VirginiaBeachTaxClient(ArcGISRESTClient):
    """Small ArcGIS client exposing metadata, count, and ordered page calls."""

    def item_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(ITEM_API_URL, params={"f": "json"})
        if not isinstance(payload, Mapping):
            raise VirginiaBeachTaxSourceChanged(
                "ArcGIS item metadata is not a JSON object",
                url=ITEM_API_URL,
            )
        return payload

    def layer_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping):
            raise VirginiaBeachTaxSourceChanged(
                "ArcGIS layer metadata is not a JSON object",
                url=self.layer_url,
            )
        return payload

    def count(self, where: str) -> int:
        payload = self._request_json(
            self.query_url,
            params={
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping):
            raise VirginiaBeachTaxSourceChanged(
                "ArcGIS count response is not a JSON object",
                url=self.query_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned an error for the count query",
                url=self.query_url,
                details={"response": payload["error"]},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise VirginiaBeachTaxSourceChanged(
                "ArcGIS count response is missing a non-negative count",
                url=self.query_url,
                details={"count": count},
            )
        return count

    def ordered_page(
        self,
        where: str,
        *,
        page_size: int,
    ) -> Mapping[str, Any]:
        payload = self._request_json(
            self.query_url,
            params={
                "where": where,
                "outFields": ",".join(OUT_FIELDS),
                "returnGeometry": "false",
                "orderByFields": "OBJECTID ASC",
                "resultRecordCount": page_size,
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping):
            raise VirginiaBeachTaxSourceChanged(
                "ArcGIS page response is not a JSON object",
                url=self.query_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned an error for the records query",
                url=self.query_url,
                details={"response": payload["error"]},
            )
        return payload


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _contains(field_name: str, value: str) -> str:
    return (
        f"UPPER({field_name}) LIKE "
        f"{_sql_literal('%' + value.upper() + '%')}"
    )


def _decimal_arg(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("amount must be numeric") from error
    if not parsed.is_finite():
        raise argparse.ArgumentTypeError("amount must be finite")
    return parsed


def _normalize_district(value: str | None) -> str | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    upper = cleaned.upper()
    match = re.fullmatch(r"D?(\d{1,2})", upper)
    if not match:
        raise VirginiaBeachTaxQueryError(
            "District must be a number or a D-prefixed number",
            url=QUERY_URL,
            details={"district": cleaned},
        )
    return f"D{int(match.group(1)):02d}"


def _criteria_from_args(args: argparse.Namespace) -> SearchCriteria:
    command = args.command
    query = _clean(getattr(args, "query", None))
    owner = _clean(getattr(args, "owner", None))
    address = _clean(getattr(args, "address", None))
    gpin = _clean(getattr(args, "gpin", None))
    bill_number = _clean(getattr(args, "bill_number", None))

    if command == "owner":
        owner = query
        query = None
    elif command == "address":
        address = query
        query = None
    elif command == "parcel":
        gpin = query
        query = None
    elif command == "bill":
        bill_number = query
        query = None
    elif command == "probe":
        query = None

    if command in {"owner", "address", "parcel", "bill"} and not any(
        (owner, address, gpin, bill_number)
    ):
        raise VirginiaBeachTaxQueryError(
            f"{command} requires a non-empty selector",
            url=QUERY_URL,
        )

    tax_year = getattr(args, "tax_year", None)
    if tax_year is not None and not 1000 <= tax_year <= 9999:
        raise VirginiaBeachTaxQueryError(
            "Tax year must contain four digits",
            url=QUERY_URL,
            details={"tax_year": tax_year},
        )
    installment = _clean(getattr(args, "installment", None))
    if installment is not None and installment not in {"1", "2"}:
        raise VirginiaBeachTaxQueryError(
            "Installment must be 1 or 2",
            url=QUERY_URL,
            details={"installment": installment},
        )
    minimum = getattr(args, "min_total_due", None)
    maximum = getattr(args, "max_total_due", None)
    if minimum is not None and maximum is not None and minimum > maximum:
        raise VirginiaBeachTaxQueryError(
            "Minimum total due cannot exceed maximum total due",
            url=QUERY_URL,
        )

    return SearchCriteria(
        query=query,
        owner=owner,
        address=address,
        gpin=gpin,
        bill_number=bill_number,
        tax_year=tax_year,
        installment=installment,
        district=_normalize_district(getattr(args, "district", None)),
        min_total_due=minimum,
        max_total_due=maximum,
    )


def build_where(criteria: SearchCriteria) -> str:
    clauses: list[str] = []

    if criteria.query:
        query_clauses = [
            _contains("Owner_Name", criteria.query),
            _contains("Mailing_Address", criteria.query),
            _contains("City_State_Zip", criteria.query),
            _contains("GPIN", criteria.query),
            _contains("Situs_Address", criteria.query),
            _contains("Property_Description", criteria.query),
            _contains("Bill_Number", criteria.query),
        ]
        clauses.append("(" + " OR ".join(query_clauses) + ")")
    if criteria.owner:
        clauses.append(_contains("Owner_Name", criteria.owner))
    if criteria.address:
        clauses.append(
            "("
            + " OR ".join(
                (
                    _contains("Situs_Address", criteria.address),
                    _contains("Mailing_Address", criteria.address),
                    _contains("City_State_Zip", criteria.address),
                )
            )
            + ")"
        )
    if criteria.gpin:
        clauses.append(f"GPIN = {_sql_literal(criteria.gpin)}")
    if criteria.bill_number:
        clauses.append(
            f"Bill_Number = {_sql_literal(criteria.bill_number)}"
        )
    if criteria.tax_year is not None:
        clauses.append(f"Tax_Year = {_sql_literal(str(criteria.tax_year))}")
    if criteria.installment:
        clauses.append(
            f"Installment = {_sql_literal(criteria.installment)}"
        )
    if criteria.district:
        clauses.append(f"District = {_sql_literal(criteria.district)}")
    if criteria.min_total_due is not None:
        clauses.append(
            "Total_Delinquent_Amount_Due >= "
            f"{format(criteria.min_total_due, 'f')}"
        )
    if criteria.max_total_due is not None:
        clauses.append(
            "Total_Delinquent_Amount_Due <= "
            f"{format(criteria.max_total_due, 'f')}"
        )
    return " AND ".join(clauses) if clauses else "1=1"


def _criteria_fingerprint(criteria: SearchCriteria) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "normalization_version": NORMALIZATION_VERSION,
            "where": build_where(criteria),
            "ordering": "OBJECTID ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source_id": SOURCE_ID,
        "criteria_fingerprint": state.criteria_fingerprint,
        "schema_fingerprint": state.schema_fingerprint,
        "data_last_edit_ms": state.data_last_edit_ms,
        "last_object_id": state.last_object_id,
        "emitted_count": state.emitted_count,
        "total_count": state.total_count,
    }
    payload["check"] = sha256_fingerprint(payload)[:16]
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def _decode_cursor(value: str) -> CursorState:
    if not value.startswith(CURSOR_PREFIX):
        raise VirginiaBeachTaxCursorError(
            "Continuation cursor has an unrecognized source or version",
            url=QUERY_URL,
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
        binascii.Error,
    ) as error:
        raise VirginiaBeachTaxCursorError(
            "Continuation cursor could not be decoded",
            url=QUERY_URL,
        ) from error
    if not isinstance(payload, Mapping):
        raise VirginiaBeachTaxCursorError(
            "Continuation cursor payload is not an object",
            url=QUERY_URL,
        )
    if (
        payload.get("v") != CURSOR_VERSION
        or payload.get("source_id") != SOURCE_ID
    ):
        raise VirginiaBeachTaxCursorError(
            "Continuation cursor has an unrecognized source or version",
            url=QUERY_URL,
        )

    supplied_check = payload.get("check")
    checked_payload = {
        key: item for key, item in payload.items() if key != "check"
    }
    expected_check = sha256_fingerprint(checked_payload)[:16]
    if (
        not isinstance(supplied_check, str)
        or supplied_check != expected_check
    ):
        raise VirginiaBeachTaxCursorError(
            "Continuation cursor consistency check failed",
            url=QUERY_URL,
        )

    string_fields = ("criteria_fingerprint", "schema_fingerprint")
    integer_fields = (
        "data_last_edit_ms",
        "last_object_id",
        "emitted_count",
        "total_count",
    )
    if any(
        not isinstance(payload.get(field_name), str)
        or not payload.get(field_name)
        for field_name in string_fields
    ) or any(
        isinstance(payload.get(field_name), bool)
        or not isinstance(payload.get(field_name), int)
        or payload.get(field_name) < 0
        for field_name in integer_fields
    ):
        raise VirginiaBeachTaxCursorError(
            "Continuation cursor fields are malformed",
            url=QUERY_URL,
        )
    if payload["emitted_count"] > payload["total_count"]:
        raise VirginiaBeachTaxCursorError(
            "Continuation cursor count is inconsistent",
            url=QUERY_URL,
        )
    return CursorState(
        criteria_fingerprint=payload["criteria_fingerprint"],
        schema_fingerprint=payload["schema_fingerprint"],
        data_last_edit_ms=payload["data_last_edit_ms"],
        last_object_id=payload["last_object_id"],
        emitted_count=payload["emitted_count"],
        total_count=payload["total_count"],
    )


def _epoch_ms_iso(value: int) -> str:
    return (
        datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _query_field_schema(
    fields: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Normalize the field properties shared by layer and query responses."""

    stable_keys = ("name", "type", "alias", "sqlType", "length")
    normalized = [
        {
            key: field.get(key)
            for key in stable_keys
            if key in field
        }
        for field in fields
    ]
    normalized.sort(key=lambda value: str(value.get("name", "")))
    return {"kind": "arcgis_query_declared", "fields": normalized}


def inspect_layer_metadata(metadata: Mapping[str, Any]) -> LayerSnapshot:
    if metadata.get("error") is not None:
        raise SourceResponseError(
            "ArcGIS returned an error for layer metadata",
            url=LAYER_URL,
            details={"response": metadata.get("error")},
        )
    if metadata.get("serviceItemId") != ARCGIS_ITEM_ID:
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS layer no longer belongs to the verified item",
            url=LAYER_URL,
            details={"serviceItemId": metadata.get("serviceItemId")},
        )
    if metadata.get("type") != "Table":
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS layer is no longer a table",
            url=LAYER_URL,
            details={"type": metadata.get("type")},
        )
    capabilities = {
        value.strip()
        for value in str(metadata.get("capabilities") or "").split(",")
        if value.strip()
    }
    if "Query" not in capabilities:
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS table no longer advertises query capability",
            url=LAYER_URL,
        )
    if metadata.get("objectIdField") != "OBJECTID":
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS table object-ID field changed",
            url=LAYER_URL,
            details={"objectIdField": metadata.get("objectIdField")},
        )

    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS layer fields metadata is malformed",
            url=LAYER_URL,
        )
    fields_by_name = {
        str(field.get("name")): field
        for field in fields
        if field.get("name") is not None
    }
    for field_name, allowed_types in EXPECTED_FIELD_TYPES.items():
        field = fields_by_name.get(field_name)
        if field is None:
            raise VirginiaBeachTaxSourceChanged(
                f"ArcGIS table is missing required field {field_name}",
                url=LAYER_URL,
            )
        field_type = field.get("type")
        if field_type not in allowed_types:
            raise VirginiaBeachTaxSourceChanged(
                f"ArcGIS field {field_name} has an incompatible type",
                url=LAYER_URL,
                details={
                    "field_type": field_type,
                    "allowed_types": sorted(allowed_types),
                },
            )

    editing_info = metadata.get("editingInfo")
    if not isinstance(editing_info, Mapping):
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS layer is missing editing snapshot metadata",
            url=LAYER_URL,
        )
    data_last_edit_ms = editing_info.get("dataLastEditDate")
    if (
        isinstance(data_last_edit_ms, bool)
        or not isinstance(data_last_edit_ms, int)
        or data_last_edit_ms <= 0
    ):
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS layer has no usable data-last-edit timestamp",
            url=LAYER_URL,
            details={"dataLastEditDate": data_last_edit_ms},
        )
    maximum = metadata.get("maxRecordCount")
    if (
        isinstance(maximum, bool)
        or not isinstance(maximum, int)
        or maximum <= 0
    ):
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS layer has no usable maximum page size",
            url=LAYER_URL,
            details={"maxRecordCount": maximum},
        )

    declared = arcgis_declared_schema(fields)
    return LayerSnapshot(
        schema=declared,
        schema_fingerprint=schema_fingerprint(declared),
        query_schema_fingerprint=schema_fingerprint(
            _query_field_schema(fields)
        ),
        data_last_edit_ms=data_last_edit_ms,
        data_last_edit_iso=_epoch_ms_iso(data_last_edit_ms),
        max_record_count=maximum,
    )


def inspect_item_metadata(metadata: Mapping[str, Any]) -> None:
    expected = {
        "id": ARCGIS_ITEM_ID,
        "type": "Feature Service",
        "access": "public",
        "url": FEATURE_SERVICE_URL,
    }
    mismatches = {
        key: {"expected": value, "actual": metadata.get(key)}
        for key, value in expected.items()
        if metadata.get(key) != value
    }
    if mismatches:
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS item metadata no longer matches the verified service",
            url=ITEM_API_URL,
            details={"mismatches": mismatches},
        )


def _page_features(
    payload: Mapping[str, Any],
    snapshot: LayerSnapshot,
) -> list[Mapping[str, Any]]:
    features = payload.get("features")
    if not isinstance(features, list) or any(
        not isinstance(feature, Mapping) for feature in features
    ):
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS page is missing a valid features array",
            url=QUERY_URL,
        )
    fields = payload.get("fields")
    if fields is not None:
        if not isinstance(fields, list) or any(
            not isinstance(field, Mapping) for field in fields
        ):
            raise VirginiaBeachTaxSourceChanged(
                "ArcGIS page fields metadata is malformed",
                url=QUERY_URL,
            )
        response_fingerprint = schema_fingerprint(
            _query_field_schema(fields)
        )
        if response_fingerprint != snapshot.query_schema_fingerprint:
            raise VirginiaBeachTaxSourceChanged(
                "ArcGIS response schema differs from the layer snapshot",
                url=QUERY_URL,
                details={
                    "expected_schema_fingerprint": (
                        snapshot.query_schema_fingerprint
                    ),
                    "response_schema_fingerprint": response_fingerprint,
                },
            )
    return list(features)


def _feature_attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS feature is missing an attributes object",
            url=QUERY_URL,
        )
    return attributes


def _object_id(feature: Mapping[str, Any]) -> int:
    value = _feature_attributes(feature).get("OBJECTID")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS feature has no positive OBJECTID",
            url=QUERY_URL,
            details={"OBJECTID": value},
        )
    return value


def _decimal_value(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as error:
        raise VirginiaBeachTaxSourceChanged(
            f"ArcGIS field {field_name} is not numeric",
            url=QUERY_URL,
            details={"value": value},
        ) from error
    if not parsed.is_finite():
        raise VirginiaBeachTaxSourceChanged(
            f"ArcGIS field {field_name} is not finite",
            url=QUERY_URL,
            details={"value": value},
        )
    return parsed


def _money_pair(value: Any, field_name: str) -> tuple[float | None, int | None]:
    parsed = _decimal_value(value, field_name)
    if parsed is None:
        return None, None
    rounded = parsed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    minor = int(
        (rounded * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return float(rounded), minor


def normalize_feature(
    feature: Mapping[str, Any],
    *,
    snapshot: LayerSnapshot,
) -> dict[str, Any]:
    attributes = dict(_feature_attributes(feature))
    object_id = _object_id(feature)
    gpin = _clean(attributes.get("GPIN"))
    tax_year_raw = _clean(attributes.get("Tax_Year"))
    bill_number = _clean(attributes.get("Bill_Number"))
    installment = _clean(attributes.get("Installment"))
    if not all((gpin, tax_year_raw, bill_number, installment)):
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS tax row is missing a stable installment key field",
            url=QUERY_URL,
            details={
                "OBJECTID": object_id,
                "GPIN": gpin,
                "Tax_Year": tax_year_raw,
                "Bill_Number": bill_number,
                "Installment": installment,
            },
        )
    if not re.fullmatch(r"\d{4}", tax_year_raw):
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS tax year is not a four-digit value",
            url=QUERY_URL,
            details={"OBJECTID": object_id, "Tax_Year": tax_year_raw},
        )
    tax_year = int(tax_year_raw)
    native_event_id = (
        f"{bill_number}:{installment}:{gpin}:{tax_year_raw}"
    )
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        VIRGINIA_BEACH_GEOID,
        "tax-delinquency",
        native_event_id,
    )

    tax_due, tax_due_minor = _money_pair(
        attributes.get("Tax_Due"), "Tax_Due"
    )
    penalty_due, penalty_due_minor = _money_pair(
        attributes.get("Penalty_Due"), "Penalty_Due"
    )
    interest_due, interest_due_minor = _money_pair(
        attributes.get("Interest_Due"), "Interest_Due"
    )
    fee_due, fee_due_minor = _money_pair(
        attributes.get("Fee_Due"), "Fee_Due"
    )
    total_due, total_due_minor = _money_pair(
        attributes.get("Total_Delinquent_Amount_Due"),
        "Total_Delinquent_Amount_Due",
    )
    component_values = (
        tax_due_minor,
        penalty_due_minor,
        interest_due_minor,
        fee_due_minor,
    )
    component_total_minor = (
        sum(value for value in component_values if value is not None)
        if all(value is not None for value in component_values)
        else None
    )
    component_difference_minor = (
        total_due_minor - component_total_minor
        if total_due_minor is not None and component_total_minor is not None
        else None
    )

    owner_name = _clean(attributes.get("Owner_Name"))
    mailing_line = _clean(attributes.get("Mailing_Address"))
    mailing_city_state_zip = _clean(attributes.get("City_State_Zip"))
    situs_address = _clean(attributes.get("Situs_Address"))
    mailing_raw = _clean(
        " ".join(
            value
            for value in (mailing_line, mailing_city_state_zip)
            if value
        )
    )
    query_parameters = urlencode(
        {
            "where": f"OBJECTID={object_id}",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
        }
    )

    return {
        "source_id": SOURCE_ID,
        "record_kind": "property_tax_delinquency",
        "record_scope": "delinquent_real_estate_tax_installment",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "native_document_id": native_event_id,
        "native_event_id": native_event_id,
        "native_object_id": object_id,
        "native_parcel_id": gpin,
        "native_account_id": bill_number,
        "gpin": gpin,
        "tax_year": tax_year,
        "bill_number": bill_number,
        "installment": installment,
        "district": _clean(attributes.get("District")),
        "delinquency_status": "delinquent_in_current_daily_extract",
        "owner_observation": {
            "raw_name": owner_name,
            "role": "published_primary_owner",
            "additional_owners_may_be_omitted": True,
        },
        "owner_names": [owner_name] if owner_name else [],
        "mailing_address": {
            "raw": mailing_raw,
            "line1_raw": mailing_line,
            "city_state_postal_raw": mailing_city_state_zip,
        },
        "situs_address": {
            "raw": situs_address,
            "locality": "Virginia Beach",
            "state": STATE_CODE,
        },
        "legal_description_raw": _clean(
            attributes.get("Property_Description")
        ),
        "amounts": {
            "tax_due": tax_due,
            "tax_due_minor": tax_due_minor,
            "penalty_due": penalty_due,
            "penalty_due_minor": penalty_due_minor,
            "interest_due": interest_due,
            "interest_due_minor": interest_due_minor,
            "fee_due": fee_due,
            "fee_due_minor": fee_due_minor,
            "total_due": total_due,
            "total_due_minor": total_due_minor,
            "component_total_minor": component_total_minor,
            "component_difference_minor": component_difference_minor,
            "currency": "USD",
        },
        "stable_key_fields": [
            "bill_number",
            "installment",
            "gpin",
            "tax_year",
        ],
        "join_keys": {
            "parcel_and_assessment": {
                "gpin": gpin,
                "situs_address": situs_address,
            },
            "tax_account": {
                "bill_number": bill_number,
                "installment": installment,
                "tax_year": tax_year,
            },
            "owner_and_land_records": {
                "owner_name": owner_name,
                "mailing_address": mailing_raw,
                "situs_address": situs_address,
                "legal_description": _clean(
                    attributes.get("Property_Description")
                ),
            },
        },
        "source_snapshot": {
            "data_last_edit_epoch_ms": snapshot.data_last_edit_ms,
            "data_last_edit_at": snapshot.data_last_edit_iso,
            "update_frequency": "daily",
        },
        "source_url": f"{QUERY_URL}?{query_parameters}",
        "open_data_url": OPEN_DATA_URL,
        "detailed_tax_search_url": DETAILED_TAX_SEARCH_URL,
        "assessment_search_url": ASSESSOR_SEARCH_URL,
        "land_records_url": LAND_RECORDS_URL,
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "response_schema_fingerprint": snapshot.schema_fingerprint,
        "raw_attributes": attributes,
    }


def _page_where(base_where: str, last_object_id: int) -> str:
    if last_object_id <= 0:
        return base_where
    return f"({base_where}) AND OBJECTID > {last_object_id}"


def _check_snapshot(
    expected: LayerSnapshot,
    current: LayerSnapshot,
) -> None:
    if current.schema_fingerprint != expected.schema_fingerprint:
        raise VirginiaBeachTaxSourceChanged(
            "ArcGIS table schema changed during traversal",
            url=LAYER_URL,
            details={
                "initial": expected.schema_fingerprint,
                "current": current.schema_fingerprint,
            },
        )
    if current.data_last_edit_ms != expected.data_last_edit_ms:
        raise VirginiaBeachTaxSnapshotChanged(
            "The daily ArcGIS table refreshed during or between result pages; "
            "rerun the query from the first page",
            url=LAYER_URL,
            details={
                "initial_data_last_edit_ms": expected.data_last_edit_ms,
                "current_data_last_edit_ms": current.data_last_edit_ms,
            },
        )


def _query_records(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    criteria: SearchCriteria,
    client: VirginiaBeachTaxClient,
) -> PublicRecordsResult:
    if args.command == "probe":
        inspect_item_metadata(client.item_metadata())

    snapshot = inspect_layer_metadata(client.layer_metadata())
    criteria_key = _criteria_fingerprint(criteria)
    cursor_state = _decode_cursor(args.cursor) if args.cursor else None
    if cursor_state is not None:
        if cursor_state.criteria_fingerprint != criteria_key:
            raise VirginiaBeachTaxCursorMismatch(
                "Continuation cursor belongs to different search criteria",
                url=QUERY_URL,
            )
        if cursor_state.schema_fingerprint != snapshot.schema_fingerprint:
            raise VirginiaBeachTaxSourceChanged(
                "ArcGIS schema changed since the continuation cursor was issued",
                url=LAYER_URL,
            )
        if cursor_state.data_last_edit_ms != snapshot.data_last_edit_ms:
            raise VirginiaBeachTaxSnapshotChanged(
                "The daily ArcGIS table refreshed since the continuation cursor "
                "was issued; rerun the query from the first page",
                url=LAYER_URL,
                details={
                    "cursor_data_last_edit_ms": (
                        cursor_state.data_last_edit_ms
                    ),
                    "current_data_last_edit_ms": snapshot.data_last_edit_ms,
                },
            )

    base_where = build_where(criteria)
    total_count = client.count(base_where)
    emitted_before = cursor_state.emitted_count if cursor_state else 0
    last_object_id = cursor_state.last_object_id if cursor_state else 0
    if cursor_state is not None and cursor_state.total_count != total_count:
        raise VirginiaBeachTaxSnapshotChanged(
            "ArcGIS result count changed since the continuation cursor was "
            "issued; rerun the query from the first page",
            url=QUERY_URL,
            details={
                "cursor_total_count": cursor_state.total_count,
                "current_total_count": total_count,
            },
        )
    if emitted_before > total_count:
        raise VirginiaBeachTaxCursorError(
            "Continuation cursor has emitted more rows than the current result",
            url=QUERY_URL,
        )

    remaining_total = total_count - emitted_before
    requested_limit = 1 if args.command == "probe" else args.limit
    target_count = (
        remaining_total
        if requested_limit is None
        else min(requested_limit, remaining_total)
    )
    records: list[dict[str, Any]] = []
    seen_native_keys: set[str] = set()
    page_size = min(
        args.page_size,
        snapshot.max_record_count,
        int(getattr(client, "page_size", args.page_size)),
    )

    while len(records) < target_count:
        request_size = min(page_size, target_count - len(records))
        payload = client.ordered_page(
            _page_where(base_where, last_object_id),
            page_size=request_size,
        )
        features = _page_features(payload, snapshot)
        if len(features) > request_size:
            raise PaginationError(
                "ArcGIS returned more rows than the requested page size",
                url=QUERY_URL,
                details={
                    "requested": request_size,
                    "returned": len(features),
                },
            )
        if not features:
            raise PaginationError(
                "ArcGIS traversal ended before the authoritative count",
                url=QUERY_URL,
                details={
                    "total_count": total_count,
                    "emitted_before": emitted_before,
                    "returned_now": len(records),
                },
            )

        object_ids = [_object_id(feature) for feature in features]
        if (
            object_ids != sorted(object_ids)
            or len(object_ids) != len(set(object_ids))
            or object_ids[0] <= last_object_id
        ):
            raise PaginationError(
                "ArcGIS keyset page is not strictly increasing by OBJECTID",
                url=QUERY_URL,
                details={
                    "previous_object_id": last_object_id,
                    "object_ids": object_ids,
                },
            )
        normalized = [
            normalize_feature(feature, snapshot=snapshot)
            for feature in features
        ]
        for record in normalized:
            native_key = str(record["native_event_id"])
            if native_key in seen_native_keys:
                raise PaginationError(
                    "ArcGIS traversal repeated a stable tax-installment key",
                    url=QUERY_URL,
                    details={"native_event_id": native_key},
                )
            seen_native_keys.add(native_key)
        records.extend(normalized)
        last_object_id = object_ids[-1]

    final_snapshot = inspect_layer_metadata(client.layer_metadata())
    _check_snapshot(snapshot, final_snapshot)

    emitted_count = emitted_before + len(records)
    next_cursor = None
    if emitted_count < total_count and args.command != "probe":
        next_cursor = _encode_cursor(
            CursorState(
                criteria_fingerprint=criteria_key,
                schema_fingerprint=snapshot.schema_fingerprint,
                data_last_edit_ms=snapshot.data_last_edit_ms,
                last_object_id=last_object_id,
                emitted_count=emitted_count,
                total_count=total_count,
            )
        )
    warnings = (
        *SOURCE_WARNINGS,
        f"Authoritative source count for this query snapshot: {total_count}.",
    )
    if args.command == "probe" and total_count > len(records):
        warnings = (
            *warnings,
            "The probe sampled one ordered row after validating the complete "
            "query count and did not issue a continuation cursor.",
        )
    if next_cursor:
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=records,
            next_cursor=next_cursor,
            warnings=warnings,
        )
    return PublicRecordsResult.success(query, records, warnings=warnings)


def _routes_record() -> dict[str, Any]:
    canonical_ref = canonical_property_ref(
        SOURCE_ID,
        VIRGINIA_BEACH_GEOID,
        "source-route-map",
        "property-tax-and-local-court",
    )
    return {
        "source_id": SOURCE_ID,
        "record_kind": "public_record_route_map",
        "record_scope": "virginia_beach_property_tax_and_related_records",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "coverage_strategy": (
            "Use the machine-readable Virginia Beach delinquency extract as "
            "the tax-collection anchor, then pivot by GPIN, bill number, "
            "owner, address, or legal description to the official route that "
            "holds the missing record role."
        ),
        "jurisdiction": {
            "name": JURISDICTION.name,
            "geoid": VIRGINIA_BEACH_GEOID,
            "state_code": STATE_CODE,
        },
        "routes": list(RELATED_ROUTES),
        "strongest_join_keys": [
            "GPIN",
            "bill_number and installment",
            "owner name",
            "situs address",
            "legal description",
        ],
    }


def build_query(
    operation: str,
    criteria: SearchCriteria | None,
    *,
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsQuery:
    parameters: Mapping[str, Any] = (
        criteria.parameters()
        if criteria is not None
        else {"route_scope": "property_tax_and_local_court"}
    )
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "ordering": "OBJECTID ASC",
                "pagination": "snapshot_bound_objectid_keyset",
            },
        ),
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog_db = Path(
        getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
    ).expanduser()
    catalog_config = Path(
        getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
    ).expanduser()
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=catalog_db,
        config_path=catalog_config,
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _new_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> VirginiaBeachTaxClient:
    limits = access_contract.get("limits") or {}
    reviewed_page_size = limits.get("maximum_page_size")
    page_size = args.page_size
    if reviewed_page_size is not None:
        page_size = min(page_size, int(reviewed_page_size))
    reviewed_interval = float(
        limits.get("minimum_interval_seconds") or 0
    )
    return VirginiaBeachTaxClient(
        LAYER_URL,
        page_size=page_size,
        timeout=args.timeout,
        minimum_interval=max(
            args.minimum_interval,
            reviewed_interval,
        ),
        session=system_trust_session(),
    )


def _access_failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        public_error = PublicRecordsError(
            code=str(
                decision.get("reason_code")
                or "acquisition_route_unavailable"
            ),
            message=str(decision.get("reason") or error),
            category="access",
            retryable=False,
            details=decision,
        )
    else:
        status = ResultStatus.UNAVAILABLE
        public_error = PublicRecordsError(
            code="catalog_unavailable",
            message=str(error),
            category="catalog",
            retryable=False,
        )
    return PublicRecordsResult.failure(
        query,
        status,
        [public_error],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: VirginiaBeachTaxClient | None = None,
) -> PublicRecordsResult:
    if args.command == "routes":
        query = build_query("routes", None, limit=None, cursor=None)
        result = PublicRecordsResult.success(
            query,
            [_routes_record()],
            warnings=SOURCE_WARNINGS,
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, 1)
        return result

    try:
        criteria = _criteria_from_args(args)
    except PublicRecordsHTTPError as error:
        criteria = SearchCriteria()
        limit = 1 if args.command == "probe" else args.limit
        query = build_query(
            args.command,
            criteria,
            limit=limit,
            cursor=args.cursor,
        )
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    limit = 1 if args.command == "probe" else args.limit
    query = build_query(
        args.command,
        criteria,
        limit=limit,
        cursor=args.cursor,
    )
    try:
        access_contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args)
        )
        source_client = client or _new_client(args, access_contract)
        result = _query_records(
            args,
            query,
            criteria,
            source_client,
        )
    except (AcquisitionUnavailableError, CatalogError, OSError) as error:
        result = _access_failure(query, error)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
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

    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=(
            f"Virginia Beach delinquent tax {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return

    print(
        f"Virginia Beach delinquent tax {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "public_record_route_map":
            print(f"  {len(record['routes'])} related official routes")
            continue
        amounts = record.get("amounts") or {}
        print(
            "  "
            f"{record.get('gpin') or '?'} | "
            f"{record.get('tax_year') or '?'} "
            f"bill {record.get('bill_number') or '?'}-"
            f"{record.get('installment') or '?'} | "
            f"{record.get('owner_observation', {}).get('raw_name') or '?'} | "
            f"${amounts.get('total_due') or 0:,.2f}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_search_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--owner", help="Owner-name contains filter")
    parser.add_argument(
        "--address",
        help="Situs or mailing-address contains filter",
    )
    parser.add_argument("--gpin", help="Exact geographic parcel identifier")
    parser.add_argument("--bill-number", help="Exact tax bill number")
    parser.add_argument("--tax-year", type=int)
    parser.add_argument("--installment", choices=("1", "2"))
    parser.add_argument(
        "--district",
        help="District number, such as 1 or D01",
    )
    parser.add_argument("--min-total-due", type=_decimal_arg)
    parser.add_argument("--max-total-due", type=_decimal_arg)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional result ceiling; omitted retrieves the full match set",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation cursor from a previous result",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Requested ArcGIS page size",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source and acquisition catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and reviewed access decisions",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the official Virginia Beach delinquent real-estate tax table"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser(
        "search",
        help="Search across tax-installment fields or combine filters",
    )
    search_parser.add_argument(
        "query",
        nargs="?",
        help="Contains search across names, addresses, GPIN, description, and bill",
    )
    _add_search_filters(search_parser)
    _add_shared_arguments(search_parser)

    for command, help_text in (
        ("owner", "Search published primary-owner observations"),
        ("address", "Search situs and mailing-address observations"),
        ("parcel", "Look up an exact GPIN"),
        ("bill", "Look up an exact tax bill number"),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_search_filters(command_parser)
        _add_shared_arguments(command_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Verify item identity, layer schema, count, and one live row",
    )
    _add_search_filters(probe_parser)
    _add_shared_arguments(probe_parser)

    routes_parser = subparsers.add_parser(
        "routes",
        help="Show official complementary sources and their join keys",
    )
    add_output_args(routes_parser)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command != "routes":
        if args.limit is not None and args.limit <= 0:
            parser.error("limit must be positive when provided")
        if args.page_size <= 0:
            parser.error("page-size must be positive")
        if args.timeout <= 0:
            parser.error("timeout must be positive")
        if args.minimum_interval < 0:
            parser.error("minimum-interval must not be negative")

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
