from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import (
    query_michigan_property_directories as michigan,
    query_property,
)
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURE_ROOT = Path(
    "tests/fixtures/public_records/michigan_property_directory"
)
DIRECTORY_HTML = (FIXTURE_ROOT / "directory.html").read_text(
    encoding="utf-8"
)


class FakeClient:
    def __init__(
        self,
        page: michigan.MichiganPropertyDirectoryPage,
    ) -> None:
        self.page = page
        self.calls = 0

    def fetch(self) -> michigan.MichiganPropertyDirectoryPage:
        self.calls += 1
        return self.page


def _shared_args(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _page() -> michigan.MichiganPropertyDirectoryPage:
    return michigan.parse_directory_page(
        DIRECTORY_HTML,
        require_complete=False,
    )


def _source_result(*values: str) -> PublicRecordsResult:
    parsed = michigan.build_parser().parse_args(list(values))
    result = michigan.execute(
        parsed,
        client=FakeClient(_page()),
        log_results=False,
    )
    return PublicRecordsResult.success(
        result.query,
        result.records,
        retrieved_at="2026-07-30T16:30:00Z",
        next_cursor=result.next_cursor,
        raw_artifact_refs=result.raw_artifact_refs,
        warnings=result.warnings,
    )


def test_shared_routes_expose_directory_search_discovery_and_probe() -> None:
    routes = query_property.LIVE_ROUTES[michigan.SOURCE_ID]

    search = routes["search"].translate(
        _shared_args(
            "search",
            "Oakland",
            "--source",
            michigan.SOURCE_ID,
            "--jurisdiction",
            "US-MI",
            "--limit",
            "10",
            "--max-records",
            "4",
        ),
        routes["search"].adapter_command,
    )
    assert search.command == "search"
    assert search.query == "Oakland"
    assert search.limit == 4

    county = routes["search"].translate(
        _shared_args(
            "search",
            "Oakland County",
            "--source",
            michigan.SOURCE_ID,
            "--jurisdiction",
            "26125",
            "--search-field",
            "county",
        ),
        routes["search"].adapter_command,
    )
    assert county.command == "list"
    assert county.county == "Oakland County"
    assert county.limit is None

    platform_summary = routes["search"].translate(
        _shared_args(
            "search",
            "bsa_online",
            "--source",
            michigan.SOURCE_ID,
            "--search-field",
            "platforms",
        ),
        routes["search"].adapter_command,
    )
    assert platform_summary.command == "platforms"
    assert platform_summary.platform == "bsa_online"

    discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "Genesee",
            "--source",
            michigan.SOURCE_ID,
            "--limit",
            "2",
        ),
        routes["discovery"].adapter_command,
    )
    assert discovery.command == "discovery"
    assert discovery.query == "Genesee"
    assert discovery.limit == 2

    county_discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "--source",
            michigan.SOURCE_ID,
            "--jurisdiction",
            "26125",
        ),
        routes["discovery"].adapter_command,
    )
    assert county_discovery.command == "discovery"
    assert county_discovery.county == "26125"

    platform_discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "bsa_online",
            "--source",
            michigan.SOURCE_ID,
            "--search-field",
            "platform",
        ),
        routes["discovery"].adapter_command,
    )
    assert platform_discovery.command == "discovery"
    assert platform_discovery.platform == "bsa_online"

    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "*",
            "--source",
            michigan.SOURCE_ID,
        ),
        routes["probe"].adapter_command,
    )
    assert probe.command == "probe"
    assert set(routes) == {"discovery", "probe", "search"}


def test_shared_route_rejects_geography_conflicts_and_property_semantics() -> None:
    routes = query_property.LIVE_ROUTES[michigan.SOURCE_ID]

    with pytest.raises(ValueError, match="accept state context"):
        routes["search"].translate(
            _shared_args(
                "search",
                "Oakland",
                "--source",
                michigan.SOURCE_ID,
                "--jurisdiction",
                "55",
            ),
            routes["search"].adapter_command,
        )

    with pytest.raises(ValueError, match="conflicts"):
        routes["search"].translate(
            _shared_args(
                "search",
                "Wayne",
                "--source",
                michigan.SOURCE_ID,
                "--jurisdiction",
                "26125",
                "--search-field",
                "county",
            ),
            routes["search"].adapter_command,
        )

    with pytest.raises(ValueError, match="must be any"):
        routes["search"].translate(
            _shared_args(
                "search",
                "123 Main",
                "--source",
                michigan.SOURCE_ID,
                "--search-field",
                "address",
            ),
            routes["search"].adapter_command,
        )

    assert "map" not in routes
    assert "parcel" not in routes
    assert "owner" not in routes
    assert "sale" not in routes
    assert "instrument" not in routes


