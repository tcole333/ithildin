import hashlib
import json
from pathlib import Path

import pytest

from tools import query_state_courts
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    SourceMetadata,
)
from tools.public_records_store import connect_courts
from tools.seed_public_records_catalog import seed_catalog


def _seed_courts(path, artifact_path):
    artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    db = connect_courts(path)
    try:
        db.execute(
            """
            INSERT INTO court(
                court_id, source_id, native_court_id, name, state_code,
                county_geoid, court_level
            ) VALUES (
                'wi-dane-circuit', 'us-wi-wcca-rest', '13',
                'Dane County Circuit Court', 'WI', '55025', 'trial'
            )
            """
        )
        public_case = db.execute(
            """
            INSERT INTO case_record(
                source_id, court_id, raw_case_number, display_case_number,
                caption, case_type, filing_date, status, access_state
            ) VALUES (
                'us-wi-wcca-rest', 'wi-dane-circuit', '2025CV000001',
                '2025CV1', 'ACME LLC v. PUBLIC PARTY', 'civil',
                '2025-01-02', 'open', 'public'
            )
            """
        ).lastrowid
        public_party = db.execute(
            """
            INSERT INTO case_party(
                case_id, sequence_no, role, raw_name, normalized_name, access_state
            ) VALUES (?, 1, 'plaintiff', 'ACME LLC', 'ACME LLC', 'public')
            """,
            (public_case,),
        ).lastrowid
        attorney = db.execute(
            """
            INSERT INTO attorney(
                source_id, raw_name, normalized_name, bar_id
            ) VALUES (
                'us-wi-wcca-rest', 'PUBLIC COUNSEL', 'PUBLIC COUNSEL', '123'
            )
            """
        ).lastrowid
        db.execute(
            """
            INSERT INTO case_representation(
                case_id, case_party_id, attorney_id
            ) VALUES (?, ?, ?)
            """,
            (public_case, public_party, attorney),
        )
        docket = db.execute(
            """
            INSERT INTO docket_entry(
                case_id, source_id, native_entry_id, sequence_no,
                raw_text, filed_date, document_available, access_state
            ) VALUES (
                ?, 'us-wi-wcca-rest', 'entry-1', '1',
                'Complaint filed', '2025-01-02', 1, 'public'
            )
            """,
            (public_case,),
        ).lastrowid
        db.execute(
            """
            INSERT INTO document_artifact(
                case_id, docket_entry_id, source_id, native_document_id,
                document_type, filed_date, sha256, mime_type, storage_path,
                access_state
            ) VALUES (
                ?, ?, 'us-wi-wcca-rest', 'doc-public', 'complaint',
                '2025-01-02', ?, 'application/pdf', ?, 'public'
            )
            """,
            (public_case, docket, artifact_sha256, str(artifact_path)),
        )

        sealed_case = db.execute(
            """
            INSERT INTO case_record(
                source_id, court_id, raw_case_number, caption, case_type,
                filing_date, status, access_state
            ) VALUES (
                'us-wi-wcca-rest', 'wi-dane-circuit', '2025CV000002',
                'SECRET PERSON v. PRIVATE PARTY', 'civil',
                '2025-01-03', 'sealed', 'sealed'
            )
            """
        ).lastrowid
        db.execute(
            """
            INSERT INTO case_party(
                case_id, sequence_no, role, raw_name, access_state
            ) VALUES (?, 1, 'plaintiff', 'SECRET PERSON', 'sealed')
            """,
            (sealed_case,),
        )
        sealed_docket = db.execute(
            """
            INSERT INTO docket_entry(
                case_id, source_id, native_entry_id, sequence_no,
                raw_text, document_available, access_state
            ) VALUES (
                ?, 'us-wi-wcca-rest', 'entry-secret', '1',
                'Sealed filing', 1, 'sealed'
            )
            """,
            (sealed_case,),
        ).lastrowid
        db.execute(
            """
            INSERT INTO document_artifact(
                case_id, docket_entry_id, source_id, native_document_id,
                storage_path, access_state
            ) VALUES (
                ?, ?, 'us-wi-wcca-rest', 'doc-secret', ?, 'sealed'
            )
            """,
            (sealed_case, sealed_docket, str(artifact_path)),
        )
        db.commit()
    finally:
        db.close()


def _parse(*values):
    return query_state_courts.build_parser().parse_args(list(values))


def _oregon_calendar_fixture_envelope():
    adapter = query_state_courts.query_oregon_court_calendar
    fixture_root = (
        Path(__file__).parent / "fixtures" / "public_records" / "oregon_court_calendar"
    )
    landing = adapter.parse_landing_html(
        (fixture_root / "landing.html").read_text(encoding="utf-8")
    )
    location = adapter._resolve_location(landing, "Deschutes")
    form = adapter.parse_search_form_html(
        (fixture_root / "search_form.html").read_text(encoding="utf-8"),
        location=location,
    )
    results = adapter.parse_results_html(
        (fixture_root / "results.html").read_text(encoding="utf-8")
    )
    records = adapter.normalize_cases(
        adapter.OregonCalendarBatch(
            location=location,
            form=form,
            payload=dict(results.request_parameters),
            results=results,
        )
    )
    source_query = PublicRecordsQuery(
        source=adapter.SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=adapter.STATE_GEOID,
            name="Oregon",
            state_code=adapter.STATE_CODE,
        ),
        query=QueryMetadata(
            operation="calendar",
            parameters={"location": location.name},
        ),
    )
    return PublicRecordsResult.success(
        source_query,
        records,
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()


def _acis_detail():
    return {
        "source": {
            "source_id": query_state_courts.ACIS_SOURCE_ID,
            "name": "Florida Appellate Case Information System",
            "official_url": "https://acis.flcourts.gov/portal/",
            "license_or_terms_url": None,
            "authority": "Florida Courts",
            "platform_family": "ACIS",
        },
        "roles": ["court"],
        "capabilities": [
            {"name": "search_parties", "supported": True},
            {"name": "search_cases", "supported": True},
            {"name": "list_docket_entries", "supported": True},
            {"name": "fetch_document", "supported": True},
        ],
        "latest_access_review": {"access_class": "A"},
    }


class _ACISCatalog:
    def __init__(self, _path=None, *, allowed=True):
        self.allowed = allowed

    def show_source(self, source_id):
        if source_id != query_state_courts.ACIS_SOURCE_ID:
            raise AssertionError(source_id)
        return _acis_detail()

    def machine_acquisition_decision(self, source_id):
        if source_id != query_state_courts.ACIS_SOURCE_ID:
            raise AssertionError(source_id)
        if self.allowed:
            return {
                "source_id": source_id,
                "allowed": True,
                "access_class": "A",
                "reason": "review permits machine acquisition",
                "reason_code": "allowed",
            }
        return {
            "source_id": source_id,
            "allowed": False,
            "access_class": "C",
            "reason": "interactive route requires manual use",
            "reason_code": "automation_not_approved",
        }

    def list_sources(self, *, domain, jurisdiction=None):
        assert domain == "court"
        return [
            {
                "source_id": query_state_courts.ACIS_SOURCE_ID,
                "name": "Florida Appellate Case Information System",
                "official_url": "https://acis.flcourts.gov/portal/",
                "jurisdiction_id": jurisdiction or "FL",
            }
        ]


def _acis_envelope(operation="search"):
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id=query_state_courts.ACIS_SOURCE_ID,
            name="Florida Appellate Case Information System",
            source_role="court_docket",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="FL",
            name="Florida",
            state_code="FL",
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={"selector": "EXAMPLE"},
            requested_limit=7,
        ),
    )
    return PublicRecordsResult.success(query, []).to_dict()


def test_local_court_queries_default_exclude_restricted_material(tmp_path, monkeypatch):
    db_path = tmp_path / "courts.db"
    artifact = tmp_path / "complaint.pdf"
    artifact.write_bytes(b"%PDF-public")
    _seed_courts(db_path, artifact)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    public_search = query_state_courts.execute(
        _parse("search", "ACME", "--court-db", str(db_path))
    )
    sealed_search = query_state_courts.execute(
        _parse("search", "SECRET", "--court-db", str(db_path))
    )
    sealed_case = query_state_courts.execute(
        _parse("case", "2025CV000002", "--court-db", str(db_path))
    )
    docket = query_state_courts.execute(
        _parse("docket", "2025CV000001", "--court-db", str(db_path))
    )
    documents = query_state_courts.execute(
        _parse("documents", "2025CV000001", "--court-db", str(db_path))
    )

    assert public_search["status"] == "ok"
    assert public_search["records"][0]["parties"][0]["raw_name"] == "ACME LLC"
    assert sealed_search["status"] == "partial"
    assert sealed_search["records"] == []
    assert sealed_search["errors"][0]["code"] == "local_cache_miss"
    assert sealed_case["status"] == "restricted"
    tombstone = sealed_case["records"][0]
    assert tombstone["record_kind"] == "case_restriction_tombstone"
    assert tombstone["raw_case_number"] == "2025CV000002"
    assert tombstone["access_state"] == "sealed"
    assert "caption" not in tombstone
    assert "parties" not in tombstone
    assert docket["records"][0]["native_entry_id"] == "entry-1"
    assert documents["records"][0]["native_document_id"] == "doc-public"
    assert all(record["access_state"] == "public" for record in documents["records"])


