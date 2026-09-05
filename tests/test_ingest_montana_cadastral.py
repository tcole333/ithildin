from __future__ import annotations

from copy import deepcopy

import pytest

from tools import query_montana_cadastral as mt
from tools.ingest_property_records import (
    PropertyIngestError,
    ingest_property_envelope,
)
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


def _snapshot() -> mt.SourceSnapshot:
    return mt.SourceSnapshot(
        schema_fingerprint="a" * 64,
        data_fingerprint="b" * 64,
        native_page_size=2_000,
        total_features=920_595,
        features_with_parcel_id=886_422,
        maximum_object_id=920_595,
        edge_tax_year=2026,
        layer_metadata={},
    )


def _feature_record(
    *,
    object_id: int = 77,
    parcel_id: str | None = "56382732101040000",
    global_id: str | None = "{montana-feature-77}",
    geometry: bool = True,
) -> dict:
    attributes = {field: None for field in mt.QUERY_FIELDS}
    attributes.update(
        {
            "OBJECTID": object_id,
            "GlobalID": global_id,
            "PARCELID": parcel_id,
            "COUNTYCD": 55,
            "CountyName": "Petroleum",
            "CountyAbbr": "PE",
            "GISAcres": 12.5,
            "TaxYear": 2026,
            "PropertyID": 100077,
            "AssessmentCode": "000077",
            "LegalDescriptionShort": "TRACT 1",
            "AddressLine1": "1 MAIN ST",
            "AddressLine2": "UNIT 2",
            "CityStateZip": "WINNETT MT 59087",
            "TotalBuildingValue": 25_000,
            "TotalLandValue": 100_000,
            "TotalValue": 125_000,
            "OwnerName": "MONTANA RANCH LLC",
            "OwnerAddress1": "PO BOX 1",
            "OwnerCity": "WINNETT",
            "OwnerState": "MT",
            "OwnerZipCode": "59087",
            "DbaName": "RANCH OPERATIONS",
            "CareOfTaxpayer": "TAX DEPARTMENT",
        }
    )
    feature = {"attributes": attributes}
    if geometry:
        feature["geometry"] = {
            "rings": [
                [
                    [-108.4, 47.0],
                    [-108.3, 47.0],
                    [-108.3, 47.1],
                    [-108.4, 47.0],
                ]
            ]
        }
    return mt._normalize_feature(
        feature,
        snapshot=_snapshot(),
        geometry_requested=geometry,
    )


def _envelope(record: dict, *, command: str = "parcel") -> dict:
    if command == "parcel":
        args = mt.build_parser().parse_args(
            [
                "parcel",
                record.get("identity", {}).get("parcel_id") or "missing",
                "--geometry",
            ]
        )
    elif command == "releases":
        args = mt.build_parser().parse_args(["releases"])
    elif command == "manifest":
        args = mt.build_parser().parse_args(
            ["manifest", "--dataset", "parcel-shp"]
        )
    elif command == "artifact-probe":
        args = mt.build_parser().parse_args(
            ["artifact-probe", "--dataset", "parcel-shp"]
        )
    elif command == "download":
        args = mt.build_parser().parse_args(
            [
                "download",
                "--dataset",
                "parcel-shp",
                "--destination",
                "/tmp/montana-parcels.zip",
            ]
        )
    else:
        raise AssertionError(command)
    return PublicRecordsResult.success(
        mt.build_query(args),
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def test_live_feature_projects_parcel_assessment_owner_addresses_aliases_and_geometry(
    tmp_path,
) -> None:
    db_path = tmp_path / "property.db"
    record = _feature_record()

    result = ingest_property_envelope(_envelope(record), db_path=db_path)

    assert result["projection_supported"] is True
    assert result["records_ingested"] == 1
    assert result["records_preserved_without_projection"] == 0
    projection = result["records"][0]
    assert projection["canonical_ref"] == (
        "PROPERTY:us-mt-msl-cadastral/30069/parcel/56382732101040000"
    )
    assert projection["source_occurrence_id"] == "{montana-feature-77}"
    assert projection["orion_county_prefix"] == 55
    assert projection["county_geoid"] == "30069"
    assert projection["typed_aliases_inserted"] == 2
    assert projection["geometry_upserted"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT jurisdiction_geoid, native_parcel_id, roll_year, raw_json
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (mt.SOURCE_ID,),
        ).fetchone()
        assert tuple(parcel)[:3] == (
            "30069",
            "56382732101040000",
            "2026",
        )
        assert '"source_record_id":"{montana-feature-77}"' in parcel["raw_json"]

        occurrence = db.execute(
            """
            SELECT source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind='parcel_feature_occurrence'
            """,
            (mt.SOURCE_ID,),
        ).fetchone()
        assert occurrence["source_native_id"] == "{montana-feature-77}"
        assert '"object_id":77' in occurrence["raw_json"]

        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor, market_value_minor, assessment_class
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            "2026",
            10_000_000,
            2_500_000,
            12_500_000,
            12_500_000,
            None,
        )

        owner = db.execute(
            """
            SELECT assertion_type, raw_owner_name, claim_type
            FROM ownership_assertion
            """
        ).fetchone()
        assert tuple(owner) == (
            "assessment_roll",
            "MONTANA RANCH LLC",
            "direct_quote",
        )

        addresses = db.execute(
            """
            SELECT address_role, raw_address, city, state, postal_code
            FROM parcel_address
            ORDER BY address_role
            """
        ).fetchall()
        assert [row["address_role"] for row in addresses] == [
            "mailing",
            "situs",
        ]
        assert addresses[0]["raw_address"] == (
            "TAX DEPARTMENT, PO BOX 1, WINNETT, MT 59087"
        )
        assert tuple(addresses[0])[2:] == ("WINNETT", "MT", "59087")
        assert addresses[1]["raw_address"] == (
            "1 MAIN ST, UNIT 2, WINNETT MT 59087"
        )

        aliases = db.execute(
            """
            SELECT alias_type, alias_value
            FROM parcel_alias
            ORDER BY alias_type, alias_value
            """
        ).fetchall()
        assert {
            (row["alias_type"], row["alias_value"])
            for row in aliases
        } >= {
            ("montana_property_id", "100077"),
            ("montana_assessment_code", "000077"),
        }

        geometry = db.execute(
            """
            SELECT geometry_format, crs, accuracy_disclaimer
            FROM parcel_geometry
            """
        ).fetchone()
        assert geometry["geometry_format"] == "esri_json"
        assert geometry["crs"] == "EPSG:4326"
        assert "recorded instruments" in geometry["accuracy_disclaimer"]
    finally:
        db.close()


