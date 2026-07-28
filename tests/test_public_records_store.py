import sqlite3

import pytest

from tools.public_records_store import (
    COURT_SCHEMA,
    SCHEMA_VERSION,
    apply_case_restriction,
    canonical_court_ref,
    canonical_property_ref,
    connect_courts,
    connect_property,
    stats,
)


def _seed_court_case(db):
    db.execute(
        """
        INSERT INTO court(
            court_id, source_id, native_court_id, name, state_code
        ) VALUES ('wi-dane-circuit', 'us-wi-wcca', '13', 'Dane County Circuit Court', 'WI')
        """
    )
    case_id = db.execute(
        """
        INSERT INTO case_record(
            source_id, court_id, raw_case_number, display_case_number, caption
        ) VALUES ('us-wi-wcca', 'wi-dane-circuit', '2025CV000001', '2025CV1', 'A v. B')
        """
    ).lastrowid
    party_id = db.execute(
        """
        INSERT INTO case_party(case_id, role, raw_name)
        VALUES (?, 'plaintiff', 'A')
        """,
        (case_id,),
    ).lastrowid
    docket_id = db.execute(
        """
        INSERT INTO docket_entry(
            case_id, source_id, native_entry_id, sequence_no, raw_text, document_available
        ) VALUES (?, 'us-wi-wcca', 'entry-1', '1', 'Complaint filed', 1)
        """,
        (case_id,),
    ).lastrowid
    db.execute(
        """
        INSERT INTO document_artifact(
            case_id, docket_entry_id, source_id, native_document_id, sha256
        ) VALUES (?, ?, 'us-wi-wcca', 'doc-1', 'abc')
        """,
        (case_id, docket_id),
    )
    db.commit()
    return case_id, party_id, docket_id


def test_sidecars_initialize_complete_schema(tmp_path):
    property_path = tmp_path / "property.db"
    court_path = tmp_path / "courts.db"

    property_db = connect_property(property_path)
    court_db = connect_courts(court_path)
    try:
        property_tables = {
            row[0]
            for row in property_db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        court_tables = {
            row[0]
            for row in court_db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "parcel_snapshot",
            "assessment",
            "recorded_instrument",
            "instrument_party",
            "ownership_assertion",
            "document_artifact",
            "source_observation",
        } <= property_tables
        assert {
            "court",
            "case_record",
            "case_party",
            "docket_entry",
            "case_event",
            "document_artifact",
            "restriction_event",
            "source_snapshot",
        } <= court_tables
        assert property_db.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0] == str(SCHEMA_VERSION)
        assert court_db.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0] == str(SCHEMA_VERSION)
    finally:
        property_db.close()
        court_db.close()


def test_parcel_identity_is_scoped_by_source_jurisdiction_and_roll(tmp_path):
    db = connect_property(tmp_path / "property.db")
    try:
        db.execute(
            """
            INSERT INTO jurisdiction(geoid, name, jurisdiction_type, state_code)
            VALUES ('25025', 'Suffolk County', 'county', 'MA')
            """
        )
        for roll_year in ("2025", "2026"):
            db.execute(
                """
                INSERT INTO parcel_snapshot(
                    source_id, jurisdiction_geoid, native_parcel_id, roll_year
                ) VALUES ('us-ma-massgis', '25025', '12-34', ?)
                """,
                (roll_year,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """
                INSERT INTO parcel_snapshot(
                    source_id, jurisdiction_geoid, native_parcel_id, roll_year
                ) VALUES ('us-ma-massgis', '25025', '12-34', '2026')
                """
            )
    finally:
        db.close()


def test_property_dates_and_owner_assertion_semantics_remain_distinct(tmp_path):
    db = connect_property(tmp_path / "property.db")
    try:
        db.execute(
            """
            INSERT INTO jurisdiction(geoid, name, jurisdiction_type, state_code)
            VALUES ('36061', 'New York County', 'county', 'NY')
            """
        )
        parcel_id = db.execute(
            """
            INSERT INTO parcel_snapshot(
                source_id, jurisdiction_geoid, native_parcel_id, roll_year
            ) VALUES ('us-nyc-acris', '36061', '1-01386-0010', '2026')
            """
        ).lastrowid
        instrument_id = db.execute(
            """
            INSERT INTO recorded_instrument(
                source_id, jurisdiction_geoid, native_document_id,
                execution_date, recording_date, consideration_minor
            ) VALUES (
                'us-nyc-acris', '36061', '2026000000001',
                '2026-01-03', '2026-01-09', 125000000
            )
            """
        ).lastrowid
        db.execute(
            """
            INSERT INTO sale_event(
                parcel_id, source_id, native_sale_id, sale_date, execution_date,
                recording_date, consideration_minor, derivation, instrument_id
            ) VALUES (
                ?, 'us-nyc-acris', '2026000000001', '2026-01-03', '2026-01-03',
                '2026-01-09', 125000000, 'recorded_instrument', ?
            )
            """,
            (parcel_id, instrument_id),
        )
        db.execute(
            """
            INSERT INTO ownership_assertion(
                parcel_id, source_id, assertion_type, raw_owner_name,
                effective_from, confidence, claim_type
            ) VALUES (
                ?, 'us-nyc-acris', 'recorded_instrument', 'BUYER LLC',
                '2026-01-03', 'high', 'paraphrase'
            )
            """,
            (parcel_id,),
        )
        row = db.execute(
            """
            SELECT sale_date, execution_date, recording_date
            FROM sale_event
            """
        ).fetchone()
        assert tuple(row) == ("2026-01-03", "2026-01-03", "2026-01-09")

        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """
                INSERT INTO ownership_assertion(
                    parcel_id, source_id, assertion_type, raw_owner_name,
                    effective_from, confidence, claim_type
                ) VALUES (
                    ?, 'derived', 'derived_chain', 'BENEFICIAL OWNER',
                    '2026-01-03', 'confirmed', 'synthesis'
                )
                """,
                (parcel_id,),
            )
    finally:
        db.close()