def test_oregon_adapter_calendar_roundtrips_multiple_cases_and_hearings(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "oregon-calendar.db"
    envelope = _oregon_calendar_fixture_envelope()
    report = ingest_envelope(envelope, court_db=db_path)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    criminal = query_state_courts.execute(
        _parse(
            "calendar",
            "26CR10001",
            "--jurisdiction",
            "OR",
            "--court-db",
            str(db_path),
        )
    )
    family = query_state_courts.execute(
        _parse(
            "calendar",
            "26DR20002",
            "--jurisdiction",
            "OR",
            "--court-db",
            str(db_path),
        )
    )

    assert report["projected"]["cases"] == 2
    assert report["projected"]["docket_entries"] == 3
    assert criminal["status"] == "ok"
    assert [
        (
            record["event_code"],
            record["event_type"],
            record["event_date"],
            record["event_time"],
            record.get("judge"),
            record.get("location"),
            record.get("status"),
        )
        for record in criminal["records"]
    ] == [
        (
            "HEARING",
            "hearing",
            "2026-07-29",
            "08:30:00",
            "Flint, Bethany",
            "Courtroom 2D",
            "Active Warrant",
        ),
        (
            "HEARING",
            "hearing",
            "2026-07-30",
            "13:30:00",
            "Miller, Walter R",
            "Courtroom 1A",
            None,
        ),
    ]
    assert family["status"] == "ok"
    assert len(family["records"]) == 1
    family_hearing = family["records"][0]
    assert family_hearing["event_type"] == "hearing"
    assert family_hearing["event_time"] == "09:00:00"
    assert "judge" not in family_hearing
    assert "location" not in family_hearing
    assert "status" not in family_hearing

    db = connect_courts(db_path)
    try:
        raw = json.loads(
            db.execute(
                """
                SELECT raw_json FROM docket_entry
                WHERE native_entry_id=?
                """,
                (family_hearing["native_entry_id"],),
            ).fetchone()["raw_json"]
        )
        raw.pop("event_type")
        raw["event_code"] = "future_hearing"
        db.execute(
            """
            UPDATE docket_entry
            SET event_code='future_hearing', event_type=NULL, raw_json=?
            WHERE native_entry_id=?
            """,
            (json.dumps(raw), family_hearing["native_entry_id"]),
        )
        db.commit()
    finally:
        db.close()

    legacy_alias = query_state_courts.execute(
        _parse(
            "calendar",
            "26DR20002",
            "--court-db",
            str(db_path),
        )
    )
    assert legacy_alias["status"] == "ok"
    assert legacy_alias["records"][0]["event_code"] == "future_hearing"
    assert "event_type" not in legacy_alias["records"][0]


def test_local_calendar_reads_legacy_future_hearing_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy-calendar.db"
    db = connect_courts(db_path)
    try:
        db.execute(
            """
            INSERT INTO court(
                court_id, source_id, native_court_id, name, state_code
            ) VALUES (
                'legacy-circuit', 'legacy-calendar-source', 'legacy',
                'Legacy Circuit Court', 'OR'
            )
            """
        )
        case_id = db.execute(
            """
            INSERT INTO case_record(
                source_id, court_id, raw_case_number, caption
            ) VALUES (
                'legacy-calendar-source', 'legacy-circuit',
                'LEGACY-100', 'Legacy calendar case'
            )
            """
        ).lastrowid
        db.execute(
            """
            INSERT INTO docket_entry(
                case_id, source_id, native_entry_id, event_code,
                raw_text, event_date, raw_json
            ) VALUES (
                ?, 'legacy-calendar-source', 'legacy-hearing',
                'future_hearing', 'Legacy scheduled hearing',
                '2026-08-12', ?
            )
            """,
            (
                case_id,
                json.dumps(
                    {
                        "event_time": "10:15",
                        "judge": "Legacy Judge",
                        "location": "Legacy Courtroom",
                        "status": "Scheduled",
                    }
                ),
            ),
        )
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse("calendar", "LEGACY-100", "--court-db", str(db_path))
    )

    assert payload["status"] == "ok"
    assert payload["records"][0]["event_code"] == "future_hearing"
    assert payload["records"][0]["event_time"] == "10:15"
    assert payload["records"][0]["judge"] == "Legacy Judge"
    assert payload["records"][0]["location"] == "Legacy Courtroom"
    assert payload["records"][0]["status"] == "Scheduled"
    assert "event_type" not in payload["records"][0]


def test_statewide_oregon_calendar_identity_is_exposed_as_gap_metadata(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "oregon-statewide-calendar.db"
    envelope = _oregon_calendar_fixture_envelope()
    adapter = query_state_courts.query_oregon_court_calendar
    fixture_root = (
        Path(__file__).parent / "fixtures" / "public_records" / "oregon_court_calendar"
    )
    landing = adapter.parse_landing_html(
        (fixture_root / "landing.html").read_text(encoding="utf-8")
    )
    statewide = adapter._resolve_location(landing, "All Locations")
    for record in envelope["records"]:
        record["court"] = adapter._court_payload(statewide)
    ingest_envelope(envelope, court_db=db_path)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse("case", "26CR10001", "--court-db", str(db_path))
    )

    assert payload["status"] == "ok"
    assert payload["records"][0]["identity_gap"] == {
        "field": "court",
        "state": "aggregate_location",
        "resolution": "concrete_court_unresolved",
    }


def test_local_case_query_distinguishes_native_ids_for_shared_case_number(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "courts.db"
    db = connect_courts(db_path)
    try:
        db.execute(
            """
            INSERT INTO court(
                court_id, source_id, native_court_id, name, state_code
            ) VALUES (
                'tx-bexar-historical', 'us-tx-bexar', 'HC',
                'Bexar Historical Cases', 'TX'
            )
            """
        )
        for source_internal_id in ("doc-101", "doc-102"):
            db.execute(
                """
                INSERT INTO case_record(
                    source_id, court_id, raw_case_number,
                    source_internal_id, caption
                ) VALUES (
                    'us-tx-bexar', 'tx-bexar-historical', '6707', ?, ?
                )
                """,
                (source_internal_id, f"Case {source_internal_id}"),
            )
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse("case", "6707", "--court-db", str(db_path))
    )

    assert payload["status"] == "ok"
    assert {
        (record["raw_case_number"], record["source_internal_id"])
        for record in payload["records"]
    } == {("6707", "doc-101"), ("6707", "doc-102")}
    assert {record["canonical_ref"] for record in payload["records"]} == {
        "STATECOURT:us-tx-bexar/tx-bexar-historical/6707/case/doc-101",
        "STATECOURT:us-tx-bexar/tx-bexar-historical/6707/case/doc-102",
    }


@pytest.mark.parametrize(
    ("operation", "identifier_field", "identifier_prefix"),
    (
        ("docket", "native_entry_id", "entry"),
        ("claims", "native_claim_id", "claim"),
        ("documents", "native_document_id", "document"),
    ),
)
def test_local_case_children_use_one_global_page_across_shared_case_numbers(
    operation,
    identifier_field,
    identifier_prefix,
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "courts.db"
    db = connect_courts(db_path)
    try:
        db.execute(
            """
            INSERT INTO court(
                court_id, source_id, native_court_id, name, state_code
            ) VALUES (
                'shared-number-court', 'shared-number-source', 'shared',
                'Shared Number Court', 'CO'
            )
            """
        )
        for case_index in range(1, 4):
            case_id = db.execute(
                """
                INSERT INTO case_record(
                    source_id, court_id, raw_case_number,
                    source_internal_id, caption, filing_date
                ) VALUES (
                    'shared-number-source', 'shared-number-court',
                    'SHARED-CASE', ?, ?, ?
                )
                """,
                (
                    f"case-{case_index}",
                    f"Shared case {case_index}",
                    f"2026-01-0{case_index}",
                ),
            ).lastrowid
            for child_index in range(1, 3):
                db.execute(
                    """
                    INSERT INTO docket_entry(
                        case_id, source_id, native_entry_id,
                        sequence_no, raw_text
                    ) VALUES (?, 'shared-number-source', ?, ?, ?)
                    """,
                    (
                        case_id,
                        f"entry-{case_index}-{child_index}",
                        str(child_index),
                        f"Docket {case_index}-{child_index}",
                    ),
                )
                db.execute(
                    """
                    INSERT INTO case_claim(
                        case_id, source_id, native_claim_id,
                        sequence_no, claimant_raw
                    ) VALUES (?, 'shared-number-source', ?, ?, ?)
                    """,
                    (
                        case_id,
                        f"claim-{case_index}-{child_index}",
                        child_index,
                        f"Claimant {case_index}-{child_index}",
                    ),
                )
                db.execute(
                    """
                    INSERT INTO document_artifact(
                        case_id, source_id, native_document_id,
                        document_type, filed_date
                    ) VALUES (
                        ?, 'shared-number-source', ?, 'filing', ?
                    )
                    """,
                    (
                        case_id,
                        f"document-{case_index}-{child_index}",
                        f"2026-01-0{child_index}",
                    ),
                )
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    records = []
    cursors = []
    cursor = None
    while True:
        values = [
            operation,
            "SHARED-CASE",
            "--court-db",
            str(db_path),
            "--limit",
            "2",
        ]
        if cursor:
            values.extend(["--cursor", cursor])
        payload = query_state_courts.execute(_parse(*values))
        assert payload["status"] == "ok"
        records.extend(payload["records"])
        cursor = payload.get("next_cursor")
        if cursor is None:
            break
        assert cursor not in cursors
        cursors.append(cursor)

    assert cursors == ["sqlite:offset:2", "sqlite:offset:4"]
    assert [record[identifier_field] for record in records] == [
        f"{identifier_prefix}-{case_index}-{child_index}"
        for case_index in (3, 2, 1)
        for child_index in (1, 2)
    ]
    assert [record["case"]["source_internal_id"] for record in records] == [
        f"case-{case_index}" for case_index in (3, 2, 1) for _child_index in (1, 2)
    ]


def test_empty_local_sidecar_is_unavailable_and_writes_artifact(tmp_path, monkeypatch):
    db_path = tmp_path / "empty-courts.db"
    output_path = tmp_path / "empty-search.json"
    logged = []
    monkeypatch.setattr(
        query_state_courts,
        "log_search",
        lambda *args: logged.append(args),
    )
    args = _parse(
        "search",
        "ACME",
        "--jurisdiction",
        "55",
        "--court-db",
        str(db_path),
        "--output",
        str(output_path),
    )

    payload = query_state_courts.execute(args)
    query_state_courts._emit(payload, args)

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == artifact
    assert artifact["status"] == "unavailable"
    assert artifact["records"] == []
    assert artifact["errors"][0]["code"] == "no_coverage"
    assert not any(
        artifact["errors"][0]["details"]["coverage"]["sidecar"]["row_counts"].values()
    )
    assert logged[0][1:] == (
        query_state_courts.LOCAL_SOURCE_ID,
        None,
    )


def test_local_download_verifies_hash_and_excludes_sealed_document(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "courts.db"
    artifact = tmp_path / "complaint.pdf"
    destination = tmp_path / "copy.pdf"
    artifact.write_bytes(b"%PDF-public")
    _seed_courts(db_path, artifact)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    public = query_state_courts.execute(
        _parse(
            "download",
            "doc-public",
            "--court-db",
            str(db_path),
            "--destination",
            str(destination),
        )
    )
    sealed = query_state_courts.execute(
        _parse("download", "doc-secret", "--court-db", str(db_path))
    )

    assert public["status"] == "ok"
    assert public["records"][0]["download_status"] == "copied"
    assert destination.read_bytes() == artifact.read_bytes()
    assert sealed["status"] == "restricted"
    tombstone = sealed["records"][0]
    assert tombstone == {
        "access_state": "sealed",
        "native_document_id": "doc-secret",
        "record_kind": "document_restriction_tombstone",
        "restriction": {
            "current_access_state": "sealed",
            "restriction_event": None,
        },
        "source_id": "us-wi-wcca-rest",
    }
    assert sealed["errors"][0]["code"] == "known_record_restricted"


def test_local_court_uncovered_jurisdiction_is_not_an_empty_result(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "courts.db"
    artifact = tmp_path / "complaint.pdf"
    artifact.write_bytes(b"%PDF-public")
    _seed_courts(db_path, artifact)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse(
            "search",
            "ACME",
            "--jurisdiction",
            "NY",
            "--court-db",
            str(db_path),
        )
    )

    assert payload["status"] == "unavailable"
    error = payload["errors"][0]
    assert error["code"] == "local_scope_not_covered"
    coverage = error["details"]["coverage"]
    assert coverage["authoritative_zero"] is False
    assert coverage["sidecar"]["requested_scope_counts"] == {
        "cases": 0,
        "courts": 0,
        "public_cases": 0,
    }
    assert "plan_action" in error["details"]["route_guidance"]


def test_local_court_preserves_exact_source_authoritative_zero(tmp_path, monkeypatch):
    db_path = tmp_path / "courts.db"
    source_query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id="us-wi-test-courts",
            name="Wisconsin test courts",
            source_role="court_docket",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="WI",
            name="Wisconsin",
            state_code="WI",
        ),
        query=QueryMetadata(
            operation="search",
            parameters={"selector": "NO SUCH CASE"},
            requested_limit=50,
        ),
    )
    ingest_envelope(
        PublicRecordsResult.success(
            source_query,
            [],
            retrieved_at="2026-07-28T12:00:00Z",
        ).to_dict(),
        court_db=db_path,
    )
    logged = []
    monkeypatch.setattr(
        query_state_courts,
        "log_search",
        lambda *args: logged.append(args),
    )

    payload = query_state_courts.execute(
        _parse(
            "search",
            "NO SUCH CASE",
            "--jurisdiction",
            "WI",
            "--court-db",
            str(db_path),
        )
    )

    assert payload["status"] == "no_results"
    assert payload["warnings"][0].startswith(
        "Exact source-query zero preserved from us-wi-test-courts"
    )
    assert logged[0][2] == 0


