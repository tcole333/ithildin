"""Focused shared-property projections for the District of Columbia family.

The DCGIS Property and Land service exposes four separately attributable
components joined by Square/Suffix/Lot (SSL).  This module keeps those source
identities intact while deciding which records populate the shared assessor,
tax, geometry, and sale tables and which remain source observations.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, Mapping


LINEAGE_SOURCE_ID = "us-dc-itspe-property-lineage"
ITSPE_SOURCE_ID = "us-dc-itspe-public-extract"
OWNER_POLYGON_SOURCE_ID = "us-dc-common-ownership-polygons"
SALES_SOURCE_ID = "us-dc-cama-property-sales"
SURVEY_SOURCE_ID = "us-dc-surveyor-document-system"
RECORDER_SOURCE_ID = "us-dc-recorder-of-deeds-public-records"

ASSESSOR_SOURCE_IDS = frozenset({ITSPE_SOURCE_ID, OWNER_POLYGON_SOURCE_ID})
SUPPORTED_SOURCE_IDS = frozenset(
    {
        ITSPE_SOURCE_ID,
        OWNER_POLYGON_SOURCE_ID,
        SALES_SOURCE_ID,
        SURVEY_SOURCE_ID,
    }
)

SOURCE_URLS: Mapping[str, str] = {
    LINEAGE_SOURCE_ID: (
        "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
        "Property_and_Land/MapServer"
    ),
    ITSPE_SOURCE_ID: (
        "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
        "Property_and_Land/MapServer/53"
    ),
    OWNER_POLYGON_SOURCE_ID: (
        "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
        "Property_and_Land/MapServer/40"
    ),
    SALES_SOURCE_ID: (
        "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
        "Property_and_Land/MapServer/57"
    ),
    SURVEY_SOURCE_ID: (
        "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
        "Property_and_Land/MapServer/69"
    ),
    RECORDER_SOURCE_ID: "https://washington.dc.publicsearch.us/",
}


@dataclass(frozen=True)
class ProjectionDecision:
    """One explicit shared-store decision for a DC source record."""

    kind: Literal["assessor", "sale", "observation"]
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


def _dc_jurisdiction(record: Mapping[str, Any]) -> dict[str, Any]:
    jurisdiction = record.get("jurisdiction")
    projected = (
        deepcopy(dict(jurisdiction))
        if isinstance(jurisdiction, Mapping)
        else {}
    )
    projected.update(
        {
            "state_code": "DC",
            "state_fips": "11",
            "jurisdiction_geoid": "11",
            "locality": "District of Columbia",
        }
    )
    return projected


def _alternate_ssl_ids(record: Mapping[str, Any]) -> list[str]:
    ssl = record.get("ssl")
    ssl_values: list[Any] = []
    if isinstance(ssl, Mapping):
        ssl_values.extend(
            [
                ssl.get("raw"),
                ssl.get("normalized"),
                "".join(
                    value
                    for value in (
                        _text(ssl.get("square")),
                        _text(ssl.get("suffix")),
                        _text(ssl.get("lot")),
                    )
                    if value
                ),
            ]
        )
    ssl_values.extend(
        [
            record.get("native_id"),
            record.get("global_id"),
            record.get("object_id"),
        ]
    )
    native_parcel_id = _text(record.get("native_parcel_id"))
    return [
        value
        for value in _unique_text(ssl_values)
        if value != native_parcel_id
    ]


def _current_tax_year(record: Mapping[str, Any]) -> str | None:
    tax = record.get("tax")
    if not isinstance(tax, Mapping):
        return None
    periods = tax.get("periods")
    if not isinstance(periods, list):
        return None
    current_years = _unique_text(
        [
            period.get("year_label")
            for period in periods
            if isinstance(period, Mapping)
            and str(period.get("source_prefix") or "").startswith("CY")
        ]
    )
    return current_years[0] if len(current_years) == 1 else None


def project_assessor_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    """Project an ITSPE account or common-ownership polygon."""

    if source_id not in ASSESSOR_SOURCE_IDS:
        raise ValueError(f"{source_id} is not a DC assessor/geometry source")
    expected_type = (
        "assessment_tax_account"
        if source_id == ITSPE_SOURCE_ID
        else "common_ownership_polygon"
    )
    if _text(record.get("record_type")) != expected_type:
        raise ValueError(
            f"{source_id} shared projection requires {expected_type}"
        )
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        raise ValueError("DC assessor/geometry record lacks an SSL")

    projected = deepcopy(dict(record))
    projected["jurisdiction"] = _dc_jurisdiction(record)
    projected["alternate_parcel_ids"] = _alternate_ssl_ids(record)
    projected["source_url"] = SOURCE_URLS[source_id]
    projected["source_last_updated"] = _text(
        record.get("source_extract_date")
        or record.get("source_last_modified")
    )
    projected["tax_year"] = _current_tax_year(record)

    assessment = record.get("assessment")
    classification = record.get("classification")
    if isinstance(assessment, Mapping):
        normalized_assessment = deepcopy(dict(assessment))
        normalized_assessment.update(
            {
                "land_value": assessment.get("current_land"),
                "improvement_value": assessment.get("current_improvement"),
                "parcel_value": assessment.get("current_total"),
                "assessed_value": assessment.get("current_total"),
                "assessment_class": (
                    classification.get("tax_class")
                    if isinstance(classification, Mapping)
                    else None
                ),
                "source_semantics": "published_itspe_current_assessment",
            }
        )
        projected["assessment"] = normalized_assessment

    last_sale = record.get("last_sale")
    if isinstance(last_sale, Mapping):
        normalized_sale = deepcopy(dict(last_sale))
        normalized_sale.update(
            {
                "source_document_ref": last_sale.get("instrument_number"),
                "source_document_date": last_sale.get("deed_date"),
                "qualification_code": last_sale.get("acceptance_code"),
            }
        )
        projected["last_sale"] = normalized_sale

    for field_name in ("situs_address", "mailing_address"):
        address = projected.get(field_name)
        if isinstance(address, Mapping):
            normalized_address = deepcopy(dict(address))
            normalized_address.setdefault("state", "DC")
            normalized_address.setdefault("country", "US")
            projected[field_name] = normalized_address

    is_account = source_id == ITSPE_SOURCE_ID
    projected["snapshot_complete"] = is_account
    projected["record_view"] = (
        "dc_itspe_assessment_tax_account"
        if is_account
        else "dc_common_ownership_polygon_same_lineage_view"
    )
    if not is_account:
        projected["geometry_disclaimer"] = (
            "DCGIS common-ownership mapping geometry; account and polygon "
            "counts have different source-native grain."
        )
    projected["projection_metadata"] = {
        "lineage_id": LINEAGE_SOURCE_ID,
        "component_source_id": source_id,
        "lineage_relationship": (
            "primary_assessment_tax_account_extract"
            if is_account
            else "same_itspe_assessment_tax_lineage_with_land_geometry"
        ),
        "independent_corroboration": False,
        "account_polygon_cardinality": "not_assumed_one_to_one",
        "recorder_complement_source_id": RECORDER_SOURCE_ID,
    }
    return projected


def project_sale_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Retain one CAMA sale row while adding shared join metadata."""

    if _text(record.get("record_type")) != "property_sale_observation":
        raise ValueError("DC CAMA sale projection requires a sale observation")
    if not _text(record.get("native_id")):
        raise ValueError("DC CAMA sale record lacks a stable row identity")
    if not _text(record.get("native_parcel_id")):
        raise ValueError("DC CAMA sale record lacks an SSL")
    projected = deepcopy(dict(record))
    projected["jurisdiction"] = _dc_jurisdiction(record)
    projected["lineage_id"] = LINEAGE_SOURCE_ID
    projected["source_url"] = SOURCE_URLS[SALES_SOURCE_ID]
    projected["source_last_updated"] = _text(
        record.get("source_last_modified")
    )
    projected["projection_metadata"] = {
        "lineage_id": LINEAGE_SOURCE_ID,
        "component_source_id": SALES_SOURCE_ID,
        "lineage_relationship": "cama_sale_observation_joined_by_ssl",
        "recorder_complement_source_id": RECORDER_SOURCE_ID,
        "recorder_equivalence": False,
    }
    return projected


