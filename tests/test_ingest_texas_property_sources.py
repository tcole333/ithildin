from __future__ import annotations

import json

from tools import query_hcad_gis
from tools import query_txgio_land_parcels
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


def _hcad_feature(object_id: int, *, account: str | None = "1144740190749") -> dict:
    return query_hcad_gis._normalize_feature(
        {
            "attributes": {
                "OBJECTID": object_id,
                "HCAD_NUM": account,
                "acct_num": account,
                "LOWPARCELID": account,
                "GlobalID": f"{{hcad-feature-{object_id}}}",
                "tax_year": "2025",
                "owner_name_1": "HILL GERALD B",
                "owner_name_2": None,
                "owner_name_3": None,
                "mail_addr_1": "PO BOX 10",
                "mail_city": "HOUSTON",
                "mail_state": "TX",
                "mail_zip": "77040",
                "site_str_num": 7906,
                "site_str_name": "WOODSMAN",
                "site_str_sfx": "TRL",
                "site_city": "HOUSTON",
                "site_county": "HARRIS",
                "site_zip": "77040",
                "land_value": 53_962,
                "impr_value": 124_062,
                "total_appraised_val": 178_024,
                "total_market_val": 180_000,
                "legal_dscr_1": "LT 749 BLK 19",
            },
            "geometry": {
                "rings": [
                    [
                        [-95.5, 29.8],
                        [-95.4, 29.8],
                        [-95.4, 29.9],
                        [-95.5, 29.8],
                    ]
                ]
            },
        },
        schema_fingerprint="a" * 64,
    )


def _hcad_envelope() -> dict:
    args = query_hcad_gis.build_parser().parse_args(
        ["account", "1144740190749", "--limit", "2", "--geometry"]
    )
    return PublicRecordsResult.success(
        query_hcad_gis.build_query(args),
        [_hcad_feature(10), _hcad_feature(11)],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _txgio_record() -> dict:
    artifact_sha256 = "b" * 64
    return {
        "canonical_ref": "property:txgio:parcel:P-100",
        "feature_ref": "property:txgio:feature:P-100:77",
        "evidence_ref": f"TXGIO-LP:{artifact_sha256}:77",
        "source_id": query_txgio_land_parcels.SOURCE_ID,
        "record_kind": "parcel_assessment_geometry_snapshot",
        "record_type": "txgio_county_parcel_feature_snapshot",
        "jurisdiction": {
            "state_code": "TX",
            "county_fips": "48261",
            "county_name": "Kenedy",
        },
        "native_parcel_id": "P-100",
        "parcel_identifiers": {
            "prop_id": "P-100",
            "geo_id": "G-200",
        },
        "feature_occurrence": {
            "dbf_record_index": 77,
            "native_object_id": "9001",
            "feature_ref": "property:txgio:feature:P-100:77",
        },
        "owners": [
            {
                "raw_name": "KING RANCH INC",
                "role": "assessment_snapshot_owner_name",
            },
            {
                "raw_name": "CARE OF TAX DEPARTMENT",
                "role": "assessment_snapshot_care_of_name",
            },
        ],
        "situs_address": {
            "raw": "100 RANCH RD",
            "city": "SARITA",
            "state": "TX",
            "postal_code": "78385",
            "country": "US",
        },
        "mailing_address": {
            "raw": "PO BOX 1",
            "city": "SARITA",
            "state": "TX",
            "postal_code": "78385",
            "country": "US",
        },
        "assessment": {
            "tax_year": 2025,
            "land_value": 100_000,
            "improvement_value": 25_000,
            "market_value": 125_000,
            "currency": "USD",
        },
        "geometry_available": {
            "artifact_path": "/tmp/txgio-kenedy.zip",
            "shapefile": {
                "member_name": "shp/Kenedy_Parcels.shp",
                "shape_type_role": "polygon",
            },
            "projection_wkt": 'PROJCS["NAD83 / Texas South"]',
            "dbf_record_index": 77,
            "projection_status": ("geometry_present_not_decoded_by_local_search"),
        },
        "artifact_snapshot": {
            "path": "/tmp/txgio-kenedy.zip",
            "sha256": artifact_sha256,
            "dbf_last_update": "2025-06-01",
            "dbf_record_index": 77,
            "schema_fingerprint": "c" * 64,
        },
        "schema_fingerprint": "c" * 64,
        "source_url": query_txgio_land_parcels.LANDING_URL,
    }


def _txgio_envelope() -> dict:
    args = query_txgio_land_parcels.build_parser().parse_args(
        [
            "search",
            "/tmp/txgio-kenedy.zip",
            "P-100",
            "--field",
            "parcel",
            "--match",
            "exact",
            "--limit",
            "1",
        ]
    )
    return PublicRecordsResult.success(
        query_txgio_land_parcels.build_query(args),
        [_txgio_record()],
        retrieved_at="2026-07-30T12:00:00Z",
        raw_artifact_refs=("/tmp/txgio-kenedy.zip",),
    ).to_dict()


def test_hcad_gis_projection_keeps_feature_occurrences_and_parcel_join(
    tmp_path,
) -> None:
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(_hcad_envelope(), db_path=db_path)

    assert result["projection_supported"] is True
    assert result["records_ingested"] == 2
    assert {record["canonical_ref"] for record in result["records"]} == {
        ("PROPERTY:us-tx-harris-hcad-gis/48201/parcel/1144740190749")
    }
    db = connect_property(db_path)
    try:
        occurrences = db.execute(
            """
            SELECT source_native_id
            FROM source_observation
            WHERE source_id=? AND record_kind=?
            ORDER BY source_native_id
            """,
            (
                query_hcad_gis.SOURCE_ID,
                "parcel_assessment_geometry_snapshot",
            ),
        ).fetchall()
        assert len(occurrences) == 2
        assert occurrences[0]["source_native_id"] != occurrences[1]["source_native_id"]
        assert (
            db.execute(
                "SELECT COUNT(*) FROM parcel_snapshot WHERE source_id=?",
                (query_hcad_gis.SOURCE_ID,),
            ).fetchone()[0]
            == 1
        )
        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor, market_value_minor,
                   assessed_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            "2025",
            5_396_200,
            12_406_200,
            17_802_400,
            18_000_000,
            17_802_400,
        )
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 1
        geometry = db.execute(
            """
            SELECT geometry_format, crs, accuracy_disclaimer
            FROM parcel_geometry
            """
        ).fetchone()
        assert tuple(geometry) == (
            "esri_json",
            "EPSG:4326",
            (
                "Source MapServer feature occurrence; HCAD_NUM is not unique "
                "within the layer."
            ),
        )
    finally:
        db.close()


