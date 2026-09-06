from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import query_new_jersey_dca_property as dca
from tools import lead_tracker, query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURE_ROOT = Path("tests/fixtures/public_records/new_jersey_dca_property")


def _shared_args(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _records() -> list[dict]:
    payload = json.loads(
        (FIXTURE_ROOT / "search-results.json").read_text(encoding="utf-8")
    )
    page = dca.parse_odata_page(payload)
    fetched = dca.SearchFetch(
        records=page.records,
        next_cursor=None,
        observed_total=len(page.records),
        emitted_count=len(page.records),
        pages_fetched=1,
        response_field_fingerprint=page.response_field_fingerprint,
    )
    return [dca.normalize_building(record, fetch=fetched) for record in page.records]


def _envelope() -> dict:
    args = dca.build_parser().parse_args(
        ["registration", "0714", "--minimum-interval", "0"]
    )
    return PublicRecordsResult.success(
        dca.build_query(args),
        _records(),
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def test_shared_routes_preserve_dca_search_branches_and_bounds() -> None:
    routes = query_property.LIVE_ROUTES[dca.SOURCE_ID]

    account = routes["account"].translate(
        _shared_args(
            "account",
            "0714-002653",
            "--source",
            dca.SOURCE_ID,
            "--jurisdiction",
            "US-NJ",
        ),
        routes["account"].adapter_command,
    )
    assert account.command == "registration"
    assert account.registration == "0714-002653"
    assert account.limit is None

    automatic = routes["search"].translate(
        _shared_args(
            "search",
            "0714002653",
            "--source",
            dca.SOURCE_ID,
            "--limit",
            "12",
            "--max-records",
            "8",
        ),
        routes["search"].adapter_command,
    )
    assert automatic.command == "registration"
    assert automatic.limit == 12
    assert automatic.max_records == 8

    address = routes["address"].translate(
        _shared_args(
            "address",
            "Broadway",
            "--source",
            dca.SOURCE_ID,
        ),
        routes["address"].adapter_command,
    )
    assert address.command == "address"
    assert address.address == "Broadway"

    parcel = routes["parcel"].translate(
        _shared_args(
            "parcel",
            "441/61",
            "--source",
            dca.SOURCE_ID,
            "--jurisdiction",
            "34013",
        ),
        routes["parcel"].adapter_command,
    )
    assert parcel.command == "parcel"
    assert parcel.county == "ESSEX"
    assert parcel.block == "441"
    assert parcel.lot == "61"

    municipality = routes["search"].translate(
        _shared_args(
            "search",
            "Newark City",
            "--source",
            dca.SOURCE_ID,
            "--search-field",
            "municipality",
        ),
        routes["search"].adapter_command,
    )
    assert municipality.command == "search"
    assert municipality.municipality == "Newark City"
    assert municipality.address is None

    county = routes["search"].translate(
        _shared_args(
            "search",
            "Essex County",
            "--source",
            dca.SOURCE_ID,
            "--search-field",
            "county",
            "--county-fips",
            "013",
        ),
        routes["search"].adapter_command,
    )
    assert county.command == "parcel"
    assert county.county == "ESSEX"
    assert county.block is None
    assert county.lot is None

    assert set(routes) == {
        "account",
        "address",
        "parcel",
        "probe",
        "search",
    }


def test_shared_dca_parcel_requires_source_geography() -> None:
    route = query_property.LIVE_ROUTES[dca.SOURCE_ID]["parcel"]

    with pytest.raises(ValueError, match="require --county-fips"):
        route.translate(
            _shared_args(
                "parcel",
                "441/61",
                "--source",
                dca.SOURCE_ID,
            ),
            route.adapter_command,
        )

    with pytest.raises(ValueError, match="cover New Jersey"):
        route.translate(
            _shared_args(
                "parcel",
                "441/61",
                "--source",
                dca.SOURCE_ID,
                "--jurisdiction",
                "24",
            ),
            route.adapter_command,
        )

    address_route = query_property.LIVE_ROUTES[dca.SOURCE_ID]["address"]
    with pytest.raises(ValueError, match="does not apply a county filter"):
        address_route.translate(
            _shared_args(
                "address",
                "Broadway",
                "--source",
                dca.SOURCE_ID,
                "--jurisdiction",
                "34013",
            ),
            address_route.adapter_command,
        )

    search_route = query_property.LIVE_ROUTES[dca.SOURCE_ID]["search"]
    with pytest.raises(ValueError, match="does not apply a county filter"):
        search_route.translate(
            _shared_args(
                "search",
                "Newark City",
                "--source",
                dca.SOURCE_ID,
                "--search-field",
                "municipality",
                "--jurisdiction",
                "34013",
            ),
            search_route.adapter_command,
        )


def test_dca_projection_retains_regulatory_identity_without_title_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "property.db"
    search_db_path = tmp_path / "search-log.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", search_db_path)
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(search_db_path))

    report = ingest_property_envelope(_envelope(), db_path=db_path)

    assert report["projection_supported"] is True
    assert report["records_seen"] == 3
    assert report["records_ingested"] == 3
    assert report["records_preserved_without_projection"] == 0
    assert {record["building_registration_number"] for record in report["records"]} == {
        "0714002653001",
        "0714003383001",
        "0714003383002",
    }
    assert all(
        record["ownership_assertions_upserted"] == 0 for record in report["records"]
    )
    first_event_ids = {
        record["building_registration_number"]: record["event_id"]
        for record in report["records"]
    }

    repeated_report = ingest_property_envelope(_envelope(), db_path=db_path)
    assert {
        record["building_registration_number"]: record["event_id"]
        for record in repeated_report["records"]
    } == first_event_ids

    db = connect_property(db_path)
    try:
        events = db.execute(
            """
            SELECT native_event_id, source_record_id, record_kind, event_type,
                   status, jurisdiction_geoid, address_raw, raw_json
            FROM property_event
            WHERE source_id=?
            ORDER BY source_record_id
            """,
            (dca.SOURCE_ID,),
        ).fetchall()
        assert len(events) == 3
        assert tuple(events[0])[:6] == (
            "0714002653",
            "0714002653001",
            "property_registration_building",
            "bhi_property_registration",
            "Active",
            "34",
        )
        assert "BROADWAY" in events[0]["address_raw"]
        assert (
            json.loads(events[0]["raw_json"])["canonical_ref"]
            == (_records()[0]["canonical_ref"])
        )

        same_property_buildings = [
            row["source_record_id"]
            for row in events
            if row["native_event_id"] == "0714003383"
        ]
        assert same_property_buildings == [
            "0714003383001",
            "0714003383002",
        ]

        parties = db.execute(
            """
            SELECT role, raw_name, assertion_type
            FROM property_event_party
            ORDER BY event_party_id
            """
        ).fetchall()
        assert len(parties) == sum(
            bool(
                isinstance(record.get("registered_owner"), dict)
                and record["registered_owner"].get("name")
            )
            for record in _records()
        )
        assert all(row["role"] == "registered_owner" for row in parties)
        assert {row["assertion_type"] for row in parties} == {
            "dca_regulatory_registration_relationship_not_title"
        }

        links = db.execute(
            """
            SELECT parcel_id, link_method, evidence_json
            FROM property_event_parcel_link
            ORDER BY event_id
            """
        ).fetchall()
        assert all(row["parcel_id"] is None for row in links)
        assert all(
            row["link_method"] == "unresolved_published_map_taxlot" for row in links
        )
        assert json.loads(links[0]["evidence_json"])["state"] == ("candidate_only")

        representation = db.execute(
            """
            SELECT representation_kind, relationship, source_state
            FROM property_event_representation
            ORDER BY representation_id
            LIMIT 1
            """
        ).fetchone()
        assert tuple(representation) == (
            "dca_property_interest_detail",
            "property_interest_locator",
            "anonymous_html",
        )
        assert db.execute(
            "SELECT COUNT(*) FROM property_event_representation"
        ).fetchone()[0] == sum(bool(record.get("detail_url")) for record in _records())
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert (
            db.execute("SELECT COUNT(*) FROM property_event_parcel_link").fetchone()[0]
            == 3
        )
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[
            0
        ] == 2 * (1 + len(_records()))
    finally:
        db.close()

    local_args = _shared_args(
        "event",
        "0714002653001",
        "--jurisdiction",
        "34",
        "--property-db",
        str(db_path),
    )
    local_result = query_property._local_result(local_args)
    assert local_result.status.value == "ok"
    assert local_result.records[0]["canonical_ref"] == (_records()[0]["canonical_ref"])
    assert (
        local_result.records[0]["raw"]["registration"]["building_registration_number"]
        == "0714002653001"
    )
    db = lead_tracker.get_db()
    try:
        logged = db.execute("SELECT query_text, source, result_count FROM search_log").fetchone()
        assert logged["source"] == query_property.LOCAL_SOURCE_ID
        assert logged["result_count"] == 1
        assert json.loads(logged["query_text"])["query"]["operation"] == "event"
        assert db.execute("SELECT COUNT(*) FROM search_history").fetchone()[0] == 1
    finally:
        db.close()
