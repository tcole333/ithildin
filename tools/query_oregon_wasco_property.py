#!/usr/bin/env python3
"""Query Wasco County assessment, taxlot, and survey-record components.

The adapter keeps the anonymous AscendWeb account, the county taxlot feature
layer, and each SurveyorData layer independently attributable.  Exact-account
joins validate both the assessor account and normalized native map-taxlot.

Examples:
    uv run python tools/query_oregon_wasco_property.py sources
    uv run python tools/query_oregon_wasco_property.py search 9450 \
        --source us-or-wasco-county-ascendweb-property --field account
    uv run python tools/query_oregon_wasco_property.py account 9450
    uv run python tools/query_oregon_wasco_property.py search "LC 179" \
        --source us-or-wasco-county-surveyor-land-corners
    uv run python tools/query_oregon_wasco_property.py attachments \
        us-or-wasco-county-surveyor-land-corners 1
    uv run python tools/query_oregon_wasco_property.py probe --all
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

from bs4 import BeautifulSoup

try:
    from tools import oregon_ascendweb as ascend
    from tools import oregon_arcgis_keyset as arcgis
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
        PublicRecordsHTTPError,
        SourceSchemaError,
        failure_result,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    import oregon_arcgis_keyset as arcgis
    import oregon_ascendweb as ascend
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
        PublicRecordsHTTPError,
        SourceSchemaError,
        failure_result,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_GEOID = "41065"
COUNTY_NAME = "Wasco County, Oregon"
PUBLISHER = "Wasco County Assessment and Taxation / Wasco County GIS"

ASCEND_SOURCE_ID = "us-or-wasco-county-ascendweb-property"
TAXLOT_SOURCE_ID = "us-or-wasco-county-taxlots"
ROAD_RECORDS_SOURCE_ID = "us-or-wasco-county-surveyor-road-records"
FILE_CABINET_SOURCE_ID = (
    "us-or-wasco-county-surveyor-file-cabinet-surveys"
)
ROLL_MAPS_SOURCE_ID = "us-or-wasco-county-surveyor-roll-maps"
COMMISSIONERS_SOURCE_ID = (
    "us-or-wasco-county-surveyor-commissioner-records"
)
LAND_CORNERS_SOURCE_ID = "us-or-wasco-county-surveyor-land-corners"
PLATS_SOURCE_ID = "us-or-wasco-county-surveyor-plats"
SUBDIVISIONS_SOURCE_ID = "us-or-wasco-county-surveyor-subdivisions"
SURVEY_BOOK_SOURCE_ID = "us-or-wasco-county-surveyor-survey-book"

SURVEY_SOURCE_IDS = (
    ROAD_RECORDS_SOURCE_ID,
    FILE_CABINET_SOURCE_ID,
    ROLL_MAPS_SOURCE_ID,
    COMMISSIONERS_SOURCE_ID,
    LAND_CORNERS_SOURCE_ID,
    PLATS_SOURCE_ID,
    SUBDIVISIONS_SOURCE_ID,
    SURVEY_BOOK_SOURCE_ID,
)
SOURCE_IDS = (ASCEND_SOURCE_ID, TAXLOT_SOURCE_ID, *SURVEY_SOURCE_IDS)

ASCEND_ROOT_URL = "https://public.co.wasco.or.us/webtax/"
ASCEND_VERSION_OBSERVED = "4.0.2.7"
ASCEND_CURSOR_PREFIX = "oregon-wasco-ascend:v1:"
ASCEND_OBSERVED_MAIN_COUNT = 182
ASCEND_SENTINEL_ACCOUNT = "9450"
ASCEND_SENTINEL_ALTERNATE = "01S13 E25CB06000 00"
TAXLOT_SENTINEL_MAP = "1S 13E 25 CB 6000"
TAXLOT_SENTINEL_OBJECT_ID = 6_575_814
ASCEND_MAX_HTML_BYTES = 16 * 1024 * 1024

TAXLOT_LAYER_URL = (
    "https://public.co.wasco.or.us/gisserver/rest/services/"
    "Taxlots/FeatureServer/0"
)
TAXLOT_SERVICE_ITEM_ID = "8ee9e99db376485aa4e0dee883f4c889"
TAXLOT_OBSERVED_COUNT = 15_515
SURVEY_SERVICE_ROOT = (
    "https://public.co.wasco.or.us/gisserver/rest/services/"
    "SurveyorData/FeatureServer"
)
SURVEY_SERVICE_ITEM_ID = "148e89cb157844b5bafecd2180922dbb"
WASCO_HELION_SOURCE_ID = "us-or-wasco-helion-recorder"

COUNTY_GIS_PORTAL_URL = "https://public.co.wasco.or.us/gisportal/"
STATE_ARCHIVE_INVENTORY_URL = (
    "https://sos.oregon.gov/archives/county-records-guide/Pages/"
    "wasco-inventory.aspx"
)
SURVEY_SERVICE_DIRECTORY_URL = f"{SURVEY_SERVICE_ROOT}/layers"

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_PAGE_SIZE = 1_000
OUTPUT_SCHEMA_VERSION = "oregon-wasco-property/1.0"
PROBE_SCHEMA_VERSION = "oregon-wasco-property-probe/1.0"


ASCEND_MANIFEST = ascend.AscendTenantManifest(
    source_id=ASCEND_SOURCE_ID,
    jurisdiction=COUNTY_NAME,
    county_geoid=COUNTY_GEOID,
    root_url=ASCEND_ROOT_URL,
    home_path="default.aspx",
    detail_path="ParcelInfo.aspx",
    observed_versions=(ASCEND_VERSION_OBSERVED,),
    form_aliases={
        "account": "mParcelID2",
        "alternate": "mAlternateParcelID",
        "address": "mStreetAddress",
        "city": "mCity",
        "state": "mStateProvince",
        "postal_code": "mPostalCode",
        "submit": "mSubmit",
    },
    submit_value="Parcel Info",
    form_action_suffixes=("default.aspx",),
    result_table_id="mGrid",
    result_headers=("Parcel Number", "Name", "Location Address"),
    result_columns=("account_number", "name", "situs_address"),
    result_count_selectors=("#Table2",),
    result_count_pattern=r"([0-9,]+)\s+records?\s+returned",
    detail_link_parameter="parcel_number",
    detail_table_ids={
        "general_information": "mGeneralInformation",
        "tax_rate": "mTaxRate",
        "property_characteristics": "mPropertyCharacteristics",
        "related_properties": "mRelatedProperties",
        "property_values": "mPropertyValues",
        "active_exemptions": "mActiveExemptions",
        "events": "mEvents",
        "receipts": "mReceipts",
        "sales_history": "mSalesHistory",
        "property_details": "mPropertyDetails",
        "installments": "mGrid",
    },
    identity_mode="table",
    identity_account_label="Account Number",
    identity_table_id="ParcelSitusTable",
    installment_link_id="mInstallments",
    installment_event_target="mInstallments",
    installment_year_field="mDifferentYear",
    maximum_html_bytes=ASCEND_MAX_HTML_BYTES,
)

TAXLOT_MANIFEST = arcgis.ArcGISLayerManifest(
    source_id=TAXLOT_SOURCE_ID,
    name="Wasco County Taxlots",
    layer_url=TAXLOT_LAYER_URL,
    layer_id=0,
    service_item_id=TAXLOT_SERVICE_ITEM_ID,
    expected_layer_name="Taxlots",
    object_id_field="OBJECTID",
    required_fields=(
        "OBJECTID",
        "AccountNum",
        "MapTaxlot",
        "Taxpayer",
        "MailingAddress1",
        "MailingAddress2",
        "MailingAddress3",
        "MailingCity",
        "MailingState",
        "MailingZIP",
        "CalculatedAcres",
    ),
    source_crs_wkids=(2913,),
    record_kind="county_taxlot",
    publisher="Wasco County GIS / Wasco County Assessor",
    observed_count=TAXLOT_OBSERVED_COUNT,
)


@dataclass(frozen=True)
class SurveyLayerDefinition:
    source_id: str
    layer_id: int
    name: str
    record_kind: str
    required_fields: tuple[str, ...]
    search_fields: tuple[str, ...]
    identity_fields: tuple[str, ...]
    identity_pattern: str
    observed_count: int
    has_attachments: bool = False
    representation_note: str | None = None

    @property
    def manifest(self) -> arcgis.ArcGISLayerManifest:
        return arcgis.ArcGISLayerManifest(
            source_id=self.source_id,
            name=f"Wasco County SurveyorData — {self.name}",
            layer_url=f"{SURVEY_SERVICE_ROOT}/{self.layer_id}",
            layer_id=self.layer_id,
            service_item_id=SURVEY_SERVICE_ITEM_ID,
            expected_layer_name=self.name,
            object_id_field="OBJECTID",
            required_fields=self.required_fields,
            source_crs_wkids=(2913,),
            record_kind=self.record_kind,
            publisher="Wasco County Surveyor / Wasco County GIS",
            observed_count=self.observed_count,
            has_attachments=self.has_attachments,
        )


SURVEY_LAYERS = {
    ROAD_RECORDS_SOURCE_ID: SurveyLayerDefinition(
        source_id=ROAD_RECORDS_SOURCE_ID,
        layer_id=47,
        name="Road Record Numbers",
        record_kind="surveyor_road_record_index",
        required_fields=("ANNO", "OBJECTID"),
        search_fields=("ANNO",),
        identity_fields=("ANNO",),
        identity_pattern=r"^[A-Z]+[- ]?[0-9]+(?:[- ][0-9]+)*$",
        observed_count=835,
        representation_note=(
            "Spatial/index representation; the archive inventory describes "
            "road jackets and road-record books as complementary documents."
        ),
    ),
    FILE_CABINET_SOURCE_ID: SurveyLayerDefinition(
        source_id=FILE_CABINET_SOURCE_ID,
        layer_id=48,
        name="File Cabinet Surveyor Records",
        record_kind="surveyor_file_cabinet_index",
        required_fields=("ANNO", "OBJECTID"),
        search_fields=("ANNO",),
        identity_fields=("ANNO",),
        identity_pattern=r"^CS\s*[0-9]+$",
        observed_count=3_402,
        representation_note=(
            "Spatial/index representation of county-surveyor CS surveys."
        ),
    ),
    ROLL_MAPS_SOURCE_ID: SurveyLayerDefinition(
        source_id=ROLL_MAPS_SOURCE_ID,
        layer_id=50,
        name="Roll Maps",
        record_kind="surveyor_roll_map_index",
        required_fields=("ANNO", "OBJECTID"),
        search_fields=("ANNO",),
        identity_fields=("ANNO",),
        identity_pattern=r"^[A-Z]+-[0-9]+(?:-[0-9]+)+$",
        observed_count=2_976,
        representation_note=(
            "Spatial/index representation of the office's historic roll-map "
            "or cubbyhole collection; scans/physical records are complementary."
        ),
    ),
    COMMISSIONERS_SOURCE_ID: SurveyLayerDefinition(
        source_id=COMMISSIONERS_SOURCE_ID,
        layer_id=52,
        name="Commissioners Records",
        record_kind="commissioner_journal_spatial_index",
        required_fields=("ANNO", "OBJECTID"),
        search_fields=("ANNO",),
        identity_fields=("ANNO",),
        identity_pattern=r"^[A-Z]+[- ]?[0-9]+$",
        observed_count=74,
        representation_note=(
            "Point index for pre-1960s Commissioners Journal references."
        ),
    ),
    LAND_CORNERS_SOURCE_ID: SurveyLayerDefinition(
        source_id=LAND_CORNERS_SOURCE_ID,
        layer_id=53,
        name="Land Corners",
        record_kind="land_corner_and_scan",
        required_fields=(
            "OBJECTID",
            "ANNO",
            "DESCRIPTION",
            "WEB_COLOR",
            "SCAN_NAM",
            "ToAttach",
        ),
        search_fields=("ANNO", "DESCRIPTION", "SCAN_NAM", "ToAttach"),
        identity_fields=("ANNO", "SCAN_NAM"),
        identity_pattern=r"^LC\s*[0-9]+$",
        observed_count=1_394,
        has_attachments=True,
        representation_note=(
            "Feature attributes and source-hosted land-corner scan attachment."
        ),
    ),
    PLATS_SOURCE_ID: SurveyLayerDefinition(
        source_id=PLATS_SOURCE_ID,
        layer_id=54,
        name="Plats",
        record_kind="plat_outline_index",
        required_fields=(
            "OBJECTID",
            "PlatName",
            "DocNumber",
            "Source",
            "SourceType",
        ),
        search_fields=("PlatName", "DocNumber", "Source", "SourceType"),
        identity_fields=("PlatName", "DocNumber"),
        identity_pattern=r"^[0-9]{4}-[0-9]+$",
        observed_count=1_279,
        representation_note=(
            "Plat outline/index maintained in the county service; the source "
            "credits Lane County for this layer."
        ),
    ),
    SUBDIVISIONS_SOURCE_ID: SurveyLayerDefinition(
        source_id=SUBDIVISIONS_SOURCE_ID,
        layer_id=55,
        name="Subdivision Outlines",
        record_kind="subdivision_outline",
        required_fields=("OBJECTID", "Shape__Length", "LINETYPE"),
        search_fields=("OBJECTID", "LINETYPE"),
        identity_fields=("OBJECTID", "LINETYPE"),
        identity_pattern=r"^[0-9]+$",
        observed_count=1_607,
        representation_note=(
            "Geometric subdivision-outline representation; it does not carry "
            "a subdivision-name field in the observed schema."
        ),
    ),
    SURVEY_BOOK_SOURCE_ID: SurveyLayerDefinition(
        source_id=SURVEY_BOOK_SOURCE_ID,
        layer_id=56,
        name="Survey Book Records",
        record_kind="survey_book_record_and_scan",
        required_fields=("OBJECTID", "ANNO", "COMMENTS", "FILEONLY"),
        search_fields=("ANNO", "COMMENTS", "FILEONLY"),
        identity_fields=("ANNO", "FILEONLY"),
        identity_pattern=r"^BK\s*[0-9]+\s+PG\s*[0-9]+$",
        observed_count=4_158,
        has_attachments=True,
        representation_note=(
            "Survey-book index with source-hosted scan attachments."
        ),
    ),
}

ARCGIS_MANIFESTS = {
    TAXLOT_SOURCE_ID: TAXLOT_MANIFEST,
    **{
        source_id: definition.manifest
        for source_id, definition in SURVEY_LAYERS.items()
    },
}

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Wasco County",
    metadata={"state_fips": STATE_FIPS},
)


def _source_metadata(source_id: str) -> SourceMetadata:
    if source_id == ASCEND_SOURCE_ID:
        return SourceMetadata(
            source_id=source_id,
            name="Wasco County AscendWeb Property Search",
            source_role="official_county_assessment_tax_and_sale_account_detail",
            base_url=ASCEND_MANIFEST.home_url,
            dataset_id="wasco-county-ascendweb",
            metadata={
                "publisher": "Wasco County Assessment and Taxation",
                "county_geoid": COUNTY_GEOID,
                "platform_family": "aumentum_ascendweb",
                "native_contract": ASCEND_MANIFEST.contract_record(),
                "detail_party_section_observed": False,
                "joins": {
                    TAXLOT_SOURCE_ID: ["account_number", "normalized_map_taxlot"],
                    WASCO_HELION_SOURCE_ID: [
                        "recording_number",
                        "excise_number",
                    ],
                },
            },
        )
    manifest = ARCGIS_MANIFESTS[source_id]
    if source_id == TAXLOT_SOURCE_ID:
        role = "official_county_taxlot_geometry_taxpayer_and_mailing_record"
        publisher = "Wasco County GIS / Wasco County Assessor"
        metadata: dict[str, Any] = {
            "publisher": publisher,
            "county_geoid": COUNTY_GEOID,
            "native_contract": manifest.contract_record(),
            "exact_join": {
                ASCEND_SOURCE_ID: ["AccountNum", "MapTaxlot"],
            },
        }
    else:
        definition = SURVEY_LAYERS[source_id]
        role = f"official_{definition.record_kind}"
        metadata = {
            "publisher": manifest.publisher,
            "county_geoid": COUNTY_GEOID,
            "native_contract": manifest.contract_record(),
            "identity_fields": list(definition.identity_fields),
            "identity_pattern": definition.identity_pattern,
            "representation_note": definition.representation_note,
            "complementary_routes": [
                {
                    "kind": "oregon_historical_county_records_inventory",
                    "url": STATE_ARCHIVE_INVENTORY_URL,
                    "adds": (
                        "coverage dates, physical holdings, and named scanned "
                        "road/survey series"
                    ),
                },
                {
                    "kind": "wasco_county_survey_service_directory",
                    "url": SURVEY_SERVICE_DIRECTORY_URL,
                    "adds": "live layer definitions and attachment capability",
                },
            ],
        }
    return SourceMetadata(
        source_id=source_id,
        name=manifest.name,
        source_role=role,
        base_url=manifest.layer_url,
        dataset_id=manifest.service_item_id,
        metadata=metadata,
    )


SOURCE_METADATA = {source_id: _source_metadata(source_id) for source_id in SOURCE_IDS}


class SourceSelectionError(ValueError):
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


class AscendWebClient(ascend.AscendWebClient):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(ASCEND_MANIFEST, **kwargs)


class WascoArcGISClient(arcgis.BoundedArcGISClient):
    pass


def _money(value: Any) -> int | float | None:
    return ascend.number(value)


def _parse_value_history(
    soup: BeautifulSoup,
    table_id: str,
) -> list[dict[str, Any]]:
    rows = ascend.table_rows(soup.select_one(f"#{table_id}"))
    if len(rows) < 2 or not rows[0] or rows[0][0] != "Value Type":
        return []
    labels = [ascend.clean(value) or "" for value in rows[0][1:]]
    history: list[dict[str, Any]] = []
    for row in rows[1:]:
        value_type = ascend.clean(row[0]) if row else None
        if not value_type:
            continue
        history.append(
            {
                "value_type": value_type,
                "values_by_tax_year": {
                    label: {
                        "raw": ascend.clean(row[index + 1])
                        if index + 1 < len(row)
                        else None,
                        "amount": _money(row[index + 1])
                        if index + 1 < len(row)
                        else None,
                    }
                    for index, label in enumerate(labels)
                },
            }
        )
    return history


def _message_aware_rows(
    soup: BeautifulSoup,
    table_id: str,
) -> list[dict[str, Any]]:
    rows = ascend.table_rows(soup.select_one(f"#{table_id}"))
    if len(rows) == 2 and len(rows[1]) == 1:
        message = ascend.clean(rows[1][0])
        return [{"message": message}] if message else []
    return ascend.row_table_or_message(soup, table_id)


def parse_ascend_detail(
    html: str,
    *,
    source_url: str,
    installment_html: str | None = None,
    installment_source_url: str | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    account, situs, identity_labels = ascend.parse_identity(
        ASCEND_MANIFEST,
        soup,
        source_url=source_url,
    )
    ids = ASCEND_MANIFEST.detail_table_ids
    general = ascend.key_value_table(soup, ids["general_information"])
    tax_rate = ascend.key_value_table(soup, ids["tax_rate"])
    characteristics = ascend.key_value_table(
        soup,
        ids["property_characteristics"],
    )
    parties_table = soup.select_one("#mParties")
    parties = ascend.row_table(soup, "mParties") if parties_table else []
    receipts = []
    for row in ascend.row_table(soup, ids["receipts"]):
        receipt_number = ascend.clean(row.get("receipt_no"))
        receipts.append(
            {
                **row,
                "date_iso": ascend.date_iso(row.get("date")),
                "receipt_number": receipt_number,
                "charged_value": _money(row.get("charged")),
                "amount_due_value": _money(row.get("amount_due")),
                "tendered_value": _money(row.get("tendered")),
                "change_value": _money(row.get("change")),
                "detail_url": (
                    f"{ASCEND_ROOT_URL}ReceiptDetail.aspx?receiptnumber="
                    f"{receipt_number}"
                    if receipt_number
                    else None
                ),
            }
        )
    sales = []
    recording_numbers: list[str] = []
    excise_numbers: list[str] = []
    for row in ascend.row_table(soup, ids["sales_history"]):
        recording = ascend.clean(row.get("recording_number"))
        excise = ascend.clean(row.get("excise_number"))
        if recording:
            recording_numbers.append(recording)
        if excise:
            excise_numbers.append(excise)
        sales.append(
            {
                **row,
                "transfer_date_iso": ascend.date_iso(row.get("transfer_date")),
                "receipt_date_iso": ascend.date_iso(row.get("receipt_date")),
                "sale_amount_value": _money(row.get("sale_amount")),
                "recording_number": recording,
                "excise_number": excise,
                "recorder_join": {
                    "source_id": WASCO_HELION_SOURCE_ID,
                    "recording_number": recording,
                    "excise_number": excise,
                    "relationship": "recorded_instrument_candidate",
                },
            }
        )
    property_rows = ascend.row_table(soup, ids["property_details"])
    property_detail = property_rows[0] if property_rows else {}
    installment = None
    if installment_html is not None:
        installment_soup = BeautifulSoup(installment_html, "lxml")
        rows = ascend.row_table(installment_soup, ids["installments"])
        installment = {
            "source_url": installment_source_url,
            "rows": [
                {
                    **row,
                    "charged_value": _money(row.get("charged")),
                    "minimum_value": _money(row.get("minimum")),
                    "balance_due_value": _money(row.get("balance_due")),
                    "due_date_iso": ascend.date_iso(row.get("due_date")),
                }
                for row in rows
            ],
        }
    alternate = ascend.clean(general.get("alternate_property"))
    canonical_ref = canonical_property_ref(
        ASCEND_SOURCE_ID,
        COUNTY_GEOID,
        "property_account",
        account,
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": ASCEND_SOURCE_ID,
        "source_url": source_url,
        "record_kind": "property_account",
        "account_number": account,
        "alternate_map_taxlot": alternate,
        "normalized_map_taxlot": normalize_wasco_taxlot(alternate),
        "situs_address": situs,
        "identity_labels": list(identity_labels),
        "general_information": general,
        "tax_rate": {
            **tax_rate,
            "total_rate_value": _money(tax_rate.get("total_rate")),
        },
        "property_characteristics": {
            **characteristics,
            "acreage_value": _money(characteristics.get("acreage")),
        },
        "party_section_observed": parties_table is not None,
        "parties": parties,
        "related_properties": ascend.row_table_or_message(
            soup,
            ids["related_properties"],
        ),
        "value_history": _parse_value_history(soup, ids["property_values"]),
        "active_exemptions": ascend.row_table_or_message(
            soup,
            ids["active_exemptions"],
        ),
        "events": _message_aware_rows(soup, ids["events"]),
        "tax_balance_observation": ascend.clean(soup.select_one("#mNoChargesOwing")),
        "receipts": receipts,
        "sales": sales,
        "property_details": {
            key: {"raw": value, "value": _money(value)}
            for key, value in property_detail.items()
        },
        "installment_detail": installment,
        "join_candidates": {
            TAXLOT_SOURCE_ID: {
                "account_number": account,
                "map_taxlot": alternate,
                "normalized_map_taxlot": normalize_wasco_taxlot(alternate),
                "relationship": "taxlot_geometry_taxpayer_and_mailing",
            },
            WASCO_HELION_SOURCE_ID: {
                "recording_numbers": recording_numbers,
                "excise_numbers": excise_numbers,
                "relationship": "recorded_instrument_detail",
            },
        },
        "source_response_schema_fingerprint": sha256_fingerprint(
            {
                "identity_labels": list(identity_labels),
                "table_ids": sorted(
                    str(table.get("id"))
                    for table in soup.select("table[id]")
                    if table.get("id")
                ),
            }
        ),
    }


def normalize_wasco_taxlot(value: Any) -> str | None:
    raw = ascend.clean(value)
    if raw is None:
        return None
    upper = raw.upper()
    native = re.fullmatch(
        r"0*([0-9]+)([NS])\s*0*([0-9]+)\s*([EW])\s*"
        r"([0-9]{2})\s*([A-Z]{0,2})\s*([0-9]{5})\s+([0-9]{2})",
        upper,
    )
    if native:
        (
            township_number,
            township_direction,
            range_number,
            range_direction,
            section,
            quarter,
            taxlot,
            extension,
        ) = native.groups()
        if extension != "00":
            return raw
        township = f"{int(township_number)}{township_direction}"
        range_value = f"{int(range_number)}{range_direction}"
    else:
        canonical = re.fullmatch(
            r"0*([0-9]+)([NS])\s+0*([0-9]+)([EW])\s+"
            r"([0-9]{2})(?:\s+([A-Z]{1,2}))?\s+0*([0-9]+)",
            upper,
        )
        if not canonical:
            return raw
        (
            township_number,
            township_direction,
            range_number,
            range_direction,
            section,
            quarter,
            taxlot,
        ) = canonical.groups()
        township = f"{int(township_number)}{township_direction}"
        range_value = f"{int(range_number)}{range_direction}"
    values = [township, range_value, section]
    if quarter:
        values.append(quarter)
    values.append(str(int(taxlot)))
    return " ".join(values)


def _sql(value: Any) -> str:
    return str(value).replace("'", "''")


def _taxlot_where(value: str, field: str) -> str:
    selected = field
    if selected == "auto":
        selected = "account" if value.isdigit() else (
            "taxlot" if re.search(r"\d+[NS].*\d+[EW]", value, re.I) else "owner"
        )
    if selected == "account":
        if not value.isdigit():
            raise SourceSelectionError(
                "invalid_account",
                "Wasco taxlot account lookup expects digits",
            )
        return f"AccountNum = {int(value)}"
    if selected == "taxlot":
        normalized = normalize_wasco_taxlot(value) or value
        return f"MapTaxlot = '{_sql(normalized)}'"
    if selected == "owner":
        return f"UPPER(Taxpayer) LIKE '%{_sql(value.upper())}%'"
    if selected == "object_id":
        if not value.isdigit():
            raise SourceSelectionError(
                "invalid_object_id",
                "object_id lookup expects digits",
            )
        return f"OBJECTID = {int(value)}"
    raise SourceSelectionError(
        "unsupported_field",
        f"Wasco taxlots do not support field {field}",
    )


def _survey_where(
    definition: SurveyLayerDefinition,
    value: str,
    field: str,
) -> str:
    if field == "all":
        return "1=1"
    selected = field
    if selected == "auto":
        selected = (
            "object_id"
            if value.isdigit() and definition.source_id == SUBDIVISIONS_SOURCE_ID
            else "text"
        )
    if selected == "object_id":
        if not value.isdigit():
            raise SourceSelectionError(
                "invalid_object_id",
                "object_id lookup expects digits",
            )
        return f"OBJECTID = {int(value)}"
    if selected == "line_type":
        if definition.source_id != SUBDIVISIONS_SOURCE_ID or not value.isdigit():
            raise SourceSelectionError(
                "invalid_line_type",
                "line_type applies only to numeric subdivision LINETYPE values",
            )
        return f"LINETYPE = {int(value)}"
    if selected == "text":
        clauses = []
        for field_name in definition.search_fields:
            if field_name in {"OBJECTID", "LINETYPE"}:
                continue
            clauses.append(
                f"UPPER({field_name}) LIKE '%{_sql(value.upper())}%'"
            )
        if not clauses:
            raise SourceSelectionError(
                "text_search_unavailable",
                f"{definition.name} has no observed text identity field",
            )
        return clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"
    if selected in definition.search_fields:
        if selected in {"OBJECTID", "LINETYPE"}:
            if not value.isdigit():
                raise SourceSelectionError(
                    "invalid_numeric_field",
                    f"{selected} expects digits",
                )
            return f"{selected} = {int(value)}"
        return f"UPPER({selected}) LIKE '%{_sql(value.upper())}%'"
    raise SourceSelectionError(
        "unsupported_field",
        f"{definition.name} does not expose field {field}",
    )


def _normalize_taxlot(
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    values = arcgis.feature_attributes(feature)
    account = values.get("AccountNum")
    native_id = str(account) if account is not None else str(values["OBJECTID"])
    ref = canonical_property_ref(
        TAXLOT_SOURCE_ID,
        COUNTY_GEOID,
        "county_taxlot",
        native_id,
    )
    mailing_parts = [
        ascend.clean(values.get(field))
        for field in (
            "MailingAddress1",
            "MailingAddress2",
            "MailingAddress3",
            "MailingCity",
            "MailingState",
            "MailingZIP",
        )
    ]
    record = {
        "canonical_ref": ref,
        "evidence_ref": ref,
        "source_id": TAXLOT_SOURCE_ID,
        "source_url": TAXLOT_LAYER_URL,
        "record_kind": "county_taxlot",
        "source_record_id": str(values["OBJECTID"]),
        "object_id": values["OBJECTID"],
        "account_number": native_id if account is not None else None,
        "map_taxlot": ascend.clean(values.get("MapTaxlot")),
        "normalized_map_taxlot": normalize_wasco_taxlot(values.get("MapTaxlot")),
        "taxpayer": ascend.clean(values.get("Taxpayer")),
        "mailing_address": {
            "raw_parts": mailing_parts,
            "formatted": ", ".join(part for part in mailing_parts if part) or None,
        },
        "calculated_acres": values.get("CalculatedAcres"),
        "source_response_schema_fingerprint": schema_value,
        "join_candidates": {
            ASCEND_SOURCE_ID: {
                "account_number": native_id if account is not None else None,
                "normalized_map_taxlot": normalize_wasco_taxlot(
                    values.get("MapTaxlot")
                ),
                "relationship": "assessment_account_detail",
            }
        },
    }
    if geometry_requested:
        record["geometry"] = feature.get("geometry")
        record["geometry_crs"] = "EPSG:4326"
    return record


def _normalize_survey(
    definition: SurveyLayerDefinition,
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    values = arcgis.feature_attributes(feature)
    object_id = int(values["OBJECTID"])
    identity = next(
        (
            ascend.clean(values.get(field))
            for field in definition.identity_fields
            if ascend.clean(values.get(field))
        ),
        str(object_id),
    )
    ref = canonical_property_ref(
        definition.source_id,
        COUNTY_GEOID,
        definition.record_kind,
        f"{identity}:{object_id}",
    )
    record = {
        "canonical_ref": ref,
        "evidence_ref": ref,
        "source_id": definition.source_id,
        "source_url": f"{SURVEY_SERVICE_ROOT}/{definition.layer_id}",
        "record_kind": definition.record_kind,
        "source_record_id": str(object_id),
        "object_id": object_id,
        "native_identity": identity,
        "attributes": dict(values),
        "source_response_schema_fingerprint": schema_value,
        "scan_attachment_listing_url": (
            definition.manifest.attachment_url(object_id)
            if definition.has_attachments
            else None
        ),
    }
    if geometry_requested:
        record["geometry"] = feature.get("geometry")
        record["geometry_crs"] = "EPSG:4326"
    return record


def _source_record(source_id: str) -> dict[str, Any]:
    metadata = SOURCE_METADATA[source_id].to_dict()
    if source_id == ASCEND_SOURCE_ID:
        observed = {
            "observed_at": "2026-07-29",
            "platform_version": ASCEND_VERSION_OBSERVED,
            "representative_complete_search": {
                "street": "MAIN",
                "record_count": ASCEND_OBSERVED_MAIN_COUNT,
            },
            "sentinel": {
                "account_number": ASCEND_SENTINEL_ACCOUNT,
                "alternate_map_taxlot": ASCEND_SENTINEL_ALTERNATE,
                "party_section_observed": False,
                "receipt_count": 7,
                "sale_count": 3,
            },
        }
        search_fields = ["account", "alternate", "address"]
    else:
        manifest = ARCGIS_MANIFESTS[source_id]
        observed = {
            "observed_at": "2026-07-29",
            "component_count": manifest.observed_count,
            "source_crs": "EPSG:2913",
            "supports_ordered_pagination": True,
            "has_attachments": manifest.has_attachments,
        }
        if source_id == TAXLOT_SOURCE_ID:
            observed["sentinel"] = {
                "account_number": ASCEND_SENTINEL_ACCOUNT,
                "map_taxlot": TAXLOT_SENTINEL_MAP,
                "object_id": TAXLOT_SENTINEL_OBJECT_ID,
            }
            search_fields = ["auto", "account", "taxlot", "owner", "object_id"]
        else:
            definition = SURVEY_LAYERS[source_id]
            observed["identity_pattern"] = definition.identity_pattern
            search_fields = [
                "auto",
                "all",
                "text",
                "object_id",
                *definition.search_fields,
            ]
    return {
        **metadata,
        "search_fields": sorted(set(search_fields)),
        "observed_contract": observed,
    }


def sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "platform_family": "wasco_county_property_and_survey_components",
        "jurisdiction": JURISDICTION.to_dict(),
        "sources": [_source_record(source_id) for source_id in SOURCE_IDS],
        "component_relationships": [
            {
                "left": ASCEND_SOURCE_ID,
                "right": TAXLOT_SOURCE_ID,
                "relationship": "same_county_account_complement",
                "join_keys": ["account_number", "normalized_map_taxlot"],
                "independent_corroboration": False,
            },
            {
                "left": ASCEND_SOURCE_ID,
                "right": WASCO_HELION_SOURCE_ID,
                "relationship": "assessment_sale_to_recorder_candidate",
                "join_keys": ["recording_number", "excise_number"],
            },
        ],
        "complementary_routes": [
            {
                "kind": "oregon_historical_county_records_inventory",
                "url": STATE_ARCHIVE_INVENTORY_URL,
                "adds": (
                    "named physical holdings, coverage dates, road jackets, "
                    "survey books, roll maps, and corner records"
                ),
            },
            {
                "kind": "wasco_county_gis_portal",
                "url": COUNTY_GIS_PORTAL_URL,
                "adds": "interactive spatial context across county layers",
            },
            {
                "kind": "wasco_helion_recorder",
                "source_id": WASCO_HELION_SOURCE_ID,
                "adds": "recorded instrument index/detail candidates",
            },
        ],
    }


def _query(
    source_id: str,
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _log(query: PublicRecordsQuery, result: PublicRecordsResult) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), query.source.source_id, count)
    except Exception as exc:
        print(f"Warning: search log was not updated: {exc}", file=sys.stderr)


def _ascend_search(
    args: argparse.Namespace,
    *,
    client: Any,
) -> PublicRecordsResult:
    parameters = {
        "value": args.value,
        "field": args.field,
        "city": args.city,
        "state": args.state,
        "postal_code": args.postal_code,
    }
    query = _query(
        ASCEND_SOURCE_ID,
        "search",
        parameters=parameters,
        limit=args.limit,
        cursor=args.cursor,
    )
    if args.field == "auto":
        field = "account" if args.value.isdigit() else "address"
    else:
        field = args.field
    if field not in {"account", "alternate", "address"}:
        raise SourceSelectionError(
            "unsupported_field",
            f"Wasco AscendWeb does not expose search field {field}",
        )
    request_values = {
        "account": "",
        "alternate": "",
        "address": "",
        "city": args.city or "",
        "state": args.state or "",
        "postal_code": args.postal_code or "",
    }
    request_values[field] = args.value
    page = client.search(**request_values)
    if urlparse(page.source_url).path.casefold().endswith("/parcelinfo.aspx"):
        record = parse_ascend_detail(page.html, source_url=page.source_url)
        return PublicRecordsResult.success(query, [record])
    parsed = ascend.parse_search(
        ASCEND_MANIFEST,
        page.html,
        source_url=page.source_url,
    )
    effective_limit = (
        args.limit
        if args.limit is not None
        else max(1, parsed.total_count)
    )
    sliced = ascend.slice_complete_search(
        ASCEND_MANIFEST,
        parsed,
        cursor_prefix=ASCEND_CURSOR_PREFIX,
        criteria=parameters,
        limit=effective_limit,
        cursor=args.cursor,
    )
    records = []
    for raw in sliced.records:
        account = str(raw["account_number"])
        ref = canonical_property_ref(
            ASCEND_SOURCE_ID,
            COUNTY_GEOID,
            "property_account_search_result",
            f"{account}:{raw['native_position']}",
        )
        records.append(
            {
                "canonical_ref": ref,
                "evidence_ref": ref,
                "source_id": ASCEND_SOURCE_ID,
                "source_url": parsed.source_url,
                "record_kind": "property_account_search_result",
                **dict(raw),
                "join_candidates": {
                    TAXLOT_SOURCE_ID: {
                        "account_number": account,
                        "relationship": "taxlot_geometry_taxpayer_and_mailing",
                    }
                },
            }
        )
    warnings = (
        f"Native complete table contains {sliced.total_count} records; "
        "this response is a deterministic local window.",
    ) if sliced.next_cursor else ()
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=sliced.next_cursor,
        warnings=warnings,
    )


def _arcgis_search(
    args: argparse.Namespace,
    *,
    client: Any,
) -> PublicRecordsResult:
    source_id = args.source
    manifest = ARCGIS_MANIFESTS[source_id]
    if source_id == TAXLOT_SOURCE_ID:
        where = _taxlot_where(args.value, args.field)
    else:
        where = _survey_where(SURVEY_LAYERS[source_id], args.value, args.field)
    query = _query(
        source_id,
        "search",
        parameters={
            "value": args.value,
            "field": args.field,
            "where": where,
            "geometry": args.geometry,
        },
        limit=args.limit,
        cursor=args.cursor,
    )
    batch = arcgis.fetch_batch(
        client,
        manifest,
        adapter_slug="wasco-property",
        operation="search",
        where=where,
        # fetch_batch still sizes each request from client.page_size; this
        # sentinel makes an omitted caller bound stop on source exhaustion.
        limit=args.limit if args.limit is not None else sys.maxsize,
        cursor=args.cursor,
        return_geometry=args.geometry,
    )
    if source_id == TAXLOT_SOURCE_ID:
        records = [
            _normalize_taxlot(
                feature,
                schema_value=batch.schema_fingerprint,
                geometry_requested=args.geometry,
            )
            for feature in batch.features
        ]
    else:
        definition = SURVEY_LAYERS[source_id]
        records = [
            _normalize_survey(
                definition,
                feature,
                schema_value=batch.schema_fingerprint,
                geometry_requested=args.geometry,
            )
            for feature in batch.features
        ]
    warnings = []
    if batch.count_changed_since_cursor:
        warnings.append(
            "Source count changed after the cursor was issued; keyset snapshot "
            "boundary was retained."
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=warnings,
    )


def _detail(
    args: argparse.Namespace,
    *,
    client: Any,
) -> PublicRecordsResult:
    query = _query(
        ASCEND_SOURCE_ID,
        "detail",
        parameters={"account_number": args.account, "tax_year": args.tax_year},
    )
    detail, installment = client.detail(args.account, tax_year=args.tax_year)
    record = parse_ascend_detail(
        detail.html,
        source_url=detail.source_url,
        installment_html=installment.html if installment else None,
        installment_source_url=installment.source_url if installment else None,
    )
    if record["account_number"] != args.account:
        raise SourceSchemaError(
            "Wasco AscendWeb detail account does not match the requested account",
            url=detail.source_url,
            details={
                "requested": args.account,
                "observed": record["account_number"],
            },
        )
    return PublicRecordsResult.success(query, [record])


def _account(
    args: argparse.Namespace,
    *,
    ascend_client: Any,
    taxlot_client: Any,
) -> PublicRecordsResult:
    query = _query(
        ASCEND_SOURCE_ID,
        "joined_account",
        parameters={"account_number": args.account, "tax_year": args.tax_year},
    )
    detail, installment = ascend_client.detail(
        args.account,
        tax_year=args.tax_year,
    )
    account_record = parse_ascend_detail(
        detail.html,
        source_url=detail.source_url,
        installment_html=installment.html if installment else None,
        installment_source_url=installment.source_url if installment else None,
    )
    if account_record["account_number"] != args.account:
        raise SourceSchemaError(
            "Wasco joined detail account does not match the request",
            url=detail.source_url,
        )
    where = _taxlot_where(args.account, "account")
    batch = arcgis.fetch_batch(
        taxlot_client,
        TAXLOT_MANIFEST,
        adapter_slug="wasco-property",
        operation="joined_account",
        where=where,
        limit=2,
        cursor=None,
        return_geometry=args.geometry,
    )
    if len(batch.features) != 1:
        raise SourceSchemaError(
            "Wasco exact account did not resolve to one taxlot",
            url=TAXLOT_LAYER_URL,
            details={"account": args.account, "matches": len(batch.features)},
        )
    taxlot = _normalize_taxlot(
        batch.features[0],
        schema_value=batch.schema_fingerprint,
        geometry_requested=args.geometry,
    )
    account_map = account_record.get("normalized_map_taxlot")
    taxlot_map = taxlot.get("normalized_map_taxlot")
    if (
        taxlot.get("account_number") != args.account
        or not account_map
        or account_map != taxlot_map
    ):
        raise SourceSchemaError(
            "Wasco exact account join identities disagree",
            url=TAXLOT_LAYER_URL,
            details={
                "requested_account": args.account,
                "ascend_map_taxlot": account_map,
                "taxlot_account": taxlot.get("account_number"),
                "taxlot_map_taxlot": taxlot_map,
            },
        )
    joined_ref = canonical_property_ref(
        ASCEND_SOURCE_ID,
        COUNTY_GEOID,
        "joined_property_account",
        args.account,
    )
    record = {
        "canonical_ref": joined_ref,
        "evidence_ref": joined_ref,
        "source_id": ASCEND_SOURCE_ID,
        "record_kind": "joined_property_account",
        "account_number": args.account,
        "assessment_account": account_record,
        "taxlot": taxlot,
        "join_validation": {
            "status": "exact",
            "account_number_equal": True,
            "normalized_map_taxlot_equal": True,
            "normalized_map_taxlot": account_map,
            "component_relationship": (
                "same_county_complement_not_independent_corroboration"
            ),
        },
    }
    return PublicRecordsResult.success(query, [record])


def _attachments(
    args: argparse.Namespace,
    *,
    client: Any,
) -> PublicRecordsResult:
    source_id = args.source
    definition = SURVEY_LAYERS.get(source_id)
    if definition is None or not definition.has_attachments:
        raise SourceSelectionError(
            "attachments_unavailable",
            f"{source_id} has no live-verified attachment collection",
        )
    manifest = definition.manifest
    query = _query(
        source_id,
        "attachments",
        parameters={"object_id": args.object_id},
    )
    metadata = client.fetch_metadata()
    arcgis.metadata_contract(manifest, metadata)
    infos = client.fetch_attachments(args.object_id)
    records = arcgis.attachment_records(manifest, args.object_id, infos)
    for record in records:
        record.update(
            {
                "source_id": source_id,
                "record_kind": f"{definition.record_kind}_attachment",
                "object_id": args.object_id,
            }
        )
    return PublicRecordsResult.success(query, records)


def _probe_one(
    source_id: str,
    *,
    client: Any,
) -> PublicRecordsResult:
    query = _query(source_id, "probe", parameters={})
    if source_id == ASCEND_SOURCE_ID:
        page = client.fetch_home()
        contract = ascend.parse_home(
            ASCEND_MANIFEST,
            page.html,
            source_url=page.source_url,
        )
        record = {
            "source_id": source_id,
            "record_kind": "source_probe",
            "source_url": contract.source_url,
            "platform_version": contract.version,
            "observed_version_match": contract.version
            in ASCEND_MANIFEST.observed_versions,
            "form_fields": list(contract.form_fields),
            "schema_fingerprint": contract.schema_fingerprint,
            "native_contract": ASCEND_MANIFEST.contract_record(),
        }
    else:
        manifest = ARCGIS_MANIFESTS[source_id]
        metadata = client.fetch_metadata()
        schema_value, maximum = arcgis.metadata_contract(manifest, metadata)
        count = client.fetch_count("1=1")
        record = {
            "source_id": source_id,
            "record_kind": "source_probe",
            "source_url": manifest.layer_url,
            "component_count": count,
            "observed_count": manifest.observed_count,
            "count_changed": (
                manifest.observed_count is not None
                and count != manifest.observed_count
            ),
            "max_record_count": maximum,
            "schema_fingerprint": schema_value,
            "native_contract": manifest.contract_record(),
        }
    return PublicRecordsResult.success(query, [record])


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
    arcgis_clients: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    if args.command == "sources":
        return sources_payload()
    if args.command == "source":
        query = _query(args.source, "source", parameters={})
        return PublicRecordsResult.success(query, [_source_record(args.source)])

    def selected_arcgis(source_id: str) -> Any:
        if arcgis_clients and source_id in arcgis_clients:
            return arcgis_clients[source_id]
        return WascoArcGISClient(
            ARCGIS_MANIFESTS[source_id],
            page_size=getattr(args, "page_size", DEFAULT_PAGE_SIZE),
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
            retry_attempts=args.retry_attempts,
        )

    ascend_client = client or AscendWebClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )
    owns_ascend = client is None
    created_arcgis: list[Any] = []
    result: PublicRecordsResult
    query_for_error: PublicRecordsQuery | None = None
    try:
        if args.command == "search":
            query_for_error = _query(
                args.source,
                "search",
                parameters={"value": args.value, "field": args.field},
                limit=args.limit,
                cursor=args.cursor,
            )
            if args.source == ASCEND_SOURCE_ID:
                result = _ascend_search(args, client=ascend_client)
            else:
                arc_client = selected_arcgis(args.source)
                if not (arcgis_clients and args.source in arcgis_clients):
                    created_arcgis.append(arc_client)
                result = _arcgis_search(args, client=arc_client)
        elif args.command == "detail":
            query_for_error = _query(
                ASCEND_SOURCE_ID,
                "detail",
                parameters={"account_number": args.account},
            )
            result = _detail(args, client=ascend_client)
        elif args.command == "account":
            query_for_error = _query(
                ASCEND_SOURCE_ID,
                "joined_account",
                parameters={"account_number": args.account},
            )
            taxlot_client = selected_arcgis(TAXLOT_SOURCE_ID)
            if not (arcgis_clients and TAXLOT_SOURCE_ID in arcgis_clients):
                created_arcgis.append(taxlot_client)
            result = _account(
                args,
                ascend_client=ascend_client,
                taxlot_client=taxlot_client,
            )
        elif args.command == "attachments":
            query_for_error = _query(
                args.source,
                "attachments",
                parameters={"object_id": args.object_id},
            )
            arc_client = selected_arcgis(args.source)
            if not (arcgis_clients and args.source in arcgis_clients):
                created_arcgis.append(arc_client)
            result = _attachments(args, client=arc_client)
        elif args.command == "probe" and args.all_sources:
            components = []
            for source_id in SOURCE_IDS:
                source_client = (
                    ascend_client
                    if source_id == ASCEND_SOURCE_ID
                    else selected_arcgis(source_id)
                )
                if source_id != ASCEND_SOURCE_ID and not (
                    arcgis_clients and source_id in arcgis_clients
                ):
                    created_arcgis.append(source_client)
                try:
                    component = _probe_one(source_id, client=source_client)
                except PublicRecordsHTTPError as exc:
                    component = failure_result(
                        _query(source_id, "probe", parameters={}),
                        exc,
                    )
                components.append(component.to_dict())
            status = (
                "ok"
                if all(item["status"] == "ok" for item in components)
                else "partial"
            )
            return {
                "schema_version": PROBE_SCHEMA_VERSION,
                "status": status,
                "components": components,
            }
        elif args.command == "probe":
            source_id = args.source
            query_for_error = _query(source_id, "probe", parameters={})
            source_client = (
                ascend_client
                if source_id == ASCEND_SOURCE_ID
                else selected_arcgis(source_id)
            )
            if source_id != ASCEND_SOURCE_ID and not (
                arcgis_clients and source_id in arcgis_clients
            ):
                created_arcgis.append(source_client)
            result = _probe_one(source_id, client=source_client)
        else:
            raise SourceSelectionError(
                "unsupported_command",
                f"unsupported command: {args.command}",
            )
    except PublicRecordsHTTPError as exc:
        if query_for_error is None:
            raise
        result = failure_result(query_for_error, exc)
    except SourceSelectionError as exc:
        if query_for_error is None:
            raise
        result = PublicRecordsResult.failure(
            query_for_error,
            exc.status,
            [exc.to_contract_error()],
        )
    except ValueError as exc:
        if query_for_error is None:
            raise
        result = PublicRecordsResult.failure(
            query_for_error,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="invalid_request",
                    message=str(exc),
                    category="selection",
                    retryable=False,
                )
            ],
        )
    finally:
        if owns_ascend:
            ascend_client.close()
        for arc_client in created_arcgis:
            arc_client.close()
    if log_results:
        _log(result.query, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Wasco County property and survey components"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser("sources")
    add_output_args(sources)

    source = subparsers.add_parser("source")
    source.add_argument("--source", choices=SOURCE_IDS, required=True)
    add_output_args(source)

    search = subparsers.add_parser("search")
    search.add_argument("value")
    search.add_argument("--source", choices=SOURCE_IDS, required=True)
    search.add_argument("--field", default="auto")
    search.add_argument("--city")
    search.add_argument("--state")
    search.add_argument("--postal-code")
    search.add_argument(
        "--limit",
        type=int,
        help="Return at most this many records; omitted traverses all matches",
    )
    search.add_argument("--cursor")
    search.add_argument("--geometry", action="store_true")
    _add_transport(search)
    add_output_args(search)

    detail = subparsers.add_parser("detail")
    detail.add_argument("account")
    detail.add_argument("--tax-year", type=int)
    _add_transport(detail, include_page_size=False)
    add_output_args(detail)

    account = subparsers.add_parser("account")
    account.add_argument("account")
    account.add_argument("--tax-year", type=int)
    account.add_argument("--geometry", action="store_true")
    _add_transport(account)
    add_output_args(account)

    attachments = subparsers.add_parser("attachments")
    attachments.add_argument("source", choices=SURVEY_SOURCE_IDS)
    attachments.add_argument("object_id", type=int)
    _add_transport(attachments)
    add_output_args(attachments)

    probe = subparsers.add_parser("probe")
    choice = probe.add_mutually_exclusive_group(required=True)
    choice.add_argument("--source", choices=SOURCE_IDS)
    choice.add_argument("--all", action="store_true", dest="all_sources")
    _add_transport(probe)
    add_output_args(probe)
    return parser


def _add_transport(
    parser: argparse.ArgumentParser,
    *,
    include_page_size: bool = True,
) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    if include_page_size:
        parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)


def _payload(value: PublicRecordsResult | Mapping[str, Any]) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    records = payload.get("records")
    count = (
        len(records)
        if isinstance(records, list)
        else len(payload.get("components", payload.get("sources", [])))
    )
    if write_output(
        payload,
        args,
        summary=f"Wasco property {args.command}",
        result_count=count,
    ):
        return
    print(canonical_json(payload))


def main() -> None:
    args = build_parser().parse_args()
    if (
        getattr(args, "limit", None) is not None
        and args.limit < 1
    ):
        raise SystemExit("--limit must be positive")
    if getattr(args, "page_size", DEFAULT_PAGE_SIZE) < 1:
        raise SystemExit("--page-size must be positive")
    result = execute(args)
    _emit(result, args)
    if isinstance(result, PublicRecordsResult) and result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
