#!/usr/bin/env python3
"""Bexar Central Appraisal District property and parcel adapter.

BCAD exposes complementary public routes:

- ArcGIS table 9 for deterministic, pageable current-roll discovery.
- ArcGIS layer 6 for parcel geometry.
- Harris Govern JSON endpoints for full-text search, property detail, roll
  history, improvements, appeals, and deed-history enrichment.

Usage:
    uv run python tools/query_bexar_property.py owner "GRACE CHURCH"
    uv run python tools/query_bexar_property.py address "STONE OAK PKWY"
    uv run python tools/query_bexar_property.py parcel 612115 --geometry
    uv run python tools/query_bexar_property.py search '"CORNERSTONE CHURCH"'
    uv run python tools/query_bexar_property.py detail 612115 --year 2026
    uv run python tools/query_bexar_property.py probe --output /tmp/bcad-probe.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

import requests

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
    )
    from tools.public_records_http import (
        ArcGISRESTClient,
        PaginatedFetch,
        PublicRecordsHTTPError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
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
    )
    from public_records_http import (
        ArcGISRESTClient,
        PaginatedFetch,
        PublicRecordsHTTPError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-tx-bexar-bcad-property"
COUNTY_GEOID = "48029"
TABLE_URL = "https://maps.bcad.org/arcgis/rest/services/PAMapSearch/MapServer/9"
PARCEL_LAYER_URL = (
    "https://maps.bcad.org/arcgis/rest/services/PAMapSearch/MapServer/6"
)
HGO_BASE_URL = "https://hgo.harrisgovern.com/bexar"
HGO_SEARCH_COUNT_URL = (
    f"{HGO_BASE_URL}/api/property/property-search/search-count"
)
HGO_SEARCH_RESULTS_URL = (
    f"{HGO_BASE_URL}/api/property/property-search/property-basic-search-results"
)
HGO_DETAIL_URL = (
    f"{HGO_BASE_URL}/api/property/property-details/property-detail-data"
)
HGO_DEED_HISTORY_URL = (
    f"{HGO_BASE_URL}/api/property/property-details/property-deed-history"
)
CLASSIC_DETAIL_URL = (
    "https://bexar.trueautomation.com/clientdb/Property.aspx?cid=110"
)
PUBLIC_INFORMATION_FORM_URL = (
    "https://bcad.org/wp-content/uploads/2026/04/"
    "BCAD-Public-Information-Act-Request.pdf"
)
TABLE_ORDER_BY = "pacs_prop_id ASC"
GEOMETRY_ORDER_BY = "PAMaps.DBO.ParcelFabric_Parcels.OBJECTID ASC"
GEOMETRY_PROPERTY_FIELD = "PAMaps.DBO.ParcelFabric_Parcels.PROP_ID"

OUT_FIELDS = (
    "pacs_prop_id",
    "prop_val_yr",
    "geo_id",
    "prop_type_cd",
    "prop_type_desc",
    "dba_name",
    "appraised_val",
    "abs_subdv_cd",
    "mapsco",
    "map_id",
    "agent_cd",
    "hood_cd",
    "hood_name",
    "owner_name",
    "owner_id",
    "addr_line1",
    "addr_line2",
    "addr_line3",
    "addr_city",
    "addr_state",
    "addr_zip",
    "addr_country",
    "pct_ownership",
    "exemptions",
    "state_cd",
    "legal_desc",
    "situs",
    "jurisdictions",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Bexar Central Appraisal District Property and Parcel Data",
    source_role="parcel_gis_assessment_detail",
    base_url=TABLE_URL,
    dataset_id="PAMapSearch/MapServer/9",
    metadata={
        "authority": "Bexar Central Appraisal District",
        "coverage": "Bexar County, Texas",
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
    },
)

SOURCE_WARNINGS = (
    "BCAD owner fields are appraisal-roll observations, not proof of legal title or beneficial ownership.",
    "BCAD parcel geometry is mapping data and is not a surveyed legal boundary.",
    "The live ArcGIS table is a current property-summary route and may not contain every appraisal-account class.",
)


class BCADHGOClient(_BaseJSONClient):
    """Client for BCAD's public Harris Govern JSON search and detail routes."""

    def search(
        self,
        search_text: str,
        *,
        requested_limit: int,
        page_size: int,
        cursor: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        offset = _hgo_cursor_offset(cursor)
        count_payload = self._request_json(
            HGO_SEARCH_COUNT_URL,
            params={"searchText": search_text},
        )
        if not isinstance(count_payload, Mapping):
            raise ValueError("BCAD search-count response must be an object")
        try:
            total_count = int(count_payload["Count"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("BCAD search-count response lacks a numeric Count") from error

        effective_limit = requested_limit
        warnings: list[str] = []
        potentially_truncated = False
        if max_records is not None and max_records < effective_limit:
            effective_limit = max_records
            potentially_truncated = True
            warnings.append(
                f"Requested {requested_limit} records but the configured cap is "
                f"{max_records}."
            )

        records: list[Mapping[str, Any]] = []
        pages_fetched = 0
        initial_requests = self.request_count
        while len(records) < effective_limit and offset + len(records) < total_count:
            take = min(page_size, effective_limit - len(records))
            payload = self._request_json(
                HGO_SEARCH_RESULTS_URL,
                params={
                    "searchText": search_text,
                    "skip": offset + len(records),
                    "take": take,
                },
            )
            pages_fetched += 1
            if not isinstance(payload, list) or any(
                not isinstance(record, Mapping) for record in payload
            ):
                raise ValueError("BCAD search results must be an array of objects")
            page = list(payload)
            records.extend(page)
            if len(page) < take:
                break

        next_offset = offset + len(records)
        source_has_more = next_offset < total_count
        return PaginatedFetch(
            records=tuple(records),
            next_cursor=(
                f"hgo:offset:{next_offset}" if source_has_more else None
            ),
            schema=inferred_schema(records),
            schema_fingerprint=schema_fingerprint(inferred_schema(records)),
            pages_fetched=pages_fetched,
            requests_made=self.request_count - initial_requests + 1,
            truncated_by_cap=potentially_truncated and source_has_more,
            warnings=tuple(warnings),
        )

    def detail(self, property_id: int, year: int) -> Mapping[str, Any] | None:
        payload = self._request_json(
            HGO_DETAIL_URL,
            params={"PropertyId": property_id, "Year": year},
        )
        if payload is None:
            return None
        if not isinstance(payload, Mapping):
            raise ValueError("BCAD property detail response must be an object")
        return payload

    def deed_history(self, property_id: int) -> Sequence[Mapping[str, Any]]:
        payload = self._request_json(
            HGO_DEED_HISTORY_URL,
            params={"propertyId": property_id},
        )
        if not isinstance(payload, list) or any(
            not isinstance(record, Mapping) for record in payload
        ):
            raise ValueError("BCAD deed-history response must be an array of objects")
        return tuple(payload)


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(
            getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
        ).expanduser(),
        config_path=Path(
            getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
        ).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _reviewed_limits(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> tuple[int, float]:
    limits = access_contract.get("limits") or {}
    page_size = min(
        args.page_size,
        int(limits.get("maximum_page_size") or args.page_size),
    )
    interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return page_size, interval


def _arcgis_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
    *,
    layer_url: str = TABLE_URL,
) -> ArcGISRESTClient:
    page_size, interval = _reviewed_limits(args, access_contract)
    return ArcGISRESTClient(
        layer_url,
        page_size=page_size,
        max_records=args.max_records,
        timeout=args.timeout,
        minimum_interval=interval,
    )


def _hgo_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> BCADHGOClient:
    _page_size, interval = _reviewed_limits(args, access_contract)
    return BCADHGOClient(
        session=requests.Session(),
        timeout=args.timeout,
        minimum_interval=interval,
    )


def _hgo_page_size(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> int:
    limits = access_contract.get("limits") or {}
    return min(
        args.page_size,
        int(limits.get("hgo_search_page_size") or args.page_size),
    )


def _hgo_cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    prefix = "hgo:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError("BCAD search cursor must have form hgo:offset:N")
    return int(cursor[len(prefix) :])


def _sql_literal(value: str) -> str:
    cleaned = _query_text(value)
    return cleaned.replace("'", "''")


def _query_text(value: str) -> str:
    cleaned = " ".join(str(value).replace("\x00", "").split()).strip()
    if not cleaned:
        raise ValueError("query value must not be blank")
    return cleaned


def _property_id(value: str) -> int:
    cleaned = "".join(str(value).split())
    if not cleaned.isdigit() or int(cleaned) <= 0:
        raise ValueError("BCAD property ID must be a positive integer")
    return int(cleaned)


def _where(operation: str, selector: str | None) -> str:
    if operation == "probe":
        return "1=1"
    value = _sql_literal(selector or "")
    upper = value.upper()
    if operation == "owner":
        return (
            f"(UPPER(owner_name) LIKE '%{upper}%' "
            f"OR UPPER(dba_name) LIKE '%{upper}%')"
        )
    if operation == "address":
        return (
            f"(UPPER(situs) LIKE '%{upper}%' "
            f"OR UPPER(addr_line1) LIKE '%{upper}%' "
            f"OR UPPER(addr_line2) LIKE '%{upper}%' "
            f"OR UPPER(addr_line3) LIKE '%{upper}%')"
        )
    if operation == "parcel":
        if value.isdigit():
            return f"pacs_prop_id={int(value)}"
        return f"geo_id='{value}'"
    if operation == "geoid":
        return f"geo_id='{value}'"
    raise ValueError(f"unsupported ArcGIS operation: {operation}")


def _nonblank(*values: Any) -> list[str]:
    return [str(value).strip() for value in values if str(value or "").strip()]


def _money(value: Any) -> int | str | None:
    if value in (None, ""):
        return None
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"invalid BCAD monetary value: {value!r}") from error
    if not amount.is_finite():
        raise ValueError(f"non-finite BCAD monetary value: {value!r}")
    if amount == amount.to_integral_value():
        return int(amount)
    return format(amount.normalize(), "f")


def _sum_money(*values: Any) -> int | str | None:
    numbers = [_money(value) for value in values if value not in (None, "")]
    if not numbers:
        return None
    total = sum(Decimal(str(value)) for value in numbers)
    return _money(total)


def _split_codes(value: Any) -> list[str]:
    return [
        code.strip()
        for code in str(value or "").split(",")
        if code.strip()
    ]


def _source_links(property_id: int, year: int | str | None) -> dict[str, str]:
    tax_year = int(year or datetime.now(tz=timezone.utc).year)
    return {
        "record": f"{HGO_BASE_URL}/property/{tax_year}-{property_id}",
        "classic_record": (
            f"{CLASSIC_DETAIL_URL}&prop_id={property_id}&year={tax_year}"
        ),
        "arcgis_service": TABLE_URL,
        "data_product_request": PUBLIC_INFORMATION_FORM_URL,
    }


def _normalize_summary(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint_value: str,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes", {})
    if not isinstance(attributes_value, Mapping):
        raise ValueError("BCAD ArcGIS feature attributes must be an object")
    attributes = dict(attributes_value)
    property_id = _property_id(str(attributes.get("pacs_prop_id") or ""))
    tax_year = attributes.get("prop_val_yr")
    owner_name = str(attributes.get("owner_name") or "").strip()
    owners = []
    if owner_name:
        owners.append(
            {
                "raw_name": owner_name,
                "role": "primary_assessor_owner",
                "assertion_type": "assessment_roll",
                "confidence": "high",
                "ownership_percentage": attributes.get("pct_ownership"),
                "owner_id": attributes.get("owner_id"),
                "title_caveat": "not_proof_of_legal_or_beneficial_ownership",
            }
        )
    alternate_ids = _nonblank(attributes.get("geo_id"))
    result: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID, COUNTY_GEOID, "parcel", str(property_id)
        ),
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "TX",
            "state_fips": "48",
            "county_name": "Bexar",
            "county_geoid": COUNTY_GEOID,
        },
        "native_parcel_id": str(property_id),
        "alternate_parcel_ids": alternate_ids,
        "geographic_id": attributes.get("geo_id"),
        "tax_year": tax_year,
        "property_type": {
            "code": str(attributes.get("prop_type_cd") or "").strip() or None,
            "description": attributes.get("prop_type_desc"),
            "state_code": attributes.get("state_cd"),
        },
        "business_name": attributes.get("dba_name"),
        "owners": owners,
        "situs_address": {
            "raw": attributes.get("situs"),
            "state": "TX",
        },
        "mailing_address": {
            "raw": " ".join(
                _nonblank(
                    attributes.get("addr_line1"),
                    attributes.get("addr_line2"),
                    attributes.get("addr_line3"),
                )
            )
            or None,
            "city": attributes.get("addr_city"),
            "state": attributes.get("addr_state"),
            "postal_code": attributes.get("addr_zip"),
            "country": attributes.get("addr_country"),
        },
        "assessment": {
            "parcel_value": _money(attributes.get("appraised_val")),
            "assessment_class": attributes.get("prop_type_desc"),
            "currency": "USD",
            "raw_appraised_value": attributes.get("appraised_val"),
        },
        "legal_description_raw": attributes.get("legal_desc"),
        "subdivision_code": attributes.get("abs_subdv_cd"),
        "neighborhood": {
            "code": attributes.get("hood_cd"),
            "name": attributes.get("hood_name"),
        },
        "agent_code": attributes.get("agent_cd"),
        "exemptions": _split_codes(attributes.get("exemptions")),
        "taxing_jurisdiction_codes": _split_codes(
            attributes.get("jurisdictions")
        ),
        "source_links": _source_links(property_id, tax_year),
        "schema_fingerprint": schema_fingerprint_value,
        "raw_attributes": attributes,
    }
    geometry = feature.get("geometry")
    if isinstance(geometry, Mapping):
        result["geometry"] = dict(geometry)
        result["geometry_disclaimer"] = SOURCE_WARNINGS[1]
    return result


def _normalize_hgo_search_record(
    record: Mapping[str, Any],
    *,
    schema_fingerprint_value: str,
) -> dict[str, Any]:
    property_id = _property_id(str(record.get("PropertyId") or ""))
    tax_year = record.get("Year")
    owner_name = str(record.get("OwnerFullName") or "").strip()
    property_type = str(record.get("PropertyTypeCode") or "").strip()
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID, COUNTY_GEOID, "parcel", str(property_id)
        ),
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "TX",
            "state_fips": "48",
            "county_name": "Bexar",
            "county_geoid": COUNTY_GEOID,
        },
        "native_parcel_id": str(property_id),
        "alternate_parcel_ids": _nonblank(record.get("GeoId")),
        "geographic_id": record.get("GeoId"),
        "tax_year": tax_year,
        "property_type": {
            "code": record.get("PropertyTypeCodeOnly"),
            "description": property_type,
        },
        "business_name": record.get("BusinessName"),
        "owners": (
            [
                {
                    "raw_name": owner_name,
                    "role": "primary_assessor_owner",
                    "assertion_type": "assessment_roll",
                    "confidence": "high",
                    "owner_id": record.get("OwnerID"),
                    "title_caveat": "not_proof_of_legal_or_beneficial_ownership",
                }
            ]
            if owner_name
            else []
        ),
        "situs_address": {
            "raw": " ".join(str(record.get("SitusAddress") or "").split())
            or None,
            "state": "TX",
        },
        "mailing_address": {},
        "assessment": {
            "parcel_value": _money(record.get("AppraisedValue")),
            "market_value": _money(record.get("MarketValue")),
            "assessed_value": _money(record.get("AssessedValue")),
            "assessment_class": property_type or None,
            "currency": "USD",
        },
        "legal_description_raw": record.get("LegalDescription"),
        "appeals": record.get("Appeals") or [],
        "group_codes": _split_codes(record.get("GroupCodes")),
        "source_links": _source_links(property_id, tax_year),
        "schema_fingerprint": schema_fingerprint_value,
        "raw_attributes": dict(record),
    }


