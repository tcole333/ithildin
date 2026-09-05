from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tools import ingest_state_court_records as ingest
from tools import query_connecticut_civil_family as ct
from tools import query_state_courts as courts
from tools import public_records_monitor as monitor
from tools import source_report
from tools.public_records_contract import (
    PublicRecordsError,
    PublicRecordsResult,
    ResultStatus,
)
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import seed_catalog


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "connecticut_civil_family"
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _case_record() -> dict[str, Any]:
    record = ct.parse_case_detail(
        _fixture("case_detail.html"),
        requested_docket=ct.SENTINEL_DOCKET,
        source_url=(
            f"{ct.CASE_DETAIL_URL}?DocketNo="
            f"{ct.compact_docket(ct.SENTINEL_DOCKET)}"
        ),
    )
    record["scheduled_events"] = [
        {
            "canonical_ref": ct._child_ref(
                ct.SENTINEL_DOCKET,
                "scheduled_event",
                "17",
            ),
            "publisher_event_number": "17",
            "date_raw": "08/14/2026",
            "date": "2026-08-14",
            "time_raw": "10:00 AM",
            "description": "Remote Status Conference",
            "status": "Scheduled",
        }
    ]
    record["history"] = [
        {
            "canonical_ref": ct._derived_child_ref(
                ct.SENTINEL_DOCKET,
                "transfer_event",
                (
                    "FBT-CV-26-6159214-S",
                    "HHD-CV-26-6159214-S",
                    "05/01/2026",
                ),
            ),
            "identity_basis": "published_transfer_field_tuple",
            "transferred_from_docket": "FBT-CV-26-6159214-S",
            "transferred_to_docket": "HHD-CV-26-6159214-S",
            "transfer_date_raw": "05/01/2026",
            "transfer_date": "2026-05-01",
        }
    ]
    record["notices"] = [
        {
            "canonical_ref": ct._child_ref(
                ct.SENTINEL_DOCKET,
                "notice",
                "991",
            ),
            "publisher_notice_id": "991",
            "publisher_publication_set_id": "44",
            "published_date_raw": "05/02/2026",
            "published_date": "2026-05-02",
            "content_preview": "Published notice text",
            "action_label": "View Notice",
            "notice_handler": "PublicNotice.aspx",
            "full_notice_url": f"{ct.BASE_URL}PublicNotice.aspx?eNID=991&PSID=44",
        }
    ]
    record["disposition"] = {
        "date_raw": "06/01/2026",
        "date": "2026-06-01",
        "description": "Withdrawn",
        "judge_or_magistrate": "Published Judicial Officer",
    }
    return record


def _envelope(record: dict[str, Any], *, operation: str = "case") -> dict[str, Any]:
    query = ct._build_query(operation, {"fixture": True})
    return PublicRecordsResult.success(query, [record]).to_dict()


class _PartyClient:
    def search_parties(self, **_kwargs: Any):
        form = ct.parse_party_search_form(
            _fixture("party_search.html"),
            source_url=ct.PARTY_SEARCH_URL,
        )
        page = ct.parse_party_results(
            _fixture("party_results_50.html"),
            source_url=ct.PARTY_SEARCH_URL,
        )
        return form, page


def test_shared_router_preserves_within_display_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ct, "log_search", lambda *_args: None)
    first = ct.search_parties(
        last_name="EPSTEIN",
        limit=7,
        client=_PartyClient(),
    )
    assert first.status is ResultStatus.PARTIAL
    assert first.next_cursor is not None

    args = courts.build_parser().parse_args(
        [
            "search",
            "EPSTEIN",
            "--source",
            ct.SOURCE_ID,
            "--limit",
            "7",
            "--cursor",
            first.next_cursor,
        ]
    )
    translated = courts._connecticut_civil_family_args(args, "search")
    assert translated.limit == 7
    assert translated.cursor == first.next_cursor

    resumed = ct.execute(translated, client=_PartyClient())
    assert resumed.status is ResultStatus.PARTIAL
    assert len(resumed.records) == 7
    assert resumed.records[0]["party_name"] == "EPSTEIN ALEX 08"
    assert resumed.errors[0].code == "source_display_slice"


