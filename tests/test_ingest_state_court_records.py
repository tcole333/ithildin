from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsError,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    ResultStatus,
    SourceMetadata,
)
from tools.public_records_store import connect_courts


SOURCE_ID = "us-wi-test-courts"
RETRIEVED_AT = "2026-07-28T12:00:00Z"


def canonical_case(case_number: str = "2026CV000123") -> dict:
    return {
        "source_id": SOURCE_ID,
        "court": {
            "court_id": "wi-dane-circuit",
            "native_court_id": "13",
            "name": "Dane County Circuit Court",
            "state_code": "WI",
            "county_geoid": "55025",
            "court_level": "trial",
            "division": "civil",
            "branch": "1",
            "official_url": "https://example.test/court/13",
        },
        "raw_case_number": case_number,
        "display_case_number": "2026CV123",
        "source_internal_id": "case-123",
        "caption": "ACME LLC v. EXAMPLE PERSON",
        "case_type": "civil",
        "filing_date": "2026-01-02",
        "disposition_date": None,
        "status": "open",
        "access_state": "redacted",
        "certified_record": False,
        "source_url": "https://example.test/case/case-123",
        "schema_fingerprint": "a" * 64,
        "parties": [
            {
                "sequence_no": 1,
                "role": "plaintiff",
                "raw_name": "ACME LLC",
                "normalized_name": "ACME LLC",
                "entity_kind": "organization",
                "attorneys": [
                    {
                        "attorney": {
                            "raw_name": "FIRST COUNSEL",
                            "normalized_name": "FIRST COUNSEL",
                            "bar_id": "WI-1",
                            "firm_name": "FIRST FIRM",
                        },
                        "effective_from": "2026-01-02",
                        "source_entry_id": "entry-1",
                    }
                ],
            },
            {
                "sequence": 2,
                "role": "defendant",
                "raw_name": "EXAMPLE PERSON",
                "normalized_name": "EXAMPLE PERSON",
                "entity_kind": "person",
            },
        ],
        "attorneys": [
            {
                "raw_name": "SECOND COUNSEL",
                "normalized_name": "SECOND COUNSEL",
                "bar_id": "WI-2",
                "firm_name": "SECOND FIRM",
                "party_sequence": 2,
                "effective_from": "2026-01-03",
            }
        ],
        "judicial_assignments": [
            {
                "officer": {
                    "raw_name": "JUDGE EXAMPLE",
                    "normalized_name": "JUDGE EXAMPLE",
                    "native_officer_id": "judge-9",
                },
                "assignment_role": "presiding",
                "effective_from": "2026-01-02",
            }
        ],
        "docket_entries": [
            {
                "native_entry_id": "entry-1",
                "sequence_no": "1",
                "event_code": "COMPLAINT",
                "raw_text": "Complaint filed",
                "filed_date": "2026-01-02",
                "entered_date": "2026-01-02",
                "event_date": "2026-01-02",
                "filer_raw": "ACME LLC",
                "document_available": True,
                "documents": [
                    {
                        "native_document_id": "doc-1",
                        "document_type": "complaint",
                        "filed_date": "2026-01-02",
                        "source_url": "https://example.test/document/doc-1",
                        "sha256": "b" * 64,
                        "mime_type": "application/pdf",
                        "page_count": 12,
                        "storage_path": "/archive/doc-1.pdf",
                        "ocr_status": "complete",
                        "certification_status": "portal_copy",
                    }
                ],
            }
        ],
        "case_events": [
            {
                "native_event_id": "event-1",
                "event_type": "filing",
                "event_date": "2026-01-02",
                "filed_date": "2026-01-02",
                "assertion_kind": "docket_metadata",
                "source_entry_native_id": "entry-1",
            }
        ],
        "documents": [
            {
                "native_document_id": "doc-2",
                "document_type": "notice",
                "filed_date": "2026-01-03",
                "sha256": None,
                "mime_type": "application/pdf",
                "access_state": "public",
            }
        ],
        "restriction_events": [
            {
                "event_type": "redacted",
                "effective_at": "2026-01-04T00:00:00Z",
                "reason": "Source portal marked selected fields redacted",
                "direction_ref": "portal:event-9",
            }
        ],
    }