def test_denver_county_calendar_route_preserves_exact_date_and_caller_slice(
    tmp_path,
    monkeypatch,
):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    calls = []
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.DENVER_COUNTY_DOCKET_SOURCE_ID
    ]["calendar"]

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return PublicRecordsResult.success(
            route.adapter.build_query(adapter_args),
            [],
        )

    monkeypatch.setattr(route.adapter, "execute", fake_execute)

    payload = query_state_courts.execute(
        _parse(
            "calendar",
            "3A",
            "--source",
            query_state_courts.DENVER_COUNTY_DOCKET_SOURCE_ID,
            "--jurisdiction",
            "08031",
            "--court-id",
            "co-denver-county-court",
            "--hearing-date",
            "2026-07-29",
            "--limit",
            "7",
            "--cursor",
            "denver-county-docket:offset:14",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert decision["allowed"] is True
    assert adapter_args.command == "calendar"
    assert adapter_args.courtroom == "3A"
    assert adapter_args.court_date == "2026-07-29"
    assert adapter_args.limit == 7
    assert adapter_args.offset == 14
    assert payload["query"]["query"]["operation"] == "calendar"


def test_denver_county_calendar_route_has_no_implicit_record_limit():
    args = _parse(
        "calendar",
        "3A",
        "--source",
        query_state_courts.DENVER_COUNTY_DOCKET_SOURCE_ID,
        "--hearing-date",
        "2026-07-29",
    )

    translated = query_state_courts._denver_county_docket_args(
        args,
        "calendar",
    )

    assert translated.limit is None
    assert translated.offset == 0


def test_denver_county_calendar_does_not_reinterpret_a_date_range():
    args = _parse(
        "calendar",
        "3A",
        "--source",
        query_state_courts.DENVER_COUNTY_DOCKET_SOURCE_ID,
        "--after",
        "2026-07-29",
    )

    with pytest.raises(ValueError, match="requires --hearing-date"):
        query_state_courts._denver_county_docket_args(args, "calendar")


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    (
        (
            ("--first-name", "JANE"),
            {
                "party_first_name": "JANE",
                "party_last_name": "DOE",
                "business_name": None,
                "attorney_last_name": None,
            },
        ),
        (
            ("--entity-kind", "organization"),
            {
                "party_first_name": None,
                "party_last_name": None,
                "business_name": "DOE",
                "attorney_last_name": None,
            },
        ),
        (
            ("--search-scope", "attorney", "--first-name", "JANE"),
            {
                "party_first_name": None,
                "party_last_name": None,
                "business_name": None,
                "attorney_first_name": "JANE",
                "attorney_last_name": "DOE",
            },
        ),
    ),
)
def test_colorado_judicial_unified_name_routes_have_no_hidden_cap(
    extra_args,
    expected,
):
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID
    ]["search"]
    args = _parse(
        "search",
        "DOE",
        "--source",
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID,
        "--jurisdiction",
        "CO",
        "--county",
        "Denver",
        "--courthouse",
        "2_denver",
        "--case-type",
        "CV",
        *extra_args,
    )

    translated = route.translate(args, route.adapter_command)

    assert translated.command == "search"
    assert translated.limit is None
    assert translated.county == "Denver"
    assert translated.courthouse == "2_denver"
    assert translated.case_class == "CV"
    for field, value in expected.items():
        assert getattr(translated, field) == value


def test_colorado_judicial_maps_equal_common_bounds_to_specific_date():
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID
    ]["search"]
    args = _parse(
        "search",
        "DOE",
        "--source",
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID,
        "--after",
        "2026-07-29",
        "--before",
        "2026-07-29",
    )

    translated = route.translate(args, route.adapter_command)

    assert translated.date_range == "specific_date"
    assert translated.specific_date == "2026-07-29"


@pytest.mark.parametrize(
    "date_args",
    (
        ("--after", "2026-07-29"),
        ("--before", "2026-07-29"),
        (
            "--after",
            "2026-07-28",
            "--before",
            "2026-07-29",
        ),
    ),
)
def test_colorado_judicial_rejects_unrepresentable_common_date_bounds(
    date_args,
):
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID
    ]["search"]
    args = _parse(
        "search",
        "DOE",
        "--source",
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID,
        *date_args,
    )

    with pytest.raises(ValueError, match="same hearing date"):
        route.translate(args, route.adapter_command)


@pytest.mark.parametrize(
    "search_scope",
    ("style", "case-number", "partial-case-number", "trial-case-number"),
)
def test_colorado_judicial_rejects_other_adapters_search_scopes(search_scope):
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID
    ]["search"]
    args = _parse(
        "search",
        "DOE",
        "--source",
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID,
        "--search-scope",
        search_scope,
    )

    with pytest.raises(ValueError, match="party or attorney"):
        route.translate(args, route.adapter_command)


def test_colorado_judicial_route_passes_catalog_decision(
    tmp_path,
    monkeypatch,
):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    calls = []
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.COLORADO_JUDICIAL_SOURCE_ID
    ]["search"]

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return PublicRecordsResult.success(
            route.adapter.build_query(adapter_args),
            [],
        )

    monkeypatch.setattr(route.adapter, "execute", fake_execute)

    payload = query_state_courts.execute(
        _parse(
            "search",
            "EXAMPLE LLC",
            "--source",
            query_state_courts.COLORADO_JUDICIAL_SOURCE_ID,
            "--entity-kind",
            "organization",
            "--limit",
            "7",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.business_name == "EXAMPLE LLC"
    assert adapter_args.limit == 7
    assert decision["allowed"] is True
    assert decision["source_id"] == (query_state_courts.COLORADO_JUDICIAL_SOURCE_ID)


def test_nyscef_and_formal_feeds_surface_catalog_access_statuses(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    logged = []
    monkeypatch.setattr(
        query_state_courts, "log_search", lambda *args: logged.append(args)
    )

    nyscef = query_state_courts.execute(
        _parse(
            "case",
            "156728/2019",
            "--source",
            "us-ny-nyscef",
            "--catalog-db",
            str(catalog_path),
            "--court-id",
            "ny-supreme",
        )
    )
    formal = query_state_courts.execute(
        _parse(
            "search",
            "ACME",
            "--source",
            "us-in-iocs-bulk",
            "--catalog-db",
            str(catalog_path),
        )
    )
    missing = query_state_courts.execute(
        _parse(
            "search",
            "ACME",
            "--source",
            "us-xx-missing-court",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert nyscef["status"] == "human_required"
    assert nyscef["errors"][0]["code"] == "automation_not_approved"
    assert nyscef["errors"][0]["details"]["manual_source_url"].startswith("https://")
    assert nyscef["errors"][0]["details"]["requested_action"]["operation"] == ("search")
    assert nyscef["query"]["query"]["operation"] == "case"
    assert (
        nyscef["errors"][0]["details"]["requested_action"]["router_operation"] == "case"
    )
    assert nyscef["errors"][0]["details"]["requested_action"]["selector"] == (
        "156728/2019"
    )
    assert formal["status"] == "unavailable"
    assert formal["errors"][0]["code"] == "access_review_required"
    assert missing["status"] == "unavailable"
    assert all(call[2] is None for call in logged)


def test_acis_live_route_dispatches_party_search_with_router_filters(
    monkeypatch,
):
    catalog = _ACISCatalog()
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: catalog,
    )
    calls = []
    route = query_state_courts.LIVE_ROUTES[query_state_courts.ACIS_SOURCE_ID]["search"]

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return _acis_envelope()

    monkeypatch.setattr(route.adapter, "execute", fake_execute)
    router_logs = []
    monkeypatch.setattr(
        query_state_courts,
        "log_search",
        lambda *args: router_logs.append(args),
    )

    payload = query_state_courts.execute(
        _parse(
            "search",
            "EXAMPLE LLC",
            "--source",
            query_state_courts.ACIS_SOURCE_ID,
            "--court-id",
            "court-resource-uuid",
            "--case-type",
            "civil",
            "--after",
            "2025-01-01",
            "--before",
            "2025-12-31",
            "--limit",
            "7",
            "--cursor",
            "acis:cursor",
            "--page-size",
            "25",
            "--max-records",
            "125",
            "--timeout",
            "8",
            "--minimum-interval",
            "0.1",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "search"
    assert adapter_args.query == "EXAMPLE LLC"
    assert adapter_args.search_scope == "party"
    assert adapter_args.match_mode == "match"
    assert adapter_args.court == "court-resource-uuid"
    assert adapter_args.case_type == "civil"
    assert adapter_args.after == "2025-01-01"
    assert adapter_args.filed_after == "2025-01-01"
    assert adapter_args.before == "2025-12-31"
    assert adapter_args.filed_before == "2025-12-31"
    assert adapter_args.limit == 7
    assert adapter_args.cursor == "acis:cursor"
    assert adapter_args.page_size == 25
    assert adapter_args.max_records == 125
    assert adapter_args.timeout == 8
    assert adapter_args.minimum_interval == 0.1
    assert decision["allowed"] is True
    assert router_logs == []


def test_acis_calendar_route_maps_dates_session_and_event_name(monkeypatch):
    catalog = _ACISCatalog()
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: catalog,
    )
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.ACIS_SOURCE_ID
    ]["calendar"]
    calls = []

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return _acis_envelope("calendar")

    monkeypatch.setattr(route.adapter, "execute", fake_execute)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse(
            "calendar",
            "Khouzam",
            "--source",
            query_state_courts.ACIS_SOURCE_ID,
            "--court-id",
            "court-resource-uuid",
            "--hearing-date",
            "2026-08-19",
            "--case-type",
            "Oral Argument",
            "--limit",
            "7",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "calendar"
    assert adapter_args.court == "court-resource-uuid"
    assert adapter_args.after == "2026-08-19"
    assert adapter_args.before == "2026-08-19"
    assert adapter_args.session_type == "Oral Argument"
    assert adapter_args.event_name == "Khouzam"
    assert adapter_args.events_only is False
    assert adapter_args.limit == 7
    assert decision["allowed"] is True


def test_acis_catalog_decision_precedes_adapter_dispatch(monkeypatch):
    catalog = _ACISCatalog(allowed=False)
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: catalog,
    )
    route = query_state_courts.LIVE_ROUTES[query_state_courts.ACIS_SOURCE_ID]["case"]
    adapter_calls = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda *args, **kwargs: adapter_calls.append((args, kwargs)),
    )
    router_logs = []
    monkeypatch.setattr(
        query_state_courts,
        "log_search",
        lambda *args: router_logs.append(args),
    )

    payload = query_state_courts.execute(
        _parse(
            "case",
            "SC2025-0001",
            "--source",
            query_state_courts.ACIS_SOURCE_ID,
        )
    )

    assert payload["status"] == "human_required"
    assert payload["errors"][0]["code"] == "automation_not_approved"
    assert payload["errors"][0]["details"]["manual_source_url"].startswith("https://")
    assert adapter_calls == []
    assert len(router_logs) == 1


def test_acis_live_case_envelope_can_be_ingested(monkeypatch, tmp_path):
    catalog = _ACISCatalog()
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: catalog,
    )
    route = query_state_courts.LIVE_ROUTES[query_state_courts.ACIS_SOURCE_ID]["case"]
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda _args, **_kwargs: _acis_envelope("case"),
    )
    ingested = []
    monkeypatch.setattr(
        query_state_courts,
        "ingest_envelope",
        lambda envelope, **kwargs: (
            ingested.append((envelope, kwargs))
            or {"status": "ingested", "projected": {"cases": 0}}
        ),
    )

    court_db = tmp_path / "courts.db"
    payload = query_state_courts.execute(
        _parse(
            "case",
            "SC2025-0001",
            "--source",
            query_state_courts.ACIS_SOURCE_ID,
            "--court-db",
            str(court_db),
            "--ingest",
        )
    )

    assert payload["ingest"]["status"] == "ingested"
    assert ingested[0][0]["query"]["source"]["source_id"] == (
        query_state_courts.ACIS_SOURCE_ID
    )
    assert ingested[0][1] == {"court_db": str(court_db)}


def test_local_ingest_is_rejected(monkeypatch):
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    with pytest.raises(ValueError, match="requires a live source"):
        query_state_courts.execute(_parse("search", "EXAMPLE LLC", "--ingest"))


def test_acis_download_translation_and_ingest_shape_are_explicit(monkeypatch):
    catalog = _ACISCatalog()
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: catalog,
    )
    route = query_state_courts.LIVE_ROUTES[query_state_courts.ACIS_SOURCE_ID][
        "download"
    ]
    calls = []

    def fake_execute(adapter_args, **_kwargs):
        calls.append(adapter_args)
        return _acis_envelope("download")

    monkeypatch.setattr(route.adapter, "execute", fake_execute)

    payload = query_state_courts.execute(
        _parse(
            "download",
            "document-uuid",
            "--source",
            query_state_courts.ACIS_SOURCE_ID,
            "--court-id",
            "court-resource-uuid",
            "--case-uuid",
            "case-uuid",
            "--destination",
            "document.pdf",
            "--ingest",
        )
    )

    assert calls[0].court_resource_uuid == "court-resource-uuid"
    assert calls[0].case_uuid == "case-uuid"
    assert calls[0].case_number is None
    assert calls[0].document_uuid == "document-uuid"
    assert calls[0].destination == "document.pdf"
    assert payload["ingest"] == {
        "status": "skipped",
        "reason": "download receipts are not case-shaped records",
    }


