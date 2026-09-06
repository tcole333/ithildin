from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tools import query_mason_county_tax_parcels as mason
from tools.ingest_property_records import (
    PropertyIngestError,
    ingest_property_envelope,
)
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_property


def _contract() -> mason.LayerContract:
    return mason.LayerContract(
        schema_fingerprint="a" * 64,
        field_names=mason.REQUIRED_FIELDS,
        max_record_count=1_000,
        object_id_field="FID",
        geometry_type=mason.GEOMETRY_TYPE,
        spatial_reference={"wkid": 102749, "latestWkid": 2286},
        supports_pagination=False,
        supports_order_by=False,
        supports_statistics=False,
        supports_advanced_queries=False,
    )


def _feature(
    fid: int,
    *,
    pin: str | None = "219010090013",
    terra_pin: str | None = "21901-00-90013",
    taxlot: str | None = "0090013",
) -> dict[str, Any]:
    return {
        "attributes": {
            "FID": fid,
            "PIN": pin,
            "TERRA_PIN": terra_pin,
            "Taxlot": taxlot,
            "Map_number": "219010",
            "SEG_NUMBER": "01",
            "Assessment": "REAL PROPERTY",
            "TotalMarke": 425_000 + fid,
            "TotalAsses": 410_000 + fid,
            "MarketLand": 150_000,
            "MarketBuil": 275_000,
            "AssessedLa": 145_000,
            "AssessedBu": 265_000,
            "ResultingT": 4_200.5,
            "LastName": "EXAMPLE",
            "FirstName": "OWNER",
            "Address1": "PO BOX 10",
            "Address2": "",
            "City": "SHELTON",
            "State": "WA",
            "Zip": "98584",
            "Situs": "100 TEST RD",
            "TotalAcres": 1.25,
            "AssembledL": "LOT 13 TEST PLAT",
            "SubName": "TEST PLAT",
        },
        "geometry": {
            "rings": [
                [
                    [-123.1, 47.2],
                    [-123.0, 47.2],
                    [-123.1, 47.2],
                ]
            ]
        },
    }


def _record(
    fid: int,
    *,
    pin: str | None = "219010090013",
    terra_pin: str | None = "21901-00-90013",
    taxlot: str | None = "0090013",
) -> dict[str, Any]:
    return mason.normalize_feature(
        _feature(
            fid,
            pin=pin,
            terra_pin=terra_pin,
            taxlot=taxlot,
        ),
        contract=_contract(),
        geometry_requested=True,
    )


def _envelope(*records: dict[str, Any]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=mason.SOURCE_METADATA,
        jurisdiction=mason.JURISDICTION,
        query=QueryMetadata(
            operation="test",
            parameters={"object_ids": [0, 1]},
        ),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def test_projection_preserves_feature_occurrences_before_parcel_join(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    zero = _record(0)
    one = _record(1)

    summary = ingest_property_envelope(
        _envelope(zero, one),
        db_path=db_path,
    )

    assert summary["projection_supported"] is True
    assert summary["records_ingested"] == 2
    assert {record["feature_occurrence_id"] for record in summary["records"]} == {
        "FID:0",
        "FID:1",
    }
    assert all(
        record["parcel_join_uniqueness_assumed"] is False
        for record in summary["records"]
    )

    db = connect_property(db_path)
    try:
        observations = db.execute(
            """
            SELECT source_native_id, record_kind
            FROM source_observation
            WHERE source_id=?
              AND record_kind='parcel_assessment_geometry_snapshot'
            ORDER BY source_native_id
            """,
            (mason.SOURCE_ID,),
        ).fetchall()
        assert [row["source_native_id"] for row in observations] == sorted(
            [zero["feature_ref"], one["feature_ref"]]
        )

        parcels = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, raw_json
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (mason.SOURCE_ID,),
        ).fetchall()
        assert len(parcels) == 1
        assert (
            parcels[0]["source_id"],
            parcels[0]["jurisdiction_geoid"],
            parcels[0]["native_parcel_id"],
        ) == (
            mason.SOURCE_ID,
            "53045",
            "219010090013",
        )
        parcel_raw = json.loads(parcels[0]["raw_json"])
        assert parcel_raw["snapshot_complete"] is False
        assert parcel_raw["source_occurrence_id"] == one["feature_ref"]

        aliases = db.execute(
            """
            SELECT alias_value
            FROM parcel_alias
            WHERE source_id=?
            ORDER BY alias_value
            """,
            (mason.SOURCE_ID,),
        ).fetchall()
        assert [row["alias_value"] for row in aliases] == [
            "0090013",
            "21901-00-90013",
        ]

        owner = db.execute(
            """
            SELECT assertion_type, raw_owner_name
            FROM ownership_assertion
            WHERE source_id=?
            """,
            (mason.SOURCE_ID,),
        ).fetchone()
        assert tuple(owner) == ("assessment_roll", "EXAMPLE, OWNER")

        assessment = db.execute(
            """
            SELECT total_value_minor, market_value_minor, assessed_value_minor
            FROM assessment
            WHERE source_id=?
            """,
            (mason.SOURCE_ID,),
        ).fetchone()
        assert tuple(assessment) == (
            42_500_100,
            42_500_100,
            41_000_100,
        )
        geometry = db.execute(
            """
            SELECT geometry_format, crs, accuracy_disclaimer
            FROM parcel_geometry
            WHERE source_id=?
            """,
            (mason.SOURCE_ID,),
        ).fetchone()
        assert geometry["geometry_format"] == "esri_json"
        assert geometry["crs"] == "EPSG:4326"
        assert "not a surveyed legal boundary" in geometry["accuracy_disclaimer"]
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 0
    finally:
        db.close()


def test_unlinked_fid_zero_is_retained_as_observation_only(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    record = _record(0, pin=None, terra_pin=None, taxlot=None)

    summary = ingest_property_envelope(
        _envelope(record),
        db_path=db_path,
    )

    assert summary["records_ingested"] == 0
    assert summary["records_preserved_without_projection"] == 1
    projected = summary["projection_skips"][0]
    assert projected["projection_skipped"] is True
    assert projected["reason"] == ("feature_occurrence_has_no_parcel_join_identifier")
    assert projected["source_native_id"] == record["feature_ref"]

    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
        observation = db.execute(
            """
            SELECT source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE source_id=?
              AND record_kind='parcel_assessment_geometry_snapshot'
            """,
            (mason.SOURCE_ID,),
        ).fetchone()
        assert observation["source_native_id"] == record["feature_ref"]
        assert observation["record_kind"] == ("parcel_assessment_geometry_snapshot")
        raw = json.loads(observation["raw_json"])
        assert raw["object_id"] == 0
        assert raw["source_occurrence_id"] == "FID:0"
    finally:
        db.close()


def test_inconsistent_join_identity_is_rejected(tmp_path: Path) -> None:
    record = _record(0)
    inconsistent = deepcopy(record)
    inconsistent["parcel_join_key"]["value"] = "another-parcel"

    with pytest.raises(
        PropertyIngestError,
        match="parcel join identity is inconsistent",
    ):
        ingest_property_envelope(
            _envelope(inconsistent),
            db_path=tmp_path / "property.db",
        )


def test_boolean_feature_identity_is_rejected(tmp_path: Path) -> None:
    record = _record(0)
    record["feature_occurrence"]["object_id"] = False

    with pytest.raises(
        PropertyIngestError,
        match="FID must be a non-negative integer",
    ):
        ingest_property_envelope(
            _envelope(record),
            db_path=tmp_path / "property.db",
        )
