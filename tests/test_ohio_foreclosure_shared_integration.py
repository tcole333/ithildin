from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import public_records_search_plan
from tools import query_licking_foreclosure_archive as archive
from tools import query_ohio_sheriff_sales as realauction
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult, canonical_json
from tools.public_records_monitor import (
    ProbeContext,
    compare_probes,
    probe_licking_foreclosure_archive,
    probe_ohio_sheriff_realauction_component,
)
from tools.public_records_store import (
    PROPERTY_SCHEMA,
    connect_property,
)
from tools.seed_public_records_catalog import seed_catalog


SOURCE_CONFIG = Path("config/public_records_sources.yaml")
CENSUS_CONFIG = Path("config/public_records_census.yaml")
CITATION_URLS = Path("web/src/data/source-urls.json")
LICKING_REALAUCTION = realauction.TENANTS["licking"].source_id
REALAUCTION_SOURCE_IDS = {
    tenant.source_id for tenant in realauction.TENANTS.values()
}
ALL_SOURCE_IDS = {
    *REALAUCTION_SOURCE_IDS,
    archive.SOURCE_ID,
}
REALAUCTION_SHARED_OPERATIONS = {
    "search",
    "address",
    "parcel",
    "sale",
    "event",
    "freshness",
    "discovery",
    "probe",
}
ARCHIVE_SHARED_OPERATIONS = {
    "search",
    "address",
    "parcel",
    "sale",
    "event",
    "releases",
    "discovery",
    "probe",
}


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _source_manifests() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(SOURCE_CONFIG.read_text(encoding="utf-8"))
    return {
        source["source_id"]: source
        for source in payload["sources"]
        if source["source_id"] in ALL_SOURCE_IDS
    }


def _realauction_record(
    native_id: str,
    *,
    case_number: str = "25CV01926",
    event_date: str = "2026-07-30",
    parcel: str = "034-105570-00.000",
) -> dict[str, Any]:
    return {
        "source_id": LICKING_REALAUCTION,
        "record_kind": "sheriff_sale_auction",
        "native_auction_id": native_id,
        "case_number": case_number,
        "auction_date": event_date,
        "parcel_ids": [parcel],
        "parcel_id_raw": parcel,
        "property_address": "100 TEST STREET",
        "city": "NEWARK",
        "postal_code": "43055",
        "auction_status": "sold",
        "appraised_value_amount": "125000.00",
        "opening_bid_amount": "83333.34",
        "deposit_requirement_amount": "5000.00",
        "sold_amount": "70680.00",
        "canonical_ref": (
            f"PROPERTY:{LICKING_REALAUCTION}/39089/"
            f"sheriff-sale-auction/{native_id}"
        ),
        "source_url": (
            "https://licking.sheriffsaleauction.ohio.gov/index.cfm"
        ),
    }


def _archive_record(
    *,
    parcel: str = "034-105570-00.000",
) -> dict[str, Any]:
    return {
        "source_id": archive.SOURCE_ID,
        "record_kind": "sheriff_foreclosure_archive_record",
        "native_case_number": "25CV01926",
        "case_number": "25CV01926",
        "sale_date": "2026-07-30",
        "parcel_ids": [parcel],
        "property_address": "100 TEST STREET",
        "city": "NEWARK",
        "postal_code": "43055",
        "status": "sold",
        "appraised_value_amount": "125000.00",
        "required_deposit_amount": "5000.00",
        "deed_as": "TEST PURCHASER LLC",
        "purchaser_contact_name": "TEST PURCHASER LLC",
        "purchase_price_amount": "70680.00",
        "canonical_ref": (
            f"PROPERTY:{archive.SOURCE_ID}/39089/"
            "foreclosure-case/25CV01926"
        ),
        "source_url": (
            "https://apps.lickingcounty.gov/sheriff/foreclosures/"
            "api/foreclosures/25CV01926"
        ),
    }