def test_live_source_reports_unsupported_unified_capability(monkeypatch):
    catalog = _ACISCatalog()
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: catalog,
    )
    search_route = query_state_courts.LIVE_ROUTES[query_state_courts.ACIS_SOURCE_ID][
        "search"
    ]
    monkeypatch.setitem(
        query_state_courts.LIVE_ROUTES,
        query_state_courts.ACIS_SOURCE_ID,
        {"search": search_route},
    )
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse(
            "case",
            "SC2025-0001",
            "--source",
            query_state_courts.ACIS_SOURCE_ID,
        )
    )

    assert payload["status"] == "unavailable"
    assert payload["errors"][0]["code"] == "capability_not_supported"
    assert payload["errors"][0]["details"]["source_guidance"]["unified_operations"] == [
        "search"
    ]


def test_acis_sources_output_includes_capabilities_and_guidance(monkeypatch):
    catalog = _ACISCatalog()
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: catalog,
    )

    payload = query_state_courts.execute(_parse("sources"))

    assert payload["status"] == "ok"
    source = payload["records"][0]
    assert source["capabilities"] == [
        "search_parties",
        "search_cases",
        "list_docket_entries",
        "fetch_document",
    ]
    assert source["query_guidance"]["mode"] == "unified_live"
    assert "query_florida_acis.py" in source["query_guidance"]["direct_tool"]
    assert source["query_guidance"]["unified_operations"] == [
        "calendar",
        "case",
        "docket",
        "documents",
        "download",
        "search",
    ]


def test_ny_law_reports_guidance_keeps_opinion_route_distinct() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.NY_LAW_REPORTS_SOURCE_ID
    )

    assert guidance["mode"] == "direct_tool"
    assert "query_ny_law_reports.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == []
    assert "complements" in guidance["note"]


def test_nyscef_guidance_exposes_local_fulltext_processing() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.NYSCEF_SOURCE_ID
    )

    assert guidance["mode"] == (
        "catalog_handoff_plus_local_fulltext"
    )
    assert "query_nyscef.py" in guidance["direct_tool"]
    assert "query_nyscef_fulltext.py" in guidance["fulltext_tool"]
    assert guidance["local_fulltext_operations"] == [
        "sources",
        "probe",
        "normalize",
        "extract",
        "index",
        "search",
        "stats",
    ]
    assert guidance["identity_model"]["page_evidence"].endswith(
        ":p<page-number>"
    )
    assert guidance["unified_operations"] == []


def test_ny_column_guidance_keeps_notice_discovery_distinct() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.NY_COLUMN_SOURCE_ID
    )

    assert guidance["mode"] == "direct_tool"
    assert "query_ny_column.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == []
    assert "does not replace" in guidance["note"]


def test_tax_court_guidance_exposes_dedicated_dawson_adapter() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.TAX_COURT_SOURCE_ID
    )

    assert guidance["mode"] == "direct_tool"
    assert "query_tax_court.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == []
    assert "native source ceilings" in guidance["note"]


@pytest.mark.parametrize(
    ("source_id", "tool_name"),
    [
        (
            query_state_courts.PA_OPINIONS_SOURCE_ID,
            "query_pa_opinions.py",
        ),
        (
            query_state_courts.DELAWARE_OPINIONS_SOURCE_ID,
            "query_delaware_opinions.py",
        ),
    ],
)
def test_opinion_corpus_guidance_stays_distinct_from_case_dockets(
    source_id: str,
    tool_name: str,
) -> None:
    guidance = query_state_courts._source_guidance(source_id)

    assert guidance["mode"] == "direct_live_document_corpus"
    assert tool_name in guidance["direct_tool"]
    assert guidance["unified_operations"] == []
    assert "rather than a complete case docket" in guidance["note"]


@pytest.mark.parametrize(
    ("source_id", "expected_phrase"),
    [
        (
            query_state_courts.COLORADO_OPINIONS_SOURCE_ID,
            "historical opinion archive",
        ),
        (
            query_state_courts.COLORADO_OPINION_RELEASES_SOURCE_ID,
            "announcement packets",
        ),
    ],
)
def test_colorado_opinion_component_guidance_preserves_source_roles(
    source_id: str,
    expected_phrase: str,
) -> None:
    guidance = query_state_courts._source_guidance(source_id)

    assert guidance["mode"] == "direct_live_document_corpus"
    assert "query_colorado_opinions.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == []
    assert expected_phrase in guidance["note"]


@pytest.mark.parametrize(
    "source_id",
    query_state_courts.OREGON_COURT_DOCUMENT_SOURCE_IDS,
)
def test_oregon_document_collection_guidance_preserves_component_identity(
    source_id: str,
) -> None:
    guidance = query_state_courts._source_guidance(source_id)

    assert guidance["mode"] == "direct_live_document_corpus"
    assert "query_oregon_court_documents.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == []
    assert "collection-specific source identity" in guidance["note"]
    assert "complementary" in guidance["note"]


def test_oregon_appellate_live_route_translates_party_search(
    tmp_path,
    monkeypatch,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.OREGON_APPELLATE_SOURCE_ID
    ]["search"]
    calls = []

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return PublicRecordsResult.success(
            route.adapter.build_query(adapter_args),
            [],
        )

    monkeypatch.setattr(route.adapter, "execute", fake_execute)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse(
            "search",
            "EXAMPLE ORGANIZATION",
            "--source",
            query_state_courts.OREGON_APPELLATE_SOURCE_ID,
            "--court-id",
            "coa",
            "--after",
            "2025-01-01",
            "--before",
            "2025-12-31",
            "--limit",
            "7",
            "--cursor",
            "oregon-appellate:cursor",
            "--page-size",
            "25",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "search-party"
    assert adapter_args.query == "EXAMPLE ORGANIZATION"
    assert adapter_args.match_mode == "match"
    assert adapter_args.court == "coa"
    assert adapter_args.filed_after == "2025-01-01"
    assert adapter_args.filed_before == "2025-12-31"
    assert adapter_args.limit == 7
    assert adapter_args.cursor == "oregon-appellate:cursor"
    assert adapter_args.page_size == 25
    assert decision["allowed"] is True


def test_oregon_appellate_guidance_exposes_component_aware_api() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.OREGON_APPELLATE_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert "query_oregon_appellate.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == [
        "calendar",
        "case",
        "docket",
        "documents",
        "search",
    ]
    assert "per-component completeness" in guidance["note"]
    assert "does not imply" in guidance["note"]