def test_multiple_feature_occurrences_keep_distinct_observations_for_one_parcel(
    tmp_path,
) -> None:
    db_path = tmp_path / "property.db"
    records = [
        _feature_record(
            object_id=77,
            global_id="{montana-feature-77}",
            geometry=False,
        ),
        _feature_record(
            object_id=78,
            global_id="{montana-feature-78}",
            geometry=False,
        ),
    ]
    args = mt.build_parser().parse_args(
        ["parcel", "56382732101040000"]
    )
    envelope = PublicRecordsResult.success(
        mt.build_query(args),
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()

    result = ingest_property_envelope(envelope, db_path=db_path)

    assert result["records_ingested"] == 2
    db = connect_property(db_path)
    try:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM parcel_snapshot WHERE source_id=?",
                (mt.SOURCE_ID,),
            ).fetchone()[0]
            == 1
        )
        occurrences = db.execute(
            """
            SELECT source_native_id
            FROM source_observation
            WHERE source_id=? AND record_kind='parcel_feature_occurrence'
            ORDER BY source_native_id
            """,
            (mt.SOURCE_ID,),
        ).fetchall()
        assert [row["source_native_id"] for row in occurrences] == [
            "{montana-feature-77}",
            "{montana-feature-78}",
        ]
    finally:
        db.close()


def test_feature_without_parcelid_is_preserved_without_fabricating_a_parcel(
    tmp_path,
) -> None:
    db_path = tmp_path / "property.db"
    record = _feature_record(parcel_id=None)

    result = ingest_property_envelope(_envelope(record), db_path=db_path)

    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"][0]["reason"] == (
        "montana_feature_occurrence_has_no_parcelid_join"
    )
    db = connect_property(db_path)
    try:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM parcel_snapshot WHERE source_id=?",
                (mt.SOURCE_ID,),
            ).fetchone()[0]
            == 0
        )
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 0
        assert (
            db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0]
            == 0
        )
        occurrence = db.execute(
            """
            SELECT source_native_id, record_kind
            FROM source_observation
            WHERE source_id=? AND record_kind='parcel_feature_occurrence'
            """,
            (mt.SOURCE_ID,),
        ).fetchone()
        assert tuple(occurrence) == (
            "{montana-feature-77}",
            "parcel_feature_occurrence",
        )
    finally:
        db.close()


@pytest.mark.parametrize(
    ("command", "record"),
    [
        (
            "releases",
            {
                "source_id": mt.SOURCE_ID,
                "record_type": "bulk_release_discovery",
                "release_discovery_fingerprint": "c" * 64,
            },
        ),
        (
            "manifest",
            {
                "source_id": mt.SOURCE_ID,
                "release": {"release_id": "parcel-shp:statewide:marker"},
                "artifacts": [],
            },
        ),
        (
            "artifact-probe",
            {
                "manifest": {"source_id": mt.SOURCE_ID},
                "selected_artifact": {"artifact_id": "data"},
                "probe": {"status": 206},
            },
        ),
        (
            "download",
            {
                "manifest": {"source_id": mt.SOURCE_ID},
                "selected_artifact": {"artifact_id": "data"},
                "download": {"status": "downloaded"},
            },
        ),
    ],
)
def test_bulk_release_records_remain_envelope_only(
    tmp_path,
    command: str,
    record: dict,
) -> None:
    db_path = tmp_path / f"{command}.db"

    result = ingest_property_envelope(
        _envelope(record, command=command),
        db_path=db_path,
    )

    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"][0]["reason"] == (
        "montana_bulk_or_metadata_record_is_envelope_only"
    )
    db = connect_property(db_path)
    try:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM parcel_snapshot WHERE source_id=?",
                (mt.SOURCE_ID,),
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute(
                """
                SELECT COUNT(*) FROM source_observation
                WHERE source_id=?
                """,
                (mt.SOURCE_ID,),
            ).fetchone()[0]
            == 2
        )
    finally:
        db.close()


def test_projection_rejects_a_county_geoid_that_conflicts_with_orion_prefix(
    tmp_path,
) -> None:
    record = deepcopy(_feature_record())
    record["jurisdiction"]["county_geoid"] = "30053"

    with pytest.raises(PropertyIngestError, match="crosswalk"):
        ingest_property_envelope(
            _envelope(record),
            db_path=tmp_path / "property.db",
        )
