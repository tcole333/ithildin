from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_georgia_property_sources as georgia
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.5},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _directory_probe_record(source_sha256: str) -> dict[str, Any]:
    return {
        "source_id": georgia.DIRECTORY_SOURCE_ID,
        "record_kind": "source_probe",
        "status": "ok",
        "row_count": 158,
        "expected_county_count": 159,
        "missing_counties": ["White"],
        "unexpected_counties": [],
        "route_disagreements": ["Atkinson"],
        "platform_counts": {
            "county_hosted": 20,
            "qpublic_legacy": 133,
            "qpublic_schneider": 5,
        },
        "source_url": georgia.DIRECTORY_URL,
        "source_document_sha256": source_sha256,
        "stable_schema_sha256": "1" * 64,
    }


def _gsccca_probe_record(component_marker: str) -> dict[str, Any]:
    return {
        "source_id": georgia.GSCCCA_SOURCE_ID,
        "record_kind": "source_probe",
        "status": "ok",
        "coverage": {
            "geography": "all Georgia counties",
            "deed_index_since_at_least": "1999-01-01",
            "historical_data": "continually_added",
            "search_dimensions": [
                "party_name",
                "property_subdivision_unit_block_lot",
                "county_book_page",
                "date_range",
                "party_type",
                "instrument_type",
                "county_or_region_or_statewide",
            ],
            "summary_fields": [
                "instrument_parties",
                "property_location",
                "deed_book",
                "deed_page",
            ],
        },
        "access": {
            "search_requires_account": True,
            "limited_use_account_cost": "no_cost",
            "limited_use_recurring_fee": False,
            "limited_use_summary_index_access": True,
            "limited_use_document_images": False,
            "registration_url": georgia.GSCCCA_REGISTRATION_URL,
            "search_url": georgia.GSCCCA_SEARCH_URL,
            "login_handoff_url": (
                "https://apps.gsccca.org/login.asp"
            ),
        },
        "component_sha256": {
            "information": component_marker * 64,
            "limited_use": component_marker * 64,
            "login_gate": component_marker * 64,
        },
        "stable_schema_sha256": "2" * 64,
    }