def _envelope(
    source_id: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    if source_id == archive.SOURCE_ID:
        query = archive._query(
            "case",
            parameters={"case_number": "25CV01926"},
        )
    else:
        tenant = realauction.TENANTS_BY_SOURCE_ID[source_id]
        query = realauction._query(
            tenant,
            "auctions",
            parameters={"auction_date": "2026-07-30"},
        )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _ingest(
    db_path: Path,
    source_id: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    return ingest_property_envelope(
        _envelope(source_id, [record]),
        db_path=db_path,
    )


def _candidate_identity_edges(db_path: Path) -> set[tuple[str, str, str, str]]:
    db = connect_property(db_path)
    try:
        rows = db.execute(
            """
            SELECT left_event.source_id AS left_source,
                   left_event.native_event_id AS left_native,
                   right_event.source_id AS right_source,
                   right_event.native_event_id AS right_native
            FROM property_event_relation relation
            JOIN property_event left_event
              ON left_event.event_id=relation.event_id
            JOIN property_event right_event
              ON right_event.event_id=relation.related_event_id
            WHERE relation.relationship='same_event_candidate'
            """
        ).fetchall()
        edges = set()
        for row in rows:
            left, right = sorted(
                (
                    (row["left_source"], row["left_native"]),
                    (row["right_source"], row["right_native"]),
                )
            )
            edges.add((*left, *right))
        return edges
    finally:
        db.close()


def test_shared_routes_and_translators_preserve_scope_and_caller_bounds() -> None:
    manifests = _source_manifests()
    for source_id in REALAUCTION_SOURCE_IDS:
        manifest = manifests[source_id]
        shared = next(
            capability
            for capability in manifest["capabilities"]
            if capability["name"] == "query_shared_property_records"
        )
        assert set(query_property.LIVE_ROUTES[source_id]) == (
            REALAUCTION_SHARED_OPERATIONS
        )
        assert set(shared["details"]["shared_operations"]) == (
            REALAUCTION_SHARED_OPERATIONS
        )

    archive_shared = next(
        capability
        for capability in manifests[archive.SOURCE_ID]["capabilities"]
        if capability["name"] == "query_shared_property_records"
    )
    assert set(query_property.LIVE_ROUTES[archive.SOURCE_ID]) == (
        ARCHIVE_SHARED_OPERATIONS
    )
    assert set(archive_shared["details"]["shared_operations"]) == (
        ARCHIVE_SHARED_OPERATIONS
    )

    unbounded = query_property._ohio_sheriff_realauction_args(
        _shared_args(
            "search",
            "25CV01926",
            "--source",
            LICKING_REALAUCTION,
            "--jurisdiction",
            "39089",
            "--from-date",
            "2026-07-30",
            "--to-date",
            "2026-07-30",
        ),
        "auctions",
    )
    bounded = query_property._ohio_sheriff_realauction_args(
        _shared_args(
            "parcel",
            "034-105570-00.000",
            "--source",
            LICKING_REALAUCTION,
            "--jurisdiction",
            "39089",
            "--from-date",
            "2026-07-30",
            "--limit",
            "2",
            "--cursor",
            "caller-cursor",
        ),
        "auctions",
    )
    exact_event = query_property._ohio_sheriff_realauction_args(
        _shared_args(
            "event",
            "9001",
            "--source",
            LICKING_REALAUCTION,
            "--jurisdiction",
            "39089",
            "--from-date",
            "2026-07-30",
        ),
        "auctions",
    )
    archive_unbounded = query_property._licking_foreclosure_archive_args(
        _shared_args(
            "search",
            "sold",
            "--search-field",
            "status",
            "--source",
            archive.SOURCE_ID,
            "--jurisdiction",
            "39089",
            "--tax-year",
            "2026",
        ),
        "year",
    )
    archive_bounded = query_property._licking_foreclosure_archive_args(
        _shared_args(
            "parcel",
            "034-105570-00.000",
            "--source",
            archive.SOURCE_ID,
            "--jurisdiction",
            "39089",
            "--tax-year",
            "2026",
            "--limit",
            "3",
            "--cursor",
            "archive-cursor",
        ),
        "year",
    )
    archive_event = query_property._licking_foreclosure_archive_args(
        _shared_args(
            "event",
            "25CV01926",
            "--source",
            archive.SOURCE_ID,
            "--jurisdiction",
            "39089",
        ),
        "case",
    )

    assert (unbounded.command, unbounded.date, unbounded.limit) == (
        "auctions",
        "2026-07-30",
        None,
    )
    assert unbounded.case_number == "25CV01926"
    assert (bounded.parcel, bounded.limit, bounded.cursor) == (
        "034-105570-00.000",
        2,
        "caller-cursor",
    )
    assert exact_event.auction_id == "9001"
    assert (archive_unbounded.year, archive_unbounded.limit) == (2026, None)
    assert archive_unbounded.status == "sold"
    assert (archive_bounded.limit, archive_bounded.cursor) == (
        3,
        "archive-cursor",
    )
    assert archive_event.case_number == "25CV01926"

    with pytest.raises(ValueError, match="serves county GEOID 39089"):
        query_property._ohio_sheriff_realauction_args(
            _shared_args(
                "search",
                "25CV01926",
                "--source",
                LICKING_REALAUCTION,
                "--jurisdiction",
                "39049",
                "--from-date",
                "2026-07-30",
            ),
            "auctions",
        )


def test_projection_is_neutral_and_metadata_is_observation_only(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    metadata_report = _ingest(
        db_path,
        LICKING_REALAUCTION,
        realauction._source_record(realauction.TENANTS["licking"]),
    )
    realauction_report = _ingest(
        db_path,
        LICKING_REALAUCTION,
        _realauction_record("9001"),
    )
    archive_report = _ingest(
        db_path,
        archive.SOURCE_ID,
        _archive_record(),
    )

    assert metadata_report["records_ingested"] == 0
    assert metadata_report["records_preserved_without_projection"] == 1
    for report in (realauction_report, archive_report):
        projection = report["records"][0]
        assert projection["sales_upserted"] == 0
        assert projection["ownership_assertions_upserted"] == 0
        assert projection["recorded_instruments_upserted"] == 0
        assert projection["title_transfer_assertions_upserted"] == 0

    db = connect_property(db_path)
    try:
        events = db.execute(
            """
            SELECT source_id, native_event_id, event_date,
                   normalized_case_number, raw_json
            FROM property_event
            ORDER BY source_id
            """
        ).fetchall()
        assertion_counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "sale_event",
                "ownership_assertion",
                "recorded_instrument",
            )
        }
        archive_party = db.execute(
            """
            SELECT role, assertion_type
            FROM property_event_party
            WHERE role='source_reported_deed_as'
            """
        ).fetchone()
    finally:
        db.close()

    assert len(events) == 2
    assert {
        (row["event_date"], row["normalized_case_number"])
        for row in events
    } == {("2026-07-30", "25CV01926")}
    assert assertion_counts == {
        "sale_event": 0,
        "ownership_assertion": 0,
        "recorded_instrument": 0,
    }
    assert archive_party["assertion_type"] == (
        "auction_outcome_observation_not_ownership"
    )
    raw_records = [json.loads(row["raw_json"]) for row in events]
    assert {
        raw["event_observation"]["purchase_price_amount"]
        for raw in raw_records
    } == {None, "70680.00"}
    assert {
        raw["event_observation"]["sold_amount"] for raw in raw_records
    } == {None, "70680.00"}


def test_exact_ogrip_link_requires_one_indexed_match(tmp_path: Path) -> None:
    db_path = tmp_path / "property.db"
    db = connect_property(db_path)
    try:
        with db:
            db.execute(
                """
                INSERT INTO jurisdiction(
                    geoid, name, jurisdiction_type, state_code
                ) VALUES ('39089', 'Licking County', 'county', 'OH')
                """
            )
            parcel_id = db.execute(
                """
                INSERT INTO parcel_snapshot(
                    source_id, jurisdiction_geoid, native_parcel_id
                ) VALUES (
                    'us-oh-ogrip-statewide-parcels',
                    '39089',
                    '39089-034-105570-00.000'
                )
                """
            ).lastrowid
            db.execute(
                """
                INSERT INTO parcel_alias(
                    parcel_id, alias_type, alias_value, source_id
                ) VALUES (
                    ?, 'local_parcel_id_normalized', '03410557000000',
                    'us-oh-ogrip-statewide-parcels'
                )
                """,
                (parcel_id,),
            )
    finally:
        db.close()

    unique = _ingest(
        db_path,
        LICKING_REALAUCTION,
        _realauction_record("9001"),
    )["records"][0]
    assert unique["parcel_id"] == parcel_id
    assert unique["parcel_link_method"] == (
        "exact_ogrip_local_parcel_normalized"
    )

    db = connect_property(db_path)
    try:
        with db:
            duplicate_id = db.execute(
                """
                INSERT INTO parcel_snapshot(
                    source_id, jurisdiction_geoid, native_parcel_id
                ) VALUES (
                    'us-oh-ogrip-statewide-parcels',
                    '39089',
                    'duplicate-native-id'
                )
                """
            ).lastrowid
            db.execute(
                """
                INSERT INTO parcel_alias(
                    parcel_id, alias_type, alias_value, source_id
                ) VALUES (
                    ?, 'local_parcel_id_normalized', '03410557000000',
                    'us-oh-ogrip-statewide-parcels'
                )
                """,
                (duplicate_id,),
            )
            plan = [
                row["detail"]
                for row in db.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT p.parcel_id
                    FROM parcel_alias a
                    JOIN parcel_snapshot p ON p.parcel_id=a.parcel_id
                    WHERE a.source_id='us-oh-ogrip-statewide-parcels'
                      AND a.alias_type='local_parcel_id_normalized'
                      AND a.alias_value='03410557000000'
                    """
                )
            ]
    finally:
        db.close()

    ambiguous = _ingest(
        db_path,
        LICKING_REALAUCTION,
        _realauction_record("9001"),
    )["records"][0]
    multiple = _ingest(
        db_path,
        LICKING_REALAUCTION,
        _realauction_record(
            "9002",
            parcel="034-105570-00.000, 054-100000-00.000",
        )
        | {
            "parcel_ids": [
                "034-105570-00.000",
                "054-100000-00.000",
            ]
        },
    )["records"][0]

    assert ambiguous["parcel_id"] is None
    assert ambiguous["parcel_link_method"] == (
        "ambiguous_ogrip_local_parcel_normalized"
    )
    assert multiple["parcel_id"] is None
    assert multiple["parcel_link_method"] == (
        "multiple_published_parcels_unresolved"
    )
    assert any(
        "idx_parcel_alias_source_type_value" in detail for detail in plan
    )
    assert not any(detail.startswith("SCAN a") for detail in plan)

    db = connect_property(db_path)
    try:
        multi_local_records = []
        for selector in (
            "034-105570-00.000",
            "054-100000-00.000",
        ):
            local_records, _cursor = query_property._local_event(
                db,
                selector,
                _shared_args(
                    "event",
                    selector,
                    "--source",
                    "local",
                    "--jurisdiction",
                    "39089",
                ),
            )
            multi_local_records.append(
                next(
                    record
                    for record in local_records
                    if record["native_event_id"] == "9002"
                )
            )
    finally:
        db.close()
    for multi_local in multi_local_records:
        assert multi_local["parcel_link"]["parcel_id"] is None
        assert multi_local["parcel_link"]["method"] == (
            "multiple_published_parcels_unresolved"
        )


def test_same_event_candidates_are_order_invariant_and_refresh_scoped(
    tmp_path: Path,
) -> None:
    first_db = tmp_path / "first.db"
    second_db = tmp_path / "second.db"
    sequences = (
        (
            first_db,
            [
                (archive.SOURCE_ID, _archive_record()),
                (LICKING_REALAUCTION, _realauction_record("X")),
                (LICKING_REALAUCTION, _realauction_record("Y")),
            ],
        ),
        (
            second_db,
            [
                (LICKING_REALAUCTION, _realauction_record("Y")),
                (LICKING_REALAUCTION, _realauction_record("X")),
                (archive.SOURCE_ID, _archive_record()),
            ],
        ),
    )
    final_reports = []
    for db_path, sequence in sequences:
        for source_id, record in sequence:
            final_reports.append(_ingest(db_path, source_id, record))

    first_edges = _candidate_identity_edges(first_db)
    second_edges = _candidate_identity_edges(second_db)
    assert first_edges == second_edges
    assert len(first_edges) == 2
    assert {
        frozenset(
            {
                (left_source, left_native),
                (right_source, right_native),
            }
        )
        for left_source, left_native, right_source, right_native in first_edges
    } == {
        frozenset(
            {
                (archive.SOURCE_ID, "25CV01926"),
                (LICKING_REALAUCTION, "X"),
            }
        ),
        frozenset(
            {
                (archive.SOURCE_ID, "25CV01926"),
                (LICKING_REALAUCTION, "Y"),
            }
        ),
    }
    assert final_reports[2]["records"][0]["same_event_relation_state"] == (
        "ambiguous_exact_cross_source_matches"
    )
    assert final_reports[-1]["records"][0]["same_event_relation_state"] == (
        "ambiguous_exact_cross_source_matches"
    )

    db = connect_property(first_db)
    try:
        relation_rows = db.execute(
            """
            SELECT relation_id, event_id, related_event_id,
                   independent_corroboration
            FROM property_event_relation
            WHERE relationship='same_event_candidate'
            ORDER BY relation_id
            """
        ).fetchall()
        assert {row["independent_corroboration"] for row in relation_rows} == {
            0
        }
        archive_event_id = db.execute(
            """
            SELECT event_id FROM property_event
            WHERE source_id=? AND native_event_id='25CV01926'
            """,
            (archive.SOURCE_ID,),
        ).fetchone()["event_id"]
        x_event_id = db.execute(
            """
            SELECT event_id FROM property_event
            WHERE source_id=? AND native_event_id='X'
            """,
            (LICKING_REALAUCTION,),
        ).fetchone()["event_id"]
        left_id, right_id = sorted((archive_event_id, x_event_id))
        with db:
            db.execute(
                """
                INSERT INTO property_event_relation(
                    event_id, related_event_id, relationship,
                    independent_corroboration, evidence_json
                ) VALUES (?, ?, 'manual_review_link', 0, ?)
                """,
                (
                    left_id,
                    right_id,
                    canonical_json({"origin": "test-manual-review"}),
                ),
            )

        local_args = _shared_args(
            "event",
            "25CV01926",
            "--source",
            "local",
            "--jurisdiction",
            "39089",
        )
        local_records, _cursor = query_property._local_event(
            db,
            "25CV01926",
            local_args,
        )
        archive_local = next(
            record
            for record in local_records
            if record["source_id"] == archive.SOURCE_ID
        )
        assert archive_local["event_date"] == "2026-07-30"
        assert archive_local["normalized_case_number"] == "25CV01926"
        assert archive_local["event_dates"]["event"] == "2026-07-30"
        assert {
            relation["relationship"]
            for relation in archive_local["relations"]
        } == {"same_event_candidate", "manual_review_link"}
    finally:
        db.close()

    refreshed = _ingest(
        first_db,
        archive.SOURCE_ID,
        _archive_record(parcel="999-999999-99.999"),
    )["records"][0]
    assert refreshed["same_event_relation_state"] == (
        "no_exact_cross_source_match"
    )
    assert refreshed["same_event_relation_ids"] == []
    db = connect_property(first_db)
    try:
        remaining = {
            row["relationship"]: (
                row["count"],
                row["normalized_case_number"],
                row["event_date"],
                row["overlapping_parcels_json"],
            )
            for row in db.execute(
                """
                SELECT relationship, COUNT(*) AS count,
                       normalized_case_number, event_date,
                       overlapping_parcels_json
                FROM property_event_relation
                GROUP BY relationship
                """
            )
        }
    finally:
        db.close()
    assert remaining == {"manual_review_link": (1, None, None, None)}


def test_property_schema_migration_retains_rows_and_adds_indexes(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy.db"
    legacy_schema = PROPERTY_SCHEMA.replace(
        "    event_date TEXT,\n    normalized_case_number TEXT,\n",
        "",
        1,
    )
    join_start = legacy_schema.index(
        "CREATE TABLE IF NOT EXISTS property_event_parcel_join_key ("
    )
    join_end = legacy_schema.index(
        "CREATE TABLE IF NOT EXISTS property_event_party ("
    )
    legacy_schema = legacy_schema[:join_start] + legacy_schema[join_end:]
    relation_start = legacy_schema.index(
        "CREATE TABLE IF NOT EXISTS property_event_relation ("
    )
    relation_end = legacy_schema.index(
        "CREATE TABLE IF NOT EXISTS recorded_instrument ("
    )
    legacy_schema = (
        legacy_schema[:relation_start] + legacy_schema[relation_end:]
    )
    legacy = sqlite3.connect(db_path)
    try:
        legacy.executescript(legacy_schema)
        legacy.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, state_code
            ) VALUES ('39089', 'Licking County', 'county', 'OH')
            """
        )
        legacy.execute(
            """
            INSERT INTO property_event(
                source_id, jurisdiction_geoid, native_event_id,
                source_record_id, record_kind
            ) VALUES (
                'legacy-source', '39089', 'legacy-event',
                'legacy-event', 'legacy-event'
            )
            """
        )
        legacy.commit()
    finally:
        legacy.close()

    migrated = connect_property(db_path)
    try:
        columns = {
            row["name"]
            for row in migrated.execute("PRAGMA table_info(property_event)")
        }
        tables = {
            row["name"]
            for row in migrated.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        indexes = {
            row["name"]
            for row in migrated.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        legacy_row = migrated.execute(
            """
            SELECT native_event_id, event_date, normalized_case_number
            FROM property_event
            WHERE source_id='legacy-source'
            """
        ).fetchone()
        join_plan = [
            row["detail"]
            for row in migrated.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT event_id
                FROM property_event
                WHERE source_id='legacy-source'
                  AND jurisdiction_geoid='39089'
                  AND normalized_case_number='25CV01926'
                  AND event_date='2026-07-30'
                """
            )
        ]
        reverse_plan = [
            row["detail"]
            for row in migrated.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT relation_id
                FROM property_event_relation
                WHERE related_event_id=7
                  AND relationship='same_event_candidate'
                """
            )
        ]
        violations = list(migrated.execute("PRAGMA foreign_key_check"))
    finally:
        migrated.close()

    assert {"event_date", "normalized_case_number"} <= columns
    assert {
        "property_event_parcel_join_key",
        "property_event_relation",
    } <= tables
    assert {
        "idx_property_event_join",
        "idx_property_event_relation_related",
    } <= indexes
    assert tuple(legacy_row) == ("legacy-event", None, None)
    assert any("idx_property_event_join" in detail for detail in join_plan)
    assert any(
        "idx_property_event_relation_related" in detail
        for detail in reverse_plan
    )
    assert violations == []


def test_property_relation_migration_relaxes_foreclosure_only_fields(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "strict-relation.db"
    strict_schema = PROPERTY_SCHEMA.replace(
        (
            "    normalized_case_number TEXT,\n"
            "    event_date TEXT,\n"
            "    overlapping_parcels_json TEXT,\n"
            "    evidence_json TEXT NOT NULL,\n"
        ),
        (
            "    normalized_case_number TEXT NOT NULL,\n"
            "    event_date TEXT NOT NULL,\n"
            "    overlapping_parcels_json TEXT NOT NULL,\n"
            "    evidence_json TEXT NOT NULL,\n"
        ),
        1,
    )
    strict = sqlite3.connect(db_path)
    try:
        strict.executescript(strict_schema)
        strict.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, state_code
            ) VALUES ('39089', 'Licking County', 'county', 'OH')
            """
        )
        event_ids = []
        for native_id in ("strict-left", "strict-right"):
            event_ids.append(
                strict.execute(
                    """
                    INSERT INTO property_event(
                        source_id, jurisdiction_geoid, native_event_id,
                        source_record_id, record_kind
                    ) VALUES (
                        'strict-source', '39089', ?, ?, 'strict-event'
                    )
                    """,
                    (native_id, native_id),
                ).lastrowid
            )
        strict.execute(
            """
            INSERT INTO property_event_relation(
                event_id, related_event_id, relationship,
                normalized_case_number, event_date,
                overlapping_parcels_json, evidence_json
            ) VALUES (?, ?, 'legacy-candidate', ?, ?, ?, ?)
            """,
            (
                *event_ids,
                "25CV01926",
                "2026-07-30",
                canonical_json(["03410557000000"]),
                canonical_json({"legacy": True}),
            ),
        )
        strict.commit()
    finally:
        strict.close()

    migrated = connect_property(db_path)
    try:
        relation_columns = {
            row["name"]: row["notnull"]
            for row in migrated.execute(
                "PRAGMA table_info(property_event_relation)"
            )
        }
        retained = migrated.execute(
            """
            SELECT relationship, normalized_case_number, event_date
            FROM property_event_relation
            """
        ).fetchone()
        with migrated:
            migrated.execute(
                """
                INSERT INTO property_event_relation(
                    event_id, related_event_id, relationship, evidence_json
                ) VALUES (?, ?, 'generic-link', ?)
                """,
                (*event_ids, canonical_json({"generic": True})),
            )
        violations = list(migrated.execute("PRAGMA foreign_key_check"))
    finally:
        migrated.close()

    assert {
        field_name: relation_columns[field_name]
        for field_name in (
            "normalized_case_number",
            "event_date",
            "overlapping_parcels_json",
        )
    } == {
        "normalized_case_number": 0,
        "event_date": 0,
        "overlapping_parcels_json": 0,
    }
    assert tuple(retained) == (
        "legacy-candidate",
        "25CV01926",
        "2026-07-30",
    )
    assert violations == []


class _FakeRealAuctionMonitorClient:
    def __init__(self, state: dict[str, Any], *, initial_count: int = 0):
        self.state = state
        self.request_count = initial_count
        self.closed = False

    def _tick(self) -> None:
        self.request_count += 1

    def bootstrap(self, _tenant: realauction.Tenant) -> None:
        self._tick()

    def calendar(
        self,
        _tenant: realauction.Tenant,
        _month: str,
    ) -> tuple[dict[str, Any], ...]:
        self._tick()
        return (
            {
                "auction_date": realauction.PROBE_SENTINEL_DATES["licking"],
                "active_count": self.state["calendar_active_count"],
                "scheduled_count": self.state["calendar_scheduled_count"],
                "source_url": "https://licking.example/calendar",
            },
        )

    def _request(
        self,
        _tenant: realauction.Tenant,
        _parameters: dict[str, Any],
    ) -> realauction.TextResponse:
        self._tick()
        return realauction.TextResponse(
            text=(
                "<html><div class='AuctionNav_Main'></div>"
                "<div id='BID_WINDOW_CONTAINER'></div></html>"
            ),
            url="https://licking.example/preview",
            headers={"Content-Type": "text/html"},
        )

    def _load_page(
        self,
        _tenant: realauction.Tenant,
        *,
        auction_date: str,
        area: str,
        page: int,
    ) -> realauction.ListingPage:
        self._tick()
        assert (area, page) == ("C", 1)
        return realauction.ListingPage(
            area=area,
            page=page,
            records=(
                {
                    "native_auction_id": "9001",
                    "native_area": "C",
                    "auction_date": auction_date,
                    "source_url": "https://licking.example/listing",
                    "appraised_value_amount": self.state["appraisal"],
                    "opening_bid_amount": self.state["opening_bid"],
                    "deposit_requirement_amount": self.state["deposit"],
                },
            ),
            auction_ids=("9001",),
            schema_fingerprint=realauction.LISTING_SCHEMA_FINGERPRINT,
        )

    def _update(
        self,
        _tenant: realauction.Tenant,
        _auction_ids: tuple[str, ...],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
        self._tick()
        return (
            {
                "9001": {
                    "source_status_label": "Auction Status",
                    "source_status_message": self.state["status"],
                    "sold_amount": self.state["sold_amount"],
                }
            },
            {"W": 0, "C": 1},
        )

    def close(self) -> None:
        self.closed = True


class _FakeArchiveMonitorClient:
    def __init__(self, state: dict[str, Any]):
        self.state = state
        self.request_count = 0
        self.closed = False

    def _tick(self) -> None:
        self.request_count += 1

    def years(self) -> archive.YearInventory:
        self._tick()
        years = tuple(self.state["years"])
        return archive.YearInventory(
            years=years,
            records=(),
            source_url="https://apps.lickingcounty.gov/years",
        )

    def year(
        self,
        _year: int,
        *,
        current_archive_year: int,
    ) -> tuple[dict[str, Any], ...]:
        self._tick()
        assert current_archive_year == max(self.state["years"])
        return (
            {
                "case_number": archive.PROBE_CASE_NUMBER,
                "source_url": "https://apps.lickingcounty.gov/full-year",
            },
        )

    def current(
        self,
        *,
        current_archive_year: int,
    ) -> tuple[dict[str, Any], ...]:
        self._tick()
        assert current_archive_year == max(self.state["years"])
        return (
            {
                "case_number": archive.PROBE_CASE_NUMBER,
                "status": self.state["status"],
                "appraised_value_amount": self.state["appraisal"],
                "required_deposit_amount": self.state["deposit"],
                "purchase_price_amount": self.state["purchase_price"],
                "source_url": "https://apps.lickingcounty.gov/current",
            },
        )

    def case(
        self,
        _case_number: str,
        *,
        current_archive_year: int,
    ) -> tuple[dict[str, Any], ...]:
        self._tick()
        assert current_archive_year == max(self.state["years"])
        return (
            {
                "case_number": archive.PROBE_CASE_NUMBER,
                "status": self.state["status"],
                "sale_date": self.state["sale_date"],
                "appraised_value_amount": self.state["appraisal"],
                "required_deposit_amount": self.state["deposit"],
                "purchase_price_amount": self.state["purchase_price"],
                "source_url": "https://apps.lickingcounty.gov/exact-case",
            },
        )

    def close(self) -> None:
        self.closed = True


def _monitor_context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_monitor_budgets_close_clients_and_separate_stable_from_rolling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    realauction_state = {
        "calendar_active_count": 1,
        "calendar_scheduled_count": 1,
        "status": "Sold",
        "appraisal": "125000.00",
        "opening_bid": "83333.34",
        "deposit": "5000.00",
        "sold_amount": "70680.00",
    }
    realauction_client = _FakeRealAuctionMonitorClient(realauction_state)
    first = probe_ohio_sheriff_realauction_component(
        _monitor_context(LICKING_REALAUCTION),
        client=realauction_client,
    )
    assert realauction_client.request_count == 5
    assert realauction_client.closed is True

    monkeypatch.setattr(realauction, "OBSERVED_AT", "2030-01-01")
    realauction_state.update(
        calendar_active_count=9,
        calendar_scheduled_count=12,
        status="Canceled",
        appraisal="999999.00",
        opening_bid="1.00",
        deposit="2.00",
        sold_amount="3.00",
    )
    rolling_client = _FakeRealAuctionMonitorClient(realauction_state)
    rolling = probe_ohio_sheriff_realauction_component(
        _monitor_context(LICKING_REALAUCTION),
        client=rolling_client,
    )
    assert rolling.artifact_sha256 == first.artifact_sha256
    assert rolling.schema_sha256 == first.schema_sha256
    assert compare_probes(first.to_dict(), rolling.to_dict())[
        "drift_detected"
    ] is False

    original_realauction_source = realauction._source_record

    def changed_realauction_source(
        tenant: realauction.Tenant,
    ) -> dict[str, Any]:
        payload = deepcopy(original_realauction_source(tenant))
        payload["endpoints"]["calendar"] += "&contract=v2"
        return payload

    monkeypatch.setattr(
        realauction,
        "_source_record",
        changed_realauction_source,
    )
    changed = probe_ohio_sheriff_realauction_component(
        _monitor_context(LICKING_REALAUCTION),
        client=_FakeRealAuctionMonitorClient(realauction_state),
    )
    assert changed.artifact_sha256 != rolling.artifact_sha256
    assert compare_probes(rolling.to_dict(), changed.to_dict())[
        "drift_detected"
    ] is True

    over_budget = _FakeRealAuctionMonitorClient(
        realauction_state,
        initial_count=1,
    )
    with pytest.raises(ValueError, match="expected 5, observed 6"):
        probe_ohio_sheriff_realauction_component(
            _monitor_context(LICKING_REALAUCTION),
            client=over_budget,
        )
    assert over_budget.closed is True

    archive_state = {
        "years": [2026, 2025, 2000],
        "status": "sold",
        "sale_date": "2026-07-30",
        "appraisal": "125000.00",
        "deposit": "5000.00",
        "purchase_price": "70680.00",
    }
    archive_client = _FakeArchiveMonitorClient(archive_state)
    archive_first = probe_licking_foreclosure_archive(
        _monitor_context(archive.SOURCE_ID),
        client=archive_client,
    )
    assert archive_client.request_count == 4
    assert archive_client.closed is True

    monkeypatch.setattr(archive, "OBSERVED_AT", "2030-01-01")
    archive_state.update(
        years=[2027, 2026, 2025, 2000],
        status="corrected",
        sale_date="2027-01-01",
        appraisal="999999.00",
        deposit="1.00",
        purchase_price="2.00",
    )
    archive_rolling = probe_licking_foreclosure_archive(
        _monitor_context(archive.SOURCE_ID),
        client=_FakeArchiveMonitorClient(archive_state),
    )
    assert archive_rolling.artifact_sha256 == archive_first.artifact_sha256
    assert archive_rolling.schema_sha256 == archive_first.schema_sha256
    assert compare_probes(
        archive_first.to_dict(),
        archive_rolling.to_dict(),
    )["drift_detected"] is False

    original_archive_source = archive._source_record

    def changed_archive_source() -> dict[str, Any]:
        payload = deepcopy(original_archive_source())
        payload["native_identity"]["key"] = "future-native-key"
        return payload

    monkeypatch.setattr(archive, "_source_record", changed_archive_source)
    archive_changed = probe_licking_foreclosure_archive(
        _monitor_context(archive.SOURCE_ID),
        client=_FakeArchiveMonitorClient(archive_state),
    )
    assert archive_changed.artifact_sha256 != (
        archive_rolling.artifact_sha256
    )
    assert compare_probes(
        archive_rolling.to_dict(),
        archive_changed.to_dict(),
    )["drift_detected"] is True

    for source_id in REALAUCTION_SOURCE_IDS:
        handler = public_records_monitor.HANDLER_REGISTRY[source_id]
        assert handler.expected_requests == 5
        assert handler.handler is (
            probe_ohio_sheriff_realauction_component
        )
    archive_handler = public_records_monitor.HANDLER_REGISTRY[
        archive.SOURCE_ID
    ]
    assert archive_handler.expected_requests == 4
    assert archive_handler.handler is probe_licking_foreclosure_archive


def test_catalog_census_citations_and_search_plan_are_complete(
    tmp_path: Path,
) -> None:
    manifests = _source_manifests()
    census = yaml.safe_load(CENSUS_CONFIG.read_text(encoding="utf-8"))
    targets = {
        (row["jurisdiction_geoid"], row["domain"], row["role"])
        for row in census["additional_targets"]
    }
    citations = json.loads(CITATION_URLS.read_text(encoding="utf-8"))

    assert set(manifests) == ALL_SOURCE_IDS
    assert {
        "sheriff_sale_auction_records",
        "sheriff_foreclosure_archive_and_sale_outcomes",
    } <= set(census["roles"]["property"])
    for geoid in ("39049", "39041", "39089"):
        assert (
            geoid,
            "property",
            "sheriff_sale_auction_records",
        ) in targets
    assert (
        "39089",
        "property",
        "sheriff_foreclosure_archive_and_sale_outcomes",
    ) in targets
    for source_id in ALL_SOURCE_IDS:
        assert f"PROPERTY_SOURCE:{source_id}" in citations

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = public_records_search_plan.build_search_plan(
        "TEST PURCHASER LLC",
        jurisdictions=("39049", "39041", "39089"),
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
        profiles_dir=tmp_path / "profiles",
    )
    task_ids = {
        task["task_id"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] in ALL_SOURCE_IDS
    }
    assert {
        "property.us-oh-franklin-sheriff-realauction.search_sales",
        "property.us-oh-franklin-sheriff-realauction.fetch_auction_event",
        "property.us-oh-delaware-sheriff-realauction.search_sales",
        "property.us-oh-delaware-sheriff-realauction.fetch_auction_event",
        "property.us-oh-licking-sheriff-realauction.search_sales",
        "property.us-oh-licking-sheriff-realauction.fetch_auction_event",
        (
            "property.us-oh-licking-sheriff-foreclosure-archive."
            "search_sales"
        ),
        (
            "property.us-oh-licking-sheriff-foreclosure-archive."
            "fetch_foreclosure_case"
        ),
        (
            "property.us-oh-licking-sheriff-foreclosure-archive."
            "list_releases"
        ),
    } <= task_ids