def test_shared_download_translation_supports_optional_docket(tmp_path: Path) -> None:
    parser = courts.build_parser()
    destination = tmp_path / "filing.pdf"
    without_docket = parser.parse_args(
        [
            "download",
            ct.SENTINEL_DOCUMENT_NUMBER,
            "--source",
            ct.SOURCE_ID,
            "--destination",
            str(destination),
        ]
    )
    direct = courts._connecticut_civil_family_args(
        without_docket,
        "document",
    )
    assert direct.document_number == ct.SENTINEL_DOCUMENT_NUMBER
    assert direct.docket is None
    assert direct.pdf_output == destination

    with_docket = parser.parse_args(
        [
            "download",
            ct.SENTINEL_DOCUMENT_NUMBER,
            "--source",
            ct.SOURCE_ID,
            "--case-number",
            ct.SENTINEL_DOCKET,
            "--destination",
            str(destination),
        ]
    )
    verified = courts._connecticut_civil_family_args(
        with_docket,
        "document",
    )
    assert verified.docket == ct.SENTINEL_DOCKET


def test_party_search_is_snapshot_only_and_never_links_same_name(
    tmp_path: Path,
) -> None:
    form, page = _PartyClient().search_parties()
    record = ct._normalize_party_occurrence(
        page.rows[0],
        page=page,
        form=form,
    )
    query = ct._build_query("party_search", {"last_name": "EPSTEIN"})
    envelope = PublicRecordsResult.failure(
        query,
        ResultStatus.PARTIAL,
        [
            PublicRecordsError(
                code="source_display_slice",
                message="fixed publisher display slice",
                category="source_completeness",
            )
        ],
        records=[record],
    ).to_dict()
    court_db = tmp_path / "courts.db"

    report = ingest.ingest_envelope(envelope, court_db=court_db)
    assert report["projected"]["cases"] == 0
    with sqlite3.connect(court_db) as db:
        assert db.execute("SELECT count(*) FROM source_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM case_record").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM case_party").fetchone()[0] == 0


