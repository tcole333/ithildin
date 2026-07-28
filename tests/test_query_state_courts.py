import hashlib
import json
from pathlib import Path

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


def test_local_court_queries_default_exclude_restricted_material(
    tmp_path, monkeypatch
):
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
    assert all(
        record["access_state"] == "public"
        for record in documents["records"]
    )


def test_empty_local_sidecar_is_unavailable_and_writes_artifact(
    tmp_path, monkeypatch
):
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
        artifact["errors"][0]["details"]["coverage"]["sidecar"][
            "row_counts"
        ].values()
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


def test_local_court_preserves_exact_source_authoritative_zero(
    tmp_path, monkeypatch
):
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


def test_nyscef_and_formal_feeds_surface_catalog_access_statuses(
    tmp_path, monkeypatch
):
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
    assert nyscef["errors"][0]["details"]["manual_source_url"].startswith(
        "https://"
    )
    assert nyscef["errors"][0]["details"]["requested_action"]["operation"] == (
        "search"
    )
    assert nyscef["query"]["query"]["operation"] == "case"
    assert nyscef["errors"][0]["details"]["requested_action"][
        "router_operation"
    ] == "case"
    assert nyscef["errors"][0]["details"]["requested_action"]["selector"] == (
        "156728/2019"
    )
    assert formal["status"] == "unavailable"
    assert formal["errors"][0]["code"] == "access_review_required"
    assert missing["status"] == "unavailable"
    assert all(call[2] is None for call in logged)


def test_sources_and_direct_cli_are_discoverable(tmp_path):
    import subprocess
    import sys

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    payload = query_state_courts.execute(
        _parse("sources", "--catalog-db", str(catalog_path))
    )
    assert payload["status"] == "ok"
    assert {
        record["source_id"] for record in payload["records"]
    } >= {"us-ny-nyscef", "us-in-iocs-bulk"}

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
