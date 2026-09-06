from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import (
    ingest_state_court_records,
    query_georgia_court_directory as georgia,
    query_state_courts,
)
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_courts


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def _envelope(records: list[dict]) -> dict:
    query = PublicRecordsQuery(
        source=georgia.SOURCE_METADATA,
        jurisdiction=georgia.JURISDICTION,
        query=QueryMetadata(
            operation="search",
            parameters={"directory_section": "Superior Court Clerks"},
        ),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T20:00:00Z",
    ).to_dict()


def test_shared_routes_preserve_search_cursor_and_exact_detail_semantics() -> None:
    routes = query_state_courts.LIVE_ROUTES[georgia.SOURCE_ID]
    cursor = (
        "ga-aoc-directory:v1:query:12d9eb0d7ca669f3:"
        "size:25:page:2:row:4"
    )

    search = routes["search"].translate(
        _shared_args(
            "search",
            "Robinson",
            "--source",
            georgia.SOURCE_ID,
            "--jurisdiction",
            "GA",
            "--first-name",
            "Marla",
            "--county",
            "Fulton",
            "--limit",
            "3",
            "--page-size",
            "25",
            "--cursor",
            cursor,
        ),
        routes["search"].adapter_command,
    )
    assert search.command == "search"
    assert search.first == "Marla"
    assert search.last == "Robinson"
    assert search.county == "Fulton"
    assert search.limit == 3
    assert search.page_size == 25
    assert search.cursor == cursor
    assert search.details is False
    assert search.all is False

    section = routes["search"].translate(
        _shared_args(
            "search",
            "Superior Court Clerks",
            "--source",
            georgia.SOURCE_ID,
            "--search-field",
            "directory-section",
            "--max-records",
            "7",
        ),
        routes["search"].adapter_command,
    )
    assert section.directory_section == "Superior Court Clerks"
    assert section.court_class is None
    assert section.limit == 7

    detail = routes["detail"].translate(
        _shared_args(
            "detail",
            "58af01d3ce9168f520c4cec9",
            "--source",
            georgia.SOURCE_ID,
        ),
        routes["detail"].adapter_command,
    )
    assert detail.command == "detail"
    assert detail.record_id == "58af01d3ce9168f520c4cec9"
    assert not hasattr(detail, "cursor")


def test_shared_discovery_and_probe_map_to_bounded_source_operations() -> None:
    routes = query_state_courts.LIVE_ROUTES[georgia.SOURCE_ID]

    discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "--source",
            georgia.SOURCE_ID,
            "--search-field",
            "manifest",
        ),
        routes["discovery"].adapter_command,
    )
    assert discovery.command == "manifest"

    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "--source",
            georgia.SOURCE_ID,
            "--jurisdiction",
            "13",
        ),
        routes["probe"].adapter_command,
    )
    assert probe.command == "probe"
    assert probe.max_attempts == 3
    assert set(routes) == {"detail", "discovery", "probe", "search"}

    guidance = query_state_courts._source_guidance(georgia.SOURCE_ID)
    assert guidance["unified_operations"] == [
        "detail",
        "discovery",
        "probe",
        "search",
    ]
    assert guidance["record_grain"] == (
        "current_court_personnel_directory_entry"
    )
    assert "directory_section" in guidance["search_fields"]


def test_shared_route_rejects_unrepresented_geography_and_case_semantics() -> None:
    route = query_state_courts.LIVE_ROUTES[georgia.SOURCE_ID]["search"]

    with pytest.raises(ValueError, match="use --county"):
        route.translate(
            _shared_args(
                "search",
                "Robinson",
                "--source",
                georgia.SOURCE_ID,
                "--jurisdiction",
                "13121",
            ),
            route.adapter_command,
        )

    with pytest.raises(ValueError, match="do not expose case type"):
        route.translate(
            _shared_args(
                "search",
                "Robinson",
                "--source",
                georgia.SOURCE_ID,
                "--case-type",
                "civil",
            ),
            route.adapter_command,
        )

    with pytest.raises(ValueError, match="requires an explicit --source"):
        query_state_courts.execute(_shared_args("probe"))


def test_shared_adapter_dispatches_translated_exact_detail(monkeypatch) -> None:
    route = query_state_courts.LIVE_ROUTES[georgia.SOURCE_ID]["detail"]
    translated = route.translate(
        _shared_args(
            "detail",
            "58af01d3ce9168f520c4cec9",
            "--source",
            georgia.SOURCE_ID,
        ),
        route.adapter_command,
    )
    captured = {}
    sentinel = object()

    def fake_execute(args):
        captured.update(vars(args))
        return sentinel

    monkeypatch.setattr(georgia, "execute", fake_execute)
    returned = route.adapter.execute(
        translated,
        access_decision={"allowed": True},
    )

    assert returned is sentinel
    assert captured["command"] == "detail"
    assert captured["record_id"] == "58af01d3ce9168f520c4cec9"


def test_all_georgia_directory_records_remain_snapshot_only(
    tmp_path: Path,
) -> None:
    records = [
        {
            "canonical_ref": (
                "GA-AOC-COURT-PERSONNEL:58af01d3ce9168f520c4cec9"
            ),
            "source_id": georgia.SOURCE_ID,
            "record_kind": "court_personnel_directory_entry",
            "native_record_id": "58af01d3ce9168f520c4cec9",
            "snapshot_only": True,
            "snapshot_state": "detail",
            "person": {
                "prefix_or_title": "Chief Deputy Clerk",
                "first": "Marla",
                "last": "Robinson",
            },
            "raw_fields": {
                "detail": {
                    "id": "58af01d3ce9168f520c4cec9",
                    "field_19_raw": ["Superior Court Clerks"],
                }
            },
            # Incidental case-shaped values must never project this directory
            # observation into a case or party.
            "raw_case_number": "NOT-A-CASE",
            "court": {
                "court_id": "ga-test-court",
                "name": "Georgia Test Court",
            },
            "parties": [
                {
                    "raw_name": "NOT A CASE PARTY",
                    "role": "directory subject",
                }
            ],
        },
        {
            "canonical_ref": (
                f"STATECOURT:{georgia.SOURCE_ID}/manifest"
            ),
            "source_id": georgia.SOURCE_ID,
            "record_kind": "source_manifest",
            "snapshot_only": True,
        },
        {
            "canonical_ref": f"STATECOURT:{georgia.SOURCE_ID}/probe",
            "source_id": georgia.SOURCE_ID,
            "record_kind": "source_probe",
            "snapshot_only": True,
        },
    ]
    envelope = _envelope(records)
    court_db = tmp_path / "georgia-directory.db"

    report = ingest_state_court_records.ingest_envelope(
        envelope,
        court_db=court_db,
    )

    assert all(value == 0 for value in report["projected"].values())
    assert report["snapshot_only"] == {
        "record_count": 3,
        "record_kinds": {
            "court_personnel_directory_entry": 1,
            "source_manifest": 1,
            "source_probe": 1,
        },
    }
    assert report["canonical_refs"] == []

    db = connect_courts(court_db)
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM court").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 0
        snapshot = db.execute(
            "SELECT raw_json FROM source_snapshot"
        ).fetchone()
        assert json.loads(snapshot["raw_json"]) == envelope
    finally:
        db.close()
