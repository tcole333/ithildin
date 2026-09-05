#!/usr/bin/env python3
"""Miami-Dade Property Appraiser search, detail, history, and parcel geometry.

The official Property Search application exposes two complementary public
routes:

- ``PApublicServiceProxy`` for owner/address/folio discovery and rich property
  detail, including assessment and sale history.
- ``MD_PA_PropertySearch`` ArcGIS layer 6 for parcel polygons keyed by the
  13-digit folio.

Usage:
    uv run python tools/query_miami_dade_property.py owner "MIAMI-DADE COUNTY"
    uv run python tools/query_miami_dade_property.py address "111 NW 1 ST"
    uv run python tools/query_miami_dade_property.py folio 01-4137-023-0020
    uv run python tools/query_miami_dade_property.py detail 0101060501010 \
        --geometry
    uv run python tools/query_miami_dade_property.py history 0101060501010
    uv run python tools/query_miami_dade_property.py geometry 0101060501010
    uv run python tools/query_miami_dade_property.py probe \
        --output /tmp/miami-dade-pa-probe.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
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
        PaginationError,
        PublicRecordsHTTPError,
        SourceResponseError,
        SourceSchemaError,
        SystemTrustHTTPAdapter,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session as _system_trust_session,
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
        PaginationError,
        PublicRecordsHTTPError,
        SourceResponseError,
        SourceSchemaError,
        SystemTrustHTTPAdapter,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
        system_trust_session as _system_trust_session,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-fl-miami-dade-property-appraiser"
COUNTY_GEOID = "12086"
PROPERTY_SEARCH_URL = "https://apps.miamidadepa.gov/PropertySearch/"
PROXY_URL = (
    "https://apps.miamidadepa.gov/"
    "PApublicServiceProxy/PaServicesProxy.ashx"
)
PARCEL_LAYER_URL = (
    "https://gisfs.miamidade.gov/mdarcgis/rest/services/"
    "MD_PA_PropertySearch/MapServer/6"
)
BULK_DATA_URL = "https://bbs.miamidadepa.gov/"
PUBLIC_RECORDS_URL = (
    "https://www.miamidadepa.gov/pa/contact/public-records-requests.page"
)
CLERK_RECORD_URL = (
    "https://onlineservices.miamidadeclerk.gov/"
    "officialrecords/SearchResults?QS="
)
PARCEL_ORDER_BY = "OBJECTID ASC"
PARCEL_OUT_FIELDS = (
    "FOLIO",
    "OBJECTID",
    "TRUE_SITE_ADDR",
    "CONDO_FLAG",
    "PARENT_FOLIO",
)
PROXY_PAGE_SIZE = 200
ARCGIS_PAGE_SIZE = 1_000

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Miami-Dade County Property Appraiser Property Search",
    source_role="assessment_ownership_sales_parcel_geometry",
    base_url=PROPERTY_SEARCH_URL,
    dataset_id="PApublicServiceProxy+MD_PA_PropertySearch/MapServer/6",
    metadata={
        "authority": "Property Appraiser of Miami-Dade County",
        "coverage": "Miami-Dade County, Florida",
        "county_geoid": COUNTY_GEOID,
        "bulk_data_url": BULK_DATA_URL,
    },
)

SOURCE_WARNINGS = (
    "Property Appraiser owner fields are tax-roll observations, not proof of legal or beneficial ownership.",
    "The Property Appraiser continually edits the tax roll, so the live site may not reflect the most current office record.",
    "Parcel geometry is mapping data and is not a surveyed legal boundary.",
)

_SystemTrustHTTPAdapter = SystemTrustHTTPAdapter

_PROXY_OPERATIONS = {
    "owner": ("GetOwners", "ownerName"),
    "address": ("GetAddress", "myAddress"),
    "partial_folio": (
        "GetPropertySearchByPartialFolio",
        "partialFolioNumber",
    ),
}


class MiamiDadePAClient(_BaseJSONClient):
    """Client for the JSON proxy used by the official Property Search app."""

    def search(
        self,
        operation: str,
        selector: str,
        *,
        requested_limit: int,
        page_size: int,
        cursor: str | None = None,
        unit: str | None = None,
        max_records: int | None = None,
    ) -> PaginatedFetch:
        try:
            source_operation, selector_parameter = _PROXY_OPERATIONS[operation]
        except KeyError as error:
            raise ValueError(
                f"unsupported Miami-Dade proxy search operation: {operation}"
            ) from error
        offset = _proxy_cursor_offset(cursor, operation)
        effective_limit = requested_limit
        warnings: list[str] = []
        potentially_truncated = False
        if max_records is not None and max_records < effective_limit:
            effective_limit = max_records
            potentially_truncated = True
            warnings.append(
                f"Requested {requested_limit} records but the caller-selected "
                f"ceiling is {max_records}."
            )

        records: list[Mapping[str, Any]] = []
        pages_fetched = 0
        initial_requests = self.request_count
        total_count: int | None = None
        while len(records) < effective_limit:
            take = min(page_size, effective_limit - len(records))
            page_offset = offset + len(records)
            first_row = page_offset + 1
            last_row = page_offset + take
            params: dict[str, Any] = {
                "Operation": source_operation,
                "clientAppName": "PropertySearch",
                "from": first_row,
                selector_parameter: selector,
                "to": last_row,
            }
            if operation == "address":
                params["myUnit"] = unit or ""
            payload = self._request_json(PROXY_URL, params=params)
            pages_fetched += 1
            page_records, observed_total = _search_page(
                payload,
                operation=operation,
            )
            total_count = observed_total
            if not page_records:
                if page_offset < observed_total:
                    raise PaginationError(
                        "Miami-Dade property search returned an empty page "
                        "before its reported total",
                        url=PROXY_URL,
                        details={
                            "operation": operation,
                            "offset": page_offset,
                            "reported_total": observed_total,
                        },
                    )
                break
            records.extend(page_records)
            if len(page_records) < take:
                if offset + len(records) < observed_total:
                    raise PaginationError(
                        "Miami-Dade property search returned a short page "
                        "before its reported total",
                        url=PROXY_URL,
                        details={
                            "operation": operation,
                            "offset": page_offset,
                            "requested_page_size": take,
                            "returned_page_size": len(page_records),
                            "reported_total": observed_total,
                        },
                    )
                break
            if offset + len(records) >= observed_total:
                break

        next_offset = offset + len(records)
        source_has_more = total_count is not None and next_offset < total_count
        schema = inferred_schema(records)
        return PaginatedFetch(
            records=tuple(records),
            next_cursor=(
                _proxy_cursor(operation, next_offset)
                if source_has_more
                else None
            ),
            schema=schema,
            schema_fingerprint=schema_fingerprint(schema),
            pages_fetched=pages_fetched,
            requests_made=self.request_count - initial_requests,
            truncated_by_cap=potentially_truncated and source_has_more,
            warnings=tuple(warnings),
        )

    def detail(self, folio: str) -> Mapping[str, Any] | None:
        payload = self._request_json(
            PROXY_URL,
            params={
                "Operation": "GetPropertySearchByFolio",
                "clientAppName": "PropertySearch",
                "folioNumber": folio,
            },
        )
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Miami-Dade property detail response is not an object",
                url=PROXY_URL,
            )
        if payload.get("Completed") is not True:
            message = str(payload.get("Message") or "").strip()
            raise SourceResponseError(
                message or "Miami-Dade property detail request did not complete",
                url=PROXY_URL,
                details={"folio": folio},
            )
        property_info = payload.get("PropertyInfo")
        if property_info is None:
            return None
        if not isinstance(property_info, Mapping):
            raise SourceSchemaError(
                "Miami-Dade property detail lacks a PropertyInfo object",
                url=PROXY_URL,
            )
        return payload


def _search_page(
    payload: Any,
    *,
    operation: str,
) -> tuple[list[Mapping[str, Any]], int]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "Miami-Dade property search response is not an object",
            url=PROXY_URL,
            details={"operation": operation},
        )
    if payload.get("Completed") is not True:
        message = str(payload.get("Message") or "").strip()
        raise SourceResponseError(
            message or "Miami-Dade property search did not complete",
            url=PROXY_URL,
            details={"operation": operation},
        )
    rows = payload.get("MinimumPropertyInfos")
    if not isinstance(rows, list) or any(
        not isinstance(row, Mapping) for row in rows
    ):
        raise SourceSchemaError(
            "Miami-Dade property search lacks a valid "
            "MinimumPropertyInfos array",
            url=PROXY_URL,
            details={"operation": operation},
        )
    try:
        total = int(payload.get("Total"))
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "Miami-Dade property search lacks a numeric Total",
            url=PROXY_URL,
            details={"operation": operation},
        ) from error
    if total < 0 or total < len(rows):
        raise SourceSchemaError(
            "Miami-Dade property search returned an invalid Total",
            url=PROXY_URL,
            details={
                "operation": operation,
                "reported_total": total,
                "page_rows": len(rows),
            },
        )
    return list(rows), total


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


def _minimum_interval(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> float:
    limits = access_contract.get("limits") or {}
    return max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )


def _proxy_page_size(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> int:
    limits = access_contract.get("limits") or {}
    reviewed = int(
        limits.get("proxy_page_size")
        or limits.get("property_search_page_size")
        or limits.get("maximum_page_size")
        or args.page_size
    )
    return min(args.page_size, reviewed)


def _proxy_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> MiamiDadePAClient:
    return MiamiDadePAClient(
        session=requests.Session(),
        timeout=args.timeout,
        minimum_interval=_minimum_interval(args, access_contract),
    )


def _arcgis_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> ArcGISRESTClient:
    limits = access_contract.get("limits") or {}
    reviewed_page_size = int(
        limits.get("arcgis_maximum_page_size")
        or limits.get("parcel_geometry_page_size")
        or ARCGIS_PAGE_SIZE
    )
    return ArcGISRESTClient(
        PARCEL_LAYER_URL,
        page_size=min(args.page_size, reviewed_page_size),
        session=_system_trust_session(),
        timeout=args.timeout,
        minimum_interval=_minimum_interval(args, access_contract),
    )


def _query_text(value: str) -> str:
    cleaned = " ".join(str(value).replace("\x00", "").split()).strip()
    if not cleaned:
        raise ValueError("query value must not be blank")
    return cleaned


def _folio_digits(value: str, *, exact: bool) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if not digits:
        raise ValueError("Miami-Dade folio must contain digits")
    if exact and len(digits) != 13:
        raise ValueError("Miami-Dade folio must contain exactly 13 digits")
    if len(digits) > 13:
        raise ValueError("Miami-Dade folio must contain at most 13 digits")
    return digits


def _formatted_folio(value: str) -> str:
    digits = _folio_digits(value, exact=True)
    return f"{digits[:2]}-{digits[2:6]}-{digits[6:9]}-{digits[9:]}"


def _proxy_cursor(operation: str, offset: int) -> str:
    return f"miami-pa:{operation}:offset:{offset}"


def _proxy_cursor_offset(cursor: str | None, operation: str) -> int:
    if cursor is None:
        return 0
    prefix = f"miami-pa:{operation}:offset:"
    if not cursor.startswith(prefix):
        raise ValueError(
            f"Miami-Dade {operation} cursor must have form {prefix}N"
        )
    value = cursor[len(prefix) :]
    if not value.isdigit():
        raise ValueError(
            f"Miami-Dade {operation} cursor must have form {prefix}N"
        )
    return int(value)


def _nonblank(*values: Any) -> list[str]:
    return [str(value).strip() for value in values if str(value or "").strip()]


def _number(value: Any) -> int | float | str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value).strip().replace("$", "").replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return str(value).strip()
    if number.is_integer():
        return int(number)
    return number


def _sum_numbers(*values: Any) -> int | float | str | None:
    normalized = [_number(value) for value in values if value not in (None, "")]
    if not normalized:
        return None
    if any(not isinstance(value, (int, float)) for value in normalized):
        return None
    total = sum(normalized)
    return int(total) if float(total).is_integer() else total


def _sale_date(value: Any) -> tuple[str | None, str]:
    """Normalize the source's US-style sale date while retaining raw input."""

    raw = str(value or "").strip()
    if not raw:
        return None, "unknown"
    try:
        return date.fromisoformat(raw).isoformat(), "day"
    except ValueError:
        pass
    for date_format in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            parsed = datetime.strptime(raw, date_format)
        except ValueError:
            continue
        return parsed.date().isoformat(), "day"
    if raw.startswith("/Date(") and raw.endswith(")/"):
        milliseconds = raw.removeprefix("/Date(").removesuffix(")/")
        if milliseconds.lstrip("-").isdigit():
            parsed = datetime.fromtimestamp(
                int(milliseconds) / 1_000,
                tz=timezone.utc,
            )
            return parsed.date().isoformat(), "day"
    return None, "unknown"


