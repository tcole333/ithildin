from __future__ import annotations

import json
from pathlib import Path

from tools import query_palm_beach_property_appraiser as palm
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_property


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "palm_beach_property_appraiser"
)


def _records():
    metadata = json.loads(
        (FIXTURE_DIR / "metadata.json").read_text(encoding="utf-8")
    )
    features = json.loads(
        (FIXTURE_DIR / "features.json").read_text(encoding="utf-8")
    )
    contract = palm.metadata_contract(metadata)
    return [
        palm.normalize_feature(
            feature,
            contract=contract,
            geometry_requested=True,
        )
        for feature in features
    ]


def _envelope(*records):
    query = PublicRecordsQuery(
        source=palm.SOURCE_METADATA,
        jurisdiction=palm.JURISDICTION,
        query=QueryMetadata(
            operation="test",
            parameters={"object_ids": [1, 2]},
        ),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def test_repeated_parcel_number_preserves_occurrences_without_parid_alias(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    first, second, _redacted = _records()

    summary = ingest_property_envelope(
        _envelope(first, second),
        db_path=db_path,
    )

    assert summary["projection_supported"] is True
    assert summary["records_ingested"] == 2
    assert {
        item["feature_occurrence_id"] for item in summary["records"]
    } == {"OBJECTID:1", "OBJECTID:2"}
    assert all(
        item["parcel_join_uniqueness_assumed"] is False
        for item in summary["records"]
    )
    assert all(
        item["parid_projected_as_parcel_alias"] is False
        for item in summary["records"]
    )

    db = connect_property(db_path)
    try:
        observations = db.execute(
            """
            SELECT source_native_id
            FROM source_observation
            WHERE source_id=?
              AND record_kind='parcel_assessment_geometry_snapshot'
            ORDER BY source_native_id
            """,
            (palm.SOURCE_ID,),
        ).fetchall()
        assert [row["source_native_id"] for row in observations] == sorted(
            [first["feature_ref"], second["feature_ref"]]
        )

        parcels = db.execute(
            """
            SELECT native_parcel_id, raw_json
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (palm.SOURCE_ID,),
        ).fetchall()
        assert len(parcels) == 1
        assert parcels[0]["native_parcel_id"] == "04364325000005040"
        raw = json.loads(parcels[0]["raw_json"])
        assert raw["source_occurrence_id"] == second["feature_ref"]
        assert raw["snapshot_complete"] is False

        assert (
            db.execute(
                "SELECT COUNT(*) FROM parcel_alias WHERE source_id=?",
                (palm.SOURCE_ID,),
            ).fetchone()[0]
            == 0
        )
        addresses = db.execute(
            """
            SELECT address_role, raw_address
            FROM parcel_address
            WHERE source_id=?
            ORDER BY address_role
            """,
            (palm.SOURCE_ID,),
        ).fetchall()
        assert [tuple(row) for row in addresses] == [
            ("mailing", "EXAMPLE OWNER, PO BOX 100"),
            ("situs", "100 MAIN ST"),
        ]
        owner = db.execute(
            """
            SELECT assertion_type, raw_owner_name
            FROM ownership_assertion
            WHERE source_id=?
            """,
            (palm.SOURCE_ID,),
        ).fetchone()
        assert tuple(owner) == ("assessment_roll", "EXAMPLE OWNER")
        sale = db.execute(
            """
            SELECT derivation, native_sale_id, instrument_id
            FROM sale_event
            WHERE source_id=?
            """,
            (palm.SOURCE_ID,),
        ).fetchone()
        assert sale["derivation"] == "assessment_roll"
        assert sale["native_sale_id"] == "BOOK:5021:PAGE:1011"
        assert sale["instrument_id"] is None
        assert (
            db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0]
            == 0
        )
    finally:
        db.close()


def test_confidential_blank_fields_remain_publisher_state(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    redacted = _records()[2]

    summary = ingest_property_envelope(
        _envelope(redacted),
        db_path=db_path,
    )
    assert summary["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM ownership_assertion WHERE source_id=?",
                (palm.SOURCE_ID,),
            ).fetchone()[0]
            == 0
        )
        raw = json.loads(
            db.execute(
                """
                SELECT raw_json FROM source_observation
                WHERE source_id=?
                  AND record_kind='parcel_assessment_geometry_snapshot'
                """,
                (palm.SOURCE_ID,),
            ).fetchone()["raw_json"]
        )
        assert raw["publisher_redaction_state"]["confidential_flag"] == "Y"
        assert raw["publisher_redaction_state"]["interpretation"] == (
            "publisher_state_preserved_without_code_inference"
        )
    finally:
        db.close()
