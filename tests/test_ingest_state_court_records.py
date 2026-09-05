from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import (
    query_dc_opinions,
    query_dc_superior_calendar,
    query_eugene_municipal_court,
    query_fresno_superior_court,
    query_orange_county_court,
    query_riverside_court,
)
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
        records = (
            [canonical_case()]
            if status in {ResultStatus.OK, ResultStatus.PARTIAL}
            else []
        )
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
        "STATECOURT:us-wi-test-courts/wi-dane-circuit/2026CV000123/case/case-123"
    ]
    assert result["projected"] == {
        "courts": 1,
        "related_courts": 0,
        "cases": 1,
        "related_cases": 0,
        "case_relations": 0,
        "parties": 2,
        "attorneys": 2,
        "representations": 2,
        "judicial_officers": 1,
        "assignments": 1,
        "claims": 0,
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
            "case_claim": 0,
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
        assert case["case_identity_key"] == "native:case-123"
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


def test_orange_hearing_and_case_bearing_ruling_project_without_conflation(
    tmp_path,
):
    fixture_root = Path("tests/fixtures/orange_county_court")
    hearing_record = query_orange_county_court.parse_calendar_page(
        (fixture_root / "calendar_page_1.html").read_text(encoding="utf-8"),
        category="civil",
        retrieved_at="2026-07-30T12:00:00Z",
    ).records[0]
    parsed_ruling = query_orange_county_court.parse_ruling_text(
        (fixture_root / "ruling_text.txt").read_text(encoding="utf-8")
    )
    ruling_source_id = query_orange_county_court.RULING_SOURCE_IDS["civil"]
    ruling_record = {
        "canonical_ref": "OC-TENTATIVE-RULING:" + "b" * 64,
        "source_id": ruling_source_id,
        "record_kind": "tentative_ruling_document",
        "court": {
            "court_id": query_orange_county_court.COURT_ID,
            "name": query_orange_county_court.COURT_NAME,
            "county_fips": query_orange_county_court.COUNTY_FIPS,
            "state_code": "CA",
        },
        "division": "civil",
        "department": "C44",
        "judicial_officer": parsed_ruling["judicial_officer"],
        "hearing": {
            "date": parsed_ruling["hearing_date"],
            "time": parsed_ruling["hearing_time"],
        },
        "case_numbers": parsed_ruling["case_numbers"],
        "text": parsed_ruling["text"],
        "text_sha256": parsed_ruling["text_sha256"],
        "artifact": {
            "url": "https://www.occourts.org/rulings/C44.pdf",
            "format": "pdf",
            "sha256": "b" * 64,
            "bytes": 1234,
            "last_modified": "2026-07-30T07:00:00Z",
        },
        "retrieved_at": "2026-07-30T12:00:00Z",
    }
    db_path = tmp_path / "orange.db"

    calendar_query = query_orange_county_court._query(
        query_orange_county_court.CALENDAR_SOURCE,
        "calendar",
        {"category": "civil"},
    )
    calendar_report = ingest_envelope(
        PublicRecordsResult.success(
            calendar_query,
            [hearing_record],
            retrieved_at="2026-07-30T12:00:00Z",
        ).to_dict(),
        court_db=db_path,
    )
    assert calendar_report["projected"]["cases"] == 1
    assert calendar_report["projected"]["docket_entries"] == 1

    ruling_query = query_orange_county_court._query(
        query_orange_county_court._ruling_source("civil"),
        "ruling",
        {"division": "civil", "department": "C44"},
    )
    ruling_report = ingest_envelope(
        PublicRecordsResult.success(
            ruling_query,
            [ruling_record],
            retrieved_at="2026-07-30T12:00:00Z",
        ).to_dict(),
        court_db=db_path,
    )
    assert ruling_report["projected"]["cases"] == 2
    assert ruling_report["projected"]["docket_entries"] == 2
    assert ruling_report["projected"]["documents"] == 2

    db = connect_courts(db_path)
    try:
        rows = db.execute(
            """
            SELECT c.source_id, c.raw_case_number, c.case_type,
                   ct.state_code, ct.county_geoid
            FROM case_record c
            JOIN court ct ON ct.court_id=c.court_id
            ORDER BY c.source_id, c.raw_case_number
            """
        ).fetchall()
        assert len(rows) == 3
        assert {row["state_code"] for row in rows} == {"CA"}
        assert {row["county_geoid"] for row in rows} == {"06059"}
        ruling_rows = [
            row for row in rows if row["source_id"] == ruling_source_id
        ]
        assert {row["raw_case_number"] for row in ruling_rows} == set(
            parsed_ruling["case_numbers"]
        )
        assert {row["case_type"] for row in ruling_rows} == {"civil"}

        entries = db.execute(
            """
            SELECT source_id, event_type, status, document_available
            FROM docket_entry
            ORDER BY source_id
            """
        ).fetchall()
        hearing_entry = next(
            row
            for row in entries
            if row["source_id"]
            == query_orange_county_court.CALENDAR_SOURCE_ID
        )
        assert hearing_entry["event_type"] == "hearing"
        assert hearing_entry["document_available"] == 0
        ruling_entries = [
            row for row in entries if row["source_id"] == ruling_source_id
        ]
        assert len(ruling_entries) == 2
        assert {row["event_type"] for row in ruling_entries} == {
            "tentative_ruling"
        }
        assert {row["status"] for row in ruling_entries} == {"tentative"}
        assert {row["document_available"] for row in ruling_entries} == {1}

        documents = db.execute(
            """
            SELECT source_id, document_type, sha256, mime_type
            FROM document_artifact
            """
        ).fetchall()
        assert len(documents) == 2
        assert {row["source_id"] for row in documents} == {ruling_source_id}
        assert {row["document_type"] for row in documents} == {
            "civil_tentative_ruling_pdf"
        }
        assert {row["sha256"] for row in documents} == {"b" * 64}
        assert {row["mime_type"] for row in documents} == {
            "application/pdf"
        }
    finally:
        db.close()


def test_riverside_calendar_and_ruling_documents_project_case_records(
    tmp_path,
):
    calendar_record = {
        "canonical_ref": "RIVERSIDE-CALENDAR:" + "a" * 64,
        "source_id": query_riverside_court.CALENDAR_SOURCE_ID,
        "record_kind": "court_calendar_event",
        "court": {
            "court_id": query_riverside_court.COURT_ID,
            "name": query_riverside_court.COURT_NAME,
            "county_fips": query_riverside_court.COUNTY_FIPS,
            "state_code": "CA",
        },
        "case_number": "PRRI2601001",
        "case_name": "Estate of Example",
        "case_type": "Probate",
        "area_of_law": "Probate",
        "hearing": {
            "date": "2026-07-30",
            "time": "08:30",
            "names": [
                "Hearing on Petition for Probate",
                "Status Conference",
            ],
            "special_status": None,
        },
        "courthouse": {
            "name": "Historic Court House",
            "address": "4050 Main Street, Riverside, CA, 92501",
        },
        "department": "8",
        "department_label": "Department 8",
        "judicial_officer": "Christopher B. Harmon",
        "attorneys": ["Alex Counsel", "Blair Counsel"],
        "charge_data": None,
        "retrieved_at": "2026-07-30T12:00:00Z",
    }
    fixture_root = Path("tests/fixtures/public_records/riverside_court")
    parsed_ruling = query_riverside_court.parse_ruling_text(
        (fixture_root / "ruling_text.txt").read_text(encoding="utf-8")
    )
    ruling_record = {
        "canonical_ref": "RIVERSIDE-RULING:" + "b" * 64,
        "source_id": query_riverside_court.RULING_SOURCE_ID,
        "record_kind": "tentative_ruling_document",
        "court": {
            "court_id": query_riverside_court.COURT_ID,
            "name": query_riverside_court.COURT_NAME,
            "county_fips": query_riverside_court.COUNTY_FIPS,
            "state_code": "CA",
        },
        "department": "PS1",
        "judicial_officer": "John G. Evans",
        "hearing_date": parsed_ruling["hearing_date"],
        "case_numbers": parsed_ruling["case_numbers"],
        "text": parsed_ruling["text"],
        "text_sha256": parsed_ruling["text_sha256"],
        "artifact": {
            "url": (
                "https://www.riverside.courts.ca.gov/system/files/"
                "2026-07/ps1.pdf"
            ),
            "content_type": "application/pdf",
            "sha256": "b" * 64,
            "bytes": 4567,
            "last_modified": "Thu, 30 Jul 2026 07:00:00 GMT",
        },
        "retrieved_at": "2026-07-30T12:00:00Z",
    }
    db_path = tmp_path / "riverside.db"

    calendar_query = query_riverside_court._query(
        query_riverside_court.CALENDAR_SOURCE,
        "calendar",
        {"department": "8"},
    )
    calendar_report = ingest_envelope(
        PublicRecordsResult.success(
            calendar_query,
            [calendar_record],
            retrieved_at="2026-07-30T12:00:00Z",
        ).to_dict(),
        court_db=db_path,
    )
    assert calendar_report["projected"]["cases"] == 1
    assert calendar_report["projected"]["docket_entries"] == 1
    assert calendar_report["projected"]["attorneys"] == 2

    ruling_query = query_riverside_court._query(
        query_riverside_court.RULING_SOURCE,
        "ruling",
        {"department": "PS1"},
    )
    ruling_report = ingest_envelope(
        PublicRecordsResult.success(
            ruling_query,
            [ruling_record],
            retrieved_at="2026-07-30T12:00:00Z",
        ).to_dict(),
        court_db=db_path,
    )
    expected_rulings = len(parsed_ruling["case_numbers"])
    assert ruling_report["projected"]["cases"] == expected_rulings
    assert ruling_report["projected"]["docket_entries"] == expected_rulings
    assert ruling_report["projected"]["documents"] == expected_rulings

    db = connect_courts(db_path)
    try:
        cases = db.execute(
            """
            SELECT c.source_id, c.raw_case_number,
                   ct.state_code, ct.county_geoid
            FROM case_record c
            JOIN court ct ON ct.court_id = c.court_id
            ORDER BY c.source_id, c.raw_case_number
            """
        ).fetchall()
        assert {row["state_code"] for row in cases} == {"CA"}
        assert {row["county_geoid"] for row in cases} == {"06065"}
        assert calendar_record["case_number"] in {
            row["raw_case_number"] for row in cases
        }
        assert set(parsed_ruling["case_numbers"]).issubset(
            {row["raw_case_number"] for row in cases}
        )
        hearing = db.execute(
            """
            SELECT event_type, judge, location, document_available
            FROM docket_entry
            WHERE source_id = ?
            """,
            (query_riverside_court.CALENDAR_SOURCE_ID,),
        ).fetchone()
        assert hearing["event_type"] == "hearing"
        assert hearing["judge"] == calendar_record["judicial_officer"]
        assert "Historic Court House" in hearing["location"]
        assert hearing["document_available"] == 0

        ruling_entries = db.execute(
            """
            SELECT event_type, status, document_available
            FROM docket_entry
            WHERE source_id = ?
            """,
            (query_riverside_court.RULING_SOURCE_ID,),
        ).fetchall()
        assert {row["event_type"] for row in ruling_entries} == {
            "tentative_ruling"
        }
        assert {row["status"] for row in ruling_entries} == {"tentative"}
        assert {row["document_available"] for row in ruling_entries} == {1}
    finally:
        db.close()


def test_riverside_ruling_directory_rows_remain_snapshot_only(tmp_path):
    fixture_root = Path("tests/fixtures/public_records/riverside_court")
    records = query_riverside_court.parse_ruling_directory(
        (fixture_root / "ruling_index.html").read_text(encoding="utf-8"),
        retrieved_at="2026-07-30T12:00:00Z",
    )
    query = query_riverside_court._query(
        query_riverside_court.RULING_SOURCE,
        "ruling-index",
        {},
    )
    report = ingest_envelope(
        PublicRecordsResult.success(
            query,
            records[:1],
            retrieved_at="2026-07-30T12:00:00Z",
        ).to_dict(),
        court_db=tmp_path / "riverside-index.db",
    )
    assert report["snapshot_only"]["record_count"] == 1
    assert report["snapshot_only"]["record_kinds"] == {
        "tentative_ruling_artifact_index": 1
    }
    assert report["projected"]["cases"] == 0
    assert report["projected"]["docket_entries"] == 0


def test_persists_only_source_published_docket_hearing_metadata(tmp_path):
    db_path = tmp_path / "courts.db"
    record = canonical_case("2026CV000777")
    record["docket_entries"] = [
        {
            "native_entry_id": "hearing-complete",
            "event_code": "HEARING",
            "event_type": "hearing",
            "raw_text": "Status conference",
            "event_date": "2026-08-10",
            "event_time": "09:30",
            "judge": "Judge Source",
            "location": "Courtroom 4",
            "status": "Remote appearance",
            "document_available": False,
        },
        {
            "native_entry_id": "hearing-sparse",
            "event_code": "future_hearing",
            "event_type": "future_hearing",
            "raw_text": "Hearing",
            "event_date": "2026-08-11",
            "document_available": False,
        },
    ]
    record["case_events"] = []
    record["restriction_events"] = []

    ingest_envelope(envelope(records=[record]), court_db=db_path)
    ingest_envelope(envelope(records=[record]), court_db=db_path)

    db = connect_courts(db_path)
    try:
        rows = list(
            db.execute(
                """
                SELECT native_entry_id, event_code, event_type, event_date,
                       event_time, judge, location, status, raw_json
                FROM docket_entry
                ORDER BY native_entry_id
                """
            )
        )
        assert len(rows) == 2
        complete, sparse = rows
        assert tuple(complete[:-1]) == (
            "hearing-complete",
            "HEARING",
            "hearing",
            "2026-08-10",
            "09:30",
            "Judge Source",
            "Courtroom 4",
            "Remote appearance",
        )
        assert json.loads(complete["raw_json"])["judge"] == "Judge Source"
        assert tuple(sparse[:-1]) == (
            "hearing-sparse",
            "future_hearing",
            "future_hearing",
            "2026-08-11",
            None,
            None,
            None,
            None,
        )
        assert table_count(db, "docket_entry") == 2
    finally:
        db.close()


def test_projects_originating_trial_case_as_searchable_relation(tmp_path):
    appellate_case = canonical_case("2026AP000123")
    appellate_case["court"] = {
        "court_id": "wi-court-of-appeals",
        "native_court_id": "coa",
        "name": "Wisconsin Court of Appeals",
        "state_code": "WI",
        "court_level": "appellate",
        "official_url": "https://example.test/appeals",
    }
    appellate_case["display_case_number"] = "2026AP123"
    appellate_case["source_internal_id"] = "appeal-123"
    appellate_case["judicial_assignments"] = []
    appellate_case["case_relations"] = [
        {
            "native_relation_id": "appeal-123:originating-trial:1",
            "relation_type": "originating_trial_case",
            "raw_case_number": "2025CV000456",
            "court_name": "Dane County Circuit Court",
            "county": "Dane",
            "county_geoid": "55025",
            "judge": "JUDGE TRIAL",
            "reporter": "REPORTER EXAMPLE",
            "source_url": "https://example.test/appeal-123",
        }
    ]

    result = ingest_envelope(
        envelope(records=[appellate_case]),
        court_db=tmp_path / "courts.db",
    )

    assert result["projected"]["cases"] == 1
    assert result["projected"]["related_courts"] == 1
    assert result["projected"]["related_cases"] == 1
    assert result["projected"]["case_relations"] == 1
    assert result["projected"]["judicial_officers"] == 1
    assert result["projected"]["assignments"] == 1

    db = connect_courts(tmp_path / "courts.db")
    try:
        relation = db.execute(
            """
            SELECT
                source_case.raw_case_number AS source_case_number,
                destination_case.raw_case_number AS destination_case_number,
                relation.relation_type,
                relation.evidence_ref
            FROM case_relation AS relation
            JOIN case_record AS source_case
              ON source_case.case_id = relation.from_case_id
            JOIN case_record AS destination_case
              ON destination_case.case_id = relation.to_case_id
            """
        ).fetchone()
        assert dict(relation) == {
            "source_case_number": "2025CV000456",
            "destination_case_number": "2026AP000123",
            "relation_type": "appealed_to",
            "evidence_ref": "appeal-123:originating-trial:1",
        }
        trial_assignment = db.execute(
            """
            SELECT
                case_record.raw_case_number,
                court.name AS court_name,
                court.county_geoid,
                judicial_officer.raw_name,
                case_assignment.assignment_role
            FROM case_assignment
            JOIN case_record
              ON case_record.case_id = case_assignment.case_id
            JOIN court ON court.court_id = case_record.court_id
            JOIN judicial_officer
              ON judicial_officer.judicial_officer_id =
                 case_assignment.judicial_officer_id
            """
        ).fetchone()
        assert dict(trial_assignment) == {
            "raw_case_number": "2025CV000456",
            "court_name": "Dane County Circuit Court",
            "county_geoid": "55025",
            "raw_name": "JUDGE TRIAL",
            "assignment_role": "trial_court_judge",
        }
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


def test_native_case_identity_preserves_duplicate_raw_numbers_idempotently(
    tmp_path,
):
    db_path = tmp_path / "courts.db"
    first = canonical_case("6707")
    first["source_internal_id"] = "doc-101"
    first["caption"] = "First native case"
    second = copy.deepcopy(first)
    second["source_internal_id"] = "doc-102"
    second["caption"] = "Second native case"

    value = envelope(records=[first, second])
    first_ingest = ingest_envelope(value, court_db=db_path)
    second_ingest = ingest_envelope(value, court_db=db_path)

    assert first_ingest["canonical_refs"] == [
        "STATECOURT:us-wi-test-courts/wi-dane-circuit/6707/case/doc-101",
        "STATECOURT:us-wi-test-courts/wi-dane-circuit/6707/case/doc-102",
    ]
    assert second_ingest["canonical_refs"] == first_ingest["canonical_refs"]
    db = connect_courts(db_path)
    try:
        cases = list(
            db.execute(
                """
                SELECT raw_case_number, source_internal_id,
                       case_identity_key, caption
                FROM case_record ORDER BY source_internal_id
                """
            )
        )
        assert [tuple(row) for row in cases] == [
            (
                "6707",
                "doc-101",
                "native:doc-101",
                "First native case",
            ),
            (
                "6707",
                "doc-102",
                "native:doc-102",
                "Second native case",
            ),
        ]
        assert table_count(db, "case_record") == 2
        assert table_count(db, "case_party") == 4
        assert table_count(db, "docket_entry") == 2
        assert table_count(db, "document_artifact") == 4
        assert table_count(db, "source_snapshot") == 2
    finally:
        db.close()


def test_missing_native_case_id_falls_back_to_raw_number_idempotently(
    tmp_path,
):
    db_path = tmp_path / "courts.db"
    record = canonical_case("NO-NATIVE-ID")
    record.pop("source_internal_id")
    value = envelope(records=[record])

    ingest_envelope(value, court_db=db_path)
    ingest_envelope(value, court_db=db_path)

    db = connect_courts(db_path)
    try:
        case = db.execute(
            """
            SELECT raw_case_number, source_internal_id, case_identity_key
            FROM case_record
            """
        ).fetchone()
        assert tuple(case) == (
            "NO-NATIVE-ID",
            None,
            "number:NO-NATIVE-ID",
        )
        assert table_count(db, "case_record") == 1
        assert table_count(db, "case_party") == 2
    finally:
        db.close()


def test_namespaced_identity_separates_native_id_from_raw_number(tmp_path):
    db_path = tmp_path / "courts.db"
    native = canonical_case("CASE-A")
    native["source_internal_id"] = "shared-key"
    fallback = copy.deepcopy(native)
    fallback["raw_case_number"] = "shared-key"
    fallback["display_case_number"] = "shared-key"
    fallback.pop("source_internal_id")

    ingest_envelope(
        envelope(records=[native, fallback]),
        court_db=db_path,
    )

    db = connect_courts(db_path)
    try:
        assert {
            row[0] for row in db.execute("SELECT case_identity_key FROM case_record")
        } == {"native:shared-key", "number:shared-key"}
        assert table_count(db, "case_record") == 2
    finally:
        db.close()


def test_claims_ingest_sparse_headers_and_replay_idempotently(tmp_path):
    db_path = tmp_path / "courts.db"
    record = canonical_case()
    record["claims"] = [
        {
            "claim_uuid": "claim-uuid-1",
            "sequence_no": 1,
            "claim_type": "Creditor Claim",
            "claim_date": "2020-01-02",
            "claimant_raw": "EXAMPLE CLAIMANT",
            "amount_minor": 125_000,
            "currency": "USD",
            "status": "filed",
            "limited_stub": False,
            "access_state": "public",
            "native_access_state": "C-Track visible",
            "raw": {"claimUUID": "claim-uuid-1"},
        },
        {
            "source_namespace_id": "CTRACK_CLAIM:sequence-2",
            "sequence_no": 2,
            "claim_type": "Administrative Claim",
            "limited_stub": True,
            "raw": {"sequenceNumber": 2},
        },
    ]
    value = envelope(records=[record])

    first = ingest_envelope(value, court_db=db_path)
    second = ingest_envelope(value, court_db=db_path)

    assert first["projected"]["claims"] == 2
    assert second["projected"]["claims"] == 2
    db = connect_courts(db_path)
    try:
        rows = list(
            db.execute(
                """
                SELECT native_claim_id, sequence_no, claim_type, claim_date,
                       claimant_raw, amount_minor, currency, status,
                       limited_stub, access_state, native_access_state,
                       snapshot_id, raw_json
                FROM case_claim ORDER BY sequence_no
                """
            )
        )
        assert len(rows) == 2
        full, sparse = rows
        assert tuple(full[:-2]) == (
            "claim-uuid-1",
            1,
            "Creditor Claim",
            "2020-01-02",
            "EXAMPLE CLAIMANT",
            125_000,
            "USD",
            "filed",
            0,
            "public",
            "C-Track visible",
        )
        assert full["snapshot_id"] == second["snapshot_id"]
        assert json.loads(full["raw_json"])["claim_uuid"] == "claim-uuid-1"
        assert tuple(sparse[:-2]) == (
            "CTRACK_CLAIM:sequence-2",
            2,
            "Administrative Claim",
            None,
            None,
            None,
            None,
            None,
            1,
            None,
            None,
        )
        assert sparse["snapshot_id"] == second["snapshot_id"]
        assert json.loads(sparse["raw_json"])["source_namespace_id"] == (
            "CTRACK_CLAIM:sequence-2"
        )
        assert table_count(db, "case_claim") == 2
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


def test_non_case_records_are_retained_without_case_projection(tmp_path):
    db_path = tmp_path / "courts.db"
    artifact = {
        "source_id": "us-tx-test-court-bulk",
        "record_kind": "bulk_dataset_artifact",
        "native_document_id": r"Civil\CaseSummary.txt",
        "source_url": "https://example.test/public-datasets",
    }
    value = envelope(records=[artifact])

    result = ingest_envelope(value, court_db=db_path)

    assert result["projected"]["cases"] == 0
    assert result["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"bulk_dataset_artifact": 1},
    }
    db = connect_courts(db_path)
    try:
        assert table_count(db, "source_snapshot") == 1
        assert table_count(db, "case_record") == 0
        snapshot = db.execute("SELECT raw_json FROM source_snapshot").fetchone()
        assert json.loads(snapshot["raw_json"]) == value
    finally:
        db.close()


def test_mixed_case_and_non_case_records_project_only_natural_case_shape(
    tmp_path,
):
    db_path = tmp_path / "courts.db"
    value = envelope(
        records=[
            canonical_case(),
            {
                "source_id": "us-wi-test-courts",
                "record_kind": "source_probe",
                "native_document_id": "probe-1",
            },
        ]
    )

    result = ingest_envelope(value, court_db=db_path)

    assert result["projected"]["cases"] == 1
    assert result["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"source_probe": 1},
    }
    assert len(result["canonical_refs"]) == 1


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


def test_non_eugene_tyler_calendar_projects_tenant_bound_cases(tmp_path):
    tenant = query_eugene_municipal_court.HERMISTON_TENANT
    fixture_path = (
        Path("tests/fixtures/public_records/oregon_tyler_municipal_tenants")
        / "hermiston_docket_detail.html"
    )
    text = fixture_path.read_text(encoding="utf-8")
    page = query_eugene_municipal_court.FetchedHTML(
        url=tenant.url("Dockets/Detail"),
        text=text,
        status_code=200,
        content_type="text/html; charset=utf-8",
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    record = query_eugene_municipal_court.parse_docket_detail(
        page,
        native_date="20260730090000",
        calendar_code="ARR",
        room_code="1",
        tenant=tenant,
    ).record
    args = query_eugene_municipal_court.build_parser().parse_args(
        [
            "docket",
            "--tenant",
            tenant.key,
            "20260730090000",
            "ARR",
            "1",
        ]
    )
    result = PublicRecordsResult.success(
        query_eugene_municipal_court.build_query(args),
        [record],
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "courts.db"

    report = ingest_envelope(result, court_db=db_path)

    assert report["source_id"] == tenant.source_id
    assert report["projected"]["cases"] == record["case_count"]
    assert report["projected"]["docket_entries"] == record["case_count"]
    db = connect_courts(db_path)
    try:
        court = db.execute(
            """
            SELECT court_id, source_id, name, state_code, county_geoid,
                   court_level
            FROM court
            """
        ).fetchone()
        assert tuple(court) == (
            tenant.court_id,
            tenant.source_id,
            tenant.court_name,
            "OR",
            tenant.county_fips,
            tenant.court_level,
        )
        cases = db.execute(
            """
            SELECT source_id, court_id, raw_case_number
            FROM case_record
            ORDER BY raw_case_number
            """
        ).fetchall()
        assert {row["source_id"] for row in cases} == {tenant.source_id}
        assert {row["court_id"] for row in cases} == {tenant.court_id}
        assert {row["raw_case_number"] for row in cases} == {
            item["raw_case_number"] for item in record["cases"]
        }
    finally:
        db.close()


def test_dc_opinion_and_moj_rows_project_distinct_dispositions_and_documents(
    tmp_path,
):
    fixture = (
        Path("tests/fixtures/public_records/dc_opinions/list_page.html")
        .read_text(encoding="utf-8")
    )
    opinion = query_dc_opinions.parse_page(
        fixture,
        source_url=query_dc_opinions.INDEX_URL,
        requested_page=0,
        selected_type="Opinions",
    ).records[0]
    moj = query_dc_opinions.parse_page(
        fixture,
        source_url=query_dc_opinions.INDEX_URL,
        requested_page=0,
        selected_type="Memorandums",
    ).records[1]
    source_query = PublicRecordsQuery(
        source=query_dc_opinions.SOURCE_METADATA,
        jurisdiction=query_dc_opinions.JURISDICTION,
        query=QueryMetadata(
            operation="list",
            parameters={
                "type": "mixed_fixture",
                "page": 0,
                "all_pages": False,
            },
        ),
    )
    envelope_value = PublicRecordsResult.success(
        source_query,
        [opinion, moj],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "dc-opinions.db"

    report = ingest_envelope(envelope_value, court_db=db_path)

    assert report["source_id"] == query_dc_opinions.SOURCE_ID
    assert report["projected"]["cases"] == 2
    assert report["projected"]["docket_entries"] == 2
    assert report["projected"]["documents"] == 1
    db = connect_courts(db_path)
    try:
        cases = db.execute(
            """
            SELECT raw_case_number, case_type, disposition_date, status,
                   access_state, source_url
            FROM case_record
            ORDER BY raw_case_number
            """
        ).fetchall()
        assert {row["raw_case_number"] for row in cases} == {
            opinion["raw_case_number"],
            moj["raw_case_number"],
        }
        assert {row["case_type"] for row in cases} == {"appellate"}
        assert {row["disposition_date"] for row in cases} == {
            opinion["decision_date"],
            moj["decision_date"],
        }
        assert {row["access_state"] for row in cases} == {"public"}
        assert {row["source_url"] for row in cases} == {
            query_dc_opinions.INDEX_URL
        }

        entries = db.execute(
            """
            SELECT native_entry_id, event_code, event_type, document_available,
                   judge, raw_json
            FROM docket_entry
            ORDER BY native_entry_id
            """
        ).fetchall()
        assert {row["event_type"] for row in entries} == {
            "appellate_disposition"
        }
        entries_by_kind = {
            json.loads(row["raw_json"])["publication_kind"]: row
            for row in entries
        }
        opinion_entry = entries_by_kind["published_opinion"]
        moj_entry = entries_by_kind[
            "memorandum_opinion_and_judgment_index"
        ]
        assert opinion_entry["document_available"] == 1
        assert moj_entry["document_available"] == 0
        moj_raw = json.loads(moj_entry["raw_json"])
        assert moj_raw["full_text_status"] == "not_published_by_court"
        assert moj_raw["publication_kind_basis"] == "source_type_filter"

        document = db.execute(
            """
            SELECT source_id, native_document_id, document_type, filed_date,
                   source_url, mime_type, access_state, docket_entry_id
            FROM document_artifact
            """
        ).fetchone()
        assert document is not None
        assert document["source_id"] == query_dc_opinions.SOURCE_ID
        assert document["native_document_id"] == opinion["native_entry_id"]
        assert document["document_type"] == "appellate_opinion"
        assert document["filed_date"] == opinion["decision_date"]
        assert document["source_url"] == opinion["pdf_url"]
        assert document["mime_type"] == "application/pdf"
        assert document["access_state"] == "public"
        assert document["docket_entry_id"] is not None
    finally:
        db.close()


def test_dc_calendar_hearings_project_as_occurrences_while_artifacts_stay_snapshots(
    tmp_path,
):
    fixture_path = Path(
        "tests/fixtures/public_records/dc_superior_calendar/today_page.html"
    )
    page = query_dc_superior_calendar.parse_calendar_html(
        fixture_path.read_text(encoding="utf-8"),
        kind="today",
        native_page=0,
        source_url=query_dc_superior_calendar.TODAY_URL,
    )
    fetched = query_dc_superior_calendar.FetchedText(
        text="fixture",
        source_url=query_dc_superior_calendar.TODAY_URL,
        headers={"date": "Thu, 30 Jul 2026 06:40:11 GMT"},
    )
    records = query_dc_superior_calendar._html_hearing_records(
        [(page, fetched)],
        kind="today",
    )
    source_query = PublicRecordsQuery(
        source=query_dc_superior_calendar.TODAY_METADATA,
        jurisdiction=query_dc_superior_calendar.JURISDICTION,
        query=QueryMetadata(
            operation="search",
            parameters={"case_number": "2026-LTB-005132", "max_pages": 1},
        ),
    )
    envelope_value = PublicRecordsResult.success(
        source_query,
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "dc-calendar.db"

    report = ingest_envelope(envelope_value, court_db=db_path)

    assert report["source_id"] == query_dc_superior_calendar.TODAY_SOURCE_ID
    assert report["projected"]["cases"] == len(records)
    assert report["projected"]["docket_entries"] == len(records)
    assert report["projected"]["documents"] == 0
    assert report["snapshot_only"]["record_count"] == 0

    db = connect_courts(db_path)
    try:
        case = db.execute(
            """
            SELECT c.raw_case_number, c.caption, c.access_state, ct.state_code
            FROM case_record c
            JOIN court ct ON ct.court_id=c.court_id
            """
        ).fetchone()
        assert case is not None
        assert case["raw_case_number"] == "2026-LTB-005132"
        assert case["access_state"] == "public"
        assert case["state_code"] == "DC"

        entries = db.execute(
            """
            SELECT native_entry_id, event_type, event_date, event_time,
                   judge, location, document_available, raw_json
            FROM docket_entry
            ORDER BY native_entry_id
            """
        ).fetchall()
        assert len(entries) == len(records)
        assert {row["event_type"] for row in entries} == {"hearing"}
        assert {row["event_date"] for row in entries} == {"2026-07-30"}
        assert {row["event_time"] for row in entries} == {
            "09:00:00-04:00"
        }
        assert all(row["judge"] for row in entries)
        assert all(row["location"] for row in entries)
        assert {row["document_available"] for row in entries} == {0}
        assert any(
            json.loads(row["raw_json"]).get("remote_hearing_url")
            for row in entries
        )
    finally:
        db.close()

    artifact = query_dc_superior_calendar._artifact_record(
        query_dc_superior_calendar.CalendarArtifact(
            family="tax",
            artifact_type="tax_show_cause",
            label="Tax Sale Show Cause Calendar",
            url="https://www.dccourts.gov/sites/default/files/tax-calendar.pdf",
        ),
        source_id=query_dc_superior_calendar.TAX_SOURCE_ID,
        index_url=query_dc_superior_calendar.TAX_URL,
        response_date="2026-07-30",
    )
    artifact_query = PublicRecordsQuery(
        source=query_dc_superior_calendar.TAX_METADATA,
        jurisdiction=query_dc_superior_calendar.JURISDICTION,
        query=QueryMetadata(
            operation="artifacts",
            parameters={"family": "tax"},
        ),
    )
    artifact_report = ingest_envelope(
        PublicRecordsResult.success(
            artifact_query,
            [artifact],
            retrieved_at="2026-07-30T12:01:00Z",
        ).to_dict(),
        court_db=db_path,
    )
    assert artifact_report["projected"]["cases"] == 0
    assert artifact_report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"court_calendar_artifact": 1},
    }


def test_fresno_hearing_ruling_and_probate_records_project_with_lineage(
    tmp_path,
):
    fixture_root = Path(
        "tests/fixtures/public_records/fresno_superior_court"
    )
    calendar_record = query_fresno_superior_court.parse_calendar_text(
        (fixture_root / "calendar_text.txt").read_text(encoding="utf-8"),
        source_url=(
            "https://www.fresno.courts.ca.gov/system/files/general/"
            "merged-calendar-07302026.pdf"
        ),
        artifact_sha256="a" * 64,
    )[0]
    ruling_record = next(
        record
        for record in query_fresno_superior_court.parse_tentative_rulings_text(
            (fixture_root / "tentative_text.txt").read_text(encoding="utf-8"),
            source_url=(
                "https://www.fresno.courts.ca.gov/system/files/"
                "tentative-rulings/07-30-26-dept-501-gsf.pdf"
            ),
            artifact_sha256="b" * 64,
        )
        if record["record_kind"] == "tentative_ruling"
    )
    search = query_fresno_superior_court.parse_probate_search_page(
        (fixture_root / "probate_search.html").read_text(encoding="utf-8")
    )
    probate_record = query_fresno_superior_court.parse_probate_results(
        (fixture_root / "probate_results.html").read_text(encoding="utf-8"),
        requested_case_number="19CEPR00967",
        search_schema_fingerprint=search.schema_fingerprint,
    ).records[0]
    db_path = tmp_path / "fresno.db"

    for source_id, operation, record in (
        (
            query_fresno_superior_court.CALENDAR_SOURCE_ID,
            "calendar",
            calendar_record,
        ),
        (
            query_fresno_superior_court.RULINGS_SOURCE_ID,
            "rulings",
            ruling_record,
        ),
        (
            query_fresno_superior_court.PROBATE_SOURCE_ID,
            "probate-notes",
            probate_record,
        ),
    ):
        query = PublicRecordsQuery(
            source=query_fresno_superior_court.SOURCE_METADATA[source_id],
            jurisdiction=query_fresno_superior_court.JURISDICTION,
            query=QueryMetadata(operation=operation, parameters={}),
        )
        report = ingest_envelope(
            PublicRecordsResult.success(
                query,
                [record],
                retrieved_at="2026-07-30T12:00:00Z",
            ).to_dict(),
            court_db=db_path,
        )
        assert report["projected"]["cases"] == 1
        assert report["projected"]["docket_entries"] == 1

    db = connect_courts(db_path)
    try:
        cases = db.execute(
            """
            SELECT c.source_id, c.raw_case_number, c.case_type,
                   c.access_state, ct.state_code, ct.county_geoid
            FROM case_record c
            JOIN court ct ON ct.court_id=c.court_id
            """
        ).fetchall()
        assert {row["source_id"] for row in cases} == {
            query_fresno_superior_court.CALENDAR_SOURCE_ID,
            query_fresno_superior_court.RULINGS_SOURCE_ID,
            query_fresno_superior_court.PROBATE_SOURCE_ID,
        }
        assert {row["access_state"] for row in cases} == {"public"}
        assert {row["state_code"] for row in cases} == {"CA"}
        assert {row["county_geoid"] for row in cases} == {"06019"}

        entries = db.execute(
            """
            SELECT source_id, event_code, event_type, event_date, status,
                   document_available, raw_json
            FROM docket_entry
            """
        ).fetchall()
        entries_by_source = {row["source_id"]: row for row in entries}
        calendar_entry = entries_by_source[
            query_fresno_superior_court.CALENDAR_SOURCE_ID
        ]
        assert calendar_entry["event_type"] == "hearing"
        assert calendar_entry["document_available"] == 0

        ruling_entry = entries_by_source[
            query_fresno_superior_court.RULINGS_SOURCE_ID
        ]
        assert ruling_entry["event_type"] == "tentative_ruling"
        assert ruling_entry["status"] == "tentative"
        assert ruling_entry["document_available"] == 1

        probate_entry = entries_by_source[
            query_fresno_superior_court.PROBATE_SOURCE_ID
        ]
        assert probate_entry["event_code"] == "probate_note"
        assert probate_entry["document_available"] == 0
        assert json.loads(probate_entry["raw_json"])["record_lineage"] == (
            "examiner_note_not_part_of_official_court_file"
        )

        document = db.execute(
            """
            SELECT source_id, document_type, sha256, mime_type, access_state
            FROM document_artifact
            """
        ).fetchone()
        assert document is not None
        assert document["source_id"] == (
            query_fresno_superior_court.RULINGS_SOURCE_ID
        )
        assert document["document_type"] == (
            "civil_tentative_ruling_pdf"
        )
        assert document["sha256"] == "b" * 64
        assert document["mime_type"] == "application/pdf"
        assert document["access_state"] == "public"
    finally:
        db.close()