def _source_links(folio: str) -> dict[str, str]:
    digits = _folio_digits(folio, exact=True)
    return {
        "record": f"{PROPERTY_SEARCH_URL}#/?folio={digits}",
        "property_search": PROPERTY_SEARCH_URL,
        "parcel_layer": PARCEL_LAYER_URL,
        "bulk_data": BULK_DATA_URL,
        "public_records_request": PUBLIC_RECORDS_URL,
    }


def _owner_contact_role(name: str) -> str | None:
    normalized = " ".join(name.upper().replace(".", "").split())
    for prefix, role in (
        ("C/O", "care_of"),
        ("CARE OF", "care_of"),
        ("ATTN", "attention"),
        ("ATTENTION", "attention"),
    ):
        if (
            normalized == prefix
            or normalized.startswith(f"{prefix} ")
            or normalized.startswith(f"{prefix}:")
            or normalized.startswith(f"{prefix}-")
        ):
            return role
    return None


def _owner_observations(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    owners: list[dict[str, Any]] = []
    contacts: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("Name") or "").strip()
        if not name:
            continue
        contact_role = _owner_contact_role(name)
        if contact_role:
            contacts.append(
                {
                    "raw_name": name,
                    "role": f"{contact_role}_contact",
                    "assertion_type": "source_contact_line",
                    "confidence": "high",
                    "source_row": dict(row),
                }
            )
            continue
        owners.append(
            {
                "raw_name": name,
                "role": row.get("Role") or "assessment_roll_owner",
                "assertion_type": "assessment_roll",
                "confidence": "high",
                "ownership_percentage": row.get("PercentageOwn"),
                "description": row.get("Description") or None,
                "tenancy_code": (
                    str(row.get("TenancyCd") or "")
                    .replace("\x00", "")
                    .strip()
                    or None
                ),
                "title_caveat": "not_proof_of_legal_or_beneficial_ownership",
            }
        )
    return owners, contacts


