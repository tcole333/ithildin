from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import query_palm_beach_official_records as recorder
from tools import query_palm_beach_property_appraiser as papa
from tools import query_palm_beach_tax_collector as tax
from tools import query_palm_beach_tax_deeds as tax_deeds
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


def _papa_envelope() -> dict[str, Any]:
    metadata = json.loads(
        (FIXTURE_DIR / "metadata.json").read_text(encoding="utf-8")
    )
    features = json.loads(
        (FIXTURE_DIR / "features.json").read_text(encoding="utf-8")
    )
    record = papa.normalize_feature(
        features[0],
        contract=papa.metadata_contract(metadata),
        geometry_requested=True,
    )
    query = PublicRecordsQuery(
        source=papa.SOURCE_METADATA,
        jurisdiction=papa.JURISDICTION,
        query=QueryMetadata(
            operation="test_cross_source_shell_reconciliation",
            parameters={"pcn": tax.SENTINEL_PCN},
        ),
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:30:00Z",
    ).to_dict()


def _source_observation(db, source_id: str, record_kind: str) -> int:
    cursor = db.execute(
        """
        INSERT INTO source_observation(
            source_id, source_native_id, record_kind, retrieved_at,
            access_status, raw_json, warning_json
        ) VALUES (?, ?, ?, '2026-07-30T12:00:00Z', 'ok', '{}', '[]')
        """,
        (source_id, f"{source_id}:legacy-shell", record_kind),
    )
    return int(cursor.lastrowid)


def _parcel_shell(db, source_id: str, observation_id: int) -> int:
    cursor = db.execute(
        """
        INSERT INTO parcel_snapshot(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year,
            effective_from, observation_id, raw_json
        ) VALUES (?, '12099', ?, '', '2026-07-30T12:00:00Z', ?, '{}')
        """,
        (source_id, tax.SENTINEL_PCN, observation_id),
    )
    return int(cursor.lastrowid)


