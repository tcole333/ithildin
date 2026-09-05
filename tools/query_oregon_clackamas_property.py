#!/usr/bin/env python3
"""Query official Clackamas County property account and taxlot sources.

The adapter keeps the county's two live representations distinct:

* Aumentum AscendWeb account, party, value, tax, receipt, and sale detail; and
* the CMap taxlot FeatureServer geometry and selected assessment attributes.

Examples:
    uv run python tools/query_oregon_clackamas_property.py sources
    uv run python tools/query_oregon_clackamas_property.py search MAIN \
        --source us-or-clackamas-county-ascendweb-property --field address
    uv run python tools/query_oregon_clackamas_property.py detail 01092276 \
        --source us-or-clackamas-county-ascendweb-property
    uv run python tools/query_oregon_clackamas_property.py account 01092276
    uv run python tools/query_oregon_clackamas_property.py probe --all
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from typing import Any, Callable, Mapping

import requests
from bs4 import BeautifulSoup

try:
    from tools import oregon_arcgis_keyset as arcgis_shared
    from tools import oregon_ascendweb as ascend_shared
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
    from tools.public_records_http import (
        PublicRecordsHTTPError,
        SourceSchemaError,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    import oregon_arcgis_keyset as arcgis_shared
    import oregon_ascendweb as ascend_shared
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
    from public_records_http import (
        PublicRecordsHTTPError,
        SourceSchemaError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_GEOID = "41005"
COUNTY_NAME = "Clackamas County, Oregon"

ASCEND_SOURCE_ID = "us-or-clackamas-county-ascendweb-property"
CMAP_SOURCE_ID = "us-or-clackamas-county-cmap-taxlots"
SOURCE_IDS = (ASCEND_SOURCE_ID, CMAP_SOURCE_ID)

ASCEND_ROOT_URL = "https://ascendweb.clackamas.us/"
ASCEND_DETAIL_URL = f"{ASCEND_ROOT_URL}ParcelInfo.aspx"
ASCEND_VERSION_OBSERVED = "4.5.0.0"
ASCEND_OBSERVED_MAIN_RESULTS = 982
ASCEND_OBSERVED_MAIN_WORDING = (
    "982 records returned from your search input."
)
ASCEND_OBSERVED_MAIN_NATIVE_INPUT = "%MAIN%"
ASCEND_SENTINEL_ACCOUNT = "01092276"
ASCEND_SENTINEL_TAXLOT = "52E08C 01500"
ASCEND_CURSOR_PREFIX = "oregon-clackamas-ascend:v1:"

CMAP_ITEM_ID = "ba94373905a54b82b05946e164e38ec9"
CMAP_LAYER_URL = (
    "https://services3.arcgis.com/I2eWXOndpF9m8oKC/ArcGIS/rest/services/"
    "Taxlots_CMap/FeatureServer/0"
)
CMAP_OBSERVED_COUNT = 163_925
CMAP_OBSERVED_MAX_RECORD_COUNT = 2_000
CMAP_OBSERVED_OBJECT_ID = 109_341

CMAP_PAGE_URL = "https://www.clackamas.us/cmap"
GIS_DATA_PORTAL_URL = "https://www.clackamas.us/gis/data-portal"
VALUE_HISTORY_URL = "https://apps.clackamas.us/taxhistory/"
TAX_STATEMENTS_URL = "https://apps.clackamas.us/taxstatements/"
RECORDING_URL = "https://www.clackamas.us/recording"
ASSESSMENT_URL = "https://www.clackamas.us/at"

OUTPUT_SCHEMA_VERSION = "oregon-clackamas-property/1.0"
PROBE_SCHEMA_VERSION = "oregon-clackamas-property-probe/1.0"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_PAGE_SIZE = 1_000


CLACKAMAS_ASCEND_MANIFEST = ascend_shared.AscendTenantManifest(
    source_id=ASCEND_SOURCE_ID,
    jurisdiction=COUNTY_NAME,
    county_geoid=COUNTY_GEOID,
    root_url=ASCEND_ROOT_URL,
    home_path="",
    detail_path="ParcelInfo.aspx",
    observed_versions=(ASCEND_VERSION_OBSERVED,),
    form_aliases={
        "account": "_ctl0:MainContent:mParcelID2",
        "address": "_ctl0:MainContent:mStreetAddress",
        "city": "_ctl0:MainContent:mCity",
        "state": "_ctl0:MainContent:mStateProvince",
        "postal_code": "_ctl0:MainContent:mPostalCode",
        "submit": "_ctl0:MainContent:mSubmit",
    },
    submit_value="Account Info",
    form_action_suffixes=("/",),
    result_table_id="MainContent_mGrid",
    result_headers=("Parcel Number", "Name", "Location Address"),
    result_columns=("account_number", "party_name", "situs_address"),
    result_count_selectors=(
        "#MainContent_mMessageLabel",
        "#MainContent_mMessage",
    ),
    result_count_pattern=r"([0-9,]+)\s+records?\s+returned\s+from\s+your\s+search\s+input",
    detail_link_parameter="parcel_number",
    detail_table_ids={
        "general_information": "MainContent_mGeneralInformation",
        "tax_rate": "MainContent_mTaxRate",
        "property_characteristics": "MainContent_mPropertyCharacteristics",
        "related_properties": "MainContent_mRelatedProperties",
        "parties": "MainContent_mParties",
        "property_values": "MainContent_mPropertyValues",
        "active_exemptions": "MainContent_mActiveExemptions",
        "events": "MainContent_mEvents",
        "installments": "MainContent_mGrid",
        "receipts": "MainContent_mReceipts",
        "sales_history": "MainContent_mSalesHistory",
        "property_details": "MainContent_mPropertyDetails",
    },
    identity_mode="elements",
    identity_account_label="Account Number",
    identity_account_id="MainContent_mParcelNumber",
    identity_address_id="MainContent_mSitusAddress",
    installment_link_id="MainContent_mInstallments",
    installment_event_target="_ctl0$MainContent$mInstallments",
    installment_year_field="_ctl0:MainContent:mDifferentYear",
)

CMAP_FIELDS = (
    "OBJECTID",
    "MAPNUMBER",
    "MAPACRES",
    "PARCEL_NUMBER",
    "TLNO",
    "SITUS_CITY",
    "SITUS_ZIP",
    "SITUS",
    "ASSESSEDVAL",
    "BLDGVAL",
    "LANDVAL",
    "TOTALVAL",
    "BEDROOMS",
    "FULL_BATHS",
    "LANDCLASS",
    "FP_ACRES",
    "YEARBLT",
    "YR_ASSESSED",
    "SALE_PRICE",
    "DOC_DATE",
    "DOC_NUMBER",
    "DOC_TYPE",
    "LIVING_AREA",
    "TAXCODE",
    "JURNAME",
    "LINK",
    "SITUS_FULL",
    "TRACT",
    "Shape__Area",
    "Shape__Length",
)

CLACKAMAS_CMAP_MANIFEST = arcgis_shared.ArcGISLayerManifest(
    source_id=CMAP_SOURCE_ID,
    name="Clackamas County CMap Taxlots",
    layer_url=CMAP_LAYER_URL,
    layer_id=0,
    service_item_id=CMAP_ITEM_ID,
    expected_layer_name="tax_taxlot_cmap",
    object_id_field="OBJECTID",
    required_fields=CMAP_FIELDS,
    source_crs_wkids=(102100, 3857),
    record_kind="current_assessment_taxlot",
    publisher="Clackamas County GIS",
    observed_count=CMAP_OBSERVED_COUNT,
)

HTMLPage = ascend_shared.HTMLPage

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Clackamas County",
    metadata={"state_fips": STATE_FIPS},
)

SOURCE_METADATA = {
    ASCEND_SOURCE_ID: SourceMetadata(
        source_id=ASCEND_SOURCE_ID,
        name="Clackamas County Aumentum AscendWeb Property Search",
        source_role="official_county_property_assessment_tax_and_sale_detail",
        base_url=ASCEND_ROOT_URL,
        dataset_id="clackamas-ascendweb-4.5",
        metadata={
            "publisher": "Clackamas County Assessment and Taxation",
            "county_geoid": COUNTY_GEOID,
            "platform_family": "aumentum_ascendweb",
            "native_root_path": "/",
            "owner_name_behavior": (
                "source_native_taxpayer_and_owner_party_rows_observed"
            ),
        },
    ),
    CMAP_SOURCE_ID: SourceMetadata(
        source_id=CMAP_SOURCE_ID,
        name="Clackamas County CMap Taxlots",
        source_role="official_county_current_taxlot_geometry_and_selected_attributes",
        base_url=CMAP_LAYER_URL,
        dataset_id=CMAP_ITEM_ID,
        metadata={
            "publisher": "Clackamas County GIS",
            "county_geoid": COUNTY_GEOID,
            "platform_family": "arcgis_feature_service",
            "source_crs": "EPSG:3857 (native WKID 102100)",
            "output_geometry_crs": "EPSG:4326",
            "owner_name_behavior": "no_owner_field_in_layer_schema",
        },
    ),
}

CATALOG_METADATA: Mapping[str, Mapping[str, Any]] = {
    ASCEND_SOURCE_ID: {
        "source_id": ASCEND_SOURCE_ID,
        "category": "property",
        "record_types": [
            "property_account",
            "assessment_value_history",
            "tax_receipt",
            "property_sale",
        ],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "web_form",
        "auth": "none",
        "official": True,
        "url": ASCEND_ROOT_URL,
        "query_tool": "tools/query_oregon_clackamas_property.py",
        "pagination": "query_schema_snapshot_bound_local_window",
    },
    CMAP_SOURCE_ID: {
        "source_id": CMAP_SOURCE_ID,
        "category": "property",
        "record_types": ["current_assessment_taxlot"],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "rest_api",
        "auth": "none",
        "official": True,
        "url": CMAP_LAYER_URL,
        "query_tool": "tools/query_oregon_clackamas_property.py",
        "pagination": "query_schema_boundary_bound_object_id_keyset",
        "supports_geometry": True,
    },
}

OFFICIAL_COMPLEMENTS = (
    {
        "kind": "county_property_map",
        "url": CMAP_PAGE_URL,
        "adds": [
            "building_and_tax_context",
            "jurisdictions",
            "hazards",
            "survey_and_tax_map_documents",
        ],
        "owner_lookup_statement": (
            "The CMap page says property owner names are not published online "
            "and directs owner questions to Assessment and Taxation."
        ),
    },
    {
        "kind": "county_gis_downloads",
        "url": GIS_DATA_PORTAL_URL,
        "adds": ["downloadable_taxlots_and_other_county_gis_layers"],
    },
    {
        "kind": "county_measure_50_value_history",
        "url": VALUE_HISTORY_URL,
        "adds": ["real_market_and_maximum_assessed_value_history"],
    },
    {
        "kind": "county_online_tax_statements",
        "url": TAX_STATEMENTS_URL,
        "adds": ["current_and_archived_property_tax_statements"],
    },
    {
        "kind": "county_recording_research_and_copies",
        "url": RECORDING_URL,
        "adds": ["recorded_real_property_instruments", "research_and_copy_route"],
    },
    {
        "kind": "county_assessment_contact",
        "url": ASSESSMENT_URL,
        "adds": ["assessment_questions_and_owner_lookup_contact"],
    },
)

ASCEND_WARNINGS = (
    "Broad AscendWeb searches return one complete native table; continuation "
    "windows are bound to the criteria, schema, and table snapshot.",
    "The value table's source-native Tax Year 1 through Tax Year 5 headings "
    "are retained because the detail response does not identify calendar years.",
)

CMAP_WARNINGS = (
    "CMap taxlots and AscendWeb account detail are county components joined "
    "by exact parcel number and normalized taxlot.",
    "The CMap layer has no owner-name field; the AscendWeb component separately "
    "publishes source-native taxpayer and owner party rows.",
)


class SourceSelectionError(ValueError):
    """Structured source-selection, field, or cursor failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
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