def test_oregon_court_calendar_live_route_preserves_location_and_date(
    tmp_path,
    monkeypatch,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.OREGON_COURT_CALENDAR_SOURCE_ID
    ]["calendar"]
    calls = []

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return PublicRecordsResult.success(
            route.adapter.build_query(adapter_args),
            [],
        )

    monkeypatch.setattr(route.adapter, "execute", fake_execute)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse(
            "calendar",
            "Deschutes",
            "--source",
            query_state_courts.OREGON_COURT_CALENDAR_SOURCE_ID,
            "--jurisdiction",
            "41017",
            "--hearing-date",
            "2026-08-01",
            "--case-type",
            "civil",
            "--limit",
            "7",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "search"
    assert adapter_args.location == "Deschutes"
    assert adapter_args.date_after == "2026-08-01"
    assert adapter_args.date_before == "2026-08-01"
    assert adapter_args.categories == ["civil"]
    assert adapter_args.limit == 7
    assert decision["allowed"] is True


def test_oregon_court_calendar_guidance_keeps_search_modes_and_limits_factual() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.OREGON_COURT_CALENDAR_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert "query_oregon_court_calendar.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == ["calendar"]
    assert "party, business, attorney" in guidance["note"]
    assert "550-row" in guidance["note"]
    assert "separate completeness facts" in guidance["note"]


@pytest.mark.parametrize(
    ("source_id", "spec"),
    [
        (
            query_state_courts.query_oregon_appellate_calendars.COURT_OF_APPEALS_SOURCE_ID,
            query_state_courts.query_oregon_appellate_calendars.COURT_OF_APPEALS,
        ),
        (
            query_state_courts.query_oregon_appellate_calendars.SUPREME_COURT_SOURCE_ID,
            query_state_courts.query_oregon_appellate_calendars.SUPREME_COURT,
        ),
    ],
)
def test_oregon_appellate_calendar_routes_keep_source_identity_and_filters(
    tmp_path,
    monkeypatch,
    source_id,
    spec,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_state_courts.LIVE_ROUTES[source_id]["calendar"]
    calls = []

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return PublicRecordsResult.success(
            route.adapter.build_query(
                adapter_args,
                spec,
                access_decision=access_decision,
            ),
            [],
        )

    monkeypatch.setattr(route.adapter, "execute", fake_execute)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *args: None)

    payload = query_state_courts.execute(
        _parse(
            "calendar",
            "S072119",
            "--source",
            source_id,
            "--jurisdiction",
            "41",
            "--court-id",
            spec.court_id,
            "--after",
            "2026-07-29",
            "--before",
            "2026-10-28",
            "--case-type",
            "oral-argument",
            "--limit",
            "9",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "search"
    assert adapter_args.court == spec.key
    assert adapter_args.query_text == "S072119"
    assert adapter_args.date_after == "2026-07-29"
    assert adapter_args.date_before == "2026-10-28"
    assert adapter_args.event_types == ["oral-argument"]
    assert adapter_args.limit == 9
    assert decision["source_id"] == source_id
    assert decision["allowed"] is True


@pytest.mark.parametrize(
    "source_id",
    query_state_courts.OREGON_APPELLATE_CALENDAR_SOURCE_IDS,
)
def test_oregon_appellate_calendar_guidance_exposes_complete_list_route(
    source_id,
) -> None:
    guidance = query_state_courts._source_guidance(source_id)

    assert guidance["mode"] == "unified_live"
    assert "query_oregon_appellate_calendars.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == ["calendar"]
    assert "every SharePoint continuation" in guidance["note"]
    assert "brief attachments" in guidance["note"]


def test_colorado_court_data_guidance_exposes_complement_catalog() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.COLORADO_COURT_DATA_SOURCE_ID
    )

    assert guidance["mode"] == "direct_live_data_catalog"
    assert "query_colorado_court_data.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == []
    assert "complements" in guidance["note"]


def test_harris_bulk_guidance_stays_distinct_from_filing_documents() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.HARRIS_COURT_BULK_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live_bulk_corpus"
    assert "query_harris_court_bulk.py" in guidance["direct_tool"]
    assert "ingest_harris_court_bulk.py" in guidance["archive_ingest"]
    assert guidance["unified_operations"] == [
        "discovery",
        "documents",
        "download",
        "probe",
    ]
    assert "rather than a complete filing-document portal" in guidance["note"]


def test_sources_and_direct_cli_are_discoverable(tmp_path):
    import subprocess
    import sys

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    payload = query_state_courts.execute(
        _parse("sources", "--catalog-db", str(catalog_path))
    )
    assert payload["status"] == "ok"
    assert {record["source_id"] for record in payload["records"]} >= {
        "us-ny-nyscef",
        "us-in-iocs-bulk",
    }

    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/query_state_courts.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "docket" in result.stdout
    assert "documents" in result.stdout

    search_help = subprocess.run(
        [
            sys.executable,
            "tools/query_state_courts.py",
            "search",
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert search_help.returncode == 0, search_help.stderr
    assert "--ingest" in search_help.stdout
    assert "--page-size" in search_help.stdout
    assert "--max-records" in search_help.stdout
    assert "--timeout" in search_help.stdout
    assert "--minimum-interval" in search_help.stdout
    assert "--first-name" in search_help.stdout

    download_help = subprocess.run(
        [
            sys.executable,
            "tools/query_state_courts.py",
            "download",
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert download_help.returncode == 0, download_help.stderr
    assert "--case-number" in download_help.stdout
    assert "--case-uuid" in download_help.stdout


def test_san_mateo_routes_preserve_native_selectors_and_no_default_cap():
    search_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.SAN_MATEO_MIDX_SOURCE_ID
    ]["search"]
    business = search_route.translate(
        _parse(
            "search",
            "ACME CORPORATION",
            "--source",
            query_state_courts.SAN_MATEO_MIDX_SOURCE_ID,
        ),
        search_route.adapter_command,
    )
    person = search_route.translate(
        _parse(
            "search",
            "Creer",
            "--first-name",
            "Frank",
            "--source",
            query_state_courts.SAN_MATEO_MIDX_SOURCE_ID,
            "--limit",
            "25",
            "--cursor",
            "midx:offset:50",
        ),
        search_route.adapter_command,
    )
    case_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.SAN_MATEO_MIDX_SOURCE_ID
    ]["case"]
    case = case_route.translate(
        _parse(
            "case",
            "PRO116668-B",
            "--source",
            query_state_courts.SAN_MATEO_MIDX_SOURCE_ID,
        ),
        case_route.adapter_command,
    )

    assert business.business_name == "ACME CORPORATION"
    assert business.first_name is None
    assert business.limit is None
    assert business.offset == 0
    assert person.business_name is None
    assert person.first_name == "Frank"
    assert person.last_name == "Creer"
    assert person.limit == 25
    assert person.offset == 50
    assert case.case_number == "PRO116668-B"


def test_san_mateo_router_rejects_unrepresented_filters():
    route = query_state_courts.LIVE_ROUTES[query_state_courts.SAN_MATEO_MIDX_SOURCE_ID][
        "search"
    ]

    with pytest.raises(ValueError, match="five-day"):
        route.translate(
            _parse(
                "search",
                "ACME",
                "--source",
                query_state_courts.SAN_MATEO_MIDX_SOURCE_ID,
                "--after",
                "2026-07-20",
                "--before",
                "2026-07-24",
            ),
            route.adapter_command,
        )
    with pytest.raises(ValueError, match="cursor"):
        route.translate(
            _parse(
                "search",
                "ACME",
                "--source",
                query_state_courts.SAN_MATEO_MIDX_SOURCE_ID,
                "--cursor",
                "bad:50",
            ),
            route.adapter_command,
        )


def test_pa_ujs_routes_preserve_entity_and_report_semantics():
    search_route = query_state_courts.LIVE_ROUTES[query_state_courts.PA_UJS_SOURCE_ID][
        "search"
    ]
    person = search_route.translate(
        _parse(
            "search",
            "SMITH",
            "--first-name",
            "JANE",
            "--county",
            "Philadelphia",
            "--source",
            query_state_courts.PA_UJS_SOURCE_ID,
        ),
        search_route.adapter_command,
    )
    organization = search_route.translate(
        _parse(
            "search",
            "ACME LLC",
            "--entity-kind",
            "organization",
            "--case-type",
            "Civil",
            "--limit",
            "25",
            "--source",
            query_state_courts.PA_UJS_SOURCE_ID,
        ),
        search_route.adapter_command,
    )
    case_route = query_state_courts.LIVE_ROUTES[query_state_courts.PA_UJS_SOURCE_ID][
        "case"
    ]
    case = case_route.translate(
        _parse(
            "case",
            "CP-51-CR-0007622-2022",
            "--source",
            query_state_courts.PA_UJS_SOURCE_ID,
        ),
        case_route.adapter_command,
    )
    download_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.PA_UJS_SOURCE_ID
    ]["download"]
    download = download_route.translate(
        _parse(
            "download",
            "docket_sheet",
            "--case-number",
            "CP-51-CR-0007622-2022",
            "--destination",
            "docket.pdf",
            "--source",
            query_state_courts.PA_UJS_SOURCE_ID,
        ),
        download_route.adapter_command,
    )

    assert person.command == "person"
    assert person.last_name == "SMITH"
    assert person.first_name == "JANE"
    assert person.county == "Philadelphia"
    assert person.limit is None
    assert organization.command == "organization"
    assert organization.organization_name == "ACME LLC"
    assert organization.case_category == "Civil"
    assert organization.limit == 25
    assert case.command == "case"
    assert case.docket_number == "CP-51-CR-0007622-2022"
    assert download.command == "report"
    assert download.kind == "docket_sheet"
    assert download.docket_number == "CP-51-CR-0007622-2022"
    assert download.destination == Path("docket.pdf")


def test_pa_documents_route_and_ingest_preserve_report_links(
    monkeypatch,
    tmp_path,
):
    catalog_path = tmp_path / "catalog.db"
    court_path = tmp_path / "courts.db"
    seed_catalog(db_path=catalog_path)
    fixture = Path("tests/fixtures/public_records/pa_ujs/cp_results.html").read_text()
    route = query_state_courts.LIVE_ROUTES[query_state_courts.PA_UJS_SOURCE_ID][
        "documents"
    ]

    def fake_execute(adapter_args, *, access_decision):
        assert access_decision["allowed"] is True
        page = route.adapter.parse_search_page(fixture)
        records = route.adapter.normalize_records(
            page,
            selection=route.adapter.native_selection(adapter_args),
        )
        return PublicRecordsResult.success(
            route.adapter.build_query(adapter_args),
            records,
        )

    monkeypatch.setattr(route.adapter, "execute", fake_execute)
    monkeypatch.setattr(
        query_state_courts,
        "log_search",
        lambda *_args: None,
    )

    payload = query_state_courts.execute(
        _parse(
            "documents",
            "CP-51-CR-0007622-2022",
            "--source",
            query_state_courts.PA_UJS_SOURCE_ID,
            "--catalog-db",
            str(catalog_path),
            "--court-db",
            str(court_path),
            "--ingest",
        )
    )

    assert payload["status"] == "ok"
    assert len(payload["records"][0]["documents"]) == 2
    assert payload["ingest"]["projected"]["documents"] == 2
    db = connect_courts(court_path)
    try:
        stored = db.execute(
            """
            SELECT native_document_id, document_type, source_url
            FROM document_artifact
            ORDER BY native_document_id
            """
        ).fetchall()
    finally:
        db.close()
    assert [tuple(row[:2]) for row in stored] == [
        (
            "CP-51-CR-0007622-2022:court_summary",
            "court_summary",
        ),
        (
            "CP-51-CR-0007622-2022:docket_sheet",
            "docket_sheet",
        ),
    ]
    assert all(str(row["source_url"]).startswith("https://") for row in stored)


def test_delaware_routes_follow_all_pages_unless_caller_selects_one():
    search_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.DELAWARE_COURTCONNECT_SOURCE_ID
    ]["search"]
    exhaustive = search_route.translate(
        _parse(
            "search",
            "TESLA",
            "--entity-kind",
            "organization",
            "--partial",
            "--source",
            query_state_courts.DELAWARE_COURTCONNECT_SOURCE_ID,
        ),
        search_route.adapter_command,
    )
    paged = search_route.translate(
        _parse(
            "search",
            "SMITH",
            "--first-name",
            "JANE",
            "--limit",
            "25",
            "--max-records",
            "10",
            "--cursor",
            ("https://courtconnect.courts.delaware.gov/cc/cconnect/results?PageNo=3"),
            "--source",
            query_state_courts.DELAWARE_COURTCONNECT_SOURCE_ID,
        ),
        search_route.adapter_command,
    )
    case_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.DELAWARE_COURTCONNECT_SOURCE_ID
    ]["docket"]
    case = case_route.translate(
        _parse(
            "docket",
            "JP13-23-013991",
            "--after",
            "2024-01-01",
            "--source",
            query_state_courts.DELAWARE_COURTCONNECT_SOURCE_ID,
        ),
        case_route.adapter_command,
    )

    assert exhaustive.command == "cases"
    assert exhaustive.last_name_or_company == "TESLA"
    assert exhaustive.first_name is None
    assert exhaustive.partial is True
    assert exhaustive.page is None
    assert exhaustive.limit is None
    assert paged.first_name == "JANE"
    assert paged.page == 3
    assert paged.limit == 10
    assert case.command == "case"
    assert case.case_id == "JP13-23-013991"
    assert case.docket_after == "2024-01-01"


def test_oregon_eugene_smart_and_ojcin_routes_preserve_native_contracts():
    eugene_search_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.EUGENE_MUNICIPAL_SOURCE_ID
    ]["search"]
    eugene_search = eugene_search_route.translate(
        _parse(
            "search",
            "A123456",
            "--source",
            query_state_courts.EUGENE_MUNICIPAL_SOURCE_ID,
            "--search-field",
            "citation",
            "--jurisdiction",
            "41039",
            "--limit",
            "12",
        ),
        eugene_search_route.adapter_command,
    )
    assert eugene_search.command == "search"
    assert eugene_search.citation == "A123456"
    assert eugene_search.last_name is None
    assert eugene_search.limit == 12

    eugene_calendar_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.EUGENE_MUNICIPAL_SOURCE_ID
    ]["calendar"]
    eugene_calendar = eugene_calendar_route.translate(
        _parse(
            "calendar",
            "*",
            "--source",
            query_state_courts.EUGENE_MUNICIPAL_SOURCE_ID,
            "--after",
            "2026-08-01",
            "--before",
            "2026-08-31",
        ),
        eugene_calendar_route.adapter_command,
    )
    assert eugene_calendar.command == "dockets"
    assert eugene_calendar.date_from == "2026-08-01"
    assert eugene_calendar.date_to == "2026-08-31"

    eugene_docket_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.EUGENE_MUNICIPAL_SOURCE_ID
    ]["docket"]
    eugene_docket = eugene_docket_route.translate(
        _parse(
            "docket",
            "08/01/2026|CRIM|ROOM1",
            "--source",
            query_state_courts.EUGENE_MUNICIPAL_SOURCE_ID,
        ),
        eugene_docket_route.adapter_command,
    )
    assert eugene_docket.command == "docket"
    assert eugene_docket.native_date == "08/01/2026"
    assert eugene_docket.calendar_code == "CRIM"
    assert eugene_docket.room_code == "ROOM1"

    smart_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.OREGON_SMART_SEARCH_SOURCE_ID
    ]["search"]
    smart = smart_route.translate(
        _parse(
            "search",
            "EXAMPLE HOLDINGS LLC",
            "--source",
            query_state_courts.OREGON_SMART_SEARCH_SOURCE_ID,
            "--entity-kind",
            "organization",
            "--courthouse",
            "Lane",
            "--case-type",
            "Civil",
            "--after",
            "2026-01-01",
            "--before",
            "2026-07-31",
        ),
        smart_route.adapter_command,
    )
    assert smart.command == "prepare"
    assert smart.search_by == "BusinessName"
    assert smart.business_name is True
    assert smart.party_name is False
    assert smart.location == "Lane"
    assert smart.file_date_start == "2026-01-01"
    assert smart.file_date_end == "2026-07-31"

    ojcin_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.OREGON_OJCIN_PRODUCT_DIRECTORY_SOURCE_ID
    ]["products"]
    ojcin_args = ojcin_route.translate(
        _parse(
            "products",
            "--product-id",
            "us-or-ojcin-oeci-subscription",
        ),
        ojcin_route.adapter_command,
    )
    ojcin_result = ojcin_route.adapter.execute(
        ojcin_args,
        access_decision={
            "source_id": (query_state_courts.OREGON_OJCIN_PRODUCT_DIRECTORY_SOURCE_ID),
            "allowed": True,
        },
    )
    assert ojcin_result.status.value == "ok"
    assert len(ojcin_result.records) == 1
    assert ojcin_result.records[0]["product_id"] == "us-or-ojcin-oeci-subscription"
    assert "raw_case_number" not in ojcin_result.records[0]