def query() -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SourceMetadata(
            source_id=SOURCE_ID,
            name="Wisconsin test court source",
            source_role="court_portal",
            base_url="https://example.test/courts",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="us-wi",
            name="Wisconsin",
            state_code="WI",
        ),
        query=QueryMetadata(
            operation="case",
            parameters={"case_number": "2026CV000123"},
            requested_limit=1,
        ),
    )


def envelope(
    status: ResultStatus = ResultStatus.OK,
    records=None,
) -> dict:
    if records is None:
        records = [canonical_case()] if status in {ResultStatus.OK, ResultStatus.PARTIAL} else []
    if status == ResultStatus.NO_RESULTS:
        result = PublicRecordsResult.success(
            query(),
            [],
            retrieved_at=RETRIEVED_AT,
        )
    elif status == ResultStatus.OK:
        result = PublicRecordsResult.success(
            query(),
            records,
            retrieved_at=RETRIEVED_AT,
            raw_artifact_refs=["SOURCE:fixture"],
            warnings=["Fixture warning"],
        )
    elif status == ResultStatus.PARTIAL:
        result = PublicRecordsResult(
            query=query(),
            status=ResultStatus.PARTIAL,
            retrieved_at=RETRIEVED_AT,
            records=records,
            warnings=["Partial fixture"],
        )
    else:
        result = PublicRecordsResult.failure(
            query(),
            status,
            [
                PublicRecordsError(
                    code=f"fixture_{status.value}",
                    message=f"Fixture {status.value}",
                    category="fixture",
                )
            ],
            retrieved_at=RETRIEVED_AT,
        )
    return result.to_dict()


def table_count(db, table: str) -> int:
    return int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def test_projects_full_canonical_case_and_preserves_lineage(tmp_path):
    db_path = tmp_path / "courts.db"
    artifact = tmp_path / "source-envelope.json"
    value = envelope()
    artifact.write_text(json.dumps(value, indent=2), encoding="utf-8")
    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()

    result = ingest_envelope(
        value,
        court_db=db_path,
        artifact_path=artifact,
    )

    assert result["source_status"] == "ok"
    assert result["raw_artifact_sha256"] == artifact_sha
    assert result["canonical_refs"] == [
        "STATECOURT:us-wi-test-courts/wi-dane-circuit/2026CV000123/case"
    ]
    assert result["projected"] == {
        "courts": 1,
        "cases": 1,
        "parties": 2,
        "attorneys": 2,
        "representations": 2,
        "judicial_officers": 1,
        "assignments": 1,
        "docket_entries": 1,
        "case_events": 1,
        "documents": 2,
        "restriction_events": 1,
    }

    db = connect_courts(db_path)
    try:
        expected_counts = {
            "source_snapshot": 1,
            "court": 1,
            "case_record": 1,
            "case_party": 2,
            "attorney": 2,
            "case_representation": 2,
            "judicial_officer": 1,
            "case_assignment": 1,
            "docket_entry": 1,
            "case_event": 1,
            "document_artifact": 2,
            "restriction_event": 1,
        }
        assert {
            table: table_count(db, table) for table in expected_counts
        } == expected_counts
        snapshot = db.execute("SELECT * FROM source_snapshot").fetchone()
        assert snapshot["query_fingerprint"] == value["query"]["fingerprint"]
        assert snapshot["raw_artifact_sha256"] == artifact_sha
        assert snapshot["raw_artifact_path"] == str(artifact.resolve())
        assert json.loads(snapshot["raw_json"]) == value
        assert json.loads(snapshot["warning_json"]) == ["Fixture warning"]
        assert snapshot["schema_fingerprint"] == "a" * 64

        case = db.execute("SELECT * FROM case_record").fetchone()
        assert case["access_state"] == "redacted"
        assert case["native_access_state"] == "redacted"
        assert case["snapshot_id"] == snapshot["snapshot_id"]
        assert json.loads(case["raw_json"])["raw_case_number"] == "2026CV000123"
        assert {
            row["access_state"]
            for row in db.execute("SELECT access_state FROM case_party")
        } == {"redacted"}
        assert {
            row["access_state"]
            for row in db.execute("SELECT access_state FROM docket_entry")
        } == {"redacted"}
        assert {
            row["access_state"]
            for row in db.execute("SELECT access_state FROM document_artifact")
        } == {"redacted", "public"}
        restriction = db.execute("SELECT * FROM restriction_event").fetchone()
        assert restriction["event_type"] == "redacted"
        assert restriction["direction_ref"] == "portal:event-9"
    finally:
        db.close()


