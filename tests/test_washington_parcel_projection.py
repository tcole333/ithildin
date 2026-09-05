from __future__ import annotations

from copy import deepcopy

from tools import (
    query_washington_parcels as washington,
    washington_parcel_projection as projection,
)
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_property


def _parcel_record(*, source_id: str = projection.ECOLOGY_SOURCE_ID):
    record = {
        "record_kind": "property_parcel",
        "source_id": source_id,
        "representation": "ecology",
        "representation_role": "default",
        "lineage_id": projection.LINEAGE_SOURCE_ID,
        "source_feature_id": "OBJECTID:12",
        "object_id": 12,
        "global_id": "example-global-id",
        "native_parcel_id": "2038010000001",
        "normalized_parcel_id": "001-2038010000001",
        "original_parcel_id": "2038010000001",
        "jurisdiction": {
            "state_code": "WA",
            "state_fips": "53",
            "county_name": "Adams",
            "county_fips": "001",
            "county_geoid": "53001",
            "source_native_county": "1",
        },
        "situs": {
            "address": "100 MAIN ST",
            "sub_address": "UNIT 2",
            "city": "RITZVILLE",
            "zip": "99169",
        },
        "assessment": {
            "land_value": 25_000,
            "building_value": 75_000,
            "total_value": 100_000,
        },
        "land_use": {
            "dor_code": 91,
            "dor_description": "91 - Residential",
            "county_original_code": "R",
            "county_original_description": "Residential",
            "county_code_join": {
                "county_native_code": "1",
                "code": "R",
                "source_id": projection.LAND_USE_SOURCE_ID,
            },
        },
        "source_file_date": "2026-01-09T00:00:00Z",
        "current_county_file_date": "2026-01-09T00:00:00Z",
        "county_freshness_source_id": projection.FRESHNESS_SOURCE_ID,
        "owners": [
            {
                "raw_name": "EXAMPLE OWNER LLC",
                "source_field": "OWNER_NAME",
            }
        ],
        "owner_visibility": {
            "state": "published_in_live_schema",
            "published_owner_fields": ["OWNER_NAME"],
            "county_detail_field": "DATA_LINK",
        },
        "owner_related_attributes": {"OWNER_NAME": "EXAMPLE OWNER LLC"},
        "county_assessor_route": {
            "kind": "county_assessor_detail",
            "url": "https://example.test/county/parcel",
            "discovered_from": "DATA_LINK",
        },
        "data_link": "https://example.test/county/parcel",
        "source_lineage": {
            "lineage_id": projection.LINEAGE_SOURCE_ID,
            "representation_source_id": source_id,
            "relationship": "same_normalized_state_county_dataset",
            "mirror_comparison_is_corroboration": False,
        },
        "response_schema_fingerprint": "a" * 64,
        "raw_attributes": {
            "OBJECTID": 12,
            "PARCEL_ID_NR": "001-2038010000001",
            "ORIG_PARCEL_ID": "2038010000001",
            "DATA_LINK": "https://example.test/county/parcel",
        },
        "geometry": {
            "rings": [
                [
                    [-118.0, 47.0],
                    [-117.9, 47.0],
                    [-118.0, 47.0],
                ]
            ]
        },
        "geometry_crs": "EPSG:4326",
    }
    return record


