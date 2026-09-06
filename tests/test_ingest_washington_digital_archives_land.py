from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools import query_washington_digital_archives_land as land
from tools.ingest_property_records import (
    PropertyIngestError,
    ingest_property_envelope,
)
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "washington_digital_archives_land"
)
RECORD_ID = "64742C2528B8C19D43FCC54D20DC97D0"


def _search_record(ordinal: int) -> dict:
    indexed_key = "WSDA:LAND:INDEXED-PARTY:" + ("a" * 64)
    occurrence_id = (
        "WSDA:LAND:SEARCH-OCCURRENCE:"
        + f"{ordinal:064x}"
    )
    return {
        "stable_id": occurrence_id,
        "source_occurrence_id": occurrence_id,
        "query_occurrence_id": occurrence_id,
        "ordinal_occurrence_key": (
            "WSDA:LAND:QUERY-RELATIVE-ORDINAL:"
            + f"{ordinal:064x}"
        ),
        "indexed_party_key": indexed_key,
        "record_kind": "recorded_land_search_result",
        "native_record_id": RECORD_ID,
        "record_url": f"{land.BASE_URL}/Record/View/{RECORD_ID}",
        "native_row_index": ordinal,
        "native_result_ordinal": ordinal,
        "record_id": RECORD_ID,
        "last_name": "SMITH",
        "first_name": "AMOS",
        "party_type": "Borrower",
        "document_type": "Assignment Of Deed Of Trust",
        "year": 2020,
        "county": "Adams",
        "legal_description": "Subdivision GREENE'S ADDITION Lot 1 Block 1",
        "image_exists": True,
        "image_state": "available",
        "evidence_lineage": land.EVIDENCE_LINEAGE,
        "provenance": {
            "source_id": land.SOURCE_ID,
            "source_url": f"{land.BASE_URL}/Search/ResultsTable/",
            "record_url": f"{land.BASE_URL}/Record/View/{RECORD_ID}",
            "retrieved_at": "2026-07-30T12:00:00Z",
            "record_series_id": land.RECORD_SERIES_ID,
            "native_record_id": RECORD_ID,
        },
    }