class ClackamasAscendClient(ascend_shared.AscendWebClient):
    """Clackamas binding for shared bounded AscendWeb mechanics."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            CLACKAMAS_ASCEND_MANIFEST,
            session=session,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_attempts=retry_attempts,
            sleeper=sleeper,
            clock=clock,
        )


class ClackamasCMapClient(arcgis_shared.BoundedArcGISClient):
    """Clackamas binding for shared bounded ArcGIS keyset mechanics."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            CLACKAMAS_CMAP_MANIFEST,
            session=session,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_attempts=retry_attempts,
            sleeper=sleeper,
            clock=clock,
        )


def parse_ascend_home(
    html: str,
    *,
    source_url: str = ASCEND_ROOT_URL,
) -> ascend_shared.AscendHomeContract:
    return ascend_shared.parse_home(
        CLACKAMAS_ASCEND_MANIFEST,
        html,
        source_url=source_url,
    )


def parse_ascend_search(
    html: str,
    *,
    source_url: str,
) -> ascend_shared.AscendSearchPage:
    return ascend_shared.parse_search(
        CLACKAMAS_ASCEND_MANIFEST,
        html,
        source_url=source_url,
    )


def _native_value_history(soup: BeautifulSoup, *, source_url: str) -> list[dict[str, Any]]:
    table_id = CLACKAMAS_ASCEND_MANIFEST.detail_table_ids["property_values"]
    rows = ascend_shared.table_rows(soup.select_one(f"#{table_id}"))
    expected_headers = (
        "Value Type",
        "Tax Year 1",
        "Tax Year 2",
        "Tax Year 3",
        "Tax Year 4",
        "Tax Year 5",
    )
    if not rows or tuple(rows[0]) != expected_headers:
        raise SourceSchemaError(
            "Clackamas AscendWeb property-value labels changed",
            url=source_url,
            details={"headers": rows[0] if rows else []},
        )
    values: list[dict[str, Any]] = []
    for row in rows[1:]:
        if len(row) != len(expected_headers):
            raise SourceSchemaError(
                "Clackamas AscendWeb property-value row shape changed",
                url=source_url,
                details={"row": row},
            )
        values.append(
            {
                "value_type": ascend_shared.clean(row[0]),
                "native_columns": [
                    {
                        "native_label": expected_headers[index],
                        "raw": ascend_shared.clean(row[index]),
                        "amount": ascend_shared.number(row[index]),
                    }
                    for index in range(1, len(expected_headers))
                ],
            }
        )
    return values