def _owner_display_group(
    row: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lines: list[dict[str, Any]] = []
    contacts: list[dict[str, Any]] = []
    for position, source_field in enumerate(
        ("Owner1", "Owner2", "Owner3"),
        start=1,
    ):
        raw_text = str(row.get(source_field) or "").strip()
        if not raw_text:
            continue
        contact_role = _owner_contact_role(raw_text)
        line = {
            "source_field": source_field,
            "position": position,
            "raw_text": raw_text,
            "classification": contact_role or "display_line",
        }
        lines.append(line)
        if contact_role:
            contacts.append(
                {
                    "raw_name": raw_text,
                    "role": f"{contact_role}_contact",
                    "assertion_type": "source_contact_line",
                    "confidence": "high",
                    "source_field": source_field,
                }
            )
    return (
        {
            "classification": "assessment_roll_owner_display_block",
            "lines": lines,
            "requires_detail_resolution": True,
        },
        contacts,
    )


def _normalize_search_record(
    row: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> dict[str, Any]:
    raw = dict(row)
    folio = _folio_digits(str(raw.get("Strap") or ""), exact=True)
    owner_display_group, owner_contacts = _owner_display_group(raw)
    owner_lines = [
        str(line["raw_text"]) for line in owner_display_group["lines"]
    ]
    site_address = " ".join(str(raw.get("SiteAddress") or "").split()) or None
    unit = str(raw.get("SiteUnit") or "").strip() or None
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            folio,
        ),
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "FL",
            "state_fips": "12",
            "county_name": "Miami-Dade",
            "county_geoid": COUNTY_GEOID,
        },
        "native_parcel_id": folio,
        "folio_number": _formatted_folio(folio),
        "record_view": "search_summary",
        "owners": [],
        "owner_display_lines": owner_lines,
        "owner_display_group": owner_display_group,
        "owner_contacts": owner_contacts,
        "situs_address": {
            "raw": site_address,
            "unit": unit,
            "municipality": raw.get("Municipality"),
            "state": "FL",
        },
        "status": raw.get("Status"),
        "neighborhood_description": raw.get("NeighborhoodDescription"),
        "subdivision_description": raw.get("SubdivisionDescription"),
        "source_links": _source_links(folio),
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": raw,
    }