def _search_envelope() -> dict:
    query = land._build_query(
        title=land.TITLES_BY_KEY["adams"],
        operation="search",
        parameters={
            "record_series_id": land.RECORD_SERIES_ID,
            "title_id": 93,
            "county": "adams",
            "last_name": "SMITH",
            "start_year": 2020,
            "end_year": 2020,
        },
        requested_limit=2,
    )
    return PublicRecordsResult.success(
        query,
        [_search_record(1), _search_record(2)],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _detail_record() -> dict:
    record = land.parse_record_detail(
        (FIXTURE_ROOT / "record_detail.html").read_text(encoding="utf-8"),
        record_id=RECORD_ID,
        source_url=f"{land.BASE_URL}/Record/View/{RECORD_ID}",
        retrieved_at="2026-07-30T12:05:00Z",
    )
    duplicate = dict(record["parties"][1])
    duplicate["sequence_no"] = 3
    record["parties"][2] = duplicate
    return record


def _detail_envelope(
    record: dict | None = None,
    *,
    retrieved_at: str = "2026-07-30T12:05:00Z",
) -> dict:
    query = land._build_query(
        title=land.TITLES_BY_KEY["adams"],
        operation="detail",
        parameters={"record_id": RECORD_ID},
        requested_limit=1,
    )
    return PublicRecordsResult.success(
        query,
        [record or _detail_record()],
        retrieved_at=retrieved_at,
    ).to_dict()


def _seed_parcel(
    db_path: Path,
    native_parcel_id: str,
    *,
    alias: str | None = None,
) -> int:
    db = connect_property(db_path)
    try:
        with db:
            db.execute(
                """
                INSERT INTO jurisdiction(
                    geoid, name, jurisdiction_type, state_code
                ) VALUES ('53', 'Washington', 'state', 'WA')
                ON CONFLICT(geoid) DO NOTHING
                """
            )
            db.execute(
                """
                INSERT INTO jurisdiction(
                    geoid, name, jurisdiction_type, parent_geoid,
                    state_code, county_code
                ) VALUES ('53001', 'Adams County', 'county', '53', 'WA', '001')
                ON CONFLICT(geoid) DO NOTHING
                """
            )
            cursor = db.execute(
                """
                INSERT INTO parcel_snapshot(
                    source_id, jurisdiction_geoid, native_parcel_id,
                    roll_year, effective_from, effective_to, raw_json
                ) VALUES (
                    'us-wa-assessor-test', '53001', ?, '2026',
                    '2026-01-01', NULL, '{}'
                )
                """,
                (native_parcel_id,),
            )
            parcel_id = int(cursor.lastrowid)
            if alias is not None:
                db.execute(
                    """
                    INSERT INTO parcel_alias(
                        parcel_id, alias_type, alias_value, source_id,
                        effective_from, effective_to
                    ) VALUES (
                        ?, 'county_parcel_id', ?, 'us-wa-assessor-test',
                        '2026-01-01', NULL
                    )
                    """,
                    (parcel_id, alias),
                )
            return parcel_id
    finally:
        db.close()


def test_index_occurrences_share_one_instrument_without_creating_parties(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(_search_envelope(), db_path=db_path)

    assert result["records_ingested"] == 2
    assert {
        row["source_occurrence_id"] for row in result["records"]
    } == {
        _search_record(1)["source_occurrence_id"],
        _search_record(2)["source_occurrence_id"],
    }
    assert {row["instrument_id"] for row in result["records"]} == {
        result["records"][0]["instrument_id"]
    }
    db = connect_property(db_path)
    try:
        occurrences = db.execute(
            """
            SELECT source_native_id
            FROM source_observation
            WHERE source_id=? AND record_kind='recorded_land_search_result'
            ORDER BY source_native_id
            """,
            (land.SOURCE_ID,),
        ).fetchall()
        assert [row["source_native_id"] for row in occurrences] == sorted(
            [
                _search_record(1)["source_occurrence_id"],
                _search_record(2)["source_occurrence_id"],
            ]
        )
        assert db.execute(
            "SELECT COUNT(*) FROM recorded_instrument WHERE source_id=?",
            (land.SOURCE_ID,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM instrument_party"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM ownership_assertion"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_detail_enriches_instrument_and_reconciles_duplicate_party_sequence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    parcel_id = _seed_parcel(
        db_path,
        "ASSESSOR-ROW-1",
        alias="1-935-23-055-0101",
    )
    search = ingest_property_envelope(_search_envelope(), db_path=db_path)
    first = ingest_property_envelope(_detail_envelope(), db_path=db_path)

    projection = first["records"][0]
    assert projection["instrument_id"] == search["records"][0]["instrument_id"]
    assert projection["parties_upserted"] == 4
    assert projection["parties_reconciled"] is True
    assert projection["parcel_links_upserted"] == 1
    assert projection["parcel_placeholders_created"] == 0
    assert projection["ownership_assertions_upserted"] == 0
    assert projection["artifacts_upserted"] == 1
    assert projection["digital_object_delivery_state"] == (
        "site_recaptcha_queue"
    )

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT instrument_id, native_document_id, jurisdiction_geoid,
                   instrument_type, recording_date, legal_description_raw,
                   raw_json
            FROM recorded_instrument
            WHERE source_id=?
            """,
            (land.SOURCE_ID,),
        ).fetchone()
        assert instrument["native_document_id"] == RECORD_ID
        assert instrument["jurisdiction_geoid"] == "53001"
        assert instrument["instrument_type"] == "Assignment Of Deed Of Trust"
        assert instrument["recording_date"] == "2020-06-19"
        assert json.loads(instrument["legal_description_raw"]) == (
            _detail_record()["legal"]
        )
        assert json.loads(instrument["raw_json"])["reference_number"] == "324744"

        parties = db.execute(
            """
            SELECT sequence_no, role, raw_name
            FROM instrument_party
            ORDER BY sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties][1:3] == [
            (2, "Borrower", "SMITH, AMOS"),
            (3, "Borrower", "SMITH, AMOS"),
        ]
        link = db.execute(
            """
            SELECT parcel_id, link_method, link_confidence, legal_description_raw
            FROM instrument_parcel
            """
        ).fetchone()
        assert link["parcel_id"] == parcel_id
        assert link["link_method"] == "exact_current_parcel_or_alias"
        assert link["link_confidence"] == 1.0
        assert json.loads(link["legal_description_raw"])["parcel"] == (
            ";1-935-23-055-0101;"
        )

        artifact = db.execute(
            """
            SELECT native_document_id, sha256, mime_type, page_count,
                   storage_path, source_url, acquisition_method, rights_tier,
                   acquired_at
            FROM document_artifact
            """
        ).fetchone()
        assert artifact["native_document_id"] == (
            "910A2CA838DCC45F1AC4363BBCF36D5B"
        )
        assert artifact["sha256"] is None
        assert artifact["mime_type"] == "application/pdf"
        assert artifact["page_count"] is None
        assert artifact["storage_path"] is None
        assert artifact["acquired_at"] is None
        assert artifact["acquisition_method"] == (
            "site_recaptcha_queue_metadata"
        )
        assert artifact["rights_tier"] == (
            "official_archive_image_uncertified"
        )
        assert artifact["source_url"].endswith(f"/Record/View/{RECORD_ID}")
    finally:
        db.close()

    replacement = _detail_record()
    duplicate = copy.deepcopy(replacement["parties"][1])
    duplicate["sequence_no"] = 1
    second_duplicate = copy.deepcopy(duplicate)
    second_duplicate["sequence_no"] = 2
    replacement["parties"] = [duplicate, second_duplicate]
    second = ingest_property_envelope(
        _detail_envelope(
            replacement,
            retrieved_at="2026-07-30T12:10:00Z",
        ),
        db_path=db_path,
    )
    assert second["records"][0]["parties_upserted"] == 2
    db = connect_property(db_path)
    try:
        parties = db.execute(
            """
            SELECT sequence_no, role, raw_name
            FROM instrument_party
            ORDER BY sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties] == [
            (1, "Borrower", "SMITH, AMOS"),
            (2, "Borrower", "SMITH, AMOS"),
        ]
    finally:
        db.close()


def test_detail_party_reconciliation_rolls_back_on_invalid_sequence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    ingest_property_envelope(_detail_envelope(), db_path=db_path)
    invalid = _detail_record()
    invalid["parties"][1]["sequence_no"] = 1

    with pytest.raises(PropertyIngestError, match="unique and positive"):
        ingest_property_envelope(
            _detail_envelope(invalid),
            db_path=db_path,
        )

    db = connect_property(db_path)
    try:
        assert db.execute(
            "SELECT COUNT(*) FROM instrument_party"
        ).fetchone()[0] == 4
        assert db.execute(
            """
            SELECT COUNT(*) FROM source_observation
            WHERE source_id=? AND record_kind='recorded_land_record'
            """,
            (land.SOURCE_ID,),
        ).fetchone()[0] == 1
    finally:
        db.close()


def test_parcel_candidate_uses_only_unique_current_normalized_match(
    tmp_path: Path,
) -> None:
    unique_db = tmp_path / "unique.db"
    parcel_id = _seed_parcel(unique_db, "1935230550101")
    unique = ingest_property_envelope(
        _detail_envelope(),
        db_path=unique_db,
    )
    assert unique["records"][0]["parcel_resolution_states"] == {
        "1-935-23-055-0101": "unique_normalized"
    }
    db = connect_property(unique_db)
    try:
        link = db.execute(
            "SELECT parcel_id, link_method FROM instrument_parcel"
        ).fetchone()
        assert tuple(link) == (
            parcel_id,
            "unique_punctuation_normalized_current_parcel_or_alias",
        )
    finally:
        db.close()

    empty_db = tmp_path / "empty.db"
    empty = ingest_property_envelope(
        _detail_envelope(),
        db_path=empty_db,
    )
    assert empty["records"][0]["parcel_links_upserted"] == 0
    db = connect_property(empty_db)
    try:
        assert db.execute(
            "SELECT COUNT(*) FROM parcel_snapshot"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM instrument_parcel"
        ).fetchone()[0] == 0
    finally:
        db.close()

    multiple_db = tmp_path / "multiple.db"
    _seed_parcel(multiple_db, "1935230550101")
    _seed_parcel(multiple_db, "1_935_23_055_0101")
    multiple = ingest_property_envelope(
        _detail_envelope(),
        db_path=multiple_db,
    )
    assert multiple["records"][0]["parcel_resolution_states"] == {
        "1-935-23-055-0101": "multiple_normalized"
    }
    db = connect_property(multiple_db)
    try:
        assert db.execute(
            "SELECT COUNT(*) FROM instrument_parcel"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM parcel_snapshot"
        ).fetchone()[0] == 2
    finally:
        db.close()
