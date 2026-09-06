from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import (
    ingest_state_court_records,
    query_georgia_court_access as georgia,
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


def _envelope(
    source_id: str,
    records: list[dict],
) -> dict:
    query = PublicRecordsQuery(
        source=georgia.SOURCE_METADATA_BY_ID[source_id],
        jurisdiction=georgia.JURISDICTION,
        query=QueryMetadata(operation="search", parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T22:00:00Z",
    ).to_dict()


def test_shared_routes_map_search_provider_discovery_and_probe() -> None:
    eaccess_routes = query_state_courts.LIVE_ROUTES[
        georgia.EACCESS_SOURCE_ID
    ]
    efile_routes = query_state_courts.LIVE_ROUTES[
        georgia.EFILE_SOURCE_ID
    ]
    cursor = (
        "ga-aoc-court-access:v1:source:"
        f"{georgia.EACCESS_SOURCE_ID}:query:0123456789abcdef:"
        "snapshot:fedcba9876543210:offset:4"
    )

    eaccess = eaccess_routes["search"].translate(
        _shared_args(
            "search",
            "researchga",
            "--source",
            georgia.EACCESS_SOURCE_ID,
            "--jurisdiction",
            "GA",
            "--search-field",
            "provider",
            "--county",
            "Fulton",
            "--limit",
            "4",
            "--cursor",
            cursor,
        ),
        eaccess_routes["search"].adapter_command,
    )
    assert eaccess.command == "search"
    assert eaccess.source == georgia.EACCESS_SOURCE_ID
    assert eaccess.query_text == "*"
    assert eaccess.county == "Fulton"
    assert eaccess.provider == "researchga"
    assert eaccess.published_state is None
    assert eaccess.limit == 4
    assert eaccess.cursor == cursor

    efile = efile_routes["search"].translate(
        _shared_args(
            "search",
            "not-listed",
            "--source",
            georgia.EFILE_SOURCE_ID,
            "--search-field",
            "published-state",
            "--max-records",
            "7",
        ),
        efile_routes["search"].adapter_command,
    )
    assert efile.command == "search"
    assert efile.source == georgia.EFILE_SOURCE_ID
    assert efile.query_text == "*"
    assert efile.published_state == "not_listed"
    assert efile.limit == 7

    efile_provider = efile_routes["search"].translate(
        _shared_args(
            "search",
            "greenfiling_infotrack",
            "--source",
            georgia.EFILE_SOURCE_ID,
            "--search-field",
            "provider",
        ),
        efile_routes["search"].adapter_command,
    )
    assert efile_provider.provider == "greenfiling_infotrack"

    discovery = eaccess_routes["discovery"].translate(
        _shared_args(
            "discovery",
            "--source",
            georgia.EACCESS_SOURCE_ID,
            "--search-field",
            "providers",
        ),
        eaccess_routes["discovery"].adapter_command,
    )
    assert discovery.command == "providers"
    assert discovery.source == georgia.EACCESS_SOURCE_ID

    probe = efile_routes["probe"].translate(
        _shared_args(
            "probe",
            "--source",
            georgia.EFILE_SOURCE_ID,
            "--jurisdiction",
            "13",
        ),
        efile_routes["probe"].adapter_command,
    )
    assert probe.command == "probe"
    assert probe.source == georgia.EFILE_SOURCE_ID

    assert set(eaccess_routes) == {"search", "discovery", "probe"}
    assert set(efile_routes) == {"search", "discovery", "probe"}


def test_guidance_keeps_access_handoff_and_filing_snapshot_distinct() -> None:
    eaccess = query_state_courts._source_guidance(
        georgia.EACCESS_SOURCE_ID
    )
    efile = query_state_courts._source_guidance(
        georgia.EFILE_SOURCE_ID
    )

    assert eaccess["unified_operations"] == [
        "discovery",
        "probe",
        "search",
    ]
    assert eaccess["record_grain"] == (
        "current_case_access_acquisition_handoff"
    )
    assert eaccess["provider_ids"] == ["peachcourt", "researchga"]
    assert efile["unified_operations"] == [
        "discovery",
        "probe",
        "search",
    ]
    assert efile["record_grain"] == (
        "current_efile_provider_availability_entry"
    )
    assert efile["published_states"] == [
        "mandatory",
        "available",
        "not_listed",
    ]


def test_shared_routes_reject_unrepresented_case_and_provider_semantics() -> None:
    eaccess = query_state_courts.LIVE_ROUTES[
        georgia.EACCESS_SOURCE_ID
    ]["search"]
    with pytest.raises(ValueError, match="not published"):
        eaccess.translate(
            _shared_args(
                "search",
                "odyssey-efilega",
                "--source",
                georgia.EACCESS_SOURCE_ID,
                "--search-field",
                "provider",
            ),
            eaccess.adapter_command,
        )

    efile = query_state_courts.LIVE_ROUTES[
        georgia.EFILE_SOURCE_ID
    ]["search"]
    with pytest.raises(ValueError, match="directory fields"):
        efile.translate(
            _shared_args(
                "search",
                "*",
                "--source",
                georgia.EFILE_SOURCE_ID,
                "--case-type",
                "civil",
            ),
            efile.adapter_command,
        )

    discovery = query_state_courts.LIVE_ROUTES[
        georgia.EFILE_SOURCE_ID
    ]["discovery"]
    with pytest.raises(ValueError, match="does not apply county"):
        discovery.translate(
            _shared_args(
                "discovery",
                "--source",
                georgia.EFILE_SOURCE_ID,
                "--county",
                "Fulton",
            ),
            discovery.adapter_command,
        )


def test_shared_adapter_dispatches_source_specific_provider_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = query_state_courts.LIVE_ROUTES[
        georgia.EFILE_SOURCE_ID
    ]["discovery"]
    translated = route.translate(
        _shared_args(
            "discovery",
            "--source",
            georgia.EFILE_SOURCE_ID,
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
    assert captured["command"] == "providers"
    assert captured["source"] == georgia.EFILE_SOURCE_ID


@pytest.mark.parametrize(
    ("source_id", "record_kinds"),
    [
        (
            georgia.EACCESS_SOURCE_ID,
            [
                "case_access_acquisition_handoff",
                "court_provider_summary",
                "source_probe",
            ],
        ),
        (
            georgia.EFILE_SOURCE_ID,
            [
                "efile_provider_directory_entry",
                "court_provider_summary",
                "source_probe",
            ],
        ),
    ],
)
def test_provider_directory_rows_are_snapshot_only_with_zero_projection(
    tmp_path: Path,
    source_id: str,
    record_kinds: list[str],
) -> None:
    records = [
        {
            "canonical_ref": f"GA-AOC-ACCESS:{source_id}:{index}",
            "source_id": source_id,
            "record_kind": record_kind,
            "snapshot_only": True,
            "projection": {
                "projectable_as_case": False,
                "projectable_as_filing": False,
            },
            # Deliberate case-shaped values prove source-level dispatch
            # controls projection.
            "raw_case_number": f"NOT-A-CASE-{index}",
            "court": {
                "court_id": f"GA-COURT:13001:state:{index}",
                "name": "Directory Route",
            },
            "parties": [
                {
                    "raw_name": "NOT A CASE PARTY",
                    "role": "provider directory label",
                }
            ],
            "docket_entries": [
                {
                    "native_entry_id": f"not-a-docket-{index}",
                    "raw_text": "provider route snapshot",
                }
            ],
        }
        for index, record_kind in enumerate(record_kinds, start=1)
    ]
    envelope = _envelope(source_id, records)
    court_db = tmp_path / f"{source_id}.db"

    report = ingest_state_court_records.ingest_envelope(
        envelope,
        court_db=court_db,
    )

    assert all(value == 0 for value in report["projected"].values())
    assert report["snapshot_only"] == {
        "record_count": 3,
        "record_kinds": {
            record_kind: 1 for record_kind in sorted(record_kinds)
        },
    }
    assert report["canonical_refs"] == []

    db = connect_courts(court_db)
    try:
        assert db.execute(
            "SELECT COUNT(*) FROM source_snapshot"
        ).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM court").fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM case_record"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM case_party"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM docket_entry"
        ).fetchone()[0] == 0
        raw_json = db.execute(
            "SELECT raw_json FROM source_snapshot"
        ).fetchone()["raw_json"]
        assert json.loads(raw_json) == envelope
    finally:
        db.close()