def _assessment_history(
    detail: Mapping[str, Any],
    *,
    assessment_class: str | None,
) -> list[dict[str, Any]]:
    assessment = detail.get("Assessment")
    if not isinstance(assessment, Mapping):
        return []
    rows = assessment.get("AssessmentInfos")
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        try:
            tax_year = int(row.get("Year"))
        except (TypeError, ValueError):
            continue
        normalized.append(
            {
                "tax_year": tax_year,
                "land_value": _number(row.get("LandValue")),
                "improvement_value": _sum_numbers(
                    row.get("BuildingOnlyValue"),
                    row.get("ExtraFeatureValue"),
                ),
                "building_value": _number(row.get("BuildingOnlyValue")),
                "extra_feature_value": _number(row.get("ExtraFeatureValue")),
                "parcel_value": _number(row.get("TotalValue")),
                "assessed_value": _number(row.get("AssessedValue")),
                "currency": "USD",
                "assessment_class": assessment_class,
                "raw": dict(row),
            }
        )
    normalized.sort(key=lambda row: int(row["tax_year"]), reverse=True)
    return normalized


def _sale_history(detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = detail.get("SalesInfos")
    if not isinstance(rows, list):
        return []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        book = str(row.get("OfficialRecordBook") or "").strip() or None
        page = str(row.get("OfficialRecordPage") or "").strip() or None
        sale_id = str(row.get("SaleId") or "").strip() or None
        has_record_reference = bool(
            book
            and page
            and (
                book.replace("0", "").strip()
                or page.replace("0", "").strip()
            )
        )
        source_document_ref = (
            f"OR:{book}:{page}"
            if has_record_reference
            else f"SALE:{sale_id}"
            if sale_id
            else None
        )
        encoded = str(row.get("EncodedRecordBookAndPage") or "").strip()
        raw_sale_date = str(row.get("DateOfSale") or "").strip() or None
        sale_date, date_precision = _sale_date(raw_sale_date)
        normalized.append(
            {
                "source_document_ref": source_document_ref,
                "source_document_url": (
                    f"{CLERK_RECORD_URL}{encoded}" if encoded else None
                ),
                "sale_id": sale_id,
                "sale_date": sale_date,
                "sale_date_raw": raw_sale_date,
                "date_precision": date_precision,
                "consideration": _number(row.get("SalePrice")),
                "document_stamps": _number(row.get("DocumentStamps")),
                "instrument_type": (
                    str(row.get("SaleInstrument") or "").strip() or None
                ),
                "book": book,
                "page": page,
                "grantors": _nonblank(
                    row.get("GrantorName1"),
                    row.get("GrantorName2"),
                ),
                "grantees": _nonblank(
                    row.get("GranteeName1"),
                    row.get("GranteeName2"),
                ),
                "qualified_flag": (
                    str(row.get("QualifiedFlag") or "").strip() or None
                ),
                "qualification_description": row.get(
                    "QualificationDescription"
                ),
                "reason_code": (
                    str(row.get("ReasonCode") or "").strip() or None
                ),
                "raw": dict(row),
            }
        )
    return normalized


def _address_record(value: Any) -> dict[str, Any]:
    row = dict(value) if isinstance(value, Mapping) else {}
    return {
        "raw": " ".join(str(row.get("Address") or "").split()) or None,
        "unit": str(row.get("Unit") or "").strip() or None,
        "city": row.get("City"),
        "state": "FL",
        "postal_code": row.get("Zip"),
        "street_number": row.get("StreetNumber"),
        "street_prefix": row.get("StreetPrefix"),
        "street_name": row.get("StreetName"),
        "street_suffix": row.get("StreetSuffix"),
        "street_suffix_direction": row.get("StreetSuffixDirection"),
        "raw_attributes": row,
    }


def _normalize_detail(detail: Mapping[str, Any]) -> dict[str, Any]:
    property_value = detail.get("PropertyInfo")
    if not isinstance(property_value, Mapping):
        raise ValueError("Miami-Dade property detail lacks PropertyInfo")
    property_info = dict(property_value)
    folio = _folio_digits(
        str(property_info.get("FolioNumber") or ""),
        exact=True,
    )
    owner_rows = detail.get("OwnerInfos")
    owners, owner_contacts = _owner_observations(
        [
            row
            for row in owner_rows
            if isinstance(row, Mapping)
        ]
        if isinstance(owner_rows, list)
        else []
    )
    site_rows = detail.get("SiteAddress")
    site_addresses = [
        _address_record(row)
        for row in site_rows
        if isinstance(row, Mapping)
    ] if isinstance(site_rows, list) else []
    mailing_value = detail.get("MailingAddress")
    mailing = (
        dict(mailing_value) if isinstance(mailing_value, Mapping) else {}
    )
    assessment_class = (
        str(property_info.get("DORDescription") or "").strip() or None
    )
    assessment_history = _assessment_history(
        detail,
        assessment_class=assessment_class,
    )
    latest_assessment = (
        dict(assessment_history[0]) if assessment_history else {}
    )
    latest_year = (
        latest_assessment.get("tax_year")
        or detail.get("RollYear1")
    )
    legal_value = detail.get("LegalDescription")
    legal = dict(legal_value) if isinstance(legal_value, Mapping) else {}
    combined_schema = inferred_schema([dict(detail)])
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel",
            folio,
        ),
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "FL",
            "state_fips": "12",
            "county_name": "Miami-Dade",
            "county_geoid": COUNTY_GEOID,
        },
        "native_parcel_id": folio,
        "folio_number": _formatted_folio(folio),
        "record_view": "property_detail",
        "alternate_parcel_ids": _nonblank(
            property_info.get("ParentFolio")
        ),
        "tax_year": latest_year,
        "status": property_info.get("Status"),
        "property_type": {
            "code": property_info.get("DORCode"),
            "description": assessment_class,
            "primary_zone": property_info.get("PrimaryZone"),
            "primary_zone_description": property_info.get(
                "PrimaryZoneDescription"
            ),
        },
        "owners": owners,
        "owner_display_lines": [
            str(row.get("Name") or "").strip()
            for row in owner_rows
            if isinstance(row, Mapping)
            and str(row.get("Name") or "").strip()
        ]
        if isinstance(owner_rows, list)
        else [],
        "owner_contacts": owner_contacts,
        "situs_address": site_addresses[0] if site_addresses else {},
        "site_addresses": site_addresses,
        "mailing_address": {
            "raw": " ".join(
                _nonblank(
                    mailing.get("Address1"),
                    mailing.get("Address2"),
                    mailing.get("Address3"),
                )
            )
            or None,
            "city": mailing.get("City"),
            "state": mailing.get("State"),
            "postal_code": mailing.get("ZipCode"),
            "country": mailing.get("Country"),
        },
        "assessment": latest_assessment,
        "assessment_history": assessment_history,
        "sale_history": _sale_history(detail),
        "taxable_history": (
            detail.get("Taxable", {}).get("TaxableInfos", [])
            if isinstance(detail.get("Taxable"), Mapping)
            else []
        ),
        "benefit_history": (
            detail.get("Benefit", {}).get("BenefitInfos", [])
            if isinstance(detail.get("Benefit"), Mapping)
            else []
        ),
        "legal_description_raw": legal.get("Description"),
        "property_characteristics": property_info,
        "land": (
            detail.get("Land", {}).get("Landlines", [])
            if isinstance(detail.get("Land"), Mapping)
            else []
        ),
        "improvements": (
            detail.get("Building", {}).get("BuildingInfos", [])
            if isinstance(detail.get("Building"), Mapping)
            else []
        ),
        "extra_features": (
            detail.get("ExtraFeature", {}).get("ExtraFeatureInfos", [])
            if isinstance(detail.get("ExtraFeature"), Mapping)
            else []
        ),
        "district": detail.get("District"),
        "classified_agriculture": detail.get("ClassifiedAgInfo"),
        "source_links": _source_links(folio),
        "response_schema_fingerprint": schema_fingerprint(combined_schema),
        "raw_attributes": dict(detail),
    }


