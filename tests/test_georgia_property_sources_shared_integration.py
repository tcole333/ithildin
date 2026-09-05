from __future__ import annotations

from pathlib import Path

import pytest

from tools import query_georgia_property_sources as georgia
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_property


def _shared_args(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _envelope(
    *,
    source_id: str,
    operation: str,
    records: list[dict],
) -> dict:
    query = PublicRecordsQuery(
        source=georgia.SOURCE_METADATA_BY_ID[source_id],
        jurisdiction=georgia.JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters={},
        ),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T18:30:00Z",
    ).to_dict()


def test_shared_directory_routes_translate_search_discovery_and_probe() -> None:
    routes = query_property.LIVE_ROUTES[georgia.DIRECTORY_SOURCE_ID]

    search = routes["search"].translate(
        _shared_args(
            "search",
            "qpublic",
            "--source",
            georgia.DIRECTORY_SOURCE_ID,
            "--jurisdiction",
            "13",
            "--limit",
            "10",
            "--max-records",
            "4",
        ),
        routes["search"].adapter_command,
    )
    assert search.command == "directory"
    assert search.query == "qpublic"
    assert search.limit == 4

    county = routes["search"].translate(
        _shared_args(
            "search",
            "Fulton County",
            "--source",
            georgia.DIRECTORY_SOURCE_ID,
            "--jurisdiction",
            "13121",
            "--search-field",
            "county",
        ),
        routes["search"].adapter_command,
    )
    assert county.command == "directory"
    assert county.query == "*"
    assert county.county == "Fulton"

    platform = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "qpublic_legacy",
            "--source",
            georgia.DIRECTORY_SOURCE_ID,
            "--search-field",
            "platform",
        ),
        routes["discovery"].adapter_command,
    )
    assert platform.command == "directory"
    assert platform.platform == "qpublic_legacy"

    platforms = routes["search"].translate(
        _shared_args(
            "search",
            "*",
            "--source",
            georgia.DIRECTORY_SOURCE_ID,
            "--search-field",
            "platforms",
        ),
        routes["search"].adapter_command,
    )
    assert platforms.command == "platforms"

    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "*",
            "--source",
            georgia.DIRECTORY_SOURCE_ID,
        ),
        routes["probe"].adapter_command,
    )
    assert probe.command == "probe"
    assert probe.source == georgia.DIRECTORY_SOURCE_ID
    assert set(routes) == {"discovery", "probe", "search"}


def test_shared_gsccca_route_is_discovery_handoff_not_index_search() -> None:
    routes = query_property.LIVE_ROUTES[georgia.GSCCCA_SOURCE_ID]

    handoff = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "--source",
            georgia.GSCCCA_SOURCE_ID,
            "--jurisdiction",
            "GA",
        ),
        routes["discovery"].adapter_command,
    )
    assert handoff.command == "handoff"

    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "*",
            "--source",
            georgia.GSCCCA_SOURCE_ID,
        ),
        routes["probe"].adapter_command,
    )
    assert probe.command == "probe"
    assert probe.source == georgia.GSCCCA_SOURCE_ID
    assert set(routes) == {"discovery", "probe"}

    with pytest.raises(ValueError, match="does not apply record selectors"):
        routes["discovery"].translate(
            _shared_args(
                "discovery",
                "SMITH",
                "--source",
                georgia.GSCCCA_SOURCE_ID,
            ),
            routes["discovery"].adapter_command,
        )


@pytest.mark.parametrize(
    ("source_id", "operation", "record", "expected_kind"),
    [
        (
            georgia.DIRECTORY_SOURCE_ID,
            "directory",
            {
                "canonical_ref": "GA-DOR-PROPERTY-ROUTE:13121",
                "source_id": georgia.DIRECTORY_SOURCE_ID,
                "record_kind": "county_property_source_route",
                "county_name": "Fulton",
                "county_geoid": "13121",
                "published_primary_url": "https://fultonassessor.org/",
                "published_description_url": "https://fultonassessor.org/",
                "platform_family": "county_hosted",
                "source_url": georgia.DIRECTORY_URL,
                "projection": {
                    "projectable_as_property_record": False,
                },
            },
            "county_property_source_route",
        ),
        (
            georgia.GSCCCA_SOURCE_ID,
            "handoff",
            {
                "canonical_ref": (
                    "GA-GSCCCA-REAL-ESTATE-INDEX:13/handoff"
                ),
                "source_id": georgia.GSCCCA_SOURCE_ID,
                "record_kind": "property_index_acquisition_handoff",
                "coverage": {"geography": "all Georgia counties"},
                "access": {
                    "search_requires_account": True,
                    "limited_use_account_cost": "no_cost",
                    "limited_use_summary_index_access": True,
                    "limited_use_document_images": False,
                },
                "source_urls": [
                    georgia.GSCCCA_INFORMATION_URL,
                    georgia.GSCCCA_LIMITED_USE_URL,
                    georgia.GSCCCA_LOGIN_GATE_URL,
                ],
                "projection": {
                    "projectable_as_property_record": False,
                },
            },
            "property_index_acquisition_handoff",
        ),
    ],
)
def test_ingestion_preserves_georgia_source_metadata_without_projection(
    tmp_path: Path,
    source_id: str,
    operation: str,
    record: dict,
    expected_kind: str,
) -> None:
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(
        _envelope(
            source_id=source_id,
            operation=operation,
            records=[record],
        ),
        db_path=db_path,
    )

    assert report["projection_supported"] is True
    assert report["records_seen"] == 1
    assert report["records_ingested"] == 0
    assert report["records_preserved_without_projection"] == 1
    skipped = report["projection_skips"][0]
    assert skipped["record_kind"] == expected_kind
    assert skipped["projection"] == "source_snapshot_observation_only"
    assert skipped["created_property_records"] == 0
    assert skipped["created_ownership_or_title_assertions"] == 0

    db = connect_property(db_path)
    try:
        rows = db.execute(
            """
            SELECT record_kind, source_native_id
            FROM source_observation
            WHERE source_id=?
            ORDER BY observation_id
            """,
            (source_id,),
        ).fetchall()
        assert [row["record_kind"] for row in rows] == [
            "query_envelope",
            expected_kind,
        ]
        assert rows[1]["source_native_id"] == record["canonical_ref"]

        jurisdictions = {
            row["geoid"]
            for row in db.execute(
                "SELECT geoid FROM jurisdiction ORDER BY geoid"
            )
        }
        expected_jurisdictions = {"13"}
        if source_id == georgia.DIRECTORY_SOURCE_ID:
            expected_jurisdictions.add("13121")
        assert jurisdictions == expected_jurisdictions

        for table in (
            "parcel_snapshot",
            "tax_account_event",
            "property_event",
            "recorded_instrument",
            "ownership_assertion",
        ):
            count = db.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            assert count == 0, table
    finally:
        db.close()


def test_shared_guidance_keeps_each_source_role_distinct() -> None:
    directory = query_property._source_guidance(
        georgia.DIRECTORY_SOURCE_ID
    )
    gsccca = query_property._source_guidance(georgia.GSCCCA_SOURCE_ID)

    assert directory["unified_operations"] == [
        "discovery",
        "probe",
        "search",
    ]
    assert "rather than parcels" in directory["note"]
    assert directory["official_complements"] == [
        georgia.GSCCCA_SOURCE_ID
    ]

    assert gsccca["unified_operations"] == ["discovery", "probe"]
    assert "does not represent" in gsccca["note"]
    assert gsccca["official_complements"] == [
        georgia.DIRECTORY_SOURCE_ID
    ]