def test_ingestion_retains_directory_rows_without_property_assertions(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    envelope = _source_result("list").to_dict()

    report = ingest_property_envelope(envelope, db_path=db_path)

    assert report["projection_supported"] is True
    assert report["records_seen"] == 5
    assert report["records_ingested"] == 0
    assert report["records_preserved_without_projection"] == 5
    assert len(report["projection_skips"]) == 5
    assert {
        skipped["reason"] for skipped in report["projection_skips"]
    } == {"michigan_directory_metadata_has_no_property_event_semantics"}
    assert all(
        skipped["projection"] == "source_discovery_observation_only"
        for skipped in report["projection_skips"]
    )
    assert all(
        skipped["created_property_records"] == 0
        and skipped["created_ownership_or_title_assertions"] == 0
        for skipped in report["projection_skips"]
    )

    db = connect_property(db_path)
    try:
        observations = db.execute(
            """
            SELECT source_native_id, record_kind, source_url,
                   schema_fingerprint, raw_json
            FROM source_observation
            WHERE source_id=?
            ORDER BY observation_id
            """,
            (michigan.SOURCE_ID,),
        ).fetchall()
        assert len(observations) == 6
        assert observations[0]["record_kind"] == "query_envelope"
        route_rows = [
            row
            for row in observations
            if row["record_kind"] == "county_tax_parcel_route"
        ]
        assert len(route_rows) == 5
        genesee = next(
            row
            for row in route_rows
            if row["source_native_id"].endswith(":26049")
        )
        genesee_raw = json.loads(genesee["raw_json"])
        assert genesee["source_url"] == michigan.DIRECTORY_URL
        assert len(genesee["schema_fingerprint"]) == 64
        assert genesee_raw["publisher_declared_role"]["role"] == (
            "parcel_geometry"
        )
        assert (
            genesee_raw["destination_triage"][
                "signals_are_verified_capabilities"
            ]
            is False
        )
        assert genesee_raw["destination_triage"]["route_signals"] == [
            "recording_office"
        ]
        assert (
            "declared_parcel_role_destination_signal_mismatch"
            in genesee_raw["destination_triage"]["review_flags"]
        )

        jurisdictions = {
            row["geoid"]
            for row in db.execute(
                "SELECT geoid FROM jurisdiction ORDER BY geoid"
            )
        }
        assert jurisdictions == {
            "26",
            "26001",
            "26011",
            "26049",
            "26071",
            "26125",
        }
        for table in (
            "parcel_snapshot",
            "tax_account_event",
            "property_event",
            "recorded_instrument",
            "ownership_assertion",
        ):
            count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0, table
    finally:
        db.close()


def test_discovery_candidate_ingestion_preserves_evidence_strength(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    envelope = _source_result(
        "discovery",
        "--query",
        "Genesee",
    ).to_dict()

    report = ingest_property_envelope(envelope, db_path=db_path)

    assert report["records_seen"] == 1
    assert report["records_ingested"] == 0
    skipped = report["projection_skips"][0]
    assert skipped["record_kind"] == "source_discovery_candidate"
    assert skipped["destination_verified_roles"] == []
    assert (
        "declared_parcel_role_destination_signal_mismatch"
        in skipped["review_flags"]
    )

    db = connect_property(db_path)
    try:
        observation = db.execute(
            """
            SELECT source_native_id, record_kind, source_url, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind='source_discovery_candidate'
            """,
            (michigan.SOURCE_ID,),
        ).fetchone()
        assert observation is not None
        assert observation["source_native_id"].startswith(
            "MI-PROPERTY-DISCOVERY:"
        )
        assert observation["source_url"] == michigan.DIRECTORY_URL
        raw = json.loads(observation["raw_json"])
        evidence = raw["capability_evidence"]
        assert evidence["publisher_declared_roles"] == ["parcel_geometry"]
        assert evidence["destination_verified_roles"] == []
        assert evidence["route_signals"] == ["recording_office"]
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[
            0
        ] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM ownership_assertion"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_shared_guidance_states_directory_role_boundaries() -> None:
    guidance: dict[str, Any] = query_property._source_guidance(
        michigan.SOURCE_ID
    )

    assert guidance["mode"] == (
        "unified_live_county_property_source_discovery"
    )
    assert guidance["unified_operations"] == [
        "discovery",
        "probe",
        "search",
    ]
    assert "not parcels" in guidance["note"]
    assert "Genesee" in guidance["note"]
