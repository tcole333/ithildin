from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_washington_digital_archives_land as land
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=land.SOURCE_ID,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _snapshot(marker: int) -> dict[str, Any]:
    return {
        "schema_contract": {
            "inventory_record_fields": [
                "county_key",
                "label_matches_inventory",
                "title",
                "title_id",
            ],
            "title_schema_fingerprint": "a" * 64,
            "title_record_fields": [
                "image_availability",
                "provenance",
                "record_count",
                "title",
                "title_id",
            ],
            "search_schema_fingerprint": "b" * 64,
            "search_record_fields": [
                "last_name",
                "native_record_id",
                "native_result_ordinal",
            ],
            "detail_schema_fingerprint": "c" * 64,
            "detail_record_fields": [
                "digital_objects",
                "native_record_id",
                "parties",
                "title_id",
            ],
            "party_fields": ["last_name", "party_type", "sequence_no"],
            "legal_fields": ["parcel"],
            "digital_object_fields": [
                "availability",
                "delivery_operation",
                "native_digital_object_id",
            ],
        },
        "rolling_observation": {
            "inventory": {
                "discovered_title_count": 26,
                "discovered_title_ids": sorted(
                    title.title_id for title in land.TITLES
                ),
                "missing_verified_title_ids": [],
                "new_title_ids": [],
                "titles": [
                    {
                        "title_id": title.title_id,
                        "title": f"{title.county} {2026 + marker}",
                        "county_key": title.key,
                        "label_matches_inventory": marker == 1,
                    }
                    for title in land.TITLES
                ],
            },
            "title": {
                "title_id": 93,
                "title": f"Adams County Auditor {2026 + marker}",
                "coverage_label": f"1988-{2026 + marker}",
                "record_count": 89_823 + marker,
                "image_availability": "some_images",
                "document_types_text": f"DEED {marker}",
            },
            "search": {
                "total_count": marker,
                "page_count": 1,
                "page_size": 50,
                "returned_count": 1,
                "sentinel_present": True,
                "records": [{"native_record_id": land.TITLES[0].sentinel_record_id}],
            },
            "detail": {
                "native_record_id": land.TITLES[0].sentinel_record_id,
                "title_id": 93,
                "county_geoid": "53001",
                "reference_number": f"rolling-{marker}",
                "recording_date": f"202{marker}-01-01",
                "document_type": "DEED",
                "parties": [
                    {
                        "sequence_no": 1,
                        "party_type": "Grantor",
                        "last_name": "ACME HOLDINGS, LLC",
                    }
                ],
                "legal": {"parcel": f"parcel-{marker}"},
                "digital_objects": [],
                "document_delivery": {"state": "site_recaptcha_queue"},
            },
            "image_generation_invoked": False,
        },
        "requests_made": 5,
    }