def test_monitors_separate_source_contracts_from_rolling_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        georgia.DIRECTORY_SOURCE_ID: "a",
        georgia.GSCCCA_SOURCE_ID: "b",
    }
    calls: list[str] = []

    def fake_execute(
        args: Any,
        **_: Any,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        calls.append(args.source)
        if args.source == georgia.DIRECTORY_SOURCE_ID:
            record = _directory_probe_record(
                rolling[args.source] * 64
            )
        else:
            record = _gsccca_probe_record(rolling[args.source])
        return PublicRecordsResult.success(
            georgia.build_query(args),
            [record],
        )

    monkeypatch.setattr(georgia, "execute", fake_execute)

    first_directory = public_records_monitor.probe_georgia_property_source(
        _context(georgia.DIRECTORY_SOURCE_ID)
    )
    first_gsccca = public_records_monitor.probe_georgia_property_source(
        _context(georgia.GSCCCA_SOURCE_ID)
    )
    rolling.update(
        {
            georgia.DIRECTORY_SOURCE_ID: "c",
            georgia.GSCCCA_SOURCE_ID: "d",
        }
    )
    second_directory = public_records_monitor.probe_georgia_property_source(
        _context(georgia.DIRECTORY_SOURCE_ID)
    )
    second_gsccca = public_records_monitor.probe_georgia_property_source(
        _context(georgia.GSCCCA_SOURCE_ID)
    )

    assert calls == [
        georgia.DIRECTORY_SOURCE_ID,
        georgia.GSCCCA_SOURCE_ID,
        georgia.DIRECTORY_SOURCE_ID,
        georgia.GSCCCA_SOURCE_ID,
    ]
    for first, second, requests_made in (
        (first_directory, second_directory, 1),
        (first_gsccca, second_gsccca, 3),
    ):
        assert first.status == "ok"
        assert first.schema_sha256 == second.schema_sha256
        assert first.artifact_sha256 == second.artifact_sha256
        assert first.details["stable_contract"] == (
            second.details["stable_contract"]
        )
        assert first.details["schema_contract"] == (
            second.details["schema_contract"]
        )
        assert first.details["artifact_identity"] == (
            second.details["artifact_identity"]
        )
        assert first.details["rolling_observation"] != (
            second.details["rolling_observation"]
        )
        assert first.details["requests_made"] == requests_made

    assert first_directory.result_count == 158
    assert first_directory.details["rolling_observation"][
        "missing_counties"
    ] == ["White"]
    assert first_directory.details["rolling_observation"][
        "route_disagreements"
    ] == ["Atkinson"]
    assert first_directory.details["rolling_observation"][
        "platform_counts"
    ] == {
        "county_hosted": 20,
        "qpublic_legacy": 133,
        "qpublic_schneider": 5,
    }

    assert first_gsccca.result_count == 1
    gsccca_contract = first_gsccca.details["stable_contract"]
    assert gsccca_contract["coverage"]["deed_index_since_at_least"] == (
        "1999-01-01"
    )
    assert gsccca_contract["access"][
        "limited_use_summary_index_access"
    ] is True
    assert gsccca_contract["access"]["limited_use_document_images"] is False


def test_catalog_and_census_preserve_complementary_source_roles(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    directory = catalog.show_source(
        georgia.DIRECTORY_SOURCE_ID
    )["current_manifest"]
    gsccca = catalog.show_source(
        georgia.GSCCCA_SOURCE_ID
    )["current_manifest"]

    assert catalog.require_machine_acquisition(
        georgia.DIRECTORY_SOURCE_ID
    )["allowed"] is True
    assert catalog.require_machine_acquisition(
        georgia.GSCCCA_SOURCE_ID
    )["allowed"] is True
    assert directory["stable_keys"] == [
        "county_geoid",
        "published_primary_url",
    ]
    assert gsccca["stable_keys"] == ["canonical_ref"]
    assert directory["identity_contract"]["source_identity_fields"] == [
        "source_id",
        "county_geoid",
        "published_primary_url",
    ]
    assert gsccca["identity_contract"]["source_identity_fields"] == [
        "canonical_ref"
    ]

    directory_capabilities = {
        item["name"]: item["details"]
        for item in directory["capabilities"]
    }
    gsccca_capabilities = {
        item["name"]: item["details"]
        for item in gsccca["capabilities"]
    }
    assert directory_capabilities["query_shared_property_records"][
        "shared_operations"
    ] == ["search", "discovery", "probe"]
    assert gsccca_capabilities["query_shared_property_records"][
        "shared_operations"
    ] == ["discovery", "probe"]
    assert directory_capabilities["ingest_property_records"][
        "projection"
    ] == "source_snapshot_only"
    assert gsccca_capabilities["ingest_property_records"][
        "projection"
    ] == "source_snapshot_only"

    directory_association = directory["census_associations"][0]
    assert directory_association["jurisdiction_geoid"] == "13"
    assert directory_association["role"] == "assessment_roll"
    assert directory_association["coverage"]["expected_county_count"] == 159
    assert directory_association["coverage"]["observed_county_count"] == 158
    assert directory["probe_evidence"]["observed_missing_counties"] == [
        "White"
    ]
    assert directory_association["coverage"][
        "observed_platform_counts"
    ] == {
        "county_hosted": 20,
        "qpublic_legacy": 133,
        "qpublic_schneider": 5,
    }
    assert directory["probe_evidence"][
        "observed_route_disagreements"
    ] == ["Atkinson"]

    gsccca_association = gsccca["census_associations"][0]
    assert gsccca_association["jurisdiction_geoid"] == "13"
    assert gsccca_association["role"] == "land_records_index"
    assert gsccca_association["coverage"]["county_coverage"] == (
        "all_159_counties"
    )
    assert gsccca_association["coverage"][
        "deed_index_since_at_least"
    ] == "1999-01-01"
    assert gsccca["publication_contract"][
        "limited_use_summary_index_access"
    ] is True
    assert gsccca["publication_contract"][
        "limited_use_document_images"
    ] is False
    assert georgia.DIRECTORY_SOURCE_ID in (
        gsccca["complementary_source_ids"]
    )
    assert (
        "county"
        in " ".join(gsccca_association["coverage_gaps"]).casefold()
    )


def test_monitor_registry_has_independent_request_budgets() -> None:
    directory = public_records_monitor.HANDLER_REGISTRY[
        georgia.DIRECTORY_SOURCE_ID
    ]
    gsccca = public_records_monitor.HANDLER_REGISTRY[
        georgia.GSCCCA_SOURCE_ID
    ]

    assert directory.handler is (
        public_records_monitor.probe_georgia_property_source
    )
    assert directory.endpoint == georgia.DIRECTORY_URL
    assert directory.expected_requests == 1
    assert directory.sentinel_record_count == 1

    assert gsccca.handler is (
        public_records_monitor.probe_georgia_property_source
    )
    assert gsccca.endpoint == georgia.GSCCCA_INFORMATION_URL
    assert gsccca.expected_requests == 3
    assert gsccca.sentinel_record_count == 1


def test_property_citation_urls_and_docs_cover_both_sources() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )

    assert source_urls[
        f"PROPERTY_SOURCE:{georgia.DIRECTORY_SOURCE_ID}"
    ] == georgia.DIRECTORY_URL
    assert source_urls[
        f"PROPERTY_SOURCE:{georgia.GSCCCA_SOURCE_ID}"
    ] == georgia.GSCCCA_INFORMATION_URL

    for relative_path in (
        "docs/modules/property.md",
        "docs/TOOL_REFERENCE.md",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert georgia.DIRECTORY_SOURCE_ID in content
        assert georgia.GSCCCA_SOURCE_ID in content
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "Georgia DOR county property-route discovery" in roadmap
    assert "GSCCCA statewide deed/lien/plat index" in roadmap