def test_source_native_labels_map_without_rolling_back_envelope(tmp_path):
    db_path = tmp_path / "courts.db"
    record = canonical_case("2026CV000125")
    record["access_state"] = "made nonpublic"
    record["parties"][0]["access_state"] = "Clerk privacy hold 42"
    record["docket_entries"][0]["access_state"] = "destroyed"
    record["docket_entries"][0]["documents"][0]["access_state"] = "sealed"
    record["case_events"][0]["assertion_kind"] = "administrative disposition note"
    record["restriction_events"] = [
        {
            "event_type": "made_nonpublic",
            "effective_at": "2026-01-04T00:00:00Z",
        },
        {
            "event_type": "destroyed",
            "effective_at": "2026-01-05T00:00:00Z",
        },
        {
            "event_type": "portal retention code 77",
            "effective_at": "2026-01-06T00:00:00Z",
        },
    ]

    result = ingest_envelope(envelope(records=[record]), court_db=db_path)

    assert result["projected"]["cases"] == 1
    assert result["projected"]["restriction_events"] == 3
    db = connect_courts(db_path)
    try:
        case = db.execute("SELECT * FROM case_record").fetchone()
        assert (case["access_state"], case["native_access_state"]) == (
            "restricted",
            "made nonpublic",
        )
        parties = list(
            db.execute(
                """
                SELECT sequence_no, access_state, native_access_state
                FROM case_party ORDER BY sequence_no
                """
            )
        )
        assert [tuple(row) for row in parties] == [
            (1, "unknown", "Clerk privacy hold 42"),
            (2, "restricted", "made nonpublic"),
        ]
        docket = db.execute("SELECT * FROM docket_entry").fetchone()
        assert (docket["access_state"], docket["native_access_state"]) == (
            "removed",
            "destroyed",
        )
        complaint = db.execute(
            """
            SELECT access_state, native_access_state
            FROM document_artifact
            WHERE native_document_id='doc-1'
            """
        ).fetchone()
        assert tuple(complaint) == ("sealed", "sealed")
        case_event = db.execute("SELECT * FROM case_event").fetchone()
        assert (
            case_event["assertion_kind"],
            case_event["native_assertion_kind"],
        ) == ("other", "administrative disposition note")
        restrictions = list(
            db.execute(
                """
                SELECT event_type, native_event_type
                FROM restriction_event ORDER BY effective_at
                """
            )
        )
        assert [tuple(row) for row in restrictions] == [
            ("restricted", "made_nonpublic"),
            ("removed", "destroyed"),
            ("other", "portal retention code 77"),
        ]
        assert table_count(db, "source_snapshot") == 1
    finally:
        db.close()


def test_replay_appends_snapshot_but_keeps_projection_idempotent(tmp_path):
    db_path = tmp_path / "courts.db"
    value = envelope()

    first = ingest_envelope(value, court_db=db_path)
    second = ingest_envelope(value, court_db=db_path)

    assert second["snapshot_id"] > first["snapshot_id"]
    db = connect_courts(db_path)
    try:
        assert table_count(db, "source_snapshot") == 2
        assert table_count(db, "court") == 1
        assert table_count(db, "case_record") == 1
        assert table_count(db, "case_party") == 2
        assert table_count(db, "attorney") == 2
        assert table_count(db, "case_representation") == 2
        assert table_count(db, "judicial_officer") == 1
        assert table_count(db, "case_assignment") == 1
        assert table_count(db, "docket_entry") == 1
        assert table_count(db, "case_event") == 1
        assert table_count(db, "document_artifact") == 2
        assert table_count(db, "restriction_event") == 1
        current_case = db.execute("SELECT * FROM case_record").fetchone()
        assert current_case["snapshot_id"] == second["snapshot_id"]
    finally:
        db.close()