def test_ojcin_delivery_command_fingerprints_and_ingests_receipt_only(tmp_path):
    delivery_path = tmp_path / "oeci-delivery.dat"
    delivery_path.write_bytes(b"uninterpreted delivery bytes\n")
    court_path = tmp_path / "courts.db"

    payload = query_state_courts.execute(
        _parse(
            "delivery",
            str(delivery_path),
            "--product-id",
            "us-or-ojcin-oeci-subscription",
            "--delivery-version",
            "provider-2026-07",
            "--received-at",
            "2026-07-29T12:00:00Z",
            "--provider-reference",
            "delivery-42",
            "--court-db",
            str(court_path),
            "--ingest",
        )
    )

    assert payload["status"] == "ok"
    assert payload["records"][0]["record_kind"] == ("court_data_delivery_receipt")
    assert (
        payload["records"][0]["delivery_receipt"]["interpretation"]["rows_interpreted"]
        is False
    )
    assert payload["ingest"]["snapshot"]["projected"]["cases"] == 0
    assert payload["ingest"]["delivery_receipt"]["case_rows_projected"] == 0
    db = connect_courts(court_path)
    try:
        assert (
            db.execute("SELECT COUNT(*) FROM court_data_delivery_receipt").fetchone()[0]
            == 1
        )
        assert (
            db.execute("SELECT COUNT(*) FROM court_data_delivery_file").fetchone()[0]
            == 1
        )
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 0
    finally:
        db.close()


def test_all_oregon_tyler_tenants_are_shared_routes_with_bound_identity():
    expected_sources = {
        tenant.source_id
        for tenant in (
            query_state_courts.query_eugene_municipal_court.OREGON_TENANTS.values()
        )
    }

    assert set(query_state_courts.OREGON_TYLER_MUNICIPAL_SOURCE_IDS) == (
        expected_sources
    )
    for source_id in expected_sources:
        assert set(query_state_courts.LIVE_ROUTES[source_id]) == {
            "search",
            "case",
            "docket",
            "calendar",
        }
        tenant = query_state_courts.OREGON_TYLER_TENANTS_BY_SOURCE[source_id]
        guidance = query_state_courts.DIRECT_TOOL_GUIDANCE[source_id]
        assert guidance["tenant_key"] == tenant.key
        assert guidance["court_id"] == tenant.court_id
        assert guidance["component_access"] == {
            "cases": tenant.case_access_state,
            "dockets": tenant.docket_access_state,
        }


def test_medford_and_grand_ronde_routes_keep_tenant_court_and_jurisdiction():
    medford = query_state_courts.query_eugene_municipal_court.MEDFORD_TENANT
    medford_route = query_state_courts.LIVE_ROUTES[medford.source_id]["search"]
    medford_args = medford_route.translate(
        _parse(
            "search",
            "E018359",
            "--source",
            medford.source_id,
            "--search-field",
            "citation",
            "--court-id",
            medford.court_id,
            "--jurisdiction",
            medford.county_fips,
        ),
        medford_route.adapter_command,
    )

    assert medford_args.tenant == "medford"
    assert medford_args.command == "search"
    assert medford_args.citation == "E018359"
    assert medford_args.last_name is None

    grand_ronde = query_state_courts.query_eugene_municipal_court.GRAND_RONDE_TENANT
    grand_ronde_route = query_state_courts.LIVE_ROUTES[grand_ronde.source_id][
        "calendar"
    ]
    grand_ronde_args = grand_ronde_route.translate(
        _parse(
            "calendar",
            "*",
            "--source",
            grand_ronde.source_id,
            "--court-id",
            grand_ronde.court_id,
            "--jurisdiction",
            grand_ronde.jurisdiction_id,
        ),
        grand_ronde_route.adapter_command,
    )

    assert grand_ronde_args.tenant == "grand-ronde"
    assert grand_ronde_args.command == "dockets"
    guidance = query_state_courts.DIRECT_TOOL_GUIDANCE[grand_ronde.source_id]
    assert guidance["mode"] == ("tenant_access_probe_and_official_alternatives")
    assert {
        route.get("audience")
        for route in guidance["official_alternatives"]
        if route.get("audience")
    } == {"court_record_requesters", "tribal_members"}


def test_public_tyler_selector_validation_is_tenant_specific():
    linn = query_state_courts.query_eugene_municipal_court.LINN_COUNTY_TENANT
    route = query_state_courts.LIVE_ROUTES[linn.source_id]["search"]

    with pytest.raises(ValueError, match="VIN was not present"):
        route.translate(
            _parse(
                "search",
                "VIN123",
                "--source",
                linn.source_id,
                "--search-field",
                "vin",
            ),
            route.adapter_command,
        )


@pytest.mark.parametrize(
    ("tenant_key", "case_state", "docket_state"),
    [
        ("clackamas", "login_required", "not_found"),
        ("corvallis", "login_required", "login_required"),
        ("grand-ronde", "login_required", "login_required"),
    ],
)
def test_gated_tyler_guidance_preserves_direct_component_observations(
    tenant_key,
    case_state,
    docket_state,
):
    tenant = query_state_courts.query_eugene_municipal_court.OREGON_TENANTS[tenant_key]
    guidance = query_state_courts.DIRECT_TOOL_GUIDANCE[tenant.source_id]

    assert guidance["mode"] == ("tenant_access_probe_and_official_alternatives")
    assert guidance["component_access"] == {
        "cases": case_state,
        "dockets": docket_state,
    }
    assert guidance["official_alternatives"] == [
        dict(route) for route in tenant.alternative_routes
    ]


