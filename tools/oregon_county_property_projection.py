"""Pure projections for selected Oregon county property adapters.

The source adapters retain richer, source-specific structures than the shared
property sidecar consumes.  This module adds the small generic field set used by
``ingest_property_records`` while leaving the native fields in each record.

Wasco survey layers are deliberately classified as observation-only.  Some
layers identify scans or plats, but a row in those indexes is not by itself a
deed or another title instrument.

Washington County assessment/property reports project only when the returned
record is an assessor representation. Survey Explorer, ArcGIS geometry,
tax-map, situs, and downloaded-document records remain source observations.

Multnomah County SAIL tax-parcel rows project to assessor snapshots. Its seven
survey, plat, corner, road, field-book, image-viewer, and PDF representations
remain source observations.

Washington County planning and permit sources use record-grain classification.
Dated casefiles and project, activity, inspection, or review reports project as
property events. Vocabularies, route catalogs, document representations, and
undated index rows remain source observations.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping, Sequence


YAMHILL_ASCEND_SOURCE_ID = "us-or-yamhill-county-ascendweb-property"
YAMHILL_TAXLOT_SOURCE_ID = "us-or-yamhill-county-at-taxlots"
YAMHILL_RETIRED_TAXLOT_SOURCE_ID = "us-or-yamhill-county-retired-taxlots"
YAMHILL_PERMIT_SOURCE_ID = "us-or-yamhill-county-assessment-permits"

CLACKAMAS_ASCEND_SOURCE_ID = "us-or-clackamas-county-ascendweb-property"
CLACKAMAS_CMAP_SOURCE_ID = "us-or-clackamas-county-cmap-taxlots"

WASCO_ASCEND_SOURCE_ID = "us-or-wasco-county-ascendweb-property"
WASCO_TAXLOT_SOURCE_ID = "us-or-wasco-county-taxlots"
WASCO_ROAD_RECORDS_SOURCE_ID = "us-or-wasco-county-surveyor-road-records"
WASCO_FILE_CABINET_SOURCE_ID = (
    "us-or-wasco-county-surveyor-file-cabinet-surveys"
)
WASCO_ROLL_MAPS_SOURCE_ID = "us-or-wasco-county-surveyor-roll-maps"
WASCO_COMMISSIONERS_SOURCE_ID = (
    "us-or-wasco-county-surveyor-commissioner-records"
)
WASCO_LAND_CORNERS_SOURCE_ID = "us-or-wasco-county-surveyor-land-corners"
WASCO_PLATS_SOURCE_ID = "us-or-wasco-county-surveyor-plats"
WASCO_SUBDIVISIONS_SOURCE_ID = "us-or-wasco-county-surveyor-subdivisions"
WASCO_SURVEY_BOOK_SOURCE_ID = "us-or-wasco-county-surveyor-survey-book"

WASHINGTON_SURVEY_API_SOURCE_ID = (
    "us-or-washington-county-survey-explorer-api"
)
WASHINGTON_SURVEY_MAP_SOURCE_ID = (
    "us-or-washington-county-survey-explorer-arcgis"
)
WASHINGTON_TAXLOT_SOURCE_ID = "us-or-washington-county-taxlots"
WASHINGTON_SITUS_SOURCE_ID = "us-or-washington-county-situs-addresses"
WASHINGTON_INTERMAP_SOURCE_ID = "us-or-washington-county-intermap-property"
WASHINGTON_TAX_SOURCE_ID = "us-or-washington-county-washcotax"
WASHINGTON_CASEFILE_SOURCE_ID = "us-or-washington-county-casefiles"
WASHINGTON_TAXLOT_ACTIVITY_SOURCE_ID = (
    "us-or-washington-county-taxlot-project-activity"
)
WASHINGTON_BUILDING_PERMIT_SOURCE_ID = (
    "us-or-washington-county-building-permits"
)
WASHINGTON_PERMIT_REPORT_SOURCE_ID = "us-or-washington-county-permit-reports"
WASHINGTON_ACCELA_SOURCE_ID = (
    "us-or-washington-county-accela-current-planning"
)
WASHINGTON_DOCUMENT_ROUTE_SOURCE_ID = (
    "us-or-washington-county-land-use-document-routes"
)

MULTNOMAH_TAX_PARCEL_SOURCE_ID = "us-or-multnomah-sail-tax-parcels"
MULTNOMAH_SURVEY_SOURCE_ID = "us-or-multnomah-sail-survey-records"
MULTNOMAH_SUBDIVISION_SOURCE_ID = "us-or-multnomah-sail-subdivision-plats"
MULTNOMAH_PARTITION_SOURCE_ID = "us-or-multnomah-sail-partition-plats"
MULTNOMAH_CONDOMINIUM_SOURCE_ID = "us-or-multnomah-sail-condominium-plats"
MULTNOMAH_ROAD_SOURCE_ID = "us-or-multnomah-sail-road-surveys"
MULTNOMAH_CORNER_SOURCE_ID = (
    "us-or-multnomah-sail-bearing-tree-public-land-corners"
)
MULTNOMAH_FIELD_BOOK_SOURCE_ID = (
    "us-or-multnomah-sail-field-book-quarter-sheets"
)

YAMHILL_ASSESSOR_SOURCE_IDS = frozenset(
    {
        YAMHILL_ASCEND_SOURCE_ID,
        YAMHILL_TAXLOT_SOURCE_ID,
        YAMHILL_RETIRED_TAXLOT_SOURCE_ID,
    }
)
CLACKAMAS_ASSESSOR_SOURCE_IDS = frozenset(
    {
        CLACKAMAS_ASCEND_SOURCE_ID,
        CLACKAMAS_CMAP_SOURCE_ID,
    }
)
WASCO_ASSESSOR_SOURCE_IDS = frozenset(
    {
        WASCO_ASCEND_SOURCE_ID,
        WASCO_TAXLOT_SOURCE_ID,
    }
)
WASHINGTON_ASSESSOR_SOURCE_IDS = frozenset(
    {
        WASHINGTON_INTERMAP_SOURCE_ID,
        WASHINGTON_TAX_SOURCE_ID,
    }
)
MULTNOMAH_ASSESSOR_SOURCE_IDS = frozenset(
    {MULTNOMAH_TAX_PARCEL_SOURCE_ID}
)
ASSESSOR_SOURCE_IDS = frozenset(
    {
        *YAMHILL_ASSESSOR_SOURCE_IDS,
        *CLACKAMAS_ASSESSOR_SOURCE_IDS,
        *WASCO_ASSESSOR_SOURCE_IDS,
        *WASHINGTON_ASSESSOR_SOURCE_IDS,
        *MULTNOMAH_ASSESSOR_SOURCE_IDS,
    }
)
WASHINGTON_CASE_PERMIT_EVENT_SOURCE_IDS = frozenset(
    {
        WASHINGTON_CASEFILE_SOURCE_ID,
        WASHINGTON_PERMIT_REPORT_SOURCE_ID,
    }
)
WASHINGTON_CASE_PERMIT_OBSERVATION_SOURCE_IDS = frozenset(
    {
        WASHINGTON_TAXLOT_ACTIVITY_SOURCE_ID,
        WASHINGTON_BUILDING_PERMIT_SOURCE_ID,
        WASHINGTON_ACCELA_SOURCE_ID,
        WASHINGTON_DOCUMENT_ROUTE_SOURCE_ID,
    }
)
WASHINGTON_CASE_PERMIT_SOURCE_IDS = frozenset(
    {
        *WASHINGTON_CASE_PERMIT_EVENT_SOURCE_IDS,
        *WASHINGTON_CASE_PERMIT_OBSERVATION_SOURCE_IDS,
    }
)
PROPERTY_EVENT_SOURCE_IDS = frozenset(
    {
        YAMHILL_PERMIT_SOURCE_ID,
        *WASHINGTON_CASE_PERMIT_EVENT_SOURCE_IDS,
    }
)
PROPERTY_EVENT_PARCEL_ALIAS_SOURCE_IDS: Mapping[str, str] = {
    YAMHILL_PERMIT_SOURCE_ID: YAMHILL_TAXLOT_SOURCE_ID,
    WASHINGTON_CASEFILE_SOURCE_ID: WASHINGTON_INTERMAP_SOURCE_ID,
    WASHINGTON_PERMIT_REPORT_SOURCE_ID: WASHINGTON_INTERMAP_SOURCE_ID,
}
WASCO_SURVEY_SOURCE_IDS = frozenset(
    {
        WASCO_ROAD_RECORDS_SOURCE_ID,
        WASCO_FILE_CABINET_SOURCE_ID,
        WASCO_ROLL_MAPS_SOURCE_ID,
        WASCO_COMMISSIONERS_SOURCE_ID,
        WASCO_LAND_CORNERS_SOURCE_ID,
        WASCO_PLATS_SOURCE_ID,
        WASCO_SUBDIVISIONS_SOURCE_ID,
        WASCO_SURVEY_BOOK_SOURCE_ID,
    }
)
WASHINGTON_OBSERVATION_SOURCE_IDS = frozenset(
    {
        WASHINGTON_SURVEY_API_SOURCE_ID,
        WASHINGTON_SURVEY_MAP_SOURCE_ID,
        WASHINGTON_TAXLOT_SOURCE_ID,
        WASHINGTON_SITUS_SOURCE_ID,
    }
)
WASHINGTON_PROPERTY_SOURCE_IDS = frozenset(
    {
        *WASHINGTON_ASSESSOR_SOURCE_IDS,
        *WASHINGTON_OBSERVATION_SOURCE_IDS,
    }
)
MULTNOMAH_OBSERVATION_SOURCE_IDS = frozenset(
    {
        MULTNOMAH_SURVEY_SOURCE_ID,
        MULTNOMAH_SUBDIVISION_SOURCE_ID,
        MULTNOMAH_PARTITION_SOURCE_ID,
        MULTNOMAH_CONDOMINIUM_SOURCE_ID,
        MULTNOMAH_ROAD_SOURCE_ID,
        MULTNOMAH_CORNER_SOURCE_ID,
        MULTNOMAH_FIELD_BOOK_SOURCE_ID,
    }
)
MULTNOMAH_PROPERTY_SOURCE_IDS = frozenset(
    {
        *MULTNOMAH_ASSESSOR_SOURCE_IDS,
        *MULTNOMAH_OBSERVATION_SOURCE_IDS,
    }
)
OBSERVATION_ONLY_SOURCE_IDS = frozenset(
    {
        *WASCO_SURVEY_SOURCE_IDS,
        *WASHINGTON_OBSERVATION_SOURCE_IDS,
        *WASHINGTON_CASE_PERMIT_OBSERVATION_SOURCE_IDS,
        *MULTNOMAH_OBSERVATION_SOURCE_IDS,
    }
)
SUPPORTED_SOURCE_IDS = frozenset(
    {
        *ASSESSOR_SOURCE_IDS,
        *PROPERTY_EVENT_SOURCE_IDS,
        *OBSERVATION_ONLY_SOURCE_IDS,
    }
)

SOURCE_JURISDICTIONS: Mapping[str, tuple[str, str]] = {
    **{
        source_id: ("41071", "Yamhill")
        for source_id in {
            *YAMHILL_ASSESSOR_SOURCE_IDS,
            YAMHILL_PERMIT_SOURCE_ID,
        }
    },
    **{
        source_id: ("41005", "Clackamas")
        for source_id in CLACKAMAS_ASSESSOR_SOURCE_IDS
    },
    **{
        source_id: ("41065", "Wasco")
        for source_id in {
            *WASCO_ASSESSOR_SOURCE_IDS,
            *WASCO_SURVEY_SOURCE_IDS,
        }
    },
    **{
        source_id: ("41067", "Washington")
        for source_id in {
            *WASHINGTON_PROPERTY_SOURCE_IDS,
            *WASHINGTON_CASE_PERMIT_SOURCE_IDS,
        }
    },
    **{
        source_id: ("41051", "Multnomah")
        for source_id in MULTNOMAH_PROPERTY_SOURCE_IDS
    },
}

WASCO_SURVEY_OBSERVATION_CLASSES: Mapping[str, str] = {
    WASCO_ROAD_RECORDS_SOURCE_ID: "road_record_spatial_index",
    WASCO_FILE_CABINET_SOURCE_ID: "surveyor_file_cabinet_index",
    WASCO_ROLL_MAPS_SOURCE_ID: "historic_roll_map_index",
    WASCO_COMMISSIONERS_SOURCE_ID: "commissioner_journal_spatial_index",
    WASCO_LAND_CORNERS_SOURCE_ID: "land_corner_reference_with_scan",
    WASCO_PLATS_SOURCE_ID: "plat_outline_index",
    WASCO_SUBDIVISIONS_SOURCE_ID: "subdivision_outline",
    WASCO_SURVEY_BOOK_SOURCE_ID: "survey_book_reference_with_scan",
}

WASHINGTON_OBSERVATION_CLASSES: Mapping[str, str] = {
    WASHINGTON_SURVEY_API_SOURCE_ID: "survey_explorer_index_or_document",
    WASHINGTON_SURVEY_MAP_SOURCE_ID: "survey_explorer_geometry_index",
    WASHINGTON_TAXLOT_SOURCE_ID: "current_taxlot_geometry_index",
    WASHINGTON_SITUS_SOURCE_ID: "situs_address_point_index",
    WASHINGTON_INTERMAP_SOURCE_ID: "intermap_tax_map_representation",
    WASHINGTON_TAX_SOURCE_ID: "property_tax_statement_document",
}

MULTNOMAH_OBSERVATION_CLASSES: Mapping[str, str] = {
    MULTNOMAH_SURVEY_SOURCE_ID: "sail_survey_record_or_document",
    MULTNOMAH_SUBDIVISION_SOURCE_ID: "sail_subdivision_plat_or_document",
    MULTNOMAH_PARTITION_SOURCE_ID: "sail_partition_plat_or_document",
    MULTNOMAH_CONDOMINIUM_SOURCE_ID: "sail_condominium_plat_or_document",
    MULTNOMAH_ROAD_SOURCE_ID: "sail_road_survey_or_document",
    MULTNOMAH_CORNER_SOURCE_ID: "sail_land_corner_or_document",
    MULTNOMAH_FIELD_BOOK_SOURCE_ID: "sail_field_book_or_document",
}

WASHINGTON_CASE_PERMIT_OBSERVATION_CLASSES: Mapping[str, str] = {
    WASHINGTON_CASEFILE_SOURCE_ID: "planning_casefile_index_or_vocabulary",
    WASHINGTON_TAXLOT_ACTIVITY_SOURCE_ID: "taxlot_project_activity_index",
    WASHINGTON_BUILDING_PERMIT_SOURCE_ID: "building_permit_index_or_vocabulary",
    WASHINGTON_PERMIT_REPORT_SOURCE_ID: "permit_report_supporting_record",
    WASHINGTON_ACCELA_SOURCE_ID: "current_planning_detail_or_document",
    WASHINGTON_DOCUMENT_ROUTE_SOURCE_ID: "land_use_document_route_catalog",
}

ProjectionKind = Literal["assessor", "property_event", "observation_only"]


class PropertyProjectionError(ValueError):
    """Raised when a record cannot be projected under its declared source."""


@dataclass(frozen=True)
class PropertyProjection:
    """One pure projection decision for the shared property ingester."""

    kind: ProjectionKind
    source_id: str
    record: dict[str, Any]
    reason: str | None = None
    source_native_id: str | None = None
    observation_kind: str | None = None


_ASSESSMENT_VALUE_FIELDS = {
    "AVR": "assessed_value",
    "MKTTL": "market_value",
    "assessed value": "assessed_value",
    "real market total": "market_value",
    "real market value": "market_value",
    "real mkt total": "market_value",
    "market land": "land_value",
    "real market land": "land_value",
    "land value": "land_value",
    "market improvements": "improvement_value",
    "real market improvements": "improvement_value",
    "improvement value": "improvement_value",
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _source_id(record: Mapping[str, Any], source_id: str | None) -> str:
    declared = _text(record.get("source_id"))
    selected = _text(source_id) or declared
    if not selected:
        raise PropertyProjectionError("record projection requires a source_id")
    if declared and declared != selected:
        raise PropertyProjectionError(
            f"record source_id {declared!r} does not match {selected!r}"
        )
    if selected not in SUPPORTED_SOURCE_IDS:
        raise PropertyProjectionError(f"unsupported property source_id {selected!r}")
    return selected


def _jurisdiction(source_id: str) -> dict[str, str]:
    geoid, county = SOURCE_JURISDICTIONS[source_id]
    return {
        "country": "US",
        "state_code": "OR",
        "county_geoid": geoid,
        "county_name": county,
    }


def _deduplicated_text(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = _text(raw_value)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_taxlot_alias(value: Any) -> str | None:
    """Return a stable comparison alias without replacing the published value."""

    text = _text(value)
    if not text:
        return None
    normalized = "".join(character for character in text.upper() if character.isalnum())
    return normalized or None


def _published_owners(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    owners: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        raw_name = _text(value.get("raw_name") or value.get("name"))
        if not raw_name:
            continue
        owners.append({**deepcopy(dict(value)), "raw_name": raw_name})
    return owners


def _owners_from_account_parties(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    owners: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        role = (_text(value.get("role")) or "").casefold()
        raw_name = _text(value.get("name") or value.get("raw_name"))
        if role != "owner" or not raw_name:
            continue
        owners.append(
            {
                **deepcopy(dict(value)),
                "raw_name": raw_name,
                "confidence": "high",
            }
        )
    return owners


def _address(raw: Any, **parts: Any) -> dict[str, Any] | None:
    raw_text = _text(raw)
    if not raw_text:
        return None
    result: dict[str, Any] = {"raw": raw_text, "country": "US"}
    for key, value in parts.items():
        normalized = _text(value)
        if normalized:
            result[key] = normalized
    return result


def _yamhill_address(value: Any, *, mailing: bool) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    parts = value.get("raw_parts")
    if not isinstance(parts, list):
        return _address(value.get("formatted"))
    if mailing:
        street = " ".join(
            part for part in (_text(item) for item in parts[:2]) if part
        )
        return _address(
            street,
            city=parts[2] if len(parts) > 2 else None,
            state=parts[3] if len(parts) > 3 else None,
            postal_code=parts[4] if len(parts) > 4 else None,
        )
    return _address(
        parts[0] if parts else value.get("formatted"),
        city=parts[1] if len(parts) > 1 else None,
        state=parts[2] if len(parts) > 2 else None,
        postal_code=parts[3] if len(parts) > 3 else None,
    )


def _wasco_mailing_address(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    parts = value.get("raw_parts")
    if not isinstance(parts, list):
        return _address(value.get("formatted"))
    street = " ".join(
        part for part in (_text(item) for item in parts[:3]) if part
    )
    return _address(
        street,
        city=parts[3] if len(parts) > 3 else None,
        state=parts[4] if len(parts) > 4 else None,
        postal_code=parts[5] if len(parts) > 5 else None,
    )


def _money_value(value: Any) -> int | float | None:
    text = _text(value)
    if not text:
        return None
    normalized = text.replace("$", "").replace(",", "").strip()
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        amount = float(normalized)
    except ValueError:
        return None
    return int(amount) if amount.is_integer() else amount


def _native_ids(record: Mapping[str, Any]) -> dict[str, Any]:
    value = record.get("native_ids")
    return dict(value) if isinstance(value, Mapping) else {}


def _representation_fields(record: Mapping[str, Any]) -> dict[str, str]:
    representation = record.get("native_representation")
    if not isinstance(representation, Mapping):
        return {}
    pairs = representation.get("field_pairs")
    if not isinstance(pairs, list):
        return {}
    fields: dict[str, str] = {}
    for pair in pairs:
        if not isinstance(pair, Mapping):
            continue
        label = _text(pair.get("label"))
        value = _text(pair.get("value"))
        if label and value:
            fields.setdefault(label.casefold(), value)
    return fields


def _first_field(
    fields: Mapping[str, str],
    *labels: str,
) -> str | None:
    for label in labels:
        value = _text(fields.get(label.casefold()))
        if value:
            return value
    return None


def _assessment_field(series: Mapping[str, Any]) -> str | None:
    code = _text(series.get("value_code"))
    if code and code.upper() in _ASSESSMENT_VALUE_FIELDS:
        return _ASSESSMENT_VALUE_FIELDS[code.upper()]
    label = (_text(series.get("value_type")) or "").casefold()
    return _ASSESSMENT_VALUE_FIELDS.get(label)


def _assessment_history(value_history: Any) -> list[dict[str, Any]]:
    if not isinstance(value_history, list):
        return []
    by_year: dict[str, dict[str, Any]] = {}
    for value in value_history:
        if not isinstance(value, Mapping):
            continue
        field = _assessment_field(value)
        values_by_year = value.get("values_by_tax_year")
        if not field or not isinstance(values_by_year, Mapping):
            continue
        for raw_year, raw_observation in values_by_year.items():
            year = _text(raw_year)
            if not year or not re.fullmatch(r"20[0-9]{2}", year):
                continue
            if not isinstance(raw_observation, Mapping):
                continue
            amount = raw_observation.get("amount")
            if amount in (None, ""):
                continue
            assessment = by_year.setdefault(
                year,
                {
                    "tax_year": year,
                    "source_value_observations": {},
                },
            )
            assessment[field] = amount
            assessment["source_value_observations"][field] = {
                "value_type": value.get("value_type"),
                "value_code": value.get("value_code"),
                **deepcopy(dict(raw_observation)),
            }
    return [by_year[year] for year in sorted(by_year, reverse=True)]


def _date_prefix(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    iso_match = re.match(r"^(20[0-9]{2}-[0-9]{2}-[0-9]{2})", text)
    if iso_match:
        return iso_match.group(1)
    for pattern in ("%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _sale_history(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    sales: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        sale_date = _text(
            value.get("sale_date_iso")
            or value.get("transfer_date_iso")
            or value.get("sale_date")
            or value.get("transfer_date")
        )
        recording_date = _text(
            value.get("recording_date_iso")
            or value.get("receipt_date_iso")
            or value.get("entry_date_iso")
        )
        recording_number = _text(value.get("recording_number"))
        if not sale_date and not recording_date and not recording_number:
            continue
        sales.append(
            {
                **deepcopy(dict(value)),
                "sale_date": _date_prefix(sale_date),
                "source_document_date": _date_prefix(recording_date),
                "source_document_ref": recording_number,
                "consideration": value.get("sale_amount_value"),
            }
        )
    return sales


def _latest_sale(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    recording_number = _text(
        value.get("recording_number") or value.get("document_number")
    )
    sale_date = _date_prefix(
        value.get("sale_date_iso")
        or value.get("sale_date_raw")
        or value.get("document_date_raw")
    )
    consideration = (
        value.get("sale_price")
        if value.get("sale_price") not in (None, "")
        else value.get("sale_amount_value")
    )
    if not recording_number and not sale_date:
        return None
    return {
        **deepcopy(dict(value)),
        "sale_date": sale_date,
        "source_document_date": _date_prefix(value.get("document_date_raw")),
        "source_document_ref": recording_number,
        "consideration": consideration,
    }


def _apply_common_assessor_fields(
    projected: dict[str, Any],
    *,
    source_id: str,
    native_parcel_id: Any,
    aliases: Sequence[Any],
) -> None:
    native_id = _text(native_parcel_id)
    if not native_id:
        raise PropertyProjectionError(
            f"{source_id} assessor record lacks a stable parcel/account identifier"
        )
    projected["source_id"] = source_id
    projected["native_parcel_id"] = native_id
    projected["jurisdiction"] = _jurisdiction(source_id)
    projected["alternate_parcel_ids"] = [
        value
        for value in _deduplicated_text(aliases)
        if value != native_id
    ]


def _project_account_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    projected = deepcopy(dict(record))
    account_record = record.get("assessment_account")
    native = (
        dict(account_record)
        if isinstance(account_record, Mapping)
        else dict(record)
    )
    taxlot_record = (
        dict(record["taxlot"]) if isinstance(record.get("taxlot"), Mapping) else {}
    )
    account_number = _text(
        native.get("account_number") or record.get("account_number")
    )
    map_taxlot = _text(
        native.get("alternate_map_taxlot")
        or native.get("normalized_map_taxlot")
        or taxlot_record.get("map_taxlot")
        or taxlot_record.get("normalized_map_taxlot")
    )
    _apply_common_assessor_fields(
        projected,
        source_id=source_id,
        native_parcel_id=account_number,
        aliases=(
            map_taxlot,
            normalize_taxlot_alias(map_taxlot),
            taxlot_record.get("source_record_id"),
        ),
    )
    source_url = _text(native.get("source_url"))
    if source_url and not _text(projected.get("source_url")):
        projected["source_url"] = source_url
    address = _address(
        native.get("situs_address_raw") or native.get("situs_address")
    )
    if address:
        projected["situs_address"] = address
    owners = _owners_from_account_parties(native.get("parties"))
    projected["owners"] = owners
    history = _assessment_history(native.get("value_history"))
    if history:
        projected["assessment_history"] = history
        projected["tax_year"] = history[0]["tax_year"]
    sales = _sale_history(native.get("sales"))
    if sales:
        projected["sale_history"] = sales
    record_kind = _text(native.get("record_kind") or record.get("record_kind"))
    if record_kind == "property_account":
        projected["record_view"] = "property_detail"
        projected["snapshot_complete"] = True
    return projected


def _project_yamhill_taxlot(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    projected = deepcopy(dict(record))
    source_record_id = record.get("source_record_id") or record.get("object_id")
    account = record.get("account_number")
    map_taxlot = record.get("map_taxlot")
    _apply_common_assessor_fields(
        projected,
        source_id=source_id,
        native_parcel_id=source_record_id,
        aliases=(
            account,
            map_taxlot,
            normalize_taxlot_alias(map_taxlot),
            record.get("global_id"),
        ),
    )
    if source_id == YAMHILL_RETIRED_TAXLOT_SOURCE_ID:
        projected["owners"] = []
        projected["projection_metadata"] = {
            "owner_projection": "not_projected_from_retired_representation",
            "published_owner_rows_preserved": bool(record.get("owners")),
        }
    else:
        projected["owners"] = _published_owners(record.get("owners"))
    situs = _yamhill_address(record.get("situs"), mailing=False)
    mailing = _yamhill_address(record.get("mailing"), mailing=True)
    if situs:
        projected["situs_address"] = situs
    if mailing:
        projected["mailing_address"] = mailing
    latest_sale = _latest_sale(record.get("latest_deed_or_sale"))
    if latest_sale:
        projected["last_sale"] = latest_sale
    projected["geometry_format"] = "geojson"
    projected["snapshot_complete"] = (
        source_id != YAMHILL_RETIRED_TAXLOT_SOURCE_ID
    )
    return projected


def _project_clackamas_cmap(record: Mapping[str, Any]) -> dict[str, Any]:
    projected = deepcopy(dict(record))
    source_id = CLACKAMAS_CMAP_SOURCE_ID
    source_record_id = record.get("source_record_id") or record.get("object_id")
    account = record.get("account_number")
    map_taxlot = record.get("map_taxlot")
    _apply_common_assessor_fields(
        projected,
        source_id=source_id,
        native_parcel_id=source_record_id,
        aliases=(account, map_taxlot, normalize_taxlot_alias(map_taxlot)),
    )
    situs = record.get("situs")
    if isinstance(situs, Mapping):
        address = _address(
            situs.get("address") or situs.get("full"),
            city=situs.get("city"),
            state="OR",
            postal_code=situs.get("postal_code"),
        )
        if address:
            projected["situs_address"] = address
    values = record.get("assessment_values")
    if isinstance(values, Mapping):
        assessment = {
            "tax_year": _text(values.get("assessment_year")),
            "land_value": values.get("land"),
            "improvement_value": values.get("building"),
            "parcel_value": values.get("total"),
            "market_value": values.get("total"),
            "assessed_value": values.get("assessed"),
            "source_assessment_values": deepcopy(dict(values)),
        }
        if any(
            assessment.get(field) not in (None, "")
            for field in (
                "land_value",
                "improvement_value",
                "parcel_value",
                "assessed_value",
            )
        ):
            projected["assessment"] = assessment
        if assessment["tax_year"]:
            projected["tax_year"] = assessment["tax_year"]
    latest_sale = _latest_sale(record.get("latest_sale_or_deed"))
    if latest_sale:
        projected["last_sale"] = latest_sale
    projected["owners"] = []
    projected["geometry_format"] = "esri_json"
    projected["snapshot_complete"] = True
    return projected


def _project_wasco_taxlot(record: Mapping[str, Any]) -> dict[str, Any]:
    projected = deepcopy(dict(record))
    source_id = WASCO_TAXLOT_SOURCE_ID
    source_record_id = record.get("source_record_id") or record.get("object_id")
    account = record.get("account_number")
    map_taxlot = record.get("map_taxlot")
    _apply_common_assessor_fields(
        projected,
        source_id=source_id,
        native_parcel_id=source_record_id,
        aliases=(
            account,
            map_taxlot,
            record.get("normalized_map_taxlot"),
            normalize_taxlot_alias(map_taxlot),
        ),
    )
    mailing = _wasco_mailing_address(record.get("mailing_address"))
    if mailing:
        projected["mailing_address"] = mailing
    projected["owners"] = []
    projected["geometry_format"] = "esri_json"
    projected["snapshot_complete"] = True
    return projected


def _project_multnomah_tax_parcel(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    projected = deepcopy(dict(record))
    native_ids = _native_ids(record)
    property_id = _text(
        record.get("property_id")
        or record.get("native_parcel_id")
        or native_ids.get("PROPID")
    )
    map_taxlot = _text(record.get("map_taxlot") or native_ids.get("MAPTAXLOT"))
    alternate_account = _text(
        record.get("alternate_account_number")
        or native_ids.get("ALTACCTNUM")
    )
    _apply_common_assessor_fields(
        projected,
        source_id=MULTNOMAH_TAX_PARCEL_SOURCE_ID,
        native_parcel_id=property_id or map_taxlot,
        aliases=(
            map_taxlot,
            normalize_taxlot_alias(map_taxlot),
            alternate_account,
            record.get("source_record_id"),
        ),
    )

    owner_values = record.get("owners")
    projected["owners"] = [
        {"raw_name": owner, "confidence": "high"}
        for owner in _deduplicated_text(
            owner_values if isinstance(owner_values, list) else []
        )
    ]

    situs = record.get("situs")
    if isinstance(situs, Mapping):
        situs_address = _address(
            situs.get("address"),
            city=situs.get("city"),
            state=situs.get("state"),
            postal_code=situs.get("postal_code"),
        )
        if situs_address:
            projected["situs_address"] = situs_address

    mailing = record.get("mailing")
    if isinstance(mailing, Mapping):
        mailing_raw = " ".join(
            value
            for value in (
                _text(mailing.get("address_1")),
                _text(mailing.get("address_2")),
            )
            if value
        )
        mailing_address = _address(
            mailing_raw,
            city=mailing.get("city"),
            state=mailing.get("state"),
            postal_code=mailing.get("postal_code"),
        )
        if mailing_address:
            projected["mailing_address"] = mailing_address

    legal = record.get("legal")
    if isinstance(legal, Mapping):
        legal_description = " ".join(
            value
            for value in (
                _text(legal.get("description")),
                _text(legal.get("additional")),
            )
            if value
        )
        if legal_description:
            projected["legal_description"] = legal_description

    roll_values = record.get("roll_values")
    if isinstance(roll_values, Mapping):
        land_value = roll_values.get("land")
        improvement_value = roll_values.get("improvements")
        assessed_value = roll_values.get("measure_50")
        market_value = (
            land_value + improvement_value
            if isinstance(land_value, (int, float))
            and not isinstance(land_value, bool)
            and isinstance(improvement_value, (int, float))
            and not isinstance(improvement_value, bool)
            else None
        )
        assessment = {
            "tax_year": _text(roll_values.get("year")),
            "land_value": land_value,
            "improvement_value": improvement_value,
            "parcel_value": market_value,
            "market_value": market_value,
            "assessed_value": assessed_value,
            "source_roll_values": deepcopy(dict(roll_values)),
        }
        if any(
            assessment.get(field) not in (None, "")
            for field in (
                "land_value",
                "improvement_value",
                "parcel_value",
                "assessed_value",
            )
        ):
            projected["assessment"] = assessment
        if assessment["tax_year"]:
            projected["tax_year"] = assessment["tax_year"]

    deed_or_sale = record.get("latest_deed_or_sale")
    if isinstance(deed_or_sale, Mapping):
        instrument = _text(deed_or_sale.get("instrument_number"))
        sale_date = _date_prefix(deed_or_sale.get("sale_date_iso"))
        document_date = _date_prefix(deed_or_sale.get("deed_date_iso"))
        if instrument or sale_date or document_date:
            projected["last_sale"] = {
                **deepcopy(dict(deed_or_sale)),
                "sale_date": sale_date,
                "source_document_date": document_date,
                "source_document_ref": instrument,
                "consideration": deed_or_sale.get("sale_price"),
            }

    geometry = record.get("geometry")
    if isinstance(geometry, Mapping):
        projected["geometry_format"] = "esri_json"
        projected["geometry_crs"] = _text(geometry.get("output_crs")) or "EPSG:4326"
    projected["record_view"] = "multnomah_sail_current_tax_parcel"
    projected["snapshot_complete"] = True
    return projected


def _project_washington_intermap(record: Mapping[str, Any]) -> dict[str, Any]:
    projected = deepcopy(dict(record))
    native_ids = _native_ids(record)
    taxlot = _text(native_ids.get("TLNO") or native_ids.get("IDValue"))
    account = _text(native_ids.get("account"))
    _apply_common_assessor_fields(
        projected,
        source_id=WASHINGTON_INTERMAP_SOURCE_ID,
        native_parcel_id=taxlot,
        aliases=(account, normalize_taxlot_alias(taxlot)),
    )
    fields = _representation_fields(record)
    owner_name = _first_field(
        fields,
        "Owner",
        "Owner Name",
        "Property Owner",
    )
    projected["owners"] = (
        [{"raw_name": owner_name, "confidence": "high"}]
        if owner_name
        else []
    )
    situs = _first_field(
        fields,
        "Site Address",
        "Property Address",
        "Situs Address",
    )
    if situs:
        projected["situs_address"] = _address(situs)
    legal = _first_field(fields, "Legal", "Legal Description")
    if legal:
        projected["legal_description"] = legal

    market_value = _money_value(
        _first_field(
            fields,
            "Real Market Value (RMV) Total",
            "Real Market Value",
        )
    )
    assessed_value = _money_value(
        _first_field(
            fields,
            "Taxable Assessed Value",
            "Assessed Value",
        )
    )
    if market_value is not None or assessed_value is not None:
        projected["assessment"] = {
            "market_value": market_value,
            "assessed_value": assessed_value,
            "source_report": _text(record.get("report")),
        }
    projected["record_view"] = (
        f"intermap_{_text(record.get('report')) or 'property'}_report"
    )
    projected["snapshot_complete"] = False
    return projected


def _project_washington_tax_account(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    projected = deepcopy(dict(record))
    native_ids = _native_ids(record)
    account = _text(native_ids.get("PropertyQuickRefID"))
    alternate_account = _text(native_ids.get("alternate_account"))
    _apply_common_assessor_fields(
        projected,
        source_id=WASHINGTON_TAX_SOURCE_ID,
        native_parcel_id=account,
        aliases=(alternate_account,),
    )
    owner_name = _text(record.get("owner_name"))
    projected["owners"] = (
        [{"raw_name": owner_name, "confidence": "high"}]
        if owner_name
        else []
    )
    fields = _representation_fields(record)
    situs = _first_field(
        fields,
        "Site Address",
        "Property Address",
        "Situs Address",
    )
    if situs:
        projected["situs_address"] = _address(situs)
    market_value = _money_value(record.get("displayed_real_market_value"))
    statements = record.get("tax_statements")
    statement_years = (
        [
            int(item["tax_year"])
            for item in statements
            if isinstance(item, Mapping)
            and str(item.get("tax_year") or "").isdigit()
        ]
        if isinstance(statements, list)
        else []
    )
    tax_year = str(max(statement_years)) if statement_years else None
    if market_value is not None:
        projected["assessment"] = {
            "tax_year": tax_year,
            "market_value": market_value,
            "parcel_value": market_value,
            "source_display_field": "displayed_real_market_value",
        }
    if tax_year:
        projected["tax_year"] = tax_year
    projected["legal_description"] = _text(record.get("legal_description"))
    projected["record_view"] = "washington_county_tax_account"
    projected["snapshot_complete"] = True
    return projected


def _is_washington_assessor_record(
    source_id: str,
    record: Mapping[str, Any],
) -> bool:
    record_type = (_text(record.get("record_type")) or "").casefold()
    if source_id == WASHINGTON_INTERMAP_SOURCE_ID:
        return (_text(record.get("report")) or "").casefold() in {
            "assessment",
            "parcel",
        }
    if source_id == WASHINGTON_TAX_SOURCE_ID:
        return record_type == "washington_county_tax_account"
    return False


def project_assessor_record(
    record: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Translate one supported account or taxlot row into assessor fields."""

    selected = _source_id(record, source_id)
    if selected not in ASSESSOR_SOURCE_IDS:
        raise PropertyProjectionError(
            f"{selected} is not an assessor projection source"
        )
    if selected in {
        YAMHILL_ASCEND_SOURCE_ID,
        CLACKAMAS_ASCEND_SOURCE_ID,
        WASCO_ASCEND_SOURCE_ID,
    }:
        return _project_account_record(record, source_id=selected)
    if selected in {
        YAMHILL_TAXLOT_SOURCE_ID,
        YAMHILL_RETIRED_TAXLOT_SOURCE_ID,
    }:
        return _project_yamhill_taxlot(record, source_id=selected)
    if selected == CLACKAMAS_CMAP_SOURCE_ID:
        return _project_clackamas_cmap(record)
    if selected == WASCO_TAXLOT_SOURCE_ID:
        return _project_wasco_taxlot(record)
    if selected == MULTNOMAH_TAX_PARCEL_SOURCE_ID:
        if (
            (_text(record.get("record_kind")) or "").casefold()
            != "current_assessment_tax_parcel"
        ):
            raise PropertyProjectionError(
                "Multnomah SAIL assessor projection requires a current "
                "assessment tax-parcel record"
            )
        return _project_multnomah_tax_parcel(record)
    if selected == WASHINGTON_INTERMAP_SOURCE_ID:
        if not _is_washington_assessor_record(selected, record):
            raise PropertyProjectionError(
                "Washington County Intermap assessor projection requires a "
                "parcel or assessment report"
            )
        return _project_washington_intermap(record)
    if selected == WASHINGTON_TAX_SOURCE_ID:
        if not _is_washington_assessor_record(selected, record):
            raise PropertyProjectionError(
                "Washington County tax assessor projection requires a "
                "property-account record"
            )
        return _project_washington_tax_account(record)
    raise AssertionError(f"unhandled assessor source {selected}")


