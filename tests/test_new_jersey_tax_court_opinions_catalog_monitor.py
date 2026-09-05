from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_new_jersey_tax_court_opinions as opinions
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _probe_record(
    *,
    published_count: int,
    unpublished_count: int,
    document_url: str,
    content_sha256: str,
) -> dict[str, Any]:
    operations: dict[str, dict[str, Any]] = {}
    for collection, count, schema in (
        ("published", published_count, "a" * 64),
        ("unpublished", unpublished_count, "b" * 64),
    ):
        operations[f"{collection}_index_direct"] = {
            "state": "edge_challenge",
            "error_code": "access_challenge",
        }
        operations[f"{collection}_index_reader"] = {
            "state": "available",
            "retrieval_transport": "reader_relay",
            "visible_count": min(count, opinions.PAGE_SIZE),
            "total_count": count,
            "total_pages": math.ceil(count / opinions.PAGE_SIZE),
            "schema_fingerprint": schema,
            "page_fingerprint": "c" * 64,
            "source_url": opinions.COLLECTIONS[collection]["url"],
        }
    operations["sample_document_direct"] = {
        "state": "edge_challenge",
        "error_code": "access_challenge",
    }
    operations["sample_document_reader"] = {
        "state": "available",
        "retrieval_transport": "reader_relay",
        "source_url": document_url,
        "media_type": "text/markdown",
        "source_media_type": "application/pdf",
        "page_count": 22,
        "content_hash_scope": "reader_extracted_text",
        "content_sha256": content_sha256,
        "content_size": 25_000,
    }
    return {
        "record_type": "source_probe",
        "source_id": opinions.SOURCE_ID,
        "operations": operations,
        "usable_index_transport": "reader_relay",
        "publisher_transport_separated": True,
    }


def test_opinion_monitor_hashes_contract_not_rolling_counts_or_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "published": 104,
        "unpublished": 374,
        "document_url": (
            "https://www.njcourts.gov/system/files/court-opinions/2026/000052-2025.pdf"
        ),
        "content_sha256": "d" * 64,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert log_results is False
        return PublicRecordsResult.success(
            opinions._query(args, parameters={}),
            [
                _probe_record(
                    published_count=rolling["published"],
                    unpublished_count=rolling["unpublished"],
                    document_url=rolling["document_url"],
                    content_sha256=rolling["content_sha256"],
                )
            ],
        )

    monkeypatch.setattr(opinions, "execute", fake_execute)
    context = ProbeContext(
        source_id=opinions.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = public_records_monitor.probe_new_jersey_tax_court_opinions(context)
    rolling.update(
        published=105,
        unpublished=377,
        document_url=(
            "https://www.njcourts.gov/system/files/court-opinions/2026/001111-2026.pdf"
        ),
        content_sha256="e" * 64,
    )
    second = public_records_monitor.probe_new_jersey_tax_court_opinions(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"] != (second.details["rolling_observation"])
    )
    assert (
        first.details["stable_contract"]["source"]["metadata"]["authority"]
        == "New Jersey Judiciary"
    )
    reader = first.details["stable_contract"]["transport_roles"]["reader_relay"]
    assert reader["publisher"] is False
    assert reader["counts_as_independent_corroboration"] is False
    assert len(first.details["stable_contract"]["alternative_routes"]) == 7
    assert first.details["artifact_identity"]["document_identity"] == (
        "exact_official_new_jersey_courts_url_path"
    )


def test_catalog_exposes_verified_opinion_contract_and_seven_routes(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    decision = catalog.require_machine_acquisition(opinions.SOURCE_ID)
    assert decision["allowed"] is True
    source = catalog.show_source(opinions.SOURCE_ID)
    manifest = source["current_manifest"]
    assert set(manifest["complementary_source_ids"]) == {
        "us-nj-courts-full-site-search",
        "us-nj-tax-case-public-access",
        "us-nj-tax-court-property-cases",
        "us-nj-tax-court-reports",
        "us-nj-local-property-assessment-sources",
        "us-nj-rutgers-court-opinions",
        "us-courtlistener-opinions",
    }
    assert manifest["probe_evidence"]["published_occurrences_observed"] == 104
    assert manifest["probe_evidence"]["unpublished_occurrences_observed"] == 374
    assert manifest["probe_evidence"]["counts_are_rolling_observations"] is True
    assert (
        manifest["transport_contract"]["reader_relay"][
            "counts_as_independent_corroboration"
        ]
        is False
    )

    full_site = catalog.show_source("us-nj-courts-full-site-search")
    assert (
        full_site["current_manifest"]["record_identity_source_id"] == opinions.SOURCE_ID
    )
    courtlistener = catalog.show_source("us-courtlistener-opinions")
    assert (
        courtlistener["current_manifest"]["record_identity_source_id"]
        == "us-courtlistener-api"
    )
    local_routes = catalog.show_source("us-nj-local-property-assessment-sources")
    assert (
        local_routes["current_manifest"]["probe_evidence"][
            "component_records_retain_their_own_source_identities"
        ]
        is True
    )

    spec = public_records_monitor.HANDLER_REGISTRY[opinions.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_new_jersey_tax_court_opinions
    assert spec.expected_requests == 6
    assert spec.sentinel_record_count == 1