def _normalize_parties(soup: BeautifulSoup) -> list[dict[str, Any]]:
    table_id = CLACKAMAS_ASCEND_MANIFEST.detail_table_ids["parties"]
    parties: list[dict[str, Any]] = []
    for row in ascend_shared.row_table_or_message(soup, table_id):
        if "message" in row:
            continue
        parties.append(
            {
                "role": (ascend_shared.clean(row.get("role")) or "").casefold(),
                "percent_raw": ascend_shared.clean(row.get("percent")),
                "percent_value": ascend_shared.number(row.get("percent")),
                "name": ascend_shared.clean(row.get("name")),
                "address": ascend_shared.clean(row.get("address")),
            }
        )
    return parties


def _normalize_receipts(soup: BeautifulSoup) -> list[dict[str, Any]]:
    table_id = CLACKAMAS_ASCEND_MANIFEST.detail_table_ids["receipts"]
    records: list[dict[str, Any]] = []
    for row in ascend_shared.row_table_or_message(soup, table_id):
        if "message" in row:
            continue
        records.append(
            {
                **row,
                "date_iso": ascend_shared.date_iso(row.get("date")),
                "amount_applied_value": ascend_shared.number(
                    row.get("amount_applied_to_parcel")
                ),
                "total_amount_due_value": ascend_shared.number(
                    row.get("total_amount_due")
                ),
                "receipt_total_value": ascend_shared.number(row.get("receipt_total")),
                "change_value": ascend_shared.number(row.get("change")),
            }
        )
    return records


def _normalize_sales(soup: BeautifulSoup) -> list[dict[str, Any]]:
    table_id = CLACKAMAS_ASCEND_MANIFEST.detail_table_ids["sales_history"]
    records: list[dict[str, Any]] = []
    for row in ascend_shared.row_table_or_message(soup, table_id):
        if "message" in row:
            continue
        records.append(
            {
                **row,
                "sale_date_iso": ascend_shared.date_iso(row.get("sale_date")),
                "entry_date_iso": ascend_shared.date_iso(row.get("entry_date")),
                "recording_date_iso": ascend_shared.date_iso(
                    row.get("recording_date")
                ),
                "recording_number": ascend_shared.clean(row.get("recording_number")),
                "sale_amount_value": ascend_shared.number(row.get("sale_amount")),
            }
        )
    return records


def _normalize_installments(
    html: str | None,
    *,
    source_url: str | None,
) -> dict[str, Any] | None:
    if html is None:
        return None
    assert source_url is not None
    soup = BeautifulSoup(html, "lxml")
    table_id = CLACKAMAS_ASCEND_MANIFEST.detail_table_ids["installments"]
    rows = ascend_shared.row_table_or_message(soup, table_id)
    normalized: list[dict[str, Any]] = []
    message = None
    for row in rows:
        if "message" in row:
            message = row["message"]
            continue
        normalized.append(
            {
                **row,
                "charged_value": ascend_shared.number(row.get("charged")),
                "minimum_value": ascend_shared.number(row.get("minimum")),
                "balance_due_value": ascend_shared.number(row.get("balance_due")),
                "due_date_iso": ascend_shared.date_iso(row.get("due_date")),
            }
        )
    return {
        "source_url": ascend_shared.canonical_url(
            CLACKAMAS_ASCEND_MANIFEST,
            source_url,
        ),
        "rows": normalized,
        "message": message,
    }


def parse_ascend_detail(
    html: str,
    *,
    source_url: str,
    installment_html: str | None = None,
    installment_source_url: str | None = None,
) -> dict[str, Any]:
    """Parse rich Clackamas account detail while retaining native labels."""

    canonical_source = ascend_shared.canonical_url(
        CLACKAMAS_ASCEND_MANIFEST,
        source_url,
    )
    soup = BeautifulSoup(html, "lxml")
    account, address, identity_labels = ascend_shared.parse_identity(
        CLACKAMAS_ASCEND_MANIFEST,
        soup,
        source_url=canonical_source,
    )
    ids = CLACKAMAS_ASCEND_MANIFEST.detail_table_ids
    general = ascend_shared.key_value_table(soup, ids["general_information"])
    parties = _normalize_parties(soup)
    values = _native_value_history(soup, source_url=canonical_source)
    sales = _normalize_sales(soup)
    recording_numbers = [
        value
        for value in (
            ascend_shared.clean(row.get("recording_number")) for row in sales
        )
        if value
    ]
    alternate = ascend_shared.clean(general.get("alternate_property"))
    return {
        "record_kind": "property_account",
        "source_id": ASCEND_SOURCE_ID,
        "source_record_id": account,
        "canonical_ref": canonical_property_ref(
            ASCEND_SOURCE_ID,
            COUNTY_GEOID,
            "property_account",
            account,
        ),
        "jurisdiction_geoid": COUNTY_GEOID,
        "account_number": account,
        "alternate_map_taxlot": alternate,
        "situs_address_raw": address,
        "identity_contract": {
            "mode": "elements",
            "labels": list(identity_labels),
            "account_element_id": (
                CLACKAMAS_ASCEND_MANIFEST.identity_account_id
            ),
            "address_element_id": (
                CLACKAMAS_ASCEND_MANIFEST.identity_address_id
            ),
        },
        "general_information": general,
        "tax_rate": ascend_shared.row_table_or_message(soup, ids["tax_rate"]),
        "property_characteristics": ascend_shared.key_value_table(
            soup,
            ids["property_characteristics"],
        ),
        "related_properties": ascend_shared.row_table_or_message(
            soup,
            ids["related_properties"],
        ),
        "parties": parties,
        "owner_name_component_behavior": {
            "component": ASCEND_SOURCE_ID,
            "published_party_rows": bool(parties),
            "roles_observed": sorted(
                {party["role"] for party in parties if party["role"]}
            ),
        },
        "value_history": values,
        "value_column_contract": {
            "labels": [
                "Tax Year 1",
                "Tax Year 2",
                "Tax Year 3",
                "Tax Year 4",
                "Tax Year 5",
            ],
            "calendar_years_identified_in_response": False,
        },
        "active_exemptions": ascend_shared.row_table_or_message(
            soup,
            ids["active_exemptions"],
        ),
        "events": ascend_shared.row_table_or_message(soup, ids["events"]),
        "receipts": _normalize_receipts(soup),
        "sales": sales,
        "property_details": ascend_shared.row_table_or_message(
            soup,
            ids["property_details"],
        ),
        "installment_detail": _normalize_installments(
            installment_html,
            source_url=installment_source_url,
        ),
        "join_candidates": {
            CMAP_SOURCE_ID: {
                "account_number": account,
                "map_taxlot": alternate,
                "relationship": "exact_account_and_normalized_taxlot_join",
            },
            "us-or-clackamas-county-recorder": {
                "recording_numbers": recording_numbers,
                "relationship": "recorded_instrument_detail_complement",
            },
        },
        "source_url": canonical_source,
    }