def _observation_identity(record: Mapping[str, Any]) -> str | None:
    record_type = _text(record.get("record_type")) or "source_row"
    if record_type == "surveyor_document":
        parts = [
            record_type,
            record.get("native_id"),
            record.get("native_parcel_id"),
        ]
    elif record_type in {"source_metadata", "source_count"}:
        parts = [
            record_type,
            record.get("component"),
            record.get("where"),
        ]
    else:
        parts = [
            record_type,
            record.get("component"),
            record.get("native_id"),
            record.get("object_id"),
        ]
    values = _unique_text(parts)
    return ":".join(values) if values else None


def project_observation(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> ProjectionDecision:
    projected = deepcopy(dict(record))
    projected["jurisdiction"] = _dc_jurisdiction(record)
    projected.setdefault("lineage_id", LINEAGE_SOURCE_ID)
    projected.setdefault("source_url", SOURCE_URLS[source_id])
    if source_id == SURVEY_SOURCE_ID:
        projected["projection_metadata"] = {
            "lineage_id": LINEAGE_SOURCE_ID,
            "component_source_id": SURVEY_SOURCE_ID,
            "lineage_relationship": "surveyor_document_joined_by_ssl",
            "recorder_complement_source_id": RECORDER_SOURCE_ID,
            "recorder_equivalence": False,
        }
    record_type = _text(record.get("record_type")) or "source_row"
    return ProjectionDecision(
        kind="observation",
        record=projected,
        source_native_id=_observation_identity(projected),
        observation_kind=record_type,
        reason=(
            "Surveyor documents, source metadata, counts, and probe rows "
            "remain separately attributable observations."
        ),
    )


def project_record(
    record: Mapping[str, Any],
    *,
    source_id: str,
) -> ProjectionDecision:
    """Classify and project one normalized DC adapter record."""

    if source_id not in SUPPORTED_SOURCE_IDS:
        raise ValueError(f"unsupported DC property source: {source_id}")
    record_type = _text(record.get("record_type"))
    if source_id in ASSESSOR_SOURCE_IDS and record_type in {
        "assessment_tax_account",
        "common_ownership_polygon",
    }:
        return ProjectionDecision(
            kind="assessor",
            record=project_assessor_record(record, source_id=source_id),
        )
    if (
        source_id == SALES_SOURCE_ID
        and record_type == "property_sale_observation"
    ):
        projected = project_sale_record(record)
        return ProjectionDecision(
            kind="sale",
            record=projected,
            source_native_id=_text(projected.get("native_id")),
            observation_kind=record_type,
        )
    return project_observation(record, source_id=source_id)