def test_dc_opinions_routes_preserve_native_page_filters_and_publication_type():
    source_id = query_state_courts.DC_OPINIONS_SOURCE_ID
    route = query_state_courts.LIVE_ROUTES[source_id]["search"]
    translated = route.translate(
        _parse(
            "search",
            "Georgia Television",
            "--source",
            source_id,
            "--jurisdiction",
            "11",
            "--court-id",
            "us-dc-court-of-appeals",
            "--case-type",
            "mojs",
            "--after",
            "2026-07-01",
            "--before",
            "2026-07-31",
            "--cursor",
            "page:7",
        ),
        route.adapter_command,
    )

    assert set(query_state_courts.LIVE_ROUTES[source_id]) == {
        "search",
        "case",
        "documents",
        "download",
    }
    assert translated.command == "list"
    assert translated.query == "Georgia Television"
    assert translated.type == "mojs"
    assert translated.date is None
    assert translated.date_from == "2026-07-01"
    assert translated.date_to == "2026-07-31"
    assert translated.page == 7
    assert translated.all_pages is False
    assert translated.order == "date"
    assert translated.sort == "desc"


def test_dc_opinions_documents_and_download_routes_keep_exact_artifact_semantics(
    tmp_path,
):
    source_id = query_state_courts.DC_OPINIONS_SOURCE_ID
    documents_route = query_state_courts.LIVE_ROUTES[source_id]["documents"]
    documents = documents_route.translate(
        _parse(
            "documents",
            "24-BG-1045",
            "--source",
            source_id,
            "--document-type",
            "appellate_opinion",
            "--after",
            "2026-07-23",
            "--before",
            "2026-07-23",
        ),
        documents_route.adapter_command,
    )
    assert documents.command == "list"
    assert documents.type == "opinions"
    assert documents.date == "2026-07-23"
    assert documents.date_from is None
    assert documents.date_to is None

    pdf_url = (
        "https://www.dccourts.gov/sites/default/files/2026-07/"
        "In_re_Alpert-24-BG-1045.pdf"
    )
    destination = tmp_path / "opinion.pdf"
    download_route = query_state_courts.LIVE_ROUTES[source_id]["download"]
    download = download_route.translate(
        _parse(
            "download",
            pdf_url,
            "--source",
            source_id,
            "--destination",
            str(destination),
        ),
        download_route.adapter_command,
    )
    assert download.command == "download"
    assert download.url == pdf_url
    assert download.destination == destination

    guidance = query_state_courts.DIRECT_TOOL_GUIDANCE[source_id]
    assert guidance["native_page_size"] == 10
    assert guidance["native_type_selectors"] == ["all", "opinions", "mojs"]
    assert guidance["direct_list_default"] == "exhaustive"
    assert guidance["direct_one_page_option"] == "--page-only"
    assert "one native page" in guidance["note"]
    assert "exhaustive" in guidance["note"]
    assert "Memorandum Opinion and Judgment" in guidance["note"]


def test_dc_opinions_router_rejects_unrepresented_or_conflicting_selection():
    source_id = query_state_courts.DC_OPINIONS_SOURCE_ID
    search_route = query_state_courts.LIVE_ROUTES[source_id]["search"]

    with pytest.raises(ValueError, match="requires both"):
        search_route.translate(
            _parse(
                "search",
                "example",
                "--source",
                source_id,
                "--after",
                "2026-07-01",
            ),
            search_route.adapter_command,
        )
    with pytest.raises(ValueError, match="page:N"):
        search_route.translate(
            _parse(
                "search",
                "example",
                "--source",
                source_id,
                "--cursor",
                "7",
            ),
            search_route.adapter_command,
        )
    with pytest.raises(ValueError, match="jurisdiction"):
        search_route.translate(
            _parse(
                "search",
                "example",
                "--source",
                source_id,
                "--jurisdiction",
                "41",
            ),
            search_route.adapter_command,
        )

    documents_route = query_state_courts.LIVE_ROUTES[source_id]["documents"]
    with pytest.raises(ValueError, match="disagree"):
        documents_route.translate(
            _parse(
                "documents",
                "24-BG-1045",
                "--source",
                source_id,
                "--case-type",
                "mojs",
                "--document-type",
                "appellate_opinion",
            ),
            documents_route.adapter_command,
        )


def test_dc_superior_calendar_routes_preserve_native_filters_and_cursor():
    today_source = query_state_courts.DC_TODAY_CALENDAR_SOURCE_ID
    today_route = query_state_courts.LIVE_ROUTES[today_source]["search"]
    today = today_route.translate(
        _parse(
            "search",
            "Example Holdings",
            "--source",
            today_source,
            "--jurisdiction",
            "11",
            "--cursor",
            "dcsc:v1:today:0123456789abcdef:page:4",
        ),
        today_route.adapter_command,
    )

    assert set(query_state_courts.LIVE_ROUTES[today_source]) == {
        "search",
        "case",
        "calendar",
    }
    assert today.command == "search"
    assert today.party == "Example Holdings"
    assert today.case_number is None
    assert today.cursor == "dcsc:v1:today:0123456789abcdef:page:4"
    assert today.max_pages == 1
    assert today.page is None

    criminal_source = query_state_courts.DC_CRIMINAL_CALENDAR_SOURCE_ID
    criminal_route = query_state_courts.LIVE_ROUTES[criminal_source]["search"]
    criminal = criminal_route.translate(
        _parse(
            "search",
            "OPERATING A VEHICLE",
            "--source",
            criminal_source,
            "--search-field",
            "charge",
            "--courthouse",
            "Courtroom 201",
        ),
        criminal_route.adapter_command,
    )
    assert criminal.command == "criminal"
    assert criminal.charge == "OPERATING A VEHICLE"
    assert criminal.courtroom == "Courtroom 201"
    assert criminal.defendant is None
    assert criminal.max_pages == 1


def test_dc_calendar_artifact_routes_keep_non_case_semantics():
    tax_source = query_state_courts.DC_TAX_CALENDAR_SOURCE_ID
    tax_route = query_state_courts.LIVE_ROUTES[tax_source]["calendar"]
    tax = tax_route.translate(
        _parse("calendar", "tax", "--source", tax_source),
        tax_route.adapter_command,
    )
    assert set(query_state_courts.LIVE_ROUTES[tax_source]) == {"calendar"}
    assert tax.command == "artifacts"
    assert tax.family == "tax"

    appeals_source = query_state_courts.DC_APPEALS_CALENDAR_SOURCE_ID
    appeals_route = query_state_courts.LIVE_ROUTES[appeals_source]["calendar"]
    appeals = appeals_route.translate(
        _parse(
            "calendar",
            "2024",
            "--source",
            appeals_source,
            "--after",
            "2024-01-01",
            "--before",
            "2024-12-31",
        ),
        appeals_route.adapter_command,
    )
    assert set(query_state_courts.LIVE_ROUTES[appeals_source]) == {"calendar"}
    assert appeals.command == "appeals"
    assert appeals.year == 2024

    guidance = query_state_courts.DIRECT_TOOL_GUIDANCE
    assert "case-file documents" in guidance[tax_source]["note"]
    assert guidance[appeals_source]["opinion_complement"] == (
        query_state_courts.DC_OPINIONS_SOURCE_ID
    )


def test_dc_current_day_route_accepts_only_matching_date(
    monkeypatch: pytest.MonkeyPatch,
):
    source_id = query_state_courts.DC_TODAY_CALENDAR_SOURCE_ID
    route = query_state_courts.LIVE_ROUTES[source_id]["calendar"]
    monkeypatch.setattr(
        query_state_courts,
        "_dc_calendar_current_date",
        lambda: "2026-07-30",
    )

    translated = route.translate(
        _parse(
            "calendar",
            "all",
            "--source",
            source_id,
            "--hearing-date",
            "2026-07-30",
        ),
        route.adapter_command,
    )
    assert translated.case_number is None

    with pytest.raises(ValueError, match="2026-07-30"):
        route.translate(
            _parse(
                "calendar",
                "all",
                "--source",
                source_id,
                "--hearing-date",
                "2026-07-29",
            ),
            route.adapter_command,
        )


def test_fresno_calendar_and_ruling_routes_keep_exact_artifact_selectors():
    calendar_source = query_state_courts.FRESNO_CALENDAR_SOURCE_ID
    calendar_route = query_state_courts.LIVE_ROUTES[calendar_source][
        "calendar"
    ]
    calendar = calendar_route.translate(
        _parse(
            "calendar",
            "2026-07-30",
            "--source",
            calendar_source,
            "--jurisdiction",
            "06019",
            "--hearing-date",
            "2026-07-30",
        ),
        calendar_route.adapter_command,
    )
    assert set(query_state_courts.LIVE_ROUTES[calendar_source]) == {
        "calendar"
    }
    assert calendar.command == "calendar"
    assert calendar.date == "2026-07-30"
    assert calendar.url is None

    rulings_source = query_state_courts.FRESNO_RULINGS_SOURCE_ID
    rulings_route = query_state_courts.LIVE_ROUTES[rulings_source][
        "calendar"
    ]
    rulings = rulings_route.translate(
        _parse(
            "calendar",
            "latest",
            "--source",
            rulings_source,
            "--courthouse",
            "Dept 501",
            "--hearing-date",
            "2026-07-30",
        ),
        rulings_route.adapter_command,
    )
    assert rulings.command == "rulings"
    assert rulings.department == 501
    assert rulings.date == "2026-07-30"
    assert rulings.url is None


def test_fresno_probate_notes_route_converts_shared_iso_hearing_date():
    source_id = query_state_courts.FRESNO_PROBATE_SOURCE_ID
    route = query_state_courts.LIVE_ROUTES[source_id]["notes"]
    translated = route.translate(
        _parse(
            "notes",
            "19CEPR00967",
            "--source",
            source_id,
            "--jurisdiction",
            "CA",
            "--court-id",
            "ca-fresno-superior-court",
            "--hearing-date",
            "2026-04-01",
        ),
        route.adapter_command,
    )

    assert set(query_state_courts.LIVE_ROUTES[source_id]) == {"notes"}
    assert translated.command == "probate-notes"
    assert translated.case_number == "19CEPR00967"
    assert translated.hearing_date == "04/01/2026"

    guidance = query_state_courts.DIRECT_TOOL_GUIDANCE
    assert "all_rows" in guidance[
        query_state_courts.FRESNO_CALENDAR_SOURCE_ID
    ]["direct_default"]
    assert "not part of the official court file" in guidance[source_id]["note"]