def _sql_text(value: Any) -> str:
    return str(value).replace("'", "''")


def _cmap_where(query: str, field: str) -> str:
    value = ascend_shared.clean(query)
    if value is None:
        raise SourceSelectionError("blank_query", "query must not be blank")
    escaped = _sql_text(value)
    if field == "object_id":
        if not value.isdigit():
            raise SourceSelectionError(
                "invalid_object_id",
                "object-ID searches require digits",
            )
        return f"OBJECTID = {int(value)}"
    if field == "account":
        return f"PARCEL_NUMBER = '{escaped}'"
    if field == "map_taxlot":
        return f"TLNO = '{escaped}'"
    if field == "recording":
        return f"DOC_NUMBER = '{escaped}'"
    if field == "tax_code":
        return f"TAXCODE = '{escaped}'"
    if field == "city":
        return f"UPPER(SITUS_CITY) LIKE '%{_sql_text(value.upper())}%'"
    if field == "address":
        return (
            f"(UPPER(SITUS) LIKE '%{_sql_text(value.upper())}%' OR "
            f"UPPER(SITUS_FULL) LIKE '%{_sql_text(value.upper())}%')"
        )
    if field == "auto":
        clauses = [
            f"PARCEL_NUMBER = '{escaped}'",
            f"TLNO = '{escaped}'",
            f"DOC_NUMBER = '{escaped}'",
            f"UPPER(SITUS_FULL) LIKE '%{_sql_text(value.upper())}%'",
        ]
        if value.isdigit():
            clauses.append(f"OBJECTID = {int(value)}")
        return f"({' OR '.join(clauses)})"
    raise SourceSelectionError(
        "unsupported_field",
        f"CMap does not support field {field!r}",
        details={
            "supported_fields": [
                "auto",
                "account",
                "map_taxlot",
                "address",
                "city",
                "recording",
                "tax_code",
                "object_id",
            ]
        },
    )