def _normalize_deeds(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized = []
    for record in records:
        normalized.append(
            {
                "sequence": record.get("seq_num"),
                "deed_date": record.get("deed_dt"),
                "deed_type_code": str(
                    record.get("deed_type_cd") or ""
                ).strip()
                or None,
                "deed_type_description": record.get("deed_type_desc"),
                "grantor": str(record.get("grantor") or "").strip() or None,
                "grantee": str(record.get("grantee") or "").strip() or None,
                "book": str(record.get("deed_book_id") or "").strip() or None,
                "page": str(record.get("deed_book_page") or "").strip() or None,
                "instrument_number": (
                    str(record.get("deed_num") or "").strip() or None
                ),
                "raw": dict(record),
            }
        )
    return normalized


def _normalize_detail(
    detail: Mapping[str, Any],
    deeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    property_id = _property_id(str(detail.get("PropertyId") or ""))
    owner_value = detail.get("Owner")
    owner = dict(owner_value) if isinstance(owner_value, Mapping) else {}
    location_value = detail.get("Location")
    location = (
        dict(location_value) if isinstance(location_value, Mapping) else {}
    )
    values_value = detail.get("Values")
    values = dict(values_value) if isinstance(values_value, Mapping) else {}
    property_type_value = detail.get("PropertyTypeCode")
    property_type = (
        dict(property_type_value)
        if isinstance(property_type_value, Mapping)
        else {}
    )
    use_code_value = values.get("PropertyUseCode")
    use_code = (
        dict(use_code_value) if isinstance(use_code_value, Mapping) else {}
    )
    owner_name = str(owner.get("FullName") or "").strip()
    tax_year = values.get("Year") or datetime.now(tz=timezone.utc).year
    combined_schema = inferred_schema(
        [dict(detail), {"deed_history": [dict(record) for record in deeds]}]
    )
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID, COUNTY_GEOID, "parcel", str(property_id)
        ),
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "TX",
            "state_fips": "48",
            "county_name": "Bexar",
            "county_geoid": COUNTY_GEOID,
        },
        "native_parcel_id": str(property_id),
        "alternate_parcel_ids": _nonblank(detail.get("GeoId")),
        "geographic_id": detail.get("GeoId"),
        "tax_year": tax_year,
        "property_type": {
            "code": property_type.get("Code"),
            "description": property_type.get("Description"),
            "use_code": use_code.get("Code"),
            "use_description": use_code.get("Description"),
            "zoning_code": detail.get("ZoningCode"),
        },
        "business_name": detail.get("DbaName"),
        "owners": (
            [
                {
                    "raw_name": owner_name,
                    "role": "primary_assessor_owner",
                    "assertion_type": "assessment_roll",
                    "confidence": "high",
                    "ownership_percentage": owner.get("PercentOwnership"),
                    "owner_id": owner.get("OwnerId"),
                    "title_caveat": "not_proof_of_legal_or_beneficial_ownership",
                }
            ]
            if owner_name
            else []
        ),
        "situs_address": {
            "raw": " ".join(str(location.get("FullAddress") or "").split())
            or None,
            "unit": location.get("UnitNumber"),
            "city": location.get("City"),
            "state": location.get("State") or "TX",
            "postal_code": location.get("Zip"),
        },
        "mailing_address": {
            "raw": " ".join(
                _nonblank(
                    owner.get("AddressLine1"),
                    owner.get("AddressLine2"),
                    owner.get("AddressLine3"),
                )
            )
            or None,
            "city": owner.get("AddressCity"),
            "state": owner.get("AddressState"),
            "postal_code": owner.get("AddressZip"),
            "country": str(owner.get("CountryCode") or "").strip() or None,
        },
        "assessment": {
            "land_value": _sum_money(
                values.get("LandHstdValue"),
                values.get("LandNonHstdValue"),
            ),
            "improvement_value": _sum_money(
                values.get("ImprvHstdValue"),
                values.get("ImprvNonHstdValue"),
            ),
            "parcel_value": _money(values.get("AppraisedValue")),
            "market_value": _money(values.get("Market")),
            "assessed_value": _money(values.get("AssessedValue")),
            "assessment_class": use_code.get("Description")
            or property_type.get("Description"),
            "currency": "USD",
        },
        "legal_description_raw": values.get("LegalDescription"),
        "legal_description_2": values.get("LegalDescription2"),
        "legal_acreage": values.get("LegalAcreage"),
        "improvements": detail.get("Improvements") or [],
        "land": detail.get("Land") or [],
        "exemptions": detail.get("Exemptions") or [],
        "appeals": detail.get("Appeals") or [],
        "taxing_jurisdictions": detail.get("TaxingJurisdictions") or {},
        "roll_history": detail.get("RollHistory") or [],
        "deed_history": _normalize_deeds(deeds),
        "agent": detail.get("Agent"),
        "group_codes": detail.get("GroupCodes") or [],
        "source_links": _source_links(property_id, tax_year),
        "schema_fingerprint": schema_fingerprint(combined_schema),
        "raw_attributes": dict(detail),
    }