def _seed_legacy_cross_source_shells(db_path: Path) -> dict[str, int]:
    db = connect_property(db_path)
    try:
        db.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, state_code
            ) VALUES ('12099', 'Palm Beach County, Florida', 'county', 'FL')
            """
        )
        observations = {
            tax.SOURCE_ID: _source_observation(
                db,
                tax.SOURCE_ID,
                "property_tax_account_snapshot",
            ),
            tax_deeds.SOURCE_ID: _source_observation(
                db,
                tax_deeds.SOURCE_ID,
                "tax_deed_case_occurrence",
            ),
            recorder.SOURCE_ID: _source_observation(
                db,
                recorder.SOURCE_ID,
                "recorded_instrument",
            ),
        }
        shells = {
            source_id: _parcel_shell(db, source_id, observation_id)
            for source_id, observation_id in observations.items()
        }

        for source_id, alias_value in (
            (tax.SOURCE_ID, "1081671"),
            (tax_deeds.SOURCE_ID, "04-36-43-25-00-000-5040"),
            (recorder.SOURCE_ID, "04364325000005040"),
        ):
            db.execute(
                """
                INSERT INTO parcel_alias(
                    parcel_id, alias_type, alias_value, source_id,
                    effective_from
                ) VALUES (?, 'palm_beach_source_identifier', ?, ?, '')
                """,
                (shells[source_id], alias_value, source_id),
            )

        db.execute(
            """
            INSERT INTO ownership_assertion(
                parcel_id, source_id, assertion_type, raw_owner_name,
                normalized_owner_name, effective_from, confidence,
                claim_type, observation_id, evidence_ref
            ) VALUES (?, ?, 'tax_account', 'TAX ACCOUNT OWNER',
                      'TAX ACCOUNT OWNER', '', 'high', 'paraphrase', ?,
                      'legacy-tax-account')
            """,
            (
                shells[tax.SOURCE_ID],
                tax.SOURCE_ID,
                observations[tax.SOURCE_ID],
            ),
        )
        db.execute(
            """
            INSERT INTO tax_account_event(
                parcel_id, source_id, tax_year, event_type, event_date,
                amount_minor, status, native_event_id, observation_id,
                raw_json
            ) VALUES (?, ?, '2024', 'tax_account_snapshot', NULL,
                      125000, 'source_observed_account_snapshot',
                      'legacy-tax-account', ?, '{}')
            """,
            (
                shells[tax.SOURCE_ID],
                tax.SOURCE_ID,
                observations[tax.SOURCE_ID],
            ),
        )

        event = db.execute(
            """
            INSERT INTO property_event(
                source_id, jurisdiction_geoid, native_event_id,
                source_record_id, record_kind, event_type,
                map_taxlot_candidate, observation_id, raw_json
            ) VALUES (?, '12099', 'legacy-tax-deed', 'legacy-tax-deed',
                      'tax_deed_case_occurrence', 'tax_deed_case',
                      ?, ?, '{}')
            """,
            (
                tax_deeds.SOURCE_ID,
                tax.SENTINEL_PCN,
                observations[tax_deeds.SOURCE_ID],
            ),
        )
        db.execute(
            """
            INSERT INTO property_event_parcel_link(
                event_id, parcel_id, map_taxlot_candidate, link_method,
                link_confidence
            ) VALUES (?, ?, ?, 'exact_source_pcn_candidate', 1.0)
            """,
            (
                int(event.lastrowid),
                shells[tax_deeds.SOURCE_ID],
                tax.SENTINEL_PCN,
            ),
        )
        db.execute(
            """
            INSERT INTO tax_account_event(
                parcel_id, source_id, tax_year, event_type, event_date,
                status, native_event_id, observation_id, raw_json
            ) VALUES (?, ?, '', 'tax_deed_case_status', '2023-10-18',
                      'LANDS AVAILABLE', 'legacy-tax-deed', ?, '{}')
            """,
            (
                shells[tax_deeds.SOURCE_ID],
                tax_deeds.SOURCE_ID,
                observations[tax_deeds.SOURCE_ID],
            ),
        )

        instrument = db.execute(
            """
            INSERT INTO recorded_instrument(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_type, recording_date, observation_id, raw_json
            ) VALUES (?, '12099', 'legacy-instrument', 'DEED',
                      '1986-09-30', ?, '{}')
            """,
            (recorder.SOURCE_ID, observations[recorder.SOURCE_ID]),
        )
        instrument_id = int(instrument.lastrowid)
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence
            ) VALUES (?, ?, 'exact_source_index_pcn', 1.0)
            """,
            (instrument_id, shells[recorder.SOURCE_ID]),
        )
        db.execute(
            """
            INSERT INTO sale_event(
                parcel_id, source_id, native_sale_id, sale_date,
                recording_date, derivation, instrument_id,
                observation_id, raw_json
            ) VALUES (?, ?, 'legacy-instrument', '1986-09-30',
                      '1986-09-30', 'recorded_instrument_index', ?, ?, '{}')
            """,
            (
                shells[recorder.SOURCE_ID],
                recorder.SOURCE_ID,
                instrument_id,
                observations[recorder.SOURCE_ID],
            ),
        )
        db.commit()
        return shells
    finally:
        db.close()


def _child_counts(db) -> dict[str, int]:
    tables = (
        "parcel_alias",
        "ownership_assertion",
        "tax_account_event",
        "property_event_parcel_link",
        "recorded_instrument",
        "instrument_parcel",
        "sale_event",
    )
    return {
        table: int(
            db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        )
        for table in tables
    }


