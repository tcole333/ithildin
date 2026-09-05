from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import dc_property_projection as projection
from tools import query_dc_property as dc
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "dc_property"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text())


def _normalized(component: dc.Component, fixture: str) -> dict[str, Any]:
    return dc._normalize_feature(
        component,
        _fixture(fixture),
        response_schema_fingerprint=f"{component.key}-schema",
        geometry_crs=4326,
    )


def _envelope(
    component: dc.Component,
    record: dict[str, Any],
) -> dict[str, Any]:
    query = dc._build_query(
        component,
        component.key,
        {"component": component.key},
        limit=1,
        cursor=None,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def test_dc_projection_keeps_component_identity_and_account_polygon_grain():
    account = projection.project_record(
        _normalized(dc.ITSPE, "assessment"),
        source_id=dc.ITSPE_SOURCE_ID,
    )
    polygon = projection.project_record(
        _normalized(dc.OWNER_POLYGONS, "owner_polygon"),
        source_id=dc.OWNER_POLYGON_SOURCE_ID,
    )

    assert account.kind == "assessor"
    assert account.record["jurisdiction"]["state_fips"] == "11"
    assert account.record["tax_year"] == "2026"
    assert account.record["assessment"]["land_value"] == 1_031_850
    assert account.record["assessment"]["parcel_value"] == 1_520_370
    assert account.record["snapshot_complete"] is True
    assert account.record["last_sale"]["source_document_ref"] == "2023000123"

    assert polygon.kind == "assessor"
    assert polygon.record["source_id"] == dc.OWNER_POLYGON_SOURCE_ID
    assert polygon.record["snapshot_complete"] is False
    assert polygon.record["geometry_crs"] == "EPSG:4326"
    assert polygon.record["projection_metadata"][
        "account_polygon_cardinality"
    ] == "not_assumed_one_to_one"
    assert polygon.record["projection_metadata"][
        "independent_corroboration"
    ] is False


def test_dc_itspe_ingestion_projects_assessment_tax_owner_and_sale(tmp_path):
    record = _normalized(dc.ITSPE, "assessment")
    result = ingest_property_envelope(
        _envelope(dc.ITSPE, record),
        db_path=tmp_path / "property.db",
    )

    projected = result["records"][0]
    assert projected["assessments_upserted"] == 1
    assert projected["owners_upserted"] == 2
    assert projected["sales_upserted"] == 1
    assert projected["tax_events_upserted"] == 18

    db = connect_property(tmp_path / "property.db")
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchone()
        assessment = db.execute(
            """
            SELECT land_value_minor, improvement_value_minor, total_value_minor
            FROM assessment
            """
        ).fetchone()
        event_types = {
            row["event_type"]
            for row in db.execute(
                "SELECT event_type FROM tax_account_event"
            ).fetchall()
        }
        sale = db.execute(
            """
            SELECT native_sale_id, derivation, consideration_minor
            FROM sale_event
            """
        ).fetchone()
    finally:
        db.close()

    assert dict(parcel) == {
        "source_id": dc.ITSPE_SOURCE_ID,
        "jurisdiction_geoid": "11",
        "native_parcel_id": dc.PROBE_SSL,
        "roll_year": "2026",
    }
    assert dict(assessment) == {
        "land_value_minor": 103_185_000,
        "improvement_value_minor": 48_852_000,
        "total_value_minor": 152_037_000,
    }
    assert {
        "account_annual_tax",
        "account_total_due",
        "account_total_collected",
        "account_total_balance",
        "installment_due",
        "period_tax",
        "period_total_due",
        "period_collected",
        "period_balance",
    }.issubset(event_types)
    assert dict(sale) == {
        "native_sale_id": "2023000123",
        "derivation": "assessment_roll",
        "consideration_minor": 49_836_000,
    }


def test_dc_geometry_and_cama_sale_share_ssl_without_claiming_same_source(tmp_path):
    db_path = tmp_path / "property.db"
    polygon = _normalized(dc.OWNER_POLYGONS, "owner_polygon")
    polygon_result = ingest_property_envelope(
        _envelope(dc.OWNER_POLYGONS, polygon),
        db_path=db_path,
    )
    sale = _normalized(dc.SALES, "sale")
    sale_result = ingest_property_envelope(
        _envelope(dc.SALES, sale),
        db_path=db_path,
    )

    polygon_projection = polygon_result["records"][0]
    sale_projection = sale_result["records"][0]
    assert polygon_projection["geometry_upserted"] == 1
    assert polygon_projection["tax_events_upserted"] == 0
    assert sale_projection["sales_upserted"] == 1
    assert sale_projection["parcel_id"] == polygon_projection["parcel_id"]

    db = connect_property(db_path)
    try:
        geometry = db.execute(
            "SELECT source_id, geometry_format, crs FROM parcel_geometry"
        ).fetchone()
        sale_row = db.execute(
            """
            SELECT source_id, native_sale_id, derivation, qualification_code
            FROM sale_event
            WHERE source_id=?
            """,
            (dc.SALES_SOURCE_ID,),
        ).fetchone()
    finally:
        db.close()

    assert dict(geometry) == {
        "source_id": dc.OWNER_POLYGON_SOURCE_ID,
        "geometry_format": "esri_json",
        "crs": "EPSG:4326",
    }
    assert dict(sale_row) == {
        "source_id": dc.SALES_SOURCE_ID,
        "native_sale_id": "420252",
        "derivation": "dc_cama_property_sales",
        "qualification_code": "Q",
    }


def test_dc_survey_ingestion_stays_an_attributable_survey_observation(tmp_path):
    record = _normalized(dc.SURVEYS, "survey")
    decision = projection.project_record(
        record,
        source_id=dc.SURVEY_SOURCE_ID,
    )
    assert decision.kind == "observation"
    assert decision.record["projection_metadata"]["recorder_equivalence"] is False

    db_path = tmp_path / "property.db"
    result = ingest_property_envelope(
        _envelope(dc.SURVEYS, record),
        db_path=db_path,
    )
    assert result["records"][0]["projection"] == "observation_only"
    assert result["records"][0]["record_kind"] == "surveyor_document"

    db = connect_property(db_path)
    try:
        survey = db.execute(
            """
            SELECT source_id, source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE record_kind='surveyor_document'
            """
        ).fetchone()
        instruments = db.execute(
            "SELECT COUNT(*) AS count FROM recorded_instrument"
        ).fetchone()
    finally:
        db.close()

    raw = json.loads(survey["raw_json"])
    assert survey["source_id"] == dc.SURVEY_SOURCE_ID
    assert dc.PROBE_SURVEY_GUID in survey["source_native_id"]
    assert raw["document"]["viewer_url"].startswith(
        "https://doberecords.dc.gov/"
    )
    assert instruments["count"] == 0