def _geometry_property_id(attributes: Mapping[str, Any]) -> str | None:
    for key, value in attributes.items():
        if key.rsplit(".", 1)[-1].upper() in {"PROP_ID", "PACS_PROP_ID"}:
            if value not in (None, ""):
                return str(value)
    return None


def _fetch_geometry(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
    property_ids: Sequence[str],
) -> dict[str, Mapping[str, Any]]:
    unique_ids = sorted(
        {_property_id(value) for value in property_ids}
    )
    if not unique_ids:
        return {}
    client = _arcgis_client(
        args,
        access_contract,
        layer_url=PARCEL_LAYER_URL,
    )
    geometries: dict[str, Mapping[str, Any]] = {}
    for index in range(0, len(unique_ids), 250):
        batch = unique_ids[index : index + 250]
        fetched = client.query(
            where=(
                f"{GEOMETRY_PROPERTY_FIELD} IN "
                f"({','.join(str(value) for value in batch)})"
            ),
            out_fields=(GEOMETRY_PROPERTY_FIELD,),
            parameters={
                "orderByFields": GEOMETRY_ORDER_BY,
                "outSR": 4326,
            },
            requested_limit=len(batch),
            return_geometry=True,
        )
        for feature in fetched.records:
            attributes = feature.get("attributes")
            geometry = feature.get("geometry")
            if isinstance(attributes, Mapping) and isinstance(geometry, Mapping):
                property_id = _geometry_property_id(attributes)
                if property_id:
                    geometries[property_id] = dict(geometry)
    return geometries