def _normalize_geometry(
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise ValueError("Miami-Dade parcel feature lacks attributes")
    attributes = dict(attributes_value)
    folio = _folio_digits(str(attributes.get("FOLIO") or ""), exact=True)
    geometry = feature.get("geometry")
    if not isinstance(geometry, Mapping):
        raise ValueError("Miami-Dade parcel feature lacks geometry")
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "parcel_geometry",
            str(attributes.get("OBJECTID") or folio),
        ),
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "FL",
            "state_fips": "12",
            "county_name": "Miami-Dade",
            "county_geoid": COUNTY_GEOID,
        },
        "native_parcel_id": folio,
        "folio_number": _formatted_folio(folio),
        "record_view": "parcel_geometry",
        "source_object_id": attributes.get("OBJECTID"),
        "situs_address": {
            "raw": attributes.get("TRUE_SITE_ADDR"),
            "state": "FL",
        },
        "condominium_flag": attributes.get("CONDO_FLAG"),
        "parent_folio": attributes.get("PARENT_FOLIO"),
        "geometry": dict(geometry),
        "geometry_format": "esri_json",
        "geometry_crs": "EPSG:4326",
        "geometry_disclaimer": SOURCE_WARNINGS[2],
        "source_links": _source_links(folio),
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": attributes,
    }


