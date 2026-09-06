from __future__ import annotations

from pathlib import Path
from typing import Any

from tools import (
    ingest_state_court_records as ingest,
    query_florida_ninth_opinions as ninth,
    query_state_courts,
)
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import PublicRecordsResult


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "florida_ninth_opinions"
)


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _artifact(name: str) -> ninth.Artifact:
    return ninth.Artifact(
        content=(FIXTURE_ROOT / name).read_bytes(),
        source_url=f"{ninth.INDEX_URL}?search=Orange%20County&page=0",
        media_type="text/html",
        headers={"content-type": "text/html"},
    )


def test_shared_search_preserves_keyword_limit_and_cursor() -> None:
    route = query_state_courts.LIVE_ROUTES[ninth.SOURCE_ID]["search"]
    translated = route.translate(
        _shared_args(
            "search",
            "Orange County",
            "--source",
            ninth.SOURCE_ID,
            "--jurisdiction",
            "FL",
            "--limit",
            "7",
            "--cursor",
            "fl-ninth-opinions:v1:continuation",
        ),
        route.adapter_command,
    )

    assert route.adapter is ninth
    assert translated.command == "search"
    assert translated.query == "Orange County"
    assert translated.limit == 7
    assert translated.cursor == "fl-ninth-opinions:v1:continuation"


def test_opinion_index_occurrences_are_explicitly_snapshot_only(
    tmp_path: Path,
) -> None:
    parsed = ninth.parse_index_page(_artifact("page-0.html"), requested_page=0)
    query = ninth.build_query(
        ninth.build_parser().parse_args(
            ["search", "Orange County", "--limit", "2"]
        )
    )
    envelope = PublicRecordsResult.success(
        query,
        list(parsed.records),
    ).to_dict()

    report = ingest_envelope(
        envelope,
        court_db=tmp_path / "courts.db",
    )

    assert report["projected"]["cases"] == 0
    assert report["snapshot_only"] == {
        "record_count": 2,
        "record_kinds": {"circuit_appellate_opinion_index": 2},
    }
    assert ingest.FLORIDA_NINTH_OPINIONS_SOURCE_ID == ninth.SOURCE_ID


def test_shared_guidance_keeps_archive_and_complements_distinct() -> None:
    guidance = query_state_courts._source_guidance(ninth.SOURCE_ID)

    assert set(query_state_courts.LIVE_ROUTES[ninth.SOURCE_ID]) == {"search"}
    assert guidance["unified_operations"] == ["search"]
    assert guidance["court_id"] == ninth.COURT_ID
    assert "direct official PDF" in guidance["note"]
    assert "Orange County clerk dockets" in guidance["note"]
