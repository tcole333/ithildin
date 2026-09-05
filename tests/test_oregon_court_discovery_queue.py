from __future__ import annotations

import sqlite3

import pytest

from tools import oregon_court_discovery_queue as discovery_queue_module
from tools.oregon_court_discovery_queue import (
    OregonCourtDiscoveryQueue,
    OregonCourtDiscoveryQueueError,
    main as discovery_queue_main,
)
from tools.public_records_catalog import PublicRecordsCatalog
from tools.query_oregon_court_directories import LOCAL_COURT_SOURCE_ID


def candidate(
    *,
    unique_id: str,
    item_id: str,
    name: str,
    url: str,
    city: str = "Bend",
) -> dict:
    return {
        "canonical_ref": f"ORCOURTDIR-DISCOVERY:url:{url}",
        "source_id": LOCAL_COURT_SOURCE_ID,
        "record_kind": "source_discovery_candidate",
        "candidate_kind": "official_local_court_website",
        "candidate_url": url,
        "candidate_host": "example.gov",
        "court": {
            "canonical_ref": (f"ORCOURTDIR:{LOCAL_COURT_SOURCE_ID}:{unique_id}"),
            "native_id": item_id,
            "name": name,
            "court_types": ["Municipal"],
            "counties": ["Deschutes"],
            "city": city,
        },
        "discovered_from": {
            "source_id": LOCAL_COURT_SOURCE_ID,
            "source_url": (
                "https://www.courts.oregon.gov/courts/Pages/other-courts.aspx"
            ),
            "list_name": "Municipal & Justice Court Registry",
            "view_id": "{9DFB7517-70A9-4D79-B6EB-0CF31F83E107}",
            "sharepoint_item_id": item_id,
            "sharepoint_unique_id": unique_id,
            "website_source_value": url,
            "created_at_source": "2020-01-01T00:00:00Z",
            "modified_at_source": "2026-01-01T00:00:00Z",
            "schema_fingerprint": "a" * 64,
        },
        "infra_request_created": False,
    }


def envelope(
    records: list[dict],
    *,
    retrieved_at: str,
    query: str | None = None,
    requested_limit: int | None = None,
    cursor: str | None = None,
    next_cursor: str | None = None,
    status: str = "ok",
) -> dict:
    return {
        "schema_version": "public-records-result/1.0",
        "retrieved_at": retrieved_at,
        "status": status,
        "query": {
            "schema_version": "public-records-query/1.0",
            "fingerprint": "b" * 64,
            "source": {
                "source_id": LOCAL_COURT_SOURCE_ID,
                "name": "Oregon Municipal and Justice Court Registry",
                "source_role": "municipal_and_justice_court_registry",
                "base_url": (
                    "https://www.courts.oregon.gov/courts/Pages/other-courts.aspx"
                ),
                "dataset_id": "oregon-ojd-sharepoint:test",
                "metadata": {},
            },
            "jurisdiction": {
                "jurisdiction_id": "41",
                "name": "Oregon",
                "country_code": "US",
                "state_code": "OR",
                "county_fips": None,
                "locality": None,
                "metadata": {},
            },
            "query": {
                "operation": "discovery",
                "parameters": {"query": query, "fields": ["all"]},
                "requested_limit": requested_limit,
                "cursor": cursor,
                "metadata": {},
            },
        },
        "records": records,
        "next_cursor": next_cursor,
        "raw_artifact_refs": [],
        "warnings": [],
        "errors": [],
    }


@pytest.fixture
def queue(tmp_path) -> OregonCourtDiscoveryQueue:
    return OregonCourtDiscoveryQueue(tmp_path / "catalog.db")


def test_cli_stats_does_not_require_list_limit(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "oregon_court_discovery_queue.py",
            "--db",
            str(tmp_path / "catalog.db"),
            "stats",
        ],
    )

    discovery_queue_main()

    assert '"candidates": 0' in capsys.readouterr().out