def _geometry_where(folios: Sequence[str]) -> str:
    values = ",".join(f"'{_folio_digits(folio, exact=True)}'" for folio in folios)
    return f"FOLIO IN ({values})"


def _fetch_geometry(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
    folios: Sequence[str],
    *,
    requested_limit: int | None = None,
    cursor: str | None = None,
) -> tuple[list[dict[str, Any]], PaginatedFetch | None]:
    unique_folios = sorted(
        {_folio_digits(folio, exact=True) for folio in folios}
    )
    if not unique_folios:
        return [], None
    client = _arcgis_client(args, access_contract)
    records: list[dict[str, Any]] = []
    last_fetch: PaginatedFetch | None = None
    for start in range(0, len(unique_folios), 100):
        batch = unique_folios[start : start + 100]
        batch_limit = requested_limit if len(unique_folios) == len(batch) else None
        fetched = client.query(
            where=_geometry_where(batch),
            out_fields=PARCEL_OUT_FIELDS,
            parameters={
                "orderByFields": PARCEL_ORDER_BY,
                "outSR": 4326,
            },
            requested_limit=batch_limit,
            cursor=cursor if start == 0 else None,
            return_geometry=True,
        )
        last_fetch = fetched
        records.extend(
            _normalize_geometry(
                feature,
                response_schema_fingerprint=fetched.schema_fingerprint,
            )
            for feature in fetched.records
        )
    return records, last_fetch