def test_monitor_keeps_growing_counts_years_and_values_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = 1

    def fake_snapshot(_context: ProbeContext) -> dict[str, Any]:
        return _snapshot(marker)

    monkeypatch.setattr(
        public_records_monitor,
        "_washington_digital_archives_land_snapshot",
        fake_snapshot,
    )
    first = public_records_monitor.probe_washington_digital_archives_land(
        _context()
    )
    marker = 2
    second = public_records_monitor.probe_washington_digital_archives_land(
        _context()
    )

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["schema_contract"] == second.details["schema_contract"]
    assert first.details["artifact_identity"] == second.details[
        "artifact_identity"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.details["requests_made"] == 5
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.details["stable_schema_sha256"] == sha256_fingerprint(
        first.details["schema_contract"]
    )

    stable = first.details["stable_contract"]
    assert stable["coverage"]["statewide"] is False
    assert all(
        set(title_contract)
        == {"county_key", "county", "county_geoid", "title_id"}
        for title_contract in stable["coverage"]["titles"]
    )
    assert stable["image_delivery"]["included_in_monitor"] is False
    assert stable["image_delivery"]["page_count_before_acquisition"] is None
    assert stable["identity"][
        "source_published_party_names_preserved_intact"
    ] is True
    assert set(stable["lineages"]) == {
        "archive_index",
        "archive_gap_recorders",
        "assessor_complements",
        "statewide_parcels",
    }

    comparison = compare_probes(
        {
            "probe_id": 1,
            "status": first.status,
            "schema_sha256": first.schema_sha256,
            "artifact_sha256": first.artifact_sha256,
        },
        {
            "probe_id": 2,
            "status": second.status,
            "schema_sha256": second.schema_sha256,
            "artifact_sha256": second.artifact_sha256,
        },
    )
    assert comparison["drift_detected"] is False


def test_monitor_snapshot_uses_only_anonymous_metadata_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    sentinel = land.TITLES_BY_KEY["adams"]

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def fetch_title_list(self) -> list[dict[str, Any]]:
            calls.append("inventory")
            return [
                {
                    "title_id": title.title_id,
                    "title": title.title,
                    "county_key": title.key,
                    "label_matches_inventory": True,
                }
                for title in land.TITLES
            ]

        def fetch_title(self, title_id: int) -> dict[str, Any]:
            calls.append("title")
            assert title_id == sentinel.title_id
            return {
                "title_id": title_id,
                "title": sentinel.title,
                "record_count": sentinel.record_count,
                "image_availability": sentinel.image_availability,
                "document_types_text": "DEED; MORTGAGE",
                "provenance": {"schema_fingerprint": "a" * 64},
            }

        def start_search(self, payload: dict[str, Any]) -> SimpleNamespace:
            calls.append("search_start")
            assert payload["TitleID"] == sentinel.title_id
            return SimpleNamespace(search_id=7)

        def fetch_results(
            self,
            search_id: int,
            *,
            page: int,
            page_size: int,
        ) -> SimpleNamespace:
            calls.append("search_results")
            assert (search_id, page, page_size) == (7, 1, 50)
            return SimpleNamespace(
                records=(
                    {
                        "native_record_id": sentinel.sentinel_record_id,
                        "native_result_ordinal": 1,
                        "last_name": "SMITH",
                    },
                ),
                total_count=1,
                page_count=1,
                page_size=50,
                schema_fingerprint="b" * 64,
            )

        def fetch_detail(self, record_id: str) -> dict[str, Any]:
            calls.append("detail")
            assert record_id == sentinel.sentinel_record_id
            return {
                "native_record_id": record_id,
                "title_id": sentinel.title_id,
                "county_geoid": sentinel.county_geoid,
                "reference_number": "324744",
                "recording_date": "2020-01-01",
                "document_type": "DEED",
                "parties": [
                    {
                        "sequence_no": 1,
                        "party_type": "Grantor",
                        "last_name": "ACME HOLDINGS, LLC",
                    }
                ],
                "legal": {"parcel": ";1-935-23-055-0101;"},
                "digital_objects": [
                    {
                        "native_digital_object_id": (
                            "910A2CA838DCC45F1AC4363BBCF36D5B"
                        ),
                        "availability": "available_for_site_generation",
                        "delivery_operation": {
                            "path": land.DIGITAL_OBJECT_QUEUE_PATH,
                            "state": "site_recaptcha_queue",
                        },
                    }
                ],
                "document_delivery": {
                    "state": "site_recaptcha_queue",
                    "direct_download_url": None,
                },
                "provenance": {"schema_fingerprint": "c" * 64},
            }

    monkeypatch.setattr(land, "DigitalArchivesClient", FakeClient)
    snapshot = (
        public_records_monitor._washington_digital_archives_land_snapshot(
            _context()
        )
    )

    assert calls == [
        "inventory",
        "title",
        "search_start",
        "search_results",
        "detail",
    ]
    assert snapshot["requests_made"] == 5
    rolling = snapshot["rolling_observation"]
    assert rolling["image_generation_invoked"] is False
    assert rolling["detail"]["parties"][0]["last_name"] == (
        "ACME HOLDINGS, LLC"
    )
    artifact = rolling["detail"]["digital_objects"][0]
    assert artifact["metadata_only"] is True
    assert artifact["sha256"] is None
    assert artifact["storage_path"] is None
    assert artifact["page_count"] is None
    assert artifact["rights_tier"] == "official_archive_image_uncertified"


def test_catalog_census_monitor_and_shared_operation_lifecycle(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    decision = catalog.require_machine_acquisition(land.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["limits"] == {}
    detail = catalog.show_source(land.SOURCE_ID)
    manifest = detail["current_manifest"]

    covered_geoids = {title.county_geoid for title in land.TITLES}
    gap_geoids = {
        alternative.county_geoid
        for alternative in land.RECORDER_ALTERNATIVES
    }
    assert len(covered_geoids) == 26
    assert len(gap_geoids) == 13
    assert covered_geoids.isdisjoint(gap_geoids)
    assert len(covered_geoids | gap_geoids) == 39
    assert {item["geoid"] for item in detail["jurisdictions"]} == covered_geoids
    assert manifest["source_coverage"]["statewide"] is False
    assert set(manifest["source_coverage"]["county_geoids"]) == covered_geoids
    assert set(manifest["source_coverage"]["archive_gap_geoids"]) == gap_geoids
    assert len(manifest["source_coverage"]["title_inventory"]) == 26
    assert manifest["operation_access"] == {
        "title_inventory": "anonymous",
        "title_metadata": "anonymous",
        "search_and_browse": "anonymous_session",
        "record_detail": "anonymous",
        "document_generation": "site_recaptcha_queue",
    }
    assert manifest["publication_contract"]["listed_digital_object"][
        "page_count_before_acquisition"
    ] is None
    assert manifest["publication_contract"]["listed_digital_object"][
        "rights_tier"
    ] == "official_archive_image_uncertified"
    assert manifest["probe_evidence"]["digital_object_sentinel"][
        "page_count"
    ] is None
    assert manifest["probe_evidence"]["digital_object_sentinel"][
        "metadata_only_until_bytes_acquired"
    ] is True
    assert manifest["identity_contract"][
        "source_published_party_names_preserved_intact"
    ] is True

    capabilities = {
        capability["name"]: capability["details"]
        for capability in manifest["capabilities"]
    }
    assert capabilities["query_shared_property_records"][
        "shared_operations"
    ] == ["instrument", "owner", "search"]
    assert capabilities["probe_source"]["operations"] == [
        "inventory",
        "title",
        "search",
        "detail",
    ]
    assert capabilities["probe_source"]["excluded_operation"] == (
        "document_generation_queue"
    )
    assert {
        complement["kind"] for complement in manifest["official_complements"]
    } == {
        "county_recorder_routes_for_archive_gaps",
        "assessor_parcel_search",
        "statewide_current_parcels",
    }

    associations = manifest["census_associations"]
    assert len(associations) == 1
    association = associations[0]
    assert association["jurisdiction_geoid"] == "53"
    assert association["role"] == "land_records_index"
    assert association["coverage"]["statewide"] is False
    assert set(association["coverage"]["county_geoids"]) == covered_geoids
    target = census.list_targets(
        state="WA",
        domain="property",
        role="land_records_index",
    )[0]
    assert land.SOURCE_ID in target["source_ids"]

    audit = audit_catalog(db_path=catalog_path)
    shared_mismatches = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert land.SOURCE_ID not in shared_mismatches

    handler = public_records_monitor.HANDLER_REGISTRY[land.SOURCE_ID]
    assert handler.handler is (
        public_records_monitor.probe_washington_digital_archives_land
    )
    assert handler.expected_requests == 5
    assert handler.sentinel_record_count == 1
    assert handler.sample_bytes is None


def test_docs_and_citation_preserve_archive_and_complement_boundaries() -> None:
    source_urls = json.loads(
        (
            ROOT / "web" / "src" / "data" / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[f"PROPERTY_SOURCE:{land.SOURCE_ID}"] == (
        "https://digitalarchives.wa.gov/Collections"
    )

    property_docs = (
        ROOT / "docs" / "modules" / "property.md"
    ).read_text(encoding="utf-8")
    tool_reference = (
        ROOT / "docs" / "TOOL_REFERENCE.md"
    ).read_text(encoding="utf-8")
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    for content in (property_docs, tool_reference, roadmap):
        assert land.SOURCE_ID in content
        assert "26" in content
        assert "13" in content
        assert "Ferry TaxSifter" in content
        assert "metadata-only" in content
    assert "Skamania 2014-2015 gap" in property_docs
    assert "official_archive_image_uncertified" in property_docs