def test_all_exact_palm_beach_shells_converge_and_reconcile_idempotently(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    shells = _seed_legacy_cross_source_shells(db_path)
    canonical_parcel_id = shells[tax.SOURCE_ID]
    envelope = _papa_envelope()

    first = ingest_property_envelope(envelope, db_path=db_path)
    projection = first["records"][0]
    assert projection["parcel_id"] == canonical_parcel_id
    assert projection["parcel_shells_adopted"] == 3
    assert projection["parcel_shells_repointed"] == 2
    assert projection["parcel_shell_source_ids_adopted"] == sorted(
        [tax.SOURCE_ID, tax_deeds.SOURCE_ID, recorder.SOURCE_ID]
    )

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, source_id
            FROM parcel_snapshot
            WHERE native_parcel_id=?
            """,
            (tax.SENTINEL_PCN,),
        ).fetchall()
        assert [tuple(row) for row in parcels] == [
            (canonical_parcel_id, papa.SOURCE_ID)
        ]

        aliases = db.execute(
            """
            SELECT DISTINCT parcel_id, source_id
            FROM parcel_alias
            WHERE source_id IN (?, ?, ?)
            ORDER BY source_id
            """,
            (tax.SOURCE_ID, tax_deeds.SOURCE_ID, recorder.SOURCE_ID),
        ).fetchall()
        assert {int(row["parcel_id"]) for row in aliases} == {
            canonical_parcel_id
        }
        assert {row["source_id"] for row in aliases} == {
            tax.SOURCE_ID,
            tax_deeds.SOURCE_ID,
            recorder.SOURCE_ID,
        }

        ownership = db.execute(
            """
            SELECT parcel_id, source_id
            FROM ownership_assertion
            WHERE raw_owner_name='TAX ACCOUNT OWNER'
            """
        ).fetchone()
        assert tuple(ownership) == (
            canonical_parcel_id,
            tax.SOURCE_ID,
        )

        tax_events = db.execute(
            """
            SELECT parcel_id, source_id
            FROM tax_account_event
            WHERE source_id IN (?, ?)
            ORDER BY source_id
            """,
            (tax.SOURCE_ID, tax_deeds.SOURCE_ID),
        ).fetchall()
        assert {int(row["parcel_id"]) for row in tax_events} == {
            canonical_parcel_id
        }
        assert {row["source_id"] for row in tax_events} == {
            tax.SOURCE_ID,
            tax_deeds.SOURCE_ID,
        }

        event_link = db.execute(
            """
            SELECT pe.source_id, pepl.parcel_id, pepl.link_method
            FROM property_event pe
            JOIN property_event_parcel_link pepl USING(event_id)
            WHERE pe.source_id=?
            """,
            (tax_deeds.SOURCE_ID,),
        ).fetchone()
        assert tuple(event_link) == (
            tax_deeds.SOURCE_ID,
            canonical_parcel_id,
            "exact_papa_pcn_after_cross_source_shell",
        )

        instrument_link = db.execute(
            """
            SELECT ri.source_id, ip.parcel_id
            FROM recorded_instrument ri
            JOIN instrument_parcel ip USING(instrument_id)
            WHERE ri.source_id=?
            """,
            (recorder.SOURCE_ID,),
        ).fetchone()
        assert tuple(instrument_link) == (
            recorder.SOURCE_ID,
            canonical_parcel_id,
        )
        recorder_sale = db.execute(
            """
            SELECT parcel_id, source_id
            FROM sale_event
            WHERE source_id=?
            """,
            (recorder.SOURCE_ID,),
        ).fetchone()
        assert tuple(recorder_sale) == (
            canonical_parcel_id,
            recorder.SOURCE_ID,
        )
        before_rerun = _child_counts(db)
    finally:
        db.close()

    second = ingest_property_envelope(envelope, db_path=db_path)
    assert second["records"][0]["parcel_id"] == canonical_parcel_id
    assert second["records"][0]["parcel_shells_adopted"] == 0
    assert second["records"][0]["parcel_shells_repointed"] == 0

    db = connect_property(db_path)
    try:
        assert _child_counts(db) == before_rerun
        observation_sources = {
            row["source_id"]
            for row in db.execute(
                """
                SELECT DISTINCT source_id
                FROM source_observation
                WHERE source_id IN (?, ?, ?)
                """,
                (tax.SOURCE_ID, tax_deeds.SOURCE_ID, recorder.SOURCE_ID),
            )
        }
        assert observation_sources == {
            tax.SOURCE_ID,
            tax_deeds.SOURCE_ID,
            recorder.SOURCE_ID,
        }
    finally:
        db.close()