def _attach_geometry(
    records: Sequence[Mapping[str, Any]],
    geometry_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_folio: dict[str, list[Mapping[str, Any]]] = {}
    for geometry_record in geometry_records:
        folio = str(geometry_record.get("native_parcel_id") or "")
        by_folio.setdefault(folio, []).append(geometry_record)
    enriched: list[dict[str, Any]] = []
    for record in records:
        output = dict(record)
        matches = by_folio.get(str(record.get("native_parcel_id") or ""), [])
        if matches:
            output["geometry_features"] = [
                {
                    "source_object_id": match.get("source_object_id"),
                    "geometry": match.get("geometry"),
                    "condominium_flag": match.get("condominium_flag"),
                    "parent_folio": match.get("parent_folio"),
                }
                for match in matches
            ]
            if len(matches) == 1:
                output["geometry"] = matches[0].get("geometry")
            output["geometry_format"] = "esri_json"
            output["geometry_crs"] = "EPSG:4326"
            output["geometry_disclaimer"] = SOURCE_WARNINGS[2]
        enriched.append(output)
    return enriched


def build_query(
    operation: str,
    selector: str | None,
    *,
    unit: str | None,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Miami-Dade County, Florida",
            state_code="FL",
            county_fips=COUNTY_GEOID,
            locality="Miami-Dade County",
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "unit": unit,
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
    command = args.command
    selector = getattr(args, "query", None)
    unit = getattr(args, "unit", None)
    limit = 1 if command in {"detail", "history", "probe"} else args.limit
    query = build_query(
        command,
        selector,
        unit=unit,
        limit=limit,
        cursor=args.cursor,
        return_geometry=args.geometry or command == "geometry",
    )
    try:
        access_contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args)
        )
        warnings: list[str] = list(SOURCE_WARNINGS)
        result_errors: list[PublicRecordsError] = []
        fetched: PaginatedFetch | None = None

        if command == "geometry":
            folio = _folio_digits(selector or "", exact=True)
            records, fetched = _fetch_geometry(
                args,
                access_contract,
                [folio],
                requested_limit=limit,
                cursor=args.cursor,
            )
        elif command in {"detail", "history"}:
            folio = _folio_digits(selector or "", exact=True)
            detail = _proxy_client(args, access_contract).detail(folio)
            records = [_normalize_detail(detail)] if detail is not None else []
            if command == "history":
                records = [
                    {**record, "record_view": "history"}
                    for record in records
                ]
        elif command == "folio":
            folio = _folio_digits(selector or "", exact=False)
            if len(folio) == 13:
                detail = _proxy_client(args, access_contract).detail(folio)
                records = [_normalize_detail(detail)] if detail is not None else []
            else:
                fetched = _proxy_client(args, access_contract).search(
                    "partial_folio",
                    folio,
                    requested_limit=limit,
                    page_size=_proxy_page_size(args, access_contract),
                    cursor=args.cursor,
                    max_records=args.max_records,
                )
                records = [
                    _normalize_search_record(
                        record,
                        response_schema_fingerprint=fetched.schema_fingerprint,
                    )
                    for record in fetched.records
                ]
                warnings.extend(fetched.warnings)
        else:
            proxy_operation = "address" if command == "probe" else command
            proxy_selector = (
                "111 NW 1 ST"
                if command == "probe"
                else _query_text(selector or "")
            )
            fetched = _proxy_client(args, access_contract).search(
                proxy_operation,
                proxy_selector,
                requested_limit=limit,
                page_size=_proxy_page_size(args, access_contract),
                cursor=args.cursor,
                unit=unit,
                max_records=args.max_records,
            )
            records = [
                _normalize_search_record(
                    record,
                    response_schema_fingerprint=fetched.schema_fingerprint,
                )
                for record in fetched.records
            ]
            warnings.extend(fetched.warnings)

        if args.geometry and command != "geometry" and records:
            try:
                geometry_records, _geometry_fetch = _fetch_geometry(
                    args,
                    access_contract,
                    [
                        str(record.get("native_parcel_id") or "")
                        for record in records
                    ],
                )
                records = _attach_geometry(records, geometry_records)
            except PublicRecordsHTTPError as error:
                result_errors.append(error.to_contract_error())
                warnings.append(
                    "Property records were returned without parcel geometry."
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
                    "Property records were returned without parcel geometry."
                )

        next_cursor = fetched.next_cursor if fetched is not None else None
        truncated_by_cap = (
            fetched.truncated_by_cap if fetched is not None else False
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
        summary=f"Miami-Dade property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"Miami-Dade property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        owner_names = ", ".join(
            str(owner.get("raw_name") or "")
            for owner in record.get("owners", [])
        )
        if not owner_names:
            owner_names = ", ".join(
                str(line)
                for line in record.get("owner_display_lines", [])
            )
        print(
            f"  {record.get('folio_number') or record.get('native_parcel_id')} "
            f"| {record.get('situs_address', {}).get('raw') or '?'} "
            f"| {owner_names or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cursor", help="Continuation cursor from a prior result")
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Enrich returned property records with official parcel geometry",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=PROXY_PAGE_SIZE,
        help="Records requested per source page",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional caller-selected overall record ceiling",
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
        description=(
            "Query the official Miami-Dade Property Appraiser search and "
            "parcel geometry services"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)
    owner = sub.add_parser("owner", help="Search current tax-roll owner names")
    owner.add_argument("query")
    _add_shared_arguments(owner)

    address = sub.add_parser("address", help="Search property situs addresses")
    address.add_argument("query")
    address.add_argument("--unit", help="Optional unit or suite selector")
    _add_shared_arguments(address)

    for command, help_text in (
        ("folio", "Look up an exact or partial 13-digit folio"),
        ("detail", "Fetch rich property detail"),
        ("history", "Fetch assessment, owner, and sale history"),
        ("geometry", "Fetch official parcel polygon geometry"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        _add_shared_arguments(command_parser)

    probe = sub.add_parser("probe", help="Run one bounded live source query")
    _add_shared_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if (
        args.limit <= 0
        or args.page_size <= 0
        or (args.max_records is not None and args.max_records <= 0)
    ):
        parser.error(
            "limit and page-size must be positive; max-records is optional"
        )
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