def test_exact_case_projects_native_children_without_metadata_artifacts(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "courts.db"
    report = ingest.ingest_envelope(
        _envelope(_case_record()),
        court_db=court_db,
    )
    assert report["projected"]["cases"] == 1
    assert report["projected"]["parties"] == 2
    assert report["projected"]["docket_entries"] == 4
    assert report["projected"]["documents"] == 0

    with sqlite3.connect(court_db) as db:
        db.row_factory = sqlite3.Row
        case = db.execute("SELECT * FROM case_record").fetchone()
        assert case is not None
        assert case["raw_case_number"] == ct.SENTINEL_DOCKET
        assert case["status"] is None
        assert case["disposition_date"] == "2026-06-01"
        raw = json.loads(case["raw_json"])
        assert raw["connecticut_source_record"]["parties"][1][
            "publisher_party_number"
        ] == "D-01"

        parties = db.execute(
            "SELECT raw_name, role, core_entity_id, resolution_status "
            "FROM case_party ORDER BY sequence_no"
        ).fetchall()
        assert [row["role"] for row in parties] == ["Plaintiff", "Defendant"]
        assert all(row["core_entity_id"] is None for row in parties)
        assert all(row["resolution_status"] == "unreviewed" for row in parties)

        entry_ids = {
            row[0]
            for row in db.execute(
                "SELECT native_entry_id FROM docket_entry"
            ).fetchall()
        }
        assert "document:32503295" in entry_ids
        assert "entry:101.00" in entry_ids
        assert db.execute(
            "SELECT count(*) FROM document_artifact"
        ).fetchone()[0] == 0

        event_ids = {
            row[0]
            for row in db.execute(
                "SELECT native_event_id FROM case_event"
            ).fetchall()
        }
        assert "scheduled:17" in event_ids
        assert "notice:991" in event_ids
        assert any(value.startswith("STATECOURT:") for value in event_ids)
        assert any(value.startswith("disposition:") for value in event_ids)


def test_appearance_identity_survives_reordering_and_labels_duplicates() -> None:
    source_party = _case_record()["parties"][0]
    first = deepcopy(source_party["appearances"][0])
    second = {
        **first,
        "display_name_or_address": "SECOND COUNSEL (22) 2 MAIN STREET",
        "display_name": "SECOND COUNSEL",
        "publisher_juris_number": "22",
        "address_raw": "2 MAIN STREET",
    }
    party_a = deepcopy(source_party)
    party_a["appearances"] = [first, second, deepcopy(first)]
    party_b = deepcopy(source_party)
    party_b["appearances"] = [second, first, deepcopy(first)]

    ids_a = {
        item["source_entry_id"]
        for item in ingest._connecticut_party(party_a, index=0)["attorneys"]
    }
    ids_b = {
        item["source_entry_id"]
        for item in ingest._connecticut_party(party_b, index=0)["attorneys"]
    }
    assert ids_a == ids_b
    first_hash_ids = sorted(
        value
        for value in ids_a
        if value.rsplit(":", 1)[-1] in {"1", "2"}
        and "appearance:" in value
    )
    assert len(first_hash_ids) == 3
    duplicate_bases = [value.rsplit(":", 1)[0] for value in ids_a]
    assert len(duplicate_bases) == 3
    assert len(set(duplicate_bases)) == 2


def test_only_validated_download_with_docket_projects_artifact(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "courts.db"
    case_record = _case_record()
    ingest.ingest_envelope(_envelope(case_record), court_db=court_db)
    content = b"%PDF-1.7\nvalidated fixture\n%%EOF\n"
    artifact_path = tmp_path / "complaint.pdf"
    artifact_path.write_bytes(content)
    metadata = next(
        item
        for item in case_record["filing_documents"]
        if item["publisher_document_number"] == ct.SENTINEL_DOCUMENT_NUMBER
    )
    record = {
        "canonical_ref": ct._child_ref(
            ct.SENTINEL_DOCKET,
            "document",
            ct.SENTINEL_DOCUMENT_NUMBER,
        ),
        "source_id": ct.SOURCE_ID,
        "record_kind": "connecticut_case_filing_pdf",
        "docket": ct.SENTINEL_DOCKET,
        "publisher_document_number": ct.SENTINEL_DOCUMENT_NUMBER,
        "source_url": (
            f"{ct.DOCUMENT_URL}?DocumentNo={ct.SENTINEL_DOCUMENT_NUMBER}"
        ),
        "content_type": "application/pdf",
        "content_disposition": None,
        "byte_length": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "artifact_path": str(artifact_path),
        "filing_metadata": metadata,
    }
    envelope = PublicRecordsResult.success(
        ct._build_query("document", {"fixture": True}),
        [record],
        raw_artifact_refs=[str(artifact_path)],
    ).to_dict()

    ingest.ingest_envelope(envelope, court_db=court_db)
    ingest.ingest_envelope(envelope, court_db=court_db)
    with sqlite3.connect(court_db) as db:
        artifact = db.execute(
            "SELECT native_document_id, sha256, storage_path "
            "FROM document_artifact"
        ).fetchone()
        assert artifact == (
            ct.SENTINEL_DOCUMENT_NUMBER,
            hashlib.sha256(content).hexdigest(),
            str(artifact_path),
        )
        assert db.execute(
            "SELECT count(*) FROM document_artifact"
        ).fetchone()[0] == 1

    metadata_only = deepcopy(record)
    metadata_only["docket"] = None
    metadata_only["canonical_ref"] = None
    ingest.ingest_envelope(
        PublicRecordsResult.success(
            ct._build_query("document", {"fixture": "no-docket"}),
            [metadata_only],
            raw_artifact_refs=[str(artifact_path)],
        ).to_dict(),
        court_db=court_db,
    )
    with sqlite3.connect(court_db) as db:
        assert db.execute(
            "SELECT count(*) FROM document_artifact"
        ).fetchone()[0] == 1


def test_missing_download_bytes_cannot_create_artifact(tmp_path: Path) -> None:
    record = {
        "source_id": ct.SOURCE_ID,
        "record_kind": "connecticut_case_filing_pdf",
        "docket": ct.SENTINEL_DOCKET,
        "publisher_document_number": ct.SENTINEL_DOCUMENT_NUMBER,
        "source_url": (
            f"{ct.DOCUMENT_URL}?DocumentNo={ct.SENTINEL_DOCUMENT_NUMBER}"
        ),
        "content_type": "application/pdf",
        "byte_length": 10,
        "sha256": "0" * 64,
        "artifact_path": str(tmp_path / "missing.pdf"),
        "filing_metadata": {
            "publisher_document_number": ct.SENTINEL_DOCUMENT_NUMBER,
            "description": "COMPLAINT",
        },
    }
    with pytest.raises(ValueError, match="artifact is missing"):
        ingest.ingest_envelope(
            _envelope(record, operation="document"),
            court_db=tmp_path / "courts.db",
        )


def test_monitor_uses_fixed_budget_and_separates_rolling_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[Any] = []
    active_case = _case_record()

    class MonitorClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.request_count = 0
            created.append(self)

        def search_parties(self, **_kwargs: Any):
            self.request_count = 2
            return _PartyClient().search_parties()

        def fetch_case_bundle(self, docket: str) -> ct.CaseBundle:
            assert docket == ct.SENTINEL_DOCKET
            self.request_count = ct.PROBE_EXPECTED_REQUESTS
            return ct.CaseBundle(record=deepcopy(active_case))

        def close(self) -> None:
            return None

    monkeypatch.setattr(ct, "ConnecticutCivilFamilyClient", MonitorClient)
    context = monitor.ProbeContext(
        source_id=ct.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=10.0,
        max_attempts=3,
        sample_bytes=None,
    )
    first = monitor.probe_connecticut_civil_family(context)
    assert first.status == ResultStatus.OK.value
    assert created[-1].kwargs["request_budget"] == ct.PROBE_EXPECTED_REQUESTS
    assert created[-1].request_count == ct.PROBE_EXPECTED_REQUESTS
    assert first.details["completeness_contract"]["party_search"][
        "publisher_continuation_beyond_display"
    ] is False
    assert first.details["stable_contract"]["document_probe"] == {
        "metadata_checked": True,
        "pdf_downloaded": False,
    }

    active_case = deepcopy(active_case)
    active_case["caption"] = "ROLLING CAPTION CHANGE"
    second = monitor.probe_connecticut_civil_family(context)
    assert second.artifact_sha256 == first.artifact_sha256
    assert second.schema_sha256 == first.schema_sha256
    assert second.details["contract_hashes"] == first.details[
        "contract_hashes"
    ]
    assert second.details["rolling_observation"] != first.details[
        "rolling_observation"
    ]


def test_catalog_census_search_plan_source_report_and_citations(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    source_ids = {
        ct.SOURCE_ID,
        "us-ct-superior-court-civil-family-bulk-data",
        "us-ct-superior-court-clerk-record-requests",
    }
    with sqlite3.connect(catalog_path) as db:
        roles = db.execute(
            "SELECT a.source_id, t.role "
            "FROM source_census_target_sources a "
            "JOIN source_census_targets t USING(census_target_id) "
            "WHERE a.source_id IN (?, ?, ?) ORDER BY a.source_id, t.role",
            tuple(sorted(source_ids)),
        ).fetchall()
    assert set(roles) == {
        (ct.SOURCE_ID, "trial_case_index"),
        (
            "us-ct-superior-court-civil-family-bulk-data",
            "bulk_data_program",
        ),
        (
            "us-ct-superior-court-clerk-record-requests",
            "court_directory",
        ),
    }

    plan = build_search_plan(
        "EXAMPLE PERSON",
        jurisdictions=["09"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
    )
    tasks = {
        (task["source_id"], task["capability"])
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] in source_ids
    }
    assert {
        (ct.SOURCE_ID, "search_parties"),
        (ct.SOURCE_ID, "fetch_case"),
        (ct.SOURCE_ID, "list_docket_entries"),
        (ct.SOURCE_ID, "list_docket_documents"),
        (ct.SOURCE_ID, "fetch_document"),
        (
            "us-ct-superior-court-civil-family-bulk-data",
            "request_court_data",
        ),
        (
            "us-ct-superior-court-clerk-record-requests",
            "request_case_copy",
        ),
    } <= tasks

    report = source_report.check_public_records_catalog(catalog_path)
    rows = {
        value["source_id"]: value
        for value in report.values()
        if isinstance(value, dict) and value.get("source_id") in source_ids
    }
    assert rows[ct.SOURCE_ID]["status"] == "configured"
    assert rows[ct.SOURCE_ID]["query_tool"] == "tools/query_state_courts.py"
    assert rows[
        "us-ct-superior-court-civil-family-bulk-data"
    ]["status"] == "human_required"
    assert rows[
        "us-ct-superior-court-clerk-record-requests"
    ]["status"] == "human_required"

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"STATECOURT_SOURCE:{ct.SOURCE_ID}"] == (
        ct.PARTY_SEARCH_URL
    )
    assert source_urls[
        "STATECOURT_SOURCE:us-ct-superior-court-civil-family-bulk-data"
    ] == ct.BULK_DESCRIPTION_URL
    assert source_urls[
        "STATECOURT_SOURCE:us-ct-superior-court-clerk-record-requests"
    ] == ct.CLERK_DIRECTORY_URL
    assert monitor.HANDLER_REGISTRY[ct.SOURCE_ID].expected_requests == (
        ct.PROBE_EXPECTED_REQUESTS
    )
    assert set(courts.LIVE_ROUTES[ct.SOURCE_ID]) == {
        "search",
        "case",
        "docket",
        "documents",
        "download",
        "discovery",
        "probe",
    }
