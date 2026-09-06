from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import (
    ingest_state_court_records as ingest,
    query_georgia_supreme_publications as publications,
    query_state_courts,
)
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "georgia_supreme_publications"
)
RETRIEVED_AT = "2026-07-30T22:00:00Z"


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _artifact(
    name: str,
    source_id: str,
    *,
    application_type: str | None = None,
) -> publications.Artifact:
    return publications.Artifact(
        content=(FIXTURE_ROOT / name).read_bytes(),
        source_url=publications._page_url(
            source_id,
            2026,
            application_type=application_type,
        ),
        media_type="text/html",
        headers={"content-type": "text/html"},
    )


def _records(
    source_id: str,
    *,
    application_type: str | None = None,
) -> list[dict[str, Any]]:
    if source_id == publications.OPINION_SOURCE_ID:
        parsed = publications.parse_opinions_page(
            _artifact("opinions-2026.html", source_id),
            year=2026,
        )
    elif source_id == publications.CERT_GRANT_SOURCE_ID:
        parsed = publications.parse_certiorari_grants_page(
            _artifact("granted-2026.html", source_id),
            year=2026,
        )
    elif source_id == publications.CERT_DENIAL_SOURCE_ID:
        parsed = publications.parse_certiorari_denials_page(
            _artifact("denied-2026.html", source_id),
            year=2026,
        )
    else:
        assert application_type is not None
        parsed = publications.parse_application_grants_page(
            _artifact(
                f"{application_type}-2026.html",
                source_id,
                application_type=application_type,
            ),
            year=2026,
            application_type=application_type,
        )
    return [dict(record) for record in parsed.records]