def test_court_case_identity_is_source_and_court_scoped(tmp_path):
    db = connect_courts(tmp_path / "courts.db")
    try:
        _seed_court_case(db)
        db.execute(
            """
            INSERT INTO court(
                court_id, source_id, native_court_id, name, state_code
            ) VALUES ('wi-milwaukee-circuit', 'us-wi-wcca', '40', 'Milwaukee Circuit', 'WI')
            """
        )
        db.execute(
            """
            INSERT INTO case_record(
                source_id, court_id, raw_case_number, caption
            ) VALUES ('us-wi-wcca', 'wi-milwaukee-circuit', '2025CV000001', 'C v. D')
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """
                INSERT INTO case_record(
                    source_id, court_id, raw_case_number, caption
                ) VALUES ('us-wi-wcca', 'wi-dane-circuit', '2025CV000001', 'duplicate')
                """
            )
    finally:
        db.close()


def test_restriction_event_propagates_and_restoration_retains_audit(tmp_path):
    db = connect_courts(tmp_path / "courts.db")
    try:
        case_id, _, _ = _seed_court_case(db)
        event_id = apply_case_restriction(
            db,
            source_id="us-wi-wcca",
            court_id="wi-dane-circuit",
            case_number="2025CV000001",
            event_type="sealed",
            effective_at="2026-07-01",
            reason="court direction",
            direction_ref="WI:ORDER:1",
        )
        assert event_id > 0
        for table in ("case_record", "case_party", "docket_entry", "document_artifact"):
            states = {
                row[0]
                for row in db.execute(
                    f"SELECT access_state FROM {table} WHERE case_id = ?",
                    (case_id,),
                )
            }
            assert states == {"sealed"}

        apply_case_restriction(
            db,
            source_id="us-wi-wcca",
            court_id="wi-dane-circuit",
            case_number="2025CV000001",
            event_type="restored",
            effective_at="2026-07-15",
        )
        assert db.execute(
            "SELECT access_state FROM case_record WHERE case_id = ?",
            (case_id,),
        ).fetchone()[0] == "public"
        assert db.execute(
            "SELECT COUNT(*) FROM restriction_event WHERE case_id = ?",
            (case_id,),
        ).fetchone()[0] == 2
    finally:
        db.close()


def test_source_native_restriction_labels_propagate_canonical_serving_state(tmp_path):
    db = connect_courts(tmp_path / "courts.db")
    try:
        case_id, _, _ = _seed_court_case(db)
        apply_case_restriction(
            db,
            source_id="us-wi-wcca",
            court_id="wi-dane-circuit",
            case_number="2025CV000001",
            event_type="made nonpublic",
            effective_at="2026-07-01",
        )
        event = db.execute(
            "SELECT event_type, native_event_type FROM restriction_event"
        ).fetchone()
        assert tuple(event) == ("restricted", "made nonpublic")
        for table in (
            "case_record",
            "case_party",
            "docket_entry",
            "document_artifact",
        ):
            state = db.execute(
                f"""
                SELECT access_state, native_access_state
                FROM {table} WHERE case_id=?
                """,
                (case_id,),
            ).fetchone()
            assert tuple(state) == ("restricted", "made nonpublic")

        apply_case_restriction(
            db,
            source_id="us-wi-wcca",
            court_id="wi-dane-circuit",
            case_number="2025CV000001",
            event_type="local retention code 9",
            effective_at="2026-07-02",
        )
        assert tuple(
            db.execute(
                """
                SELECT access_state, native_access_state
                FROM case_record WHERE case_id=?
                """,
                (case_id,),
            ).fetchone()
        ) == ("unknown", "local retention code 9")
        assert tuple(
            db.execute(
                """
                SELECT event_type, native_event_type
                FROM restriction_event ORDER BY restriction_event_id DESC
                LIMIT 1
                """
            ).fetchone()
        ) == ("other", "local retention code 9")
    finally:
        db.close()


def test_v1_court_sidecar_migrates_native_labels_and_open_categories(tmp_path):
    court_path = tmp_path / "legacy-courts.db"
    legacy_schema = (
        COURT_SCHEMA.replace("    native_access_state TEXT,\n", "")
        .replace("    native_assertion_kind TEXT,\n", "")
        .replace("    native_event_type TEXT NOT NULL DEFAULT '',\n", "")
        .replace("'judgment', 'other'", "'judgment'")
        .replace("'restored',\n        'other'", "'restored'")
    )
    assert "native_access_state" not in legacy_schema
    assert "native_assertion_kind" not in legacy_schema
    assert "native_event_type" not in legacy_schema

    legacy_db = sqlite3.connect(court_path)
    legacy_db.row_factory = sqlite3.Row
    legacy_db.execute("PRAGMA foreign_keys=ON")
    legacy_db.executescript(legacy_schema)
    legacy_db.execute(
        "INSERT INTO schema_meta(key, value) VALUES ('schema_version', '1')"
    )
    case_id, _, docket_id = _seed_court_case(legacy_db)
    legacy_db.execute(
        """
        INSERT INTO case_event(
            case_id, source_id, native_event_id, event_type, event_date,
            assertion_kind, source_entry_id
        ) VALUES (?, 'us-wi-wcca', 'event-1', 'filing', '2025-01-01',
                  'docket_metadata', ?)
        """,
        (case_id, docket_id),
    )
    document_id = legacy_db.execute(
        "SELECT document_id FROM document_artifact"
    ).fetchone()[0]
    legacy_db.execute(
        """
        INSERT INTO evidence_representation(
            document_id, representation_type, assertion_kind
        ) VALUES (?, 'metadata', 'court_finding')
        """,
        (document_id,),
    )
    legacy_db.execute(
        """
        INSERT INTO restriction_event(
            case_id, source_id, event_type, effective_at
        ) VALUES (?, 'us-wi-wcca', 'sealed', '2025-01-02')
        """,
        (case_id,),
    )
    legacy_db.commit()
    legacy_db.close()

    db = connect_courts(court_path)
    try:
        assert db.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0] == str(SCHEMA_VERSION)
        assert db.execute(
            "SELECT native_access_state FROM case_record"
        ).fetchone()[0] == "public"
        assert tuple(
            db.execute(
                """
                SELECT assertion_kind, native_assertion_kind FROM case_event
                """
            ).fetchone()
        ) == ("docket_metadata", "docket_metadata")
        assert tuple(
            db.execute(
                """
                SELECT assertion_kind, native_assertion_kind
                FROM evidence_representation
                """
            ).fetchone()
        ) == ("court_finding", "court_finding")
        assert tuple(
            db.execute(
                "SELECT event_type, native_event_type FROM restriction_event"
            ).fetchone()
        ) == ("sealed", "sealed")

        db.execute(
            """
            INSERT INTO case_event(
                case_id, source_id, native_event_id, event_type,
                assertion_kind, native_assertion_kind
            ) VALUES (?, 'us-wi-wcca', 'event-2', 'classification',
                      'other', 'local-class-17')
            """,
            (case_id,),
        )
        db.execute(
            """
            INSERT INTO restriction_event(
                case_id, source_id, event_type, native_event_type, effective_at
            ) VALUES (?, 'us-wi-wcca', 'other', 'retention-code-4',
                      '2025-01-03')
            """,
            (case_id,),
        )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        db.close()


def test_canonical_refs_are_scoped_and_url_safe():
    assert canonical_property_ref(
        "us-nyc-acris", "36061", "instrument", "2026/ABC 1"
    ) == "PROPERTY:us-nyc-acris/36061/instrument/2026%2FABC%201"
    assert canonical_court_ref(
        "us-wi-wcca", "wi-dane-circuit", "2025 CV 1", "document", "entry/1"
    ) == (
        "STATECOURT:us-wi-wcca/wi-dane-circuit/2025%20CV%201/"
        "document/entry%2F1"
    )


def test_stats_uses_injected_sidecars(tmp_path):
    result = stats(tmp_path / "property.db", tmp_path / "court.db")
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["property"]["parcel_snapshot"] == 0
    assert result["state_local_courts"]["case_record"] == 0