def _ascend_parameters(
    query: str,
    field: str,
    *,
    city: str,
    state: str,
    postal_code: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    value = ascend_shared.clean(query)
    if value is None:
        raise SourceSelectionError("blank_query", "query must not be blank")
    selected = field
    if selected == "auto":
        selected = "account" if re.fullmatch(r"[0-9]{6,10}", value) else "address"
    if selected not in {"account", "address"}:
        raise SourceSelectionError(
            "unsupported_field",
            f"Clackamas AscendWeb does not support field {field!r}",
            details={"supported_fields": ["auto", "account", "address"]},
        )
    native_address = value
    if selected == "address" and "%" not in value:
        native_address = f"%{value}%"
    parameters = {
        "account": value if selected == "account" else "",
        "address": native_address if selected == "address" else "",
        "city": city,
        "state": state,
        "postal_code": postal_code,
    }
    criteria = {"field": selected, **parameters}
    return parameters, criteria


def _normalize_cmap(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = dict(arcgis_shared.feature_attributes(feature))
    object_id = attributes.get("OBJECTID")
    if isinstance(object_id, bool) or not isinstance(object_id, int):
        raise SourceSchemaError(
            "Clackamas CMap feature lacks integer OBJECTID",
            url=CMAP_LAYER_URL,
            details={"OBJECTID": object_id},
        )
    account = ascend_shared.clean(attributes.get("PARCEL_NUMBER"))
    map_taxlot = ascend_shared.clean(attributes.get("TLNO"))
    native_id = str(object_id)
    geometry = feature.get("geometry") if geometry_requested else None
    return {
        "record_kind": "current_assessment_taxlot",
        "source_id": CMAP_SOURCE_ID,
        "source_record_id": native_id,
        "canonical_ref": canonical_property_ref(
            CMAP_SOURCE_ID,
            COUNTY_GEOID,
            "current_assessment_taxlot",
            native_id,
        ),
        "jurisdiction_geoid": COUNTY_GEOID,
        "object_id": object_id,
        "account_number": account,
        "map_taxlot": map_taxlot,
        "map_number": ascend_shared.clean(attributes.get("MAPNUMBER")),
        "map_acres": attributes.get("MAPACRES"),
        "situs": {
            "address": ascend_shared.clean(attributes.get("SITUS")),
            "city": ascend_shared.clean(attributes.get("SITUS_CITY")),
            "postal_code": attributes.get("SITUS_ZIP"),
            "full": ascend_shared.clean(attributes.get("SITUS_FULL")),
        },
        "assessment_values": {
            "assessed": attributes.get("ASSESSEDVAL"),
            "building": attributes.get("BLDGVAL"),
            "land": attributes.get("LANDVAL"),
            "total": attributes.get("TOTALVAL"),
            "assessment_year": attributes.get("YR_ASSESSED"),
        },
        "building": {
            "bedrooms": attributes.get("BEDROOMS"),
            "full_baths": attributes.get("FULL_BATHS"),
            "year_built": attributes.get("YEARBLT"),
            "living_area_sq_ft": attributes.get("LIVING_AREA"),
            "land_class": ascend_shared.clean(attributes.get("LANDCLASS")),
        },
        "latest_sale_or_deed": {
            "sale_price": attributes.get("SALE_PRICE"),
            "document_date_raw": ascend_shared.clean(attributes.get("DOC_DATE")),
            "document_number": ascend_shared.clean(attributes.get("DOC_NUMBER")),
            "document_type": ascend_shared.clean(attributes.get("DOC_TYPE")),
        },
        "tax_code": ascend_shared.clean(attributes.get("TAXCODE")),
        "named_jurisdiction": ascend_shared.clean(attributes.get("JURNAME")),
        "jurisdiction_link": ascend_shared.clean(attributes.get("LINK")),
        "census_tract": ascend_shared.clean(attributes.get("TRACT")),
        "owner_name_component_behavior": {
            "component": CMAP_SOURCE_ID,
            "owner_field_present": False,
            "cmap_page_statement_url": CMAP_PAGE_URL,
        },
        "geometry": geometry,
        "geometry_crs": "EPSG:4326" if geometry is not None else None,
        "source_response_schema_fingerprint": schema_fingerprint,
        "join_candidates": {
            ASCEND_SOURCE_ID: {
                "account_number": account,
                "map_taxlot": map_taxlot,
                "relationship": "exact_account_and_normalized_taxlot_join",
            },
            "us-or-clackamas-county-recorder": {
                "recording_number": ascend_shared.clean(
                    attributes.get("DOC_NUMBER")
                ),
                "relationship": "recorded_instrument_detail_complement",
            },
        },
        "raw_attributes": attributes,
        "source_url": CMAP_LAYER_URL,
    }


def _source_record(source_id: str) -> dict[str, Any]:
    metadata = SOURCE_METADATA[source_id].to_dict()
    if source_id == ASCEND_SOURCE_ID:
        observed = {
            "observed_at": "2026-07-29",
            "platform_version": ASCEND_VERSION_OBSERVED,
            "tenant_host": CLACKAMAS_ASCEND_MANIFEST.hostname,
            "tenant_root_path": CLACKAMAS_ASCEND_MANIFEST.root_path,
            "representative_complete_search": {
                "street": "MAIN",
                "native_input": ASCEND_OBSERVED_MAIN_NATIVE_INPUT,
                "record_count": ASCEND_OBSERVED_MAIN_RESULTS,
                "native_count_wording": ASCEND_OBSERVED_MAIN_WORDING,
            },
            "sentinel": {
                "account_number": ASCEND_SENTINEL_ACCOUNT,
                "map_taxlot": ASCEND_SENTINEL_TAXLOT,
            },
            "native_manifest": CLACKAMAS_ASCEND_MANIFEST.contract_record(),
            "value_column_labels": [
                "Tax Year 1",
                "Tax Year 2",
                "Tax Year 3",
                "Tax Year 4",
                "Tax Year 5",
            ],
            "identity_elements": {
                "account": "MainContent_mParcelNumber",
                "address": "MainContent_mSitusAddress",
            },
        }
        search_fields = ["auto", "account", "address"]
        required_fields = list(
            CLACKAMAS_ASCEND_MANIFEST.form_aliases.values()
        )
        warnings = list(ASCEND_WARNINGS)
    else:
        observed = {
            "observed_at": "2026-07-29",
            "component_count": CMAP_OBSERVED_COUNT,
            "max_record_count": CMAP_OBSERVED_MAX_RECORD_COUNT,
            "native_crs_wkids": [102100, 3857],
            "sentinel": {
                "account_number": ASCEND_SENTINEL_ACCOUNT,
                "map_taxlot": ASCEND_SENTINEL_TAXLOT,
                "object_id": CMAP_OBSERVED_OBJECT_ID,
            },
            "native_manifest": CLACKAMAS_CMAP_MANIFEST.contract_record(),
            "update_description": "Tuesday at noon",
        }
        search_fields = [
            "auto",
            "account",
            "map_taxlot",
            "address",
            "city",
            "recording",
            "tax_code",
            "object_id",
        ]
        required_fields = list(CMAP_FIELDS)
        warnings = list(CMAP_WARNINGS)
    return {
        **metadata,
        "catalog_metadata": dict(CATALOG_METADATA[source_id]),
        "search_fields": search_fields,
        "required_fields": required_fields,
        "observed_contract": observed,
        "complementary_official_routes": [dict(item) for item in OFFICIAL_COMPLEMENTS],
        "warnings": warnings,
    }


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "platform_family": "clackamas_county_property_components",
        "jurisdiction": JURISDICTION.to_dict(),
        "sources": [_source_record(source_id) for source_id in SOURCE_IDS],
        "component_reconciliation": {
            "county_page_statement": (
                "The CMap page says property owner names are not published "
                "online."
            ),
            "cmap_observation": "The ArcGIS layer schema has no owner-name field.",
            "ascend_observation": (
                "The sentinel AscendWeb detail contains Taxpayer and Owner "
                "party rows."
            ),
            "interpretation": (
                "These observations describe different county components; "
                "their source-native behavior is retained separately."
            ),
        },
        "process_learnings": [
            {
                "scope": "component_specific_publication",
                "learning": (
                    "County-level statements can describe one application while "
                    "a separate official application exposes different fields."
                ),
            },
            {
                "scope": "exact_component_join",
                "learning": (
                    "Parcel number is compared exactly and taxlot is compared "
                    "after whitespace normalization across AscendWeb and CMap."
                ),
            },
            {
                "scope": "native_value_labels",
                "learning": (
                    "Placeholder value headings are retained when the response "
                    "does not map them to calendar years."
                ),
            },
        ],
    }


def _build_query(
    source_id: str,
    *,
    operation: str,
    parameters: Mapping[str, Any],
    requested_limit: int | None,
    cursor: str | None,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsQuery:
    query_metadata: dict[str, Any] = {
        "adapter": "tools/query_oregon_clackamas_property.py",
        "pagination": (
            "query_schema_snapshot_bound_local_window"
            if source_id == ASCEND_SOURCE_ID
            else "query_schema_boundary_bound_object_id_keyset"
        ),
    }
    if access_decision is not None:
        query_metadata["access_decision"] = dict(access_decision)
    return PublicRecordsQuery(
        source=SOURCE_METADATA[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata=query_metadata,
        ),
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
        log_search(canonical_json(query.to_dict()), query.source.source_id, count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _selection_failure(
    query: PublicRecordsQuery,
    error: SourceSelectionError,
    *,
    warnings: tuple[str, ...],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=warnings,
    )


def _unexpected_failure(
    query: PublicRecordsQuery,
    error: Exception,
    *,
    code: str,
    warnings: tuple[str, ...],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.SOURCE_CHANGED,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category="source_schema",
                retryable=False,
            )
        ],
        warnings=warnings,
    )


def _new_ascend_client(args: argparse.Namespace) -> ClackamasAscendClient:
    return ClackamasAscendClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _new_cmap_client(args: argparse.Namespace) -> ClackamasCMapClient:
    return ClackamasCMapClient(
        page_size=args.page_size,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _selected_client(client: Any, source_id: str) -> Any:
    if isinstance(client, Mapping):
        return client.get(source_id)
    return client


def _ascend_result(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    operation = args.command
    query = _build_query(
        ASCEND_SOURCE_ID,
        operation=operation,
        parameters={
            "selector": args.query,
            "field": getattr(args, "field", "account"),
            "city": getattr(args, "city", ""),
            "state": getattr(args, "state", ""),
            "postal_code": getattr(args, "postal_code", ""),
            "tax_year": getattr(args, "tax_year", None),
        },
        requested_limit=1 if operation == "detail" else args.limit,
        cursor=getattr(args, "cursor", None),
        access_decision=access_decision,
    )
    try:
        active_client = client or _new_ascend_client(args)
        if operation == "detail":
            account = ascend_shared.clean(args.query)
            if account is None:
                raise SourceSelectionError(
                    "blank_query",
                    "account number must not be blank",
                )
            detail, installment = active_client.detail(
                account,
                tax_year=args.tax_year,
            )
            record = parse_ascend_detail(
                detail.html,
                source_url=detail.source_url,
                installment_html=installment.html if installment else None,
                installment_source_url=(
                    installment.source_url if installment else None
                ),
            )
            if record["account_number"] != account:
                raise SourceSchemaError(
                    "Clackamas AscendWeb returned a different account",
                    url=detail.source_url,
                    details={
                        "requested": account,
                        "returned": record["account_number"],
                    },
                )
            record["retrieval_snapshot"] = {
                "native_response": "exact_account_detail",
                "tax_year_postback_requested": args.tax_year,
                "installment_detail_returned": installment is not None,
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=ASCEND_WARNINGS,
            )
        else:
            parameters, criteria = _ascend_parameters(
                args.query,
                args.field,
                city=args.city,
                state=args.state,
                postal_code=args.postal_code,
            )
            page = active_client.search(**parameters)
            soup = BeautifulSoup(page.html, "lxml")
            if soup.select_one(
                f"#{CLACKAMAS_ASCEND_MANIFEST.identity_account_id}"
            ):
                if args.cursor:
                    raise SourceSelectionError(
                        "cursor_query_mismatch",
                        "exact account detail has no result-table continuation",
                    )
                record = parse_ascend_detail(
                    page.html,
                    source_url=page.source_url,
                )
                record["retrieval_snapshot"] = {
                    "native_response": "exact_account_detail",
                    "total_matching_records": 1,
                    "window_returned_records": 1,
                    "continuation_available": False,
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    warnings=ASCEND_WARNINGS,
                )
            else:
                parsed = parse_ascend_search(
                    page.html,
                    source_url=page.source_url,
                )
                effective_limit = (
                    args.limit
                    if args.limit is not None
                    else max(1, parsed.total_count)
                )
                try:
                    window = ascend_shared.slice_complete_search(
                        CLACKAMAS_ASCEND_MANIFEST,
                        parsed,
                        cursor_prefix=ASCEND_CURSOR_PREFIX,
                        criteria=criteria,
                        limit=effective_limit,
                        cursor=args.cursor,
                    )
                except ValueError as error:
                    raise SourceSelectionError(
                        "cursor_query_mismatch",
                        str(error),
                    ) from error
                records = [dict(record) for record in window.records]
                snapshot = {
                    "native_response": "complete_search_table",
                    "total_matching_records": parsed.total_count,
                    "window_offset": window.offset,
                    "window_returned_records": len(records),
                    "continuation_available": window.next_cursor is not None,
                    "schema_fingerprint": parsed.schema_fingerprint,
                    "snapshot_fingerprint": parsed.snapshot_fingerprint,
                }
                for record in records:
                    record.update(
                        {
                            "record_kind": "property_account_search_observation",
                            "source_id": ASCEND_SOURCE_ID,
                            "canonical_ref": canonical_property_ref(
                                ASCEND_SOURCE_ID,
                                COUNTY_GEOID,
                                "property_account",
                                str(record["account_number"]),
                            ),
                            "retrieval_snapshot": snapshot,
                        }
                    )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=window.next_cursor,
                    warnings=ASCEND_WARNINGS,
                )
    except SourceSelectionError as error:
        result = _selection_failure(query, error, warnings=ASCEND_WARNINGS)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=ASCEND_WARNINGS)
    except (TypeError, ValueError) as error:
        result = _unexpected_failure(
            query,
            error,
            code="normalization_failed",
            warnings=ASCEND_WARNINGS,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _cmap_result(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    field = args.field
    if args.command == "detail" and field == "auto":
        field = "account"
    query = _build_query(
        CMAP_SOURCE_ID,
        operation=args.command,
        parameters={
            "selector": args.query,
            "field": field,
            "geometry": args.geometry,
        },
        requested_limit=args.limit,
        cursor=args.cursor,
        access_decision=access_decision,
    )
    try:
        where = _cmap_where(args.query, field)
        active_client = client or _new_cmap_client(args)
        batch = arcgis_shared.fetch_batch(
            active_client,
            CLACKAMAS_CMAP_MANIFEST,
            adapter_slug="clackamas-cmap",
            operation=args.command,
            where=where,
            # fetch_batch still sizes each request from client.page_size;
            # this sentinel makes an omitted caller bound stop on source
            # exhaustion rather than creating a local continuation window.
            limit=args.limit if args.limit is not None else sys.maxsize,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        records = [
            _normalize_cmap(
                feature,
                schema_fingerprint=batch.schema_fingerprint,
                geometry_requested=args.geometry,
            )
            for feature in batch.features
        ]
        snapshot = {
            "total_matching_records_at_retrieval": batch.total_count,
            "records_inside_cursor_boundary": batch.bounded_count,
            "boundary_object_id": batch.boundary_object_id,
            "last_object_id": batch.last_object_id,
            "window_returned_records": len(records),
            "continuation_available": batch.next_cursor is not None,
            "pages_fetched": batch.pages_fetched,
            "schema_fingerprint": batch.schema_fingerprint,
            "count_changed_inside_boundary_since_cursor": (
                batch.count_changed_since_cursor
            ),
        }
        for record in records:
            record["retrieval_snapshot"] = snapshot
        warnings = list(CMAP_WARNINGS)
        if batch.count_changed_since_cursor:
            warnings.append(
                "The count inside the original object-ID boundary changed "
                "while the same boundary remained in force."
            )
        result = PublicRecordsResult.success(
            query,
            records,
            next_cursor=batch.next_cursor,
            warnings=warnings,
        )
    except SourceSelectionError as error:
        result = _selection_failure(query, error, warnings=CMAP_WARNINGS)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=CMAP_WARNINGS)
    except ValueError as error:
        result = _selection_failure(
            query,
            SourceSelectionError("cursor_query_mismatch", str(error)),
            warnings=CMAP_WARNINGS,
        )
    except TypeError as error:
        result = _unexpected_failure(
            query,
            error,
            code="normalization_failed",
            warnings=CMAP_WARNINGS,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _source_result(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    query = _build_query(
        args.source,
        operation="source",
        parameters={"source_id": args.source},
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    return PublicRecordsResult.success(query, [_source_record(args.source)])


def _ascend_probe(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        ASCEND_SOURCE_ID,
        operation="probe",
        parameters={
            "sentinel_account": args.sentinel_account,
            "broad_search": args.broad_search,
        },
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    try:
        active_client = client or _new_ascend_client(args)
        home = active_client.fetch_home()
        contract = parse_ascend_home(home.html, source_url=home.source_url)
        if contract.version not in CLACKAMAS_ASCEND_MANIFEST.observed_versions:
            raise SourceSchemaError(
                "Clackamas AscendWeb version differs from the observed manifest",
                url=home.source_url,
                details={
                    "observed": contract.version,
                    "expected": list(
                        CLACKAMAS_ASCEND_MANIFEST.observed_versions
                    ),
                },
            )
        detail, _ = active_client.detail(args.sentinel_account)
        record = parse_ascend_detail(
            detail.html,
            source_url=detail.source_url,
        )
        if record["account_number"] != args.sentinel_account:
            raise SourceSchemaError(
                "Clackamas AscendWeb sentinel account changed",
                url=detail.source_url,
            )
        broad = None
        if args.broad_search:
            search_page = active_client.search(
                address=ASCEND_OBSERVED_MAIN_NATIVE_INPUT
            )
            parsed = parse_ascend_search(
                search_page.html,
                source_url=search_page.source_url,
            )
            broad = {
                "query": "MAIN",
                "field": "address",
                "record_count": parsed.total_count,
                "expected_observation": ASCEND_OBSERVED_MAIN_RESULTS,
                "schema_fingerprint": parsed.schema_fingerprint,
                "snapshot_fingerprint": parsed.snapshot_fingerprint,
            }
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": ASCEND_SOURCE_ID,
                    "platform_version": contract.version,
                    "home_schema_fingerprint": contract.schema_fingerprint,
                    "form_fields": list(contract.form_fields),
                    "form_action": contract.form_action,
                    "sentinel": {
                        "account_number": record["account_number"],
                        "map_taxlot": record["alternate_map_taxlot"],
                        "party_roles": sorted(
                            {
                                party["role"]
                                for party in record["parties"]
                                if party["role"]
                            }
                        ),
                        "value_column_labels": (
                            record["value_column_contract"]["labels"]
                        ),
                        "receipt_count": len(record["receipts"]),
                        "sale_count": len(record["sales"]),
                    },
                    "broad_search": broad,
                }
            ],
            warnings=ASCEND_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=ASCEND_WARNINGS)
    except (TypeError, ValueError) as error:
        result = _unexpected_failure(
            query,
            error,
            code="probe_failed",
            warnings=ASCEND_WARNINGS,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _cmap_probe(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        CMAP_SOURCE_ID,
        operation="probe",
        parameters={"sentinel_account": args.sentinel_account},
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    try:
        active_client = client or _new_cmap_client(args)
        metadata = active_client.fetch_metadata()
        schema_value, maximum = arcgis_shared.metadata_contract(
            CLACKAMAS_CMAP_MANIFEST,
            metadata,
        )
        count = active_client.fetch_count("1=1")
        features = active_client.fetch_page(
            where=f"PARCEL_NUMBER = '{_sql_text(args.sentinel_account)}'",
            record_count=2,
            return_geometry=False,
        )
        normalized = [
            _normalize_cmap(
                feature,
                schema_fingerprint=schema_value,
                geometry_requested=False,
            )
            for feature in features
        ]
        if not normalized or any(
            record["account_number"] != args.sentinel_account
            for record in normalized
        ):
            raise SourceSchemaError(
                "Clackamas CMap sentinel account changed",
                url=CMAP_LAYER_URL,
            )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": CMAP_SOURCE_ID,
                    "component_total_count": count,
                    "observed_count_reference": CMAP_OBSERVED_COUNT,
                    "schema_fingerprint": schema_value,
                    "layer_name": metadata.get("name"),
                    "layer_id": metadata.get("id"),
                    "service_item_id": metadata.get("serviceItemId"),
                    "max_record_count": maximum,
                    "source_crs": "EPSG:3857 (native WKID 102100)",
                    "sentinel": normalized,
                    "owner_name_component_behavior": {
                        "owner_field_present": False,
                        "ascend_party_rows_observed": True,
                        "cmap_page_statement_url": CMAP_PAGE_URL,
                    },
                }
            ],
            warnings=CMAP_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=CMAP_WARNINGS)
    except (TypeError, ValueError) as error:
        result = _unexpected_failure(
            query,
            error,
            code="probe_failed",
            warnings=CMAP_WARNINGS,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _account_payload(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> dict[str, Any]:
    account = ascend_shared.clean(args.query)
    if account is None:
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "status": "unavailable",
            "account_number": None,
            "components": [],
            "reconciliation": None,
            "errors": [
                {
                    "code": "blank_query",
                    "message": "account number must not be blank",
                    "category": "selection",
                    "retryable": False,
                    "details": {},
                }
            ],
        }
    ascend_args = argparse.Namespace(**vars(args))
    ascend_args.command = "detail"
    ascend_args.source = ASCEND_SOURCE_ID
    ascend_args.field = "account"
    ascend_args.limit = 1
    ascend_args.cursor = None
    cmap_args = argparse.Namespace(**vars(args))
    cmap_args.command = "detail"
    cmap_args.source = CMAP_SOURCE_ID
    cmap_args.field = "account"
    cmap_args.limit = args.limit
    cmap_args.cursor = None
    ascend_result = _ascend_result(
        ascend_args,
        client=_selected_client(client, ASCEND_SOURCE_ID),
        access_decision=access_decision,
        log_results=log_results,
    )
    cmap_result = _cmap_result(
        cmap_args,
        client=_selected_client(client, CMAP_SOURCE_ID),
        access_decision=access_decision,
        log_results=log_results,
    )
    ascend_records = list(ascend_result.records)
    cmap_records = list(cmap_result.records)
    ascend_taxlot = (
        ascend_records[0].get("alternate_map_taxlot") if ascend_records else None
    )
    cmap_taxlots = [
        record.get("map_taxlot")
        for record in cmap_records
        if record.get("map_taxlot")
    ]
    def normalize_taxlot(value: Any) -> str:
        return re.sub(r"\s+", "", str(value or "")).upper()
    account_exact = bool(ascend_records and cmap_records) and all(
        record.get("account_number") == account
        for record in [*ascend_records, *cmap_records]
    )
    taxlot_matches = (
        bool(ascend_taxlot and cmap_taxlots)
        and normalize_taxlot(ascend_taxlot)
        in {normalize_taxlot(value) for value in cmap_taxlots}
    )
    successful = [
        result.status in {ResultStatus.OK, ResultStatus.NO_RESULTS}
        for result in (ascend_result, cmap_result)
    ]
    status = (
        "ok"
        if all(successful) and account_exact and taxlot_matches
        else "source_changed"
        if all(successful)
        else "partial"
        if any(successful)
        else "unavailable"
    )
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "status": status,
        "account_number": account,
        "components": [ascend_result.to_dict(), cmap_result.to_dict()],
        "reconciliation": {
            "join_keys": ["account_number", "normalized_map_taxlot"],
            "account_exact": account_exact,
            "ascend_map_taxlot": ascend_taxlot,
            "cmap_map_taxlots": cmap_taxlots,
            "map_taxlot_matches": taxlot_matches,
            "owner_name_behavior": {
                "ascend_party_rows": (
                    ascend_records[0].get("owner_name_component_behavior")
                    if ascend_records
                    else None
                ),
                "cmap_owner_field_present": False,
                "cmap_page_statement_url": CMAP_PAGE_URL,
            },
        },
    }


def _all_probe_payload(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> dict[str, Any]:
    components = [
        _ascend_probe(
            args,
            client=_selected_client(client, ASCEND_SOURCE_ID),
            access_decision=access_decision,
            log_results=log_results,
        ).to_dict(),
        _cmap_probe(
            args,
            client=_selected_client(client, CMAP_SOURCE_ID),
            access_decision=access_decision,
            log_results=log_results,
        ).to_dict(),
    ]
    successful = sum(
        component["status"] in {"ok", "no_results"}
        for component in components
    )
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": (
            "ok"
            if successful == len(components)
            else "partial"
            if successful
            else "unavailable"
        ),
        "components": components,
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute a source listing, source detail, query, account join, or probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "source":
        return _source_result(args, access_decision=access_decision)
    if args.command == "account":
        return _account_payload(
            args,
            client=client,
            access_decision=access_decision,
            log_results=log_results,
        )
    if args.command == "probe":
        if args.all_sources:
            return _all_probe_payload(
                args,
                client=client,
                access_decision=access_decision,
                log_results=log_results,
            )
        selected = _selected_client(client, args.source)
        if args.source == ASCEND_SOURCE_ID:
            return _ascend_probe(
                args,
                client=selected,
                access_decision=access_decision,
                log_results=log_results,
            )
        return _cmap_probe(
            args,
            client=selected,
            access_decision=access_decision,
            log_results=log_results,
        )
    selected = _selected_client(client, args.source)
    if args.source == ASCEND_SOURCE_ID:
        return _ascend_result(
            args,
            client=selected,
            access_decision=access_decision,
            log_results=log_results,
        )
    return _cmap_result(
        args,
        client=selected,
        access_decision=access_decision,
        log_results=log_results,
    )


def _payload(value: PublicRecordsResult | Mapping[str, Any]) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    records = payload.get("records")
    if isinstance(records, list):
        result_count = len(records)
    else:
        result_count = len(
            payload.get("components", payload.get("sources", []))
        )
    if write_output(
        payload,
        args,
        summary=f"Clackamas property {args.command}",
        result_count=result_count,
    ):
        return
    if args.command == "sources":
        print(f"Clackamas County property components: {len(payload['sources'])}")
        for source in payload["sources"]:
            print(f"  {source['source_id']} | {source['source_role']}")
        return
    if args.command == "probe" and args.all_sources:
        print(f"Clackamas County property probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | "
                f"{component['status']}"
            )
        return
    if args.command == "account":
        print(
            f"Clackamas property account join {payload['account_number']}: "
            f"{payload['status']}"
        )
        return
    rows = payload.get("records", [])
    print(
        f"Clackamas property {args.command}: "
        f"{payload.get('status')} ({len(rows)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in rows:
        identity = (
            record.get("account_number")
            or record.get("object_id")
            or record.get("source_id")
        )
        print(f"  {identity} | {record.get('record_kind')}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


SEARCH_FIELDS = (
    "auto",
    "account",
    "map_taxlot",
    "address",
    "city",
    "recording",
    "tax_code",
    "object_id",
)


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def _add_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        required=True,
        choices=SOURCE_IDS,
        help="Exact component-scoped source ID",
    )
    parser.add_argument("--field", choices=SEARCH_FIELDS, default="auto")
    parser.add_argument(
        "--limit",
        type=int,
        help="Return at most this many records; omitted traverses all matches",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation returned by the same component and criteria",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Include WGS84 geometry from the CMap component",
    )
    parser.add_argument("--city", default="")
    parser.add_argument("--state", default="")
    parser.add_argument("--postal-code", default="")
    parser.set_defaults(tax_year=None)
    _add_transport_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Clackamas County AscendWeb accounts and CMap taxlots"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List component contracts and complementary official routes",
    )
    add_output_args(sources)

    source = sub.add_parser("source", help="Show one component contract")
    source.add_argument("--source", required=True, choices=SOURCE_IDS)
    add_output_args(source)

    search = sub.add_parser("search", help="Search one selected component")
    search.add_argument("query")
    _add_query_arguments(search)

    detail = sub.add_parser("detail", help="Fetch exact component detail")
    detail.add_argument("query")
    _add_query_arguments(detail)
    detail.add_argument(
        "--tax-year",
        type=int,
        help="AscendWeb installment-year postback",
    )

    account = sub.add_parser(
        "account",
        help="Join exact AscendWeb and CMap account observations",
    )
    account.add_argument("query")
    account.add_argument(
        "--limit",
        type=int,
        help="Bound the CMap side of the joined account lookup",
    )
    account.add_argument("--geometry", action="store_true")
    account.add_argument("--tax-year", type=int)
    account.set_defaults(
        field="account",
        cursor=None,
        city="",
        state="",
        postal_code="",
    )
    _add_transport_arguments(account)

    probe = sub.add_parser("probe", help="Run bounded component health probes")
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source", choices=SOURCE_IDS)
    selection.add_argument("--all", action="store_true", dest="all_sources")
    probe.set_defaults(all_sources=False)
    probe.add_argument(
        "--sentinel-account",
        default=ASCEND_SENTINEL_ACCOUNT,
    )
    probe.add_argument(
        "--broad-search",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also validate the complete MAIN result table",
    )
    _add_transport_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for name in ("page_size", "retry_attempts"):
        if getattr(args, name, 1) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if (
        getattr(args, "limit", None) is not None
        and args.limit <= 0
    ):
        parser.error("--limit must be positive")
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