@pytest.mark.parametrize(
    "status",
    [
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
        ResultStatus.UNAVAILABLE,
        ResultStatus.RESTRICTED,
        ResultStatus.HUMAN_REQUIRED,
        ResultStatus.RATE_LIMITED,
        ResultStatus.TERMS_BLOCKED,
        ResultStatus.SOURCE_CHANGED,
    ],
)
def test_every_shared_status_preserves_source_snapshot(tmp_path, status):
    db_path = tmp_path / f"{status.value}.db"
    value = envelope(status)

    result = ingest_envelope(value, court_db=db_path)

    assert result["source_status"] == status.value
    db = connect_courts(db_path)
    try:
        snapshot = db.execute("SELECT * FROM source_snapshot").fetchone()
        assert snapshot is not None
        assert snapshot["access_status"] == status.value
        assert json.loads(snapshot["raw_json"]) == value
        expected_cases = 1 if status in {ResultStatus.OK, ResultStatus.PARTIAL} else 0
        assert table_count(db, "case_record") == expected_cases
    finally:
        db.close()


def test_transaction_rolls_back_snapshot_and_projection_on_invalid_record(tmp_path):
    db_path = tmp_path / "courts.db"
    invalid = canonical_case("2026CV000124")
    invalid.pop("access_state")
    value = envelope(records=[canonical_case(), invalid])

    with pytest.raises(ValueError, match="case.access_state"):
        ingest_envelope(value, court_db=db_path)

    db = connect_courts(db_path)
    try:
        assert table_count(db, "source_snapshot") == 0
        assert table_count(db, "court") == 0
        assert table_count(db, "case_record") == 0
        assert table_count(db, "case_party") == 0
    finally:
        db.close()


def test_artifact_hash_mismatch_is_rejected_before_snapshot(tmp_path):
    db_path = tmp_path / "courts.db"
    artifact = tmp_path / "source.json"
    artifact.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        ingest_envelope(
            envelope(),
            court_db=db_path,
            artifact_path=artifact,
            artifact_sha256="0" * 64,
        )

    db = connect_courts(db_path)
    try:
        assert table_count(db, "source_snapshot") == 0
    finally:
        db.close()


def test_docket_wrapper_record_projects_case_and_entry(tmp_path):
    db_path = tmp_path / "courts.db"
    base = canonical_case()
    base.pop("docket_entries")
    base.pop("documents")
    base.pop("case_events")
    wrapper = {
        "case": base,
        "native_entry_id": "entry-wrapper",
        "sequence": "7",
        "text": "Wrapper docket entry",
        "document_available": False,
        "access_state": "public",
    }

    result = ingest_envelope(
        envelope(records=[wrapper]),
        court_db=db_path,
    )

    assert result["projected"]["cases"] == 1
    assert result["projected"]["docket_entries"] == 1
    db = connect_courts(db_path)
    try:
        entry = db.execute("SELECT * FROM docket_entry").fetchone()
        assert entry["native_entry_id"] == "entry-wrapper"
        assert entry["raw_text"] == "Wrapper docket entry"
    finally:
        db.close()


def test_direct_cli_ingests_json_and_writes_report(tmp_path):
    db_path = tmp_path / "courts.db"
    input_path = tmp_path / "envelope.json"
    output_path = tmp_path / "report.json"
    input_path.write_text(json.dumps(envelope()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "tools/ingest_state_court_records.py",
            "ingest",
            str(input_path),
            "--court-db",
            str(db_path),
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["source_status"] == "ok"
    assert report["projected"]["cases"] == 1
    assert Path(report["raw_artifact_path"]) == input_path.resolve()