def project_yamhill_permit_record(
    record: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Translate one annual Yamhill permit row into property-event fields."""

    selected = _source_id(record, source_id)
    if selected != YAMHILL_PERMIT_SOURCE_ID:
        raise PropertyProjectionError(
            f"{selected} is not the Yamhill annual permit source"
        )
    projected = deepcopy(dict(record))
    native_event_id = _text(
        record.get("native_event_id") or record.get("native_permit_id")
    )
    source_record_id = _text(
        record.get("source_record_id") or record.get("object_id")
    )
    if not native_event_id or not source_record_id:
        raise PropertyProjectionError(
            "Yamhill permit record lacks permit and source-record identifiers"
        )
    permit = record.get("permit")
    permit_values = dict(permit) if isinstance(permit, Mapping) else {}
    issue_date = permit_values.get("issue_date")
    issue_observation = (
        deepcopy(dict(issue_date)) if isinstance(issue_date, Mapping) else None
    )
    if issue_observation is not None:
        issue_observation["source_semantics"] = "issue_date"
    taxlot = _text(record.get("map_taxlot"))
    projected.update(
        {
            "source_id": selected,
            "native_event_id": native_event_id,
            "source_record_id": source_record_id,
            "jurisdiction": _jurisdiction(selected),
            "event_type": "assessment_permit",
            "description": _text(permit_values.get("description")),
            "event_dates": {
                "approved": issue_observation,
                "issued": deepcopy(issue_observation),
            },
            "parcel_join_evidence": {
                "method": "published_account_and_map_taxlot",
                "published_location": {
                    "raw": taxlot,
                    "normalized_candidate": normalize_taxlot_alias(taxlot),
                },
                "published_account_number": _text(record.get("account_number")),
            },
            "people": [
                {
                    **owner,
                    "role": owner.get("role") or "published_assessment_owner",
                    "assertion_type": (
                        owner.get("assertion_type")
                        or "published_annual_permit_owner"
                    ),
                }
                for owner in _published_owners(record.get("owners"))
            ],
        }
    )
    address = _yamhill_address(record.get("situs"), mailing=False)
    if address:
        projected["address"] = address
    return projected


def classify_wasco_survey_record(
    record: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> PropertyProjection:
    """Classify a Wasco survey row for attributable observation storage."""

    selected = _source_id(record, source_id)
    if selected not in WASCO_SURVEY_SOURCE_IDS:
        raise PropertyProjectionError(f"{selected} is not a Wasco survey source")
    source_native_id = _text(
        record.get("source_record_id")
        or record.get("object_id")
        or record.get("native_identity")
        or record.get("canonical_ref")
    )
    return PropertyProjection(
        kind="observation_only",
        source_id=selected,
        record=deepcopy(dict(record)),
        reason="wasco_survey_reference_not_assessor_or_title_projection",
        source_native_id=source_native_id,
        observation_kind=WASCO_SURVEY_OBSERVATION_CLASSES[selected],
    )


def _washington_observation_identity(
    record: Mapping[str, Any],
    source_id: str,
) -> str | None:
    native_ids = _native_ids(record)
    record_type = _text(record.get("record_type"))
    layer_key = _text(record.get("layer_key"))
    if source_id == WASHINGTON_SURVEY_API_SOURCE_ID:
        identity = next(
            (
                _text(native_ids.get(field))
                for field in (
                    "Surveynumber",
                    "Platname",
                    "DocNumber",
                    "TLID",
                    "ACCOUNT",
                    "CORNERID",
                    "CROAD_ID",
                    "Benchmark_ID",
                    "ID",
                )
                if _text(native_ids.get(field))
            ),
            None,
        ) or _text(record.get("uid"))
        prefix = _text(record.get("kind")) or record_type
        return ":".join(value for value in (prefix, identity) if value) or None
    if source_id == WASHINGTON_SURVEY_MAP_SOURCE_ID:
        identity = _text(
            native_ids.get("OBJECTID")
            or native_ids.get("SurvNum")
            or native_ids.get("Platname")
            or native_ids.get("TLID")
        )
        return ":".join(value for value in (layer_key, identity) if value) or None
    if source_id == WASHINGTON_TAXLOT_SOURCE_ID:
        return _text(native_ids.get("TLNO") or native_ids.get("OBJECTID"))
    if source_id == WASHINGTON_SITUS_SOURCE_ID:
        return _text(
            native_ids.get("SITUS_ID")
            or native_ids.get("OBJECTID")
            or native_ids.get("ACCOUNT_ID")
        )
    if source_id == WASHINGTON_INTERMAP_SOURCE_ID:
        taxlot = _text(native_ids.get("TLNO") or native_ids.get("IDValue"))
        report = _text(record.get("report"))
        return ":".join(value for value in (report, taxlot) if value) or None
    if source_id == WASHINGTON_TAX_SOURCE_ID:
        account = _text(native_ids.get("PropertyQuickRefID"))
        tax_year = _text(native_ids.get("tax_year"))
        filename = _text(native_ids.get("generated_filename"))
        return (
            ":".join(
                value for value in (account, tax_year, filename) if value
            )
            or None
        )
    return None


def _washington_observation_kind(
    record: Mapping[str, Any],
    source_id: str,
) -> str:
    record_type = (_text(record.get("record_type")) or "").casefold()
    layer_key = (_text(record.get("layer_key")) or "").casefold()
    if source_id == WASHINGTON_SURVEY_API_SOURCE_ID:
        if record_type == "survey_explorer_document":
            return "survey_explorer_document"
        return record_type or WASHINGTON_OBSERVATION_CLASSES[source_id]
    if source_id == WASHINGTON_SURVEY_MAP_SOURCE_ID:
        return (
            f"survey_explorer_{layer_key}_geometry_index"
            if layer_key
            else WASHINGTON_OBSERVATION_CLASSES[source_id]
        )
    if source_id == WASHINGTON_INTERMAP_SOURCE_ID:
        return (
            record_type
            or WASHINGTON_OBSERVATION_CLASSES[source_id]
        )
    if source_id == WASHINGTON_TAX_SOURCE_ID:
        return (
            record_type
            or WASHINGTON_OBSERVATION_CLASSES[source_id]
        )
    return record_type or WASHINGTON_OBSERVATION_CLASSES[source_id]


def classify_washington_record(
    record: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> PropertyProjection:
    """Classify one Washington County index or document representation."""

    selected = _source_id(record, source_id)
    if selected not in WASHINGTON_PROPERTY_SOURCE_IDS:
        raise PropertyProjectionError(
            f"{selected} is not a Washington County property source"
        )
    return PropertyProjection(
        kind="observation_only",
        source_id=selected,
        record=deepcopy(dict(record)),
        reason="washington_county_index_or_document_observation",
        source_native_id=_washington_observation_identity(record, selected),
        observation_kind=_washington_observation_kind(record, selected),
    )


def _event_date_observation(
    value: Any,
    *,
    source_semantics: str,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    utc_date = _text(value.get("utc_date") or value.get("iso_date"))
    if not utc_date:
        return None
    return {
        **deepcopy(dict(value)),
        "utc_date": utc_date,
        "source_semantics": source_semantics,
    }


def _washington_case_permit_event_dates(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    record_kind = (_text(record.get("record_kind")) or "").casefold()
    dates_value = record.get("dates")
    dates = dict(dates_value) if isinstance(dates_value, Mapping) else {}

    def observed(key: str) -> dict[str, Any] | None:
        return _event_date_observation(
            dates.get(key),
            source_semantics=key,
        )

    native_dates = {
        key: value
        for key in (
            "submitted",
            "accepted",
            "decision",
            "entered",
            "hearing",
            "opened",
            "completed",
            "issued",
            "final",
            "expires",
            "inspection",
            "task",
        )
        if (value := observed(key)) is not None
    }
    if record_kind in {
        "planning_casefile",
        "applications_under_review",
        "recent_decisions",
    }:
        submitted = native_dates.get("submitted") or native_dates.get("accepted")
        approved = native_dates.get("decision")
        last_update = native_dates.get("entered") or native_dates.get("accepted")
    elif record_kind == "project_report":
        submitted = native_dates.get("opened")
        approved = native_dates.get("completed")
        last_update = native_dates.get("completed")
    elif record_kind == "activity_report":
        submitted = native_dates.get("submitted") or native_dates.get("entered")
        approved = native_dates.get("final") or native_dates.get("issued")
        last_update = native_dates.get("accepted") or native_dates.get("entered")
    elif record_kind == "inspection_report":
        submitted = None
        approved = None
        last_update = native_dates.get("inspection")
    elif record_kind == "review_report":
        submitted = None
        approved = None
        last_update = native_dates.get("task")
    else:
        return {}

    return {
        **native_dates,
        **(
            {"submitted": deepcopy(submitted)}
            if submitted is not None
            else {}
        ),
        **(
            {"approved": deepcopy(approved)}
            if approved is not None
            else {}
        ),
        **(
            {"last_update": deepcopy(last_update)}
            if last_update is not None
            else {}
        ),
    }


def _washington_case_permit_taxlots(
    record: Mapping[str, Any],
) -> list[str]:
    joins_value = record.get("joins")
    joins = dict(joins_value) if isinstance(joins_value, Mapping) else {}
    candidates: list[Any] = []
    candidates.extend(
        joins.get("taxlots")
        if isinstance(joins.get("taxlots"), list)
        else []
    )
    candidates.extend(
        joins.get("casefile_taxlots")
        if isinstance(joins.get("casefile_taxlots"), list)
        else []
    )
    candidates.extend(
        [
            joins.get("taxlot"),
            record.get("taxlot"),
        ]
    )
    return _deduplicated_text(candidates)


def _washington_case_permit_people(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    applicant = _text(record.get("applicant"))
    if applicant:
        people.append(
            {
                "raw_name": applicant,
                "role": "applicant",
                "assertion_type": "published_planning_or_permit_record",
            }
        )
    staff_value = record.get("staff")
    staff_name = (
        _text(staff_value.get("name"))
        if isinstance(staff_value, Mapping)
        else _text(staff_value)
    )
    if staff_name:
        people.append(
            {
                "raw_name": staff_name,
                "role": "assigned_staff",
                "assertion_type": "published_planning_or_permit_record",
            }
        )
    native_value = record.get("source_native")
    native = dict(native_value) if isinstance(native_value, Mapping) else {}
    for field, role in (
        ("Inspector", "inspector"),
        ("PlansExaminer", "plans_examiner"),
    ):
        raw_name = _text(native.get(field))
        if raw_name:
            people.append(
                {
                    "raw_name": raw_name,
                    "role": role,
                    "assertion_type": "published_planning_or_permit_record",
                }
            )
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for person in people:
        key = (person["raw_name"].casefold(), person["role"])
        if key in seen:
            continue
        seen.add(key)
        result.append(person)
    return result


def _washington_case_permit_representations(
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source_urls = record.get("source_urls")
    if not isinstance(source_urls, Mapping):
        return []
    return [
        {
            "kind": str(kind),
            "url": url,
            "relationship": "source_representation",
            "source_state": "published",
        }
        for kind, raw_url in source_urls.items()
        if (url := _text(raw_url))
    ]


def project_washington_case_permit_event(
    record: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Translate one dated Washington planning/permit row into an event."""

    selected = _source_id(record, source_id)
    if selected not in WASHINGTON_CASE_PERMIT_EVENT_SOURCE_IDS:
        raise PropertyProjectionError(
            f"{selected} is not a Washington County event-capable source"
        )
    event_dates = _washington_case_permit_event_dates(record)
    if not any(
        isinstance(value, Mapping) and _text(value.get("utc_date"))
        for value in event_dates.values()
    ):
        raise PropertyProjectionError(
            "Washington County event projection requires a published date"
        )

    record_kind = (_text(record.get("record_kind")) or "").casefold()
    event_types = {
        "planning_casefile": "planning_casefile",
        "applications_under_review": "planning_application_under_review",
        "recent_decisions": "land_use_decision",
        "project_report": "permit_project",
        "activity_report": "permit_activity",
        "inspection_report": "permit_inspection",
        "review_report": "permit_review",
    }
    if record_kind not in event_types:
        raise PropertyProjectionError(
            f"{record_kind or 'unknown record'} is not an event-grain record"
        )
    native_event_id = _text(record.get("native_record_id"))
    if not native_event_id:
        raise PropertyProjectionError(
            "Washington County event record lacks a native identifier"
        )
    native_ids_value = record.get("native_ids")
    native_ids = (
        dict(native_ids_value) if isinstance(native_ids_value, Mapping) else {}
    )
    source_record_id = _text(
        native_ids.get("submittal_number")
        or native_ids.get("accela_cap_id")
        or record.get("canonical_ref")
        or native_event_id
    )
    if not source_record_id:
        raise PropertyProjectionError(
            "Washington County event record lacks a source-row identifier"
        )

    projected = deepcopy(dict(record))
    taxlots = _washington_case_permit_taxlots(record)
    first_taxlot = taxlots[0] if taxlots else None
    native_value = record.get("source_native")
    native = dict(native_value) if isinstance(native_value, Mapping) else {}
    raw_address = _text(
        record.get("situs_address")
        or native.get("STREET_NAME")
        or native.get("Address")
    )
    projected.update(
        {
            "source_id": selected,
            "native_event_id": native_event_id,
            "source_record_id": source_record_id,
            "jurisdiction": _jurisdiction(selected),
            "event_type": event_types[record_kind],
            "description": _text(
                record.get("description")
                or record.get("application_name")
                or native.get("DESCRIPTION")
                or native.get("Description")
                or native.get("Insp_Comments")
                or native.get("Comment")
            ),
            "event_dates": event_dates,
            "people": _washington_case_permit_people(record),
            "detail_representations": (
                _washington_case_permit_representations(record)
            ),
            "parcel_join_evidence": {
                "method": "published_taxlot",
                "published_location": {
                    "raw": first_taxlot,
                    "normalized_candidate": normalize_taxlot_alias(first_taxlot),
                },
                "published_taxlots": taxlots,
            },
        }
    )
    if raw_address:
        projected["address"] = _address(
            raw_address,
            city=native.get("CITY_NAME"),
            state="OR",
        )
    return projected


def _washington_case_permit_observation_identity(
    record: Mapping[str, Any],
) -> str | None:
    record_kind = _text(record.get("record_kind"))
    native_id = _text(record.get("native_record_id"))
    casefile = _text(record.get("casefile_number"))
    document_number = _text(record.get("document_number"))
    artifact_sha256 = _text(
        record.get("sha256")
        or (
            record.get("binary_representation", {}).get("content_sha256")
            if isinstance(record.get("binary_representation"), Mapping)
            else None
        )
    )
    return (
        ":".join(
            value
            for value in (
                record_kind,
                native_id or casefile,
                document_number,
                artifact_sha256,
            )
            if value
        )
        or _text(record.get("canonical_ref"))
    )


def classify_washington_case_permit_record(
    record: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> PropertyProjection:
    """Classify a planning index, vocabulary, route, or representation."""

    selected = _source_id(record, source_id)
    if selected not in WASHINGTON_CASE_PERMIT_SOURCE_IDS:
        raise PropertyProjectionError(
            f"{selected} is not a Washington County case/permit source"
        )
    return PropertyProjection(
        kind="observation_only",
        source_id=selected,
        record=deepcopy(dict(record)),
        reason="washington_county_non_event_grain_or_supporting_representation",
        source_native_id=_washington_case_permit_observation_identity(record),
        observation_kind=(
            _text(record.get("record_kind"))
            or WASHINGTON_CASE_PERMIT_OBSERVATION_CLASSES[selected]
        ),
    )


def _multnomah_observation_identity(
    record: Mapping[str, Any],
) -> str | None:
    source_record_id = _text(record.get("source_record_id"))
    if source_record_id:
        return source_record_id
    native_ids = _native_ids(record)
    object_id = _text(
        native_ids.get("OBJECTID")
        or native_ids.get("OBJECTID_1")
        or record.get("object_id")
    )
    if object_id:
        return object_id
    record_kind = _text(record.get("record_kind"))
    survey_document_id = _text(
        record.get("survey_document_id")
        or native_ids.get("SURVEYID")
    )
    representation_index = _text(record.get("representation_index"))
    artifact_sha256 = _text(record.get("sha256"))
    return (
        ":".join(
            value
            for value in (
                record_kind,
                survey_document_id,
                representation_index,
                artifact_sha256,
            )
            if value
        )
        or None
    )


def classify_multnomah_sail_record(
    record: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> PropertyProjection:
    """Classify one SAIL index, geometry, viewer, or PDF representation."""

    selected = _source_id(record, source_id)
    if selected not in MULTNOMAH_OBSERVATION_SOURCE_IDS:
        raise PropertyProjectionError(
            f"{selected} is not a Multnomah SAIL observation source"
        )
    return PropertyProjection(
        kind="observation_only",
        source_id=selected,
        record=deepcopy(dict(record)),
        reason="multnomah_sail_non_assessor_representation",
        source_native_id=_multnomah_observation_identity(record),
        observation_kind=(
            _text(record.get("record_kind"))
            or MULTNOMAH_OBSERVATION_CLASSES[selected]
        ),
    )


def project_record(
    record: Mapping[str, Any],
    *,
    source_id: str | None = None,
) -> PropertyProjection:
    """Return the explicit projection decision for one adapter record."""

    selected = _source_id(record, source_id)
    if selected in WASHINGTON_CASE_PERMIT_SOURCE_IDS:
        record_kind = (_text(record.get("record_kind")) or "").casefold()
        event_dates = _washington_case_permit_event_dates(record)
        dated_event = record_kind in {
            "planning_casefile",
            "applications_under_review",
            "recent_decisions",
            "project_report",
            "activity_report",
            "inspection_report",
            "review_report",
        } and any(
            isinstance(value, Mapping) and _text(value.get("utc_date"))
            for value in event_dates.values()
        )
        if (
            selected in WASHINGTON_CASE_PERMIT_EVENT_SOURCE_IDS
            and dated_event
        ):
            return PropertyProjection(
                kind="property_event",
                source_id=selected,
                record=project_washington_case_permit_event(
                    record,
                    source_id=selected,
                ),
            )
        return classify_washington_case_permit_record(
            record,
            source_id=selected,
        )
    if selected in MULTNOMAH_PROPERTY_SOURCE_IDS:
        if selected == MULTNOMAH_TAX_PARCEL_SOURCE_ID:
            return PropertyProjection(
                kind="assessor",
                source_id=selected,
                record=project_assessor_record(record, source_id=selected),
            )
        return classify_multnomah_sail_record(record, source_id=selected)
    if selected in WASHINGTON_PROPERTY_SOURCE_IDS:
        if _is_washington_assessor_record(selected, record):
            return PropertyProjection(
                kind="assessor",
                source_id=selected,
                record=project_assessor_record(record, source_id=selected),
            )
        return classify_washington_record(record, source_id=selected)
    if selected in ASSESSOR_SOURCE_IDS:
        return PropertyProjection(
            kind="assessor",
            source_id=selected,
            record=project_assessor_record(record, source_id=selected),
        )
    if selected == YAMHILL_PERMIT_SOURCE_ID:
        return PropertyProjection(
            kind="property_event",
            source_id=selected,
            record=project_yamhill_permit_record(record, source_id=selected),
        )
    return classify_wasco_survey_record(record, source_id=selected)