def test_assess_help_describes_structured_input(capsys):
    parser = discovery_queue_module.build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["assess", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "JSON object or @path to a JSON object" in help_text
    assert "JSON list of objects or @path to a JSON list" in help_text


def test_initialization_is_additive_and_repeatable(tmp_path):
    db_path = tmp_path / "catalog.db"
    PublicRecordsCatalog(db_path)
    queue = OregonCourtDiscoveryQueue(db_path)
    queue.sync_payload(
        envelope(
            [
                candidate(
                    unique_id="GUID-1",
                    item_id="15",
                    name="Bend Municipal Court",
                    url="http://court.example.gov/",
                )
            ],
            retrieved_at="2026-07-29T12:00:00Z",
        )
    )

    OregonCourtDiscoveryQueue(db_path)
    shown = queue.list_candidates()[0]

    assert shown["court"]["name"] == "Bend Municipal Court"
    db = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "sources" in tables
        assert "oregon_court_discovery_candidate" in tables
        assert (
            db.execute(
                """
                SELECT value FROM oregon_court_discovery_meta
                WHERE key='schema_version'
                """
            ).fetchone()[0]
            == "1"
        )
    finally:
        db.close()


def test_sync_is_idempotent_for_same_registry_snapshot(queue):
    payload = envelope(
        [
            candidate(
                unique_id="GUID-1",
                item_id="15",
                name="Bend Municipal Court",
                url="http://court.example.gov/",
            )
        ],
        retrieved_at="2026-07-29T12:00:00Z",
    )

    first = queue.sync_payload(payload)
    second = queue.sync_payload(payload)
    rows = queue.list_candidates()

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["updated"] == 1
    assert len(rows) == 1
    assert len(rows[0]["urls"]) == 1
    assert rows[0]["first_seen_at"] == "2026-07-29T12:00:00Z"
    assert rows[0]["last_seen_at"] == "2026-07-29T12:00:00Z"
    assert queue.stats()["sync_runs"] == 2


def test_url_change_preserves_identity_claim_and_assessment(queue):
    first = queue.sync_payload(
        envelope(
            [
                candidate(
                    unique_id="GUID-1",
                    item_id="15",
                    name="Bend Municipal Court",
                    url="http://old.example.gov/court/",
                )
            ],
            retrieved_at="2026-07-29T12:00:00Z",
        )
    )
    candidate_id = queue.list_candidates()[0]["candidate_id"]
    stable_key = queue.show(candidate_id)["stable_key"]
    queue.claim(
        candidate_id,
        claimed_by="agent:oregon",
        claimed_at="2026-07-29T12:05:00Z",
    )
    queue.assess(
        candidate_id,
        assessed_by="agent:oregon",
        assessed_at="2026-07-29T12:06:00Z",
        fields={
            "case_search": {
                "state": "found",
                "urls": ["http://old.example.gov/search"],
            },
            "vendor_family": {
                "name": "Example CMS",
                "evidence": ["http://old.example.gov/search"],
            },
        },
        complements=[
            {
                "kind": "official_request_route",
                "url": "http://old.example.gov/records",
            }
        ],
        summary="Official court website assessed",
    )

    second = queue.sync_payload(
        envelope(
            [
                candidate(
                    unique_id="GUID-1",
                    item_id="15",
                    name="Bend Municipal Court",
                    url="https://new.example.gov/municipal-court",
                )
            ],
            retrieved_at="2026-07-30T12:00:00Z",
        )
    )
    shown = queue.show(candidate_id)

    assert first["candidate_count"] == second["candidate_count"] == 1
    assert second["created"] == 0
    assert shown["stable_key"] == stable_key
    assert shown["claimed_by"] == "agent:oregon"
    assert shown["assessment"]["case_search"]["state"] == "found"
    assert shown["current_url"] == ("https://new.example.gov/municipal-court")
    assert {(url["normalized_url"], url["state"]) for url in shown["urls"]} == {
        ("http://old.example.gov/court", "stale"),
        ("https://new.example.gov/municipal-court", "active"),
    }


def test_complete_sync_marks_missing_candidates_stale_and_reactivates(queue):
    bend = candidate(
        unique_id="GUID-1",
        item_id="15",
        name="Bend Municipal Court",
        url="https://bend.example.gov/court",
    )
    salem = candidate(
        unique_id="GUID-2",
        item_id="16",
        name="Salem Municipal Court",
        url="https://salem.example.gov/court",
        city="Salem",
    )
    queue.sync_payload(
        envelope(
            [bend, salem],
            retrieved_at="2026-07-29T12:00:00Z",
        )
    )

    stale_sync = queue.sync_payload(
        envelope([bend], retrieved_at="2026-07-30T12:00:00Z")
    )
    stale_rows = queue.list_candidates(state="stale")

    assert stale_sync["candidates_staled"] == 1
    assert [row["court"]["name"] for row in stale_rows] == ["Salem Municipal Court"]

    reactivated = queue.sync_payload(
        envelope(
            [bend, salem],
            retrieved_at="2026-07-31T12:00:00Z",
        )
    )
    assert reactivated["reactivated"] == 1
    assert queue.list_candidates(state="stale") == []
    assert len(queue.list_candidates(state="active")) == 2


@pytest.mark.parametrize(
    "payload",
    [
        envelope(
            [],
            retrieved_at="2026-07-30T12:00:00Z",
            query="Bend",
        ),
        envelope(
            [],
            retrieved_at="2026-07-30T12:00:00Z",
            requested_limit=10,
        ),
        envelope(
            [],
            retrieved_at="2026-07-30T12:00:00Z",
            next_cursor="next",
        ),
        envelope(
            [],
            retrieved_at="2026-07-30T12:00:00Z",
            status="partial",
        ),
    ],
)
def test_filtered_partial_or_paginated_sync_cannot_retire_candidates(
    queue,
    payload,
):
    queue.sync_payload(
        envelope(
            [
                candidate(
                    unique_id="GUID-1",
                    item_id="15",
                    name="Bend Municipal Court",
                    url="https://bend.example.gov/court",
                )
            ],
            retrieved_at="2026-07-29T12:00:00Z",
        )
    )

    with pytest.raises(OregonCourtDiscoveryQueueError):
        queue.sync_payload(payload)

    assert len(queue.list_candidates(state="active")) == 1
    assert queue.stats()["sync_runs"] == 1


def test_claim_release_list_and_show_lifecycle(queue):
    queue.sync_payload(
        envelope(
            [
                candidate(
                    unique_id="GUID-1",
                    item_id="15",
                    name="Bend Municipal Court",
                    url="https://bend.example.gov/court",
                )
            ],
            retrieved_at="2026-07-29T12:00:00Z",
        )
    )
    candidate_id = queue.list_candidates()[0]["candidate_id"]

    claimed = queue.claim(
        candidate_id,
        claimed_by="agent:one",
        claimed_at="2026-07-29T12:05:00Z",
    )
    assert claimed["workflow_state"] == "claimed"
    assert (
        queue.list_candidates(
            workflow_state="claimed",
            claimed_by="agent:one",
        )[0]["candidate_id"]
        == candidate_id
    )
    with pytest.raises(
        OregonCourtDiscoveryQueueError,
        match="already claimed",
    ):
        queue.claim(candidate_id, claimed_by="agent:two")

    released = queue.release(
        candidate_id,
        released_by="agent:one",
        released_at="2026-07-29T12:10:00Z",
        notes="Assessment saved for later",
    )
    assert released["workflow_state"] == "pending"
    assert released["claimed_by"] is None
    assert [event["event_type"] for event in released["events"]] == [
        "discovered",
        "claimed",
        "released",
    ]


def test_structured_assessment_and_explicit_infra_link(queue, tmp_path):
    queue.sync_payload(
        envelope(
            [
                candidate(
                    unique_id="GUID-1",
                    item_id="15",
                    name="Bend Municipal Court",
                    url="https://bend.example.gov/court",
                )
            ],
            retrieved_at="2026-07-29T12:00:00Z",
        )
    )
    candidate_id = queue.list_candidates()[0]["candidate_id"]
    fields = {
        "case_search": {"state": "found", "urls": ["/cases"]},
        "calendars": {"state": "found", "urls": ["/calendar"]},
        "registers_dockets": {"state": "not_found"},
        "opinions_orders": {"state": "not_found"},
        "request_routes": {"state": "found", "urls": ["/records"]},
        "bulk_products": {"state": "not_found"},
        "vendor_family": {"name": "Example CMS", "confidence": "high"},
    }
    assessed = queue.assess(
        candidate_id,
        assessed_by="agent:one",
        assessed_at="2026-07-29T12:15:00Z",
        fields=fields,
        complements=[
            {
                "kind": "statewide_calendar",
                "source_id": "us-or-circuit-tax-court-calendars",
            }
        ],
        summary="All requested discovery dimensions assessed",
    )

    assert assessed["workflow_state"] == "assessed"
    assert {field: assessed["assessment"][field] for field in fields} == fields
    assert assessed["assessment"]["complements"][0]["kind"] == ("statewide_calendar")
    assert assessed["infra_requests"] == []

    investigation_db = tmp_path / "investigation.db"
    db = sqlite3.connect(investigation_db)
    try:
        db.execute(
            """
            CREATE TABLE infra_requests (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            INSERT INTO infra_requests(id, title, status)
            VALUES(501, 'Build Bend municipal case adapter', 'open')
            """
        )
        db.commit()
    finally:
        db.close()

    promoted = queue.link_infra_request(
        candidate_id,
        infra_request_id=501,
        linked_by="agent:one",
        linked_at="2026-07-29T12:20:00Z",
        investigation_db=investigation_db,
        notes="Selected after structured assessment",
    )
    queue.link_infra_request(
        candidate_id,
        infra_request_id=501,
        linked_by="agent:one",
        linked_at="2026-07-29T12:21:00Z",
        investigation_db=investigation_db,
        notes="Link refreshed",
    )

    assert promoted["workflow_state"] == "promoted"
    assert promoted["infra_requests"][0]["infra_request_id"] == 501
    assert len(queue.show(candidate_id)["infra_requests"]) == 1
    assert queue.stats()["promoted"] == 1
