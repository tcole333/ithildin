"""Project Washington statewide parcel records into the shared property model.

The Washington adapter exposes three representations of one normalized
state/county parcel lineage plus separate freshness, county land-use, and
representation-parity observations.  Parcel rows can populate the shared
assessment and geometry tables.  The other record kinds remain attributable
source observations.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, Mapping


LINEAGE_SOURCE_ID = "us-wa-state-parcels-normalized"
ECOLOGY_SOURCE_ID = "us-wa-current-parcels-ecology"
DNR_SOURCE_ID = "us-wa-current-parcels-dnr"
WISAARD_SOURCE_ID = "us-wa-current-parcels-wisaard"
FRESHNESS_SOURCE_ID = "us-wa-current-parcels-county-freshness"
LAND_USE_SOURCE_ID = "us-wa-current-parcels-county-land-use"

PARCEL_SOURCE_IDS = frozenset(
    {
        ECOLOGY_SOURCE_ID,
        DNR_SOURCE_ID,
        WISAARD_SOURCE_ID,
    }
)
OBSERVATION_SOURCE_IDS = frozenset(
    {
        LINEAGE_SOURCE_ID,
        FRESHNESS_SOURCE_ID,
        LAND_USE_SOURCE_ID,
    }
)
SUPPORTED_SOURCE_IDS = frozenset(
    {
        *PARCEL_SOURCE_IDS,
        *OBSERVATION_SOURCE_IDS,
    }
)

SOURCE_URLS: Mapping[str, str] = {
    LINEAGE_SOURCE_ID: (
        "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/"
        "Current_Parcels/FeatureServer"
    ),
    ECOLOGY_SOURCE_ID: (
        "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/"
        "Current_Parcels/FeatureServer/0"
    ),
    DNR_SOURCE_ID: (
        "https://gis.dnr.wa.gov/site2/rest/services/Public_Forest_Practices/"
        "WADNR_PUBLIC_OCIO_Parcels/MapServer/0"
    ),
    WISAARD_SOURCE_ID: (
        "https://wisaard.dahp.wa.gov/server/rest/services/County_Parcels/"
        "MapServer/0"
    ),
    FRESHNESS_SOURCE_ID: (
        "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/"
        "Current_Parcels/FeatureServer/1"
    ),
    LAND_USE_SOURCE_ID: (
        "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/"
        "Current_Parcels/FeatureServer/2"
    ),
}


@dataclass(frozen=True)
class ProjectionDecision:
    """One explicit decision for shared property ingestion."""

    kind: Literal["assessor", "observation"]
    record: dict[str, Any]
    source_native_id: str | None = None
    observation_kind: str | None = None
    reason: str | None = None


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _unique_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _observation_identity(record: Mapping[str, Any]) -> str | None:
    kind = _text(record.get("record_kind")) or "source_row"
    if kind == "county_parcel_freshness":
        parts = [
            kind,
            record.get("county_geoid"),
            record.get("object_id"),
        ]
    elif kind == "county_land_use_code":
        parts = [
            kind,
            record.get("county_geoid"),
            record.get("code"),
            record.get("object_id"),
        ]
    elif kind == "parcel_representation_parity":
        parts = [kind, record.get("sentinel_parcel_id")]
    elif kind == "source_metadata":
        parts = [kind, record.get("representation")]
    elif kind == "source_count":
        parts = [
            kind,
            record.get("representation"),
            record.get("where"),
        ]
    elif kind == "source_probe":
        operations = record.get("operations")
        operation_names = (
            ",".join(sorted(str(key) for key in operations))
            if isinstance(operations, Mapping)
            else None
        )
        parts = [
            kind,
            record.get("source_id"),
            record.get("representation"),
            operation_names,
        ]
    elif kind == "companion_table_probe":
        parts = [kind, record.get("lineage_id")]
    else:
        parts = [
            kind,
            record.get("source_id"),
            record.get("source_feature_id"),
            record.get("object_id"),
            record.get("global_id"),
        ]
    values = _unique_text(parts)
    return ":".join(values) if values else None


def project_parcel_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    """Add the generic assessor projection while retaining native lineage."""

    if source_id not in PARCEL_SOURCE_IDS:
        raise ValueError(f"{source_id} is not a Washington parcel representation")
    if _text(record.get("record_kind")) != "property_parcel":
        raise ValueError("Washington assessor projection requires property_parcel")

    projected = deepcopy(dict(record))
    original_id = _text(record.get("original_parcel_id"))
    normalized_id = _text(record.get("normalized_parcel_id"))
    feature_id = _text(record.get("source_feature_id"))
    native_id = original_id or normalized_id or feature_id
    if native_id is None:
        raise ValueError("Washington parcel record lacks a stable parcel identity")
    projected["native_parcel_id"] = native_id
    projected["alternate_parcel_ids"] = [
        value
        for value in _unique_text(
            [
                normalized_id,
                original_id,
                feature_id,
                record.get("global_id"),
            ]
        )
        if value != native_id
    ]

    situs = record.get("situs")
    if isinstance(situs, Mapping):
        projected["situs_address"] = {
            "raw": situs.get("address"),
            "unit": situs.get("sub_address"),
            "city": situs.get("city"),
            "state": "WA",
            "postal_code": situs.get("zip"),
            "country": "US",
        }

    assessment = record.get("assessment")
    if isinstance(assessment, Mapping):
        total_value = assessment.get("total_value")
        projected["assessment"] = {
            "land_value": assessment.get("land_value"),
            "improvement_value": assessment.get("building_value"),
            "parcel_value": total_value,
            "assessed_value": total_value,
            "source_semantics": "normalized_statewide_assessed_components",
            "land_use": deepcopy(record.get("land_use")),
        }

    source_date = _text(
        record.get("source_file_date")
        or record.get("current_county_file_date")
    )
    if source_date:
        projected["source_last_updated"] = source_date
    projected["snapshot_complete"] = False
    projected["record_view"] = "washington_state_normalized_parcel_representation"
    projected["geometry_format"] = "esri_json"
    projected["source_url"] = SOURCE_URLS[source_id]
    projected["projection_metadata"] = {
        "lineage_id": LINEAGE_SOURCE_ID,
        "representation_source_id": source_id,
        "same_lineage_representation": True,
        "independent_corroboration": False,
        "county_detail_route_preserved": bool(record.get("data_link")),
        "owner_field_state": deepcopy(record.get("owner_visibility")),
    }
    return projected


def project_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> ProjectionDecision:
    """Classify and project one adapter record for shared ingestion."""

    if source_id not in SUPPORTED_SOURCE_IDS:
        raise ValueError(f"unsupported Washington parcel source: {source_id}")
    kind = _text(record.get("record_kind")) or "source_row"
    if source_id in PARCEL_SOURCE_IDS and kind == "property_parcel":
        return ProjectionDecision(
            kind="assessor",
            record=project_parcel_record(record, source_id=source_id),
        )
    return ProjectionDecision(
        kind="observation",
        record=deepcopy(dict(record)),
        source_native_id=_observation_identity(record),
        observation_kind=kind,
        reason=(
            "Freshness, land-use vocabulary, lineage parity, metadata, counts, "
            "and probe results remain attributable observations."
        ),
    )