def test_txgio_projection_keeps_owner_semantics_and_polygon_reference(
    tmp_path,
) -> None:
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(_txgio_envelope(), db_path=db_path)

    assert result["projection_supported"] is True
    assert result["records_ingested"] == 1
    projection = result["records"][0]
    assert projection["geometry_upserted"] == 1
    assert projection["geometry_decoded"] is False
    assert projection["geometry_reference"].endswith(
        "#shp/Kenedy_Parcels.shp:dbf-record=77"
    )
    db = connect_property(db_path)
    try:
        observation = db.execute(
            """
            SELECT source_native_id, raw_artifact_sha256, raw_artifact_path
            FROM source_observation
            WHERE source_id=? AND record_kind=?
            """,
            (
                query_txgio_land_parcels.SOURCE_ID,
                "parcel_assessment_geometry_snapshot",
            ),
        ).fetchone()
        assert tuple(observation) == (
            "property:txgio:feature:P-100:77",
            "b" * 64,
            "/tmp/txgio-kenedy.zip",
        )
        aliases = db.execute("SELECT alias_value FROM parcel_alias").fetchall()
        assert [row["alias_value"] for row in aliases] == ["G-200"]
        owners = db.execute("SELECT raw_owner_name FROM ownership_assertion").fetchall()
        assert [row["raw_owner_name"] for row in owners] == ["KING RANCH INC"]
        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor, market_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            "2025",
            10_000_000,
            2_500_000,
            12_500_000,
            12_500_000,
        )
        geometry = db.execute(
            """
            SELECT geometry_format, crs, source_resolution,
                   accuracy_disclaimer, snapshot_date
            FROM parcel_geometry
            """
        ).fetchone()
        assert geometry["geometry_format"] == "shapefile_record_reference"
        assert geometry["crs"].startswith("source-prj-wkt-sha256:")
        assert geometry["source_resolution"] == "source_polygon_reference"
        assert geometry["snapshot_date"] == "2025-06-01"
        assert "not decoded" in geometry["accuracy_disclaimer"]
    finally:
        db.close()


def test_nonparcel_bulk_records_remain_preserved_without_projection(
    tmp_path,
) -> None:
    envelope = _txgio_envelope()
    envelope["records"] = [
        {
            "source_id": query_txgio_land_parcels.SOURCE_ID,
            "record_kind": "bulk_dataset_manifest",
            "release_id": "fixture",
        }
    ]

    result = ingest_property_envelope(
        envelope,
        db_path=tmp_path / "property.db",
    )

    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"][0]["reason"] == (
        "txgio_record_is_not_a_local_parcel_feature"
    )


def test_unlinked_hcad_features_retain_distinct_occurrence_references(
    tmp_path,
) -> None:
    envelope = _hcad_envelope()
    # Normalize absent raw join keys so the occurrence reference is generated
    # consistently, rather than mutating only part of an already-linked record.
    features = [_hcad_feature(object_id, account=None) for object_id in (99, 100)]
    envelope["records"] = features

    db_path = tmp_path / "property.db"
    result = ingest_property_envelope(envelope, db_path=db_path)

    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 2
    assert all(
        item["reason"] == "feature_occurrence_has_no_parcel_join_identifier"
        for item in result["projection_skips"]
    )
    db = connect_property(db_path)
    try:
        occurrences = db.execute(
            """
            SELECT source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind<>?
            """,
            (query_hcad_gis.SOURCE_ID, "query_envelope"),
        ).fetchall()
        assert {row["source_native_id"] for row in occurrences} == {
            "PROPERTY:us-tx-harris-hcad-gis/48201/parcel_feature/unlinked%3A99",
            "PROPERTY:us-tx-harris-hcad-gis/48201/parcel_feature/unlinked%3A100",
        }
        assert {row["record_kind"] for row in occurrences} == {
            "hcad_mapserver_parcel_feature"
        }
        for row in occurrences:
            raw = json.loads(row["raw_json"])
            assert raw["native_parcel_id"] is None
            assert raw["feature_ref"] == row["source_native_id"]
            assert raw["parcel_join_key"]["value"] is None
        assert {
            json.loads(row["raw_json"])["feature_occurrence"]["object_id"]
            for row in occurrences
        } == {99, 100}
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
    finally:
        db.close()