def _envelope(
    source_id: str,
    operation: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=publications.SOURCE_METADATA[source_id],
        jurisdiction=publications.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def test_all_four_sources_expose_truthful_shared_publication_operations(
    tmp_path: Path,
) -> None:
    expected_operations = {
        "case",
        "discovery",
        "documents",
        "download",
        "probe",
        "search",
    }
    case_numbers = {
        publications.OPINION_SOURCE_ID: "S26A0062",
        publications.CERT_GRANT_SOURCE_ID: "S26G0537",
        publications.CERT_DENIAL_SOURCE_ID: "S26C0747",
        publications.APPLICATION_GRANT_SOURCE_ID: "S26D1454",
    }
    for source_id, case_number in case_numbers.items():
        routes = query_state_courts.LIVE_ROUTES[source_id]
        assert set(routes) == expected_operations
        assert "docket" not in routes

        exact_case = routes["case"].translate(
            _shared_args(
                "case",
                case_number,
                "--source",
                source_id,
            ),
            routes["case"].adapter_command,
        )
        documents = routes["documents"].translate(
            _shared_args(
                "documents",
                case_number,
                "--source",
                source_id,
            ),
            routes["documents"].adapter_command,
        )
        manifest = routes["discovery"].translate(
            _shared_args(
                "discovery",
                "manifest",
                "--source",
                source_id,
            ),
            routes["discovery"].adapter_command,
        )
        probe = routes["probe"].translate(
            _shared_args("probe", "--source", source_id),
            routes["probe"].adapter_command,
        )

        assert exact_case.command == "search"
        assert exact_case.source == source_id
        assert exact_case.query == "*"
        assert exact_case.case_number == case_number
        assert documents.command == "search"
        assert documents.case_number == case_number
        assert manifest.command == "manifest"
        assert manifest.source == source_id
        assert probe.command == "probe"
        assert probe.source == source_id
        assert query_state_courts._source_guidance(source_id)[
            "unified_operations"
        ] == sorted(expected_operations)

    destination = str(tmp_path / "S26G0537.pdf")
    url = (
        "https://www.gasupreme.us/wp-content/uploads/"
        "2026/07/s26c0537.pdf"
    )
    route = query_state_courts.LIVE_ROUTES[
        publications.CERT_GRANT_SOURCE_ID
    ]["download"]
    download = route.translate(
        _shared_args(
            "download",
            url,
            "--source",
            publications.CERT_GRANT_SOURCE_ID,
            "--destination",
            destination,
        ),
        route.adapter_command,
    )
    assert download.command == "download"
    assert download.document_url == url
    assert download.destination == destination

    with pytest.raises(ValueError, match="exact official PDF URL"):
        route.translate(
            _shared_args(
                "download",
                "S26G0537",
                "--source",
                publications.CERT_GRANT_SOURCE_ID,
                "--case-number",
                "S26G0537",
                "--destination",
                destination,
            ),
            route.adapter_command,
        )


def test_search_translation_retains_native_date_type_cursor_and_limit() -> None:
    route = query_state_courts.LIVE_ROUTES[
        publications.APPLICATION_GRANT_SOURCE_ID
    ]["search"]
    translated = route.translate(
        _shared_args(
            "search",
            "Amera Imaging",
            "--source",
            publications.APPLICATION_GRANT_SOURCE_ID,
            "--case-type",
            "discretionary",
            "--after",
            "2026-01-01",
            "--before",
            "2026-12-31",
            "--limit",
            "12",
        ),
        route.adapter_command,
    )

    assert translated.command == "search"
    assert translated.source == publications.APPLICATION_GRANT_SOURCE_ID
    assert translated.query == "Amera Imaging"
    assert translated.case_number is None
    assert translated.year == [2026]
    assert translated.date_from == "2026-01-01"
    assert translated.date_to == "2026-12-31"
    assert translated.application_type == "discretionary"
    assert translated.publication_type == [
        "discretionary_application_grant"
    ]
    assert translated.limit == 12


def test_multi_case_opinion_projects_each_case_without_inferred_parties(
    tmp_path: Path,
) -> None:
    record = _records(publications.OPINION_SOURCE_ID)[0]
    assert record["case_numbers"] == ["S26A0035", "S26A0036"]
    court_db = tmp_path / "courts.db"

    report = ingest.ingest_envelope(
        _envelope(publications.OPINION_SOURCE_ID, "search", [record]),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 2
    assert report["projected"]["docket_entries"] == 2
    assert report["projected"]["documents"] == 2
    assert report["projected"]["parties"] == 0
    assert report["snapshot_only"]["record_count"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = db.execute(
            """
            SELECT raw_case_number, caption, raw_json
            FROM case_record
            ORDER BY raw_case_number
            """
        ).fetchall()
        assert [row["raw_case_number"] for row in cases] == [
            "S26A0035",
            "S26A0036",
        ]
        assert {row["caption"] for row in cases} == {
            "RUCKER v. THE STATE (two cases)"
        }
        assert all(
            json.loads(row["raw_json"])["preserve_existing_case_fields"]
            is True
            for row in cases
        )
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 0

        entries = db.execute(
            "SELECT native_entry_id, raw_json FROM docket_entry"
        ).fetchall()
        assert len(entries) == 2
        assert {row["native_entry_id"] for row in entries} == {
            f"ga-supreme-publication:{record['publication_id']}"
        }
        for row in entries:
            event = json.loads(row["raw_json"])
            assert event["component_source_id"] == (
                publications.OPINION_SOURCE_ID
            )
            assert event["multi_case_identity"]["case_numbers"] == [
                "S26A0035",
                "S26A0036",
            ]
            assert "Final Copy" in event["version_notice"]
            assert "bound volumes" in event["version_notice"]

        documents = db.execute(
            """
            SELECT native_document_id, source_url
            FROM document_artifact
            """
        ).fetchall()
        assert len(documents) == 2
        assert {row["native_document_id"] for row in documents} == {
            record["document"]["native_document_id"]
        }
        assert {row["source_url"] for row in documents} == {
            record["document"]["source_url"]
        }
    finally:
        db.close()


def test_revision_identity_is_stable_and_retains_raw_and_normalized_state(
    tmp_path: Path,
) -> None:
    record = next(
        item
        for item in _records(publications.OPINION_SOURCE_ID)
        if item["primary_case_number"] == "S26A0062"
    )
    first = ingest._georgia_supreme_publication_projection_records(
        record,
        source_id=publications.OPINION_SOURCE_ID,
    )[0]
    second = ingest._georgia_supreme_publication_projection_records(
        record,
        source_id=publications.OPINION_SOURCE_ID,
    )[0]
    first_event = first["docket_entries"][0]
    second_event = second["docket_entries"][0]

    assert first_event["native_entry_id"] == second_event["native_entry_id"]
    assert first_event["revision_note_raw"] == (
        "7-1-2026 Substitute opinion issued."
    )
    normalized = first_event["normalized_revision_events"][0]
    assert normalized["event_type"] == "substitute_opinion_issued"
    assert normalized["event_dates_iso"] == ["2026-07-01"]
    assert normalized["native_revision_event_id"] == (
        second_event["normalized_revision_events"][0][
            "native_revision_event_id"
        ]
    )

    court_db = tmp_path / "courts.db"
    envelope = _envelope(
        publications.OPINION_SOURCE_ID,
        "search",
        [record],
    )
    ingest.ingest_envelope(envelope, court_db=court_db)
    ingest.ingest_envelope(envelope, court_db=court_db)
    db = sqlite3.connect(court_db)
    try:
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM docket_entry").fetchone()[0] == 1
        assert (
            db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0]
            == 1
        )
    finally:
        db.close()


def test_html_denial_projects_event_without_fake_document(
    tmp_path: Path,
) -> None:
    record = _records(publications.CERT_DENIAL_SOURCE_ID)[0]
    assert record["list_entry_has_document"] is False
    court_db = tmp_path / "courts.db"

    report = ingest.ingest_envelope(
        _envelope(
            publications.CERT_DENIAL_SOURCE_ID,
            "search",
            [record],
        ),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 1
    assert report["projected"]["related_cases"] == 1
    assert report["projected"]["case_relations"] == 1
    assert report["projected"]["docket_entries"] == 1
    assert report["projected"]["documents"] == 0
    assert report["projected"]["parties"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        event = db.execute(
            """
            SELECT event_type, document_available, raw_json
            FROM docket_entry
            """
        ).fetchone()
        assert event["event_type"] == "certiorari_denial"
        assert event["document_available"] == 0
        assert json.loads(event["raw_json"])[
            "ga_supreme_publication_source_occurrence"
        ]["list_entry_has_document"] is False
        assert (
            db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0]
            == 0
        )
    finally:
        db.close()


def test_linked_denial_supplement_is_projected_only_when_present(
    tmp_path: Path,
) -> None:
    record = _records(publications.CERT_DENIAL_SOURCE_ID)[-1]
    assert record["list_entry_has_document"] is True

    report = ingest.ingest_envelope(
        _envelope(
            publications.CERT_DENIAL_SOURCE_ID,
            "search",
            [record],
        ),
        court_db=tmp_path / "courts.db",
    )

    assert report["projected"]["documents"] == 2
    assert report["projected"]["related_cases"] == 1


def test_certiorari_crosswalk_is_typed_and_lower_pdf_keeps_origin(
    tmp_path: Path,
) -> None:
    record = _records(publications.CERT_GRANT_SOURCE_ID)[0]
    court_db = tmp_path / "courts.db"

    report = ingest.ingest_envelope(
        _envelope(
            publications.CERT_GRANT_SOURCE_ID,
            "search",
            [record],
        ),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 1
    assert report["projected"]["related_cases"] == 1
    assert report["projected"]["case_relations"] == 1
    assert report["projected"]["docket_entries"] == 1
    assert report["projected"]["documents"] == 2
    assert report["projected"]["parties"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        relation = db.execute(
            "SELECT relation_type, source_id, evidence_ref FROM case_relation"
        ).fetchone()
        assert dict(relation) == {
            "relation_type": "appealed_to",
            "source_id": publications.CERT_GRANT_SOURCE_ID,
            "evidence_ref": record["canonical_ref"],
        }

        documents = db.execute(
            """
            SELECT c.raw_case_number, d.source_url, d.document_type,
                   d.native_access_state
            FROM document_artifact AS d
            JOIN case_record AS c ON c.case_id=d.case_id
            ORDER BY c.raw_case_number
            """
        ).fetchall()
        assert [row["raw_case_number"] for row in documents] == [
            "A25A1237",
            "S26G0537",
        ]
        lower_case = json.loads(
            db.execute(
                """
                SELECT raw_json FROM case_record
                WHERE raw_case_number='A25A1237'
                """
            ).fetchone()[0]
        )
        relation_source = lower_case["relation_source"]
        assert relation_source["relation_type"] == (
            "originating_appellate_case"
        )
        assert relation_source["native_relation_type"] == (
            "certiorari_grant_originating_appellate_case"
        )
        assert relation_source["normalized_relation_type"] == "appealed_to"
        lower = relation_source["documents"][0]
        assert lower["originating_court"] == "Court of Appeals of Georgia"
        assert lower["originating_case_numbers"] == ["A25A1237"]
        assert lower["representation_role"] == (
            "originating_appellate_opinion_crosswalk"
        )
        assert lower["independent_corroboration"] is False
        assert lower["exact_document_identity"] == {
            "native_document_id": (
                record["lower_appellate_cases"][0]["native_document_id"]
            ),
            "source_url": (
                record["lower_appellate_cases"][0]["document_url"]
            ),
        }
        assert documents[0]["source_url"].endswith("/a25a1237.pdf")
        assert documents[0]["document_type"] == (
            "court_of_appeals_opinion_crosswalk"
        )
        assert documents[0]["native_access_state"] == (
            "official_linked_lower_appellate_representation"
        )
        assert documents[1]["source_url"].endswith("/s26c0537.pdf")
    finally:
        db.close()


def test_application_grant_types_remain_distinct_on_joint_case_orders(
    tmp_path: Path,
) -> None:
    discretionary = _records(
        publications.APPLICATION_GRANT_SOURCE_ID,
        application_type="discretionary",
    )[0]
    interlocutory = _records(
        publications.APPLICATION_GRANT_SOURCE_ID,
        application_type="interlocutory",
    )[0]

    report = ingest.ingest_envelope(
        _envelope(
            publications.APPLICATION_GRANT_SOURCE_ID,
            "search",
            [discretionary, interlocutory],
        ),
        court_db=tmp_path / "courts.db",
    )

    assert report["projected"]["cases"] == 5
    assert report["projected"]["docket_entries"] == 5
    assert report["projected"]["documents"] == 5
    assert report["projected"]["parties"] == 0

    db = sqlite3.connect(tmp_path / "courts.db")
    try:
        event_types = {
            row[0]
            for row in db.execute("SELECT event_type FROM docket_entry")
        }
        assert event_types == {
            "discretionary_application_grant",
            "interlocutory_application_grant",
        }
    finally:
        db.close()


def test_summary_manifest_probe_and_download_receipt_remain_snapshots(
    tmp_path: Path,
) -> None:
    summary = next(
        record
        for record in _records(publications.OPINION_SOURCE_ID)
        if record["record_kind"] == "noteworthy_opinion_summary_packet"
    )
    records = [
        summary,
        publications._source_inventory_record(
            publications.OPINION_SOURCE_ID
        ),
        {
            "record_kind": "source_probe",
            "source_id": publications.OPINION_SOURCE_ID,
            "status": "ok",
            "source_url": "https://www.gasupreme.us/2026-opinions/",
        },
        {
            "record_kind": "publication_document_download",
            "source_id": publications.OPINION_SOURCE_ID,
            "native_document_id": "wp-content/uploads/2026/06/s26a0035.pdf",
            "document_url": (
                "https://www.gasupreme.us/wp-content/uploads/"
                "2026/06/s26a0035.pdf"
            ),
            "sha256": "a" * 64,
            "byte_count": 1234,
        },
    ]

    report = ingest.ingest_envelope(
        _envelope(
            publications.OPINION_SOURCE_ID,
            "discovery",
            records,
        ),
        court_db=tmp_path / "courts.db",
    )

    assert report["projected"]["cases"] == 0
    assert report["projected"]["docket_entries"] == 0
    assert report["projected"]["documents"] == 0
    assert report["snapshot_only"] == {
        "record_count": 4,
        "record_kinds": {
            "noteworthy_opinion_summary_packet": 1,
            "publication_document_download": 1,
            "source_manifest": 1,
            "source_probe": 1,
        },
    }