def _envelope(source, records):
    query = PublicRecordsQuery(
        source=source,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="53",
            name="Washington",
            state_code="WA",
        ),
        query=QueryMetadata(operation="test", parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def test_parcel_projection_preserves_lineage_and_county_enrichment() -> None:
    native = _parcel_record()
    before = deepcopy(native)

    decision = projection.project_record(
        native,
        source_id=projection.ECOLOGY_SOURCE_ID,
    )

    assert decision.kind == "assessor"
    record = decision.record
    assert record["native_parcel_id"] == "2038010000001"
    assert {
        "001-2038010000001",
        "OBJECTID:12",
        "example-global-id",
    } <= set(record["alternate_parcel_ids"])
    assert record["situs_address"] == {
        "raw": "100 MAIN ST",
        "unit": "UNIT 2",
        "city": "RITZVILLE",
        "state": "WA",
        "postal_code": "99169",
        "country": "US",
    }
    assert record["assessment"]["improvement_value"] == 75_000
    assert record["assessment"]["assessed_value"] == 100_000
    assert record["source_last_updated"] == "2026-01-09T00:00:00Z"
    assert record["snapshot_complete"] is False
    assert record["projection_metadata"]["independent_corroboration"] is False
    assert record["data_link"] == "https://example.test/county/parcel"
    assert record["owner_visibility"]["published_owner_fields"] == ["OWNER_NAME"]
    assert native == before


def test_freshness_land_use_and_parity_are_observation_only() -> None:
    cases = [
        (
            projection.FRESHNESS_SOURCE_ID,
            {
                "record_kind": "county_parcel_freshness",
                "source_id": projection.FRESHNESS_SOURCE_ID,
                "lineage_id": projection.LINEAGE_SOURCE_ID,
                "county_name": "Adams",
                "county_fips": "001",
                "county_geoid": "53001",
                "file_date": "2026-01-09T00:00:00Z",
                "object_id": 1,
            },
            "county_parcel_freshness:53001:1",
        ),
        (
            projection.LAND_USE_SOURCE_ID,
            {
                "record_kind": "county_land_use_code",
                "source_id": projection.LAND_USE_SOURCE_ID,
                "lineage_id": projection.LINEAGE_SOURCE_ID,
                "county_name": "Adams",
                "county_fips": "001",
                "county_geoid": "53001",
                "code": "R",
                "description": "Residential",
                "object_id": 2,
            },
            "county_land_use_code:53001:R:2",
        ),
        (
            projection.LINEAGE_SOURCE_ID,
            {
                "record_kind": "parcel_representation_parity",
                "lineage_id": projection.LINEAGE_SOURCE_ID,
                "sentinel_parcel_id": "001-2038010000001",
                "interpretation": "mirror_health_not_corroboration",
                "representations": {},
                "comparisons": [],
            },
            "parcel_representation_parity:001-2038010000001",
        ),
    ]

    for source_id, record, expected_identity in cases:
        decision = projection.project_record(record, source_id=source_id)
        assert decision.kind == "observation"
        assert decision.observation_kind == record["record_kind"]
        assert decision.source_native_id == expected_identity
        assert decision.record == record


def test_ingest_projects_parcel_values_geometry_owner_and_source_lineage(
    tmp_path,
) -> None:
    db_path = tmp_path / "property.db"
    envelope = _envelope(washington.ECOLOGY.source_metadata(), [_parcel_record()])

    result = ingest_property_envelope(envelope, db_path=db_path)

    assert result["projection_supported"] is True
    assert result["records_ingested"] == 1
    assert result["records"][0]["assessments_upserted"] == 1
    assert result["records"][0]["owners_upserted"] == 1
    assert result["records"][0]["geometry_upserted"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            projection.ECOLOGY_SOURCE_ID,
            "53001",
            "2038010000001",
            "",
        )
        assessment = db.execute(
            """
            SELECT land_value_minor, improvement_value_minor,
                   total_value_minor, assessed_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            2_500_000,
            7_500_000,
            10_000_000,
            10_000_000,
        )
        owner = db.execute(
            "SELECT raw_owner_name FROM ownership_assertion"
        ).fetchone()
        assert owner["raw_owner_name"] == "EXAMPLE OWNER LLC"
        geometry = db.execute(
            "SELECT geometry_format, crs FROM parcel_geometry"
        ).fetchone()
        assert tuple(geometry) == ("esri_json", "EPSG:4326")
        state = db.execute(
            "SELECT name, state_code FROM jurisdiction WHERE geoid='53'"
        ).fetchone()
        assert tuple(state) == ("Washington", "WA")
    finally:
        db.close()


def test_ingest_preserves_county_freshness_as_attributable_observation(
    tmp_path,
) -> None:
    record = {
        "record_kind": "county_parcel_freshness",
        "source_id": projection.FRESHNESS_SOURCE_ID,
        "lineage_id": projection.LINEAGE_SOURCE_ID,
        "county_name": "Adams",
        "county_fips": "001",
        "county_geoid": "53001",
        "source_native_county": "1",
        "file_date": "2026-01-09T00:00:00Z",
        "global_id": "freshness-row",
        "object_id": 1,
    }
    envelope = _envelope(washington.FRESHNESS_METADATA, [record])
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(envelope, db_path=db_path)

    assert result["records_ingested"] == 1
    assert result["records"][0]["projection"] == "observation_only"
    assert result["records"][0]["source_native_id"] == (
        "county_parcel_freshness:53001:1"
    )
    db = connect_property(db_path)
    try:
        observation = db.execute(
            """
            SELECT source_id, source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE record_kind='county_parcel_freshness'
            """
        ).fetchone()
        assert observation["source_id"] == projection.FRESHNESS_SOURCE_ID
        assert observation["source_native_id"] == (
            "county_parcel_freshness:53001:1"
        )
        assert '"file_date":"2026-01-09T00:00:00Z"' in observation["raw_json"]
    finally:
        db.close()