def _attach_geometry(
    records: Sequence[Mapping[str, Any]],
    geometries: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    enriched = []
    for record in records:
        output = dict(record)
        geometry = geometries.get(str(record.get("native_parcel_id") or ""))
        if geometry is not None:
            output["geometry"] = dict(geometry)
            output["geometry_disclaimer"] = SOURCE_WARNINGS[1]
        enriched.append(output)
    return enriched


def build_query(
    operation: str,
    selector: str | None,
    *,
    year: int | None,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Bexar County, Texas",
            state_code="TX",
            county_fips=COUNTY_GEOID,
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "year": year,
                "return_geometry": return_geometry,
            },
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    operation = args.command
    selector = getattr(args, "query", None)
    limit = 1 if operation == "probe" else args.limit
    query = build_query(
        operation,
        selector,
        year=getattr(args, "year", None),
        limit=limit,
        cursor=args.cursor,
        return_geometry=args.geometry,
    )
    try:
        access_contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args)
        )
        result_errors: list[PublicRecordsError] = []
        warnings: list[str] = list(SOURCE_WARNINGS)

        if operation == "detail":
            property_id = _property_id(selector or "")
            year = args.year or datetime.now(tz=timezone.utc).year
            hgo = _hgo_client(args, access_contract)
            detail = hgo.detail(property_id, year)
            if detail is None:
                records: list[dict[str, Any]] = []
            else:
                deeds: Sequence[Mapping[str, Any]] = ()
                try:
                    deeds = hgo.deed_history(property_id)
                except PublicRecordsHTTPError as error:
                    result_errors.append(error.to_contract_error())
                    warnings.append(
                        "Property detail was returned without deed-history enrichment."
                    )
                except (TypeError, ValueError) as error:
                    result_errors.append(
                        PublicRecordsError(
                            code="deed_history_normalization_failed",
                            message=str(error),
                            category="source_schema",
                            retryable=False,
                        )
                    )
                    warnings.append(
                        "Property detail was returned without deed-history enrichment."
                    )
                records = [_normalize_detail(detail, deeds)]
        elif operation == "search":
            fetched = _hgo_client(args, access_contract).search(
                _query_text(selector or ""),
                requested_limit=limit,
                page_size=_hgo_page_size(args, access_contract),
                cursor=args.cursor,
                max_records=args.max_records,
            )
            records = [
                _normalize_hgo_search_record(
                    record,
                    schema_fingerprint_value=fetched.schema_fingerprint,
                )
                for record in fetched.records
            ]
            warnings.extend(fetched.warnings)
        else:
            fetched = _arcgis_client(args, access_contract).query(
                where=_where(operation, selector),
                out_fields=OUT_FIELDS,
                parameters={"orderByFields": TABLE_ORDER_BY},
                requested_limit=limit,
                cursor=args.cursor,
                return_geometry=False,
            )
            records = [
                _normalize_summary(
                    feature,
                    schema_fingerprint_value=fetched.schema_fingerprint,
                )
                for feature in fetched.records
            ]
            warnings.extend(fetched.warnings)

        if args.geometry and records:
            try:
                geometries = _fetch_geometry(
                    args,
                    access_contract,
                    [
                        str(record.get("native_parcel_id") or "")
                        for record in records
                    ],
                )
                records = _attach_geometry(records, geometries)
            except PublicRecordsHTTPError as error:
                result_errors.append(error.to_contract_error())
                warnings.append(
                    "Property records were returned without parcel-geometry enrichment."
                )
            except (TypeError, ValueError) as error:
                result_errors.append(
                    PublicRecordsError(
                        code="geometry_normalization_failed",
                        message=str(error),
                        category="source_schema",
                        retryable=False,
                    )
                )
                warnings.append(
                    "Property records were returned without parcel-geometry enrichment."
                )

        next_cursor = (
            fetched.next_cursor
            if operation not in {"detail"} and "fetched" in locals()
            else None
        )
        truncated_by_cap = (
            fetched.truncated_by_cap
            if operation not in {"detail"} and "fetched" in locals()
            else False
        )
        if result_errors:
            result = PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                result_errors,
                records=records,
                next_cursor=next_cursor,
                warnings=warnings,
            )
        elif truncated_by_cap:
            result = PublicRecordsResult(
                query=query,
                status=ResultStatus.PARTIAL,
                records=records,
                next_cursor=next_cursor,
                warnings=warnings,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                warnings=warnings,
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

    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"BCAD {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"BCAD {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        owners = ", ".join(
            str(owner.get("raw_name") or "")
            for owner in record.get("owners", [])
        )
        print(
            f"  {record['native_parcel_id']} | "
            f"{record.get('situs_address', {}).get('raw') or '?'} | "
            f"{owners or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cursor", help="Continuation cursor from a previous result")
    parser.add_argument("--geometry", action="store_true", help="Return parcel geometry")
    parser.add_argument(
        "--year",
        type=int,
        help="Tax year for detail lookup; defaults to the current year",
    )
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional user-selected record ceiling",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
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
        description="Query official Bexar County appraisal and parcel records"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("owner", "Search appraisal-roll owner and DBA names"),
        ("address", "Search situs and owner mailing addresses"),
        ("parcel", "Look up a BCAD property ID or geographic ID"),
        ("geoid", "Look up a BCAD geographic ID"),
        ("search", "Run the public portal's full-text property search"),
        ("detail", "Fetch rich property detail and deed history"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_shared_arguments(command_parser)
    probe_parser = sub.add_parser("probe", help="Run one bounded source-health query")
    _add_shared_arguments(probe_parser)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if (
        args.limit <= 0
        or args.page_size <= 0
        or (args.max_records is not None and args.max_records <= 0)
    ):
        parser.error("limit and page-size must be positive; max-records is optional")
    if args.year is not None and args.year <= 0:
        parser.error("--year must be positive")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