def test_orange_calendar_routes_preserve_category_filters_and_optional_bounds():
    source_id = query_state_courts.ORANGE_CALENDAR_SOURCE_ID
    search_route = query_state_courts.LIVE_ROUTES[source_id]["search"]
    complete = search_route.translate(
        _parse(
            "search",
            "Kiani",
            "--source",
            source_id,
            "--jurisdiction",
            "06059",
            "--court-id",
            "ca-orange-superior",
            "--case-type",
            "civil",
            "--after",
            "2026-07-30",
            "--before",
            "2026-08-15",
        ),
        search_route.adapter_command,
    )

    assert set(query_state_courts.LIVE_ROUTES[source_id]) == {
        "search",
        "case",
        "calendar",
    }
    assert complete.command == "calendar"
    assert complete.category == "civil"
    assert complete.title == "Kiani"
    assert complete.case_id is None
    assert complete.date_from == "2026-07-30"
    assert complete.date_to == "2026-08-15"
    assert complete.limit is None

    bounded = search_route.translate(
        _parse(
            "search",
            "Kiani",
            "--source",
            source_id,
            "--case-type",
            "civil",
            "--limit",
            "5",
        ),
        search_route.adapter_command,
    )
    assert bounded.limit == 5

    case_route = query_state_courts.LIVE_ROUTES[source_id]["case"]
    exact_case = case_route.translate(
        _parse(
            "case",
            "30-2026-12345678-CU-BC-CJC",
            "--source",
            source_id,
            "--case-type",
            "civil",
        ),
        case_route.adapter_command,
    )
    assert exact_case.case_id == "30-2026-12345678-CU-BC-CJC"
    assert exact_case.title is None

    with pytest.raises(ValueError, match="require --case-type"):
        search_route.translate(
            _parse("search", "Kiani", "--source", source_id),
            search_route.adapter_command,
        )


def test_orange_ruling_routes_keep_division_and_department_grain():
    source_id = (
        query_state_courts.ORANGE_RULING_SOURCE_IDS["civil"]
    )
    routes = query_state_courts.LIVE_ROUTES[source_id]
    index = routes["calendar"].translate(
        _parse("calendar", "all", "--source", source_id),
        routes["calendar"].adapter_command,
    )
    assert set(routes) == {"search", "calendar", "documents"}
    assert index.command == "ruling-index"
    assert index.division == "civil"
    assert index.department is None

    document = routes["documents"].translate(
        _parse("documents", "C44", "--source", source_id),
        routes["documents"].adapter_command,
    )
    assert document.command == "ruling"
    assert document.division == "civil"
    assert document.department == "C44"
    assert document.no_text is False
    assert document.download is None
    assert "rolling" in query_state_courts.DIRECT_TOOL_GUIDANCE[source_id][
        "note"
    ]


def test_riverside_calendar_route_preserves_native_filters_and_source_window():
    source_id = query_state_courts.RIVERSIDE_CALENDAR_SOURCE_ID
    route = query_state_courts.LIVE_ROUTES[source_id]["calendar"]
    complete = route.translate(
        _parse(
            "calendar",
            "8",
            "--source",
            source_id,
            "--jurisdiction",
            "06065",
            "--court-id",
            "ca-riverside-superior",
            "--search-field",
            "department",
            "--case-type",
            "probate",
            "--after",
            "2026-07-30",
            "--before",
            "2026-08-04",
        ),
        route.adapter_command,
    )

    assert set(query_state_courts.LIVE_ROUTES[source_id]) == {"calendar"}
    assert complete.command == "calendar"
    assert complete.department == "8"
    assert complete.area_of_law == "probate"
    assert complete.start_date == "2026-07-30"
    assert complete.end_date == "2026-08-04"
    assert complete.limit is None

    bounded = route.translate(
        _parse(
            "calendar",
            "Historic Court House",
            "--source",
            source_id,
            "--search-field",
            "courthouse",
            "--max-records",
            "7",
        ),
        route.adapter_command,
    )
    assert bounded.courthouse == "Historic Court House"
    assert bounded.department is None
    assert bounded.limit == 7


def test_riverside_ruling_routes_separate_directory_and_document_selection():
    source_id = query_state_courts.RIVERSIDE_RULING_SOURCE_ID
    routes = query_state_courts.LIVE_ROUTES[source_id]

    directory = routes["calendar"].translate(
        _parse("calendar", "all", "--source", source_id),
        routes["calendar"].adapter_command,
    )
    assert set(routes) == {"search", "calendar", "documents"}
    assert directory.command == "ruling-index"
    assert directory.department is None

    filtered = routes["search"].translate(
        _parse("search", "PS1", "--source", source_id),
        routes["search"].adapter_command,
    )
    assert filtered.department == "PS1"

    document = routes["documents"].translate(
        _parse(
            "documents",
            "PS1",
            "--source",
            source_id,
        ),
        routes["documents"].adapter_command,
    )
    assert document.command == "ruling"
    assert document.department == "PS1"
    assert document.no_text is False
    assert document.download is None
    assert "mixed-age" in query_state_courts.DIRECT_TOOL_GUIDANCE[source_id][
        "note"
    ]


def test_riverside_routes_reject_other_courts_and_unreliable_ruling_dates():
    calendar_source = query_state_courts.RIVERSIDE_CALENDAR_SOURCE_ID
    calendar_route = query_state_courts.LIVE_ROUTES[calendar_source][
        "calendar"
    ]
    with pytest.raises(ValueError, match="06065"):
        calendar_route.translate(
            _parse(
                "calendar",
                "all",
                "--source",
                calendar_source,
                "--jurisdiction",
                "06059",
            ),
            calendar_route.adapter_command,
        )

    ruling_source = query_state_courts.RIVERSIDE_RULING_SOURCE_ID
    ruling_route = query_state_courts.LIVE_ROUTES[ruling_source]["calendar"]
    with pytest.raises(ValueError, match="reliable date filter"):
        ruling_route.translate(
            _parse(
                "calendar",
                "all",
                "--source",
                ruling_source,
                "--after",
                "2026-07-30",
            ),
            ruling_route.adapter_command,
        )


def test_qld_ecourts_routes_preserve_registry_identity_and_exhaustive_default():
    source_id = query_state_courts.QLD_ECOURTS_SOURCE_ID
    routes = query_state_courts.LIVE_ROUTES[source_id]

    search = routes["search"].translate(
        _parse(
            "search",
            "COSCOLLUELA",
            "--source",
            source_id,
            "--jurisdiction",
            "AU-QLD",
            "--court-id",
            "qld-supreme-court",
            "--courthouse",
            "BRISB",
            "--first-name",
            "ROBERTO",
        ),
        routes["search"].adapter_command,
    )
    assert set(routes) == {"search", "case", "docket", "documents"}
    assert search.command == "search"
    assert search.party_name == "COSCOLLUELA"
    assert search.given_names == "ROBERTO"
    assert search.court == "SUPRE"
    assert search.location == "BRISB"
    assert search.limit is None

    case = routes["documents"].translate(
        _parse(
            "documents",
            "6819/11",
            "--source",
            source_id,
            "--court-id",
            "qld-supreme-court",
            "--courthouse",
            "BRISB",
        ),
        routes["documents"].adapter_command,
    )
    assert case.command == "case"
    assert case.file_number == "6819/11"
    assert case.court == "SUPRE"
    assert case.location == "BRISB"

    guidance = query_state_courts._source_guidance(source_id)
    assert guidance["mode"] == "unified_live_civil_case_index"
    assert guidance["native_result_ceiling"] == 500
    assert guidance["identity_model"] == (
        "court_code + originating_registry_code + file_number"
    )
    assert guidance["unified_operations"] == [
        "case",
        "docket",
        "documents",
        "search",
    ]


def test_qld_ecourts_route_rejects_unmapped_filing_dates_and_courts():
    source_id = query_state_courts.QLD_ECOURTS_SOURCE_ID
    route = query_state_courts.LIVE_ROUTES[source_id]["search"]
    with pytest.raises(ValueError, match="party-entry date"):
        route.translate(
            _parse(
                "search",
                "SMITH",
                "--source",
                source_id,
                "--after",
                "2026-01-01",
            ),
            route.adapter_command,
        )
    with pytest.raises(ValueError, match="qld-supreme-court"):
        route.translate(
            _parse(
                "search",
                "SMITH",
                "--source",
                source_id,
                "--court-id",
                "qld-magistrates-court",
            ),
            route.adapter_command,
        )


def test_los_angeles_name_index_guidance_exposes_paid_workflow() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.LOS_ANGELES_NAME_INDEX_SOURCE_ID
    )

    assert guidance["mode"] == "direct_paid_name_index_workflow"
    assert "query_los_angeles_name_index.py" in guidance["direct_tool"]
    assert set(guidance["operations"]) == {
        "probe",
        "prepare",
        "receipt --retrieve",
        "parse-results",
    }
    assert "public_records_actions.py" in guidance["paid_action_tool"]
    assert guidance["unified_operations"] == []
    assert "canonical case crosswalk" in guidance["note"]


def test_los_angeles_civil_case_routes_keep_exact_case_and_optional_paging():
    source_id = query_state_courts.LOS_ANGELES_CIVIL_SOURCE_ID
    route = query_state_courts.LIVE_ROUTES[source_id]["case"]
    complete = route.translate(
        _parse(
            "case",
            "24NNCV00427",
            "--source",
            source_id,
            "--jurisdiction",
            "06037",
            "--court-id",
            "ca-los-angeles-superior-court-civil",
            "--courthouse",
            "ALH",
        ),
        route.adapter_command,
    )

    assert set(query_state_courts.LIVE_ROUTES[source_id]) == {
        "case",
        "docket",
        "documents",
        "calendar",
    }
    assert complete.command == "case"
    assert complete.case_number == "24NNCV00427"
    assert complete.courthouse == "ALH"
    assert complete.limit is None
    assert complete.offset == 0

    paged = route.translate(
        _parse(
            "docket",
            "24NNCV00427",
            "--source",
            source_id,
            "--limit",
            "2",
            "--cursor",
            "la-civil-case-entry:4",
        ),
        route.adapter_command,
    )
    assert paged.limit == 2
    assert paged.offset == 4


def test_los_angeles_civil_ruling_route_preserves_native_selection_and_cursor():
    source_id = query_state_courts.LOS_ANGELES_CIVIL_SOURCE_ID
    route = query_state_courts.LIVE_ROUTES[source_id]["calendar"]
    exact = route.translate(
        _parse(
            "calendar",
            "ALH,3,07/30/2026",
            "--source",
            source_id,
            "--hearing-date",
            "2026-07-30",
        ),
        route.adapter_command,
    )

    assert exact.command == "rulings"
    assert exact.selection == "ALH,3,07/30/2026"
    assert exact.max_selections is None
    assert exact.selection_offset == 0

    complete = route.translate(
        _parse("calendar", "all", "--source", source_id),
        route.adapter_command,
    )
    assert complete.max_selections is None
    assert complete.selection_offset == 0

    paged = route.translate(
        _parse(
            "calendar",
            "all",
            "--source",
            source_id,
            "--limit",
            "3",
            "--cursor",
            "la-tentative-selection:6",
        ),
        route.adapter_command,
    )
    assert paged.max_selections == 3
    assert paged.selection_offset == 6
    assert (
        "paid name discovery"
        in query_state_courts.DIRECT_TOOL_GUIDANCE[source_id]["note"]
    )
